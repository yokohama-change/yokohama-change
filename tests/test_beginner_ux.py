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
        cls.home_css = (ROOT / "docs" / "home-v2.css").read_text(encoding="utf-8")
        cls.beginner_js = (ROOT / "docs" / "beginner.js").read_text(encoding="utf-8")
        cls.region_filter = (ROOT / "docs" / "region-filter.js").read_text(encoding="utf-8")

    def test_home_has_search_and_three_plain_purpose_choices(self):
        self.assertIn('id="heroSearchForm"', self.index)
        self.assertIn('仕事を受注したい', self.index)
        self.assertIn('補助金・支援を探したい', self.index)
        self.assertIn('自分に合うものだけ見たい', self.index)
        self.assertIn('data-quick-action="procurement"', self.index)
        self.assertIn('data-quick-action="support"', self.index)

    def test_home_explains_a_simple_three_step_journey(self):
        self.assertIn('id="howToUse"', self.index)
        self.assertIn('使い方は3つだけ', self.index)
        self.assertIn('公式サイトで最終確認', self.index)

    def test_filters_have_recovery_path_and_advanced_options_are_collapsed(self):
        self.assertIn('id="resetFilters"', self.index)
        self.assertIn('id="advancedFilters"', self.index)
        self.assertIn('<details id="advancedFilters"', self.index)
        self.assertIn('<details class="advanced-section">', self.index)

    def test_quality_and_coverage_are_moved_out_of_primary_journey(self):
        self.assertIn('id="trustArea"', self.index)
        self.assertIn("document.querySelector('#trustArea')", (ROOT / "docs" / "quality-audit.js").read_text(encoding="utf-8"))
        self.assertIn("document.querySelector('#trustArea')", self.region_filter)

    def test_quality_audit_is_actually_loaded(self):
        self.assertIn('quality-audit.css', self.index)
        self.assertIn('quality-audit.js', self.index)
        self.assertIn('beginner.css', self.index)
        self.assertIn('beginner.js', self.index)
        self.assertIn('home-v2.css', self.index)

    def test_primary_copy_avoids_internal_jargon(self):
        first_screen = self.index[:7000]
        self.assertNotIn('PUBLIC SIGNAL INTELLIGENCE', first_screen)
        self.assertNotIn('confidence high', first_screen)
        self.assertNotIn('buyer_segments', first_screen)
        self.assertNotIn('gBizINFO', first_screen)
        self.assertNotIn('JSON', first_screen)

    def test_deadline_time_is_never_treated_as_exact_without_flag(self):
        self.assertIn("x?.deadline_time_exact !== true", self.app)
        self.assertIn("x.deadline_time_exact === true", self.app)
        self.assertIn('時刻未確認', self.app)

    def test_home_prefers_internal_explainer_before_external_site(self):
        self.assertIn('opportunities/${encodeURIComponent(id)}.html', self.app)
        self.assertIn('かんたん詳細', self.app)
        self.assertIn('自治体公式サイト ↗', self.app)

    def test_mobile_controls_have_large_tap_targets(self):
        combined = self.beginner_css + self.home_css
        self.assertIn('min-height:48px', combined)
        self.assertIn('.purpose-card', self.home_css)
        self.assertIn('.hero-search', self.home_css)

    def test_quick_actions_clear_stale_filters(self):
        self.assertIn('resetForQuickAction()', self.beginner_js)
        self.assertIn("action === 'procurement'", self.beginner_js)
        self.assertIn("action === 'support'", self.beginner_js)

    def test_hero_search_reuses_the_main_results(self):
        self.assertIn("$('#heroSearchForm')", self.beginner_js)
        self.assertIn("scrollToId('#find')", self.beginner_js)
        self.assertIn("search.value = String(query", self.beginner_js)

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
            "region":"相模原市","source_name":"相模原市 新着更新情報","participation_deadline":"2026-09-03","participation_deadline_at":"2026-09-03T23:59+09:00","deadline_time_exact":False,"status_reason":"明示された新規参加期限を確認","status_confidence":"high",
        })
        self.assertIn('2026/09/03', html)
        self.assertNotIn('23:59', html)
        self.assertIn('公開基準を通過', html)

    def test_generated_detail_uses_plain_priority_label_and_external_warning(self):
        html = pages.render_detail({
            "id":"sample123","title":"サンプル業務委託","region":"大磯町","source_name":"大磯町 新着情報","category":"入札・調達","opportunity_type":"受注機会","commercial_score":80,"application_status":"受付中","is_open_now":True,"participation_deadline":"2026-09-08","participation_deadline_at":"2026-09-08T12:00+09:00","deadline_label":"残り13日","buyer_segments":["入札・公共調達"],"status_reason":"明示された新規参加期限を確認","url":"https://www.town.oiso.kanagawa.jp/example",
        }, "2026-08-26T00:00:00+09:00")
        self.assertIn('見る優先度（独自目安）', html)
        self.assertIn('大磯町の公式サイトを開く（外部）', html)
        self.assertNotIn('内部商用スコア', html)


if __name__ == "__main__":
    unittest.main()
