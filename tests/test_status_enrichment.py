import importlib.util
import unittest
from datetime import date
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "scripts" / "enrich_status.py"
spec = importlib.util.spec_from_file_location("status_enrichment", p)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class StatusEnrichmentTests(unittest.TestCase):
    def test_open_participation_deadline(self):
        facts = {"participation_dates": ["2026-08-20"], "downstream_dates": [], "generic_dates": [], "result_hit": False}
        out = s.classify_status(facts, date(2026, 8, 14))
        self.assertEqual(out["application_status"], "受付中")
        self.assertTrue(out["is_open_now"])

    def test_participation_closed_but_qualified_progresses(self):
        facts = {"participation_dates": ["2026-08-04"], "downstream_dates": ["2026-08-19", "2026-09-16"], "generic_dates": [], "result_hit": False}
        out = s.classify_status(facts, date(2026, 8, 14))
        self.assertEqual(out["application_status"], "資格者のみ進行中")
        self.assertFalse(out["is_open_now"])
        self.assertEqual(out["next_deadline"], "2026-08-19")

    def test_participation_closed(self):
        facts = {"participation_dates": ["2026-07-28"], "downstream_dates": [], "generic_dates": [], "result_hit": False}
        out = s.classify_status(facts, date(2026, 8, 14))
        self.assertEqual(out["application_status"], "参加締切済")
        self.assertFalse(out["is_open_now"])

    def test_reiwa_and_fullwidth_dates(self):
        item = {"source_updated": "Thu, 13 Aug 2026 01:00:00 GMT"}
        text = "参加意向申出書 提出期限：令和８年８月４日 質問書提出期限：令和8年8月19日 提案書提出期限：令和8年9月16日"
        facts = s.extract_facts(text, item, date(2026, 8, 14))
        self.assertIn("2026-08-04", facts["participation_dates"])
        self.assertIn("2026-08-19", facts["downstream_dates"])
        self.assertIn("2026-09-16", facts["downstream_dates"])


if __name__ == "__main__":
    unittest.main()
