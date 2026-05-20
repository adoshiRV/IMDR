"""Adaptive Card formatter for the Polymarket macro snapshot.

Consumes the `SnapshotData` produced by
`scripts.prediction.polymarket.macro_snapshot.collect_snapshot_rows` and
returns an Adaptive Card content dict suitable for
`imdr.notifications.teams.post_adaptive_card`.

The card mirrors the HTML snapshot's section layout but renders one row per
event (headline / modal sub-market only — tail rows are dropped to keep the
card under the Teams ~28 KB payload limit). Each row links to its
Polymarket event URL via a `selectAction` so the desk can click through.

The HTML snapshot remains the canonical full-detail artifact; this card is
the Teams-channel summary.
"""

from __future__ import annotations

import json
from typing import Any


POLYMARKET_EVENT_URL = "https://polymarket.com/event/{slug}"

# Teams rejects AdaptiveCards over 28,672 bytes (observed `MessageSizeExceeded`).
# Aim well below that to cover Workflows envelope + section headers + footer.
MAX_CARD_BYTES = 24_000

SECTION_ORDER = (
    "Geopolitics / Oil",
    "US Data & Fed",
    "Europe / G10 CB",
    "Asia Overlay",
    "Tariffs / Trade",
    "Recently Resolved",
)


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:.1f}%"


def _fmt_delta_text(d: float | None) -> tuple[str, str]:
    """Return (text, adaptive-card-color) for a delta value."""
    if d is None:
        return ("n/a", "Default")
    pp = d * 100
    if pp > 0.05:
        return (f"+{pp:.1f}pp", "Good")
    if pp < -0.05:
        return (f"{pp:.1f}pp", "Attention")
    return (f"{pp:+.1f}pp", "Default")


def _fmt_vol(v: float | None) -> str:
    if v is None or v <= 0:
        return "—"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:.0f}"


def _strip_long(s: str, n: int = 90) -> str:
    s = (s or "").strip().rstrip("?")
    return s if len(s) <= n else s[: n - 1] + "…"


def _fmt_gap(gap: float | None) -> str:
    """Decisiveness gap pill — same logic as HTML's `_fmt_gap`."""
    if gap is None:
        return ""
    pp = gap * 100
    if pp < 0:
        return f"{pp:+.1f}pp vs leading horizon"
    if pp <= 5:
        return f"gap +{pp:.1f}pp · two-way"
    return f"gap +{pp:.1f}pp"


def _fmt_burst(ratio: float | None) -> str:
    """Vol-burst pill — same thresholds as HTML's `_fmt_burst`."""
    if ratio is None:
        return ""
    if ratio >= 1.5:
        return f"{ratio:.1f}× burst"
    if ratio <= 0.5:
        return f"{ratio:.1f}× quiet"
    return ""


def _fmt_rel_subnote(delta: float | None, prior: float | None) -> str:
    """Relative %-change subnote — mirrors HTML's tail-regime annotation.

    Only renders when prior was in the tail (<20% or >80%) so the pp move
    underplays the magnitude. e.g. a 1pp move on a 2% prior is "+50% rel".
    """
    if delta is None or prior is None or abs(delta) < 0.005 or prior <= 0:
        return ""
    if not (prior < 0.20 or prior > 0.80):
        return ""
    rel = (delta / prior) * 100
    sign = "+" if rel >= 0 else ""
    return f"{sign}{rel:.0f}% rel"


def _delta_col(text: str, color: str, rel_note: str = "",
               *, subtle: bool = False) -> dict[str, Any]:
    """Right-aligned delta column. `rel_note` renders as a small subnote
    under the pp value when prior was in the tail regime.
    """
    items: list[dict[str, Any]] = [{
        "type": "TextBlock",
        "text": text,
        "color": color,
        "size": "Small",
        "horizontalAlignment": "Right",
        **({"isSubtle": True} if subtle else {}),
    }]
    if rel_note:
        items.append({
            "type": "TextBlock",
            "text": rel_note,
            "isSubtle": True,
            "size": "Small",
            "horizontalAlignment": "Right",
            "spacing": "None",
        })
    return {"type": "Column", "width": "60px", "items": items}


