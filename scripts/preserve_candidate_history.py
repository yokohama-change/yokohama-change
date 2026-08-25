#!/usr/bin/env python3
"""Keep known opportunity candidates in the public status-evaluation window.

Collector history is intentionally bounded and the public latest window is even smaller.
When new municipalities are baseline-seeded, those records can push older-but-still-open
opportunities out of latest.json before the status engine has a chance to re-evaluate
those opportunities. This script prevents that failure mode.

All historical records with commercial_score >= 50 are treated as a candidate registry.
They are merged back into latest.json (deduped by stable id) before status enrichment.
The status engine then decides whether each record is open, closed or unknown. This does
NOT make old records open; it only guarantees they are not silently forgotten because of
an unrelated source expansion.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "history.ndjson"
LATEST = ROOT / "docs" / "data" / "latest.json"
MIN_COMMERCIAL = 50


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def load_candidate_history() -> list[dict[str, Any]]:
    if not HISTORY.exists():
        return []
    newest_by_id: dict[str, dict[str, Any]] = {}
    # Later lines are newer revisions, so overwrite earlier revisions.
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        stable = str(item.get("id", "")).strip()
        if not stable:
            continue
        if int(item.get("commercial_score", 0) or 0) < MIN_COMMERCIAL:
            continue
        newest_by_id[stable] = item
    return list(newest_by_id.values())


def merge_candidates(latest_items: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    # Existing latest records win because they may contain a newer revision than the
    # historical candidate registry.
    existing_ids = {str(x.get("id", "")) for x in latest_items if isinstance(x, dict) and x.get("id")}
    recovered = [x for x in candidates if str(x.get("id", "")) not in existing_ids]
    merged = latest_items + recovered
    return merged, len(recovered)


def main() -> int:
    payload = load_json(LATEST, {})
    if not isinstance(payload, dict):
        return 0
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []

    candidates = load_candidate_history()
    merged, recovered = merge_candidates(items, candidates)
    payload["items"] = merged
    payload["count"] = len(merged)
    payload["candidate_registry_size"] = len(candidates)
    payload["candidate_registry_recovered"] = recovered
    LATEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "candidate_registry_size": len(candidates),
        "candidate_registry_recovered": recovered,
        "latest_items": len(merged),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
