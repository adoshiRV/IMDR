"""India fresh-food inflation nowcaster — P1: weekly median feed.

Commodity-filtered OGD Agmarknet pull (FOCUS vegetables / fruits / spices).
For each date in a trailing window (default last 10 calendar days), fetches
all mandi price rows for FOCUS commodities, applies hygiene bands, then
aggregates to a weekly (ISO-week) national median per commodity.

Trailing-window daily-fire design: the run fires every day and covers the
last 10 calendar days. Because OGD data lags 1-2 days, the most recent 1-2
dates are often empty — those are skipped without aborting the window. The
MERGE on the DB PK makes every run idempotent; a re-run on the same day
upserts identical values without duplicating rows.

P1 delivers: weekly median + n_markets confidence indicator per commodity.
Later phases add: MoM/WoW/YoY momentum (P2), CPI-weighted composite nowcast
(P3), regional state-level medians (P4), and arrivals via UPAg (P5).

Spec: docs/admin/research/india_food_nowcast_spec.md
"""
from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from statistics import median

from imdr.domains.econ import india_food_basket as fb
from imdr.domains.econ.ogd_mandi import fetch_date, load_key, make_session
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from imdr.domains.econ.upag import slug
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# Global sane band for v1 — drops ₹0.66/qtl entry errors and implausible highs.
# TODO: replace with per-commodity floor/ceiling table once sufficient history exists.
_PRICE_MIN = Decimal("100")
_PRICE_MAX = Decimal("200000")

# Coverage floor: a (commodity, ISO-week) point is only emitted when at least
# this many distinct markets contributed price quotes.
# Spec §10 says >=3; v1 uses 5 for robustness (intentional divergence).
_MIN_MARKETS = 5

# Sub-group → short prefix used in imdr_code
_SUBGROUP_PREFIX: dict[str, str] = {
    "vegetables": "VEG",
    "fruits": "FRUIT",
    "spices": "SPICE",
}


