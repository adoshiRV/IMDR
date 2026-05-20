"""Polywatch — move-detection runtime over the Polymarket streaming SQLite.

Reads observations written by ``scripts.prediction.polymarket.streaming``
(``C:\\IMDR_LOCAL\\polymarket\\observations.db``), classifies meaningful
move events on each watchlisted Polymarket event, and emits an HTML email
alert via the existing IMDR notifications module.

Runs as its own process; the streaming poller is purely a collector. Polywatch
only reads from ``market_observation`` and writes its own state to two new
tables in the same SQLite file (``alert_state``, ``alert_log``).

Three subcommands:

    detect    one-shot detection (latest snapshot vs prior); send email; exit
    loop      long-running daemon; runs detect every --interval seconds
    backfill  replay detection over historical observations; print to stdout

Run:
    python -m scripts.prediction.polymarket.polywatch detect
    python -m scripts.prediction.polymarket.polywatch loop --interval 900
    python -m scripts.prediction.polymarket.polywatch backfill --since 2026-04-26

Replay note: emails are point-in-time renders. ``alert_log`` is the audit
record but stores only modal-market data. Sub-market breakdowns are recomputed
on the fly from ``market_observation`` at email-send time, so replaying alerts
older than the streaming retention window (30 days) loses the children table.
"""
from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

from scripts.prediction.polymarket.watchlist import (
    DEFAULT_ASSET_TAG,
    WATCHLIST_FILE,
    asset_tag_map,
    load_watchlist,
)

POLY_DIR = Path(r"C:\IMDR_LOCAL\polymarket")
DB_FILE = POLY_DIR / "observations.db"
LOG_DIR = POLY_DIR / "logs"

# Display order for asset buckets in the email (curated first, discovery last).
# Tags not listed here render after these in alphabetical order.
ASSET_TAG_ORDER = (
    "oil_mena",
    "fx_safehaven_eur",
    "equity_il_mena",
    "equity_china_taiwan",
    "us_data",
    "us_fed",
    "g10_cb",
    "asia_cb",
    "global_macro",
    "tariffs_trade",
    "emea_em_cb",
    "asia_pol",
    "political_us",
    DEFAULT_ASSET_TAG,
)

DEFAULT_INTERVAL_SEC = 900
INTERVAL_MIN_SEC = 60
INTERVAL_MAX_SEC = 1800
HEARTBEAT_EVERY_N = 12

# Default move thresholds (overridable via CLI flags).
DEFAULT_SPIKE_THRESHOLD = 0.10        # |Δ modal_yes| vs prior snapshot
DEFAULT_DRIFT_THRESHOLD = 0.25        # cumulative |Δ modal_yes| over lookback (raised
                                      # 0.15→0.25 on 2026-05-01: DRIFT was too noisy
                                      # after volume floor was removed for discovery)
DEFAULT_DRIFT_LOOKBACK_HOURS = 6
DEFAULT_DRIFT_MIN_VOL_24H = 10_000.0  # DRIFT class only fires for liquid markets;
                                      # thinly-traded markets drift on noise alone
DEFAULT_VOL_BURST_RATIO = 5.0         # 24h vol / 7d avg 24h vol
DEFAULT_ILLIQUID_SPREAD = 0.30        # absolute hard cap: spread > this is always illiquid
DEFAULT_ILLIQUID_REL_SPREAD = 0.50    # relative cap: spread / max(p, 1-p, 0.05) > this is illiquid
DEFAULT_ILLIQUID_OVERRIDE_DELTA = 0.30  # if |Δ| or |Δ_lookback| ≥ this, emit despite ILLIQUID
DEFAULT_COOLDOWN_MINUTES = 30
DEFAULT_REARM_DELTA = 0.05            # min further |Δ| to re-alert within cooldown
DEFAULT_RESOLVED_BAND = 0.03          # suppress when modal_yes within this of 0 or 1
DEFAULT_MODAL_FLIP_MIN_DELTA = 0.02   # min |Δ modal_yes| for a MODAL_FLIP to fire

ALERT_CLASSES = ("SPIKE", "MODAL_FLIP", "DRIFT", "VOL_BURST")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger("polywatch")


