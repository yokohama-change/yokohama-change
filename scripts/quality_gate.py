#!/usr/bin/env python3
"""Validate public outputs before they are committed/published."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import enrich_status_multi
import normalize_public
import source_gate

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "docs" / "data" / "latest.json"
STATUS = ROOT / "docs" / "data" / "status.json"
SUMMARY = ROOT / "docs" / "data" / "summary.json"
OPEN_JSON = ROOT / "docs" / "data" / "open_now.json"
QUALITY = ROOT / "docs" / "data" / "quality.json"
CONFIG = ROOT / "config" / "sources.json"
STATE = ROOT / "data" / "state.json"
GBIZ = ROOT / "docs" / "data" / "gbiz_latest.json"
JST = timezone(timedelta(hours=9))
EMPLOYMENT_TERMS = ["会計年度任用職員", "職員採用", "職員募集", "任用職員", "採用選考", "採用試験"]


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def safe_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def main() -> int:
    now = datetime.now(timezone.utc)
    now_jst = now.astimezone(JST)
    latest = load_json(LATEST, {})
    status = load_json(STATUS, {})
    summary = load_json(SUMMARY, {})
    open_feed = load_json(OPEN_JSON, {})
    config = load_json(CONFIG, {})
    state = load_json(STATE, {})
    gbiz = load_json(GBIZ, {})
    items = latest.get("items", []) if isinstance(latest, dict) else []
    open_items = [x for x in items if isinstance(x, dict) and x.get("is_open_now") is True]
    errors: list[str] = []
    warnings: list[str] = []

    # Replay the collection safety checks immediately before publication. This is
    # deliberate defense-in-depth: a future workflow edit must not accidentally
    # bypass SOURCE GATE and still publish an incomplete/empty source inventory.
    if isinstance(status, dict):
        source_problems = source_gate.validate(status)
        source_problems.extend(source_gate.validate_inventory(config, state, status))
    else:
        source_problems = ["status payload is invalid"]
    errors.extend(f"公式ソース整合性: {problem}" for problem in source_problems)
    inventory = source_gate.inventory_summary(config, state)

    configured_sources = config.get("sources", []) if isinstance(config, dict) else []
    source_map = {
        str(source.get("id", "")).strip(): source
        for source in configured_sources
        if isinstance(source, dict) and str(source.get("id", "")).strip()
    }

    ids = [str(x.get("id", "")) for x in items if isinstance(x, dict) and x.get("id")]
    if len(ids) != len(set(ids)):
        errors.append("latest.json に重複IDがあります")

    public_urls = [
        normalize_public.canonical_url(x.get("url"))
        for x in items
        if isinstance(x, dict) and normalize_public.canonical_url(x.get("url"))
    ]
    duplicate_url_count = len(public_urls) - len(set(public_urls))
    if duplicate_url_count:
        errors.append(f"latest.json に同一公式URLの重複が{duplicate_url_count}件あります")

    deadline_field_errors = 0
    provenance_errors = 0
    for item in open_items:
        title = str(item.get("title", ""))
        if item.get("application_status") != "受付中":
            errors.append(f"受付中フラグ不整合: {title[:70]}")
        if item.get("status_confidence") != "high":
            errors.append(f"受付中なのに信頼度highではありません: {title[:70]}")
        if any(term in title for term in EMPLOYMENT_TERMS):
            errors.append(f"採用情報が受付中案件に混入: {title[:70]}")

        source_id = str(item.get("source_id", "") or "").strip()
        source_cfg = source_map.get(source_id)
        if not source_cfg:
            errors.append(f"受付中案件のsource_idが設定に存在しません: {title[:70]}")
            provenance_errors += 1
        else:
            expected_region = str(source_cfg.get("region", "") or "").strip()
            expected_name = str(source_cfg.get("name", "") or "").strip()
            if str(item.get("region", "") or "").strip() != expected_region:
                errors.append(f"受付中案件の地域が公式ソース設定と不一致: {title[:70]}")
                provenance_errors += 1
            if str(item.get("source_name", "") or "").strip() != expected_name:
                errors.append(f"受付中案件のソース名が公式ソース設定と不一致: {title[:70]}")
                provenance_errors += 1

        url = str(item.get("url", "") or "")
        if not enrich_status_multi.approved_detail_url(url):
            errors.append(f"受付中案件のURLが許可済み公式ドメインではありません: {title[:70]}")
            provenance_errors += 1

        cutoff_raw = str(item.get("participation_deadline_at", "") or "")
        deadline_raw = str(item.get("participation_deadline", "") or "")
        if not cutoff_raw:
            errors.append(f"受付中なのに締切日時がありません: {title[:70]}")
            deadline_field_errors += 1
            continue
        try:
            cutoff = datetime.fromisoformat(cutoff_raw)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=JST)
            cutoff_jst = cutoff.astimezone(JST)
            if cutoff_jst < now_jst:
                errors.append(f"過去締切なのに受付中: {title[:70]}")
            if not deadline_raw:
                errors.append(f"受付中なのに締切日がありません: {title[:70]}")
                deadline_field_errors += 1
            elif deadline_raw != cutoff_jst.date().isoformat():
                errors.append(f"締切日と締切日時が不一致: {title[:70]}")
                deadline_field_errors += 1

            expected_days_left = max(0, (cutoff_jst.date() - now_jst.date()).days)
            if safe_int(item.get("days_left")) != expected_days_left:
                errors.append(f"残日数が締切日と不一致: {title[:70]}")
                deadline_field_errors += 1
        except ValueError:
            errors.append(f"締切日時形式エラー: {title[:70]}")
            deadline_field_errors += 1

    expected_open = len(open_items)
    expected_high = sum(1 for x in open_items if safe_int(x.get("commercial_score"), 0) >= 70)
    if safe_int(latest.get("open_now_count")) != expected_open:
        errors.append("latest.json の open_now_count が実データと不一致")
    if safe_int(summary.get("open_now")) != expected_open:
        errors.append("summary.json の open_now が実データと不一致")
    if safe_int(open_feed.get("count")) != expected_open:
        errors.append("open_now.json の count が実データと不一致")
    if safe_int(status.get("application_status_open_now")) != expected_open:
        errors.append("status.json の application_status_open_now が実データと不一致")

    if safe_int(summary.get("open_now_commercial_70_plus")) != expected_high:
        errors.append("summary.json の open_now_commercial_70_plus が実データと不一致")
    if safe_int(open_feed.get("high_value_count")) != expected_high:
        errors.append("open_now.json の high_value_count が実データと不一致")

    open_ids = sorted(str(x.get("id")) for x in open_items if x.get("id"))
    feed_items = open_feed.get("items", []) if isinstance(open_feed, dict) else []
    feed_ids = sorted(
        str(x.get("id")) for x in feed_items if isinstance(x, dict) and x.get("id")
    ) if isinstance(feed_items, list) else []
    if open_ids != feed_ids:
        errors.append("open_now.json の案件ID集合が latest.json の受付中案件と不一致")

    by_region = summary.get("open_now_by_region", {}) if isinstance(summary, dict) else {}
    if not isinstance(by_region, dict) or sum(safe_int(value, 0) for value in by_region.values()) != expected_open:
        errors.append("summary.json の地域別受付中件数が実データと不一致")

    if status.get("application_status_errors"):
        warnings.append(f"締切確認エラー {len(status.get('application_status_errors', []))}件")
    if status.get("application_status_warnings"):
        warnings.append(f"締切確認注意 {len(status.get('application_status_warnings', []))}件")
    if status.get("support_period_errors"):
        warnings.append(f"支援期間確認エラー {len(status.get('support_period_errors', []))}件")
    if status.get("gbiz_errors"):
        warnings.append(f"gBizINFO注意 {len(status.get('gbiz_errors', []))}件")
    if isinstance(gbiz, dict) and gbiz.get("enabled") is True and gbiz.get("stale") is True:
        warnings.append("gBizINFOデータがstaleです")

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
    else:
        errors.append("latest.json に generated_at がありません")

    health = "critical" if errors else "warning" if warnings else "good"
    payload = {
        "checked_at": now.isoformat(timespec="seconds"),
        "health": health,
        "health_label": "要修正" if errors else "注意" if warnings else "正常",
        "errors": errors,
        "warnings": warnings,
        "freshness_minutes": freshness_minutes,
        "open_now": expected_open,
        "open_now_high_value": expected_high,
        "source_inventory": {
            "configured_sources": inventory.get("configured_sources", 0),
            "nonempty_sources": inventory.get("nonempty_sources", 0),
            "state_items": inventory.get("state_items", 0),
            "zero_item_source_ids": inventory.get("zero_item_source_ids", []),
            "orphan_source_ids": inventory.get("orphan_source_ids", []),
        },
        "dedupe": {
            "duplicate_revisions_removed": safe_int(status.get("public_duplicate_revisions_removed"), 0),
            "duplicate_urls_removed": safe_int(status.get("public_duplicate_urls_removed"), 0),
            "remaining_duplicate_urls": duplicate_url_count,
        },
        "checks": {
            "source_inventory_healthy": not source_problems,
            "official_provenance_consistent": provenance_errors == 0,
            "open_deadlines_not_past": not any("過去締切" in e for e in errors),
            "deadline_fields_consistent": deadline_field_errors == 0,
            "employment_excluded": not any("採用情報" in e for e in errors),
            "counts_consistent": not any("件数" in e or "count" in e or "open_now" in e for e in errors),
            "open_feed_ids_consistent": open_ids == feed_ids,
            "high_value_counts_consistent": (
                safe_int(summary.get("open_now_commercial_70_plus")) == expected_high
                and safe_int(open_feed.get("high_value_count")) == expected_high
            ),
            "unique_ids": len(ids) == len(set(ids)),
            "unique_public_urls": duplicate_url_count == 0,
        },
    }
    QUALITY.parent.mkdir(parents=True, exist_ok=True)
    QUALITY.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
