import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import enrich_status_multi as multi  # noqa: E402

s = multi.core
JST = timezone(timedelta(hours=9))


def item(title="案件"):
    return {
        "title": title,
        "source_updated": "Tue, 21 Jul 2026 08:00:00 GMT",
        "commercial_score": 90,
        "opportunity_type": "受注機会",
        "category": "入札・調達",
    }


class MultiStatusSafetyTests(unittest.TestCase):
    def classify(self, text, title="案件"):
        today = date(2026, 8, 14)
        facts = s.extract_facts(text, item(title), today)
        return s.classify_status(facts, today, datetime(2026, 8, 14, 10, 0, tzinfo=JST))

    def test_question_reception_period_is_never_participation_deadline(self):
        out = self.classify("質問受付期間 令和8年9月4日17時まで", "質問期間だけの案件")
        self.assertIsNot(out.get("is_open_now"), True)
        self.assertNotEqual(out.get("application_status"), "受付中")

    def test_proposal_reception_period_is_never_participation_deadline(self):
        out = self.classify("企画提案書受付期間 令和8年9月4日17時まで", "提案書期間だけの案件")
        self.assertIsNot(out.get("is_open_now"), True)
        self.assertNotEqual(out.get("application_status"), "受付中")

    def test_bid_document_reception_period_is_never_participation_deadline(self):
        out = self.classify("入札書受付期間 令和8年9月4日17時まで", "入札書期間だけの案件")
        self.assertIsNot(out.get("is_open_now"), True)
        self.assertNotEqual(out.get("application_status"), "受付中")

    def test_explicit_bid_participation_window_still_opens(self):
        out = self.classify("入札参加申込受付期間 令和8年9月4日17時まで", "参加申込あり")
        self.assertTrue(out.get("is_open_now"))
        self.assertEqual(out.get("participation_deadline"), "2026-09-04")

    def test_application_section_submission_period_still_opens(self):
        out = self.classify(
            """申込について
提出書類 参加意向申出書
提出期間 令和8年9月4日17時まで
関連資料について""",
            "申込欄あり",
        )
        self.assertTrue(out.get("is_open_now"))
        self.assertEqual(out.get("participation_deadline"), "2026-09-04")


if __name__ == "__main__":
    unittest.main()
