#!/usr/bin/env python3
"""Seed newly configured sources without falsely reporting their existing feed as new.

When YOKOHAMA CHANGE expands to another official source, the first successful fetch is
recorded as a baseline. A small set of the strongest records is added to public history
as `baseline`, while all current item fingerprints are written to state so the following
collector run reports only genuine additions/updates.
"""
from __future__ import annotations

import json
from typing import Any

import collect as core


def load_config() -> dict[str, Any]:
    value = core.load_json(core.CONFIG, {"sources": []})
    return value if isinstance(value, dict) else {"sources": []}


def main() -> int:
    config = load_config()
    raw_state = core.load_json(core.STATE, {"version": 2, "initialized": False, "items": {}})
    prior = core.normalize_prior_state(raw_state if isinstance(raw_state, dict) else {})
    if not prior.get("initialized"):
        # The normal collector already has a first-run baseline mode.
        return 0

    state_items: dict[str, dict[str, str]] = dict(prior.get("items", {}))
    known_source_ids = {v.get("source_id", "") for v in state_items.values() if v.get("source_id")}
    baseline_records: list[dict[str, Any]] = []
    seeded: list[dict[str, Any]] = []

    for source in config.get("sources", []):
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("id", ""))
        if not source_id or source_id in known_source_ids:
            continue
        if source.get("bootstrap_mode") != "baseline":
            continue

        try:
            raw = core.fetch(str(source["url"]))
            if source.get("type") == "rss":
                items = core.parse_rss(raw, source)
            elif source.get("type") == "ckan":
                items = core.parse_ckan(raw, source)
            else:
                continue
        except Exception as exc:
            print(json.dumps({"baseline_source": source_id, "seeded": False, "error": str(exc)[:200]}, ensure_ascii=False))
            continue

        # Seed every current fingerprint into state so the next collector pass does not
        # mislabel the source's historical feed contents as newly published.
        for item in items:
            state_items[item["id"]] = {"fingerprint": item["fingerprint"], "source_id": item["source_id"]}

        limit = max(0, min(int(source.get("baseline_limit", 20) or 20), 50))
        ranked = sorted(
            items,
            key=lambda x: (-int(x.get("commercial_score", 0)), -int(x.get("importance", 0)),
                           -int(x.get("urgency", 0)), str(x.get("title", ""))),
        )[:limit]
        detected_at = core.now_iso()
        for item in ranked:
            public_item = {k: v for k, v in item.items() if k != "fingerprint"}
            public_item.update({"change_type": "baseline", "detected_at": detected_at})
            baseline_records.append(public_item)

        seeded.append({"source_id": source_id, "items_seen": len(items), "baseline_published": len(ranked)})

    if not seeded:
        return 0

    core.STATE.parent.mkdir(parents=True, exist_ok=True)
    core.STATE.write_text(json.dumps({
        "version": 2,
        "initialized": True,
        "updated_at": core.now_iso(),
        "items": state_items,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    core.append_and_prune_history(baseline_records)
    print(json.dumps({"new_source_baselines": seeded}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
