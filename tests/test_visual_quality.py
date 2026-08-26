import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class VisualQualityTests(unittest.TestCase):
    def test_home_has_desktop_tablet_and_small_mobile_tuning(self):
        css = (DOCS / "home-v2.css").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:980px)", css)
        self.assertIn("@media(max-width:700px)", css)
        self.assertIn("@media(max-width:390px)", css)
        self.assertIn("clamp(48px", css)
        self.assertIn("max-width:1200px", css)

    def test_motion_is_progressive_and_respects_reduced_motion(self):
        css = (DOCS / "home-v2.css").read_text(encoding="utf-8")
        js = (DOCS / "beginner.js").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion:reduce", css)
        self.assertIn("prefers-reduced-motion: reduce", js)
        self.assertIn("IntersectionObserver", js)
        self.assertIn("{passive:true}", js.replace(" ", ""))
        self.assertIn("data-reveal", js)

    def test_premium_polish_does_not_pull_remote_fonts_or_frameworks(self):
        for name in ["home-v2.css", "monetization.css", "my-fit.css"]:
            content = (DOCS / name).read_text(encoding="utf-8").lower()
            self.assertNotIn("@import", content)
            self.assertNotIn("fonts.googleapis.com", content)
            self.assertNotIn("cdn.jsdelivr.net", content)

    def test_alert_page_matches_light_visual_system(self):
        css = (DOCS / "monetization.css").read_text(encoding="utf-8")
        fit = (DOCS / "my-fit.css").read_text(encoding="utf-8")
        self.assertIn("body:has(.alert-page)", css)
        self.assertIn("#f6f8fa", css)
        self.assertIn("border-radius:28px", css)
        self.assertIn("#0f7a5b", fit)
        self.assertIn("min-height:44px", fit)
        self.assertIn("prefers-reduced-motion:reduce", fit)


if __name__ == "__main__":
    unittest.main()
