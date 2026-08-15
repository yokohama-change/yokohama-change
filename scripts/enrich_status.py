#!/usr/bin/env python3
"""Enrich YOKOHAMA CHANGE items with conservative, deadline-aware status.

Principles:
- Never mark an opportunity open unless a first-time participation/application deadline is explicit.
- Use JST and, when available, the exact deadline time.
- Separate current opportunities from recruitment notices and historical/result pages.
- Publish lightweight open-only feeds for downstream alerting without republishing page bodies.
"""
from __future__ import annotations

import csv
import html
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "docs" / "data" / "latest.json"
STATUS = ROOT / "docs" / "data" / "status.json"
LEADS_CSV = ROOT / "docs" / "data" / "leads.csv"
SUMMARY = ROOT / "docs" / "data" / "summary.json"
OPEN_JSON = ROOT / "docs" / "data" / "open_now.json"
OPEN_CSV = ROOT / "docs" / "data" / "open_now.csv"
OPEN_RSS = ROOT / "docs" / "data" / "open_now.rss"
CACHE = ROOT / "data" / "application_status_cache.json"

USER_AGENT = "YokohamaChange/0.7 (+deadline-status; respectful-fetching)"
TIMEOUT = 30
MAX_PAGE_FETCHES = 40
CACHE_VERSION = 3
STATUS_ENGINE_VERSION = 3
JST = timezone(timedelta(hours=9))

FINAL_RESULT_TERMS = [
    "特定結果掲載", "契約結果掲載", "入札結果公表", "落札結果掲載",
    "選定結果掲載", "審査結果掲載", "プロポーザル結果掲載",
    "特定結果】", "契約結果】", "入札結果】", "落札結果】",
]
CLOSED_TERMS = [
    "参加申込終了", "参加申込み終了", "参加受付終了", "応募受付終了",
    "受付終了しました", "募集を終了しました", "申込受付を終了",
]
EMPLOYMENT_TERMS = [
    "会計年度任用職員", "職員採用", "職員募集", "採用選考", "採用試験",
    "任用職員", "非常勤職員", "臨時職員",
]
PARTICIPATION_DOC_TERMS = [
    "参加意向申出書", "参加意向申出", "入札参加意向申出書",
    "公募型指名競争入札参加意向申出書", "参加申込", "参加申し込み",
    "参加表明", "参加資格確認申請", "入札参加申込", "応募申込",
]
PARTICIPATION_PERIOD_LABELS = [
    "申込期限", "申込み期限", "応募期限", "申請期限", "受付期限",
    "申請期間", "応募期間", "募集期間", "受付期間", "公募期間",
]
DOWNSTREAM_TERMS = [
    "質問書", "質問受付", "質問期限", "提案書", "提案期限", "企画提案書",
    "入札開始日", "入札日", "開札予定日", "ヒアリング実施日", "ヒアリング",
    "プレゼンテーション", "指名・非指名通知日",
]

DATE_RE = re.compile(
    r"(?:(?:令和\s*(?P<era_year>\d{1,2})年)|(?P<year>20\d{2})年)?\s*"
    r"(?P<month>\d{1,2})月\s*(?P<day>\d{1,2})日"
)
COLON_TIME_RE = re.compile(r"(?<!\d)(?P<h>\d{1,2})\s*[:：]\s*(?P<m>\d{2})(?!\d)")
JP_TIME_RE = re.compile(r"(?:(?P<ampm>午前|午後)\s*)?(?P<h>\d{1,2})\s*時(?:\s*(?P<m>\d{1,2})\s*分)?")


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
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        elif tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "br", "dt", "dd", "th", "td"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        elif tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "dt", "dd", "th", "td"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        value = html.unescape(" ".join(self.parts))
        value = normalize_digits(value)
        value = re.sub(r"[\t\r ]+", " ", value)
        value = re.sub(r" *\n *", "\n", value)
        value = re.sub(r"\n{2,}", "\n", value)
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


