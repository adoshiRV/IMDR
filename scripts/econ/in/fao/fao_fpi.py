"""FAO Food Price Index — monthly headline + 5 commodity-group indices.

Source: UN FAO at fao.org/worldfoodsituation/foodpricesindex. Single CSV,
no auth, monthly cadence from Jan 1990 (~437 months × 6 series).

Cross-country macro benchmark — placed under `in/` because it serves as
the imported-food inflation reference for India per the cluster map
(cluster 12 commodity shocks). country_iso stays WLD on the indicator
side; the country_code arg only anchors the on-disk parquet path.

Cell mapping for India (see docs/admin/econ/india/in_coverage_plan.md):
  1.2 Imported price  — global food price benchmark
  Cluster 12          — commodity shocks
"""
from __future__ import annotations

import datetime
import io

import httpx
import pandas as pd

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_CSV_URL = (
    "https://www.fao.org/media/docs/worldfoodsituationlibraries/"
    "default-document-library/food_price_indices_data.csv"
    "?sfvrsn=523ebd2a_80&download=true"
)

_SERIES: dict[str, tuple[str, str]] = {
    "Food Price Index": ("HEADLINE", "FAO Food Price Index — Headline (2014-2016=100)"),
    "Meat":             ("MEAT",     "FAO Food Price Index — Meat"),
    "Dairy":            ("DAIRY",    "FAO Food Price Index — Dairy"),
    "Cereals":          ("CEREALS",  "FAO Food Price Index — Cereals"),
    "Oils":             ("OILS",     "FAO Food Price Index — Oils & Fats"),
    "Sugar":            ("SUGAR",    "FAO Food Price Index — Sugar"),
}


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    r = httpx.get(_CSV_URL, timeout=60, follow_redirects=True,
                  headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    print(f"  downloaded {len(r.content)} bytes")

    # CSV: 3 header rows (title / base year / column names) + 1 blank
    # before data. Skip 4 and supply column names manually.
    df = pd.read_csv(
        io.BytesIO(r.content), skiprows=4, header=None,
        usecols=range(7),
        names=["Date", "Food Price Index", "Meat", "Dairy",
               "Cereals", "Oils", "Sugar"],
    )
    df = df.dropna(subset=["Date"])
    df = df[df["Date"].astype(str).str.match(r"^\d{4}-\d{2}$")]
    print(f"  parsed {len(df)} monthly rows")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for col_label, (stem, display) in _SERIES.items():
        if col_label not in df.columns:
            print(f"  skip — column missing: {col_label}")
            continue
        imdr_code = f"FAO.FPI.{stem}.GLOBAL"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code, vendor_name="FAO",
            source_code=f"FAO/FPI/{stem}",
            display_name=display,
            unit="index", frequency="MONTHLY",
            country_iso="WW",
            category="cpi",
            is_seasonally_adjusted=False, bbg_ticker=None,
        ))
        for _, row in df.iterrows():
            try:
                obs_date = datetime.datetime.strptime(str(row["Date"]), "%Y-%m").date()
                value = float(row[col_label])
            except (ValueError, TypeError):
                continue
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
    return indicators, observations


def main() -> int:
    return run_main(vendor="fao", topic="fpi",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="IN")


if __name__ == "__main__":
    import sys
    sys.exit(main())
