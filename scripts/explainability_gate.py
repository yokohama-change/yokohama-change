#!/usr/bin/env python3
"""Fail closed when an open opportunity cannot explain why it is open.

This gate is deliberately separate from the deadline parser and the general quality
checker. It verifies that every public `is_open_now=true` record carries the minimum
evidence needed for a user-facing verification trace.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "docs" / "data" / "latest.json"
OUT = ROOT / "docs" / "data" / "explainability.json"
OPEN_REASON_MARKER = "明示された新規参加期限"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def validate_open_item(item: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if item.get("is_open_now") is not True:
        return problems

    required_text = {
        "id": "案件ID",
        "source_id": "source_id",
        "source_name": "公式ソース名",
        "region": "地域",
        "url": "公式URL",
        "participation_deadline": "参加期限日",
        "participation_deadline_at": "参加期限日時",
        "status_reason": "判定根拠",
    }
    for key, label in required_text.items():
        if not str(item.get(key, "") or "").strip():
            problems.append(f"{label}がありません")

    if item.get("application_status") != "受付中":
        problems.append("is_open_now=true なのに application_status が受付中ではありません")
    if item.get("status_confidence") != "high":
        problems.append("受付中なのに status_confidence が high ではありません")

    reason = str(item.get("status_reason", "") or "").strip()
    if reason and OPEN_REASON_MARKER not in reason:
        problems.append("判定根拠が新規参加期限の明示確認を示していません")

    if not isinstance(item.get("deadline_time_exact"), bool):
        problems.append("deadline_time_exact が真偽値ではありません")

    url = str(item.get("url", "") or "").strip()
    if url and not url.startswith("https://"):
        problems.append("公式URLがHTTPSではありません")

    cutoff = str(item.get("participation_deadline_at", "") or "").strip()
    if cutoff:
        try:
            parsed = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                problems.append("参加期限日時にタイムゾーンがありません")
        except ValueError:
            problems.append("参加期限日時をISO日時として解釈できません")

    return problems


def build_report(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    open_items = [x for x in items if isinstance(x, dict) and x.get("is_open_now") is True]
    errors: list[dict[str, Any]] = []
    for item in open_items:
        problems = validate_open_item(item)
        if problems:
            errors.append({
                "id": str(item.get("id", "")),
                "title": str(item.get("title", ""))[:120],
                "problems": problems,
            })

    exact = sum(1 for item in open_items if item.get("deadline_time_exact") is True)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "health": "critical" if errors else "good",
        "health_label": "要修正" if errors else "正常",
        "open_now": len(open_items),
        "explainable_open_now": len(open_items) - len(errors),
        "deadline_time_exact": exact,
        "deadline_date_only": len(open_items) - exact,
        "errors": errors,
        "checks": {
            "all_open_items_explainable": not errors,
            "explicit_participation_reason_required": not any(
                any("新規参加期限" in p for p in err.get("problems", [])) for err in errors
            ),
        },
    }


def main() -> int:
    payload = load_json(LATEST, {})
    if not isinstance(payload, dict):
        report = {
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "health": "critical",
            "health_label": "要修正",
            "open_now": 0,
            "explainable_open_now": 0,
            "deadline_time_exact": 0,
            "deadline_date_only": 0,
            "errors": [{"id": "", "title": "", "problems": ["latest.json が不正です"]}],
            "checks": {"all_open_items_explainable": False, "explicit_participation_reason_required": False},
        }
    else:
        report = build_report(payload)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report.get("health") != "good" else 0


if __name__ == "__main__":
    raise SystemExit(main())
