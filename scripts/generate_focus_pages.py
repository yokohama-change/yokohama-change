#!/usr/bin/env python3
"""Generate focused SEO/utility landing pages from verified open opportunities.

Only current verified-open items from open_now.json are eligible. Empty focus pages are
removed rather than published, avoiding thin pages and stale claims.
"""
from __future__ import annotations

import html
import json
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OPEN_JSON = DOCS / "data" / "open_now.json"
OPPORTUNITIES = DOCS / "opportunities"
INDEX = OPPORTUNITIES / "index.html"
SITEMAP = DOCS / "sitemap.xml"
BASE = "https://yokohama-change.github.io/yokohama-change/"


def int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def score(item: dict[str, Any]) -> int:
    return int_value(item.get("commercial_score"), 0)


def days_left(item: dict[str, Any]) -> int:
    return int_value(item.get("days_left"), 9999)


FOCUS = {
    "high-value": {
        "title": "神奈川県内の高商用案件（商用70+）",
        "description": "神奈川県内で現在受付中と確認できた案件のうち、YOKOHAMA CHANGE商用スコア70以上の案件",
        "nav": "高商用70+",
        "filter": lambda x: score(x) >= 70,
    },
    "deadline-soon": {
        "title": "神奈川県内の締切7日以内案件",
        "description": "神奈川県内で現在受付中と確認でき、参加・申請締切まで7日以内の案件",
        "nav": "締切7日以内",
        "filter": lambda x: 0 <= days_left(x) <= 7,
    },
}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def verified_open(item: dict[str, Any]) -> bool:
    if str(item.get("application_status") or "") != "受付中":
        return False
    if str(item.get("status_confidence") or "") != "high":
        return False
    if not str(item.get("participation_deadline") or "").strip():
        return False
    return days_left(item) >= 0 and days_left(item) < 9999


def prep_copy(item: dict[str, Any]) -> str:
    start = str(item.get("preparation_start_date") or "").strip()
    status = str(item.get("preparation_status") or "").strip()
    days = item.get("preparation_days")
    if not start or not status or days in (None, ""):
        return ""
    if status == "準備開始推奨":
        text = f"独自目安 · 準備開始推奨 · 標準{esc(days)}日前 · {esc(start)}"
    else:
        text = f"独自目安 · 準備開始 {esc(start)}ごろ · 標準{esc(days)}日前"
    return f'<div class="opportunity-list-prep">{text}</div>'


def render_page(slug: str, items: list[dict[str, Any]], generated_at: str) -> str:
    cfg = FOCUS[slug]
    title = str(cfg["title"])
    description = f"{cfg['description']}を{len(items)}件掲載。公式期限、地域、商用スコア、準備開始目安を確認できます。"
    canonical = f"{BASE}opportunities/{slug}/"
    high = sum(1 for x in items if score(x) >= 70)

    cards = []
    for item in sorted(items, key=lambda x: (days_left(x), -score(x))):
        exact = "時刻確認済" if item.get("deadline_time_exact") is True else "締切日確認済・時刻未確認"
        cards.append(f'''<article class="opportunity-list-card">
  <div class="opportunity-list-top"><span>受付中</span><b>商用 {esc(score(item))}</b></div>
  <a href="../{esc(item.get('id'))}.html">{esc(item.get('title'))}</a>
  {prep_copy(item)}
  <p>{esc(item.get('region'))} · {esc(item.get('source_name'))} · {esc(item.get('opportunity_type'))}</p>
  <small>締切 {esc(item.get('deadline_label') or item.get('participation_deadline'))} · {esc(exact)}</small>
</article>''')

    structured = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "url": canonical,
        "description": description,
        "dateModified": generated_at,
        "inLanguage": "ja-JP",
        "isPartOf": {"@type": "WebSite", "name": "YOKOHAMA CHANGE", "url": BASE},
    }, ensure_ascii=False).replace("</", "<\\/")

    return f'''<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="{esc(description)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{esc(canonical)}">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="ja_JP">
  <meta property="og:site_name" content="YOKOHAMA CHANGE">
  <meta property="og:title" content="{esc(title)} | YOKOHAMA CHANGE">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{esc(canonical)}">
  <title>{esc(title)} | YOKOHAMA CHANGE</title>
  <link rel="stylesheet" href="../../styles.css">
  <link rel="stylesheet" href="../../opportunity.css">
  <script type="application/ld+json">{structured}</script>
</head>
<body>
  <main class="opportunity-page">
    <nav class="opportunity-nav"><a href="../../">← YOKOHAMA CHANGE</a><a href="../">神奈川の受付中案件一覧</a></nav>
    <header class="opportunity-list-header">
      <span>FOCUS · VERIFIED OPEN ONLY</span>
      <h1>{esc(title)}</h1>
      <p>公式ページの参加・申請期限を確認し、現在受付中・信頼度highと判定した案件だけを掲載します。商用スコアと準備開始表示はYOKOHAMA CHANGE独自の参考指標です。</p>
      <small>対象 {len(items)}件 · 商用70+ {high}件 · 生成 {esc(generated_at)}</small>
    </header>
    <section class="opportunity-list">{''.join(cards)}</section>
    <div class="opportunity-warning"><strong>重要：</strong>掲載情報・商用スコア・準備開始目安は参考情報です。応募・申請・契約等の最終判断は必ず公式情報を確認し、利用者ご自身の責任で行ってください。本サービスの利用等により生じた損害等について、運営者は法令上認められる範囲で責任を負いません。 <a href="../../disclaimer.html">免責事項</a></div>
  </main>
</body>
</html>
'''


