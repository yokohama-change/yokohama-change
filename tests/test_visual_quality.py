import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class VisualQualityTests(unittest.TestCase):
    def test_home_has_desktop_tablet_and_small_mobile_tuning(self):
        css = (DOCS / "home-v2.css").read_text(encoding="utf-8")
        polish = (DOCS / "home-polish.css").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:980px)", css)
        self.assertIn("@media(max-width:700px)", css)
        self.assertIn("@media(max-width:390px)", css)
        self.assertIn("clamp(48px", css)
        self.assertIn("max-width:1200px", css)
        self.assertIn("@media(max-width:980px) and (min-width:701px)", polish)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))", polish)
        self.assertIn(".gateway-home .gateway-hero h1 span{display:block}", polish)
        self.assertIn(".gateway-home .gateway-purpose-card", polish)
        self.assertIn(".gateway-live", polish)

    def test_motion_is_progressive_and_respects_reduced_motion(self):
        css = (DOCS / "home-v2.css").read_text(encoding="utf-8")
        js = (DOCS / "beginner.js").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion:reduce", css)
        self.assertIn("prefers-reduced-motion: reduce", js)
        self.assertIn("IntersectionObserver", js)
        self.assertIn("{passive:true}", js.replace(" ", ""))
        self.assertIn("data-reveal", js)

    def test_premium_polish_does_not_pull_remote_fonts_or_frameworks(self):
        for name in ["home-v2.css", "home-polish.css", "preparation.css", "next-deadline.css", "monetization.css", "my-fit.css", "opportunity.css"]:
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
        self.assertIn("min-height:48px", fit)
        self.assertIn("prefers-reduced-motion:reduce", fit)

    def test_opportunity_pages_match_light_visual_system(self):
        css = (DOCS / "opportunity.css").read_text(encoding="utf-8")
        self.assertIn("background:linear-gradient(180deg,#fbfcfd,#f5f7fa)", css)
        self.assertIn(".category-tools", css)
        self.assertIn(".choice-back", css)
        self.assertIn("background:#fff", css)
        self.assertNotIn("background:#0d1118", css)

    def test_preparation_guidance_matches_light_premium_system(self):
        css = (DOCS / "preparation.css").read_text(encoding="utf-8")
        self.assertIn("background:linear-gradient(145deg,#fffdf8,#fff", css)
        self.assertIn("color:#172033", css)
        self.assertIn("background:#fff", css)
        self.assertNotIn("background:#11151d", css)
        self.assertNotIn("background:#211a0e", css)

    def test_second_pass_polish_is_loaded_without_remote_dependency(self):
        js = (DOCS / "next-deadline.js").read_text(encoding="utf-8")
        polish = (DOCS / "home-polish.css").read_text(encoding="utf-8")
        self.assertIn("home-polish.css", js)
        self.assertIn("data-home-polish-style", js)
        self.assertIn("#667487", polish)
        self.assertIn(".home-v2 .why", polish)
        self.assertIn("background:#f1f8f5", polish)

    def test_next_deadline_uses_light_shell_and_deep_green_accent(self):
        css = (DOCS / "next-deadline.css").read_text(encoding="utf-8")
        self.assertIn("background:linear-gradient(145deg,#fbfdfc,#fff", css)
        self.assertIn("background:linear-gradient(145deg,#164438,#17392f)", css)
        self.assertIn("color:#172033", css)
        self.assertNotIn("background:#0d1b17", css)


if __name__ == "__main__":
    unittest.main()
