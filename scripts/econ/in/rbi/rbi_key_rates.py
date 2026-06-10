"""RBI DBIE — India Key Rates dashboard snapshot.

Source: ``dbie_getPublicationDataImpala`` on the CIMS_Gateway_DBIE gateway.
Despite the endpoint name, this is *not* a generic publication fetcher —
it always returns the same 9-row "Major Monetary Policy Rates" dashboard
card (verified 2026-06-10 across multiple ``reportId`` values).

Each row carries ``{name, rate, timeDate, ...}`` where ``timeDate`` is the
epoch-ms of the last release / change. Step-function rates (Repo / SDF /
CRR / SLR / Reverse Repo) only change on MPC events; daily quotes (WACR,
Exchange Rate) and monthly releases (CPI / WPI) update on their own cadence.

The fetcher is idempotent — the loader MERGE deduplicates on
``(indicator_id, obs_date, vintage)``, so repeated runs only insert rows
that genuinely changed.

Cell mapping (see docs/admin/econ/india/in_coverage_plan.md):
  4.4 Policy Reaction      — Repo, SDF, Reverse Repo, CRR, SLR
  2.4 CPI Pressure         — CPI Inflation (headline YoY latest)
  2.2 Producer Prices      — WPI Inflation (latest)
  4.3 Financial Conditions — WACR (weighted average call rate, daily)

Indicators (8 emitted; the 9th DBIE row, "Exchange Rate", is ambiguous —
95.6 is not INR/USD, possibly REER or INR/EUR; deferred until classified):
  INDIA.POLICY.REPO_RATE.IN
  INDIA.POLICY.SDF_RATE.IN
  INDIA.POLICY.REVERSE_REPO_RATE.IN
  INDIA.POLICY.CRR.IN
  INDIA.POLICY.SLR.IN
  INDIA.CPI.YOY_LATEST.IN
  INDIA.WPI.YOY_LATEST.IN
  INDIA.RATES.WACR_LATEST.IN
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.rbi_dbie import DBIEClient
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# Map DBIE row "name" -> (imdr_code, display, unit, frequency, category).
# Frequency "EVENT" used for step-function policy rates that only change
# on MPC announcements; "DAILY" / "MONTHLY" for the live quotes.
_MAP: dict[str, tuple[str, str, str, str, str]] = {
    "Policy Repo Rate": (
        "INDIA.POLICY.REPO_RATE.IN",
        "India Policy Repo Rate (RBI MPC, %)",
        "pct", "EVENT", "rates"),
    "Standing Deposit Facility (SDF) Rate": (
        "INDIA.POLICY.SDF_RATE.IN",
        "India Standing Deposit Facility Rate (RBI MPC, %)",
        "pct", "EVENT", "rates"),
    "Reverse Repo Rate": (
        "INDIA.POLICY.REVERSE_REPO_RATE.IN",
        "India Reverse Repo Rate (legacy floor, RBI, %)",
        "pct", "EVENT", "rates"),
    "Cash Reserve Ratio": (
        "INDIA.POLICY.CRR.IN",
        "India Cash Reserve Ratio (RBI, %)",
        "pct", "EVENT", "rates"),
    "Statutory Liquidity Ratio": (
        "INDIA.POLICY.SLR.IN",
        "India Statutory Liquidity Ratio (RBI, %)",
        "pct", "EVENT", "rates"),
    "CPI Inflation": (
        "INDIA.CPI.YOY_LATEST.IN",
        "India CPI Headline YoY — latest published value (RBI DBIE snapshot, %)",
        "pct", "MONTHLY", "cpi"),
    "WPI Inflation": (
        "INDIA.WPI.YOY_LATEST.IN",
        "India WPI Headline YoY — latest published value (RBI DBIE snapshot, %)",
        # `cpi` category here matches the Indonesia BPS PPI convention --
        # `econ.dim_indicator_category` has no `ppi` row, and producer-price
        # indices are filed under `cpi` (price-index family) repo-wide.
        "pct", "MONTHLY", "cpi"),
    "WACR": (
        "INDIA.RATES.WACR_LATEST.IN",
        "India Weighted Average Call Rate — latest daily fixing (RBI, %)",
        "pct", "DAILY", "rates"),
    # "Exchange Rate" — DBIE-side ambiguous (value 95.6 isn't INR/USD;
    # likely REER or INR/EUR). Excluded until source clarifies. TODO.
}


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    # since/until are accepted for CLI compatibility but ignored — this
    # is a snapshot fetcher; the only date available is the row's timeDate.
    now = datetime.datetime.now(UTC)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    with DBIEClient() as client:
        rows = client.publication_data_impala(151)
        print(f"  got {len(rows)} rows from Impala/Key Rates dashboard")
        for row in rows:
            # DBIE responses embed U+00A0 (non-breaking space) inside string
            # values even after html.unescape(). Normalise before lookup.
            name = (row.get("name") or "").replace("\xa0", " ").strip()
            mapping = _MAP.get(name)
            if mapping is None:
                print(f"    skip unmapped: {name!r}")
                continue
            imdr_code, display, unit, freq, cat = mapping
            ts_ms = row.get("timeDate")
            rate = row.get("rate")
            if ts_ms is None or rate is None:
                print(f"    skip null ts/rate: {name!r}")
                continue
            obs_date = datetime.datetime.fromtimestamp(
                ts_ms / 1000, tz=UTC
            ).date()
            indicators.append(IndicatorRow(
                imdr_code=imdr_code, vendor_name="RBI",
                source_code=f"dbie_getPublicationDataImpala/151/{name}",
                display_name=display, unit=unit, frequency=freq,
                country_iso="IN", category=cat,
                is_seasonally_adjusted=False, bbg_ticker=None,
            ))
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=float(rate), ingested_at=now,
            ))
            print(f"    {imdr_code:36s} {rate:>10}  {obs_date}")
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="rbi", topic="key_rates",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="IN",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
