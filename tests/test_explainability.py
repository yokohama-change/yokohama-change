import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load_module("explainability_gate", ROOT / "scripts" / "explainability_gate.py")
trace = load_module("inject_opportunity_trace", ROOT / "scripts" / "inject_opportunity_trace.py")


def good_open(**overrides):
    item = {
        "id": "abc123def456",
        "source_id": "sample_source",
        "source_name": "大磯町 新着情報",
        "region": "大磯町",
        "url": "https://www.town.oiso.kanagawa.jp/example.html",
        "application_status": "受付中",
        "is_open_now": True,
        "participation_deadline": "2026-09-08",
        "participation_deadline_at": "2026-09-08T12:00+09:00",
        "status_confidence": "high",
        "status_reason": "明示された新規参加期限（申込期限）を確認",
        "deadline_time_exact": True,
        "status_checked_at": "2026-08-26T06:59:37+09:00",
        "title": "サンプル案件",
    }
    item.update(overrides)
    return item


class ExplainabilityGateTests(unittest.TestCase):
    def test_valid_open_item_passes(self):
        self.assertEqual([], gate.validate_open_item(good_open()))

    def test_open_item_without_reason_fails(self):
        problems = gate.validate_open_item(good_open(status_reason=""))
        self.assertTrue(any("判定根拠" in p for p in problems))

    def test_non_participation_reason_fails(self):
        problems = gate.validate_open_item(good_open(status_reason="質問受付期限を確認"))
        self.assertTrue(any("新規参加期限" in p for p in problems))

    def test_deadline_precision_must_be_boolean(self):
        problems = gate.validate_open_item(good_open(deadline_time_exact="true"))
        self.assertTrue(any("deadline_time_exact" in p for p in problems))

    def test_closed_item_is_out_of_scope(self):
        self.assertEqual([], gate.validate_open_item(good_open(is_open_now=False)))


class OpportunityTraceTests(unittest.TestCase):
    def base_page(self):
        return '''<html><head><link rel="stylesheet" href="../opportunity.css"></head><body>
      <section class="opportunity-section">
        <h2>判定根拠</h2>
      </section>
      <a class="opportunity-official" href="#">公式</a>
</body></html>'''

    def test_trace_is_injected_with_jst_and_exact_time_label(self):
        page = trace.inject_page(self.base_page(), good_open())
        self.assertIn("受付中判定の証跡", page)
        self.assertIn("2026/09/08 12:00", page)
        self.assertIn("公式ページ上の締切時刻まで確認済み", page)
        self.assertIn("opportunity-trace.css", page)
        self.assertIn("明示された新規参加期限", page)

    def test_date_only_precision_hides_internal_end_of_day_time(self):
        page = trace.inject_page(
            self.base_page(),
            good_open(
                deadline_time_exact=False,
                participation_deadline="2026-09-03",
                participation_deadline_at="2026-09-03T23:59+09:00",
            ),
        )
        self.assertIn("2026/09/03", page)
        self.assertNotIn("2026/09/03 23:59", page)
        self.assertIn("締切日を確認・締切時刻は未確認", page)

    def test_injection_is_idempotent(self):
        once = trace.inject_page(self.base_page(), good_open())
        twice = trace.inject_page(once, good_open())
        self.assertEqual(once, twice)
        self.assertEqual(once.count('class="opportunity-trace"'), 1)


if __name__ == "__main__":
    unittest.main()
