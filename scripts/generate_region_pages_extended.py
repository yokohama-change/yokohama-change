#!/usr/bin/env python3
"""Generate regional SEO landing pages for the current staged Kanagawa free beta."""
from __future__ import annotations

import generate_region_pages as core

core.SLUGS.update({
    "藤沢市": "fujisawa",
    "茅ヶ崎市": "chigasaki",
    "横須賀市": "yokosuka",
    "鎌倉市": "kamakura",
})

_original_render_region = core.render_region


def render_region(region, items, generated_at):
    html = _original_render_region(region, items, generated_at)
    legal = (
        '<div class="opportunity-warning"><strong>重要：</strong>掲載情報は参考情報です。応募・申請・契約等の最終判断は必ず公式情報を確認し、'
        '利用者ご自身の責任で行ってください。本サービスの利用等により生じた損害等について、運営者は法令上認められる範囲で責任を負いません。 '
        '<a href="../../../disclaimer.html">免責事項</a></div>'
    )
    return html.replace("  </main>", f"    {legal}\n  </main>", 1)


core.render_region = render_region

if __name__ == "__main__":
    raise SystemExit(core.main())
