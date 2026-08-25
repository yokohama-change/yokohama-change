#!/usr/bin/env python3
"""Generate region-aware static opportunity pages for the Kanagawa beta."""
from __future__ import annotations

import generate_opportunity_pages as core


_original_detail = core.render_detail
_original_index = core.render_index


def render_detail(item, generated_at):
    html = _original_detail(item, generated_at)
    region = str(item.get("region") or "神奈川県内")
    html = html.replace("横浜市の公式情報を確認する →", f"{region}の公式情報を確認する →")
    html = html.replace("横浜市公式情報", f"{region}公式情報")
    return html


def render_index(open_items, generated_at):
    html = _original_index(open_items, generated_at)
    html = html.replace(
        "横浜市の公式情報から現在受付中と確認できた入札・調達・補助金の静的一覧。締切と商用スコア付き。",
        "神奈川県内の公式情報から現在受付中と確認できた入札・調達・補助金の静的一覧。締切と商用スコア付き。",
    )
    html = html.replace("横浜市の現在受付中 入札・調達・補助金一覧", "神奈川県内の現在受付中 入札・調達・補助金一覧")
    html = html.replace("<h1>横浜市の現在受付中案件</h1>", "<h1>神奈川県内の現在受付中案件</h1>")
    return html


def main():
    core.render_detail = render_detail
    core.render_index = render_index
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
