#!/usr/bin/env python3
"""Generate region-aware static opportunity pages for the Kanagawa beta."""
from __future__ import annotations

import html as html_lib

import generate_opportunity_pages as core


_original_detail = core.render_detail
_original_index = core.render_index
_original_sitemap = core.build_sitemap


def e(value):
    return html_lib.escape(str(value or ""), quote=True)


def preparation_block(item):
    if item.get("is_open_now") is not True:
        return ""
    start = str(item.get("preparation_start_date") or "").strip()
    status = str(item.get("preparation_status") or "").strip()
    days = item.get("preparation_days")
    if not start or not status or days in (None, ""):
        return ""

    if status == "準備開始推奨":
        headline = "準備を始める目安に入っています"
    elif status == "準備開始前":
        headline = f"{start}ごろから準備開始の目安"
    else:
        headline = status

    return f'''      <section class="opportunity-section opportunity-preparation">
        <span class="opportunity-preparation-kicker">YOKOHAMA CHANGE独自の目安</span>
        <h2>{e(headline)}</h2>
        <p><strong>標準準備目安：締切の {e(days)} 日前</strong> ／ 準備開始目安 {e(start)}。案件種別から機械的に付けた参考目安で、自治体の公式期限・応募要件・必要準備期間ではありません。</p>
      </section>'''


def render_detail(item, generated_at):
    page = _original_detail(item, generated_at)
    region = str(item.get("region") or "神奈川県内")
    page = page.replace("横浜市の公式情報を確認する →", f"{region}の公式サイトを開く（外部） ↗")
    page = page.replace("横浜市公式情報", f"{region}公式情報")
    page = page.replace("YOKOHAMA CHANGE · OFFICIAL SOURCE SIGNAL", "自治体公式情報をもとに整理")
    page = page.replace("YOKOHAMA CHANGE内部商用スコア", "YOKOHAMA CHANGE独自の見る優先度")
    page = page.replace("<span>内部商用スコア</span>", "<span>見る優先度（独自目安）</span>")

    prep = preparation_block(item)
    if prep:
        marker = '      <section class="opportunity-section">\n        <h2>想定利用者</h2>'
        page = page.replace(marker, prep + "\n" + marker, 1)

    old_warning = (
        '<div class="opportunity-warning">YOKOHAMA CHANGEの商用スコア・MY FIT等は公式評価ではありません。'
        '応募資格、提出物、期限変更、契約条件などの最終判断は必ず公式ページで確認してください。</div>'
    )
    new_warning = (
        '<div class="opportunity-warning"><strong>大切な確認：</strong>見る優先度・かんたん絞り込み・準備開始目安などはYOKOHAMA CHANGE独自の参考情報です。'
        '応募資格、提出物、期限変更、契約条件などの最終判断は必ず自治体の公式ページで確認し、利用者ご自身の責任で行ってください。'
        '本サービスの利用等により生じた損害・損失・機会損失等について、運営者は法令上認められる範囲で責任を負いません。 '
        '<a href="../disclaimer.html">免責事項の全文</a></div>'
    )
    page = page.replace(old_warning, new_warning)
    return page


def render_index(open_items, generated_at):
    page = _original_index(open_items, generated_at)
    page = page.replace(
        "横浜市の公式情報から現在受付中と確認できた入札・調達・補助金の静的一覧。締切と商用スコア付き。",
        "神奈川県内の公式情報から現在受付中と確認できた入札・調達・補助金の一覧。締切と見る優先度付き。",
    )
    page = page.replace("横浜市の現在受付中 入札・調達・補助金一覧", "神奈川県内の現在受付中 入札・調達・補助金一覧")
    page = page.replace("<h1>横浜市の現在受付中案件</h1>", "<h1>神奈川県内の現在受付中案件</h1>")
    page = page.replace("<b>商用 ", "<b>見る優先度 ")
    page = page.replace(
        "公式の新規参加期限を確認でき、現在受付中と判定した案件だけを掲載します。最終確認は必ず公式情報で行ってください。",
        "公式の新規参加期限を確認でき、現在受付中と判定した案件だけを掲載します。準備開始目安や見る優先度はYOKOHAMA CHANGE独自の参考情報です。最終確認は必ず自治体の公式情報で行ってください。",
    )
    legal = (
        '<div class="opportunity-warning"><strong>大切な確認：</strong>掲載情報・見る優先度・準備開始目安は参考情報です。応募・申請・契約等の最終判断は必ず公式情報を確認し、'
        '利用者ご自身の責任で行ってください。本サービスの利用等により生じた損害等について、運営者は法令上認められる範囲で責任を負いません。 '
        '<a href="../disclaimer.html">免責事項</a></div>'
    )
    page = page.replace("    <section class=\"opportunity-list\">", f"    {legal}\n    <section class=\"opportunity-list\">", 1)
    return page


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
