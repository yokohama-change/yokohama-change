#!/usr/bin/env python3
"""Generate region-aware static opportunity pages for the Kanagawa beta."""
from __future__ import annotations

import generate_opportunity_pages as core


_original_detail = core.render_detail
_original_index = core.render_index
_original_sitemap = core.build_sitemap


def render_detail(item, generated_at):
    html = _original_detail(item, generated_at)
    region = str(item.get("region") or "神奈川県内")
    html = html.replace("横浜市の公式情報を確認する →", f"{region}の公式情報を確認する →")
    html = html.replace("横浜市公式情報", f"{region}公式情報")
    old_warning = (
        '<div class="opportunity-warning">YOKOHAMA CHANGEの商用スコア・MY FIT等は公式評価ではありません。'
        '応募資格、提出物、期限変更、契約条件などの最終判断は必ず公式ページで確認してください。</div>'
    )
    new_warning = (
        '<div class="opportunity-warning"><strong>重要：</strong>YOKOHAMA CHANGEの商用スコア・MY FIT等は公式評価ではありません。'
        '応募資格、提出物、期限変更、契約条件などの最終判断は必ず公式ページで確認し、利用者ご自身の責任で行ってください。'
        '本サービスの利用等により生じた損害・損失・機会損失等について、運営者は法令上認められる範囲で責任を負いません。 '
        '<a href="../disclaimer.html">免責事項の全文</a></div>'
    )
    html = html.replace(old_warning, new_warning)
    return html


def render_index(open_items, generated_at):
    html = _original_index(open_items, generated_at)
    html = html.replace(
        "横浜市の公式情報から現在受付中と確認できた入札・調達・補助金の静的一覧。締切と商用スコア付き。",
        "神奈川県内の公式情報から現在受付中と確認できた入札・調達・補助金の静的一覧。締切と商用スコア付き。",
    )
    html = html.replace("横浜市の現在受付中 入札・調達・補助金一覧", "神奈川県内の現在受付中 入札・調達・補助金一覧")
    html = html.replace("<h1>横浜市の現在受付中案件</h1>", "<h1>神奈川県内の現在受付中案件</h1>")
    legal = (
        '<div class="opportunity-warning"><strong>重要：</strong>掲載情報は参考情報です。応募・申請・契約等の最終判断は必ず公式情報を確認し、'
        '利用者ご自身の責任で行ってください。本サービスの利用等により生じた損害等について、運営者は法令上認められる範囲で責任を負いません。 '
        '<a href="../disclaimer.html">免責事項</a></div>'
    )
    html = html.replace("    <section class=\"opportunity-list\">", f"    {legal}\n    <section class=\"opportunity-list\">", 1)
    return html


def build_sitemap(open_items, lastmod):
    xml = _original_sitemap(open_items, lastmod)
    if f"{core.SITE}/disclaimer.html" in xml:
        return xml
    entry = (
        "  <url>\n"
        f"    <loc>{core.SITE}/disclaimer.html</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        "    <changefreq>monthly</changefreq>\n"
        "    <priority>0.4</priority>\n"
        "  </url>\n"
    )
    return xml.replace("</urlset>", entry + "</urlset>")


def main():
    core.render_detail = render_detail
    core.render_index = render_index
    core.build_sitemap = build_sitemap
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())