def _week_monday(iso_year: int, iso_week: int) -> datetime.date:
    """Return the Monday (day 1) of the given ISO year+week."""
    return datetime.date.fromisocalendar(iso_year, iso_week, 1)


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Fetch OGD FOCUS commodities for a trailing window, aggregate to weekly medians.

    Window: default last 10 calendar days ending at `until` (today if None).
    `since` overrides the window start.

    Call-count note: the full-day pull (~22 pages/day) is cheaper than
    per-commodity pulls (~110 calls/day for 55+ FOCUS commodities), so we
    fetch the full day and filter client-side.  Switching to per-commodity
    fetching would INCREASE 429 pressure, not reduce it.
    """
    now = datetime.datetime.now(UTC)
    today = datetime.date.today()

    until_dt = datetime.date.fromisoformat(until) if until else today
    if since:
        since_dt = datetime.date.fromisoformat(since)
    else:
        since_dt = until_dt - datetime.timedelta(days=9)

    focus_names = fb.focus_raw_names()

    # Build the date window.
    window: list[datetime.date] = []
    d = since_dt
    while d <= until_dt:
        window.append(d)
        d += datetime.timedelta(days=1)

    key = load_key()
    session = make_session()

    # (canonical_name, iso_year, iso_week) -> set of (market_key, arrival_date, variety)
    # deduplication keys — ensures identical repeated source rows do not double-count.
    # Weekly median is over distinct (market, day, variety) modal quotes pooled
    # across the ISO week — markets quoting more days contribute more points
    # (intended for a national price read).
    seen_keys: dict[tuple[str, int, int], set[tuple[str, datetime.date, str]]] = defaultdict(set)
    # (canonical_name, iso_year, iso_week) -> list of modal_price Decimal
    price_buckets: dict[tuple[str, int, int], list[Decimal]] = defaultdict(list)
    # (canonical_name, iso_year, iso_week) -> set of distinct markets
    market_buckets: dict[tuple[str, int, int], set[str]] = defaultdict(set)

    rows_total = 0
    rows_dropped_hygiene = 0
    rows_dropped_focus = 0
    days_fetched_ok = 0
    days_fetch_failed = 0
    days_empty = 0
    good_day_dates: set[datetime.date] = set()

    for date in window:
        try:
            rows, pages = fetch_date(session, key, date)
        except Exception as exc:
            # Visually distinct from empty — operator must see coverage loss.
            print(f"  [FETCH-FAIL] {date}: {type(exc).__name__}: {exc}")
            days_fetch_failed += 1
            continue

        focus_rows_this_day = 0
        for row in rows:
            raw_commodity = row["commodity"]

            # Focus filter: keep only FOCUS commodities (by canonical name).
            if raw_commodity not in focus_names:
                rows_dropped_focus += 1
                continue

            canonical_name = fb.canonical(raw_commodity)

            # Hygiene band.
            mp = row["modal_price"]
            if mp is None or mp < _PRICE_MIN or mp > _PRICE_MAX:
                rows_dropped_hygiene += 1
                continue

            iso_cal = date.isocalendar()
            bucket_key = (canonical_name, iso_cal.year, iso_cal.week)
            market_key = row["market"] or f"{row['state']}:{row['district']}"
            variety = row.get("variety") or ""

            # Dedup: (market, arrival_date, variety) — prevents identical repeated
            # source rows from double-counting in the median.
            dedup_key = (market_key, date, variety)
            if dedup_key in seen_keys[bucket_key]:
                continue
            seen_keys[bucket_key].add(dedup_key)

            price_buckets[bucket_key].append(mp)
            market_buckets[bucket_key].add(market_key)
            focus_rows_this_day += 1

        rows_total += len(rows)

        if focus_rows_this_day == 0:
            if not rows:
                days_empty += 1
                print(f"  [EMPTY] {date}: 0 rows from API (data lag)")
            else:
                days_empty += 1
                print(f"  [EMPTY] {date}: {len(rows)} rows fetched, 0 focus rows kept")
        else:
            distinct_markets_today = len({
                row["market"] or f"{row['state']}:{row['district']}"
                for row in rows
                if row["commodity"] in focus_names
            })
            print(
                f"  [OK]    {date}: pages={pages}, "
                f"focus_rows={focus_rows_this_day}, "
                f"markets_today={distinct_markets_today}"
            )
            days_fetched_ok += 1
            good_day_dates.add(date)

    print(
        f"\nWindow {since_dt} → {until_dt} ({len(window)} days): "
        f"{days_fetched_ok} fetched OK, {days_fetch_failed} fetch-failed, "
        f"{days_empty} empty; "
        f"weekly points from {len(good_day_dates)} distinct good days"
    )
    print(
        f"Rows fetched: {rows_total}  "
        f"dropped-non-focus: {rows_dropped_focus}  "
        f"dropped-hygiene: {rows_dropped_hygiene}"
    )

    # Aggregate to (commodity, week) medians.
    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []
    groups_dropped_coverage = 0

    for bucket_key, prices in price_buckets.items():
        canonical_name, iso_year, iso_week = bucket_key
        n_markets = len(market_buckets[bucket_key])

        if n_markets < _MIN_MARKETS:
            groups_dropped_coverage += 1
            print(
                f"  [SKIP coverage] {canonical_name} w{iso_year}-W{iso_week:02d}: "
                f"n_markets={n_markets} < {_MIN_MARKETS}"
            )
            continue

        subgroup = fb.subgroup_of(canonical_name)
        if subgroup is None:
            # Should not happen after focus filter — guards against basket inconsistency.
            print(f"  [BUG] {canonical_name}: passed focus filter but no subgroup — skipping")
            continue
        sub_prefix = _SUBGROUP_PREFIX[subgroup]
        commodity_slug = slug(canonical_name)
        imdr_code = f"INDIA.FOODNOWCAST.{sub_prefix}.{commodity_slug}.MEDIAN_WK.NATL.IN"

        if imdr_code not in indicators:
            # Bucketed under 'other' until a food/agri category exists —
            # same pattern as cga_monthly _FISCAL_CATEGORY.
            indicators[imdr_code] = IndicatorRow(
                imdr_code=imdr_code,
                vendor_name="OGD",
                source_code=f"data.gov.in/OGD/35985678/{canonical_name}",
                display_name=(
                    f"India mandi weekly median price — {canonical_name} "
                    f"({subgroup}, INR/Qtl, all-India)"
                )[:255],
                unit="inr",
                frequency="WEEKLY",
                country_iso="IN",
                category="other",
                is_seasonally_adjusted=False,
                bbg_ticker=None,
            )

        week_monday = _week_monday(iso_year, iso_week)
        week_median = float(median(prices))

        observations.append(ObservationRow(
            imdr_code=imdr_code,
            obs_date=week_monday,
            vintage=0,
            release_date=now,
            value=week_median,
            ingested_at=now,
        ))

    print(
        f"Aggregated: {len(indicators)} commodities, "
        f"{len(observations)} week-points, "
        f"{groups_dropped_coverage} groups dropped (coverage < {_MIN_MARKETS} markets)"
    )
    if observations:
        all_dates = [o.obs_date for o in observations]
        print(f"Date span: {min(all_dates)} → {max(all_dates)}")

    # Sample output for verification.
    for ind in sorted(indicators.values(), key=lambda i: i.imdr_code)[:5]:
        matching = [o for o in observations if o.imdr_code == ind.imdr_code]
        sample_val = matching[-1].value if matching else None
        print(f"  {ind.imdr_code}  latest={sample_val:.1f}" if sample_val else f"  {ind.imdr_code}")

    return list(indicators.values()), observations


def main() -> int:
    return run_main(
        vendor="ogd",
        topic="food_nowcast",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="IN",
        allow_empty=True,
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
