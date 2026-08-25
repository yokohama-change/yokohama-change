import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import inject_opportunity_trace as trace  # noqa: E402
import generate_opportunity_pages_multi as pages  # noqa: E402


class BeginnerUXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        cls.app = (ROOT / "docs" / "app.js").read_text(encoding="utf-8")
        cls.alert = (ROOT / "docs" / "alert.html").read_text(encoding="utf-8")
        cls.beginner_css = (ROOT / "docs" / "beginner.css").read_text(encoding="utf-8")
        cls.region_filter = (ROOT / "docs" / "region-filter.js").read_text(encoding="utf-8")

    def test_home_starts_with_three_clear_actions(self):
        self.assertIn('id="quickStart"', self.index)
        self.assertIn('data-quick-action="open"', self.index)
        self.assertIn('data-quick-action="support"', self.index)
        self.assertIn('自分向けに絞る', self.index)

    def test_filters_have_recovery_path_and_advanced_options_are_collapsed(self):
        self.assertIn('id="resetFilters"', self.index)
        self.assertIn('id="advancedFilters"', self.index)
        self.assertIn('<details class="advanced-data">', self.index)
        self.assertIn('<details class="advanced-section">', self.index)

    def test_quality_audit_is_actually_loaded(self):
        self.assertIn('quality-audit.css', self.index)
        self.assertIn('quality-audit.js', self.index)
        self.assertIn('beginner.css', self.index)
        self.assertIn('beginner.js', self.index)

    def test_primary_copy_avoids_internal_jargon(self):
        self.assertNotIn('PUBLIC SIGNAL INTELLIGENCE', self.index)
        self.assertNotIn('confidence high', self.index)
        self.assertNotIn('confidence high', self.alert)
        self.assertNotIn('buyer_segments', self.alert)
        self.assertNotIn('opportunity_type / region', self.alert)

    def test_deadline_time_is_never_treated_as_exact_without_flag(self):
        self.assertIn("x?.deadline_time_exact !== true", self.app)
        self.assertIn("x.deadline_time_exact === true", self.app)
        self.assertIn('時刻未確認', self.app)

    def test_home_prefers_internal_explainer_before_external_site(self):
        self.assertIn('opportunities/${encodeURIComponent(id)}.html', self.app)
        self.assertIn('かんたん詳細', self.app)
        self.assertIn('自治体公式サイト ↗', self.app)
        self.assertNotIn('<small>BUSINESS</small>', self.app)

    def test_mobile_controls_have_large_tap_targets(self):
        self.assertIn('min-height:44px', self.beginner_css)
        self.assertIn('.my-fit-choice span', self.beginner_css)
        self.assertIn('.reset-filters', self.beginner_css)

    def test_coverage_is_collapsed_instead_of_long_always_visible_list(self):
        self.assertIn("document.createElement('details')", self.region_filter)
        self.assertIn('地域を見る', self.region_filter)

    def test_alert_explains_three_steps_in_plain_japanese(self):
        self.assertIn('使い方は3ステップ', self.alert)
        self.assertIn('① あなたの仕事に近いもの', self.alert)
        self.assertIn('② 探したいもの', self.alert)
        self.assertIn('登録不要', self.alert)

    def test_date_only_trace_never_displays_inferred_2359(self):
        html = trace.trace_block({
            "region": "相模原市",
            "source_name": "相模原市 新着更新情報",
            "participation_deadline": "2026-09-03",
            "participation_deadline_at": "2026-09-03T23:59+09:00",
            "deadline_time_exact": False,
            "status_reason": "明示された新規参加期限を確認",
            "status_confidence": "high",
        })
        self.assertIn('2026/09/03', html)
        self.assertNotIn('23:59', html)
        self.assertNotIn('high /', html)
        self.assertIn('公開基準を通過', html)

    def test_generated_detail_uses_plain_priority_label_and_external_warning(self):
        html = pages.render_detail({
            "id": "sample123",
            "title": "サンプル業務委託",
            "region": "大磯町",
            "source_name": "大磯町 新着情報",
            "category": "入札・調達",
            "opportunity_type": "受注機会",
            "commercial_score": 80,
            "application_status": "受付中",
            "is_open_now": True,
            "participation_deadline": "2026-09-08",
            "participation_deadline_at": "2026-09-08T12:00+09:00",
            "deadline_label": "残り13日",
            "buyer_segments": ["入札・公共調達"],
            "status_reason": "明示された新規参加期限を確認",
            "url": "https://www.town.oiso.kanagawa.jp/example",
        }, "2026-08-26T00:00:00+09:00")
        self.assertIn('見る優先度（独自目安）', html)
        self.assertIn('大磯町の公式サイトを開く（外部）', html)
        self.assertNotIn('内部商用スコア', html)


if __name__ == "__main__":
    unittest.main()
