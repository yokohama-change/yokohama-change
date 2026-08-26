import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FrontendResilienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.beginner_js = (ROOT / "docs" / "beginner.js").read_text(encoding="utf-8")
        cls.region_filter = (ROOT / "docs" / "region-filter.js").read_text(encoding="utf-8")

    def test_mobile_load_guard_does_not_refetch_large_latest_payload(self):
        self.assertNotIn("fetchRequiredJson('./data/latest.json')", self.beginner_js)
        self.assertIn("fetchRequiredJson('./data/status.json')", self.beginner_js)
        self.assertIn("fetchRequiredJson('./data/quality.json')", self.beginner_js)
        self.assertIn('quality?.open_now', self.beginner_js)
        self.assertIn('Date.now() + 10000', self.beginner_js)
        self.assertIn('setTimeout(verifyRendered, 250)', self.beginner_js)

    def test_region_filter_does_not_identify_cards_by_source_url(self):
        self.assertIn("card.querySelector('.meta')", self.region_filter)
        self.assertIn('cardRegion(card) === region', self.region_filter)
        self.assertNotIn('normalizeHref', self.region_filter)
        self.assertNotIn('byUrl', self.region_filter)


if __name__ == "__main__":
    unittest.main()
