"""India fresh-food inflation nowcaster — P3: month-on-month composite.

Reads the P1 weekly-median series (imdr_code INDIA.FOODNOWCAST.*.MEDIAN_WK.NATL.IN,
stored in econ.fact_indicator) and derives month-on-month % change indicators plus a
CPI-weight-blended perishables composite.

Design:
  - No API fetch: the sole input is fact_indicator rows written by ogd_food_nowcast.py.
  - MTD accrual: current_month = month containing `until` (today by default).
    current_level = mean of all ISO-week Monday obs_dates within that calendar month;
    prior_level = mean of all complete ISO-week Monday obs_dates within the prior
    calendar month.  Because the run fires daily and the underlying series is updated
    daily via P1, the MoM nowcast is always MTD-current.  The MERGE on the PK makes
    every daily re-run idempotent.

Composite methodology:
  - Per-commodity MoM_pct is computed only when BOTH current_month AND prior_month
    have at least one weekly-median point for that commodity.
  - Sub-group composite = MEDIAN of constituent MoM_pct values (robust to outlier
    commodities within the group).  Only Tier A + B commodities enter any composite;
    Tier C commodities get a per-commodity MoM_PCT row but are excluded from the
    composite calculations.
  - Headline composite = CPI-weighted average of the three sub-group composites
    (veg 6.04, fruit 2.89, spice 2.50), renormalised to the sub-groups actually
    present in the current run.

YoY and seasonal-vs-norm metrics require a multi-year backfill (P2) and are
deferred to a later phase.

Spec: docs/admin/research/india_food_nowcast_spec.md §7
"""
from __future__ import annotations

import datetime
from statistics import median as _statistics_median

from sqlalchemy import create_engine, text

from imdr.config.settings import get_settings
from imdr.domains.econ import india_food_basket as fb
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from imdr.domains.econ.upag import slug
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# Sub-group → short prefix used in imdr_code (mirrors P1)
_SUBGROUP_PREFIX: dict[str, str] = {
    "vegetables": "VEG",
    "fruits": "FRUIT",
    "spices": "SPICE",
}

# Build a lookup: canonical_name -> (subgroup, tier) for all FOCUS entries.
_FOCUS_META: dict[str, tuple[str, str]] = {
    name: (sub, tier) for name, sub, tier in fb.FOCUS
}


def _engine():
    """Read engine using ODBC Driver 18 — consistent with in_daily and kr_daily."""
    s = get_settings()
    url = (
        f"mssql+pyodbc://@{s.mssql_host}:{s.mssql_port}/{s.mssql_database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes"
        "&LoginTimeout=60"
    )
    return create_engine(url, pool_pre_ping=True, use_setinputsizes=False)


def _month_start(year: int, month: int) -> datetime.date:
    return datetime.date(year, month, 1)


def _prior_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _parse_imdr_code(imdr_code: str) -> tuple[str, str] | None:
    """Extract (canonical_commodity_slug, subgroup_prefix) from a MEDIAN_WK imdr_code.

    Returns None if the code does not match the P1 pattern.
    Pattern: INDIA.FOODNOWCAST.{SUB}.{SLUG}.MEDIAN_WK.NATL.IN
    """
    parts = imdr_code.split(".")
    # Expect exactly: INDIA FOODNOWCAST {SUB} {SLUG} MEDIAN_WK NATL IN
    if len(parts) != 7:
        return None
    if parts[0] != "INDIA" or parts[1] != "FOODNOWCAST" or parts[4] != "MEDIAN_WK":
        return None
    sub_prefix = parts[2]
    commodity_slug = parts[3]
    return commodity_slug, sub_prefix


def _slug_to_canonical(commodity_slug: str) -> str | None:
    """Reverse-map an upag slug back to the canonical FOCUS name.

    Iterates FOCUS to find the name whose slug matches. The upag.slug()
    function is deterministic and injective within the FOCUS set so this
    reverse lookup is safe.
    """
    for name, _sub, _tier in fb.FOCUS:
        if slug(name) == commodity_slug:
            return name
    return None


