#!/usr/bin/env python3
"""Generate dedicated category landing pages from verified open opportunities only."""
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
CATEGORIES_DIR = OPPORTUNITIES / "categories"
INDEX = OPPORTUNITIES / "index.html"
SITEMAP = DOCS / "sitemap.xml"
BASE = "https://yokohama-change.github.io/yokohama-change/"

CATEGORY_CONFIG = {
    "入札・調達": {
        "slug": "procurement",
        "search_name": "入札・調達・公募",
        "journey_title": "仕事を受注したい",
        "journey_lead": "現在応募できる入札・業務委託・プロポーザルだけをまとめています。",
        "description": "神奈川県内で現在受付中と確認できた入札・調達・公募案件",
    },
    "補助金・支援": {
        "slug": "support",
        "search_name": "補助金・助成金・支援",
        "journey_title": "補助金・支援を探したい",
        "journey_lead": "現在申請できる補助金・助成金・事業者支援だけをまとめています。",
        "description": "神奈川県内で現在受付中と確認できた補助金・助成金・支援制度",
    },
}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def verified_open_feed_item(item: dict[str, Any]) -> bool:
    if item.get("is_open_now") is False:
        return False
    return bool(
        item.get("application_status") == "受付中"
        and item.get("status_confidence") == "high"
        and str(item.get("participation_deadline") or "").strip()
        and str(item.get("url") or "").strip()
        and str(item.get("id") or "").strip()
    )


def prep_copy(item: dict[str, Any]) -> str:
    start = str(item.get("preparation_start_date") or "").strip()
    status = str(item.get("preparation_status") or "").strip()
    days = item.get("preparation_days")
    if not start or not status or days in (None, ""):
        return ""
    if status == "準備開始推奨":
        return f'<div class="opportunity-list-prep">独自目安 · 準備開始推奨 · 標準{esc(days)}日前 · {esc(start)}</div>'
    return f'<div class="opportunity-list-prep">独自目安 · 準備開始 {esc(start)}ごろ · 標準{esc(days)}日前</div>'


def render_page(category: str, items: list[dict[str, Any]], generated_at: str) -> str:
    cfg = CATEGORY_CONFIG[category]
    slug = cfg["slug"]
    search_name = cfg["search_name"]
    journey_title = cfg["journey_title"]
    journey_lead = cfg["journey_lead"]
    canonical = f"{BASE}opportunities/categories/{slug}/"
    count = len(items)
    high = sum(1 for x in items if int(x.get("commercial_score", 0) or 0) >= 70)
    regions = sorted({str(x.get("region") or "").strip() for x in items if str(x.get("region") or "").strip()})
    title = f"{journey_title}｜神奈川県内の{search_name} 現在受付中 {count}件 | YOKOHAMA CHANGE"
    description = f"{cfg['description']}を{count}件掲載。締切・地域・公式情報へのリンクを分かりやすく確認できます。"

    cards = []
    for item in sorted(items, key=lambda x: (-int(x.get("commercial_score", 0) or 0), int(x.get("days_left", 9999) or 9999))):
        exact = "締切時刻まで確認済" if item.get("deadline_time_exact") is True else "締切日確認済・時刻未確認"
        cards.append(f'''<article class="opportunity-list-card" data-category-card data-region="{esc(item.get('region'))}" data-search="{esc(str(item.get('title') or '').lower())}">
  <div class="opportunity-list-top"><span>受付中</span><b>見る優先度 {esc(item.get("commercial_score", 0))}</b></div>
  <a href="../../{esc(item.get('id'))}.html">{esc(item.get('title'))}</a>
  {prep_copy(item)}
  <p>{esc(item.get('region'))} · {esc(item.get('source_name'))} · {esc(item.get('opportunity_type'))}</p>
  <small>締切 {esc(item.get('deadline_label') or item.get('participation_deadline'))} · {esc(exact)}</small>
</article>''')

    structured = json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage", "name": title,
        "url": canonical, "description": description, "dateModified": generated_at,
        "inLanguage": "ja-JP", "isPartOf": {"@type":"WebSite","name":"YOKOHAMA CHANGE","url":BASE},
    }, ensure_ascii=False).replace("</", "<\\/")

    region_options = ''.join(f'<option value="{esc(region)}">{esc(region)}</option>' for region in regions)
    script = r'''<script>
(() => {
  const cards = [...document.querySelectorAll('[data-category-card]')];
  const search = document.querySelector('#categorySearch');
  const region = document.querySelector('#categoryRegion');
  const reset = document.querySelector('#categoryReset');
  const summary = document.querySelector('#categoryResultSummary');
  const empty = document.querySelector('#categoryEmpty');
  function render(){
    const q = String(search?.value || '').trim().toLowerCase();
    const r = String(region?.value || '');
    let shown = 0;
    cards.forEach(card => {
      const okQ = !q || (card.dataset.search || '').includes(q);
      const okR = !r || card.dataset.region === r;
      card.hidden = !(okQ && okR);
      if (!card.hidden) shown += 1;
    });
    if (summary) summary.innerHTML = `<strong>${shown}件</strong> 表示中`;
    if (empty) empty.style.display = shown ? 'none' : 'block';
  }
  search?.addEventListener('input', render);
  region?.addEventListener('change', render);
  reset?.addEventListener('click', () => { if(search) search.value=''; if(region) region.value=''; render(); });
  render();
})();
</script>'''

    return f'''<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="{esc(description)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{esc(canonical)}">
  <meta property="og:type" content="website"><meta property="og:locale" content="ja_JP"><meta property="og:site_name" content="YOKOHAMA CHANGE">
  <meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{esc(canonical)}">
  <title>{esc(title)}</title>
  <link rel="stylesheet" href="../../../styles.css"><link rel="stylesheet" href="../../../opportunity.css">
  <script type="application/ld+json">{structured}</script>
</head>
<body>
  <main class="opportunity-page category-journey-page">
    <nav class="opportunity-nav"><a class="choice-back" href="../../../">← 3つの入口に戻る</a><a href="../../../alert.html">自分向けに絞る</a></nav>
    <header class="opportunity-list-header">
      <span>あなたが選んだ探し方</span>
      <div class="journey-chip">{esc(category)}</div>
      <h1>{esc(journey_title)}</h1>
      <p>{esc(journey_lead)} 案件名を押すと、締切と「なぜ受付中と判断したか」を確認できます。</p>
      <small>現在受付中 {count}件 · 優先して見る案件 {high}件 · {esc(generated_at)}</small>
    </header>
    <section class="category-tools" aria-label="このページ内で絞り込む">
      <label>キーワード<input id="categorySearch" type="search" placeholder="例：システム、清掃、設備"></label>
      <label>地域<select id="categoryRegion"><option value="">すべての地域</option>{region_options}</select></label>
      <button id="categoryReset" class="category-reset" type="button">条件をクリア</button>
    </section>
    <div id="categoryResultSummary" class="category-result-summary"><strong>{count}件</strong> 表示中</div>
    <section class="opportunity-list">{''.join(cards)}</section>
    <div id="categoryEmpty" class="category-empty">この条件に一致する案件はありません。条件をクリアしてもう一度ご確認ください。</div>
    <div class="opportunity-warning"><strong>重要：</strong>掲載情報・見る優先度・準備開始目安は参考情報です。応募・申請・契約等の最終判断は必ず公式情報を確認し、利用者ご自身の責任で行ってください。本サービスの利用等により生じた損害等について、運営者は法令上認められる範囲で責任を負いません。 <a href="../../../disclaimer.html">免責事項</a></div>
  </main>
  {script}
</body>
</html>'''


