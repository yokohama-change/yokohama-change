#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "docs" / "data" / "latest.json"
REPORT = ROOT / "docs" / "data" / "classification.json"

SUPPORT_TERMS = ("補助金", "助成金", "助成", "給付金", "給付", "支援金", "融資", "補助事業")
PROCUREMENT_TERMS = ("入札", "調達", "事業者募集", "指定管理", "業務委託", "委託", "プロポーザル", "公募型")


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def expected_category(item: dict[str, Any]) -> str | None:
    opportunity = str(item.get("opportunity_type") or "").strip()
    if opportunity == "受注機会":
        return "入札・調達"
    if opportunity == "資金・支援":
        return "補助金・支援"

    text = f"{item.get('title') or ''} {item.get('description') or ''}"
    if any(term in text for term in SUPPORT_TERMS):
        return "補助金・支援"
    if any(term in text for term in PROCUREMENT_TERMS):
        return "入札・調達"
    return None


def normalize_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        expected = expected_category(item)
        current = str(item.get("category") or "").strip()
        if expected and current != expected:
            changes.append({
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "from": current,
                "to": expected,
                "opportunity_type": str(item.get("opportunity_type") or ""),
            })
            item["category"] = expected
    return changes


def remaining_conflicts(items: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        opportunity = str(item.get("opportunity_type") or "").strip()
        category = str(item.get("category") or "").strip()
        title = str(item.get("title") or "")
        if opportunity == "受注機会" and category == "補助金・支援":
            problems.append(f"受注機会が補助金・支援に残存: {title[:80]}")
        if opportunity == "資金・支援" and category == "入札・調達":
            problems.append(f"資金・支援が入札・調達に残存: {title[:80]}")
    return problems


def main() -> int:
    payload = load_json(LATEST, {})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []

    changes = normalize_items(items)
    problems = remaining_conflicts(items)
    if isinstance(payload, dict):
        payload["items"] = items
        LATEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "normalized_items": len(changes),
        "changes": changes[:50],
        "errors": problems,
        "checks": {"opportunity_category_consistent": not problems},
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
