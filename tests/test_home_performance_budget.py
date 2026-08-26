import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class HomePerformanceBudgetTests(unittest.TestCase):
    def test_home_uses_no_external_runtime_scripts(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        external = re.findall(r'<script[^>]+src=["\']https?://', html, flags=re.I)
        self.assertEqual([], external)

    def test_home_has_no_large_decorative_images(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('<img', html.lower())
        self.assertNotIn('<video', html.lower())

    def test_initial_home_assets_stay_lightweight(self):
        files = [
            "index.html", "styles.css", "today.css", "monetization.css",
            "next-deadline.css", "quality-audit.css", "beginner.css", "home-v2.css",
            "app.js", "next-deadline.js", "region-filter.js", "quality-audit.js", "beginner.js",
        ]
        total = sum((DOCS / name).stat().st_size for name in files)
        # A generous ceiling that catches accidental framework/image bundles while
        # allowing the current dependency-free implementation to evolve.
        self.assertLess(total, 350_000, f"initial home assets too large: {total} bytes")

    def test_home_has_one_clear_h1(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertEqual(1, len(re.findall(r'<h1\b', html, flags=re.I)))
        self.assertIn('今応募できる', html)
        self.assertIn('入札・補助金', html)


if __name__ == "__main__":
    unittest.main()
