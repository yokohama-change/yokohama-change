#!/usr/bin/env python3
"""Generate crawlable region landing pages from verified open opportunities only.

Empty regions are not indexed. This avoids thin SEO pages and keeps growth aligned with
product quality: a region page exists only when YOKOHAMA CHANGE has at least one
`is_open_now` opportunity already admitted to open_now.json.
"""
from __future__ import annotations

import html
import json
import shutil
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OPEN_JSON = DOCS / "data" / "open_now.json"
OPPORTUNITIES = DOCS / "opportunities"
REGIONS_DIR = OPPORTUNITIES / "regions"
INDEX = OPPORTUNITIES / "index.html"
SITEMAP = DOCS / "sitemap.xml"
BASE = "https://yokohama-change.github.io/yokohama-change/"

SLUGS = {
    "神奈川県": "kanagawa-pref",
    "横浜市": "yokohama",
    "川崎市": "kawasaki",
    "相模原市": "sagamihara",
}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def render_region(region: str, items: list[dict[str, Any]], generated_at: str) -> str:
    count = len(items)
    high = sum(1 for x in items if int(x.get("commercial_score", 0) or 0) >= 70)
    slug = SLUGS.get(region, region)
    canonical = f"{BASE}opportunities/regions/{slug}/"
    cards = []
    for item in sorted(items, key=lambda x: (-int(x.get("commercial_score", 0) or 0), int(x.get("days_left", 9999) or 9999))):
        exact = "時刻確認済" if item.get("deadline_time_exact") is True else "締切日確認済・時刻未確認"
        cards.append(f'''<article class="opportunity-list-card">
  <div class="opportunity-list-top"><span>受付中</span><b>商用 {esc(item.get("commercial_score", 0))}</b></div>
  <a href="../../{esc(item.get('id'))}.html">{esc(item.get('title'))}</a>
  <p>{esc(item.get('source_name'))} · {esc(item.get('opportunity_type'))}</p>
  <small>締切 {esc(item.get('deadline_label') or item.get('participation_deadline'))} · {esc(exact)}</small>
</article>''')

    description = f"{region}の公式情報から、現在受付中と確認できた入札・調達・公募・補助金を{count}件掲載。締切・商用スコア付き。"
    title = f"{region}の現在受付中 入札・公募・補助金 {count}件 | YOKOHAMA CHANGE"
    structured = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "url": canonical,
        "description": description,
        "dateModified": generated_at,
        "inLanguage": "ja-JP",
        "isPartOf": {"@type":"WebSite","name":"YOKOHAMA CHANGE","url":BASE},
    }, ensure_ascii=False)
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
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{esc(canonical)}">
  <title>{esc(title)}</title>
  <link rel="stylesheet" href="../../../styles.css">
  <link rel="stylesheet" href="../../../opportunity.css">
  <script type="application/ld+json">{structured}</script>
</head>
<body>
  <main class="opportunity-page">
    <nav class="opportunity-nav"><a href="../../../">← YOKOHAMA CHANGE</a><a href="../../">神奈川の受付中案件一覧</a></nav>
    <header class="opportunity-list-header">
      <span>OPEN OPPORTUNITIES · {esc(region)}</span>
      <h1>{esc(region)}の現在受付中案件</h1>
      <p>公式ページで新規参加期限を確認でき、現在受付中と判定した案件だけを掲載します。最終確認は必ず公式情報で行ってください。</p>
      <small>受付中 {count}件 · 商用70+ {high}件 · 生成 {esc(generated_at)}</small>
    </header>
    <section class="opportunity-list">{''.join(cards)}</section>
  </main>
</body>
</html>
'''


def add_region_nav(region_counts: list[tuple[str, str, int]]) -> None:
    try:
        source = INDEX.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    marker = '<section class="opportunity-list">'
    if marker not in source:
        return
    links = ''.join(
        f'<a href="regions/{esc(slug)}/">{esc(region)} <b>{count}</b></a>'
        for region, slug, count in region_counts
    )
    nav = f'<nav class="opportunity-region-nav" aria-label="地域別受付中案件">{links}</nav>\n    '
    source = source.replace(marker, nav + marker, 1)
    INDEX.write_text(source, encoding="utf-8")


def update_sitemap(region_counts: list[tuple[str, str, int]]) -> None:
    try:
        tree = ET.parse(SITEMAP)
        root = tree.getroot()
    except (FileNotFoundError, ET.ParseError):
        return
    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("", ns)
    today = datetime.now(timezone.utc).date().isoformat()
    existing = {node.text for node in root.findall(f"{{{ns}}}url/{{{ns}}}loc") if node.text}
    for _, slug, _ in region_counts:
        loc = f"{BASE}opportunities/regions/{slug}/"
        if loc in existing:
            continue
        node = ET.SubElement(root, f"{{{ns}}}url")
        ET.SubElement(node, f"{{{ns}}}loc").text = loc
        ET.SubElement(node, f"{{{ns}}}lastmod").text = today
        ET.SubElement(node, f"{{{ns}}}changefreq").text = "daily"
        ET.SubElement(node, f"{{{ns}}}priority").text = "0.85"
    tree.write(SITEMAP, encoding="utf-8", xml_declaration=True)


def main() -> int:
    payload = load_json(OPEN_JSON, {})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    generated_at = str(payload.get("generated_at") or datetime.now(timezone.utc).isoformat())

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        if not isinstance(item, dict):
            continue
        region = str(item.get("region", "")).strip()
        if region and region in SLUGS:
            groups[region].append(item)

    if REGIONS_DIR.exists():
        shutil.rmtree(REGIONS_DIR)
    REGIONS_DIR.mkdir(parents=True, exist_ok=True)

    region_counts: list[tuple[str, str, int]] = []
    for region, region_items in groups.items():
        if not region_items:
            continue
        slug = SLUGS[region]
        target = REGIONS_DIR / slug
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(render_region(region, region_items, generated_at), encoding="utf-8")
        region_counts.append((region, slug, len(region_items)))

    region_counts.sort(key=lambda x: (-x[2], x[0]))
    add_region_nav(region_counts)
    update_sitemap(region_counts)
    print(json.dumps({"indexed_regions": [{"region": r, "slug": s, "open": n} for r,s,n in region_counts]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
