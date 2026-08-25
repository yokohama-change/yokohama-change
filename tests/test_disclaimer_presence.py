import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_opportunity_pages_multi as opportunities  # noqa: E402
import generate_region_pages_extended as regions  # noqa: E402


class DisclaimerPresenceTests(unittest.TestCase):
    def test_static_pages_expose_disclaimer(self):
        for relative in ("docs/index.html", "docs/alert.html", "docs/disclaimer.html"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("disclaimer.html", text if relative != "docs/disclaimer.html" else "disclaimer.html") if relative != "docs/disclaimer.html" else None
            self.assertIn("法令上認められる範囲で責任を負いません", text)

    def test_generated_opportunity_detail_contains_disclaimer(self):
        item = {
            "id": "abcdef123456",
            "region": "相模原市",
            "title": "テスト案件",
            "source_name": "相模原市 新着情報",
            "category": "入札・調達",
            "opportunity_type": "受注機会",
            "commercial_score": 87,
            "application_status": "受付中",
            "is_open_now": True,
            "participation_deadline_at": "2026-09-01T17:00+09:00",
            "deadline_label": "残り7日",
            "buyer_segments": ["入札・公共調達"],
            "status_reason": "公式期限を確認",
            "url": "https://example.invalid/official",
        }
        text = opportunities.render_detail(item, "2026-08-25T00:00:00+00:00")
        self.assertIn("../disclaimer.html", text)
        self.assertIn("法令上認められる範囲で責任を負いません", text)

    def test_generated_region_page_contains_disclaimer(self):
        item = {
            "id": "abcdef123456",
            "title": "テスト案件",
            "source_name": "相模原市 新着情報",
            "opportunity_type": "受注機会",
            "commercial_score": 87,
            "days_left": 7,
            "deadline_label": "残り7日",
            "deadline_time_exact": True,
        }
        text = regions.render_region("相模原市", [item], "2026-08-25T00:00:00+00:00")
        self.assertIn("../../../disclaimer.html", text)
        self.assertIn("法令上認められる範囲で責任を負いません", text)


if __name__ == "__main__":
    unittest.main()
