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

    def test_same_official_url_different_ids_collapses(self):
        items = [
            {"id": "A", "url": "https://example.jp/a", "commercial_score": 70},
            {"id": "B", "url": "https://example.jp/a", "commercial_score": 70},
        ]
        out, removed = s.dedupe_urls(items)
        self.assertEqual(1, len(out))
        self.assertEqual("A", out[0]["id"])
        self.assertEqual(1, removed)

    def test_stronger_duplicate_wins(self):
        items = [
            {"id": "A", "url": "https://example.jp/a", "commercial_score": 50, "importance": 40},
            {"id": "B", "url": "https://example.jp/a", "commercial_score": 90, "importance": 80},
        ]
        out, removed = s.dedupe_urls(items)
        self.assertEqual(1, removed)
        self.assertEqual("B", out[0]["id"])

    def test_fragment_only_difference_collapses(self):
        items = [
            {"id": "A", "url": "https://EXAMPLE.jp/a/#top"},
            {"id": "B", "url": "https://example.jp/a"},
        ]
        out, removed = s.dedupe_urls(items)
        self.assertEqual(1, len(out))
        self.assertEqual(1, removed)

    def test_query_difference_is_preserved(self):
        items = [
            {"id": "A", "url": "https://example.jp/feed?id=1"},
            {"id": "B", "url": "https://example.jp/feed?id=2"},
        ]
        out, removed = s.dedupe_urls(items)
        self.assertEqual(2, len(out))
        self.assertEqual(0, removed)

    def test_missing_or_invalid_url_is_not_collapsed(self):
        items = [
            {"id": "A", "title": "x"},
            {"id": "B", "title": "x"},
            {"id": "C", "url": "not-a-url"},
            {"id": "D", "url": "not-a-url"},
        ]
        out, removed = s.dedupe_urls(items)
        self.assertEqual(4, len(out))
        self.assertEqual(0, removed)

    def test_trailing_slash_normalizes(self):
        self.assertEqual(
            s.canonical_url("https://example.jp/a/"),
            s.canonical_url("https://example.jp/a"),
        )


if __name__ == "__main__":
    unittest.main()
