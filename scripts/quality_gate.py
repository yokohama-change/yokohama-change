#!/usr/bin/env python3
"""Validate public outputs before they are committed/published."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "docs" / "data" / "latest.json"
STATUS = ROOT / "docs" / "data" / "status.json"
SUMMARY = ROOT / "docs" / "data" / "summary.json"
OPEN_JSON = ROOT / "docs" / "data" / "open_now.json"
QUALITY = ROOT / "docs" / "data" / "quality.json"
JST = timezone(timedelta(hours=9))
EMPLOYMENT_TERMS = ["会計年度任用職員", "職員採用", "職員募集", "任用職員", "採用選考", "採用試験"]


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main() -> int:
    now = datetime.now(timezone.utc)
    now_jst = now.astimezone(JST)
    latest = load_json(LATEST, {})
    status = load_json(STATUS, {})
    summary = load_json(SUMMARY, {})
    open_feed = load_json(OPEN_JSON, {})
    items = latest.get("items", []) if isinstance(latest, dict) else []
    open_items = [x for x in items if x.get("is_open_now") is True]
    errors: list[str] = []
    warnings: list[str] = []

    ids = [str(x.get("id", "")) for x in items if x.get("id")]
    if len(ids) != len(set(ids)):
        errors.append("latest.json に重複IDがあります")

    for item in open_items:
        title = str(item.get("title", ""))
        if item.get("application_status") != "受付中":
            errors.append(f"受付中フラグ不整合: {title[:70]}")
        if item.get("status_confidence") != "high":
            errors.append(f"受付中なのに信頼度highではありません: {title[:70]}")
        if any(term in title for term in EMPLOYMENT_TERMS):
            errors.append(f"採用情報が受付中案件に混入: {title[:70]}")
        cutoff_raw = str(item.get("participation_deadline_at", "") or "")
        if not cutoff_raw:
            errors.append(f"受付中なのに締切日時がありません: {title[:70]}")
        else:
            try:
                cutoff = datetime.fromisoformat(cutoff_raw)
                if cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=JST)
                if cutoff.astimezone(JST) < now_jst:
                    errors.append(f"過去締切なのに受付中: {title[:70]}")
            except ValueError:
                errors.append(f"締切日時形式エラー: {title[:70]}")

    expected_open = len(open_items)
    if int(latest.get("open_now_count", -1)) != expected_open:
        errors.append("latest.json の open_now_count が実データと不一致")
    if int(summary.get("open_now", -1)) != expected_open:
        errors.append("summary.json の open_now が実データと不一致")
    if int(open_feed.get("count", -1)) != expected_open:
        errors.append("open_now.json の count が実データと不一致")

    source_total = int(status.get("sources_total", 0) or 0)
    source_ok = int(status.get("sources_ok", 0) or 0)
    if source_total and source_ok < source_total:
        warnings.append(f"公式ソース成功 {source_ok}/{source_total}")
    if status.get("application_status_errors"):
        warnings.append(f"締切確認エラー {len(status.get('application_status_errors', []))}件")
    if status.get("application_status_warnings"):
        warnings.append(f"締切確認注意 {len(status.get('application_status_warnings', []))}件")
    if status.get("gbiz_errors"):
        warnings.append(f"gBizINFO注意 {len(status.get('gbiz_errors', []))}件")

    generated_raw = str(latest.get("generated_at", "") or "")
    freshness_minutes = None
    if generated_raw:
        try:
            generated = datetime.fromisoformat(generated_raw.replace("Z", "+00:00"))
            if generated.tzinfo is None:
                generated = generated.replace(tzinfo=timezone.utc)
            freshness_minutes = max(0, int((now - generated.astimezone(timezone.utc)).total_seconds() // 60))
            if freshness_minutes > 360:
                warnings.append(f"公開データが{freshness_minutes}分前です")
        except ValueError:
            warnings.append("generated_at を解釈できません")

    health = "critical" if errors else "warning" if warnings else "good"
    payload = {
        "checked_at": now.isoformat(timespec="seconds"),
        "health": health,
        "health_label": "要修正" if errors else "注意" if warnings else "正常",
        "errors": errors,
        "warnings": warnings,
        "freshness_minutes": freshness_minutes,
        "open_now": expected_open,
        "open_now_high_value": sum(1 for x in open_items if int(x.get("commercial_score", 0) or 0) >= 70),
        "checks": {
            "open_deadlines_not_past": not any("過去締切" in e for e in errors),
            "employment_excluded": not any("採用情報" in e for e in errors),
            "counts_consistent": not any("count" in e or "open_now" in e for e in errors),
            "unique_ids": len(ids) == len(set(ids)),
        },
    }
    QUALITY.parent.mkdir(parents=True, exist_ok=True)
    QUALITY.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
