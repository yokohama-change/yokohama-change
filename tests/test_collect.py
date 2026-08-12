import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

p = Path(__file__).resolve().parents[1] / "scripts" / "collect.py"
spec = importlib.util.spec_from_file_location("collector", p)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CollectorTests(unittest.TestCase):
    def test_classification(self):
        cat, score, words = c.classify("市内中小企業向け設備投資補助金の申請受付")
        self.assertIn(cat, {"補助金・支援", "事業・雇用"})
        self.assertGreaterEqual(score, 50)
        self.assertIn("補助金", words)

    def test_rss_parse_and_business_signal(self):
        xml = '''<?xml version="1.0"?><rss><channel><item><title>市有地公募売却と道路整備のお知らせ</title><link>https://example.test/a</link><pubDate>2026-08-12</pubDate></item></channel></rss>'''.encode('utf-8')
        src={"id":"t","name":"test","region":"x"}
        rows=c.parse_rss(xml,src)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "都市・不動産")
        self.assertIn("不動産・建設", rows[0]["buyer_segments"])
        self.assertGreaterEqual(rows[0]["commercial_score"], 50)

    def test_procurement_signal(self):
        row = c.normalize_item(
            {"id":"p","name":"proc","region":"横浜市"},
            "https://example.test/p",
            "事業者募集 公募型プロポーザルを実施します",
            "2026-08-12",
            "委託事業の契約候補者を募集",
            "rss",
        )
        self.assertEqual(row["opportunity_type"], "受注機会")
        self.assertIn("入札・公共調達", row["buyer_segments"])
        self.assertGreaterEqual(row["commercial_score"], 70)

    def test_v1_state_is_readable(self):
        s = c.normalize_prior_state({"initialized": True, "items": {"abc": "deadbeef"}})
        self.assertTrue(s["initialized"])
        self.assertEqual(s["items"]["abc"]["fingerprint"], "deadbeef")

    def test_all_source_failure_preserves_state(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            config = tmp_path / "sources.json"
            state = tmp_path / "state.json"
            history = tmp_path / "history.ndjson"
            latest = tmp_path / "latest.json"
            status = tmp_path / "status.json"
            config.write_text(json.dumps({"sources":[{"id":"x","name":"X","type":"rss","url":"https://invalid.test/x"}]}), encoding="utf-8")
            original = {"version":2,"initialized":True,"items":{"abc":{"fingerprint":"f","source_id":"x"}}}
            state.write_text(json.dumps(original), encoding="utf-8")
            latest.write_text('{"keep":true}', encoding="utf-8")

            with patch.object(c, "CONFIG", config), patch.object(c, "STATE", state), patch.object(c, "HISTORY", history), patch.object(c, "LATEST", latest), patch.object(c, "STATUS", status), patch.object(c, "fetch", side_effect=OSError("down")):
                rc = c.main()

            self.assertEqual(rc, 1)
            self.assertEqual(json.loads(state.read_text(encoding="utf-8")), original)
            self.assertEqual(json.loads(latest.read_text(encoding="utf-8")), {"keep": True})
            self.assertTrue(json.loads(status.read_text(encoding="utf-8"))["state_preserved"])


if __name__ == "__main__":
    unittest.main()