def _setup_logging() -> None:
    """Configure stdout + per-process file logging.

    File: ``C:\\IMDR_LOCAL\\polymarket\\logs\\polywatch_<UTC-date>_pid<PID>.log``.
    A fresh file per startup avoids the multi-process rename race that
    TimedRotatingFileHandler hits when more than one polywatch process is
    accidentally running. Cleanup of old files belongs to the streaming
    cleanup command (or a separate retention sweep).

    Idempotent — safe to call multiple times.
    """
    if log.handlers:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(sh)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = LOG_DIR / f"polywatch_{started}_pid{os.getpid()}.log"
    fh = logging.FileHandler(filename=str(log_path), encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    log.propagate = False
    log.info("logging initialized — file=%s", log_path)

DDL = """
CREATE TABLE IF NOT EXISTS alert_state (
    event_id              INTEGER PRIMARY KEY,
    last_alert_ts         TEXT,
    last_alert_modal_yes  REAL,
    last_alert_class      TEXT
);

CREATE TABLE IF NOT EXISTS alert_log (
    alert_ts        TEXT,
    event_id        INTEGER,
    event_slug      TEXT,
    event_title     TEXT,
    alert_class     TEXT,
    modal_yes       REAL,
    prior_modal_yes REAL,
    delta           REAL,
    volume_24h      REAL,
    vol_ratio       REAL,
    is_illiquid     INTEGER NOT NULL DEFAULT 0,
    suppressed      TEXT,
    PRIMARY KEY (alert_ts, event_id, alert_class)
);
CREATE INDEX IF NOT EXISTS idx_alert_log_event_ts ON alert_log (event_id, alert_ts);
CREATE INDEX IF NOT EXISTS idx_alert_log_ts ON alert_log (alert_ts);
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Thresholds:
    spike: float = DEFAULT_SPIKE_THRESHOLD
    drift: float = DEFAULT_DRIFT_THRESHOLD
    drift_lookback_hours: int = DEFAULT_DRIFT_LOOKBACK_HOURS
    drift_min_vol_24h: float = DEFAULT_DRIFT_MIN_VOL_24H
    vol_burst_ratio: float = DEFAULT_VOL_BURST_RATIO
    illiquid_spread: float = DEFAULT_ILLIQUID_SPREAD
    illiquid_rel_spread: float = DEFAULT_ILLIQUID_REL_SPREAD
    illiquid_override_delta: float = DEFAULT_ILLIQUID_OVERRIDE_DELTA
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES
    rearm_delta: float = DEFAULT_REARM_DELTA
    resolved_band: float = DEFAULT_RESOLVED_BAND
    modal_flip_min_delta: float = DEFAULT_MODAL_FLIP_MIN_DELTA

    def to_template_dict(self) -> dict:
        return {
            "spike": self.spike,
            "drift": self.drift,
            "drift_lookback_hours": self.drift_lookback_hours,
            "drift_min_vol_24h": self.drift_min_vol_24h,
            "vol_burst_ratio": self.vol_burst_ratio,
            "illiquid_spread": self.illiquid_spread,
            "illiquid_rel_spread": self.illiquid_rel_spread,
            "illiquid_override_delta": self.illiquid_override_delta,
            "cooldown_minutes": self.cooldown_minutes,
            "rearm_delta": self.rearm_delta,
            "resolved_band": self.resolved_band,
            "modal_flip_min_delta": self.modal_flip_min_delta,
        }


@dataclass(frozen=True)
class EventSnapshot:
    """Aggregated event view at a single snapshot_ts."""

    event_id: int
    event_slug: str | None
    event_title: str | None
    snapshot_ts: str
    modal_condition_id: str | None
    modal_question: str | None
    modal_yes: float | None
    modal_spread: float | None
    modal_volume_24h: float | None


@dataclass(frozen=True)
class ChildRow:
    """One sub-market row for the email's per-event breakdown table.

    All children of an event at a snapshot, with per-child deltas computed
    against the prior snapshot. is_modal/was_modal mark current/prior leaders;
    used for highlighting and the NEW LEADER pill on MODAL_FLIP.
    """

    condition_id: str
    question: str
    yes_price: float | None
    prior_yes: float | None
    delta: float | None
    vol_24h: float | None
    spread: float | None
    is_modal: bool
    was_modal: bool
    is_resolved: bool


# ---------------------------------------------------------------------------
# DB / setup helpers
# ---------------------------------------------------------------------------

def open_db(db_path: Path | str = DB_FILE) -> sqlite3.Connection:
    """Open the polymarket SQLite DB; ensure alert tables exist.

    Note: This module assumes the streaming.py DDL has already created
    ``market_observation``. Polywatch only adds the two alert tables.

    WAL journal mode + 2s busy_timeout: streaming.py and polywatch.py both
    hold long-lived connections to this file. Without WAL, a writer in one
    process locks out the other and surfaces as ``OperationalError: database
    is locked``.
    """
    conn = sqlite3.connect(str(db_path), timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(DDL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Snapshot extraction
# ---------------------------------------------------------------------------

def list_snapshot_ts(conn: sqlite3.Connection, *, since: str | None = None) -> list[str]:
    """Distinct snapshot timestamps in chronological order."""
    if since:
        rows = conn.execute(
            "SELECT DISTINCT snapshot_ts FROM market_observation "
            "WHERE snapshot_ts >= ? ORDER BY snapshot_ts ASC",
            [since],
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT snapshot_ts FROM market_observation "
            "ORDER BY snapshot_ts ASC"
        ).fetchall()
    return [r[0] for r in rows]


def event_snapshot_at(conn: sqlite3.Connection, snapshot_ts: str) -> dict[int, EventSnapshot]:
    """Per event_id, pick the modal market (highest yes_price) at snapshot_ts.

    Returns: event_id → EventSnapshot.
    """
    rows = conn.execute(
        """
        SELECT event_id, event_slug, event_title,
               condition_id, question, yes_price, spread, volume_24h
        FROM market_observation
        WHERE snapshot_ts = ?
        """,
        [snapshot_ts],
    ).fetchall()

    by_event: dict[int, EventSnapshot] = {}
    for r in rows:
        eid = r["event_id"]
        if eid is None:
            continue
        existing = by_event.get(eid)
        new_yes = r["yes_price"]
        cur_yes = existing.modal_yes if existing else None
        if new_yes is None:
            continue
        if cur_yes is None or new_yes > cur_yes:
            by_event[eid] = EventSnapshot(
                event_id=eid,
                event_slug=r["event_slug"],
                event_title=r["event_title"],
                snapshot_ts=snapshot_ts,
                modal_condition_id=r["condition_id"],
                modal_question=r["question"],
                modal_yes=new_yes,
                modal_spread=r["spread"],
                modal_volume_24h=r["volume_24h"],
            )
    return by_event


def event_children_raw(conn: sqlite3.Connection, event_id: int,
                       snapshot_ts: str) -> list[sqlite3.Row]:
    """All market_observation rows for (event_id, snapshot_ts), ordered
    by yes_price desc. Helper for building the per-event children table."""
    return conn.execute(
        """
        SELECT condition_id, question, yes_price, spread, volume_24h
        FROM market_observation
        WHERE event_id = ? AND snapshot_ts = ?
        ORDER BY yes_price DESC
        """,
        [event_id, snapshot_ts],
    ).fetchall()


def event_children_at(
    conn: sqlite3.Connection,
    event_id: int,
    snapshot_ts: str,
    *,
    prior_snapshot_ts: str | None,
    modal_condition_id: str | None,
    prior_modal_condition_id: str | None,
    resolved_band: float,
) -> list[ChildRow]:
    """Build the per-event children list for the email.

    - Fetches all sub-markets at snapshot_ts.
    - For each, looks up the same condition_id at prior_snapshot_ts (if any)
      to compute per-child delta (None when the child didn't exist prior).
    - Marks is_modal / was_modal / is_resolved.
    """
    rows = event_children_raw(conn, event_id, snapshot_ts)
    if not rows:
        return []

    prior_by_cid: dict[str, float] = {}
    if prior_snapshot_ts:
        for pr in event_children_raw(conn, event_id, prior_snapshot_ts):
            yp = pr["yes_price"]
            if pr["condition_id"] and yp is not None:
                prior_by_cid[pr["condition_id"]] = float(yp)

    out: list[ChildRow] = []
    for r in rows:
        cid = r["condition_id"]
        yp = r["yes_price"]
        prior = prior_by_cid.get(cid)
        delta = (float(yp) - prior) if (yp is not None and prior is not None) else None
        is_resolved = bool(
            yp is not None
            and (float(yp) >= 1.0 - resolved_band or float(yp) <= resolved_band)
        )
        out.append(ChildRow(
            condition_id=cid,
            question=r["question"] or "",
            yes_price=float(yp) if yp is not None else None,
            prior_yes=prior,
            delta=delta,
            vol_24h=float(r["volume_24h"]) if r["volume_24h"] is not None else None,
            spread=float(r["spread"]) if r["spread"] is not None else None,
            is_modal=(modal_condition_id is not None and cid == modal_condition_id),
            was_modal=(prior_modal_condition_id is not None
                       and cid == prior_modal_condition_id),
            is_resolved=is_resolved,
        ))
    return out


def find_anchor_snapshot(conn: sqlite3.Connection, event_id: int,
                         not_after_ts: str, lookback_hours: int) -> EventSnapshot | None:
    """Find the latest snapshot for event_id at or before
    (not_after_ts - lookback_hours), used as the drift baseline."""
    not_after_dt = _parse_ts(not_after_ts)
    if not_after_dt is None:
        return None
    target = not_after_dt - timedelta(hours=lookback_hours)
    target_iso = target.isoformat(timespec="microseconds")
    row = conn.execute(
        """
        SELECT snapshot_ts FROM market_observation
        WHERE event_id = ? AND snapshot_ts <= ?
        ORDER BY snapshot_ts DESC LIMIT 1
        """,
        [event_id, target_iso],
    ).fetchone()
    if row is None:
        return None
    snap = event_snapshot_at(conn, row[0])
    return snap.get(event_id)


def vol_baseline_24h(conn: sqlite3.Connection, condition_id: str,
                     not_after_ts: str, days: int = 7) -> float | None:
    """Median of distinct daily volume_24h values for the modal market over
    the trailing ``days``. Median rather than mean to avoid letting a single
    burst day inflate the baseline.
    """
    not_after_dt = _parse_ts(not_after_ts)
    if not_after_dt is None:
        return None
    start = (not_after_dt - timedelta(days=days)).isoformat(timespec="microseconds")
    rows = conn.execute(
        """
        SELECT volume_24h FROM market_observation
        WHERE condition_id = ?
          AND snapshot_ts BETWEEN ? AND ?
          AND volume_24h IS NOT NULL
        """,
        [condition_id, start, not_after_ts],
    ).fetchall()
    vals = sorted(float(r[0]) for r in rows if r[0] is not None and float(r[0]) > 0)
    if not vals:
        return None
    n = len(vals)
    if n % 2 == 1:
        return vals[n // 2]
    return 0.5 * (vals[n // 2 - 1] + vals[n // 2])


def _parse_ts(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        s = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
        return datetime.fromisoformat(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Core detector
# ---------------------------------------------------------------------------

@dataclass
class DetectionResult:
    event_id: int
    event_slug: str
    event_title: str
    modal_question: str
    alert_classes: list[str]
    modal_yes: float
    prior_modal_yes: float | None
    delta: float                 # modal_yes - prior_modal_yes (snapshot-over-snapshot)
    delta_lookback: float | None  # modal_yes - anchor_modal_yes (rolling window)
    vol_24h: float | None
    vol_ratio: float | None
    spread: float | None
    is_illiquid: bool
    suppressed_reason: str | None  # e.g. "ILLIQUID", "COOLDOWN", or None
    snapshot_ts: str
    asset_tag: str = DEFAULT_ASSET_TAG
    child_markets: tuple[ChildRow, ...] = ()  # populated by detect_at; default empty preserves test fixtures


def detect_at(
    conn: sqlite3.Connection,
    snapshot_ts: str,
    *,
    thresholds: Thresholds,
    update_state: bool,
) -> list[DetectionResult]:
    """Run detection for all events with observations at ``snapshot_ts``.

    If ``update_state`` is True, write to ``alert_state`` and ``alert_log``.
    For backfill we usually pass False; for live detect/loop, True.
    """
    snaps = event_snapshot_at(conn, snapshot_ts)
    if not snaps:
        return []

    asset_tags = asset_tag_map(load_watchlist())

    # Find prior snapshot per event (latest ts strictly before snapshot_ts).
    # One query per event keeps this simple and the watchlist is small (~30).
    prior_snaps: dict[int, EventSnapshot] = {}
    prior_ts_by_event: dict[int, str] = {}
    for eid in snaps:
        row = conn.execute(
            """
            SELECT snapshot_ts FROM market_observation
            WHERE event_id = ? AND snapshot_ts < ?
            ORDER BY snapshot_ts DESC LIMIT 1
            """,
            [eid, snapshot_ts],
        ).fetchone()
        if row is None:
            continue
        prior_ts_by_event[eid] = row[0]
        prev = event_snapshot_at(conn, row[0])
        if eid in prev:
            prior_snaps[eid] = prev[eid]

    # Existing alert state (per event_id).
    state_rows = conn.execute("SELECT * FROM alert_state").fetchall()
    state = {r["event_id"]: r for r in state_rows}

    now_dt = _parse_ts(snapshot_ts) or datetime.now(timezone.utc)

    results: list[DetectionResult] = []
    for eid, cur in snaps.items():
        prev = prior_snaps.get(eid)
        if cur.modal_yes is None:
            continue

        delta = (cur.modal_yes - prev.modal_yes) if (prev and prev.modal_yes is not None) else 0.0

        anchor = find_anchor_snapshot(
            conn, eid, snapshot_ts, thresholds.drift_lookback_hours
        )
        delta_lookback: float | None = None
        if anchor and anchor.modal_yes is not None:
            delta_lookback = cur.modal_yes - anchor.modal_yes

        vol_baseline: float | None = None
        if cur.modal_condition_id:
            vol_baseline = vol_baseline_24h(
                conn, cur.modal_condition_id, snapshot_ts, days=7
            )
        vol_ratio: float | None = None
        if cur.modal_volume_24h is not None and vol_baseline and vol_baseline > 0:
            vol_ratio = float(cur.modal_volume_24h) / float(vol_baseline)

        # Liquidity classification: tail-binaries naturally have wide *absolute*
        # spreads (a 0.005-priced YES with a 5-cent spread is normal), so use a
        # relative measure scaled by the dominant outcome probability, with an
        # absolute hard cap on top.
        is_illiquid = False
        if cur.modal_spread is not None:
            scale = max(min(cur.modal_yes, 1.0 - cur.modal_yes), 0.05)
            rel_spread = cur.modal_spread / scale
            is_illiquid = (
                cur.modal_spread > thresholds.illiquid_spread
                or rel_spread > thresholds.illiquid_rel_spread
            )

        modal_flip = bool(prev and prev.modal_condition_id
                          and cur.modal_condition_id
                          and prev.modal_condition_id != cur.modal_condition_id
                          and abs(delta) >= thresholds.modal_flip_min_delta)

        classes: list[str] = []
        if modal_flip:
            classes.append("MODAL_FLIP")
        if abs(delta) >= thresholds.spike:
            classes.append("SPIKE")
        if (
            delta_lookback is not None
            and abs(delta_lookback) >= thresholds.drift
            and (cur.modal_volume_24h or 0.0) >= thresholds.drift_min_vol_24h
        ):
            classes.append("DRIFT")
        if vol_ratio is not None and vol_ratio >= thresholds.vol_burst_ratio:
            classes.append("VOL_BURST")

        if not classes:
            continue

        # Suppression: liquidity guard — but a sufficiently large move overrides
        # ILLIQUID. A binary that just blew through 30pp is alert-worthy even
        # if its book temporarily widened.
        suppressed_reason: str | None = None
        if is_illiquid:
            big_move = (
                abs(delta) >= thresholds.illiquid_override_delta
                or (delta_lookback is not None
                    and abs(delta_lookback) >= thresholds.illiquid_override_delta)
            )
            if not big_move:
                suppressed_reason = "ILLIQUID"

        # Suppression: near-resolution. Only suppress when the modal market
        # was ALREADY pinned within `resolved_band` of 0 or 1 at the prior
        # snapshot AND is still pinned now — i.e., the event has been settled
        # for at least one cycle. The first move INTO the resolved band (e.g.
        # 0.35 → 0.99) still fires, since that is the headline news.
        if suppressed_reason is None and prev is not None and prev.modal_yes is not None:
            band = thresholds.resolved_band
            cur_resolved = cur.modal_yes >= (1.0 - band) or cur.modal_yes <= band
            prev_resolved = prev.modal_yes >= (1.0 - band) or prev.modal_yes <= band
            if cur_resolved and prev_resolved:
                suppressed_reason = "RESOLVED"

        # Suppression: cooldown / re-arm.
        if suppressed_reason is None and eid in state:
            st = state[eid]
            last_ts = _parse_ts(st["last_alert_ts"]) if st["last_alert_ts"] else None
            last_yes = st["last_alert_modal_yes"]
            if last_ts is not None:
                age = now_dt - last_ts
                cooldown = timedelta(minutes=thresholds.cooldown_minutes)
                if age < cooldown:
                    further = (
                        abs(cur.modal_yes - last_yes) if last_yes is not None else 0.0
                    )
                    if further < thresholds.rearm_delta:
                        suppressed_reason = "COOLDOWN"

        # Suppression: DRIFT-only alerts. Slow-burn drift is informational, not
        # actionable — keep it logged for backtests but skip the email and skip
        # the alert_state write (so a noisy DRIFT-only stream doesn't lock out a
        # subsequent SPIKE/MODAL_FLIP via cooldown).
        if suppressed_reason is None and classes == ["DRIFT"]:
            suppressed_reason = "DRIFT_ONLY"

        children = event_children_at(
            conn,
            eid,
            snapshot_ts,
            prior_snapshot_ts=prior_ts_by_event.get(eid),
            modal_condition_id=cur.modal_condition_id,
            prior_modal_condition_id=prev.modal_condition_id if prev else None,
            resolved_band=thresholds.resolved_band,
        )

        result = DetectionResult(
            event_id=eid,
            event_slug=cur.event_slug or "",
            event_title=cur.event_title or "",
            modal_question=cur.modal_question or "",
            alert_classes=classes,
            modal_yes=cur.modal_yes,
            prior_modal_yes=prev.modal_yes if prev else None,
            delta=delta,
            delta_lookback=delta_lookback,
            vol_24h=cur.modal_volume_24h,
            vol_ratio=vol_ratio,
            spread=cur.modal_spread,
            is_illiquid=is_illiquid,
            suppressed_reason=suppressed_reason,
            snapshot_ts=snapshot_ts,
            asset_tag=asset_tags.get(cur.event_slug or "", DEFAULT_ASSET_TAG),
            child_markets=tuple(children),
        )
        results.append(result)

        if update_state:
            for cls in classes:
                conn.execute(
                    """INSERT OR REPLACE INTO alert_log
                       (alert_ts, event_id, event_slug, event_title, alert_class,
                        modal_yes, prior_modal_yes, delta, volume_24h, vol_ratio,
                        is_illiquid, suppressed)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [
                        snapshot_ts, eid, cur.event_slug, cur.event_title, cls,
                        cur.modal_yes, prev.modal_yes if prev else None, delta,
                        cur.modal_volume_24h, vol_ratio,
                        1 if is_illiquid else 0, suppressed_reason,
                    ],
                )
            if suppressed_reason is None:
                conn.execute(
                    """INSERT OR REPLACE INTO alert_state
                       (event_id, last_alert_ts, last_alert_modal_yes, last_alert_class)
                       VALUES (?,?,?,?)""",
                    [eid, snapshot_ts, cur.modal_yes, classes[0]],
                )
    if update_state:
        conn.commit()
    return results


def emittable_alerts(results: list[DetectionResult]) -> list[DetectionResult]:
    """Subset of detection results that should be in the email
    (not suppressed by ILLIQUID guard or cooldown)."""
    return [r for r in results if r.suppressed_reason is None]


# ---------------------------------------------------------------------------
# Email send wrapper
# ---------------------------------------------------------------------------

def _summarize_alerts(results: list[DetectionResult]) -> str:
    """One-line per alert summary for log output."""
    parts = []
    for r in sorted(results, key=lambda x: abs(x.delta or 0.0), reverse=True):
        cls = ",".join(r.alert_classes)
        delta_pp = f"{r.delta * 100:+.1f}pp"
        title = (r.event_title or r.event_slug or str(r.event_id))[:60]
        parts.append(
            f"[{r.asset_tag}] {cls}({delta_pp}, yes={r.modal_yes * 100:.1f}%) {title}"
        )
    return " | ".join(parts) if parts else "(none)"


def send_email_for(results: list[DetectionResult], thresholds: Thresholds) -> bool:
    """Build PolywatchAlert objects and send. Returns True if sent."""
    if not results:
        return False
    try:
        # Lazy import — keep test fixtures from depending on imdr/jinja2.
        from imdr.config.settings import get_settings
        from imdr.notifications.email import send_outlook_email
        from imdr.notifications.formatters.polywatch_alert import (
            ChildMarket,
            PolywatchAlert,
            PolywatchAlertFormatter,
        )
    except ImportError:
        log.exception("email_imports_failed")
        return False

    try:
        settings = get_settings()
    except Exception:
        log.exception("email_settings_failed")
        return False

    def _children_to_formatter(rows: tuple[ChildRow, ...]) -> tuple[ChildMarket, ...]:
        return tuple(
            ChildMarket(
                condition_id=c.condition_id,
                question=c.question,
                yes_price=c.yes_price,
                prior_yes=c.prior_yes,
                delta=c.delta,
                vol_24h=c.vol_24h,
                spread=c.spread,
                is_modal=c.is_modal,
                was_modal=c.was_modal,
                is_resolved=c.is_resolved,
            )
            for c in rows
        )

    alerts = [
        PolywatchAlert(
            event_id=r.event_id,
            event_slug=r.event_slug,
            event_title=r.event_title,
            modal_question=r.modal_question,
            alert_classes=tuple(r.alert_classes),
            modal_yes=r.modal_yes,
            prior_modal_yes=r.prior_modal_yes,
            delta=r.delta,
            delta_lookback=r.delta_lookback,
            vol_24h=r.vol_24h,
            vol_ratio=r.vol_ratio,
            spread=r.spread,
            is_illiquid=r.is_illiquid,
            asset_tag=r.asset_tag,
            child_markets=_children_to_formatter(r.child_markets),
        )
        for r in results
    ]
    if not (settings.email_enabled and settings.email_to):
        log.warning(
            "email_disabled — settings.email_enabled=%s email_to=%r; would have sent: %s",
            settings.email_enabled, settings.email_to, _summarize_alerts(results),
        )
        return False

    fmt = PolywatchAlertFormatter()
    has_critical = any(
        ("SPIKE" in r.alert_classes or "MODAL_FLIP" in r.alert_classes)
        for r in results
    )
    subject = fmt.format_subject(alerts=alerts)
    try:
        ok = send_outlook_email(
            to=settings.email_to,
            subject=subject,
            html_body=fmt.format_body(alerts=alerts, thresholds=thresholds.to_template_dict()),
            importance=2 if has_critical else 1,
        )
    except Exception:
        log.exception("email_send_raised — subject=%r alerts=%s",
                      subject, _summarize_alerts(results))
        return False

    if ok:
        log.info(
            "EMAIL SENT — to=%s | subject=%r | alerts=%d | %s",
            settings.email_to, subject, len(results), _summarize_alerts(results),
        )
    else:
        log.error(
            "EMAIL FAILED — to=%s | subject=%r | alerts=%d | %s",
            settings.email_to, subject, len(results), _summarize_alerts(results),
        )
    return ok


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def _format_results_table(results: list[DetectionResult]) -> str:
    if not results:
        return "  (no events triggered)"
    lines = []
    for r in sorted(results, key=lambda x: abs(x.delta), reverse=True):
        cls_str = ",".join(r.alert_classes)
        flag = ""
        if r.suppressed_reason:
            flag = f"  [{r.suppressed_reason}]"
        delta_pp = f"{r.delta * 100:+.1f}pp"
        vol = f"{r.vol_ratio:.1f}x" if r.vol_ratio is not None else "n/a"
        title = (r.event_title or r.event_slug or str(r.event_id))[:60]
        lines.append(
            f"  {cls_str:<24} {delta_pp:>8}  vol×{vol:<5}  "
            f"yes={r.modal_yes * 100:5.1f}%  {title}{flag}"
        )
    return "\n".join(lines)


def cmd_detect(args: argparse.Namespace) -> None:
    _setup_logging()
    thresholds = _thresholds_from_args(args)
    conn = open_db()
    try:
        ts_list = list_snapshot_ts(conn)
        if not ts_list:
            log.info("no snapshots in DB yet — nothing to detect.")
            return
        latest = ts_list[-1]
        results = detect_at(conn, latest, thresholds=thresholds, update_state=True)
        emittable = emittable_alerts(results)
        log.info("detect snapshot=%s triggered=%d emittable=%d",
                 latest, len(results), len(emittable))
        log.info("results:\n%s", _format_results_table(results))
        if args.no_email:
            log.info("--no-email set; skipping send.")
            return
        if emittable:
            send_email_for(emittable, thresholds)
        else:
            log.info("no emittable alerts; no email sent.")
    finally:
        conn.close()


def cmd_loop(args: argparse.Namespace) -> None:
    _setup_logging()
    thresholds = _thresholds_from_args(args)
    interval = max(INTERVAL_MIN_SEC, min(INTERVAL_MAX_SEC, args.interval))
    log.info("loop interval=%ds  db=%s", interval, DB_FILE)
    log.info("thresholds=%s", thresholds)
    log.info("log_dir=%s", LOG_DIR)
    log.info("Ctrl+C to stop.")
    conn = open_db()
    last_processed_ts: str | None = None
    n_cycles = 0
    try:
        while True:
            t0 = time.monotonic()
            try:
                ts_list = list_snapshot_ts(conn)
                if ts_list:
                    latest = ts_list[-1]
                    if latest != last_processed_ts:
                        results = detect_at(
                            conn, latest, thresholds=thresholds, update_state=True
                        )
                        emittable = emittable_alerts(results)
                        log.info(
                            "cycle #%-4d snapshot=%s triggered=%d emittable=%d",
                            n_cycles + 1, latest, len(results), len(emittable),
                        )
                        if results:
                            log.info("triggered_detail: %s", _summarize_alerts(results))
                        if emittable and not args.no_email:
                            send_email_for(emittable, thresholds)
                        elif emittable and args.no_email:
                            log.info("--no-email set; skipping send for %d emittable",
                                     len(emittable))
                        last_processed_ts = latest
                    else:
                        if (n_cycles % HEARTBEAT_EVERY_N) == 0:
                            log.info("heartbeat — no new snapshot since %s", latest)
                else:
                    log.warning("no snapshots in DB yet")
                n_cycles += 1
            except Exception:
                log.error("detect cycle failed:\n%s", traceback.format_exc())
            sleep_for = interval - (time.monotonic() - t0)
            if sleep_for > 0:
                time.sleep(sleep_for)
    except KeyboardInterrupt:
        log.info("stopped after %d cycles.", n_cycles)
    finally:
        conn.close()


def cmd_backfill(args: argparse.Namespace) -> None:
    _setup_logging()
    thresholds = _thresholds_from_args(args)
    conn = open_db()
    try:
        ts_list = list_snapshot_ts(conn, since=args.since)
        if not ts_list:
            print(f"[polywatch] no snapshots since {args.since!r}")
            return
        # Backfill writes alert_log but not alert_state (so the live state machine
        # is undisturbed). Replay-only: we want the *historical* signal, not
        # cooldown-influenced output.
        all_results: list[DetectionResult] = []
        for ts in ts_list:
            results = detect_at(conn, ts, thresholds=thresholds, update_state=False)
            all_results.extend(results)
        print(f"[polywatch] backfill since={args.since}  "
              f"snapshots={len(ts_list)}  triggered={len(all_results)}")
        # Group by class for a one-glance summary.
        from collections import Counter
        class_counts = Counter(c for r in all_results for c in r.alert_classes)
        print("  by class:")
        for cls in ALERT_CLASSES:
            print(f"    {cls:<11} {class_counts.get(cls, 0)}")
        if args.show > 0:
            print(f"  top {args.show} by |Δ|:")
            top = sorted(all_results, key=lambda x: abs(x.delta), reverse=True)[: args.show]
            print(_format_results_table(top))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Argparse plumbing
# ---------------------------------------------------------------------------

def _add_threshold_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--spike-threshold", type=float, default=DEFAULT_SPIKE_THRESHOLD)
    p.add_argument("--drift-threshold", type=float, default=DEFAULT_DRIFT_THRESHOLD)
    p.add_argument("--drift-lookback-hours", type=int, default=DEFAULT_DRIFT_LOOKBACK_HOURS)
    p.add_argument("--vol-burst-ratio", type=float, default=DEFAULT_VOL_BURST_RATIO)
    p.add_argument("--illiquid-spread", type=float, default=DEFAULT_ILLIQUID_SPREAD,
                   help="Absolute spread cap (cents). Above this is always ILLIQUID.")
    p.add_argument("--illiquid-rel-spread", type=float, default=DEFAULT_ILLIQUID_REL_SPREAD,
                   help="Relative spread cap = spread / max(p, 1-p, 0.05).")
    p.add_argument("--illiquid-override-delta", type=float,
                   default=DEFAULT_ILLIQUID_OVERRIDE_DELTA,
                   help="If |Δ| or |Δ_lookback| ≥ this, emit despite ILLIQUID.")
    p.add_argument("--cooldown-minutes", type=int, default=DEFAULT_COOLDOWN_MINUTES)
    p.add_argument("--rearm-delta", type=float, default=DEFAULT_REARM_DELTA)
    p.add_argument("--resolved-band", type=float, default=DEFAULT_RESOLVED_BAND,
                   help="Suppress alerts when modal_yes is within this of 0 or 1")
    p.add_argument("--modal-flip-min-delta", type=float, default=DEFAULT_MODAL_FLIP_MIN_DELTA,
                   help="Min |Δ modal_yes| for a MODAL_FLIP to fire")


def _thresholds_from_args(args: argparse.Namespace) -> Thresholds:
    return Thresholds(
        spike=args.spike_threshold,
        drift=args.drift_threshold,
        drift_lookback_hours=args.drift_lookback_hours,
        vol_burst_ratio=args.vol_burst_ratio,
        illiquid_spread=args.illiquid_spread,
        illiquid_rel_spread=args.illiquid_rel_spread,
        illiquid_override_delta=args.illiquid_override_delta,
        cooldown_minutes=args.cooldown_minutes,
        rearm_delta=args.rearm_delta,
        resolved_band=args.resolved_band,
        modal_flip_min_delta=args.modal_flip_min_delta,
    )


def main() -> None:
    p = argparse.ArgumentParser(prog="polywatch")
    sub = p.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("detect", help="One-shot detect on the latest snapshot")
    _add_threshold_args(pd)
    pd.add_argument("--no-email", action="store_true",
                    help="Don't send email; print results only")

    pl = sub.add_parser("loop", help="Continuous detection daemon")
    _add_threshold_args(pl)
    pl.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SEC,
                    help=f"Seconds between detection cycles (default {DEFAULT_INTERVAL_SEC},"
                         f" clamped to [{INTERVAL_MIN_SEC},{INTERVAL_MAX_SEC}])")
    pl.add_argument("--no-email", action="store_true",
                    help="Don't send email; print results only")

    pb = sub.add_parser("backfill", help="Replay detection over historical snapshots")
    _add_threshold_args(pb)
    pb.add_argument("--since", required=True,
                    help="ISO datetime; replay all snapshots at or after this")
    pb.add_argument("--show", type=int, default=10,
                    help="Show top N triggered by |Δ| (default 10)")

    args = p.parse_args()
    {
        "detect":   cmd_detect,
        "loop":     cmd_loop,
        "backfill": cmd_backfill,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
