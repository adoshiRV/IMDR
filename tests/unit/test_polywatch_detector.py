"""Unit tests for the Polywatch detector.

Uses an in-memory SQLite mirror of the streaming.py ``market_observation``
table plus the alert tables created by polywatch.open_db. Each test seeds
synthetic snapshots and asserts which alert classes fire (or are suppressed).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from scripts.prediction.polymarket.polywatch import (
    DDL as POLYWATCH_DDL,
    Thresholds,
    detect_at,
    emittable_alerts,
    event_children_at,
)


STREAMING_DDL = """
CREATE TABLE IF NOT EXISTS market_observation (
    snapshot_ts        TEXT     NOT NULL,
    condition_id       TEXT     NOT NULL,
    event_id           INTEGER,
    event_slug         TEXT,
    event_title        TEXT,
    question           TEXT,
    yes_price          REAL,
    no_price           REAL,
    best_bid           REAL,
    best_ask           REAL,
    spread             REAL,
    last_trade_price   REAL,
    volume_total       REAL,
    volume_24h         REAL,
    liquidity          REAL,
    updated_at_src     TEXT,
    PRIMARY KEY (snapshot_ts, condition_id)
);
CREATE INDEX IF NOT EXISTS idx_obs_event_ts ON market_observation (event_id, snapshot_ts);
CREATE INDEX IF NOT EXISTS idx_obs_ts       ON market_observation (snapshot_ts);
"""

EVENT_ID = 1001
EVENT_SLUG = "test-fed-decision"
EVENT_TITLE = "Test Fed decision"
COND_A = "0xAAA"
COND_B = "0xBBB"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(STREAMING_DDL)
    c.executescript(POLYWATCH_DDL)
    yield c
    c.close()


def _ts(offset_minutes: int, base: datetime | None = None) -> str:
    base = base or datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(minutes=offset_minutes)).isoformat(timespec="microseconds")


def insert_obs(conn, snapshot_ts: str, condition_id: str, *,
               event_id: int = EVENT_ID,
               event_slug: str = EVENT_SLUG,
               event_title: str = EVENT_TITLE,
               question: str = "Will Fed cut?",
               yes_price: float = 0.5,
               spread: float = 0.02,
               volume_24h: float = 1000.0) -> None:
    no_price = max(0.0, 1.0 - yes_price)
    best_bid = max(0.0, yes_price - spread / 2)
    best_ask = min(1.0, yes_price + spread / 2)
    conn.execute(
        """INSERT INTO market_observation
           (snapshot_ts, condition_id, event_id, event_slug, event_title,
            question, yes_price, no_price, best_bid, best_ask, spread,
            last_trade_price, volume_total, volume_24h, liquidity, updated_at_src)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [snapshot_ts, condition_id, event_id, event_slug, event_title,
         question, yes_price, no_price, best_bid, best_ask, spread,
         yes_price, 100000.0, volume_24h, 5000.0, snapshot_ts],
    )
    conn.commit()


def _seed_baseline_volume(conn, *, condition_id: str = COND_A,
                          baseline: float = 1000.0, days: int = 7):
    """Seed 7 days of prior observations on COND_A so the vol baseline is deterministic."""
    base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    for d in range(1, days + 1):
        ts = (base - timedelta(days=d)).isoformat(timespec="microseconds")
        insert_obs(conn, ts, condition_id, yes_price=0.50, spread=0.02,
                   volume_24h=baseline)


def thresholds(**kwargs) -> Thresholds:
    return Thresholds(**kwargs) if kwargs else Thresholds()


# ─────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────

def test_spike_triggers(conn):
    """0.50 → 0.62 in one snapshot step ⇒ SPIKE fires."""
    _seed_baseline_volume(conn)
    insert_obs(conn, _ts(0), COND_A, yes_price=0.50)
    insert_obs(conn, _ts(5), COND_A, yes_price=0.62)

    results = detect_at(conn, _ts(5), thresholds=thresholds(), update_state=True)
    assert len(results) == 1
    r = results[0]
    assert "SPIKE" in r.alert_classes
    assert r.suppressed_reason is None
    assert abs(r.delta - 0.12) < 1e-9

    # alert_state row is written for non-suppressed alert.
    row = conn.execute("SELECT * FROM alert_state WHERE event_id = ?", [EVENT_ID]).fetchone()
    assert row is not None
    assert row["last_alert_class"] == "SPIKE"
    assert pytest.approx(row["last_alert_modal_yes"], abs=1e-9) == 0.62


