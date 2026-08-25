#!/usr/bin/env python3
"""Apply current staged Kanagawa free-beta coverage to public metadata."""
from __future__ import annotations

import regionalize_outputs as core

core.SCOPE = "神奈川 β（県＋7市の公式情報）"
core.PLANNED_REGIONS = [
    "神奈川県",
    "横浜市",
    "川崎市",
    "相模原市",
    "藤沢市",
    "茅ヶ崎市",
    "横須賀市",
    "鎌倉市",
]


if __name__ == "__main__":
    raise SystemExit(core.main())