def parse_time_value(snippet: str) -> time | None:
    text_value = normalize_digits(snippet)
    if "正午" in text_value:
        return time(12, 0)
    m = COLON_TIME_RE.search(text_value)
    if m:
        try:
            return time(int(m.group("h")), int(m.group("m")))
        except ValueError:
            pass
    m = JP_TIME_RE.search(text_value)
    if not m:
        return None
    try:
        hour = int(m.group("h"))
        minute = int(m.group("m") or 0)
        if m.group("ampm") == "午後" and hour < 12:
            hour += 12
        elif m.group("ampm") == "午前" and hour == 12:
            hour = 0
        return time(hour, minute)
    except ValueError:
        return None


def deadline_at(d: date, t: time | None) -> datetime:
    return datetime.combine(d, t or time(23, 59, 59), JST)


def _line_after_label(text: str, label: str, start: int) -> tuple[str, int] | None:
    idx = text.find(label, start)
    if idx < 0:
        return None
    line_end = text.find("\n", idx)
    if line_end < 0:
        line_end = len(text)
    same_line = text[idx + len(label):line_end].strip(" ：:\t")
    if same_line:
        return same_line, idx + len(label)
    pos = line_end + 1
    while pos < len(text):
        next_end = text.find("\n", pos)
        if next_end < 0:
            next_end = len(text)
        value_line = text[pos:next_end].strip()
        if value_line:
            return value_line, idx + len(label)
        pos = next_end + 1
    return "", idx + len(label)


def deadline_at_label(text: str, label: str, default_year: int) -> tuple[date, time | None, str] | None:
    start = 0
    blocked = [
        "質問", "提案", "企画提案", "入札", "開札", "ヒアリング", "プレゼン",
        "指名・非指名", "関連資料", "設計図書", "参加資格確認結果",
    ]
    while True:
        found = _line_after_label(text, label, start)
        if found is None:
            return None
        value, next_start = found
        if any(term in value[:60] for term in blocked):
            start = next_start
            continue
        dates = parse_dates(value, default_year)
        if dates:
            d = max(dates)
            return d, parse_time_value(value), value
        start = next_start


def deadline_after_participation_anchor(text: str, term: str, default_year: int) -> tuple[date, time | None, str] | None:
    start = 0
    blockers = [
        "質問", "提案", "企画提案", "入札開始", "開札", "ヒアリング", "プレゼン",
        "指名・非指名", "関連資料", "設計図書", "参加資格確認結果",
    ]
    while True:
        idx = text.find(term, start)
        if idx < 0:
            return None
        snippet = text[idx: idx + 420]
        cut = len(snippet)
        for blocker in blockers:
            j = snippet.find(blocker, len(term))
            if j >= 0:
                cut = min(cut, j)
        local = snippet[:cut]
        if any(cue in local for cue in ["期限", "まで", "必着", "提出期間", "締切", "締め切り"]):
            dates = parse_dates(local, default_year)
            if dates:
                d = max(dates)
                return d, parse_time_value(local), local
        start = idx + len(term)


def section(text: str, start_term: str, end_terms: list[str], max_len: int = 5000) -> str:
    idx = text.find(start_term)
    if idx < 0:
        return ""
    end = min(len(text), idx + max_len)
    for term in end_terms:
        j = text.find(term, idx + len(start_term))
        if j >= 0:
            end = min(end, j)
    return text[idx:end]


