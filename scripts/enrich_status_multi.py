#!/usr/bin/env python3
"""Run the conservative status engine for approved Kanagawa official domains.

The underlying deadline parser remains conservative. This wrapper broadens the
official-domain allowlist and masks downstream compound labels such as
`質問受付期間` so they cannot be mistaken for a first-time participation deadline.
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
    "www.city.zushi.kanagawa.jp",
    "www.city.ebina.kanagawa.jp",
    "www.city.isehara.kanagawa.jp",
    "www.city.zama.kanagawa.jp",
    "www.town.oiso.kanagawa.jp",
    "www.town.ninomiya.kanagawa.jp",
}

DOWNSTREAM_PREFIX_BLOCKERS = (
    "質問",
    "提案",
    "企画提案",
    "入札書",
    "開札",
    "ヒアリング",
    "プレゼン",
    "指名・非指名",
    "関連資料",
    "設計図書",
    "参加資格確認結果",
)

_original_deadline_at_label = core.deadline_at_label


def approved_detail_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == "https" and (parsed.hostname or "") in APPROVED_OFFICIAL_HOSTS


def mask_downstream_compound_labels(text: str, label: str) -> str:
    """Hide generic labels embedded in downstream phrases on the same line.

    Example: `質問受付期間 9月4日まで` contains the generic label `受付期間`,
    but it is a question window rather than a participation window. We only mask
    the label occurrence; all surrounding text and dates remain unchanged.
    """
    if not text or not label:
        return text
    chars = list(text)
    start = 0
    while True:
        idx = text.find(label, start)
        if idx < 0:
            break
        line_start = text.rfind("\n", 0, idx) + 1
        prefix = text[line_start:idx][-60:]
        if any(term in prefix for term in DOWNSTREAM_PREFIX_BLOCKERS):
            chars[idx] = "□"
        start = idx + len(label)
    return "".join(chars)


def safer_deadline_at_label(text: str, label: str, default_year: int):
    return _original_deadline_at_label(mask_downstream_compound_labels(text, label), label, default_year)


# Patch the core parser for both workflow execution and tests importing this wrapper.
core.deadline_at_label = safer_deadline_at_label


def main() -> int:
    core.official_detail_url = approved_detail_url
    core.USER_AGENT = "KanagawaChange/1.0 (+deadline-status; respectful-fetching)"
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
