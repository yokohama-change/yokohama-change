import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import plain_language_pages as plain  # noqa: E402


class PlainLanguagePageTests(unittest.TestCase):
    def test_visible_jargon_is_rewritten(self):
        source = '''<span>OPEN OPPORTUNITIES · 相模原市</span>
        <h1>神奈川県内の高商用案件（商用70+）</h1>
        <p>現在受付中・信頼度high。YOKOHAMA CHANGE商用スコアを表示。</p>
        <div><b>商用 87</b></div>
        <small>受付中 3件 · 商用70+ 2件 · 生成 2026-08-26</small>
        <span>FOCUS · VERIFIED OPEN ONLY</span>'''
        result = plain.transform_html(source)
        self.assertNotIn("OPEN OPPORTUNITIES", result)
        self.assertNotIn("FOCUS · VERIFIED OPEN ONLY", result)
        self.assertNotIn("信頼度high", result)
        self.assertNotIn("商用スコア", result)
        self.assertNotIn("<b>商用 ", result)
        self.assertIn("受付中案件 · 相模原市", result)
        self.assertIn("見る優先度70以上", result)
        self.assertIn("公開基準を通過", result)
        self.assertIn("<b>見る優先度 87</b>", result)
        self.assertIn(" · 更新 2026-08-26", result)

    def test_internal_field_names_are_not_touched(self):
        source = '{"commercial_score":87,"status_confidence":"high"}'
        self.assertEqual(source, plain.transform_html(source))


if __name__ == "__main__":
    unittest.main()
