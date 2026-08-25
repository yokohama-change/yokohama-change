#!/usr/bin/env python3
"""Fail closed when the official-source collection is incomplete.

This gate runs immediately after collect.py. A failed source must not proceed to
normalization, status enrichment, SEO generation, or an automatic public commit.
The previous successfully published dataset therefore remains in place.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "docs" / "data" / "status.json"


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


def main() -> int:
    try:
        payload = json.loads(STATUS.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"SOURCE GATE: invalid status file: {exc}")
        return 1
    if not isinstance(payload, dict):
        print("SOURCE GATE: status payload is not an object")
        return 1

    problems = validate(payload)
    if problems:
        print("SOURCE GATE: BLOCKED")
        for problem in problems:
            print(f"- {problem}")
        print("Public refresh is stopped; the last successful published dataset remains authoritative.")
        return 1

    print(f"SOURCE GATE: PASS ({payload.get('sources_ok')}/{payload.get('sources_total')} official sources, {payload.get('items_seen')} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
