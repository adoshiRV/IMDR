"""ABS CPI playground fetch.

Dataflow: CPI. Key shape: {MEASURE}.{INDEX}.{TSEST}.{REGION}.{FREQ}.

MEASURE: 1 = Index numbers, 2 = % chg prev period, 3 = % chg prev year (YoY).
INDEX:   10001 = All groups CPI; 999902 = Trimmed Mean; 999903 = Weighted Median;
         20001..20006 = food/alcohol/clothing/housing/furnishings/transport top groups.
TSEST:   10 = Original (NSA), 20 = Seasonally Adjusted, 30 = Trend.
REGION:  50 = Australia (national); 1..8 = capital cities.
FREQ:    Q (quarterly headline) or M (monthly headline since Nov 2023).

Verified live combinations (2026-06-09 codelist + wildcard probe):
  - Headline Q (NSA) index: 1.10001.10.50.Q
  - Headline M (NSA) index: 1.10001.10.50.M
  - Headline M YoY %:       3.10001.10.50.M
  - Trimmed Mean M YoY:     3.999902.20.50.M  (SA, monthly only)
  - Weighted Median M YoY:  3.999903.20.50.M  (SA, monthly only)
  - Capital cities Q index: 1.10001.10.{1..8}.Q

Notes:
  - Quarterly Trimmed Mean / Weighted Median are NOT in the SDMX dataflow as
    of 2026-06-09 — only the monthly analytical series are exposed. The
    quarterly versions live in catalogue 6401.0 XLSX downloads (out of scope
    for this fetcher).
  - Quarterly headline YoY (MEASURE=3) is also not exposed for FREQ=Q —
    only MEASURE=1 (index) and MEASURE=2 (QoQ %). Compute YoY downstream
    from the index series if needed.
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_CAPITAL_CITIES = [
    (1, "SYDNEY"),
    (2, "MELBOURNE"),
    (3, "BRISBANE"),
    (4, "ADELAIDE"),
    (5, "PERTH"),
    (6, "HOBART"),
    (7, "DARWIN"),
    (8, "CANBERRA"),
]


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = [
        # Headline — national
        SDMXSeries(
            dataflow="CPI", key="1.10001.10.50.Q",
            imdr_code="ABS.CPI.HEADLINE_NSA.AU",
            display_name="ABS CPI All Groups Australia (NSA, index)",
            unit="index", frequency="QUARTERLY", category="cpi", is_sa=False,
        ),
        SDMXSeries(
            dataflow="CPI", key="2.10001.10.50.Q",
            imdr_code="ABS.CPI.HEADLINE_QOQ.AU",
            display_name="ABS CPI All Groups Australia, QoQ % change (NSA)",
            unit="pct", frequency="QUARTERLY", category="cpi", is_sa=False,
        ),
        SDMXSeries(
            dataflow="CPI", key="1.10001.10.50.M",
            imdr_code="ABS.CPI.HEADLINE_M_INDEX.AU",
            display_name="ABS CPI All Groups Australia monthly (index, NSA, since Nov 2023)",
            unit="index", frequency="MONTHLY", category="cpi", is_sa=False,
        ),
        SDMXSeries(
            dataflow="CPI", key="3.10001.10.50.M",
            imdr_code="ABS.CPI.HEADLINE_M_YOY.AU",
            display_name="ABS CPI All Groups Australia monthly YoY % (NSA, since Nov 2023)",
            unit="pct_yoy", frequency="MONTHLY", category="cpi", is_sa=False,
        ),
        # Analytical SA — monthly only in SDMX
        SDMXSeries(
            dataflow="CPI", key="1.999902.20.50.M",
            imdr_code="ABS.CPI.TRIMMED_MEAN_M_INDEX.AU",
            display_name="ABS CPI Trimmed Mean monthly index (SA)",
            unit="index", frequency="MONTHLY", category="cpi", is_sa=True,
        ),
        SDMXSeries(
            dataflow="CPI", key="3.999902.20.50.M",
            imdr_code="ABS.CPI.TRIMMED_MEAN_M_YOY.AU",
            display_name="ABS CPI Trimmed Mean monthly YoY % (SA) — RBA's preferred underlying inflation",
            unit="pct_yoy", frequency="MONTHLY", category="cpi", is_sa=True,
        ),
        SDMXSeries(
            dataflow="CPI", key="1.999903.20.50.M",
            imdr_code="ABS.CPI.WEIGHTED_MEDIAN_M_INDEX.AU",
            display_name="ABS CPI Weighted Median monthly index (SA)",
            unit="index", frequency="MONTHLY", category="cpi", is_sa=True,
        ),
        SDMXSeries(
            dataflow="CPI", key="3.999903.20.50.M",
            imdr_code="ABS.CPI.WEIGHTED_MEDIAN_M_YOY.AU",
            display_name="ABS CPI Weighted Median monthly YoY % (SA)",
            unit="pct_yoy", frequency="MONTHLY", category="cpi", is_sa=True,
        ),
    ]
    # Capital cities — quarterly headline index
    for code, name in _CAPITAL_CITIES:
        out.append(SDMXSeries(
            dataflow="CPI", key=f"1.10001.10.{code}.Q",
            imdr_code=f"ABS.CPI.{name}.AU",
            display_name=f"ABS CPI All Groups, {name.title()} (Q, NSA, index)",
            unit="index", frequency="QUARTERLY", category="cpi", is_sa=False,
        ))
    return out


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    with ABSClient() as client:
        for spec in _build_series():
            try:
                ind, obs = fetch_series(client, spec, since, until)
            except Exception as exc:
                print(f"  ERROR {spec.imdr_code}: {exc}")
                continue
            indicators.append(ind)
            observations.extend(obs)
            print(f"  {spec.imdr_code:<45s} {len(obs):>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="abs", topic="cpi", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
