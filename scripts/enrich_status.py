#!/usr/bin/env python3
"""Enrich YOKOHAMA CHANGE items with conservative application-window status.

Safety principle: never mark an opportunity as open unless the new-participant
application deadline is found explicitly. Ambiguous future dates are not enough.
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
USER_AGENT = "YokohamaChange/0.6 (+application-status-conservative; respectful-fetching)"
TIMEOUT = 30
MAX_PAGE_FETCHES = 40
CACHE_VERSION = 2
JST = timezone(timedelta(hours=9))

# Strong markers for a final procurement result. Avoid generic words such as
# "結果" because Yokohama pages routinely contain "参加資格確認結果通知" even
# while a procurement is still underway.
FINAL_RESULT_TERMS = [
    "特定結果掲載", "契約結果掲載", "入札結果公表", "落札結果掲載",
    "選定結果掲載", "審査結果掲載", "プロポーザル結果掲載",
    "特定結果】", "契約結果】", "入札結果】", "落札結果】",
]
CLOSED_TERMS = [
    "参加申込終了", "参加申込み終了", "参加受付終了", "応募受付終了",
    "受付終了しました", "募集を終了しました",
]

# Labels that explicitly refer to first-time participation/application.
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
    "プレゼンテーション",
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
        elif tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "br", "dt", "dd"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        elif tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "dt", "dd"}:
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


def dates_at_label(text: str, label: str, default_year: int) -> list[date]:
    """Read dates only from the label line or the immediately following value line.

    Never scan through a later field such as 質問書/提案書/ヒアリング. This keeps
    a blank "申込期限" label from borrowing a downstream date.
    """
    start = 0
    blocked = [
        "質問", "提案", "企画提案", "入札", "開札", "ヒアリング", "プレゼン",
        "指名・非指名", "関連資料", "設計図書", "参加資格確認結果",
    ]
    while True:
        idx = text.find(label, start)
        if idx < 0:
            return []
        line_end = text.find("\n", idx)
        if line_end < 0:
            line_end = len(text)

        same_line = text[idx + len(label):line_end].strip(" ：:\t")
        dates = parse_dates(same_line, default_year)
        if dates:
            return dates

        pos = line_end + 1
        while pos < len(text):
            next_end = text.find("\n", pos)
            if next_end < 0:
                next_end = len(text)
            value_line = text[pos:next_end].strip()
            if value_line:
                if any(term in value_line[:60] for term in blocked):
                    break
                dates = parse_dates(value_line, default_year)
                if dates:
                    return dates
                break
            pos = next_end + 1

        start = idx + len(label)



def dates_after_participation_anchor(text: str, term: str, default_year: int) -> list[date]:
    """Read an explicit deadline tied to a participation document without crossing
    into later question/proposal/selection fields."""
    start = 0
    blockers = [
        "質問", "提案", "企画提案", "入札開始", "開札", "ヒアリング", "プレゼン",
        "指名・非指名", "関連資料", "設計図書", "参加資格確認結果",
    ]
    while True:
        idx = text.find(term, start)
        if idx < 0:
            return []
        snippet = text[idx: idx + 320]
        cut = len(snippet)
        for blocker in blockers:
            j = snippet.find(blocker, len(term))
            if j >= 0:
                cut = min(cut, j)
        local = snippet[:cut]
        if any(cue in local for cue in ["期限", "まで", "必着", "提出期間", "締切", "締め切り"]):
            dates = parse_dates(local, default_year)
            if dates:
                return dates
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


def explicit_participation_deadline(text: str, item: dict[str, Any], today: date) -> tuple[date | None, str]:
    """Return only a deadline that is explicit enough to safely mark an item open."""
    normalized = normalize_digits(text)
    year = source_year(item, today)

    for label in ["申込期限", "申込み期限"]:
        dates = dates_at_label(normalized, label, year)
        if dates:
            return max(dates), label

    app = section(
        normalized,
        "申込について",
        ["関連資料について", "関連資料", "設計図書について", "設計図書", "参加資格確認結果", "指名・非指名通知", "その他の書類", "発注担当課"],
        max_len=7000,
    )
    if app:
        for label in ["提出期間", "申請期間", "応募期間", "募集期間", "受付期間"]:
            dates = dates_at_label(app, label, year)
            if dates:
                return max(dates), f"申込欄:{label}"

        for term in PARTICIPATION_DOC_TERMS:
            dates = dates_after_participation_anchor(app, term, year)
            if dates:
                return max(dates), f"申込欄:{term}"

    # Some compact pages do not expose a separate "申込について" heading, but do
    # place an explicit 提出期限 directly after a participation-document label.
    for term in PARTICIPATION_DOC_TERMS:
        dates = dates_after_participation_anchor(normalized, term, year)
        if dates:
            return max(dates), term

    for label in PARTICIPATION_PERIOD_LABELS:
        dates = dates_at_label(normalized, label, year)
        if dates:
            return max(dates), label

    return None, ""

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
            # Require a deadline/event cue near the term. This still allows dedicated
            # fields such as "入札開始日 2026年8月24日" and "ヒアリング実施日".
            if any(w in snippet for w in ["期限", "まで", "必着", "実施日", "開始日", "入札日", "開札", "提出"]):
                out.extend(parse_dates(snippet, year))
            pos = idx + len(term)
    return sorted(set(out))


def strong_result_hit(text: str, item: dict[str, Any]) -> bool:
    title = normalize_digits(str(item.get("title", "")))
    normalized = normalize_digits(text)
    if any(term in title for term in FINAL_RESULT_TERMS):
        return True
    # Accept strong body markers only when they are not immediately followed by
    # "今後掲載予定".
    for term in FINAL_RESULT_TERMS:
        idx = normalized.find(term)
        if idx >= 0 and "今後掲載予定" not in normalized[idx: idx + 80]:
            return True
    return False


def extract_facts(text: str, item: dict[str, Any], today: date) -> dict[str, Any]:
    normalized = normalize_digits(text)
    deadline, source = explicit_participation_deadline(normalized, item, today)
    downstream = explicit_downstream_dates(normalized, item, today)
    closed_hit = any(term in normalize_digits(str(item.get("title", ""))) or term in normalized for term in CLOSED_TERMS)
    participation_iso = deadline.isoformat() if deadline else ""
    return {
        "participation_deadline": participation_iso,
        "participation_source": source,
        "downstream_dates": [d.isoformat() for d in downstream],
        "result_hit": strong_result_hit(normalized, item),
        "closed_hit": closed_hit,
        # Backward-compatible fields retained for the existing workflow tests.
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


def classify_status(facts: dict[str, Any], today: date) -> dict[str, Any]:
    raw_deadline = str(facts.get("participation_deadline", "") or "")
    if not raw_deadline:
        # Compatibility with the first-generation tests/cache schema.
        legacy_dates = to_dates(facts.get("participation_dates", []))
        if legacy_dates:
            raw_deadline = max(legacy_dates).isoformat()
    try:
        participation_deadline = date.fromisoformat(raw_deadline)
    except ValueError:
        participation_deadline = None
    downstream = to_dates(facts.get("downstream_dates", []))
    result_hit = bool(facts.get("result_hit"))
    closed_hit = bool(facts.get("closed_hit"))
    source = str(facts.get("participation_source", ""))
    downstream_future = [d for d in downstream if d >= today]
    next_downstream = min(downstream_future) if downstream_future else None

    if participation_deadline:
        if participation_deadline >= today and not closed_hit:
            return {
                "application_status": "受付中",
                "is_open_now": True,
                "participation_deadline": participation_deadline.isoformat(),
                "next_deadline": participation_deadline.isoformat(),
                "status_confidence": "high",
                "status_reason": f"明示された新規参加期限（{source}）を{participation_deadline.isoformat()}と判定",
            }
        if result_hit:
            return {
                "application_status": "結果掲載済",
                "is_open_now": False,
                "participation_deadline": participation_deadline.isoformat(),
                "next_deadline": "",
                "status_confidence": "high",
                "status_reason": "新規参加期限を経過し、最終結果掲載を検出",
            }
        if next_downstream:
            return {
                "application_status": "資格者のみ進行中",
                "is_open_now": False,
                "participation_deadline": participation_deadline.isoformat(),
                "next_deadline": next_downstream.isoformat(),
                "status_confidence": "high",
                "status_reason": "新規参加期限は終了。質問・提案・入札・ヒアリング等の後続日程あり",
            }
        return {
            "application_status": "参加締切済",
            "is_open_now": False,
            "participation_deadline": participation_deadline.isoformat(),
            "next_deadline": "",
            "status_confidence": "high",
            "status_reason": "明示された新規参加期限を経過",
        }

    # Conservative fallback: a future generic/proposal/hearing date alone can never
    # make an item "受付中". This is intentional to avoid false commercial leads.
    if result_hit:
        return {
            "application_status": "結果掲載済",
            "is_open_now": False,
            "participation_deadline": "",
            "next_deadline": "",
            "status_confidence": "medium",
            "status_reason": "最終結果掲載を検出。新規参加期限は特定できず",
        }
    if closed_hit:
        return {
            "application_status": "参加締切済",
            "is_open_now": False,
            "participation_deadline": "",
            "next_deadline": next_downstream.isoformat() if next_downstream else "",
            "status_confidence": "medium",
            "status_reason": "受付終了表記を検出",
        }
    return {
        "application_status": "判定不可",
        "is_open_now": None,
        "participation_deadline": "",
        "next_deadline": next_downstream.isoformat() if next_downstream else "",
        "status_confidence": "low",
        "status_reason": "新規参加期限を明示的に特定できないため、安全側で受付中にしません",
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
    raw_cache = load_json(CACHE, {"version": CACHE_VERSION, "items": {}})
    if not isinstance(raw_cache, dict) or raw_cache.get("version") != CACHE_VERSION:
        cache = {"version": CACHE_VERSION, "items": {}}
    else:
        cache = raw_cache
    cache_items = cache.setdefault("items", {})
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

        if facts is None and isinstance(entry.get("facts"), dict) and raw_cache.get("version") == CACHE_VERSION:
            facts = entry["facts"]
        if facts is None:
            item.update({
                "application_status": "判定不可",
                "is_open_now": None,
                "participation_deadline": "",
                "next_deadline": "",
                "status_confidence": "low",
                "status_reason": "公式ページの新規参加期限を確認できませんでした。原典確認が必要です",
            })
        else:
            item.update(classify_status(facts, today))

    payload["items"] = items
    payload["open_now_count"] = sum(1 for x in items if x.get("is_open_now") is True)
    payload["application_status_checked_at"] = now_iso()
    payload["disclaimer"] = (
        "公開情報の自動整理です。『受付中』は公式ページで新規参加期限を明示的に特定できた案件だけです。"
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
        "application_status_version": CACHE_VERSION,
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
