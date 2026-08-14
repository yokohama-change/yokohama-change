#!/usr/bin/env python3
"""Enrich YOKOHAMA CHANGE items with application-window status.

This script runs after collect.py. It only fetches official Yokohama City detail
pages for high-value procurement/support opportunities, extracts date facts,
caches those facts, and recomputes the status against today's JST date on every
run. Page text is used for classification only and is not republished.
"""
from __future__ import annotations

import csv
import html
import json
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "docs" / "data" / "latest.json"
STATUS = ROOT / "docs" / "data" / "status.json"
LEADS_CSV = ROOT / "docs" / "data" / "leads.csv"
SUMMARY = ROOT / "docs" / "data" / "summary.json"
CACHE = ROOT / "data" / "application_status_cache.json"
USER_AGENT = "YokohamaChange/0.5 (+application-status; respectful-fetching)"
TIMEOUT = 30
MAX_PAGE_FETCHES = 40
JST = timezone(timedelta(hours=9))

PARTICIPATION_TERMS = [
    "参加意向申出書", "参加意向申出", "参加申込", "参加申し込み", "参加表明",
    "参加資格確認申請", "入札参加申込", "応募申込", "応募受付", "申請受付",
    "申請期限", "申込期限", "受付期間", "募集期間", "応募期間", "申請期間", "公募期間",
]
DOWNSTREAM_TERMS = [
    "質問書", "質問受付", "質問期限", "提案書", "提案期限", "企画提案書",
    "入札書", "見積書", "プレゼンテーション", "ヒアリング",
]
GENERAL_DEADLINE_TERMS = [
    "提出期限", "応募締切", "応募締め切り", "募集締切", "募集締め切り",
    "受付期限", "公募締切", "公募締め切り", "締切", "締め切り",
]
RESULT_TERMS = [
    "選定結果", "特定結果", "契約結果", "落札結果", "入札結果", "審査結果",
    "結果を掲載", "結果公表", "選考結果",
]
DATE_RE = re.compile(
    r"(?:(?:令和\s*(?P<era_year>\d{1,2})年)|(?P<year>20\d{2})年)?\s*"
    r"(?P<month>\d{1,2})月\s*(?P<day>\d{1,2})日"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def normalize_digits(text: str) -> str:
    return text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        elif tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        elif tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        value = html.unescape(" ".join(self.parts))
        value = normalize_digits(value)
        value = re.sub(r"[\t\r ]+", " ", value)
        value = re.sub(r"\n\s*\n+", "\n", value)
        return value.strip()


def fetch_page_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
    parser = VisibleTextParser()
    parser.feed(raw.decode(charset, errors="replace"))
    return parser.text()


def official_detail_url(url: str) -> bool:
    try:
        p = urlparse(url)
    except ValueError:
        return False
    return p.scheme == "https" and p.hostname == "www.city.yokohama.lg.jp"


def source_year(item: dict[str, Any], today: date) -> int:
    s = normalize_digits(str(item.get("source_updated", "")))
    m = re.search(r"(20\d{2})", s)
    return int(m.group(1)) if m else today.year


def parse_dates(snippet: str, default_year: int) -> list[date]:
    out: list[date] = []
    for m in DATE_RE.finditer(normalize_digits(snippet)):
        try:
            if m.group("era_year"):
                year = 2018 + int(m.group("era_year"))
            elif m.group("year"):
                year = int(m.group("year"))
            else:
                year = default_year
            out.append(date(year, int(m.group("month")), int(m.group("day"))))
        except ValueError:
            continue
    return out


def dates_near_terms(text: str, terms: list[str], default_year: int) -> list[date]:
    dates: list[date] = []
    for term in terms:
        start = 0
        while True:
            idx = text.find(term, start)
            if idx < 0:
                break
            # Most city pages put the relevant date just after a heading/label.
            snippet = text[max(0, idx - 50): min(len(text), idx + 240)]
            dates.extend(parse_dates(snippet, default_year))
            start = idx + len(term)
    return sorted(set(dates))


def extract_facts(text: str, item: dict[str, Any], today: date) -> dict[str, Any]:
    normalized = normalize_digits(text)
    year = source_year(item, today)
    participation = dates_near_terms(normalized, PARTICIPATION_TERMS, year)
    downstream = dates_near_terms(normalized, DOWNSTREAM_TERMS, year)
    generic = dates_near_terms(normalized, GENERAL_DEADLINE_TERMS, year)
    result_hit = any(term in normalized for term in RESULT_TERMS)
    return {
        "participation_dates": [d.isoformat() for d in participation],
        "downstream_dates": [d.isoformat() for d in downstream],
        "generic_dates": [d.isoformat() for d in generic],
        "result_hit": result_hit,
    }


def to_dates(values: list[str]) -> list[date]:
    out: list[date] = []
    for value in values:
        try:
            out.append(date.fromisoformat(value))
        except (TypeError, ValueError):
            pass
    return sorted(set(out))


def classify_status(facts: dict[str, Any], today: date) -> dict[str, Any]:
    participation = to_dates(facts.get("participation_dates", []))
    downstream = to_dates(facts.get("downstream_dates", []))
    generic = to_dates(facts.get("generic_dates", []))
    result_hit = bool(facts.get("result_hit"))

    participation_deadline = max(participation) if participation else None
    downstream_future = [d for d in downstream if d >= today]
    generic_future = [d for d in generic if d >= today]
    next_downstream = min(downstream_future) if downstream_future else None
    next_generic = min(generic_future) if generic_future else None
    any_past = any(d < today for d in participation + downstream + generic)

    if participation_deadline:
        if participation_deadline >= today:
            return {
                "application_status": "受付中",
                "is_open_now": True,
                "participation_deadline": participation_deadline.isoformat(),
                "next_deadline": participation_deadline.isoformat(),
                "status_confidence": "high",
                "status_reason": f"参加・申込期限を{participation_deadline.isoformat()}と判定",
            }
        if next_downstream:
            return {
                "application_status": "資格者のみ進行中",
                "is_open_now": False,
                "participation_deadline": participation_deadline.isoformat(),
                "next_deadline": next_downstream.isoformat(),
                "status_confidence": "high",
                "status_reason": "新規参加期限は終了。質問・提案等の後続期限あり",
            }
        return {
            "application_status": "結果掲載済" if result_hit else "参加締切済",
            "is_open_now": False,
            "participation_deadline": participation_deadline.isoformat(),
            "next_deadline": "",
            "status_confidence": "high" if not result_hit else "medium",
            "status_reason": "新規参加期限を経過" if not result_hit else "新規参加期限を経過し、結果掲載語を検出",
        }

    if next_generic:
        return {
            "application_status": "受付中",
            "is_open_now": True,
            "participation_deadline": "",
            "next_deadline": next_generic.isoformat(),
            "status_confidence": "medium",
            "status_reason": f"募集・提出期限を{next_generic.isoformat()}と判定",
        }

    if result_hit and any_past:
        return {
            "application_status": "結果掲載済",
            "is_open_now": False,
            "participation_deadline": "",
            "next_deadline": "",
            "status_confidence": "medium",
            "status_reason": "過去期限と結果掲載語を検出",
        }
    if any_past:
        return {
            "application_status": "参加締切済",
            "is_open_now": False,
            "participation_deadline": "",
            "next_deadline": "",
            "status_confidence": "medium",
            "status_reason": "募集・提出期限を経過",
        }
    if result_hit:
        return {
            "application_status": "結果掲載済",
            "is_open_now": False,
            "participation_deadline": "",
            "next_deadline": "",
            "status_confidence": "low",
            "status_reason": "結果掲載語を検出",
        }
    return {
        "application_status": "判定不可",
        "is_open_now": None,
        "participation_deadline": "",
        "next_deadline": "",
        "status_confidence": "low",
        "status_reason": "締切を特定できませんでした。原典確認が必要です",
    }


def is_candidate(item: dict[str, Any]) -> bool:
    if int(item.get("commercial_score", 0) or 0) < 50:
        return False
    return item.get("opportunity_type") in {"受注機会", "資金・支援"} or item.get("category") in {"入札・調達", "補助金・支援"}


def cache_fresh(entry: dict[str, Any], item: dict[str, Any], now: datetime) -> bool:
    if not entry or entry.get("source_updated") != item.get("source_updated"):
        return False
    try:
        fetched = datetime.fromisoformat(str(entry.get("fetched_at", "")).replace("Z", "+00:00"))
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return (now - fetched.astimezone(timezone.utc)) < timedelta(days=7)


def rewrite_exports(items: list[dict[str, Any]], generated_at: str) -> None:
    ranked = sorted(
        [x for x in items if int(x.get("commercial_score", 0) or 0) >= 50],
        key=lambda x: (
            0 if x.get("is_open_now") is True else 1,
            -int(x.get("commercial_score", 0) or 0),
            -int(x.get("urgency", 0) or 0),
        ),
    )[:300]
    fields = [
        "application_status", "is_open_now", "participation_deadline", "next_deadline",
        "commercial_score", "urgency", "importance", "change_type", "opportunity_type",
        "category", "buyer_segments", "title", "source_name", "license_mode", "source_updated",
        "detected_at", "status_checked_at", "url",
    ]
    LEADS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with LEADS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for x in ranked:
            row = {k: x.get(k, "") for k in fields}
            row["buyer_segments"] = " / ".join(x.get("buyer_segments", []))
            writer.writerow(row)

    summary = load_json(SUMMARY, {})
    summary.update({
        "generated_at": generated_at,
        "open_now": sum(1 for x in items if x.get("is_open_now") is True),
        "open_now_commercial_70_plus": sum(1 for x in items if x.get("is_open_now") is True and int(x.get("commercial_score", 0) or 0) >= 70),
        "application_status_counts": {
            status: sum(1 for x in items if x.get("application_status") == status)
            for status in ["受付中", "参加締切済", "資格者のみ進行中", "結果掲載済", "判定不可"]
        },
    })
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    payload = load_json(LATEST, {})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return 0

    now = datetime.now(timezone.utc)
    today = datetime.now(JST).date()
    cache = load_json(CACHE, {"items": {}})
    cache_items = cache.setdefault("items", {}) if isinstance(cache, dict) else {}
    fetches = 0
    errors: list[dict[str, str]] = []

    for item in items:
        item["status_checked_at"] = now_iso()
        if not is_candidate(item):
            item.update({
                "application_status": "案件外",
                "is_open_now": None,
                "participation_deadline": "",
                "next_deadline": "",
                "status_confidence": "n/a",
                "status_reason": "応募型案件の自動判定対象外",
            })
            continue

        entry = cache_items.get(item.get("id", ""), {})
        facts: dict[str, Any] | None = None
        if cache_fresh(entry, item, now):
            facts = entry.get("facts") if isinstance(entry.get("facts"), dict) else None

        if facts is None and fetches < MAX_PAGE_FETCHES and official_detail_url(str(item.get("url", ""))):
            try:
                text = fetch_page_text(str(item["url"]))
                facts = extract_facts(text, item, today)
                fetches += 1
                cache_items[item["id"]] = {
                    "url": item.get("url", ""),
                    "source_updated": item.get("source_updated", ""),
                    "fetched_at": now_iso(),
                    "facts": facts,
                }
            except Exception as exc:
                errors.append({"title": str(item.get("title", ""))[:100], "error": f"{type(exc).__name__}: {str(exc)[:180]}"})

        if facts is None and isinstance(entry.get("facts"), dict):
            facts = entry["facts"]
        if facts is None:
            item.update({
                "application_status": "判定不可",
                "is_open_now": None,
                "participation_deadline": "",
                "next_deadline": "",
                "status_confidence": "low",
                "status_reason": "公式ページの締切確認待ち。原典確認が必要です",
            })
        else:
            item.update(classify_status(facts, today))

    payload["items"] = items
    payload["open_now_count"] = sum(1 for x in items if x.get("is_open_now") is True)
    payload["application_status_checked_at"] = now_iso()
    payload["disclaimer"] = (
        "公開情報の自動整理です。『受付中』は公式ページの締切表記から機械判定しています。"
        "判定不可・契約・商用判断は必ずリンク先の公式情報を確認してください。"
    )
    LATEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"version": 1, "updated_at": now_iso(), "items": cache_items}, ensure_ascii=False, indent=2), encoding="utf-8")
    rewrite_exports(items, payload.get("generated_at", now_iso()))

    status = load_json(STATUS, {})
    if not isinstance(status, dict):
        status = {}
    status.update({
        "application_status_checked_at": now_iso(),
        "application_status_candidates": sum(1 for x in items if is_candidate(x)),
        "application_status_open_now": sum(1 for x in items if x.get("is_open_now") is True),
        "application_status_fetches": fetches,
        "application_status_errors": errors[:20],
    })
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"open_now": status["application_status_open_now"], "page_fetches": fetches, "errors": len(errors)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
