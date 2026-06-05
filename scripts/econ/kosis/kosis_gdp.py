"""KOSIS BOK Quarterly Key Indicators fetcher (DT_200Y102).

Source: Bank of Korea (orgId=301), 주요지표(분기지표) — Main Quarterly
Indicators, reference year 2020.

The table publishes 28 quarterly indicators in two blocks:
  Block 10111-10128: Real GDP, sectors, expenditure components — QoQ % SA
  Block 10211-10228: Same series — YoY % (raw)

We pull 10 headline cuts × 2 frequencies (QoQ SA + YoY) = 20 indicators
covering:
  - Total GDP
  - Manufacturing GDP
  - Construction GDP
  - Services GDP
  - Agriculture/forestry/fishing GDP
  - Private consumption
  - Government consumption
  - Facilities investment
  - Construction investment
  - Domestic demand (ex-inventories)
  - Goods exports
  - Goods imports

Cell mapping: 1.4 Macro Core + parts of 1.1 / 1.2 / 1.3 (consumption,
fiscal, external demand).

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_gdp.py
    python -m scripts.econ.kosis.kosis_gdp
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# C1 suffix (last segment after ACC_ITEM.) → (imdr suffix, display, freq_kind)
# Block 101xx = QoQ %, SA  (real, seasonally adjusted, prior quarter)
# Block 102xx = YoY % (real, raw, same period prior year)
_CUTS: dict[str, tuple[str, str, str]] = {
    # Block 101xx — QoQ SA
    "10111": ("GDP",               "Real GDP",                      "QOQ_SA"),
    "10113": ("AGRI",              "Agriculture / Forestry / Fishing GDP", "QOQ_SA"),
    "10114": ("MFG",               "Manufacturing GDP",             "QOQ_SA"),
    "10115": ("CONSTR",            "Construction GDP",              "QOQ_SA"),
    "10116": ("SVC",               "Services GDP",                  "QOQ_SA"),
    "10122": ("PCE",               "Private Consumption",           "QOQ_SA"),
    "10123": ("FACIL_INV",         "Facilities Investment",         "QOQ_SA"),
    "10124": ("CONSTR_INV",        "Construction Investment",       "QOQ_SA"),
    "10125": ("EXP_GOODS",         "Goods Exports",                 "QOQ_SA"),
    "10126": ("IMP_GOODS",         "Goods Imports",                 "QOQ_SA"),
    "10127": ("DOMESTIC_DEMAND",   "Domestic Demand (ex-inventories)", "QOQ_SA"),
    "10128": ("GOV_CONS",          "Government Consumption",        "QOQ_SA"),
    # Block 102xx — YoY raw
    "10211": ("GDP",               "Real GDP",                      "YOY"),
    "10212": ("AGRI",              "Agriculture / Forestry / Fishing GDP", "YOY"),
    "10213": ("MFG",               "Manufacturing GDP",             "YOY"),
    "10215": ("CONSTR",            "Construction GDP",              "YOY"),
    "10216": ("SVC",               "Services GDP",                  "YOY"),
    "10222": ("PCE",               "Private Consumption",           "YOY"),
    "10223": ("FACIL_INV",         "Facilities Investment",         "YOY"),
    "10224": ("CONSTR_INV",        "Construction Investment",       "YOY"),
    "10225": ("EXP_GOODS",         "Goods Exports",                 "YOY"),
    "10226": ("IMP_GOODS",         "Goods Imports",                 "YOY"),
    "10227": ("DOMESTIC_DEMAND",   "Domestic Demand (ex-inventories)", "YOY"),
    "10228": ("GOV_CONS",          "Government Consumption",        "YOY"),
}


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  Fetching GDP-Q: DT_200Y102 (BOK, orgId=301) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="301",
        tbl_id="DT_200Y102",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="Q",
        start_prd_de="19601",
        end_prd_de="20264",
    )
    print(f"{len(rows)} rows")

    # Index rows by C1 last-segment.
    by_suffix: dict[str, list[dict]] = {}
    for r in rows:
        c1 = r.get("C1") or ""
        last = c1.split(".")[-1]
        by_suffix.setdefault(last, []).append(r)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for c1_suffix, (cut_suffix, display, freq_kind) in _CUTS.items():
        sub = by_suffix.get(c1_suffix, [])
        if not sub:
            print(f"  WARN: no rows for C1 suffix {c1_suffix} ({cut_suffix} {freq_kind})")
            continue
        imdr_code = f"BOK.GDP.{cut_suffix}.{freq_kind}.KR"
        sa = freq_kind == "QOQ_SA"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="KOSIS",
            source_code=f"301/DT_200Y102/{c1_suffix}",
            display_name=f"Korea {display}, {freq_kind.replace('_',' ')} % (BOK)",
            unit="pct",
            frequency="QUARTERLY",
            country_iso="KR",
            category="gdp",
            is_seasonally_adjusted=sa,
            bbg_ticker=None,
        ))
        for r in sub:
            ymd = parse_kosis_period(r.get("PRD_DE"), "Q")
            if ymd is None:
                continue
            obs_date = datetime.date(*ymd)
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            try:
                value = float(r["DT"]) if r.get("DT") not in (None, "") else None
            except (TypeError, ValueError):
                value = None
            observations.append(ObservationRow(
                imdr_code=imdr_code,
                obs_date=obs_date,
                vintage=0,
                release_date=now,
                value=value,
                ingested_at=now,
            ))

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="gdp",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
