#!/usr/bin/env python3
"""Add region-aware metadata after status enrichment.

This keeps the existing conservative status engine intact while making public exports
clear about the expanded Kanagawa beta scope.
"""
from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "docs" / "data" / "latest.json"
STATUS = ROOT / "docs" / "data" / "status.json"
SUMMARY = ROOT / "docs" / "data" / "summary.json"
OPEN_JSON = ROOT / "docs" / "data" / "open_now.json"
OPEN_CSV = ROOT / "docs" / "data" / "open_now.csv"
OPEN_RSS = ROOT / "docs" / "data" / "open_now.rss"
SCOPE = "神奈川県 β（横浜市＋県公式情報）"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main() -> int:
    latest = load_json(LATEST, {})
    items = latest.get("items", []) if isinstance(latest, dict) else []
    if not isinstance(items, list):
        items = []
    latest["scope"] = SCOPE
    latest["disclaimer"] = (
        "神奈川県内の公式公開情報を自動整理しています。『受付中』は公式ページで新規参加期限を明示的に特定した案件だけです。"
        "応募・契約・商用判断は必ずリンク先の公式情報を確認してください。"
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
    open_feed["scope"] = SCOPE
    open_feed["items"] = open_items
    open_feed["note"] = (
        "神奈川県内の公式ページで新規参加期限を明示的に確認でき、現時点で受付中と判定した案件のみ。応募前に原典確認が必要です。"
    )
    OPEN_JSON.write_text(json.dumps(open_feed, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_fields = ["region", "priority_tier", "deadline_label", "participation_deadline", "days_left", "commercial_score",
                  "urgency", "opportunity_type", "category", "buyer_segments", "title", "source_name", "url"]
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
                title.text = "YOKOHAMA CHANGE | 神奈川県内の今、応募できる案件"
            if desc is not None:
                desc.text = "神奈川県内の公式情報から新規参加期限を確認できた受付中案件"
        tree.write(OPEN_RSS, encoding="utf-8", xml_declaration=True)
    except (FileNotFoundError, ET.ParseError):
        pass

    status = load_json(STATUS, {})
    if not isinstance(status, dict):
        status = {}
    status["scope"] = SCOPE
    status["regions_seen"] = regions
    status["open_now_by_region"] = {
        region: sum(1 for x in items if x.get("is_open_now") is True and x.get("region") == region)
        for region in regions
    }
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = load_json(SUMMARY, {})
    if not isinstance(summary, dict):
        summary = {}
    summary["scope"] = SCOPE
    summary["by_region"] = {
        region: sum(1 for x in items if x.get("region") == region)
        for region in regions
    }
    summary["open_now_by_region"] = status["open_now_by_region"]
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"scope": SCOPE, "regions": regions, "open_now_by_region": status["open_now_by_region"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