def update_index(category_counts: list[tuple[str, str, int]]) -> None:
    try:
        source = INDEX.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    marker = '<section class="opportunity-list">'
    if marker not in source:
        return
    links = ''.join(
        f'<a href="categories/{esc(slug)}/">{esc(CATEGORY_CONFIG[category]["search_name"])} <b>{count}</b></a>'
        for category, slug, count in category_counts
    )
    nav = f'<nav class="opportunity-region-nav opportunity-category-nav" aria-label="分類別受付中案件">{links}</nav>\n    '
    source = source.replace(marker, nav + marker, 1)
    INDEX.write_text(source, encoding="utf-8")


def update_sitemap(category_counts: list[tuple[str, str, int]]) -> None:
    try:
        tree = ET.parse(SITEMAP); root = tree.getroot()
    except (FileNotFoundError, ET.ParseError):
        return
    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"; ET.register_namespace("", ns)
    today = datetime.now(timezone.utc).date().isoformat()
    existing = {node.text for node in root.findall(f"{{{ns}}}url/{{{ns}}}loc") if node.text}
    for _, slug, _ in category_counts:
        loc = f"{BASE}opportunities/categories/{slug}/"
        if loc in existing: continue
        node = ET.SubElement(root, f"{{{ns}}}url")
        ET.SubElement(node, f"{{{ns}}}loc").text = loc
        ET.SubElement(node, f"{{{ns}}}lastmod").text = today
        ET.SubElement(node, f"{{{ns}}}changefreq").text = "daily"
        ET.SubElement(node, f"{{{ns}}}priority").text = "0.85"
    tree.write(SITEMAP, encoding="utf-8", xml_declaration=True)


def main() -> int:
    payload = load_json(OPEN_JSON, {})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list): items = []
    generated_at = str(payload.get("generated_at") or datetime.now(timezone.utc).isoformat())
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        if not isinstance(item, dict) or not verified_open_feed_item(item): continue
        category = str(item.get("category") or "").strip()
        if category in CATEGORY_CONFIG: groups[category].append(item)
    if CATEGORIES_DIR.exists(): shutil.rmtree(CATEGORIES_DIR)
    CATEGORIES_DIR.mkdir(parents=True, exist_ok=True)
    category_counts: list[tuple[str, str, int]] = []
    for category, category_items in groups.items():
        if not category_items: continue
        slug = CATEGORY_CONFIG[category]["slug"]
        target = CATEGORIES_DIR / slug; target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(render_page(category, category_items, generated_at), encoding="utf-8")
        category_counts.append((category, slug, len(category_items)))
    category_counts.sort(key=lambda x: (-x[2], x[0]))
    update_index(category_counts); update_sitemap(category_counts)
    print(json.dumps({"indexed_categories": [{"category": c, "slug": s, "open": n} for c,s,n in category_counts]}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
