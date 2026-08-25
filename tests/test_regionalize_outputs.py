import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import regionalize_outputs as regional  # noqa: E402


class DeadlineTimeExactTests(unittest.TestCase):
    def test_explicit_clock_time_is_exact(self):
        self.assertTrue(regional.deadline_time_exact({
            "participation_deadline_at": "2026-09-04T17:00+09:00"
        }))

    def test_date_only_end_of_day_fallback_is_not_exact(self):
        self.assertFalse(regional.deadline_time_exact({
            "participation_deadline_at": "2026-08-27T23:59+09:00"
        }))

    def test_missing_time_is_not_exact(self):
        self.assertFalse(regional.deadline_time_exact({
            "participation_deadline_at": ""
        }))

    def test_true_2359_is_conservatively_suppressed(self):
        # We intentionally prefer a false negative over a false precise 48H/TODAY alert.
        self.assertFalse(regional.deadline_time_exact({
            "participation_deadline_at": "2026-08-31T23:59+09:00"
        }))


if __name__ == "__main__":
    unittest.main()
