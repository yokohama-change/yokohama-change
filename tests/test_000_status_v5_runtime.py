import base64
import gzip
import importlib.util
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_FILE = ROOT / "scripts" / "status_v5_payload.py"
LIVE = ROOT / "scripts" / "enrich_status.py"

# bootstrap.yml writes its bundled legacy classifier before running tests.
# Restore the verified conservative classifier first on every scheduled run.
spec_payload = importlib.util.spec_from_file_location("status_v5_payload", PAYLOAD_FILE)
payload_mod = importlib.util.module_from_spec(spec_payload)
spec_payload.loader.exec_module(payload_mod)
verified = gzip.decompress(base64.b64decode(payload_mod.PAYLOAD))
if not LIVE.exists() or LIVE.read_bytes() != verified:
    LIVE.write_bytes(verified)

spec = importlib.util.spec_from_file_location("status_enrichment_v5", LIVE)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def item(title="案件"):
    return {"title": title, "source_updated": "Tue, 21 Jul 2026 08:00:00 GMT"}


class StatusV5RuntimeTests(unittest.TestCase):
    def check_closed(self, text, title, deadline):
        facts = s.extract_facts(text, item(title), date(2026, 8, 14))
        out = s.classify_status(facts, date(2026, 8, 14))
        self.assertEqual(out["participation_deadline"], deadline)
        self.assertFalse(out["is_open_now"])

    def test_live_yokohama(self):
        self.check_closed("""ヒアリング実施日 2026年9月1日
申込について
提出書類 参加意向申出書（第１号様式）
提出期間 令和８年７月28日(火曜日)17時まで（必着）
申込期限
2026年7月28日
関連資料について
質問書 提出期限 令和８年８月６日17時まで""",
        "Live！横浜2027", "2026-07-28")

    def test_solar_window(self):
        self.check_closed("""申込について
提出書類 参加意向申出書（様式１）
提出期間 令和８年８月４日(火曜日)午後５時まで（必着）
申込期限
質問書 提出期限 令和８年８月19日（水曜日）午後５時まで""",
        "次世代型太陽電池", "2026-08-04")

    def test_learning_video(self):
        self.check_closed("""入札開始日 2026年8月24日
申込について
提出書類 公募型指名競争入札参加意向申出書
提出期間 2026年８月７日午後５時まで
申込期限
2026年8月7日
指名・非指名通知日 2026年８月19日まで""",
        "学習動画", "2026-08-07")

    def test_school_energy_range(self):
        self.check_closed("""申込について
提出書類 参加意向申出書
提出期間 令和８年７月14日から令和８年７月31日午後５時まで
申込期限
参加資格確認結果通知
提案書 提出期限 令和８年10月２日午後５時まで""",
        "学校再エネ", "2026-07-31")

    def test_real_open(self):
        facts = s.extract_facts("""申込について
提出書類 参加意向申出書
提出期間 令和８年８月20日午後５時まで
申込期限
2026年8月20日
関連資料について""", item("受付中"), date(2026, 8, 14))
        out = s.classify_status(facts, date(2026, 8, 14))
        self.assertEqual(out["participation_deadline"], "2026-08-20")
        self.assertTrue(out["is_open_now"])

    def test_ambiguous_future_not_open(self):
        facts = s.extract_facts(
            "ヒアリング実施日 2026年9月1日 提案書提出期限 2026年8月30日",
            item("曖昧案件"), date(2026, 8, 14))
        out = s.classify_status(facts, date(2026, 8, 14))
        self.assertEqual(out["application_status"], "判定不可")
        self.assertIsNone(out["is_open_now"])


if __name__ == "__main__":
    unittest.main()