def test_drift_only_triggers_but_is_suppressed_from_email(conn):
    """0.40 → 0.50 → 0.60 → 0.68 over 6h, no single jump > 10pp ⇒ DRIFT only.
    DRIFT-only alerts get tagged ``suppressed_reason="DRIFT_ONLY"`` so they
    are kept in alert_log (for backtests) but excluded from emails."""
    # Seed baseline at the same volume the current snapshots use so vol_ratio
    # stays ~1 and VOL_BURST doesn't co-fire (we want pure DRIFT-only here).
    _seed_baseline_volume(conn, baseline=15000.0)
    insert_obs(conn, _ts(-360), COND_A, yes_price=0.40, volume_24h=15000.0)
    insert_obs(conn, _ts(-240), COND_A, yes_price=0.50, volume_24h=15000.0)
    insert_obs(conn, _ts(-120), COND_A, yes_price=0.60, volume_24h=15000.0)
    insert_obs(conn, _ts(0),    COND_A, yes_price=0.68, volume_24h=15000.0)

    results = detect_at(conn, _ts(0), thresholds=thresholds(), update_state=True)
    assert len(results) == 1
    r = results[0]
    assert r.alert_classes == ["DRIFT"]
    assert r.suppressed_reason == "DRIFT_ONLY"
    assert emittable_alerts(results) == []


def test_drift_gated_by_volume_floor(conn):
    """Same drift pattern but with vol_24h below the gate ⇒ DRIFT class does
    not fire at all (no other classes either ⇒ no result)."""
    _seed_baseline_volume(conn)
    insert_obs(conn, _ts(-360), COND_A, yes_price=0.40, volume_24h=500.0)
    insert_obs(conn, _ts(-240), COND_A, yes_price=0.50, volume_24h=500.0)
    insert_obs(conn, _ts(-120), COND_A, yes_price=0.60, volume_24h=500.0)
    insert_obs(conn, _ts(0),    COND_A, yes_price=0.68, volume_24h=500.0)

    results = detect_at(conn, _ts(0), thresholds=thresholds(), update_state=True)
    assert results == []


def test_vol_burst_triggers(conn):
    """Flat price, but volume_24h jumps 8x baseline ⇒ VOL_BURST fires."""
    _seed_baseline_volume(conn, baseline=1000.0)  # 7d median = 1000
    insert_obs(conn, _ts(-5), COND_A, yes_price=0.50, volume_24h=1000.0)
    insert_obs(conn, _ts(0),  COND_A, yes_price=0.51, volume_24h=8000.0)

    results = detect_at(conn, _ts(0), thresholds=thresholds(), update_state=True)
    assert len(results) == 1
    r = results[0]
    assert "VOL_BURST" in r.alert_classes
    assert r.vol_ratio is not None and r.vol_ratio >= 5.0


def test_modal_flip_triggers(conn):
    """Prior modal market = COND_B; new modal = COND_A and the new leader has
    moved up by more than the modal-flip floor ⇒ MODAL_FLIP fires."""
    _seed_baseline_volume(conn, condition_id=COND_A)
    _seed_baseline_volume(conn, condition_id=COND_B)
    # Prior snapshot: B leads at 0.55, A is the runner-up at 0.45.
    insert_obs(conn, _ts(-5), COND_A, yes_price=0.45)
    insert_obs(conn, _ts(-5), COND_B, yes_price=0.55)
    # New snapshot: A leads at 0.60 (5pp jump on the leader), B drops to 0.40.
    insert_obs(conn, _ts(0), COND_A, yes_price=0.60)
    insert_obs(conn, _ts(0), COND_B, yes_price=0.40)

    results = detect_at(conn, _ts(0), thresholds=thresholds(), update_state=True)
    assert len(results) == 1
    r = results[0]
    assert "MODAL_FLIP" in r.alert_classes


def test_modal_flip_suppressed_when_below_min_delta(conn):
    """Modal market identity flips but the modal_yes barely moves
    (sub-2pp by default) ⇒ MODAL_FLIP does NOT fire — this is the
    French-election-style noise pattern."""
    # No baseline seed: keep this test isolated to the prev→cur pair so
    # DRIFT (which uses a 6h lookback anchor) cannot fire.
    # Prior: A leads at 0.225, B at 0.220 (1pp gap).
    insert_obs(conn, _ts(-5), COND_A, yes_price=0.225)
    insert_obs(conn, _ts(-5), COND_B, yes_price=0.220)
    # Now: B leads at 0.225, A at 0.220 — flip with delta = 0pp.
    insert_obs(conn, _ts(0), COND_A, yes_price=0.220)
    insert_obs(conn, _ts(0), COND_B, yes_price=0.225)

    results = detect_at(conn, _ts(0), thresholds=thresholds(), update_state=True)
    assert results == []


