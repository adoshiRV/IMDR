"""ABS CPI playground fetch.

Dataflows: CPI (legacy combined) + CPI_Q (quarterly) + CPI_M (monthly).
Key shape (all three): {MEASURE}.{INDEX}.{TSEST}.{REGION}.{FREQ}.

MEASURE: 1 = Index numbers, 2 = % chg prev period, 3 = % chg prev year (YoY).
INDEX:   10001 = All groups CPI; 999902 = Trimmed Mean; 999903 = Weighted Median;
         20001..20006 = food/alcohol/clothing/housing/furnishings/transport top groups.
TSEST:   10 = Original (NSA), 20 = Seasonally Adjusted, 30 = Trend.
REGION:  50 = Australia (national); 1..8 = capital cities.
FREQ:    Q (quarterly) or M (monthly headline since Nov 2023).

Verified live combinations (2026-06-19 codelist + wildcard probe):
  - Headline Q (NSA) index: CPI/1.10001.10.50.Q
  - Headline M (NSA) index: CPI/1.10001.10.50.M
  - Headline M YoY %:       CPI/3.10001.10.50.M
  - Trimmed Mean M YoY:     CPI/3.999902.20.50.M  (SA, monthly)
  - Weighted Median M YoY:  CPI/3.999903.20.50.M  (SA, monthly)
  - Trimmed Mean Q YoY:     CPI_Q/3.999902.20.50.Q  (SA, quarterly — RBA's canonical underlying)
  - Weighted Median Q YoY:  CPI_Q/3.999903.20.50.Q  (SA, quarterly)
  - Capital cities Q index: CPI/1.10001.10.{1..8}.Q

Notes:
  - The quarterly SA analytical series (Trimmed Mean / Weighted Median) are
    NOT in the legacy ``CPI`` dataflow — that flow only carries NSA quarterly
    (TSEST=10). They live in the dedicated ``CPI_Q`` dataflow under TSEST=20,
    history 2000-Q1→ in index (MEASURE=1), QoQ (2) and YoY (3). Confirmed
    2026-06-19; supersedes the earlier "XLSX-only" note.
  - Quarterly headline YoY (MEASURE=3) is still not exposed for the legacy
    ``CPI`` headline series — only MEASURE=1 (index) and MEASURE=2 (QoQ %).
    Compute YoY downstream from the index series if needed.
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
            display_name="ABS CPI Trimmed Mean monthly YoY % (SA) — underlying inflation (monthly indicator)",
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
        # Analytical SA — quarterly (CPI_Q dataflow). The quarterly trimmed
        # mean YoY is the RBA's canonical underlying-inflation gauge.
        SDMXSeries(
            dataflow="CPI_Q", key="1.999902.20.50.Q",
            imdr_code="ABS.CPI.TRIMMED_MEAN_Q_INDEX.AU",
            display_name="ABS CPI Trimmed Mean quarterly index (SA)",
            unit="index", frequency="QUARTERLY", category="cpi", is_sa=True,
        ),
        SDMXSeries(
            dataflow="CPI_Q", key="2.999902.20.50.Q",
            imdr_code="ABS.CPI.TRIMMED_MEAN_Q_QOQ.AU",
            display_name="ABS CPI Trimmed Mean quarterly QoQ % (SA)",
            unit="pct", frequency="QUARTERLY", category="cpi", is_sa=True,
        ),
        SDMXSeries(
            dataflow="CPI_Q", key="3.999902.20.50.Q",
            imdr_code="ABS.CPI.TRIMMED_MEAN_Q_YOY.AU",
            display_name="ABS CPI Trimmed Mean quarterly YoY % (SA) — RBA's canonical underlying inflation",
            unit="pct_yoy", frequency="QUARTERLY", category="cpi", is_sa=True,
        ),
        SDMXSeries(
            dataflow="CPI_Q", key="1.999903.20.50.Q",
            imdr_code="ABS.CPI.WEIGHTED_MEDIAN_Q_INDEX.AU",
            display_name="ABS CPI Weighted Median quarterly index (SA)",
            unit="index", frequency="QUARTERLY", category="cpi", is_sa=True,
        ),
        SDMXSeries(
            dataflow="CPI_Q", key="2.999903.20.50.Q",
            imdr_code="ABS.CPI.WEIGHTED_MEDIAN_Q_QOQ.AU",
            display_name="ABS CPI Weighted Median quarterly QoQ % (SA)",
            unit="pct", frequency="QUARTERLY", category="cpi", is_sa=True,
        ),
        SDMXSeries(
            dataflow="CPI_Q", key="3.999903.20.50.Q",
            imdr_code="ABS.CPI.WEIGHTED_MEDIAN_Q_YOY.AU",
            display_name="ABS CPI Weighted Median quarterly YoY % (SA)",
            unit="pct_yoy", frequency="QUARTERLY", category="cpi", is_sa=True,
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
