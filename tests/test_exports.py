import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "enrich_status.py"
spec = importlib.util.spec_from_file_location("status_enrichment_exports", p)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class ExportTests(unittest.TestCase):
    def test_rank_prefers_high_score_then_deadline(self):
        a = {"commercial_score": 87, "days_left": 3, "urgency": 30, "title": "A"}
        b = {"commercial_score": 70, "days_left": 1, "urgency": 80, "title": "B"}
        self.assertLess(s.open_rank_key(a), s.open_rank_key(b))

    def test_employment_is_not_candidate_even_with_procurement_words(self):
        x = {
            "title": "会計年度任用職員 入札参加資格審査 10月1日採用",
            "commercial_score": 100,
            "opportunity_type": "受注機会",
            "category": "入札・調達",
        }
        self.assertFalse(s.is_candidate(x))


if __name__ == "__main__":
    unittest.main()
