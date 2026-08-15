#!/usr/bin/env python3
"""Normalize the public latest view while preserving the append-only raw history.

The internal history is an event log and may contain multiple revisions of the same
stable item id. The public product should show only the most recent revision per item.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


def main() -> int:
    payload = load_json(LATEST, {})
    if not isinstance(payload, dict):
        return 0
    items = payload.get("items", [])
    if not isinstance(items, list):
        return 0

    before = len(items)
    normalized, duplicates = dedupe_items(items)
    payload["history_events_in_public_window"] = before
    payload["duplicate_revisions_removed"] = duplicates
    payload["items"] = normalized
    payload["count"] = len(normalized)
    LATEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    status = load_json(STATUS, {})
    if not isinstance(status, dict):
        status = {}
    status.update({
        "public_items": len(normalized),
        "public_duplicate_revisions_removed": duplicates,
    })
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"public_items": len(normalized), "duplicates_removed": duplicates}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
