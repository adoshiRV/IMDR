"""MOEF (Korea Ministry of Economy & Finance) — 10 RSS boards.

Recipe (proven 2026-06-09):
  https://english.moef.go.kr/{pc|ec|mi}/engmosfrss.do?boardCd={code}

Each feed is RSS 2.0 with `<title>`, `<link>`, `<description>`, `<pubDate>`.
Detail-page links are http (not https); upgrade to https at consumer time.

The DPM-speeches board (M0002) was stale to 2023 on the 2026-06-09 probe —
still emitted in case it resumes; orchestrator can spot empty/stale feeds
in the daily summary.
"""
from __future__ import annotations

import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402

BASE_PC = "https://english.moef.go.kr/pc/engmosfrss.do"
BASE_EC = "https://english.moef.go.kr/ec/engmosfpolicyrss.do"
BASE_MI = "https://english.moef.go.kr/mi/engmosfpublicrss.do"

# (base_url, board_code, stream_label, doc_type)
MOEF_BOARDS: list[tuple[str, str, str, str]] = [
    (BASE_PC, "N0001", "moef_press_releases",     "release"),
    (BASE_PC, "N0002", "moef_media_schedule",     "release"),
    (BASE_EC, "E0001", "moef_policy_general",     "release"),
    (BASE_EC, "E0002", "moef_budget",             "release"),
    (BASE_EC, "E0003", "moef_cooperation",        "release"),
    (BASE_EC, "E0004", "moef_tax",                "release"),
    (BASE_EC, "E0005", "moef_state_property",     "release"),
    (BASE_EC, "E0007", "moef_international",      "release"),
    (BASE_EC, "E0009", "moef_treasury_debt",      "release"),
    (BASE_MI, "M0002", "moef_dpm_speeches",       "speech"),
]


def _parse_pubdate(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        # RSS pubDate is RFC-822 (e.g. "Thu, 04 Jun 2026 15:00:00 GMT").
        dt = parsedate_to_datetime(s)
        if dt is None:
            return None
        # Normalize to date in source TZ; MOEF uses GMT consistently.
        return dt.astimezone(timezone.utc).date()
    except (TypeError, ValueError):
        return None


def _upgrade_http(url: str) -> str:
    if url.startswith("http://english.moef.go.kr"):
        return "https://" + url[len("http://"):]
    return url


def _parse_feed(xml_bytes: bytes, stream: str, doc_type: str) -> list[FilingItem]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    items: list[FilingItem] = []
    for it in root.findall(".//item"):
        title = (it.findtext("title") or "").strip()
        link = _upgrade_http((it.findtext("link") or "").strip())
        pubdate = _parse_pubdate(it.findtext("pubDate") or "")
        if not title or not link or pubdate is None:
            continue
        items.append(FilingItem(
            vendor_code="moef",
            title=title,
            publish_date=pubdate,
            source_url=link,
            pdf_url=None,
            doc_type=doc_type,
            stream=stream,
            extras={"description": (it.findtext("description") or "").strip()[:400]},
        ))
    return items


def discover() -> FetchResult:
    sess = make_session()
    items: list[FilingItem] = []
    failed_boards: list[str] = []
    for base_url, code, stream, doc_type in MOEF_BOARDS:
        url = f"{base_url}?boardCd={code}"
        try:
            r = patient_get(sess, url, attempts=6, base_sleep=1.5)
        except RuntimeError as exc:
            failed_boards.append(f"{stream}({code}): {str(exc)[:80]}")
            continue
        items.extend(_parse_feed(r.content, stream, doc_type))
        time.sleep(0.5)  # be polite — 10 feeds total
    if failed_boards and not items:
        return FetchResult(vendor_code="moef", ok=False, error="; ".join(failed_boards))
    note = f"{len(MOEF_BOARDS) - len(failed_boards)}/{len(MOEF_BOARDS)} boards"
    if failed_boards:
        note += f"  (failed: {', '.join(b.split(':')[0] for b in failed_boards)})"
    return FetchResult(vendor_code="moef", ok=True, items=items, note=note)


if __name__ == "__main__":
    res = discover()
    print(f"moef ok={res.ok} items={len(res.items)} note={res.note}")
    by_stream: dict[str, int] = {}
    for it in res.items:
        by_stream[it.stream] = by_stream.get(it.stream, 0) + 1
    for s, n in sorted(by_stream.items(), key=lambda kv: -kv[1]):
        print(f"  {s:30}  n={n}")
    print()
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.stream:30}  {it.title[:90]}")
