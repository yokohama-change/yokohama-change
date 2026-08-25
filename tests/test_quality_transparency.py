import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class QualityTransparencyTests(unittest.TestCase):
    def test_loader_is_wired_without_modifying_main_app(self):
        region_filter = (ROOT / "docs" / "region-filter.js").read_text(encoding="utf-8")
        self.assertIn("quality-audit.css", region_filter)
        self.assertIn("quality-audit.js", region_filter)
        self.assertIn("data-quality-audit", region_filter)

    def test_panel_reads_quality_without_cache_and_fails_closed(self):
        script = (ROOT / "docs" / "quality-audit.js").read_text(encoding="utf-8")
        self.assertIn("data/quality.json", script)
        self.assertIn("cache: 'no-store'", script)
        self.assertIn("shell.hidden = true", script)
        self.assertIn("unique_public_urls", script)
        self.assertIn("公式情報の正確性を保証するものではありません", script)

    def test_panel_styles_exist(self):
        css = (ROOT / "docs" / "quality-audit.css").read_text(encoding="utf-8")
        self.assertIn(".quality-audit", css)
        self.assertIn(".quality-audit-chip.pass", css)
        self.assertIn(".quality-audit.is-warning", css)


if __name__ == "__main__":
    unittest.main()
