#!/usr/bin/env python3
"""Make generated opportunity HTML easier to understand without touching data logic.

This runs only after all verified static pages are generated. It changes user-visible
Japanese/English labels, never source JSON or scoring/status computation.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPPORTUNITIES = ROOT / "docs" / "opportunities"

REPLACEMENTS = [
    ("神奈川県内の高商用案件（商用70+）", "神奈川県内の優先して見たい案件（見る優先度70以上）"),
    ("高商用70+", "優先度70以上"),
    ("商用70+", "見る優先度70以上"),
    ("YOKOHAMA CHANGE商用スコア", "YOKOHAMA CHANGE独自の見る優先度"),
    ("商用スコア", "見る優先度"),
    ("<b>商用 ", "<b>見る優先度 "),
    ("信頼度high", "公開基準を通過"),
    ("OPEN OPPORTUNITIES ·", "受付中案件 ·"),
    ("FOCUS · VERIFIED OPEN ONLY", "条件に合う受付中案件"),
    (" · 生成 ", " · 更新 "),
]


def transform_html(source: str) -> str:
    result = source
    for before, after in REPLACEMENTS:
        result = result.replace(before, after)
    return result


def main() -> int:
    changed = 0
    scanned = 0
    if not OPPORTUNITIES.exists():
        print(json.dumps({"scanned": 0, "changed": 0}, ensure_ascii=False))
        return 0

    for path in OPPORTUNITIES.rglob("*.html"):
        scanned += 1
        before = path.read_text(encoding="utf-8")
        after = transform_html(before)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed += 1

    print(json.dumps({"scanned": scanned, "changed": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
