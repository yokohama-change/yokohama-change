#!/usr/bin/env python3
"""Enrich support/subsidy items that publish multi-phase application periods.

Procurement pages usually expose an explicit participation deadline. Support programs
more often publish ranges such as 第1期 4/22 9:00〜8/31 17:00 and 第2期 ... .
This module finds the range containing the current JST time and only then marks it open.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import enrich_status as base

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "docs" / "data" / "latest.json"
STATUS = ROOT / "docs" / "data" / "status.json"
JST = timezone(timedelta(hours=9))
PERIOD_LABELS = ["申請期間", "応募期間", "受付期間", "募集期間", "公募期間"]


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def dated_points(snippet: str, default_year: int) -> list[tuple[date, time | None]]:
    text_value = base.normalize_digits(snippet)
    matches = list(base.DATE_RE.finditer(text_value))
    points: list[tuple[date, time | None]] = []
    for i, match in enumerate(matches):
        dates = base.parse_dates(match.group(0), default_year)
        if not dates:
            continue
        next_start = matches[i + 1].start() if i + 1 < len(matches) else min(len(text_value), match.end() + 80)
        tail = text_value[match.end():next_start]
        points.append((dates[0], base.parse_time_value(tail)))
    return points


def active_period_from_text(text: str, item: dict[str, Any], now_jst: datetime) -> tuple[datetime, str] | None:
    """Return the end of an application range that currently contains now_jst."""
    normalized = base.normalize_digits(text)
    year = base.source_year(item, now_jst.date())
    candidates: list[tuple[datetime, str]] = []
    for label in PERIOD_LABELS:
        pos = 0
        while True:
            idx = normalized.find(label, pos)
            if idx < 0:
                break
            # Enough for adjacent phases, but short enough to avoid later result-report sections.
            snippet = normalized[idx: idx + 1400]
            points = dated_points(snippet, year)
            # Consecutive date points are interpreted as start/end ranges.
            for i in range(0, len(points) - 1, 2):
                start_d, start_t = points[i]
                end_d, end_t = points[i + 1]
                start_at = datetime.combine(start_d, start_t or time(0, 0), JST)
                end_at = datetime.combine(end_d, end_t or time(23, 59, 59), JST)
                if start_at <= now_jst <= end_at:
                    candidates.append((end_at, f"支援制度:{label}"))
            pos = idx + len(label)
    if not candidates:
        return None
    return min(candidates, key=lambda x: x[0])


def is_support_candidate(item: dict[str, Any]) -> bool:
    if base.is_employment_notice(item):
        return False
    return (
        item.get("opportunity_type") == "資金・支援"
        or item.get("category") == "補助金・支援"
        or any(term in str(item.get("title", "")) for term in ["補助金", "助成金", "支援金"])
    ) and base.official_detail_url(str(item.get("url", "")))


def main() -> int:
    payload = load_json(LATEST, {})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return 0

    now_jst = datetime.now(JST)
    updated = 0
    checked = 0
    errors: list[dict[str, str]] = []
    for item in items:
        if not is_support_candidate(item):
            continue
        # Already-high-confidence open items need no second fetch.
        if item.get("is_open_now") is True and item.get("status_confidence") == "high":
            continue
        checked += 1
        try:
            text = base.fetch_page_text(str(item["url"]))
            active = active_period_from_text(text, item, now_jst)
            if not active:
                continue
            cutoff, source = active
            facts = {
                "participation_deadline": cutoff.date().isoformat(),
                "participation_deadline_at": cutoff.isoformat(timespec="minutes"),
                "participation_source": source,
                "downstream_dates": [],
                "result_hit": False,
                "closed_hit": False,
            }
            item.update(base.classify_status(facts, now_jst.date(), now_jst=now_jst))
            base.enrich_open_metadata(item, now_jst.date())
            item["status_source_state"] = "support_period_fetched"
            updated += 1
        except Exception as exc:
            errors.append({"title": str(item.get("title", ""))[:100], "error": f"{type(exc).__name__}: {str(exc)[:160]}"})

    payload["items"] = items
    payload["open_now_count"] = sum(1 for x in items if x.get("is_open_now") is True)
    payload["open_now_high_value_count"] = sum(1 for x in items if x.get("is_open_now") is True and int(x.get("commercial_score", 0) or 0) >= 70)
    LATEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    base.rewrite_exports(items, payload.get("generated_at", base.now_iso()))

    status = load_json(STATUS, {})
    if not isinstance(status, dict):
        status = {}
    status.update({
        "support_period_candidates_checked": checked,
        "support_period_open_enriched": updated,
        "support_period_errors": errors[:20],
        "application_status_open_now": sum(1 for x in items if x.get("is_open_now") is True),
    })
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checked": checked, "open_enriched": updated, "errors": len(errors)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
