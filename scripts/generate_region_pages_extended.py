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


if __name__ == "__main__":
    raise SystemExit(core.main())
