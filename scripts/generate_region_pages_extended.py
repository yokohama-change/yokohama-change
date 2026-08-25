#!/usr/bin/env python3
"""Generate regional SEO landing pages for the current staged Kanagawa free beta."""
from __future__ import annotations

import html as html_lib

import generate_region_pages as core

core.SLUGS.update({
    "藤沢市": "fujisawa",
    "茅ヶ崎市": "chigasaki",
    "横須賀市": "yokosuka",
    "鎌倉市": "kamakura",
    "平塚市": "hiratsuka",
    "小田原市": "odawara",
    "三浦市": "miura",
})

_original_render_region = core.render_region


def e(value):
    return html_lib.escape(str(value or ""), quote=True)


def render_region(region, items, generated_at):
    page = _original_render_region(region, items, generated_at)

    for item in items:
        # Region pages are generated from open_now.json, which is already the verified
        # current-open feed and does not redundantly carry is_open_now=true on each row.
        if item.get("application_status") != "受付中" or item.get("status_confidence") != "high":
            continue
        start = str(item.get("preparation_start_date") or "").strip()
        status = str(item.get("preparation_status") or "").strip()
        days = item.get("preparation_days")
        item_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or "")
        if not start or not status or days in (None, "") or not item_id:
            continue

        anchor = f'<a href="../../{e(item_id)}.html">{e(title)}</a>'
        if status == "準備開始推奨":
            prep_copy = f'準備開始推奨 · 標準{e(days)}日前 · 目安{e(start)}'
        else:
            prep_copy = f'準備開始目安 {e(start)} · 標準{e(days)}日前'
        badge = f'{anchor}<div class="opportunity-list-prep">独自目安 · {prep_copy}</div>'
        page = page.replace(anchor, badge, 1)

    page = page.replace(
        "公式ページで新規参加期限を確認でき、現在受付中と判定した案件だけを掲載します。最終確認は必ず公式情報で行ってください。",
        "公式ページで新規参加期限を確認でき、現在受付中と判定した案件だけを掲載します。準備開始表示はYOKOHAMA CHANGE独自の参考目安です。最終確認は必ず公式情報で行ってください。",
        1,
    )

    legal = (
        '<div class="opportunity-warning"><strong>重要：</strong>掲載情報・商用スコア・準備開始目安は参考情報です。応募・申請・契約等の最終判断は必ず公式情報を確認し、'
        '利用者ご自身の責任で行ってください。本サービスの利用等により生じた損害等について、運営者は法令上認められる範囲で責任を負いません。 '
        '<a href="../../../disclaimer.html">免責事項</a></div>'
    )
    return page.replace("  </main>", f"    {legal}\n  </main>", 1)


core.render_region = render_region

if __name__ == "__main__":
    raise SystemExit(core.main())