def explicit_participation_deadline(text: str, item: dict[str, Any], today: date) -> tuple[date | None, time | None, str]:
    normalized = normalize_digits(text)
    year = source_year(item, today)

    direct_hit = None
    direct_label = ""
    for label in ["申込期限", "申込み期限"]:
        hit = deadline_at_label(normalized, label, year)
        if hit:
            direct_hit = hit
            direct_label = label
            break

    app = section(
        normalized,
        "申込について",
        ["関連資料について", "関連資料", "設計図書について", "設計図書", "参加資格確認結果", "指名・非指名通知", "その他の書類", "発注担当課"],
        max_len=7000,
    )
    if direct_hit:
        if direct_hit[1] is None and app:
            for label in ["提出期間", "申請期間", "応募期間", "募集期間", "受付期間"]:
                app_hit = deadline_at_label(app, label, year)
                if app_hit and app_hit[0] == direct_hit[0] and app_hit[1] is not None:
                    return direct_hit[0], app_hit[1], f"{direct_label}+申込欄:{label}"
        return direct_hit[0], direct_hit[1], direct_label

    if app:
        for label in ["提出期間", "申請期間", "応募期間", "募集期間", "受付期間"]:
            hit = deadline_at_label(app, label, year)
            if hit:
                return hit[0], hit[1], f"申込欄:{label}"
        for term in PARTICIPATION_DOC_TERMS:
            hit = deadline_after_participation_anchor(app, term, year)
            if hit:
                return hit[0], hit[1], f"申込欄:{term}"

    for term in PARTICIPATION_DOC_TERMS:
        hit = deadline_after_participation_anchor(normalized, term, year)
        if hit:
            return hit[0], hit[1], term

    for label in PARTICIPATION_PERIOD_LABELS:
        hit = deadline_at_label(normalized, label, year)
        if hit:
            return hit[0], hit[1], label

    return None, None, ""


def explicit_downstream_dates(text: str, item: dict[str, Any], today: date) -> list[date]:
    normalized = normalize_digits(text)
    year = source_year(item, today)
    out: list[date] = []
    for term in DOWNSTREAM_TERMS:
        pos = 0
        while True:
            idx = normalized.find(term, pos)
            if idx < 0:
                break
            snippet = normalized[idx: idx + 220]
            if any(w in snippet for w in ["期限", "まで", "必着", "実施日", "開始日", "入札日", "開札", "提出", "通知日"]):
                out.extend(parse_dates(snippet, year))
            pos = idx + len(term)
    return sorted(set(out))


def strong_result_hit(text: str, item: dict[str, Any]) -> bool:
    title = normalize_digits(str(item.get("title", "")))
    normalized = normalize_digits(text)
    if any(term in title for term in FINAL_RESULT_TERMS):
        return True
    for term in FINAL_RESULT_TERMS:
        idx = normalized.find(term)
        if idx >= 0 and "今後掲載予定" not in normalized[idx: idx + 80]:
            return True
    return False


def extract_facts(text: str, item: dict[str, Any], today: date) -> dict[str, Any]:
    normalized = normalize_digits(text)
    d, t, source = explicit_participation_deadline(normalized, item, today)
    downstream = explicit_downstream_dates(normalized, item, today)
    closed_hit = any(term in normalize_digits(str(item.get("title", ""))) or term in normalized for term in CLOSED_TERMS)
    participation_iso = d.isoformat() if d else ""
    deadline_iso = deadline_at(d, t).isoformat(timespec="minutes") if d else ""
    return {
        "participation_deadline": participation_iso,
        "participation_deadline_at": deadline_iso,
        "participation_source": source,
        "downstream_dates": [x.isoformat() for x in downstream],
        "result_hit": strong_result_hit(normalized, item),
        "closed_hit": closed_hit,
        "participation_dates": [participation_iso] if participation_iso else [],
        "generic_dates": [],
    }


def to_dates(values: list[str]) -> list[date]:
    out: list[date] = []
    for value in values:
        try:
            out.append(date.fromisoformat(value))
        except (TypeError, ValueError):
            pass
    return sorted(set(out))


def _parse_deadline_at(value: str, fallback_date: date | None) -> datetime | None:
    if value:
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            return dt.astimezone(JST)
        except ValueError:
            pass
    if fallback_date:
        return deadline_at(fallback_date, None)
    return None


