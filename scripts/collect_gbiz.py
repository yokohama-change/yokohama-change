#!/usr/bin/env python3
"""Collect gBizINFO corporate-update signals without mislabeling them as open opportunities.

The current Gビズインフォ V2 period-specified endpoint documented by the service is
/v2/hojin/updateInfo. We intentionally do not call legacy-looking per-category
/updateInfo/procurement or /updateInfo/subsidy paths because they are not part of the
current period-search contract and were returning 404.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "gbiz_latest.json"
STATUS = ROOT / "docs" / "data" / "status.json"
BASE = "https://api.info.gbiz.go.jp/hojin/v2/hojin/updateInfo"
JST = timezone(timedelta(hours=9))
TIMEOUT = 45


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def fetch_json(url: str, token: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={
        "X-hojinInfo-api-token": token,
        "Accept": "application/json",
        "User-Agent": "YokohamaChange/0.7 (+gbiz-corporate-update-signal)",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_companies(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, dict):
        for key in ("hojin-infos", "hojin_infos", "hojinInfos", "items", "results"):
            value = obj.get(key)
            if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                return value
        for value in obj.values():
            found = find_companies(value)
            if found:
                return found
    return []


def is_yokohama_company(company: dict[str, Any]) -> bool:
    return "横浜市" in json.dumps(company, ensure_ascii=False)


def compact_company(company: dict[str, Any]) -> dict[str, Any]:
    number = company.get("corporate_number") or company.get("corporateNumber") or company.get("corporate-number") or ""
    name = company.get("name") or company.get("corporate_name") or company.get("corporateName") or ""
    location = company.get("location") or company.get("address") or company.get("headquarter_location") or ""
    return {
        "signal_type": "法人情報更新",
        "signal_scope": "営業シグナル",
        "is_current_opportunity": False,
        "corporate_number": number,
        "name": name,
        "location": location if isinstance(location, str) else "",
        "note": "法人情報の更新シグナルです。現在募集中の調達・補助金を意味しません。",
    }


def update_status(**values: Any) -> None:
    status = load_json(STATUS, {})
    if not isinstance(status, dict):
        status = {}
    status.update(values)
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    token = os.environ.get("GBIZINFO_API_TOKEN", "").strip()
    today = datetime.now(JST).date()
    from_day = (today - timedelta(days=2)).strftime("%Y%m%d")
    to_day = today.strftime("%Y%m%d")
    period = {"from": from_day, "to": to_day}

    if not token:
        payload = {
            "generated_at": now_iso(), "enabled": False, "stale": False, "period": period,
            "count": 0, "items": [], "errors": [],
            "note": "GBIZINFO_API_TOKEN が未設定のため法人更新シグナルは停止中です。",
            "signal_semantics": "gBizINFOは営業シグナルとして扱い、現在募集中の案件とは分離します。",
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        update_status(gbiz_enabled=False, gbiz_period=period, gbiz_items_seen=0, gbiz_errors=[])
        print(json.dumps({"gbiz_enabled": False}, ensure_ascii=False))
        return 0

    params = urllib.parse.urlencode({"from": from_day, "to": to_day, "page": 1})
    try:
        response = fetch_json(BASE + "?" + params, token)
        companies = [compact_company(c) for c in find_companies(response) if is_yokohama_company(c)]
        seen: set[tuple[str, str]] = set()
        items: list[dict[str, Any]] = []
        for company in companies:
            key = (str(company.get("corporate_number", "")), str(company.get("name", "")))
            if key in seen:
                continue
            seen.add(key)
            items.append(company)
        payload = {
            "generated_at": now_iso(), "enabled": True, "stale": False, "period": period,
            "count": len(items), "items": items[:500], "errors": [],
            "endpoint_mode": "v2-period-corporate-update-only",
            "note": "法人情報の更新シグナルです。現在募集中の調達・補助金ではありません。",
            "signal_semantics": "営業先探索の補助情報。応募可能案件は YOKOHAMA CHANGE の受付中フィードを参照してください。",
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        update_status(gbiz_enabled=True, gbiz_period=period, gbiz_items_seen=len(items), gbiz_errors=[],
                      gbiz_endpoint_mode="v2-period-corporate-update-only")
        print(json.dumps({"gbiz_items_seen": len(items), "errors": 0}, ensure_ascii=False))
        return 0
    except Exception as exc:
        error = f"{type(exc).__name__}: {str(exc)[:240]}"
        previous = load_json(OUT, {})
        if not isinstance(previous, dict):
            previous = {}
        payload = {**previous, "last_attempt_at": now_iso(), "enabled": True, "stale": True, "period": period,
                   "errors": [{"source": "法人情報更新", "error": error}],
                   "note": "gBizINFO更新取得に失敗したため、直前データを保持しています。現在募集中の案件とは分離されています。"}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        update_status(gbiz_enabled=True, gbiz_period=period, gbiz_items_seen=int(previous.get("count", 0) or 0),
                      gbiz_errors=[{"source": "法人情報更新", "error": error}],
                      gbiz_endpoint_mode="v2-period-corporate-update-only")
        print(json.dumps({"gbiz_stale": True, "error": error}, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