def _read_weekly_medians(engine) -> dict[str, list[tuple[datetime.date, float]]]:
    """SELECT all P1 weekly-median obs from econ.fact_indicator.

    Returns {imdr_code: [(obs_date, value), ...]} sorted by obs_date asc.
    Only MEDIAN_WK.NATL.IN series are fetched.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT d.imdr_code, CAST(f.obs_date AS DATE) AS obs_date, f.value
                FROM   econ.fact_indicator f
                JOIN   econ.dim_indicator  d ON d.id = f.indicator_id
                WHERE  d.imdr_code LIKE 'INDIA.FOODNOWCAST.%.MEDIAN_WK.NATL.IN'
                  AND  f.vintage = 0
                ORDER BY d.imdr_code, f.obs_date
                """
            )
        ).all()
    series: dict[str, list[tuple[datetime.date, float]]] = {}
    for r in rows:
        series.setdefault(r.imdr_code, []).append((r.obs_date, float(r.value)))
    return series


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Read P1 weekly-median series and compute per-commodity + composite MoM%.

    `until` pins the current_month (default today). `since` is accepted for
    interface compatibility but is not used — the composite always computes
    for exactly one month pair (current vs prior).
    """
    now = datetime.datetime.now(UTC)
    today = datetime.date.today()
    until_dt = datetime.date.fromisoformat(until) if until else today

    cur_year, cur_month = until_dt.year, until_dt.month
    pri_year, pri_month = _prior_month(cur_year, cur_month)

    cur_label = f"{cur_year}-{cur_month:02d}"
    pri_label = f"{pri_year}-{pri_month:02d}"

    print(f"\nP3 MoM nowcast: current={cur_label}  prior={pri_label}")

    eng = _engine()
    try:
        all_series = _read_weekly_medians(eng)
    finally:
        eng.dispose()

    print(f"Read {len(all_series)} weekly-median series from econ.fact_indicator")

    # Bucket obs_dates into months.
    def _in_month(d: datetime.date, yr: int, mo: int) -> bool:
        return d.year == yr and d.month == mo

    # Per-commodity MoM computation.
    # commodity_mom: { canonical_name: mom_pct }
    commodity_mom: dict[str, float] = {}
    # Per sub-group constituent lists (Tier A+B only) for the composite.
    subgroup_constituents: dict[str, list[float]] = {
        "vegetables": [],
        "fruits": [],
        "spices": [],
    }
    skipped: list[str] = []  # commodities with missing month data

    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []

    # Track MTD week count for logging.
    mtd_weeks_per_commodity: dict[str, int] = {}

    for imdr_code, pts in all_series.items():
        parsed = _parse_imdr_code(imdr_code)
        if parsed is None:
            continue
        commodity_slug, sub_prefix = parsed

        canonical_name = _slug_to_canonical(commodity_slug)
        if canonical_name is None:
            # Cannot reverse-map — skip (should not happen with P1 output)
            print(f"  [WARN] cannot reverse-map slug {commodity_slug!r} — skipping")
            continue

        meta = _FOCUS_META.get(canonical_name)
        if meta is None:
            print(f"  [WARN] {canonical_name}: not in FOCUS meta — skipping")
            continue
        subgroup, tier = meta

        cur_vals = [v for d, v in pts if _in_month(d, cur_year, cur_month)]
        pri_vals = [v for d, v in pts if _in_month(d, pri_year, pri_month)]

        if not cur_vals or not pri_vals:
            reason = (
                "no current-month data" if not cur_vals
                else "no prior-month data"
            )
            print(f"  [SKIP] {canonical_name}: {reason} (tier {tier})")
            skipped.append(canonical_name)
            continue

        cur_level = sum(cur_vals) / len(cur_vals)
        pri_level = sum(pri_vals) / len(pri_vals)
        mom_pct = (cur_level / pri_level - 1) * 100
        commodity_mom[canonical_name] = mom_pct
        mtd_weeks_per_commodity[canonical_name] = len(cur_vals)

        # Emit per-commodity MoM indicator.
        mom_code = f"INDIA.FOODNOWCAST.{sub_prefix}.{commodity_slug}.MOM_PCT.NATL.IN"
        if mom_code not in indicators:
            indicators[mom_code] = IndicatorRow(
                imdr_code=mom_code,
                vendor_name="OGD",
                source_code=f"data.gov.in/OGD/35985678/{canonical_name}/MoM",
                display_name=(
                    f"India fresh-food MoM % — {canonical_name} "
                    f"(mandi weekly-median, MTD vs prior month)"
                )[:255],
                unit="pct",
                frequency="MONTHLY",
                country_iso="IN",
                category="other",
                is_seasonally_adjusted=False,
                bbg_ticker=None,
            )

        observations.append(ObservationRow(
            imdr_code=mom_code,
            obs_date=_month_start(cur_year, cur_month),
            vintage=0,
            release_date=now,
            value=mom_pct,
            ingested_at=now,
        ))

        # Only Tier A + B enter sub-group composite.
        if tier in ("A", "B"):
            subgroup_constituents[subgroup].append(mom_pct)

    # Sub-group composites.
    subgroup_mom: dict[str, float] = {}
    for subgroup, constituents in subgroup_constituents.items():
        if not constituents:
            continue
        sg_mom = float(_statistics_median(constituents))
        subgroup_mom[subgroup] = sg_mom

        sub_prefix = _SUBGROUP_PREFIX[subgroup]
        sg_code = f"INDIA.FOODNOWCAST.{sub_prefix}.COMPOSITE.MOM_PCT.NATL.IN"
        if sg_code not in indicators:
            indicators[sg_code] = IndicatorRow(
                imdr_code=sg_code,
                vendor_name="OGD",
                source_code=f"data.gov.in/OGD/35985678/composite/{subgroup}/MoM",
                display_name=(
                    f"India fresh-food MoM % — {subgroup} sub-composite "
                    f"(median of Tier A/B, mandi-derived)"
                )[:255],
                unit="pct",
                frequency="MONTHLY",
                country_iso="IN",
                category="other",
                is_seasonally_adjusted=False,
                bbg_ticker=None,
            )
        observations.append(ObservationRow(
            imdr_code=sg_code,
            obs_date=_month_start(cur_year, cur_month),
            vintage=0,
            release_date=now,
            value=sg_mom,
            ingested_at=now,
        ))

    # Headline composite: CPI-weighted average of available sub-group medians.
    present_weights = {
        sg: fb.CPI_SUBGROUP_WEIGHT_PCT[sg]
        for sg in subgroup_mom
    }
    if present_weights:
        total_weight = sum(present_weights.values())
        composite_mom = sum(
            subgroup_mom[sg] * w / total_weight
            for sg, w in present_weights.items()
        )

        headline_code = "INDIA.FOODNOWCAST.PERISHABLE.MOM_NOWCAST.NATL.IN"
        if headline_code not in indicators:
            indicators[headline_code] = IndicatorRow(
                imdr_code=headline_code,
                vendor_name="OGD",
                source_code="data.gov.in/OGD/35985678/composite/perishable/MoM",
                display_name=(
                    "India fresh-food (veg+fruit+spice) MoM nowcast % — "
                    "CPI-weighted, mandi-derived"
                )[:255],
                unit="pct",
                frequency="MONTHLY",
                country_iso="IN",
                category="other",
                is_seasonally_adjusted=False,
                bbg_ticker=None,
            )
        observations.append(ObservationRow(
            imdr_code=headline_code,
            obs_date=_month_start(cur_year, cur_month),
            vintage=0,
            release_date=now,
            value=composite_mom,
            ingested_at=now,
        ))

    # Summary report.
    n_computable = len(commodity_mom)
    n_skipped = len(skipped)
    total_mtd_weeks = (
        max(mtd_weeks_per_commodity.values()) if mtd_weeks_per_commodity else 0
    )

    print(
        f"\n--- P3 MoM Summary ---"
        f"\n  Current month : {cur_label}"
        f"\n  Prior month   : {pri_label}"
        f"\n  Commodities with computable MoM : {n_computable}"
        f"\n  Commodities skipped (missing month): {n_skipped}"
        f"\n  MTD (max weeks of current month) : {total_mtd_weeks}"
    )
    for sg in ("vegetables", "fruits", "spices"):
        if sg in subgroup_mom:
            n_c = len(subgroup_constituents[sg])
            print(f"  Sub-group {sg:12s}: {subgroup_mom[sg]:+.3f}%  (n_constituents={n_c})")
        else:
            print(f"  Sub-group {sg:12s}: n/a (no Tier A/B data)")
    if present_weights:
        present_sg_str = "+".join(sorted(present_weights))
        print(
            f"  Headline composite ({present_sg_str}): {composite_mom:+.3f}%"
            f"  (weights renormalised, total_w={total_weight:.2f}%)"
        )
    else:
        print("  Headline composite: n/a (no sub-groups available)")

    if skipped:
        print(f"\n  Skipped commodities ({n_skipped}):")
        for c in sorted(skipped):
            print(f"    {c}")

    return list(indicators.values()), observations


def main() -> int:
    return run_main(
        vendor="ogd",
        topic="food_mom",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="IN",
        allow_empty=True,
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
