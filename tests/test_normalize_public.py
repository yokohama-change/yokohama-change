import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "scripts" / "normalize_public.py"
spec = importlib.util.spec_from_file_location("normalize_public", p)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class NormalizePublicTests(unittest.TestCase):
    def test_keeps_newest_first_revision(self):
        items = [
            {"id": "A", "title": "new"},
            {"id": "B", "title": "other"},
            {"id": "A", "title": "old"},
        ]
        out, removed = s.dedupe_items(items)
        self.assertEqual([x["title"] for x in out], ["new", "other"])
        self.assertEqual(removed, 1)

    def test_idless_items_are_not_collapsed(self):
        items = [{"title": "x"}, {"title": "x"}]
        out, removed = s.dedupe_items(items)
        self.assertEqual(len(out), 2)
        self.assertEqual(removed, 0)


if __name__ == "__main__":
    unittest.main()
