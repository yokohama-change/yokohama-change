import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FrontendResilienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.beginner_js = (ROOT / "docs" / "beginner.js").read_text(encoding="utf-8")
        cls.region_filter = (ROOT / "docs" / "region-filter.js").read_text(encoding="utf-8")
        cls.alert = (ROOT / "docs" / "alert.html").read_text(encoding="utf-8")
        cls.my_fit_js = (ROOT / "docs" / "my-fit.js").read_text(encoding="utf-8")
        cls.my_fit_css = (ROOT / "docs" / "my-fit.css").read_text(encoding="utf-8")

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

    def test_my_fit_separates_show_results_from_optional_save(self):
        self.assertIn('id="myFitShowResults"', self.alert)
        self.assertIn('結果を見る', self.alert)
        self.assertIn('条件を保存（任意）', self.alert)
        self.assertIn('選ぶだけで結果は更新されます', self.alert)
        self.assertIn("showButton?.addEventListener('click', showResults)", self.my_fit_js)
        self.assertIn("scrollIntoView", self.my_fit_js)

    def test_my_fit_reports_saved_and_restored_state_accessibly(self):
        self.assertIn('id="myFitSaveStatus"', self.alert)
        self.assertIn('aria-live="polite"', self.alert)
        self.assertIn('前回保存した条件を復元しました。', self.my_fit_js)
        self.assertIn('この端末に条件を保存しました。', self.my_fit_js)

    def test_my_fit_mobile_tap_targets_are_48px(self):
        self.assertIn('.my-fit-choice span', self.my_fit_css)
        self.assertIn('min-height:48px', self.my_fit_css)
        self.assertIn('.my-fit-show,.my-fit-save,.my-fit-clear{width:100%}', self.my_fit_css)


if __name__ == "__main__":
    unittest.main()
