import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_category_pages as pages  # noqa: E402


class CategoryPageTests(unittest.TestCase):
    def sample_item(self):
        return {
            "id": "abcdef123456", "title": "テスト業務委託", "url": "https://example.invalid/item",
            "region": "相模原市", "source_name": "相模原市", "category": "入札・調達",
            "opportunity_type": "受注機会", "commercial_score": 87, "days_left": 10,
            "deadline_label": "残り10日", "deadline_time_exact": True, "application_status": "受付中",
            "status_confidence": "high", "participation_deadline": "2026-09-04",
            "preparation_status": "準備開始推奨", "preparation_start_date": "2026-08-25", "preparation_days": 10,
        }

    def test_procurement_page_labels_preparation_as_own_guidance(self):
        html = pages.render_page("入札・調達", [self.sample_item()], "2026-08-25T00:00:00+00:00")
        self.assertIn("独自目安", html)
        self.assertIn("法令上認められる範囲で責任を負いません", html)

    def test_category_page_is_a_clear_second_step_journey(self):
        html = pages.render_page("入札・調達", [self.sample_item()], "2026-08-25T00:00:00+00:00")
        self.assertIn("仕事を受注したい", html)
        self.assertIn("← 3つの入口に戻る", html)
        self.assertIn('id="categorySearch"', html)
        self.assertIn('id="categoryRegion"', html)
        self.assertIn('data-category-card', html)
        self.assertIn("案件名を押すと", html)

    def test_support_page_has_support_specific_journey_title(self):
        item = self.sample_item() | {"category": "補助金・支援", "title": "テスト補助金", "opportunity_type": "資金・支援"}
        html = pages.render_page("補助金・支援", [item], "2026-08-25T00:00:00+00:00")
        self.assertIn("補助金・支援を探したい", html)
        self.assertNotIn("仕事を受注したい", html)

    def test_real_open_feed_schema_does_not_require_redundant_is_open_now(self):
        item = {"id":"abcdef123456","url":"https://example.invalid/item","application_status":"受付中","status_confidence":"high","participation_deadline":"2026-09-04"}
        self.assertTrue(pages.verified_open_feed_item(item))

    def test_explicit_false_open_flag_is_rejected_defensively(self):
        item = {"id":"abcdef123456","url":"https://example.invalid/item","application_status":"受付中","status_confidence":"high","participation_deadline":"2026-09-04","is_open_now":False}
        self.assertFalse(pages.verified_open_feed_item(item))

    def test_only_configured_categories_are_index_targets(self):
        self.assertIn("入札・調達", pages.CATEGORY_CONFIG)
        self.assertIn("補助金・支援", pages.CATEGORY_CONFIG)
        self.assertNotIn("案件外", pages.CATEGORY_CONFIG)


if __name__ == "__main__":
    unittest.main()
