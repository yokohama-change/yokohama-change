#!/usr/bin/env python3
"""Add region-aware metadata and conservative preparation guidance.

The beta expands source by source. Public metadata names only the regions currently
collected. 48H/TODAY remains limited to officially explicit clock times.

Preparation guidance is intentionally separate from official deadlines. It is a simple,
transparent YOKOHAMA CHANGE heuristic used to answer "when should I start preparing?"
and must never be presented as an official requirement or legal deadline.
"""
from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "docs" / "data" / "latest.json"
STATUS = ROOT / "docs" / "data" / "status.json"
SUMMARY = ROOT / "docs" / "data" / "summary.json"
OPEN_JSON = ROOT / "docs" / "data" / "open_now.json"
OPEN_CSV = ROOT / "docs" / "data" / "open_now.csv"
OPEN_RSS = ROOT / "docs" / "data" / "open_now.rss"
SCOPE = "神奈川 β（神奈川県・横浜市・川崎市・相模原市）"
PLANNED_REGIONS = ["神奈川県", "横浜市", "川崎市", "相模原市"]
PREPARATION_NOTE = "YOKOHAMA CHANGE独自の準備目安です。公式期限・応募要件ではありません。"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def deadline_time_exact(item: dict[str, Any]) -> bool:
    """Conservative proxy for an explicitly stated clock time.

    The legacy status engine fills date-only deadlines with 23:59. We therefore treat
    23:59 as *not exact*. A genuinely official 23:59 deadline will also be suppressed
    from 48H/TODAY, intentionally preferring a false negative to a false precise alert.
    """
    raw = str(item.get("participation_deadline_at", "") or "")
    match = re.search(r"T(\d{2}):(\d{2})", raw)
    if not match:
        return False
    return (match.group(1), match.group(2)) != ("23", "59")


def preparation_days(item: dict[str, Any]) -> int:
    """Return a deterministic preparation lead-time heuristic in calendar days."""
    opportunity_type = str(item.get("opportunity_type", "") or "")
    category = str(item.get("category", "") or "")
    title = str(item.get("title", "") or "")

    if opportunity_type == "開発・不動産" or "指定管理" in title:
        return 14
    if category == "入札・調達" or opportunity_type == "受注機会":
        return 10
    if category == "補助金・支援" or opportunity_type == "資金・支援":
        return 7
    return 7


def preparation_metadata(item: dict[str, Any], today: date) -> dict[str, Any]:
    raw = str(item.get("participation_deadline", "") or "")
    if item.get("is_open_now") is not True or not raw:
        return {
            "preparation_days": None,
            "preparation_start_date": "",
            "preparation_status": "",
            "preparation_note": PREPARATION_NOTE,
        }
    try:
        deadline = date.fromisoformat(raw)
    except ValueError:
        return {
            "preparation_days": None,
            "preparation_start_date": "",
            "preparation_status": "",
            "preparation_note": PREPARATION_NOTE,
        }

    days = preparation_days(item)
    start = deadline - timedelta(days=days)
    if today >= deadline:
        status = "締切日"
    elif today >= start:
        status = "準備開始推奨"
    else:
        status = "準備開始前"
    return {
        "preparation_days": days,
        "preparation_start_date": start.isoformat(),
        "preparation_status": status,
        "preparation_note": PREPARATION_NOTE,
    }


def generated_tokyo_date(payload: dict[str, Any]) -> date:
    raw = str(payload.get("generated_at", "") or "")
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo("Asia/Tokyo")).date()
    except ValueError:
        return datetime.now(ZoneInfo("Asia/Tokyo")).date()


