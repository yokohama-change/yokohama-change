import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import source_gate  # noqa: E402


class SourceGateTests(unittest.TestCase):
    def healthy(self, **overrides):
        payload = {
            "sources_total": 17,
            "sources_ok": 17,
            "items_seen": 100,
            "errors": [],
            "state_preserved": False,
        }
        payload.update(overrides)
        return payload

    def test_healthy_collection_passes(self):
        self.assertEqual([], source_gate.validate(self.healthy()))

    def test_one_failed_source_blocks(self):
        problems = source_gate.validate(self.healthy(
            sources_ok=16,
            errors=[{"source": "X", "error": "404"}],
        ))
        self.assertTrue(any("16/17" in p for p in problems))
        self.assertTrue(any("source error" in p for p in problems))

    def test_preserved_state_blocks(self):
        problems = source_gate.validate(self.healthy(state_preserved=True))
        self.assertTrue(any("stale state" in p for p in problems))

    def test_zero_items_blocks(self):
        problems = source_gate.validate(self.healthy(items_seen=0))
        self.assertTrue(any("no items" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
