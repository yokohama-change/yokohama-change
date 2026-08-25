#!/usr/bin/env python3
"""Fail closed when the official-source collection is incomplete or structurally suspicious.

This gate runs immediately after collect.py. A failed or empty source must not proceed to
normalization, status enrichment, SEO generation, or an automatic public commit.
The previous successfully published dataset therefore remains in place.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "docs" / "data" / "status.json"
CONFIG = ROOT / "config" / "sources.json"
STATE = ROOT / "data" / "state.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    try:
        total = int(payload.get("sources_total", 0))
        ok = int(payload.get("sources_ok", -1))
        seen = int(payload.get("items_seen", 0))
    except (TypeError, ValueError):
        return ["collector counters are invalid"]

    errors = payload.get("errors", [])
    if total <= 0:
        problems.append("sources_total must be positive")
    if ok != total:
        problems.append(f"official sources incomplete: {ok}/{total}")
    if isinstance(errors, list) and errors:
        problems.append(f"collector reported {len(errors)} source error(s)")
    elif not isinstance(errors, list):
        problems.append("collector errors field is invalid")
    if seen <= 0:
        problems.append("collector returned no items")
    if payload.get("state_preserved") is True:
        problems.append("collector preserved stale state")
    return problems


def inventory_summary(config_payload: Any, state_payload: Any) -> dict[str, Any]:
    sources = config_payload.get("sources", []) if isinstance(config_payload, dict) else []
    configured_ids = [
        str(source.get("id", "")).strip()
        for source in sources
        if isinstance(source, dict) and str(source.get("id", "")).strip()
    ]

    items = state_payload.get("items", {}) if isinstance(state_payload, dict) else {}
    counts: Counter[str] = Counter()
    items_without_source_id = 0
    if isinstance(items, dict):
        for value in items.values():
            source_id = str(value.get("source_id", "")).strip() if isinstance(value, dict) else ""
            if source_id:
                counts[source_id] += 1
            else:
                items_without_source_id += 1

    configured_set = set(configured_ids)
    orphan_ids = sorted(source_id for source_id in counts if source_id not in configured_set)
    zero_ids = sorted(source_id for source_id in configured_set if counts.get(source_id, 0) <= 0)
    return {
        "configured_sources": len(configured_ids),
        "unique_configured_sources": len(configured_set),
        "nonempty_sources": sum(1 for source_id in configured_set if counts.get(source_id, 0) > 0),
        "state_items": sum(counts.values()),
        "items_without_source_id": items_without_source_id,
        "zero_item_source_ids": zero_ids,
        "orphan_source_ids": orphan_ids,
        "source_item_counts": {source_id: counts.get(source_id, 0) for source_id in sorted(configured_set)},
    }


def validate_inventory(config_payload: Any, state_payload: Any, status_payload: Any | None = None) -> list[str]:
    problems: list[str] = []
    if not isinstance(config_payload, dict) or not isinstance(config_payload.get("sources"), list):
        return ["source config is invalid"]
    if not config_payload.get("sources"):
        return ["source config is empty"]
    if not isinstance(state_payload, dict) or not isinstance(state_payload.get("items"), dict):
        return ["collector state inventory is invalid"]

    summary = inventory_summary(config_payload, state_payload)
    if summary["configured_sources"] != summary["unique_configured_sources"]:
        problems.append("source config contains duplicate source ids")
    if summary["items_without_source_id"]:
        problems.append(f"collector state has {summary['items_without_source_id']} item(s) without source_id")
    for source_id in summary["zero_item_source_ids"]:
        problems.append(f"official source returned zero current items: {source_id}")
    if summary["orphan_source_ids"]:
        problems.append("collector state contains removed/unknown source ids: " + ", ".join(summary["orphan_source_ids"][:10]))

    if isinstance(status_payload, dict):
        try:
            reported_total = int(status_payload.get("sources_total", -1))
        except (TypeError, ValueError):
            reported_total = -1
        if reported_total != summary["configured_sources"]:
            problems.append(
                f"configured source count mismatch: config={summary['configured_sources']} status={reported_total}"
            )
    return problems


def main() -> int:
    try:
        payload = load_json(STATUS)
        config_payload = load_json(CONFIG)
        state_payload = load_json(STATE)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"SOURCE GATE: invalid input file: {exc}")
        return 1
    if not isinstance(payload, dict):
        print("SOURCE GATE: status payload is not an object")
        return 1

    problems = validate(payload)
    problems.extend(validate_inventory(config_payload, state_payload, payload))
    if problems:
        print("SOURCE GATE: BLOCKED")
        for problem in problems:
            print(f"- {problem}")
        print("Public refresh is stopped; the last successful published dataset remains authoritative.")
        return 1

    inventory = inventory_summary(config_payload, state_payload)
    print(
        "SOURCE GATE: PASS "
        f"({payload.get('sources_ok')}/{payload.get('sources_total')} official sources, "
        f"{payload.get('items_seen')} fetched items, {inventory['nonempty_sources']} non-empty inventories)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
