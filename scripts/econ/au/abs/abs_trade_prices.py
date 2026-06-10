"""ABS International Trade Price Indices (ITPI_IMP + ITPI_EXP) playground fetch.

Dataflows: ITPI_IMP, ITPI_EXP. Key shape: {MEASURE}.{INDEX}.{FREQ}.

MEASURE (CL_INDEX_MEASURES):
  1 = Index Number; 2 = % Chg prev period; 3 = % Chg YoY.
INDEX (All Groups headlines; flows differ on which code is live):
  ITPI_IMP: 6011001 (verified live; 3111001 in the codelist returns 404)
  ITPI_EXP: 8093697 — "SITC (Rev3) All Groups"  (verified live)
FREQ: Q (quarterly).

Terms of Trade = export price index / import price index — derive downstream
from the two headline series.
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


# Import-side SITC 1-digit input-cost breakdown — populates wiring-map cell
# 2.1 Input Costs (energy / food / commodities / capital goods / manufactures).
# Use the live 6013xxx family (NOT 8093xxx — both are in the codelist but
# only 6013xxx has data on the SDMX API as of 2026-06-10).
_IMPORT_INPUT_CATEGORIES = [
    ("6013001", "FOOD",                 "Food and live animals (SITC 0)"),
    ("6013002", "BEVERAGES_TOBACCO",    "Beverages and tobacco (SITC 1)"),
    ("6013003", "CRUDE_MATERIALS",      "Crude materials inedible ex fuels (SITC 2)"),
    ("6013004", "ENERGY",               "Mineral fuels, lubricants and related materials (SITC 3)"),
    ("6013005", "FATS_OILS",            "Animal and vegetable oils, fats and waxes (SITC 4)"),
    ("6013006", "CHEMICALS",            "Chemicals and related products (SITC 5)"),
    ("6013007", "MFG_BY_MATERIAL",      "Manufactured goods classified by material (SITC 6)"),
    ("6013008", "MACHINERY_TRANSPORT",  "Machinery and transport equipment (SITC 7)"),
    ("6013009", "MISC_MANUFACTURES",    "Miscellaneous manufactured articles (SITC 8)"),
]


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    # All Groups headline — import (6011001) + export (8093697).
    for flow, side, index_code in [
        ("ITPI_IMP", "IMPORT", "6011001"),
        ("ITPI_EXP", "EXPORT", "8093697"),
    ]:
        for measure, suffix, label_suffix, unit in [
            ("1", "INDEX",  "(Index, NSA)",                "index"),
            ("2", "QOQ",    "(QoQ %, NSA)",                "pct_qoq"),
            ("3", "YOY",    "(YoY %, NSA)",                "pct_yoy"),
        ]:
            out.append(SDMXSeries(
                dataflow=flow, key=f"{measure}.{index_code}.Q",
                imdr_code=f"ABS.ITPI.{side}_HEADLINE_{suffix}.AU",
                display_name=f"ABS {flow} All Groups headline {label_suffix}",
                unit=unit, frequency="QUARTERLY", category="other", is_sa=False,
            ))
    # Import-side input-cost breakdown — Index + YoY % per category.
    for index_code, code_suffix, display_name in _IMPORT_INPUT_CATEGORIES:
        out.append(SDMXSeries(
            dataflow="ITPI_IMP", key=f"1.{index_code}.Q",
            imdr_code=f"ABS.ITPI.IMPORT_{code_suffix}_INDEX.AU",
            display_name=f"ABS ITPI_IMP {display_name} (Index, NSA)",
            unit="index", frequency="QUARTERLY", category="other", is_sa=False,
        ))
        out.append(SDMXSeries(
            dataflow="ITPI_IMP", key=f"3.{index_code}.Q",
            imdr_code=f"ABS.ITPI.IMPORT_{code_suffix}_YOY.AU",
            display_name=f"ABS ITPI_IMP {display_name} (YoY %, NSA)",
            unit="pct_yoy", frequency="QUARTERLY", category="other", is_sa=False,
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
            print(f"  {spec.imdr_code:<48s} {len(obs):>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="abs", topic="trade_prices", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
