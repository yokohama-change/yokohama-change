#!/usr/bin/env python3
"""Zero-cost public-change collector.

Uses only Python stdlib. It reads official RSS/CKAN sources, compares the latest
snapshot with the prior state, classifies changes with deterministic keywords,
and writes static JSON that can be hosted on GitHub Pages.

Design goals:
- no paid AI/API dependency
- source-isolated failures (one broken feed must not corrupt another feed's state)
- commercial signal fields so the output is closer to a sellable lead/data product
- bounded history so the repository does not grow forever
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "sources.json"
STATE = ROOT / "data" / "state.json"
HISTORY = ROOT / "data" / "history.ndjson"
LATEST = ROOT / "docs" / "data" / "latest.json"
STATUS = ROOT / "docs" / "data" / "status.json"
LEADS_CSV = ROOT / "docs" / "data" / "leads.csv"
SUMMARY = ROOT / "docs" / "data" / "summary.json"
USER_AGENT = "JapanChangeZero/0.2 (+public-data-monitor; respectful-fetching)"
TIMEOUT = 30
MAX_HISTORY_LINES = 5000
PUBLIC_HISTORY_LIMIT = 500

KEYWORDS: dict[str, list[str]] = {
    "補助金・支援": ["補助金", "助成", "給付", "支援金", "融資", "申請受付", "公募", "補助事業"],
    "入札・調達": ["入札", "調達", "契約", "事業者募集", "指定管理", "委託", "プロポーザル", "公募型"],
    "都市・不動産": ["都市計画", "再開発", "地区計画", "用途地域", "道路", "公園", "建築", "開発許可", "市有地", "土地", "区画整理", "整備事業"],
    "事業・雇用": ["中小企業", "事業者", "創業", "採用", "雇用", "就業", "店舗", "商店街", "設備投資", "企業立地"],
    "子育て・教育": ["子育て", "保育", "幼児", "児童", "学校", "教育", "妊娠", "出産", "学童"],
    "制度・ルール": ["条例", "規則", "制度", "改正", "施行", "届出", "許可", "手続", "要綱", "基準"],
    "防災・安全": ["防災", "災害", "避難", "防犯", "消防", "救急", "休館", "通行止", "規制"],
    "施設・イベント": ["開館", "開設", "施設", "イベント", "開催", "募集", "オープン"]
}

HIGH_VALUE = [
    "補助金", "助成", "給付", "入札", "調達", "プロポーザル", "都市計画", "再開発",
    "用途地域", "市有地", "事業者募集", "設備投資", "条例", "改正", "通行止", "開設",
    "公募", "企業立地", "開発許可", "指定管理", "委託"
]

# Who is likely to pay attention to the signal. These are deliberately broad
# buyer segments, not claims that a specific company needs the information.
BUYER_RULES: dict[str, list[str]] = {
    "不動産・建設": ["都市計画", "再開発", "地区計画", "用途地域", "道路", "建築", "開発許可", "市有地", "土地", "区画整理", "整備", "公園"],
    "士業・補助金支援": ["補助金", "助成", "給付", "支援金", "融資", "申請", "公募", "制度", "条例", "改正", "許可", "届出"],
    "法人営業": ["中小企業", "事業者", "創業", "設備投資", "事業者募集", "店舗", "商店街", "企業立地", "採用", "雇用"],
    "入札・公共調達": ["入札", "調達", "契約", "委託", "プロポーザル", "指定管理", "事業者募集", "公募型"],
    "地域メディア": ["開館", "開設", "イベント", "開催", "道路", "公園", "学校", "通行止", "再開発", "市有地"],
}

OPPORTUNITY_RULES: list[tuple[str, list[str]]] = [
    ("受注機会", ["入札", "調達", "委託", "プロポーザル", "指定管理", "事業者募集"]),
    ("資金・支援", ["補助金", "助成", "給付", "支援金", "融資"]),
    ("開発・不動産", ["都市計画", "再開発", "用途地域", "市有地", "開発許可", "区画整理", "整備事業"]),
    ("制度対応", ["条例", "規則", "改正", "施行", "届出", "許可", "手続", "基準"]),
    ("営業シグナル", ["設備投資", "創業", "企業立地", "店舗", "採用", "雇用"]),
    ("地域影響", ["道路", "通行止", "休館", "開館", "開設", "公園", "学校"]),
]

URGENCY_WORDS = {
    "締切": 30, "期限": 24, "受付中": 22, "募集開始": 20, "申請受付": 20,
    "公募": 18, "入札": 24, "プロポーザル": 24, "通行止": 28, "休館": 20,
    "施行": 16, "改正": 14, "本日": 18, "重要": 14,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def first_local_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in node.iter():
        local = child.tag.rsplit("}", 1)[-1]
        if local in names and child.text:
            return clean_text(child.text)
    return ""


def parse_rss(raw: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    root = ET.fromstring(raw)
    items: list[dict[str, Any]] = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "item":
            continue
        title = first_local_text(node, ("title",))
        link = first_local_text(node, ("link", "guid"))
        date = first_local_text(node, ("pubDate", "date", "updated"))
        desc = first_local_text(node, ("description", "summary"))
        if not title or not link:
            continue
        items.append(normalize_item(source, link, title, date, desc, "rss"))
    return items


def parse_ckan(raw: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    payload = json.loads(raw.decode("utf-8"))
    if not payload.get("success"):
        raise ValueError("CKAN API returned success=false")
    rows = payload.get("result", {}).get("results", [])
    items = []
    for row in rows:
        rid = row.get("id") or row.get("name")
        title = clean_text(row.get("title") or row.get("name"))
        if not rid or not title:
            continue
        link = f"https://data.city.yokohama.lg.jp/dataset/{row.get('name', rid)}"
        updated = row.get("metadata_modified") or row.get("metadata_created") or ""
        desc = clean_text(row.get("notes"))
        items.append(normalize_item(source, link, title, updated, desc, "ckan", raw_id=str(rid)))
    return items


def classify(text: str) -> tuple[str, int, list[str]]:
    hits: dict[str, int] = {}
    lowered = text.lower()
    matched: list[str] = []
    for category, words in KEYWORDS.items():
        n = 0
        for word in words:
            if word.lower() in lowered:
                n += 1
                matched.append(word)
        if n:
            hits[category] = n
    category = max(hits, key=hits.get) if hits else "その他"
    score = 20
    score += min(35, sum(hits.values()) * 6)
    score += min(40, sum(1 for w in HIGH_VALUE if w.lower() in lowered) * 12)
    return category, min(100, score), sorted(set(matched))[:10]


def derive_business_signal(text: str, category: str, source_type: str) -> dict[str, Any]:
    lowered = text.lower()
    buyer_segments: list[str] = []
    commercial_hits = 0
    for segment, words in BUYER_RULES.items():
        n = sum(1 for w in words if w.lower() in lowered)
        if n:
            buyer_segments.append(segment)
            commercial_hits += min(n, 3)

    opportunity_type = "情報更新"
    for label, words in OPPORTUNITY_RULES:
        if any(w.lower() in lowered for w in words):
            opportunity_type = label
            break

    urgency = 10
    for word, points in URGENCY_WORDS.items():
        if word.lower() in lowered:
            urgency += points
    # A date-looking expression often indicates a concrete window/deadline.
    if re.search(r"(?:令和\s*[0-9０-９]+年|20\d{2}年)?\s*[0-9０-９]{1,2}月\s*[0-9０-９]{1,2}日", text):
        urgency += 12
    urgency = min(100, urgency)

    commercial = 15 + min(45, commercial_hits * 8)
    commercial += min(30, sum(1 for w in HIGH_VALUE if w.lower() in lowered) * 10)
    if category in {"入札・調達", "補助金・支援", "都市・不動産"}:
        commercial += 10
    # Metadata-only CKAN changes are useful, but should not automatically outrank
    # directly published RSS opportunities unless their wording contains a signal.
    if source_type == "ckan" and commercial_hits == 0:
        commercial -= 10
    commercial = max(0, min(100, commercial))

    if opportunity_type == "受注機会":
        why = "公共案件・事業者募集の可能性があり、受注候補企業が早期確認する価値があります。"
    elif opportunity_type == "資金・支援":
        why = "補助・助成等の利用可能性があり、対象事業者や支援者にとって確認価値があります。"
    elif opportunity_type == "開発・不動産":
        why = "開発・土地利用・周辺環境に影響する可能性があり、不動産・建設事業者の先行確認に向きます。"
    elif opportunity_type == "制度対応":
        why = "制度・許認可・手続の変更可能性があり、対象事業者の対応確認に向きます。"
    elif opportunity_type == "営業シグナル":
        why = "設備・採用・出店等の企業活動シグナルを含む可能性があり、法人営業の探索材料になります。"
    elif opportunity_type == "地域影響":
        why = "施設・道路・地域環境への影響があり、地域事業者やメディアの確認対象になり得ます。"
    else:
        why = "公開情報の更新です。商用判断には原典の内容確認が必要です。"

    return {
        "buyer_segments": buyer_segments[:5],
        "opportunity_type": opportunity_type,
        "commercial_score": commercial,
        "urgency": urgency,
        "why_it_matters": why,
    }


def stable_id(source_id: str, raw_id: str) -> str:
    return hashlib.sha256(f"{source_id}|{raw_id}".encode()).hexdigest()[:20]


def normalize_item(source: dict[str, Any], link: str, title: str, updated: str, desc: str, kind: str, raw_id: str | None = None) -> dict[str, Any]:
    raw_id = raw_id or link
    text = f"{title} {desc}"
    category, score, matched = classify(text)
    business = derive_business_signal(text, category, kind)
    fingerprint = hashlib.sha256(f"{title}|{updated}|{desc}".encode()).hexdigest()
    return {
        "id": stable_id(source["id"], raw_id),
        "source_id": source["id"],
        "source_name": source["name"],
        "source_type": kind,
        "region": source.get("region", ""),
        "title": title,
        "url": link,
        "source_updated": updated,
        # To stay conservative with ordinary website copyright, RSS body text is
        # used for machine classification/fingerprinting but is not republished.
        # CKAN/open-data descriptions may be republished subject to the dataset license.
        "description": desc[:500] if kind == "ckan" else "",
        "license_mode": source.get("license_mode", "unknown"),
        "commercial_redistribution": source.get("commercial_redistribution", "review"),
        "category": category,
        "importance": score,
        "matched_keywords": matched,
        **business,
        "fingerprint": fingerprint,
    }


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def normalize_prior_state(raw: dict[str, Any]) -> dict[str, Any]:
    """Read v1 or v2 state without falsely flagging everything as new."""
    items = raw.get("items", {}) if isinstance(raw, dict) else {}
    normalized: dict[str, dict[str, str]] = {}
    for item_id, value in items.items():
        if isinstance(value, str):  # v1 fingerprint-only format
            normalized[item_id] = {"fingerprint": value, "source_id": ""}
        elif isinstance(value, dict) and value.get("fingerprint"):
            normalized[item_id] = {
                "fingerprint": str(value.get("fingerprint", "")),
                "source_id": str(value.get("source_id", "")),
            }
    return {
        "initialized": bool(raw.get("initialized")) if isinstance(raw, dict) else False,
        "items": normalized,
    }


def load_history(limit: int = PUBLIC_HISTORY_LIMIT) -> list[dict[str, Any]]:
    if not HISTORY.exists():
        return []
    lines = HISTORY.read_text(encoding="utf-8").splitlines()[-limit:]
    result = []
    for line in lines:
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return result


def write_commercial_exports(items: list[dict[str, Any]], generated_at: str) -> None:
    """Write zero-cost machine- and human-friendly commercial exports."""
    ranked = sorted(
        items,
        key=lambda x: (-int(x.get("commercial_score", 0)), -int(x.get("urgency", 0)), -int(x.get("importance", 0))),
    )
    hot = [x for x in ranked if int(x.get("commercial_score", 0)) >= 50][:300]
    LEADS_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "commercial_score", "urgency", "importance", "change_type", "opportunity_type",
        "category", "buyer_segments", "title", "source_name", "license_mode", "source_updated", "detected_at", "url"
    ]
    with LEADS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for x in hot:
            row = {k: x.get(k, "") for k in fields}
            row["buyer_segments"] = " / ".join(x.get("buyer_segments", []))
            writer.writerow(row)

    by_buyer: dict[str, int] = {}
    by_opportunity: dict[str, int] = {}
    for x in items:
        if int(x.get("commercial_score", 0)) < 50:
            continue
        for b in x.get("buyer_segments", []):
            by_buyer[b] = by_buyer.get(b, 0) + 1
        o = x.get("opportunity_type", "情報更新")
        by_opportunity[o] = by_opportunity.get(o, 0) + 1
    summary = {
        "generated_at": generated_at,
        "commercial_50_plus": sum(1 for x in items if int(x.get("commercial_score", 0)) >= 50),
        "commercial_70_plus": sum(1 for x in items if int(x.get("commercial_score", 0)) >= 70),
        "commercial_85_plus": sum(1 for x in items if int(x.get("commercial_score", 0)) >= 85),
        "by_buyer_segment": dict(sorted(by_buyer.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_opportunity_type": dict(sorted(by_opportunity.items(), key=lambda kv: (-kv[1], kv[0]))),
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def append_and_prune_history(changes: list[dict[str, Any]]) -> None:
    if not changes:
        return
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    old_lines = HISTORY.read_text(encoding="utf-8").splitlines() if HISTORY.exists() else []
    new_lines = old_lines + [json.dumps(item, ensure_ascii=False) for item in changes]
    if len(new_lines) > MAX_HISTORY_LINES:
        new_lines = new_lines[-MAX_HISTORY_LINES:]
    HISTORY.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")


def main() -> int:
    config = load_json(CONFIG, {"sources": []})
    raw_prior = load_json(STATE, {"items": {}, "initialized": False})
    prior = normalize_prior_state(raw_prior)
    prior_items: dict[str, dict[str, str]] = prior["items"]
    initialized = bool(prior["initialized"])

    all_items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    ok_source_ids: set[str] = set()

    for source in config.get("sources", []):
        try:
            raw = fetch(source["url"])
            if source["type"] == "rss":
                items = parse_rss(raw, source)
            elif source["type"] == "ckan":
                items = parse_ckan(raw, source)
            else:
                raise ValueError(f"unsupported type: {source['type']}")
            all_items.extend(items)
            ok_source_ids.add(source["id"])
        except Exception as exc:  # source isolation is intentional
            errors.append({"source": source.get("name", source.get("id", "unknown")), "source_id": source.get("id", ""), "error": str(exc)[:300]})

    sources_total = len(config.get("sources", []))
    # Critical safety rule: if every configured source failed, keep the previous
    # state and published data untouched. Otherwise the next recovery run could
    # incorrectly classify the whole universe as newly added.
    if sources_total and not ok_source_ids:
        status_payload = {
            "generated_at": now_iso(),
            "sources_total": sources_total,
            "sources_ok": 0,
            "items_seen": 0,
            "changes_this_run": 0,
            "errors": errors,
            "state_preserved": True,
        }
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        STATUS.write_text(json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(status_payload, ensure_ascii=False, indent=2))
        return 1

    # Deduplicate by stable item id. Prefer the most recently encountered record.
    dedup = {item["id"]: item for item in all_items}
    all_items = list(dedup.values())

    # Preserve prior state for any source that failed during this run. Without this,
    # a temporary one-source outage would make its whole feed appear "new" later.
    current: dict[str, dict[str, str]] = {
        item_id: value for item_id, value in prior_items.items()
        if value.get("source_id") and value.get("source_id") not in ok_source_ids
    }
    for item in all_items:
        current[item["id"]] = {"fingerprint": item["fingerprint"], "source_id": item["source_id"]}

    changes: list[dict[str, Any]] = []
    detected_at = now_iso()
    if initialized:
        for item in all_items:
            old = prior_items.get(item["id"], {}).get("fingerprint")
            if old is None:
                change_type = "added"
            elif old != item["fingerprint"]:
                change_type = "updated"
            else:
                continue
            public_item = {k: v for k, v in item.items() if k != "fingerprint"}
            public_item.update({"change_type": change_type, "detected_at": detected_at})
            changes.append(public_item)
    else:
        # First run is a baseline: show the strongest current records without
        # pretending they were newly published during this run.
        ranked = sorted(
            all_items,
            key=lambda x: (-x["commercial_score"], -x["importance"], -x["urgency"], x["title"]),
        )[:40]
        for item in ranked:
            public_item = {k: v for k, v in item.items() if k != "fingerprint"}
            public_item.update({"change_type": "baseline", "detected_at": detected_at})
            changes.append(public_item)

    changes.sort(key=lambda x: (-x["commercial_score"], -x["importance"], -x["urgency"], x["title"]))
    append_and_prune_history(changes)

    history = load_history(PUBLIC_HISTORY_LIMIT)
    history.sort(
        key=lambda x: (
            x.get("detected_at", ""),
            x.get("commercial_score", 0),
            x.get("importance", 0),
        ),
        reverse=True,
    )
    latest_payload = {
        "generated_at": detected_at,
        "scope": "横浜市 MVP",
        "count": len(history),
        "changes_this_run": len(changes),
        "items": history[:300],
        "disclaimer": "公開情報の自動整理です。商用・契約・投資等の判断は必ずリンク先の公式情報を確認してください。",
    }
    status_payload = {
        "generated_at": detected_at,
        "sources_total": sources_total,
        "sources_ok": len(ok_source_ids),
        "items_seen": len(all_items),
        "changes_this_run": len(changes),
        "errors": errors,
        "state_preserved": False,
    }

    LATEST.parent.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(latest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    STATUS.write_text(json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_commercial_exports(history, detected_at)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"version": 2, "initialized": True, "updated_at": detected_at, "items": current}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(status_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
