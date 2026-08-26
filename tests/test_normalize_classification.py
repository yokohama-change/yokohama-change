import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import normalize_classification as classify  # noqa: E402


class ClassificationNormalizationTests(unittest.TestCase):
    def test_procurement_opportunity_cannot_remain_in_support_category(self):
        item = {
            "id": "market1",
            "title": "指定管理者公募に向けたサウンディング型市場調査",
            "category": "補助金・支援",
            "opportunity_type": "受注機会",
        }
        changes = classify.normalize_items([item])
        self.assertEqual("入札・調達", item["category"])
        self.assertEqual(1, len(changes))
        self.assertEqual([], classify.remaining_conflicts([item]))

    def test_support_opportunity_cannot_remain_in_procurement_category(self):
        item = {
            "id": "grant1",
            "title": "展示会出展費用助成金",
            "category": "入札・調達",
            "opportunity_type": "資金・支援",
        }
        classify.normalize_items([item])
        self.assertEqual("補助金・支援", item["category"])

    def test_generic_public_call_is_not_automatically_support(self):
        item = {
            "id": "generic1",
            "title": "参加者を公募します",
            "description": "",
            "category": "施設・イベント",
            "opportunity_type": "情報更新",
        }
        self.assertIsNone(classify.expected_category(item))

    def test_strong_terms_are_used_when_opportunity_type_is_generic(self):
        support = {"title": "設備投資補助金", "description": "", "opportunity_type": "情報更新"}
        procurement = {"title": "清掃業務委託", "description": "", "opportunity_type": "情報更新"}
        self.assertEqual("補助金・支援", classify.expected_category(support))
        self.assertEqual("入札・調達", classify.expected_category(procurement))


if __name__ == "__main__":
    unittest.main()
