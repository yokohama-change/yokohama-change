import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import preserve_candidate_history as preserve  # noqa: E402


class CandidatePreservationTests(unittest.TestCase):
    def test_missing_candidate_is_recovered(self):
        latest = [{"id": "new", "commercial_score": 87}]
        candidates = [
            {"id": "old-open", "commercial_score": 59},
            {"id": "new", "commercial_score": 87, "title": "historical revision"},
        ]
        merged, recovered = preserve.merge_candidates(latest, candidates)
        self.assertEqual(recovered, 1)
        self.assertEqual({x["id"] for x in merged}, {"new", "old-open"})

    def test_current_latest_revision_wins(self):
        latest = [{"id": "same", "commercial_score": 87, "title": "current"}]
        candidates = [{"id": "same", "commercial_score": 87, "title": "old"}]
        merged, recovered = preserve.merge_candidates(latest, candidates)
        self.assertEqual(recovered, 0)
        self.assertEqual(merged[0]["title"], "current")


if __name__ == "__main__":
    unittest.main()
