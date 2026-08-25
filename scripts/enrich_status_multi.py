#!/usr/bin/env python3
"""Run the conservative status engine for approved Kanagawa official domains.

The underlying deadline parser remains unchanged. This wrapper only broadens the
official-domain allowlist; it does not relax the requirement for an explicit first-time
participation/application deadline before an item can become `受付中`.
"""
from __future__ import annotations

from urllib.parse import urlparse

import enrich_status as core

APPROVED_OFFICIAL_HOSTS = {
    "www.city.yokohama.lg.jp",
    "www.pref.kanagawa.jp",
    "www.city.kawasaki.jp",
    "www.city.sagamihara.kanagawa.jp",
    "www.city.fujisawa.kanagawa.jp",
    "www.city.chigasaki.kanagawa.jp",
    "www.city.yokosuka.kanagawa.jp",
    "www.city.kamakura.kanagawa.jp",
    "www.city.hiratsuka.kanagawa.jp",
    "www.city.odawara.kanagawa.jp",
    "www.city.miura.kanagawa.jp",
}


def approved_detail_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == "https" and (parsed.hostname or "") in APPROVED_OFFICIAL_HOSTS


def main() -> int:
    core.official_detail_url = approved_detail_url
    core.USER_AGENT = "KanagawaChange/1.0 (+deadline-status; respectful-fetching)"
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
