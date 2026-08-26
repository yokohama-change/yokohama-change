import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class QualityTransparencyTests(unittest.TestCase):
    def test_loader_is_wired_directly_from_homepage(self):
        index = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("quality-audit.css", index)
        self.assertIn("quality-audit.js", index)
        self.assertIn('id="quickStart"', index)
        self.assertIn('id="trustArea"', index)

    def test_panel_reads_quality_and_explainability_without_cache_and_fails_closed(self):
        script = (ROOT / "docs" / "quality-audit.js").read_text(encoding="utf-8")
        compact = script.replace(" ", "")
        self.assertIn("data/quality.json", script)
        self.assertIn("data/explainability.json", script)
        self.assertIn("cache:'no-store'", compact)
        self.assertIn("shell.hidden = true", script)
        self.assertIn("unique_public_urls", script)
        self.assertIn("公式情報を保証するものではありません", script)
        self.assertIn("正確性・最新性は必ず公式ページでご確認ください", script)
        self.assertIn("explainable === openNow", script)

    def test_panel_stays_in_optional_trust_area(self):
        script = (ROOT / "docs" / "quality-audit.js").read_text(encoding="utf-8")
        self.assertIn("document.querySelector('#trustArea')", script)
        self.assertIn("trustArea.appendChild(shell)", script)
        self.assertIn("document.createElement('details')", script)

    def test_panel_styles_exist_and_are_collapsible(self):
        css = (ROOT / "docs" / "quality-audit.css").read_text(encoding="utf-8")
        self.assertIn(".quality-audit", css)
        self.assertIn(".quality-audit-chip.pass", css)
        self.assertIn(".quality-audit.is-warning", css)


if __name__ == "__main__":
    unittest.main()
