#!/usr/bin/env python3
"""Generate crawlable static pages for YOKOHAMA CHANGE opportunities.

Only high-confidence application-status records with an explicit deadline receive a
static detail page. Current open opportunities are indexable and listed in the
sitemap. Closed/result/qualified-only records remain available for link stability
but are marked noindex so stale opportunities are not used to attract search traffic.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
LATEST = DOCS / "data" / "latest.json"
OUT_DIR = DOCS / "opportunities"
SITEMAP = DOCS / "sitemap.xml"
SITE = "https://yokohama-change.github.io/yokohama-change"
VALID_STATUSES = {"受付中", "参加締切済", "結果掲載済", "資格者のみ進行中"}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def safe_id(value: Any) -> str:
    raw = str(value or "").strip()
    return raw if re.fullmatch(r"[A-Za-z0-9_-]{6,80}", raw) else ""


def publishable(item: dict[str, Any]) -> bool:
    return bool(
        safe_id(item.get("id"))
        and item.get("status_confidence") == "high"
        and str(item.get("participation_deadline_at") or "").strip()
        and item.get("application_status") in VALID_STATUSES
        and item.get("application_status") != "案件外"
    )


def is_open(item: dict[str, Any]) -> bool:
    return item.get("is_open_now") is True and item.get("application_status") == "受付中"


def e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def deadline_label(item: dict[str, Any]) -> str:
    return str(item.get("deadline_label") or item.get("participation_deadline_at") or "").strip()


def detail_title(item: dict[str, Any]) -> str:
    prefix = "受付中" if is_open(item) else str(item.get("application_status") or "案件情報")
    return f"【{prefix}】{str(item.get('title') or '').strip()} | YOKOHAMA CHANGE"


def render_detail(item: dict[str, Any], generated_at: str) -> str:
    item_id = safe_id(item.get("id"))
    canonical = f"{SITE}/opportunities/{item_id}.html"
    open_now = is_open(item)
    robots = "index,follow,max-image-preview:large" if open_now else "noindex,follow"
    title = detail_title(item)
    source_name = str(item.get("source_name") or "横浜市公式情報")
    deadline = deadline_label(item)
    commercial = int(item.get("commercial_score") or 0)
    category = str(item.get("category") or "")
    opportunity_type = str(item.get("opportunity_type") or "")
    status = str(item.get("application_status") or "")
    official_url = str(item.get("url") or "")
    buyers = [str(v) for v in (item.get("buyer_segments") or []) if str(v).strip()]
    status_reason = str(item.get("status_reason") or "")
    meta_description = (
        f"{source_name}の案件情報。{status}、締切 {deadline}。"
        f"YOKOHAMA CHANGE内部商用スコア {commercial}。応募前に公式情報を確認してください。"
    )
    buyer_html = "".join(f"<span>{e(v)}</span>" for v in buyers) or "<span>未分類</span>"
    state_class = "open" if open_now else "closed"
    state_copy = "現在受付中" if open_now else f"現在は「{status}」"
    json_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": title,
            "url": canonical,
            "description": meta_description,
            "dateModified": generated_at,
            "inLanguage": "ja-JP",
            "isPartOf": {"@type": "WebSite", "name": "YOKOHAMA CHANGE", "url": f"{SITE}/"},
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return f'''<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="{e(meta_description)}">
  <meta name="robots" content="{robots}">
  <meta name="theme-color" content="#090b10">
  <link rel="canonical" href="{e(canonical)}">
  <meta property="og:type" content="article">
  <meta property="og:locale" content="ja_JP">
  <meta property="og:site_name" content="YOKOHAMA CHANGE">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(meta_description)}">
  <meta property="og:url" content="{e(canonical)}">
  <title>{e(title)}</title>
  <link rel="stylesheet" href="../styles.css">
  <link rel="stylesheet" href="../opportunity.css">
  <script type="application/ld+json">{json_ld}</script>
</head>
<body>
  <main class="opportunity-page">
    <nav class="opportunity-nav"><a href="../">← YOKOHAMA CHANGE</a><a href="./">受付中案件一覧</a></nav>
    <article class="opportunity-detail {state_class}">
      <div class="opportunity-kicker">YOKOHAMA CHANGE · OFFICIAL SOURCE SIGNAL</div>
      <div class="opportunity-status {state_class}">{e(state_copy)}</div>
      <h1>{e(item.get('title'))}</h1>
      <p class="opportunity-source">{e(source_name)} · {e(category)} · {e(opportunity_type)}</p>
      <div class="opportunity-metrics">
        <div><b>{commercial}</b><span>内部商用スコア</span></div>
        <div><b>{e(deadline)}</b><span>公式参加期限</span></div>
        <div><b>{e(status)}</b><span>現在判定</span></div>
      </div>
      <section class="opportunity-section">
        <h2>想定利用者</h2>
        <div class="opportunity-tags">{buyer_html}</div>
      </section>
      <section class="opportunity-section">
        <h2>判定根拠</h2>
        <p>{e(status_reason) or '公式ページに記載された期限・状態を基に判定しています。'}</p>
      </section>
      <a class="opportunity-official" href="{e(official_url)}" target="_blank" rel="noopener">横浜市の公式情報を確認する →</a>
      <div class="opportunity-warning">YOKOHAMA CHANGEの商用スコア・MY FIT等は公式評価ではありません。応募資格、提出物、期限変更、契約条件などの最終判断は必ず公式ページで確認してください。</div>
    </article>
  </main>
</body>
</html>
'''


def render_index(open_items: list[dict[str, Any]], generated_at: str) -> str:
    cards = []
    for item in sorted(
        open_items,
        key=lambda x: (-int(x.get("commercial_score") or 0), str(x.get("participation_deadline_at") or "")),
    ):
        item_id = safe_id(item.get("id"))
        buyers = " / ".join(str(v) for v in (item.get("buyer_segments") or []))
        cards.append(
            f'''<article class="opportunity-list-card">
  <div class="opportunity-list-top"><span>受付中</span><b>商用 {int(item.get('commercial_score') or 0)}</b></div>
  <a href="{item_id}.html">{e(item.get('title'))}</a>
  <p>{e(item.get('source_name'))} · {e(item.get('opportunity_type'))}</p>
  <small>締切 {e(deadline_label(item))} · {e(buyers)}</small>
</article>'''
        )
    body = "\n".join(cards) if cards else '<div class="opportunity-empty">現在、公式期限を確認できた受付中案件はありません。</div>'
    return f'''<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="横浜市の公式情報から現在受付中と確認できた入札・調達・補助金の静的一覧。締切と商用スコア付き。">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{SITE}/opportunities/">
  <title>横浜市の現在受付中 入札・調達・補助金一覧 | YOKOHAMA CHANGE</title>
  <link rel="stylesheet" href="../styles.css">
  <link rel="stylesheet" href="../opportunity.css">
</head>
<body>
  <main class="opportunity-page">
    <nav class="opportunity-nav"><a href="../">← YOKOHAMA CHANGE</a><a href="../alert.html">MY FIT 無料β</a></nav>
    <header class="opportunity-list-header">
      <span>STATIC OPEN OPPORTUNITIES</span>
      <h1>横浜市の現在受付中案件</h1>
      <p>公式の新規参加期限を確認でき、現在受付中と判定した案件だけを掲載します。最終確認は必ず公式情報で行ってください。</p>
      <small>生成: {e(generated_at)}</small>
    </header>
    <section class="opportunity-list">{body}</section>
  </main>
</body>
</html>
'''


def build_sitemap(open_items: list[dict[str, Any]], lastmod: str) -> str:
    urls = [
        (f"{SITE}/", "daily", "1.0"),
        (f"{SITE}/alert.html", "daily", "0.9"),
        (f"{SITE}/opportunities/", "daily", "0.9"),
    ]
    for item in sorted(open_items, key=lambda x: str(x.get("participation_deadline_at") or "")):
        item_id = safe_id(item.get("id"))
        urls.append((f"{SITE}/opportunities/{item_id}.html", "daily", "0.8"))
    rows = []
    for loc, changefreq, priority in urls:
        rows.append(
            "  <url>\n"
            f"    <loc>{html.escape(loc)}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            "  </url>"
        )
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n"


def main() -> int:
    payload = load_json(LATEST, {})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []

    candidates = [item for item in items if isinstance(item, dict) and publishable(item)]
    open_items = [item for item in candidates if is_open(item)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    expected = {"index.html"}
    generated_at = str(payload.get("generated_at") or datetime.now(ZoneInfo("Asia/Tokyo")).isoformat())
    for item in candidates:
        name = f"{safe_id(item.get('id'))}.html"
        expected.add(name)
        (OUT_DIR / name).write_text(render_detail(item, generated_at), encoding="utf-8")

    (OUT_DIR / "index.html").write_text(render_index(open_items, generated_at), encoding="utf-8")

    # Remove stale generated detail pages that no longer exist in the normalized public window.
    for path in OUT_DIR.glob("*.html"):
        if path.name not in expected:
            path.unlink()

    today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    SITEMAP.write_text(build_sitemap(open_items, today), encoding="utf-8")
    print(json.dumps({"static_pages": len(candidates), "indexable_open_pages": len(open_items)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
