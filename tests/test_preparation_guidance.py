import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import regionalize_outputs as regional  # noqa: E402


class PreparationGuidanceTests(unittest.TestCase):
    def test_procurement_uses_ten_days(self):
        item = {"category": "入札・調達", "opportunity_type": "受注機会", "title": "業務委託"}
        self.assertEqual(regional.preparation_days(item), 10)

    def test_designated_manager_uses_fourteen_days(self):
        item = {"category": "補助金・支援", "opportunity_type": "受注機会", "title": "指定管理者公募"}
        self.assertEqual(regional.preparation_days(item), 14)

    def test_support_uses_seven_days(self):
        item = {"category": "補助金・支援", "opportunity_type": "資金・支援", "title": "助成金"}
        self.assertEqual(regional.preparation_days(item), 7)

    def test_open_procurement_becomes_due_on_start_date(self):
        item = {
            "is_open_now": True,
            "category": "入札・調達",
            "opportunity_type": "受注機会",
            "title": "業務委託",
            "participation_deadline": "2026-09-04",
        }
        meta = regional.preparation_metadata(item, date(2026, 8, 25))
        self.assertEqual(meta["preparation_start_date"], "2026-08-25")
        self.assertEqual(meta["preparation_status"], "準備開始推奨")

    def test_closed_item_gets_no_active_guidance(self):
        item = {
            "is_open_now": False,
            "category": "入札・調達",
            "participation_deadline": "2026-09-04",
        }
        meta = regional.preparation_metadata(item, date(2026, 8, 25))
        self.assertEqual(meta["preparation_status"], "")
        self.assertIsNone(meta["preparation_days"])


if __name__ == "__main__":
    unittest.main()
