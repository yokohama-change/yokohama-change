import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_focus_pages as pages  # noqa: E402


class FocusPageTests(unittest.TestCase):
    def item(self, **overrides):
        base = {
            "id": "abc123",
            "title": "テスト案件",
            "application_status": "受付中",
            "status_confidence": "high",
            "participation_deadline": "2026-08-25",
            "days_left": 0,
            "commercial_score": 80,
            "region": "横浜市",
            "source_name": "公式情報",
            "opportunity_type": "受注機会",
            "deadline_label": "本日締切",
            "deadline_time_exact": True,
        }
        base.update(overrides)
        return base

    def test_today_is_deadline_soon(self):
        item = self.item(days_left=0)
        self.assertTrue(pages.verified_open(item))
        self.assertTrue(pages.FOCUS["deadline-soon"]["filter"](item))

    def test_day_eight_is_not_deadline_soon(self):
        item = self.item(days_left=8)
        self.assertFalse(pages.FOCUS["deadline-soon"]["filter"](item))

    def test_high_value_threshold(self):
        self.assertTrue(pages.FOCUS["high-value"]["filter"](self.item(commercial_score=70)))
        self.assertFalse(pages.FOCUS["high-value"]["filter"](self.item(commercial_score=69)))

    def test_unverified_item_never_eligible(self):
        self.assertFalse(pages.verified_open(self.item(status_confidence="medium")))
        self.assertFalse(pages.verified_open(self.item(application_status="締切済")))
        self.assertFalse(pages.verified_open(self.item(participation_deadline="")))

    def test_page_labels_internal_metrics(self):
        item = self.item()
        html = pages.render_page("high-value", [item], "2026-08-25T00:00:00+00:00")
        self.assertIn("YOKOHAMA CHANGE独自の参考指標", html)
        self.assertIn("最終判断は必ず公式情報", html)
        self.assertIn("法令上認められる範囲で責任を負いません", html)


if __name__ == "__main__":
    unittest.main()