def _event_blocks(row: dict) -> list[dict[str, Any]]:
    """One event → headline ColumnSet + tail-row ColumnSets.

    Mirrors the HTML's `tr.headline` + `tr.subrow` structure: the modal
    sub-market goes on the headline row with full styling; remaining
    sub-markets in `row['tail']` render as compact subtle rows below.
    """
    asset = row.get("asset") or ""
    label = _strip_long(row.get("label") or "", 80)
    modal_q = _strip_long(row.get("modal_q") or "", 80)
    yes_pct = _fmt_pct(row.get("yes"))
    d6_text, d6_color = _fmt_delta_text(row.get("delta_6h"))
    d24_text, d24_color = _fmt_delta_text(row.get("delta_24h"))
    d7_text, d7_color = _fmt_delta_text(row.get("delta_7d"))
    vol_text = _fmt_vol(row.get("vol_24h"))
    burst = _fmt_burst(row.get("vol_ratio"))
    gap = _fmt_gap(row.get("gap"))
    slug = row.get("event_slug") or ""

    subtitle_bits: list[str] = []
    if row.get("event_date"):
        subtitle_bits.append(f"target {row['event_date']}")
    if row.get("horizon_mismatch_days") is not None and row.get("modal_qdate"):
        subtitle_bits.append(
            f"⚠ outcome shown is {row['modal_qdate']} "
            f"({int(row['horizon_mismatch_days'])}d off target)"
        )

    middle_items: list[dict[str, Any]] = [
        {"type": "TextBlock", "text": label, "weight": "Bolder", "wrap": True},
        {"type": "TextBlock", "text": modal_q, "isSubtle": True, "wrap": True,
         "spacing": "None"},
    ]
    if subtitle_bits:
        middle_items.append({
            "type": "TextBlock",
            "text": " · ".join(subtitle_bits),
            "isSubtle": True,
            "size": "Small",
            "wrap": True,
            "spacing": "None",
        })

    yes_items: list[dict[str, Any]] = [{
        "type": "TextBlock", "text": yes_pct, "weight": "Bolder",
        "color": "Accent", "horizontalAlignment": "Right",
    }]
    if gap:
        yes_items.append({
            "type": "TextBlock", "text": gap, "isSubtle": True,
            "size": "Small", "horizontalAlignment": "Right", "spacing": "None",
        })

    vol_items: list[dict[str, Any]] = [{
        "type": "TextBlock", "text": vol_text, "size": "Small",
        "horizontalAlignment": "Right",
    }]
    if burst:
        vol_items.append({
            "type": "TextBlock", "text": burst, "isSubtle": True,
            "size": "Small", "horizontalAlignment": "Right", "spacing": "None",
        })

    rel_24h_main = _fmt_rel_subnote(row.get("delta_24h"), row.get("prior_24h"))

    headline: dict[str, Any] = {
        "type": "ColumnSet",
        "spacing": "Small",
        "separator": True,
        "columns": [
            {"type": "Column", "width": "60px",
             "items": [{"type": "TextBlock", "text": asset or " ",
                        "weight": "Bolder", "color": "Accent", "wrap": True}]},
            {"type": "Column", "width": "stretch", "items": middle_items},
            {"type": "Column", "width": "75px", "items": yes_items},
            _delta_col(d6_text, d6_color),
            _delta_col(d24_text, d24_color, rel_24h_main),
            _delta_col(d7_text, d7_color),
            {"type": "Column", "width": "70px", "items": vol_items},
        ],
    }
    if slug:
        headline["selectAction"] = {
            "type": "Action.OpenUrl",
            "url": POLYMARKET_EVENT_URL.format(slug=slug),
        }

    blocks: list[dict[str, Any]] = [headline]

    # Tail sub-markets — same columns, subdued styling, no asset/event repeat.
    for t in row.get("tail") or []:
        t_q = _strip_long(t.get("q") or "", 80)
        t_yes = _fmt_pct(t.get("yes"))
        t_d6_text, t_d6_color = _fmt_delta_text(t.get("delta_6h"))
        t_d24_text, t_d24_color = _fmt_delta_text(t.get("delta_24h"))
        t_d7_text, t_d7_color = _fmt_delta_text(t.get("delta_7d"))
        t_vol = _fmt_vol(t.get("vol_24h"))
        t_rel = _fmt_rel_subnote(t.get("delta_24h"), t.get("prior_24h"))

        sub: dict[str, Any] = {
            "type": "ColumnSet",
            "spacing": "None",
            "columns": [
                {"type": "Column", "width": "60px", "items": []},
                {"type": "Column", "width": "stretch",
                 "items": [{"type": "TextBlock", "text": t_q,
                            "isSubtle": True, "size": "Small", "wrap": True}]},
                {"type": "Column", "width": "75px",
                 "items": [{"type": "TextBlock", "text": t_yes,
                            "isSubtle": True, "size": "Small",
                            "horizontalAlignment": "Right"}]},
                _delta_col(t_d6_text, t_d6_color, subtle=True),
                _delta_col(t_d24_text, t_d24_color, t_rel, subtle=True),
                _delta_col(t_d7_text, t_d7_color, subtle=True),
                {"type": "Column", "width": "70px",
                 "items": [{"type": "TextBlock", "text": t_vol,
                            "isSubtle": True, "size": "Small",
                            "horizontalAlignment": "Right"}]},
            ],
        }
        blocks.append(sub)

    return blocks


def _bytes_of(body: list[dict[str, Any]]) -> int:
    return len(json.dumps(body, ensure_ascii=False).encode("utf-8"))


