import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_opportunity_pages.py"
spec = importlib.util.spec_from_file_location("generate_opportunity_pages", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class GenerateOpportunityPagesTests(unittest.TestCase):
    def base_item(self):
        return {
            "id": "abc123def456",
            "title": "テスト案件 <script>",
            "url": "https://example.test/official?a=1&b=2",
            "source_name": "横浜市 入札・契約",
            "category": "入札・調達",
            "opportunity_type": "受注機会",
            "buyer_segments": ["入札・公共調達"],
            "commercial_score": 87,
            "application_status": "受付中",
            "is_open_now": True,
            "participation_deadline_at": "2026-09-02T17:00+09:00",
            "deadline_label": "残り8日",
            "status_confidence": "high",
            "status_reason": "公式期限を確認",
        }

    def test_open_high_confidence_item_is_publishable_and_indexable(self):
        item = self.base_item()
        self.assertTrue(mod.publishable(item))
        self.assertTrue(mod.is_open(item))
        page = mod.render_detail(item, "2026-08-25T12:00:00+09:00")
        self.assertIn('content="index,follow,max-image-preview:large"', page)
        self.assertIn("現在受付中", page)
        self.assertNotIn("<script>\n", page)
        self.assertIn("&lt;script&gt;", page)

    def test_closed_item_is_kept_but_noindexed(self):
        item = self.base_item()
        item.update({"application_status": "結果掲載済", "is_open_now": False})
        self.assertTrue(mod.publishable(item))
        self.assertFalse(mod.is_open(item))
        page = mod.render_detail(item, "2026-08-25T12:00:00+09:00")
        self.assertIn('content="noindex,follow"', page)
        self.assertIn("結果掲載済", page)

    def test_low_confidence_or_no_deadline_is_not_publishable(self):
        low = self.base_item()
        low["status_confidence"] = "medium"
        self.assertFalse(mod.publishable(low))
        no_deadline = self.base_item()
        no_deadline["participation_deadline_at"] = ""
        self.assertFalse(mod.publishable(no_deadline))

    def test_sitemap_only_receives_passed_open_items(self):
        item = self.base_item()
        xml = mod.build_sitemap([item], "2026-08-25")
        self.assertIn("opportunities/abc123def456.html", xml)
        self.assertIn("<lastmod>2026-08-25</lastmod>", xml)


if __name__ == "__main__":
    unittest.main()
