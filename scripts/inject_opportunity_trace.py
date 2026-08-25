#!/usr/bin/env python3
"""Inject a user-visible verification trace into generated open-opportunity pages."""
from __future__ import annotations

import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "docs" / "data" / "latest.json"
OUT_DIR = ROOT / "docs" / "opportunities"
STYLE_NAME = "opportunity-trace.css"
STYLE_LINK = f'<link rel="stylesheet" href="../{STYLE_NAME}">'
JST = timezone(timedelta(hours=9))


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def fmt_jst(iso: str) -> str:
    raw = str(iso or "").strip()
    if not raw:
        return "—"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return dt.astimezone(JST).strftime("%Y/%m/%d %H:%M")
    except ValueError:
        return raw


def fmt_date(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    try:
        return datetime.fromisoformat(raw).strftime("%Y/%m/%d")
    except ValueError:
        return raw


def trace_block(item: dict[str, Any]) -> str:
    reason = str(item.get("status_reason") or "").strip()
    region = str(item.get("region") or "神奈川県内").strip()
    source_name = str(item.get("source_name") or "公式情報").strip()
    cutoff = str(item.get("participation_deadline_at") or "").strip()
    deadline_date = str(item.get("participation_deadline") or "").strip()
    exact = item.get("deadline_time_exact") is True
    precision = "公式ページ上の締切時刻まで確認済み" if exact else "締切日を確認・締切時刻は未確認"
    deadline_display = fmt_jst(cutoff) if exact else fmt_date(deadline_date)
    checked_at = str(item.get("status_checked_at") or "").strip()

    return f'''      <section class="opportunity-trace" aria-label="受付中判定の確認内容">
        <span class="opportunity-trace-kicker">YOKOHAMA CHANGEの確認内容</span>
        <h2>なぜ「受付中」と表示しているの？</h2>
        <div class="opportunity-trace-grid">
          <div><span>確認した公式情報</span><b>{e(region)} · {e(source_name)}</b></div>
          <div><span>参加期限</span><b>{e(deadline_display)}</b><small>{e(precision)}</small></div>
          <div><span>受付中とした理由</span><b>{e(reason)}</b></div>
          <div><span>公開チェック</span><b>公開基準を通過</b></div>
        </div>
        {f'<p class="opportunity-trace-checked">状態を確認した時刻: {e(fmt_jst(checked_at))}</p>' if checked_at else ''}
        <p class="opportunity-trace-note">ここはYOKOHAMA CHANGEによる機械判定の説明です。応募資格・提出物・期限変更などを保証するものではありません。応募前には必ず自治体の公式ページをご確認ください。</p>
      </section>'''


def inject_page(page: str, item: dict[str, Any]) -> str:
    if item.get("is_open_now") is not True:
        return page
    if 'class="opportunity-trace"' in page:
        return page

    if STYLE_LINK not in page:
        page = page.replace(
            '<link rel="stylesheet" href="../opportunity.css">',
            '<link rel="stylesheet" href="../opportunity.css">\n  ' + STYLE_LINK,
            1,
        )

    marker = '      <section class="opportunity-section">\n        <h2>判定根拠</h2>'
    block = trace_block(item)
    if marker in page:
        return page.replace(marker, block + "\n" + marker, 1)

    marker = '      <a class="opportunity-official"'
    if marker in page:
        return page.replace(marker, block + "\n" + marker, 1)
    return page


def main() -> int:
    payload = load_json(LATEST, {})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    open_items = {
        str(item.get("id")): item
        for item in items
        if isinstance(item, dict) and item.get("is_open_now") is True and item.get("id")
    }

    injected = 0
    missing_pages: list[str] = []
    for item_id, item in open_items.items():
        path = OUT_DIR / f"{item_id}.html"
        if not path.exists():
            missing_pages.append(item_id)
            continue
        before = path.read_text(encoding="utf-8")
        after = inject_page(before, item)
        if after != before:
            path.write_text(after, encoding="utf-8")
            injected += 1

    result = {"open_items": len(open_items), "trace_pages_injected": injected, "missing_pages": missing_pages}
    print(json.dumps(result, ensure_ascii=False))
    return 1 if missing_pages else 0


if __name__ == "__main__":
    raise SystemExit(main())
