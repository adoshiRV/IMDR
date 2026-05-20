"""Polywatch alert email formatter.

Produces the HTML email sent by the Polymarket move-detector
(``scripts/prediction/polymarket/polywatch.py``) when one or more
watchlisted events trigger an alert class
(SPIKE / MODAL_FLIP / DRIFT / VOL_BURST).

Layout: asset bucket → events → all sub-markets (each event card renders
every child market in a small table). Alert classes appear as coloured
badges on the event header instead of grouping the email body.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader

_SGT = timezone(timedelta(hours=8))
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

POLYMARKET_EVENT_URL = "https://polymarket.com/event/{slug}"

ALERT_CLASS_ORDER = ("SPIKE", "MODAL_FLIP", "DRIFT", "VOL_BURST")

# Display order for asset buckets in the email body. Buckets not in the list
# are appended in alphabetical order at the end.
ASSET_TAG_ORDER = (
    "oil_mena",
    "fx_safehaven_eur",
    "equity_il_mena",
    "equity_china_taiwan",
    "fx_political_eu",
    "political_us",
    "uncurated",
)

ASSET_TAG_LABELS = {
    "oil_mena":            "Oil / MENA (WTI, Brent, USD)",
    "fx_safehaven_eur":    "FX safe-haven / EUR (Russia-Ukraine)",
    "equity_il_mena":      "Equity risk-off / Israel",
    "equity_china_taiwan": "Equity / USDCNH (Taiwan)",
    "fx_political_eu":     "FX EU politics (EUR, GBP)",
    "political_us":        "US politics (USD, UST, equities)",
    "uncurated":           "Uncategorized (auto-discovered)",
}

# Cap how many uncurated events render per email. The bucket can grow large
# under auto-discovery; keep the email skim-able and footer the rest.
MAX_UNCURATED_PER_EMAIL = 10
# Cap rows per event card. Modal + new-leader rows are always retained.
MAX_CHILDREN_PER_EVENT = 8


@dataclass(frozen=True)
class ChildMarket:
    """One sub-market row inside an event card."""

    condition_id: str
    question: str
    yes_price: float | None
    prior_yes: float | None
    delta: float | None
    vol_24h: float | None
    spread: float | None
    is_modal: bool = False
    was_modal: bool = False
    is_resolved: bool = False


@dataclass(frozen=True)
class PolywatchAlert:
    """One detector finding for a single event in a single detection cycle."""

    event_id: int
    event_slug: str
    event_title: str
    modal_question: str
    alert_classes: tuple[str, ...]
    modal_yes: float
    prior_modal_yes: float | None
    delta: float
    delta_lookback: float | None
    vol_24h: float | None
    vol_ratio: float | None
    spread: float | None
    is_illiquid: bool
    asset_tag: str = "uncurated"
    child_markets: tuple[ChildMarket, ...] = field(default_factory=tuple)

    @property
    def polymarket_url(self) -> str:
        return POLYMARKET_EVENT_URL.format(slug=self.event_slug)


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def _pp_signed(delta: float | None) -> str:
    if delta is None:
        return "n/a"
    pp = delta * 100.0
    return f"{pp:+.1f}pp"


def _pct(p: float | None) -> str:
    if p is None:
        return "n/a"
    return f"{p * 100:.1f}%"


def _arrow(delta: float | None) -> str:
    if delta is None or abs(delta) < 1e-6:
        return "&rarr;"
    return "&uarr;" if delta > 0 else "&darr;"


def _vol_fmt(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"${v:,.0f}"


def _modal_flip_target(alert: PolywatchAlert) -> str | None:
    """For MODAL_FLIP alerts, return the condition_id of the new leader.

    The new leader is the current modal child (is_modal=True). Returns None
    when the alert isn't MODAL_FLIP or when children aren't populated.
    """
    if "MODAL_FLIP" not in alert.alert_classes:
        return None
    for c in alert.child_markets:
        if c.is_modal:
            return c.condition_id
    return None


def _max_abs_child_delta(alert: PolywatchAlert) -> float:
    """Largest |delta| among children. Falls back to event delta when empty."""
    deltas = [abs(c.delta) for c in alert.child_markets if c.delta is not None]
    if deltas:
        return max(deltas)
    return abs(alert.delta or 0.0)


def _prepare_child_rows(alert: PolywatchAlert) -> tuple[list[dict[str, Any]], int]:
    """Build the per-event children table rows for the template.

    Sort by |delta| desc, cap at MAX_CHILDREN_PER_EVENT but always retain
    the modal row and (when present) the new-leader row. Returns
    (rows, n_truncated).
    """
    if not alert.child_markets:
        return ([], 0)

    new_leader_cid = _modal_flip_target(alert)

    sortable = list(alert.child_markets)
    # Stable sort by |delta| desc (None deltas — new children — at the end).
    sortable.sort(
        key=lambda c: (-(abs(c.delta) if c.delta is not None else -1.0),
                       -(c.yes_price or 0.0)),
    )

    keep: list[ChildMarket] = []
    deferred: list[ChildMarket] = []
    must_keep_cids = {c.condition_id for c in alert.child_markets if c.is_modal}
    if new_leader_cid:
        must_keep_cids.add(new_leader_cid)

    for c in sortable:
        if len(keep) < MAX_CHILDREN_PER_EVENT or c.condition_id in must_keep_cids:
            keep.append(c)
        else:
            deferred.append(c)
    # If we exceeded the cap because we had to keep modal/new-leader, drop the
    # weakest non-must rows back into deferred to honour the cap.
    if len(keep) > MAX_CHILDREN_PER_EVENT:
        # Walk from the tail (smallest |delta|) and demote non-must rows.
        tail_idx = len(keep) - 1
        while len(keep) > MAX_CHILDREN_PER_EVENT and tail_idx >= 0:
            c = keep[tail_idx]
            if c.condition_id not in must_keep_cids:
                deferred.append(keep.pop(tail_idx))
            tail_idx -= 1

    rows: list[dict[str, Any]] = []
    for c in keep:
        rows.append({
            "condition_id": c.condition_id,
            "question": c.question,
            "yes_pct": _pct(c.yes_price),
            "prior_yes_pct": _pct(c.prior_yes) if c.prior_yes is not None else None,
            "delta_pp": _pp_signed(c.delta) if c.delta is not None else None,
            "delta_value": c.delta,
            "arrow": _arrow(c.delta) if c.delta is not None else "&rarr;",
            "vol_24h_fmt": _vol_fmt(c.vol_24h),
            "spread_pct": _pct(c.spread),
            "is_modal": c.is_modal,
            "was_modal": c.was_modal,
            "is_resolved": c.is_resolved,
            "is_new": c.prior_yes is None,
            "is_new_leader": (new_leader_cid is not None
                              and c.condition_id == new_leader_cid),
        })
    return (rows, len(deferred))


def _alert_to_ctx(alert: PolywatchAlert) -> dict[str, Any]:
    child_rows, n_truncated = _prepare_child_rows(alert)
    primary_class = alert.alert_classes[0] if alert.alert_classes else ""

    badges: list[dict[str, str]] = []
    badge_colours = {
        "SPIKE":      "#e74c3c",
        "MODAL_FLIP": "#e74c3c",
        "DRIFT":      "#e67e22",
        "VOL_BURST":  "#8e44ad",
    }
    for cls in ALERT_CLASS_ORDER:
        if cls in alert.alert_classes:
            badges.append({"class": cls, "colour": badge_colours[cls]})
    if alert.is_illiquid:
        badges.append({"class": "ILLIQUID", "colour": "#7f8c8d"})

    return {
        "event_id": alert.event_id,
        "event_slug": alert.event_slug,
        "event_title": alert.event_title,
        "polymarket_url": alert.polymarket_url,
        "alert_classes": list(alert.alert_classes),
        "primary_class": primary_class,
        "badges": badges,
        "modal_question": alert.modal_question,
        "modal_yes_pct": _pct(alert.modal_yes),
        "prior_modal_yes_pct": _pct(alert.prior_modal_yes),
        "delta_pp": _pp_signed(alert.delta),
        "delta_lookback_pp": _pp_signed(alert.delta_lookback),
        "vol_24h_fmt": _vol_fmt(alert.vol_24h),
        "vol_ratio_fmt": (f"{alert.vol_ratio:.1f}x"
                          if alert.vol_ratio is not None else None),
        "vol_ratio": alert.vol_ratio,
        "is_illiquid": alert.is_illiquid,
        "asset_tag": alert.asset_tag,
        "asset_label": ASSET_TAG_LABELS.get(alert.asset_tag, alert.asset_tag),
        "child_rows": child_rows,
        "n_children_truncated": n_truncated,
        "has_children": bool(child_rows),
    }


def _ordered_asset_groups(alerts: list[PolywatchAlert]) -> list[dict[str, Any]]:
    """Group alerts by asset_tag in canonical display order, sort events
    within each group by max(|child.delta|) desc, cap uncurated bucket."""
    by_tag: dict[str, list[PolywatchAlert]] = {}
    for a in alerts:
        by_tag.setdefault(a.asset_tag, []).append(a)
    known = [t for t in ASSET_TAG_ORDER if t in by_tag]
    extras = sorted(t for t in by_tag if t not in ASSET_TAG_ORDER)

    groups: list[dict[str, Any]] = []
    for tag in known + extras:
        bucket = by_tag[tag]
        bucket.sort(key=_max_abs_child_delta, reverse=True)

        n_total = len(bucket)
        n_suppressed = 0
        if tag == "uncurated" and n_total > MAX_UNCURATED_PER_EMAIL:
            n_suppressed = n_total - MAX_UNCURATED_PER_EMAIL
            bucket = bucket[:MAX_UNCURATED_PER_EMAIL]

        groups.append({
            "asset_tag": tag,
            "asset_label": ASSET_TAG_LABELS.get(tag, tag),
            "count": n_total,
            "n_rendered": len(bucket),
            "n_suppressed": n_suppressed,
            "events": [_alert_to_ctx(a) for a in bucket],
        })
    return groups


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

class PolywatchAlertFormatter:
    """Formats the Polymarket move-detection alert email."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("polywatch_alert.html")

    def format_subject(
        self,
        alerts: Iterable[PolywatchAlert] | None = None,
        **kwargs: Any,
    ) -> str:
        alerts = list(alerts or [])
        if not alerts:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return f"[Polywatch] No moves detected | {today}"

        counts: dict[str, int] = {cls: 0 for cls in ALERT_CLASS_ORDER}
        for a in alerts:
            for cls in a.alert_classes:
                counts[cls] = counts.get(cls, 0) + 1
        parts = [f"{counts[c]} {c}" for c in ALERT_CLASS_ORDER if counts.get(c, 0) > 0]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"[Polywatch] {len(alerts)} event(s) moving | {', '.join(parts)} | {today}"

    def format_body(
        self,
        alerts: Iterable[PolywatchAlert] | None = None,
        thresholds: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        alerts = list(alerts or [])
        thresholds = thresholds or {}

        now_utc = datetime.now(timezone.utc)
        run_time_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        run_time_sgt = now_utc.astimezone(_SGT).strftime("%H:%M:%S SGT")

        counts: dict[str, int] = {cls: 0 for cls in ALERT_CLASS_ORDER}
        for a in alerts:
            for cls in a.alert_classes:
                counts[cls] = counts.get(cls, 0) + 1

        asset_groups = _ordered_asset_groups(alerts)
        has_critical = counts.get("SPIKE", 0) > 0 or counts.get("MODAL_FLIP", 0) > 0

        ctx = {
            "n_total": len(alerts),
            "n_spike": counts.get("SPIKE", 0),
            "n_modal_flip": counts.get("MODAL_FLIP", 0),
            "n_drift": counts.get("DRIFT", 0),
            "n_vol_burst": counts.get("VOL_BURST", 0),
            "has_critical": has_critical,
            "asset_groups": asset_groups,
            "run_time_utc": run_time_utc,
            "run_time_sgt": run_time_sgt,
            "thresholds": thresholds,
        }
        return self._template.render(**ctx)
