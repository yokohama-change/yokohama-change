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

    def inventory(self):
        config = {
            "sources": [
                {"id": "a", "name": "A"},
                {"id": "b", "name": "B"},
            ]
        }
        state = {
            "items": {
                "1": {"source_id": "a", "fingerprint": "x"},
                "2": {"source_id": "a", "fingerprint": "y"},
                "3": {"source_id": "b", "fingerprint": "z"},
            }
        }
        status = self.healthy(sources_total=2, sources_ok=2, items_seen=3)
        return config, state, status

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

    def test_nonempty_inventory_passes(self):
        config, state, status = self.inventory()
        self.assertEqual([], source_gate.validate_inventory(config, state, status))
        summary = source_gate.inventory_summary(config, state)
        self.assertEqual(2, summary["nonempty_sources"])
        self.assertEqual(3, summary["state_items"])

    def test_zero_item_source_blocks(self):
        config, state, status = self.inventory()
        state["items"].pop("3")
        problems = source_gate.validate_inventory(config, state, status)
        self.assertTrue(any("zero current items: b" in p for p in problems))

    def test_orphan_source_blocks(self):
        config, state, status = self.inventory()
        state["items"]["4"] = {"source_id": "removed", "fingerprint": "q"}
        problems = source_gate.validate_inventory(config, state, status)
        self.assertTrue(any("removed/unknown" in p for p in problems))

    def test_duplicate_source_id_blocks(self):
        config, state, status = self.inventory()
        config["sources"].append({"id": "a", "name": "A duplicate"})
        status["sources_total"] = 3
        problems = source_gate.validate_inventory(config, state, status)
        self.assertTrue(any("duplicate source ids" in p for p in problems))

    def test_config_status_count_mismatch_blocks(self):
        config, state, status = self.inventory()
        status["sources_total"] = 3
        problems = source_gate.validate_inventory(config, state, status)
        self.assertTrue(any("count mismatch" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