def update_index(counts: list[tuple[str, int]]) -> None:
    try:
        source = INDEX.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    marker = '<section class="opportunity-list">'
    if marker not in source:
        return
    links = ''.join(
        f'<a href="{esc(slug)}/">{esc(FOCUS[slug]["nav"])} <b>{count}</b></a>'
        for slug, count in counts
    )
    nav = f'<nav class="opportunity-region-nav opportunity-focus-nav" aria-label="注目案件">{links}</nav>\n    '
    source = source.replace(marker, nav + marker, 1)
    INDEX.write_text(source, encoding="utf-8")


def update_sitemap(counts: list[tuple[str, int]]) -> None:
    try:
        tree = ET.parse(SITEMAP)
        root = tree.getroot()
    except (FileNotFoundError, ET.ParseError):
        return
    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("", ns)
    wanted = {f"{BASE}opportunities/{slug}/" for slug, _ in counts}
    focus_urls = {f"{BASE}opportunities/{slug}/" for slug in FOCUS}
    for node in list(root.findall(f"{{{ns}}}url")):
        loc = node.find(f"{{{ns}}}loc")
        if loc is not None and loc.text in focus_urls:
            root.remove(node)
    today = datetime.now(timezone.utc).date().isoformat()
    for loc in sorted(wanted):
        node = ET.SubElement(root, f"{{{ns}}}url")
        ET.SubElement(node, f"{{{ns}}}loc").text = loc
        ET.SubElement(node, f"{{{ns}}}lastmod").text = today
        ET.SubElement(node, f"{{{ns}}}changefreq").text = "daily"
        ET.SubElement(node, f"{{{ns}}}priority").text = "0.9"
    tree.write(SITEMAP, encoding="utf-8", xml_declaration=True)


def main() -> int:
    payload = load_json(OPEN_JSON, {})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    generated_at = str(payload.get("generated_at") or datetime.now(timezone.utc).isoformat())
    eligible = [x for x in items if isinstance(x, dict) and verified_open(x)]

    counts: list[tuple[str, int]] = []
    for slug, cfg in FOCUS.items():
        target = OPPORTUNITIES / slug
        if target.exists():
            shutil.rmtree(target)
        selected = [x for x in eligible if cfg["filter"](x)]
        if not selected:
            continue
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(render_page(slug, selected, generated_at), encoding="utf-8")
        counts.append((slug, len(selected)))

    update_index(counts)
    update_sitemap(counts)
    print(json.dumps({"focus_pages": [{"slug": slug, "open": count} for slug, count in counts]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