def main() -> int:
    latest = load_json(LATEST, {})
    items = latest.get("items", []) if isinstance(latest, dict) else []
    if not isinstance(items, list):
        items = []
    today = generated_tokyo_date(latest if isinstance(latest, dict) else {})

    for item in items:
        if isinstance(item, dict):
            item["deadline_time_exact"] = deadline_time_exact(item)
            item.update(preparation_metadata(item, today))

    region_copy = " / ".join(PLANNED_REGIONS)
    latest["scope"] = SCOPE
    latest["coverage_regions"] = PLANNED_REGIONS
    latest["disclaimer"] = (
        f"無料βでは {region_copy} の公式公開情報から段階的に収集しています。"
        "『受付中』は公式ページで新規参加期限を明示的に特定した案件だけです。"
        "48H/TODAYは締切時刻まで明示確認できた案件だけを対象にします。"
        "『準備開始』はYOKOHAMA CHANGE独自の目安で、公式期限・応募要件ではありません。"
        "県内全自治体を網羅済みという意味ではありません。応募・契約・商用判断は必ずリンク先の公式情報を確認してください。"
    )
    LATEST.write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")

    by_id = {str(x.get("id", "")): x for x in items if isinstance(x, dict) and x.get("id")}
    regions = sorted({str(x.get("region", "")).strip() for x in items if str(x.get("region", "")).strip()})

    open_feed = load_json(OPEN_JSON, {})
    open_items = open_feed.get("items", []) if isinstance(open_feed, dict) else []
    if not isinstance(open_items, list):
        open_items = []
    for item in open_items:
        original = by_id.get(str(item.get("id", "")), {})
        item["region"] = original.get("region", "")
        item["deadline_time_exact"] = bool(original.get("deadline_time_exact", False))
        for key in ("preparation_days", "preparation_start_date", "preparation_status", "preparation_note"):
            item[key] = original.get(key)
    open_feed["scope"] = SCOPE
    open_feed["coverage_regions"] = PLANNED_REGIONS
    open_feed["items"] = open_items
    open_feed["note"] = (
        f"{region_copy} の公式ページで新規参加期限を明示的に確認でき、現時点で受付中と判定した案件のみ。"
        "48H/TODAYはdeadline_time_exact=trueの案件だけを対象にします。"
        "preparation_* は独自の準備目安で公式期限ではありません。県内全自治体の網羅ではなく、応募前に原典確認が必要です。"
    )
    OPEN_JSON.write_text(json.dumps(open_feed, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_fields = [
        "region", "deadline_time_exact", "preparation_status", "preparation_start_date", "preparation_days",
        "priority_tier", "deadline_label", "participation_deadline", "days_left", "commercial_score",
        "urgency", "opportunity_type", "category", "buyer_segments", "title", "source_name", "url"
    ]
    with OPEN_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for item in open_items:
            row = {k: item.get(k, "") for k in csv_fields}
            row["buyer_segments"] = " / ".join(item.get("buyer_segments", [])) if isinstance(item.get("buyer_segments"), list) else item.get("buyer_segments", "")
            writer.writerow(row)

    try:
        tree = ET.parse(OPEN_RSS)
        root = tree.getroot()
        channel = root.find("channel")
        if channel is not None:
            title = channel.find("title")
            desc = channel.find("description")
            if title is not None:
                title.text = "YOKOHAMA CHANGE | 神奈川の今、応募できる案件"
            if desc is not None:
                desc.text = "神奈川県内の段階対応地域から、新規参加期限を確認できた受付中案件"
        tree.write(OPEN_RSS, encoding="utf-8", xml_declaration=True)
    except (FileNotFoundError, ET.ParseError):
        pass

    status = load_json(STATUS, {})
    if not isinstance(status, dict):
        status = {}
    status["scope"] = SCOPE
    status["coverage_regions"] = PLANNED_REGIONS
    status["regions_seen"] = regions
    status["open_now_by_region"] = {
        region: sum(1 for x in items if x.get("is_open_now") is True and x.get("region") == region)
        for region in PLANNED_REGIONS
    }
    status["open_now_exact_time"] = sum(
        1 for x in items if x.get("is_open_now") is True and x.get("deadline_time_exact") is True
    )
    status["open_now_high_value_exact_time"] = sum(
        1 for x in items
        if x.get("is_open_now") is True
        and int(x.get("commercial_score", 0) or 0) >= 70
        and x.get("deadline_time_exact") is True
    )
    status["preparation_due_now"] = sum(
        1 for x in items if x.get("is_open_now") is True and x.get("preparation_status") == "準備開始推奨"
    )
    status["preparation_due_now_high_value"] = sum(
        1 for x in items
        if x.get("is_open_now") is True
        and x.get("preparation_status") == "準備開始推奨"
        and int(x.get("commercial_score", 0) or 0) >= 70
    )
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = load_json(SUMMARY, {})
    if not isinstance(summary, dict):
        summary = {}
    summary["scope"] = SCOPE
    summary["coverage_regions"] = PLANNED_REGIONS
    summary["by_region"] = {region: sum(1 for x in items if x.get("region") == region) for region in PLANNED_REGIONS}
    summary["open_now_by_region"] = status["open_now_by_region"]
    summary["open_now_exact_time"] = status["open_now_exact_time"]
    summary["open_now_high_value_exact_time"] = status["open_now_high_value_exact_time"]
    summary["preparation_due_now"] = status["preparation_due_now"]
    summary["preparation_due_now_high_value"] = status["preparation_due_now_high_value"]
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "scope": SCOPE,
        "regions_seen": regions,
        "open_now_by_region": status["open_now_by_region"],
        "open_now_exact_time": status["open_now_exact_time"],
        "open_now_high_value_exact_time": status["open_now_high_value_exact_time"],
        "preparation_due_now": status["preparation_due_now"],
        "preparation_due_now_high_value": status["preparation_due_now_high_value"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
