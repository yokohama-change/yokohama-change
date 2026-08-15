import importlib.util
import unittest
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "enrich_status.py"
spec = importlib.util.spec_from_file_location("status_enrichment", p)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
JST = timezone(timedelta(hours=9))


def item(title="案件"):
    return {
        "title": title,
        "source_updated": "Tue, 21 Jul 2026 08:00:00 GMT",
        "commercial_score": 90,
        "opportunity_type": "受注機会",
        "category": "入札・調達",
    }


class StatusEnrichmentTests(unittest.TestCase):
    def check_closed(self, text, title, deadline):
        facts = s.extract_facts(text, item(title), date(2026, 8, 14))
        out = s.classify_status(facts, date(2026, 8, 14), datetime(2026, 8, 14, 10, 0, tzinfo=JST))
        self.assertEqual(out["participation_deadline"], deadline)
        self.assertFalse(out["is_open_now"])

    def test_live_yokohama_deadline_not_hearing(self):
        self.check_closed("""ヒアリング実施日 2026年9月1日
申込について
提出書類 参加意向申出書（第１号様式）
提出期間 令和８年７月28日(火曜日)17時まで（必着）
申込期限
2026年7月28日
関連資料について
質問書 提出期限 令和８年８月６日17時まで""", "Live！横浜2027", "2026-07-28")

    def test_solar_window_deadline_not_question(self):
        self.check_closed("""申込について
提出書類 参加意向申出書（様式１）
提出期間 令和８年８月４日(火曜日)午後５時まで（必着）
申込期限
質問書 提出期限 令和８年８月19日（水曜日）午後５時まで""", "次世代型太陽電池", "2026-08-04")

    def test_learning_video_deadline_not_bid_date(self):
        self.check_closed("""入札開始日 2026年8月24日
申込について
提出書類 公募型指名競争入札参加意向申出書
提出期間 2026年８月７日午後５時まで
申込期限
2026年8月7日
指名・非指名通知日 2026年８月19日まで""", "学習動画", "2026-08-07")

    def test_range_uses_end_date(self):
        self.check_closed("""申込について
提出書類 参加意向申出書
提出期間 令和８年７月14日から令和８年７月31日午後５時まで
申込期限
参加資格確認結果通知
提案書 提出期限 令和８年10月２日午後５時まで""", "学校再エネ", "2026-07-31")

    def test_open_future_date(self):
        facts = s.extract_facts("""申込について
提出書類 参加意向申出書
提出期間 令和８年８月20日午後５時まで
申込期限
2026年8月20日
関連資料について""", item("受付中"), date(2026, 8, 14))
        out = s.classify_status(facts, date(2026, 8, 14), datetime(2026, 8, 14, 10, 0, tzinfo=JST))
        self.assertTrue(out["is_open_now"])
        self.assertEqual(out["participation_deadline"], "2026-08-20")

    def test_same_day_before_5pm_is_open(self):
        facts = s.extract_facts("""申込について
提出書類 参加意向申出書
提出期間 令和８年８月14日午後5時まで（必着）
関連資料について""", item("本日17時"), date(2026, 8, 14))
        out = s.classify_status(facts, date(2026, 8, 14), datetime(2026, 8, 14, 16, 59, tzinfo=JST))
        self.assertTrue(out["is_open_now"])
        self.assertIn("T17:00", out["participation_deadline_at"])

    def test_same_day_after_5pm_is_closed(self):
        facts = s.extract_facts("""申込について
提出書類 参加意向申出書
提出期間 令和８年８月14日午後5時まで（必着）
関連資料について""", item("本日17時"), date(2026, 8, 14))
        out = s.classify_status(facts, date(2026, 8, 14), datetime(2026, 8, 14, 17, 1, tzinfo=JST))
        self.assertFalse(out["is_open_now"])
        self.assertEqual(out["application_status"], "参加締切済")

    def test_ambiguous_future_date_never_open(self):
        facts = s.extract_facts("ヒアリング実施日 2026年9月1日 提案書提出期限 2026年8月30日", item("曖昧案件"), date(2026, 8, 14))
        out = s.classify_status(facts, date(2026, 8, 14), datetime(2026, 8, 14, 10, 0, tzinfo=JST))
        self.assertEqual(out["application_status"], "判定不可")
        self.assertIsNone(out["is_open_now"])

    def test_result_marker(self):
        facts = s.extract_facts("""申込について
参加意向申出書 提出期限 2026年7月1日まで
特定結果掲載""", item("【特定結果掲載】案件"), date(2026, 8, 14))
        out = s.classify_status(facts, date(2026, 8, 14), datetime(2026, 8, 14, 10, 0, tzinfo=JST))
        self.assertEqual(out["application_status"], "結果掲載済")
        self.assertFalse(out["is_open_now"])

    def test_employment_false_positive_is_excluded(self):
        job = item("【総務局】会計年度任用職員（入札参加資格審査に係る事務補助等）（令和８年10月１日採用）")
        self.assertTrue(s.is_employment_notice(job))
        self.assertFalse(s.is_candidate(job))

    def test_open_metadata(self):
        x = {"is_open_now": True, "participation_deadline": "2026-08-18", "commercial_score": 87}
        s.enrich_open_metadata(x, date(2026, 8, 15))
        self.assertEqual(x["days_left"], 3)
        self.assertEqual(x["deadline_label"], "残り3日")
        self.assertEqual(x["priority_tier"], "最優先")


if __name__ == "__main__":
    unittest.main()
