#!/usr/bin/env python3
"""Normalize the public latest view while preserving the append-only raw history.

The internal history is an event log and may contain multiple revisions of the same
stable item id. Multiple official feeds can also point at the same detail URL. The
public product should show one best record per stable id and per canonical official URL.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "docs" / "data" / "latest.json"
STATUS = ROOT / "docs" / "data" / "status.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def dedupe_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep the first occurrence of each stable id; input is already newest-first."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    duplicates = 0
    for item in items:
        stable = str(item.get("id", "")).strip()
        # ID-less records are not collapsed because equality cannot be proven safely.
        if not stable:
            out.append(item)
            continue
        if stable in seen:
            duplicates += 1
            continue
        seen.add(stable)
        out.append(item)
    return out, duplicates


def canonical_url(value: Any) -> str:
    """Return a conservative URL identity key without over-normalizing queries.

    Fragments do not identify a different official page, and trailing slashes are
    normalized. Query strings are deliberately preserved because municipalities can
    use them to identify genuinely different pages/resources.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if scheme not in {"http", "https"} or not netloc:
        return ""
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def preference(item: dict[str, Any]) -> tuple[int, int, int, int, int]:
    """Prefer the more informative duplicate while keeping ties newest-first."""
    def num(name: str) -> int:
        try:
            return int(item.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0

    return (
        num("commercial_score"),
        num("importance"),
        num("urgency"),
        int(bool(str(item.get("description", "") or "").strip())),
        int(bool(str(item.get("source_updated", "") or "").strip())),
    )


def dedupe_urls(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Collapse records that point to the same canonical official URL.

    Records without a valid HTTP(S) URL are retained because equality cannot be
    established safely. For duplicate URLs, the stronger business-signal record wins;
    ties retain the earlier record, preserving the newest-first order.
    """
    out: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    duplicates = 0
    for item in items:
        key = canonical_url(item.get("url"))
        if not key:
            out.append(item)
            continue
        if key not in positions:
            positions[key] = len(out)
            out.append(item)
            continue
        duplicates += 1
        pos = positions[key]
        if preference(item) > preference(out[pos]):
            out[pos] = item
    return out, duplicates


def main() -> int:
    payload = load_json(LATEST, {})
    if not isinstance(payload, dict):
        return 0
    items = payload.get("items", [])
    if not isinstance(items, list):
        return 0

    before = len(items)
    by_id, revision_duplicates = dedupe_items(items)
    normalized, url_duplicates = dedupe_urls(by_id)
    payload["history_events_in_public_window"] = before
    payload["duplicate_revisions_removed"] = revision_duplicates
    payload["duplicate_urls_removed"] = url_duplicates
    payload["items"] = normalized
    payload["count"] = len(normalized)
    LATEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    status = load_json(STATUS, {})
    if not isinstance(status, dict):
        status = {}
    status.update({
        "public_items": len(normalized),
        "public_duplicate_revisions_removed": revision_duplicates,
        "public_duplicate_urls_removed": url_duplicates,
    })
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "public_items": len(normalized),
        "duplicate_revisions_removed": revision_duplicates,
        "duplicate_urls_removed": url_duplicates,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