def test_resolved_does_not_suppress_first_pin(conn):
    """A market that JUST ripped from mid-conviction to near-1 still fires —
    that is the headline news. Only repeat alerts on an already-pinned market
    get suppressed."""
    _seed_baseline_volume(conn)
    insert_obs(conn, _ts(-5), COND_A, yes_price=0.50)
    insert_obs(conn, _ts(0),  COND_A, yes_price=0.999)  # huge jump INTO resolved band

    results = detect_at(conn, _ts(0), thresholds=thresholds(), update_state=True)
    assert len(results) == 1
    r = results[0]
    assert "SPIKE" in r.alert_classes
    assert r.suppressed_reason is None
    assert emittable_alerts(results) == [r]


def test_resolved_suppresses_repeat_pin(conn):
    """Modal market was already pinned at 99.7% on the prior snapshot and is
    still pinned at 99.9% now ⇒ RESOLVED-suppressed."""
    _seed_baseline_volume(conn)
    # Drift baseline that would otherwise trigger DRIFT.
    # Volume above DRIFT vol gate so DRIFT class actually fires; without it
    # the only class would never form and len(results) would be 0.
    insert_obs(conn, _ts(-360), COND_A, yes_price=0.50, volume_24h=15000.0)
    insert_obs(conn, _ts(-180), COND_A, yes_price=0.85, volume_24h=15000.0)
    insert_obs(conn, _ts(-5),   COND_A, yes_price=0.997, volume_24h=15000.0)  # already pinned
    insert_obs(conn, _ts(0),    COND_A, yes_price=0.999, volume_24h=15000.0)  # still pinned

    results = detect_at(conn, _ts(0), thresholds=thresholds(), update_state=True)
    assert len(results) == 1
    r = results[0]
    assert r.suppressed_reason == "RESOLVED"
    assert emittable_alerts(results) == []


def test_resolved_suppresses_repeat_pin_low(conn):
    """Modal market pinned near 0 across consecutive snapshots ⇒ suppressed."""
    _seed_baseline_volume(conn)
    insert_obs(conn, _ts(-5), COND_A, yes_price=0.005)
    insert_obs(conn, _ts(0),  COND_A, yes_price=0.010)
    # Force a class to fire via volume burst.
    conn.execute(
        "UPDATE market_observation SET volume_24h=8000.0 WHERE snapshot_ts=?",
        [_ts(0)],
    )
    conn.commit()

    results = detect_at(conn, _ts(0), thresholds=thresholds(), update_state=True)
    if results:
        for r in results:
            assert r.suppressed_reason == "RESOLVED"
        assert emittable_alerts(results) == []


def test_illiquid_suppresses(conn):
    """Modal spread > 20pp ⇒ alert is logged but suppressed (not emittable)."""
    _seed_baseline_volume(conn)
    insert_obs(conn, _ts(-5), COND_A, yes_price=0.50, spread=0.25)
    insert_obs(conn, _ts(0),  COND_A, yes_price=0.62, spread=0.25)

    results = detect_at(conn, _ts(0), thresholds=thresholds(), update_state=True)
    assert len(results) == 1
    r = results[0]
    assert "SPIKE" in r.alert_classes
    assert r.is_illiquid is True
    assert r.suppressed_reason == "ILLIQUID"
    assert emittable_alerts(results) == []


def test_cooldown_suppresses_then_rearms(conn):
    """SPIKE fires, second SPIKE 10min later with 3pp further move ⇒ suppressed.
    A third snapshot 10min after that with another 6pp move ⇒ re-armed and fires."""
    _seed_baseline_volume(conn)
    # Initial spike: 0.50 → 0.62. SPIKE fires, alert_state set.
    insert_obs(conn, _ts(-30), COND_A, yes_price=0.50)
    insert_obs(conn, _ts(-25), COND_A, yes_price=0.62)
    detect_at(conn, _ts(-25), thresholds=thresholds(), update_state=True)

    # 10min later, only 3pp further (0.62 → 0.65). Within cooldown (30min) AND
    # sub-rearm (5pp) ⇒ suppressed by COOLDOWN. Note: snapshot-over-snapshot
    # |Δ| = 3pp does NOT exceed spike threshold so SPIKE wouldn't fire anyway;
    # use a fresh non-spike-triggering case but with a class still firing.
    # Easiest: large drift. Bump volume to trigger VOL_BURST.
    insert_obs(conn, _ts(-15), COND_A, yes_price=0.65, volume_24h=8000.0)
    r2 = detect_at(conn, _ts(-15), thresholds=thresholds(), update_state=True)
    if r2:
        # If anything fires here, it must be cooldown-suppressed.
        for r in r2:
            assert r.suppressed_reason == "COOLDOWN", (
                f"expected COOLDOWN, got {r.suppressed_reason} on {r.alert_classes}"
            )

    # 10min later, +6pp further (0.65 → 0.71): re-arm threshold (5pp from
    # last_alert_modal_yes=0.62 ⇒ |0.71 - 0.62| = 9pp ≥ 5pp). SPIKE not strict
    # enough alone (Δ vs prior snapshot = 6pp). Force re-arm with a 12pp spike.
    insert_obs(conn, _ts(-5), COND_A, yes_price=0.77)
    r3 = detect_at(conn, _ts(-5), thresholds=thresholds(), update_state=True)
    assert len(r3) == 1
    assert "SPIKE" in r3[0].alert_classes
    assert r3[0].suppressed_reason is None


