import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_category_pages as pages  # noqa: E402


class CategoryPageTests(unittest.TestCase):
    def test_procurement_page_labels_preparation_as_own_guidance(self):
        item = {
            "id": "abcdef123456",
            "title": "テスト業務委託",
            "url": "https://example.invalid/item",
            "region": "相模原市",
            "source_name": "相模原市",
            "category": "入札・調達",
            "opportunity_type": "受注機会",
            "commercial_score": 87,
            "days_left": 10,
            "deadline_label": "残り10日",
            "deadline_time_exact": True,
            "is_open_now": True,
            "preparation_status": "準備開始推奨",
            "preparation_start_date": "2026-08-25",
            "preparation_days": 10,
        }
        html = pages.render_page("入札・調達", [item], "2026-08-25T00:00:00+00:00")
        self.assertIn("独自目安", html)
        self.assertIn("公式期限・応募要件ではありません", html)
        self.assertIn("法令上認められる範囲で責任を負いません", html)

    def test_only_configured_categories_are_index_targets(self):
        self.assertIn("入札・調達", pages.CATEGORY_CONFIG)
        self.assertIn("補助金・支援", pages.CATEGORY_CONFIG)
        self.assertNotIn("案件外", pages.CATEGORY_CONFIG)


if __name__ == "__main__":
    unittest.main()