def _header_blocks(title: str, subtitle: str) -> list[dict[str, Any]]:
    return [
        {"type": "TextBlock", "text": title, "size": "Large",
         "weight": "Bolder", "wrap": True},
        {"type": "TextBlock", "text": subtitle, "isSubtle": True,
         "size": "Small", "spacing": "Small", "wrap": True},
    ]


def _section_header(section: str) -> dict[str, Any]:
    return {"type": "TextBlock", "text": section, "size": "Medium",
            "weight": "Bolder", "spacing": "Medium", "wrap": True}


def _column_header() -> dict[str, Any]:
    """Header row mirroring `_row_block`'s ColumnSet shape so columns line up."""
    def _h(text: str, *, right: bool = False) -> dict[str, Any]:
        block = {
            "type": "TextBlock",
            "text": text,
            "weight": "Bolder",
            "isSubtle": True,
            "size": "Small",
        }
        if right:
            block["horizontalAlignment"] = "Right"
        return block

    return {
        "type": "ColumnSet",
        "spacing": "Small",
        "columns": [
            {"type": "Column", "width": "60px", "items": [_h("Asset")]},
            {"type": "Column", "width": "stretch", "items": [_h("Event · Outcome")]},
            {"type": "Column", "width": "75px", "items": [_h("Yes %", right=True)]},
            {"type": "Column", "width": "60px", "items": [_h("Δ6h", right=True)]},
            {"type": "Column", "width": "60px", "items": [_h("Δ24h", right=True)]},
            {"type": "Column", "width": "60px", "items": [_h("Δ7d", right=True)]},
            {"type": "Column", "width": "70px", "items": [_h("Vol 24h", right=True)]},
        ],
    }


def _wrap_card(body: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap a body list in an AdaptiveCard with `msteams.width: Full` so the
    Teams renderer uses the full channel width instead of a narrow side card.
    """
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "msteams": {"width": "Full"},
        "body": body,
    }


def build_cards(
    rows: list[dict],
    snapshot_ts: str,
    generated_ts: str,
    missing: list[str] | None = None,
    dropped_stale: list[str] | None = None,
    *,
    title_suffix: str = "",
) -> list[dict[str, Any]]:
    """Build one or more Adaptive Cards for a macro snapshot.

    Splits across cards along section boundaries (and within a section if a
    single section exceeds `MAX_CARD_BYTES`). Each card gets the title +
    snapshot/generated subtitle so the desk can read them in any order; the
    last card carries the footer with `missing` / `dropped_stale` notes.
    `title_suffix` is appended to the title (" — AM" / " — PM"). When more
    than one card is produced, a "(N/M)" pagination suffix is appended too.
    """
    title_base = f"Polymarket Macro Snapshot{title_suffix}"
    subtitle = f"snapshot {snapshot_ts} · generated {generated_ts}"

    by_section: dict[str, list[dict]] = {}
    for r in rows:
        by_section.setdefault(r["section"], []).append(r)

    # Pack rows greedily into pages keyed by serialized-bytes budget.
    pages: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = list(_header_blocks(title_base, subtitle))

    def _flush() -> None:
        nonlocal current
        if len(current) > 2:  # more than just header
            pages.append(current)
        current = list(_header_blocks(title_base, subtitle))

    for section in SECTION_ORDER:
        section_rows = by_section.get(section, [])
        if not section_rows:
            continue
        section_header = _section_header(section)
        column_header = _column_header()
        candidate = current + [section_header, column_header]
        if _bytes_of(candidate) > MAX_CARD_BYTES:
            _flush()
            candidate = current + [section_header, column_header]
        current = candidate

        for r in section_rows:
            row_blocks = _event_blocks(r)
            candidate = current + row_blocks
            if _bytes_of(candidate) > MAX_CARD_BYTES:
                _flush()
                current.append(section_header)
                current.append(_column_header())
                current.extend(row_blocks)
            else:
                current = candidate

    # Footer goes on the final page. Build it then flush.
    footer_bits: list[str] = []
    if missing:
        footer_bits.append(f"not found at snapshot: {', '.join(missing)}")
    if dropped_stale:
        footer_bits.append(f"dropped (stale): {', '.join(dropped_stale)}")
    footer_bits.append("Full HTML at C:\\IMDR_LOCAL\\polymarket\\snapshots\\")
    footer = {
        "type": "TextBlock",
        "text": " · ".join(footer_bits),
        "isSubtle": True,
        "size": "Small",
        "spacing": "Medium",
        "wrap": True,
    }
    candidate = current + [footer]
    if _bytes_of(candidate) > MAX_CARD_BYTES:
        _flush()
        current.append(footer)
    else:
        current = candidate
    _flush()

    # Append pagination to titles when there's more than one card.
    if len(pages) > 1:
        for i, body in enumerate(pages, start=1):
            body[0] = {**body[0], "text": f"{title_base} ({i}/{len(pages)})"}

    return [_wrap_card(body) for body in pages]