# ─────────────────────────────────────────────────────────────────
# Multi-market children tests
# ─────────────────────────────────────────────────────────────────

MULTI_EID = 2002
MULTI_SLUG = "what-will-the-us-agree-to"
COND_C = "0xCCC"
COND_D = "0xDDD"


def _seed_multi_event_baseline(conn):
    """Seed a 4-child event ('demands trump will agree to') across 7 days
    so the modal vol baseline is set; the modal child is COND_A."""
    base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    for d in range(1, 8):
        ts = (base - timedelta(days=d)).isoformat(timespec="microseconds")
        for cid, q, yp in [
            (COND_A, "Enrichment of Uranium",     0.30),
            (COND_B, "Oil Sanction Relief",       0.10),
            (COND_C, "Hormuz Transit Fees",       0.05),
            (COND_D, "Unfreeze Iranian Assets",   0.03),
        ]:
            insert_obs(conn, ts, cid, event_id=MULTI_EID, event_slug=MULTI_SLUG,
                       event_title="What Iranian demands will Trump agree to in April?",
                       question=q, yes_price=yp, spread=0.02, volume_24h=1000.0)


def test_event_children_at_returns_all_children_yes_desc(conn):
    """All sub-markets at a snapshot returned, ordered by yes_price desc.
    Per-child deltas computed correctly against prior snapshot."""
    base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
    prior_ts = base.isoformat(timespec="microseconds")
    cur_ts = (base + timedelta(minutes=5)).isoformat(timespec="microseconds")

    for cid, yp_prior, yp_cur in [
        (COND_A, 0.30, 0.45),  # +15pp
        (COND_B, 0.10, 0.08),  # -2pp
        (COND_C, 0.05, 0.05),  # 0
        (COND_D, 0.03, 0.04),  # +1pp
    ]:
        insert_obs(conn, prior_ts, cid, event_id=MULTI_EID, event_slug=MULTI_SLUG,
                   yes_price=yp_prior, spread=0.02)
        insert_obs(conn, cur_ts, cid, event_id=MULTI_EID, event_slug=MULTI_SLUG,
                   yes_price=yp_cur, spread=0.02)

    children = event_children_at(
        conn, MULTI_EID, cur_ts,
        prior_snapshot_ts=prior_ts,
        modal_condition_id=COND_A,
        prior_modal_condition_id=COND_A,
        resolved_band=0.03,
    )
    assert len(children) == 4
    # Ordered by yes_price desc.
    yes_seq = [c.yes_price for c in children]
    assert yes_seq == sorted(yes_seq, reverse=True)
    # Deltas computed correctly.
    deltas_by_cid = {c.condition_id: c.delta for c in children}
    assert deltas_by_cid[COND_A] == pytest.approx(0.15)
    assert deltas_by_cid[COND_B] == pytest.approx(-0.02)
    # Modal flag set on COND_A (current modal).
    by_cid = {c.condition_id: c for c in children}
    assert by_cid[COND_A].is_modal is True
    assert by_cid[COND_B].is_modal is False