def classify_status(facts: dict[str, Any], today: date, now_jst: datetime | None = None) -> dict[str, Any]:
    raw_deadline = str(facts.get("participation_deadline", "") or "")
    if not raw_deadline:
        legacy_dates = to_dates(facts.get("participation_dates", []))
        if legacy_dates:
            raw_deadline = max(legacy_dates).isoformat()
    try:
        participation_deadline = date.fromisoformat(raw_deadline) if raw_deadline else None
    except ValueError:
        participation_deadline = None

    downstream = to_dates(facts.get("downstream_dates", []))
    result_hit = bool(facts.get("result_hit"))
    closed_hit = bool(facts.get("closed_hit"))
    source = str(facts.get("participation_source", ""))
    downstream_future = [d for d in downstream if d >= today]
    next_downstream = min(downstream_future) if downstream_future else None
    cutoff = _parse_deadline_at(str(facts.get("participation_deadline_at", "") or ""), participation_deadline)
    now_local = now_jst.astimezone(JST) if now_jst else None

    is_before_cutoff = False
    if participation_deadline:
        is_before_cutoff = participation_deadline >= today
        if now_local and cutoff:
            is_before_cutoff = now_local <= cutoff

    common = {
        "participation_deadline": participation_deadline.isoformat() if participation_deadline else "",
        "participation_deadline_at": cutoff.isoformat(timespec="minutes") if cutoff else "",
    }

    if participation_deadline:
        if is_before_cutoff and not closed_hit:
            return {**common, "application_status": "受付中", "is_open_now": True,
                    "next_deadline": participation_deadline.isoformat(), "status_confidence": "high",
                    "status_reason": f"明示された新規参加期限（{source}）を確認"}
        if result_hit:
            return {**common, "application_status": "結果掲載済", "is_open_now": False, "next_deadline": "",
                    "status_confidence": "high", "status_reason": "新規参加期限を経過し、最終結果掲載を検出"}
        if next_downstream:
            return {**common, "application_status": "資格者のみ進行中", "is_open_now": False,
                    "next_deadline": next_downstream.isoformat(), "status_confidence": "high",
                    "status_reason": "新規参加期限は終了。質問・提案・入札・ヒアリング等の後続日程あり"}
        return {**common, "application_status": "参加締切済", "is_open_now": False, "next_deadline": "",
                "status_confidence": "high", "status_reason": "明示された新規参加期限を経過"}

    if result_hit:
        return {**common, "application_status": "結果掲載済", "is_open_now": False, "next_deadline": "",
                "status_confidence": "medium", "status_reason": "最終結果掲載を検出。新規参加期限は特定できず"}
    if closed_hit:
        return {**common, "application_status": "参加締切済", "is_open_now": False,
                "next_deadline": next_downstream.isoformat() if next_downstream else "", "status_confidence": "medium",
                "status_reason": "受付終了表記を検出"}
    return {**common, "application_status": "判定不可", "is_open_now": None,
            "next_deadline": next_downstream.isoformat() if next_downstream else "", "status_confidence": "low",
            "status_reason": "新規参加期限を明示的に特定できないため、安全側で受付中にしません"}


def is_employment_notice(item: dict[str, Any]) -> bool:
    title = normalize_digits(str(item.get("title", "")))
    if any(term in title for term in EMPLOYMENT_TERMS):
        return True
    return "採用" in title and any(term in title for term in ["職員", "任用", "求人"])


def is_candidate(item: dict[str, Any]) -> bool:
    if is_employment_notice(item):
        return False
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


def enrich_open_metadata(item: dict[str, Any], today: date) -> None:
    item["days_left"] = None
    item["deadline_label"] = ""
    item["priority_tier"] = ""
    if item.get("is_open_now") is not True:
        return
    try:
        d = date.fromisoformat(str(item.get("participation_deadline", "")))
        days = (d - today).days
        item["days_left"] = days
        item["deadline_label"] = "本日締切" if days == 0 else "明日締切" if days == 1 else f"残り{days}日"
    except ValueError:
        days = 999
    score = int(item.get("commercial_score", 0) or 0)
    if score >= 85 and days <= 7:
        item["priority_tier"] = "最優先"
    elif score >= 70:
        item["priority_tier"] = "高優先"
    else:
        item["priority_tier"] = "受付中"


def open_rank_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    days = item.get("days_left")
    days_num = int(days) if isinstance(days, int) else 9999
    return (-int(item.get("commercial_score", 0) or 0), days_num,
            -int(item.get("urgency", 0) or 0), str(item.get("title", "")))


def write_open_feeds(items: list[dict[str, Any]], generated_at: str) -> None:
    open_items = sorted([x for x in items if x.get("is_open_now") is True], key=open_rank_key)
    public_fields = [
        "id", "title", "url", "source_name", "category", "opportunity_type", "buyer_segments",
        "commercial_score", "urgency", "importance", "application_status", "participation_deadline",
        "participation_deadline_at", "days_left", "deadline_label", "priority_tier", "status_confidence",
        "status_reason", "detected_at", "source_updated",
    ]
    compact = [{k: item.get(k, "") for k in public_fields} for item in open_items]
    OPEN_JSON.parent.mkdir(parents=True, exist_ok=True)
    OPEN_JSON.write_text(json.dumps({
        "generated_at": generated_at,
        "count": len(compact),
        "high_value_count": sum(1 for x in compact if int(x.get("commercial_score", 0) or 0) >= 70),
        "items": compact,
        "note": "公式ページで新規参加期限を明示的に確認でき、現時点で受付中と判定した案件のみ。応募前に原典確認が必要です。",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_fields = ["priority_tier", "deadline_label", "participation_deadline", "days_left", "commercial_score",
                  "urgency", "opportunity_type", "category", "buyer_segments", "title", "source_name", "url"]
    with OPEN_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for item in open_items:
            row = {k: item.get(k, "") for k in csv_fields}
            row["buyer_segments"] = " / ".join(item.get("buyer_segments", []))
            writer.writerow(row)

    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "YOKOHAMA CHANGE | 今、応募できる案件"
    ET.SubElement(channel, "link").text = "https://yokohama-change.github.io/yokohama-change/"
    ET.SubElement(channel, "description").text = "横浜市公式情報から新規参加期限を確認できた受付中案件"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(datetime.now(timezone.utc))
    for item in open_items[:50]:
        node = ET.SubElement(channel, "item")
        prefix = f"[{item.get('deadline_label') or item.get('participation_deadline')}]"
        ET.SubElement(node, "title").text = f"{prefix} {item.get('title', '')}"
        ET.SubElement(node, "link").text = str(item.get("url", ""))
        ET.SubElement(node, "guid", {"isPermaLink": "false"}).text = str(item.get("id", item.get("url", "")))
        ET.SubElement(node, "description").text = (
            f"優先度: {item.get('priority_tier','')} / 商用スコア: {item.get('commercial_score',0)} / "
            f"参加期限: {item.get('participation_deadline','')}。応募前に公式ページをご確認ください。"
        )
    OPEN_RSS.write_bytes(ET.tostring(rss, encoding="utf-8", xml_declaration=True))


def rewrite_exports(items: list[dict[str, Any]], generated_at: str) -> None:
    ranked = sorted([x for x in items if int(x.get("commercial_score", 0) or 0) >= 50],
                    key=lambda x: (0 if x.get("is_open_now") is True else 1, *open_rank_key(x)))[:300]
    fields = [
        "application_status", "is_open_now", "priority_tier", "deadline_label", "days_left",
        "participation_deadline", "participation_deadline_at", "next_deadline", "commercial_score",
        "urgency", "importance", "change_type", "opportunity_type", "category", "buyer_segments",
        "title", "source_name", "license_mode", "source_updated", "detected_at", "status_checked_at", "url",
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
        "status_engine_version": STATUS_ENGINE_VERSION,
        "open_now": sum(1 for x in items if x.get("is_open_now") is True),
        "open_now_commercial_70_plus": sum(1 for x in items if x.get("is_open_now") is True and int(x.get("commercial_score", 0) or 0) >= 70),
        "application_status_counts": {status: sum(1 for x in items if x.get("application_status") == status)
                                      for status in ["受付中", "参加締切済", "資格者のみ進行中", "結果掲載済", "判定不可", "案件外"]},
    })
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_open_feeds(items, generated_at)


def main() -> int:
    payload = load_json(LATEST, {})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return 0

    now_utc = datetime.now(timezone.utc)
    now_jst = datetime.now(JST)
    today = now_jst.date()
    raw_cache = load_json(CACHE, {"version": CACHE_VERSION, "items": {}})
    cache = raw_cache if isinstance(raw_cache, dict) and raw_cache.get("version") == CACHE_VERSION else {"version": CACHE_VERSION, "items": {}}
    cache_items = cache.setdefault("items", {})
    fetches = 0
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    for item in items:
        item["status_checked_at"] = now_iso()
        item["status_source_state"] = "not_applicable"
        if not is_candidate(item):
            item.update({
                "application_status": "案件外", "is_open_now": None, "participation_deadline": "",
                "participation_deadline_at": "", "next_deadline": "", "status_confidence": "n/a",
                "status_reason": "応募型案件の自動判定対象外" if not is_employment_notice(item) else "採用・求人情報のため公共案件判定対象外",
            })
            enrich_open_metadata(item, today)
            continue

        entry = cache_items.get(item.get("id", ""), {})
        facts: dict[str, Any] | None = None
        if cache_fresh(entry, item, now_utc):
            facts = entry.get("facts") if isinstance(entry.get("facts"), dict) else None
            if facts is not None:
                item["status_source_state"] = "cache"

        if facts is None and fetches < MAX_PAGE_FETCHES and official_detail_url(str(item.get("url", ""))):
            fetches += 1
            try:
                text = fetch_page_text(str(item["url"]))
                facts = extract_facts(text, item, today)
                item["status_source_state"] = "fetched"
                cache_items[item["id"]] = {"url": item.get("url", ""), "source_updated": item.get("source_updated", ""),
                                           "fetched_at": now_iso(), "facts": facts}
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    item["status_source_state"] = "source_404"
                    warnings.append({"title": str(item.get("title", ""))[:100], "warning": "公式ページ404。受付中にはしません"})
                else:
                    errors.append({"title": str(item.get("title", ""))[:100], "error": f"HTTP {exc.code}"})
            except Exception as exc:
                errors.append({"title": str(item.get("title", ""))[:100], "error": f"{type(exc).__name__}: {str(exc)[:180]}"})

        if facts is None and isinstance(entry.get("facts"), dict) and raw_cache.get("version") == CACHE_VERSION:
            facts = entry["facts"]
            item["status_source_state"] = "stale_cache"
        if facts is None:
            item.update({"application_status": "判定不可", "is_open_now": None, "participation_deadline": "",
                         "participation_deadline_at": "", "next_deadline": "", "status_confidence": "low",
                         "status_reason": "公式ページの新規参加期限を確認できませんでした。原典確認が必要です"})
        else:
            item.update(classify_status(facts, today, now_jst=now_jst))
        enrich_open_metadata(item, today)

    payload["items"] = items
    payload["open_now_count"] = sum(1 for x in items if x.get("is_open_now") is True)
    payload["open_now_high_value_count"] = sum(1 for x in items if x.get("is_open_now") is True and int(x.get("commercial_score", 0) or 0) >= 70)
    payload["application_status_checked_at"] = now_iso()
    payload["status_engine_version"] = STATUS_ENGINE_VERSION
    payload["disclaimer"] = (
        "公開情報の自動整理です。『受付中』は公式ページで新規参加期限を明示的に特定し、締切時刻も可能な範囲で確認した案件だけです。"
        "判定不可・契約・商用判断は必ずリンク先の公式情報を確認してください。"
    )
    LATEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"version": CACHE_VERSION, "updated_at": now_iso(), "items": cache_items}, ensure_ascii=False, indent=2), encoding="utf-8")
    rewrite_exports(items, payload.get("generated_at", now_iso()))

    status = load_json(STATUS, {})
    if not isinstance(status, dict):
        status = {}
    status.update({
        "application_status_version": STATUS_ENGINE_VERSION,
        "application_status_checked_at": now_iso(),
        "application_status_candidates": sum(1 for x in items if is_candidate(x)),
        "application_status_open_now": sum(1 for x in items if x.get("is_open_now") is True),
        "application_status_fetches": fetches,
        "application_status_errors": errors[:20],
        "application_status_warnings": warnings[:20],
        "employment_notices_excluded": sum(1 for x in items if is_employment_notice(x)),
    })
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"open_now": status["application_status_open_now"], "page_fetches": fetches,
                      "errors": len(errors), "warnings": len(warnings),
                      "employment_excluded": status["employment_notices_excluded"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