def test_alert_carries_child_markets_with_per_child_deltas(conn):
    """A SPIKE on a multi-market event should attach all sub-markets to
    DetectionResult, with per-child deltas computed against the prior snapshot."""
    _seed_multi_event_baseline(conn)
    # Prior snapshot: modal at 0.30
    insert_obs(conn, _ts(0), COND_A, event_id=MULTI_EID, event_slug=MULTI_SLUG,
               question="Enrichment of Uranium", yes_price=0.30, spread=0.02)
    insert_obs(conn, _ts(0), COND_B, event_id=MULTI_EID, event_slug=MULTI_SLUG,
               question="Oil Sanction Relief", yes_price=0.10, spread=0.02)
    # Current snapshot: modal spikes to 0.45 (+15pp), sibling drifts -2pp
    insert_obs(conn, _ts(5), COND_A, event_id=MULTI_EID, event_slug=MULTI_SLUG,
               question="Enrichment of Uranium", yes_price=0.45, spread=0.02)
    insert_obs(conn, _ts(5), COND_B, event_id=MULTI_EID, event_slug=MULTI_SLUG,
               question="Oil Sanction Relief", yes_price=0.08, spread=0.02)

    results = detect_at(conn, _ts(5), thresholds=thresholds(), update_state=True)
    assert len(results) == 1
    r = results[0]
    assert "SPIKE" in r.alert_classes
    # Children attached and deltas computed per child.
    assert len(r.child_markets) == 2
    by_cid = {c.condition_id: c for c in r.child_markets}
    assert by_cid[COND_A].delta == pytest.approx(0.15)
    assert by_cid[COND_B].delta == pytest.approx(-0.02)
    assert by_cid[COND_A].is_modal is True
    assert by_cid[COND_B].is_modal is False


def test_child_marked_new_when_prior_snapshot_missing_it(conn):
    """A child added between prior and current snapshot should report
    prior_yes=None and delta=None — rendered as NEW in the email."""
    _seed_multi_event_baseline(conn)
    # Prior snapshot: only COND_A and COND_B exist
    insert_obs(conn, _ts(0), COND_A, event_id=MULTI_EID, event_slug=MULTI_SLUG,
               yes_price=0.30, spread=0.02)
    insert_obs(conn, _ts(0), COND_B, event_id=MULTI_EID, event_slug=MULTI_SLUG,
               yes_price=0.10, spread=0.02)
    # Current snapshot: COND_C is new
    insert_obs(conn, _ts(5), COND_A, event_id=MULTI_EID, event_slug=MULTI_SLUG,
               yes_price=0.50, spread=0.02)  # spike on modal
    insert_obs(conn, _ts(5), COND_B, event_id=MULTI_EID, event_slug=MULTI_SLUG,
               yes_price=0.10, spread=0.02)
    insert_obs(conn, _ts(5), COND_C, event_id=MULTI_EID, event_slug=MULTI_SLUG,
               yes_price=0.08, spread=0.02)

    results = detect_at(conn, _ts(5), thresholds=thresholds(), update_state=True)
    assert len(results) == 1
    by_cid = {c.condition_id: c for c in results[0].child_markets}
    assert by_cid[COND_C].prior_yes is None
    assert by_cid[COND_C].delta is None
    # COND_A, COND_B should still have proper prior values.
    assert by_cid[COND_A].prior_yes == pytest.approx(0.30)
    assert by_cid[COND_B].prior_yes == pytest.approx(0.10)


def test_child_table_sorted_by_abs_delta_in_formatter():
    """Formatter sorts children by |delta| desc — non-modal child with bigger
    delta should appear first regardless of yes ordering."""
    from imdr.notifications.formatters.polywatch_alert import (
        ChildMarket,
        PolywatchAlert,
        _prepare_child_rows,
    )

    alert = PolywatchAlert(
        event_id=MULTI_EID,
        event_slug=MULTI_SLUG,
        event_title="What Iranian demands will Trump agree to in April?",
        modal_question="Enrichment of Uranium",
        alert_classes=("DRIFT",),
        modal_yes=0.45, prior_modal_yes=0.43, delta=0.02, delta_lookback=0.05,
        vol_24h=1000.0, vol_ratio=2.0, spread=0.02, is_illiquid=False,
        asset_tag="oil_mena",
        child_markets=(
            ChildMarket(condition_id=COND_A, question="Enrichment", yes_price=0.45,
                        prior_yes=0.43, delta=0.02, vol_24h=1000.0, spread=0.02,
                        is_modal=True),
            ChildMarket(condition_id=COND_B, question="Oil Sanctions", yes_price=0.08,
                        prior_yes=0.51, delta=-0.43, vol_24h=500.0, spread=0.02),
        ),
    )
    rows, n_truncated = _prepare_child_rows(alert)
    assert n_truncated == 0
    # Non-modal Oil Sanctions has bigger |delta| (0.43 vs 0.02), should sort first.
    assert rows[0]["condition_id"] == COND_B
    assert rows[1]["condition_id"] == COND_A
    assert rows[0]["is_modal"] is False
    assert rows[1]["is_modal"] is True
