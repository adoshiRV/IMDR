"""ABS Labour Force, Australia, Detailed — Table 04: Employed persons by
Industry division of main job (ANZSIC).

Source: XLSX time-series workbook (NOT the SDMX REST API — this table is
only published as a standalone workbook), resolved off the "latest-release"
landing page so the quarterly release-folder segment (e.g. ``mar-2026``)
never needs to be hardcoded:

  https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia-detailed/latest-release
  -> .../labour-force-australia-detailed/{mon-yyyy}/6291004.xlsx

Quarterly, back to 1984-11-01. Only the ``Employed total ; Persons``
division-level rows are ingested (Males/Females and full-time/part-time
splits are out of scope for this pass) across all three published series
types: Original, Seasonally Adjusted, Trend.

Division description format verified live 2026-07-23 against the Index
sheet: ``"{Division} ;  Employed total ;"`` for the 19 ANZSIC divisions,
and bare ``"Employed total ;"`` for the all-industries total row.

``_DIVISIONS`` maps the ABS division name (as it appears verbatim in the
workbook) to a hand-checked ``imdr_code`` suffix — not auto-slugified, so
codes stay stable across releases even if ABS tweaks description wording.
"""
from __future__ import annotations

import datetime
import sys

from imdr.domains.econ.abs_timeseries_xlsx import (
    download_workbook,
    parse_workbook,
    resolve_latest_xlsx_url,
)
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_LANDING_URL = (
    "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/"
    "labour-force-australia-detailed/latest-release"
)
_TABLE_FILENAME = "6291004.xlsx"

_TOTAL_KEY = "__TOTAL__"

# ABS division name (verbatim, as it appears in the Index sheet) -> imdr_code suffix.
_DIVISIONS: dict[str, str] = {
    "Agriculture, Forestry and Fishing": "AGRIC_FOREST_FISH",
    "Mining": "MINING",
    "Manufacturing": "MANUFACTURING",
    "Electricity, Gas, Water and Waste Services": "ELEC_GAS_WATER_WASTE",
    "Construction": "CONSTRUCTION",
    "Wholesale Trade": "WHOLESALE_TRADE",
    "Retail Trade": "RETAIL_TRADE",
    "Accommodation and Food Services": "ACCOM_FOOD",
    "Transport, Postal and Warehousing": "TRANSPORT_POSTAL_WAREHOUSE",
    "Information Media and Telecommunications": "INFO_MEDIA_TELECOM",
    "Financial and Insurance Services": "FINANCE_INSURANCE",
    "Rental, Hiring and Real Estate Services": "RENTAL_HIRING_REALESTATE",
    "Professional, Scientific and Technical Services": "PROF_SCI_TECH",
    "Administrative and Support Services": "ADMIN_SUPPORT",
    "Public Administration and Safety": "PUBLIC_ADMIN_SAFETY",
    "Education and Training": "EDUCATION_TRAINING",
    "Health Care and Social Assistance": "HEALTH_SOCIAL",
    "Arts and Recreation Services": "ARTS_RECREATION",
    "Other Services": "OTHER_SERVICES",
    _TOTAL_KEY: "ALL_INDUSTRIES",
}

_DIVISION_LABELS: dict[str, str] = {
    _TOTAL_KEY: "All industries",
}

# ABS Series Type -> (imdr_code suffix, display label, is_seasonally_adjusted).
_SERIES_TYPES: dict[str, tuple[str, str, bool]] = {
    "Original": ("ORIG", "Original", False),
    "Seasonally Adjusted": ("SA", "SA", True),
    "Trend": ("TREND", "Trend", False),
}


def _division_key(description: str) -> str | None:
    """Extract the division name (or ``_TOTAL_KEY``) from an Index sheet
    ``Data Item Description`` cell, e.g.
    ``"Education and Training ;  Employed total ;"`` -> ``"Education and Training"``,
    ``"Employed total ;"`` -> ``_TOTAL_KEY``.
    """
    first = description.split(";")[0].strip()
    if not first:
        return None
    if first == "Employed total":
        return _TOTAL_KEY
    return first


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_d = datetime.date.fromisoformat(since) if since else None
    until_d = datetime.date.fromisoformat(until) if until else None

    url = resolve_latest_xlsx_url(_LANDING_URL, _TABLE_FILENAME)
    print(f"  resolved workbook URL: {url}")
    data = download_workbook(url)
    print(f"  downloaded {len(data):,} bytes")
    parsed = parse_workbook(data)
    print(f"  parsed {len(parsed)} series from workbook")

    now = datetime.datetime.now(UTC)
    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []
    unmatched: list[str] = []

    for series in parsed.values():
        key = _division_key(series.description)
        if key is None or key not in _DIVISIONS:
            unmatched.append(series.description)
            continue
        type_info = _SERIES_TYPES.get(series.series_type)
        if type_info is None:
            continue
        type_suffix, type_label, is_sa = type_info
        div_suffix = _DIVISIONS[key]
        div_label = _DIVISION_LABELS.get(key, key)

        imdr_code = f"ABS.LF.EMPLOYED_IND_{div_suffix}_{type_suffix}.AU"
        # Guard against two workbook series mapping to one imdr_code. _division_key
        # only reads the first ";"-segment, so if ABS ever adds a Male/Female (or
        # FT/PT) split to Table 04 (e.g. "Construction ;  Employed total ;  Males ;")
        # it would collide with the Persons-total row. Keep the first (the total),
        # skip and warn on the rest — never silently blend two series' obs.
        if imdr_code in indicators:
            unmatched.append(f"{series.description} [collides with {imdr_code}, skipped]")
            continue
        indicators[imdr_code] = IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="ABS",
            source_code=f"ABS.LF_DETAILED.6291004.{series.series_id}",
            display_name=f"ABS Labour Force — Employed persons ({div_label}, {type_label})",
            unit="persons",
            frequency="QUARTERLY",
            country_iso="AU",
            category="labour",
            is_seasonally_adjusted=is_sa,
        )
        n_obs = 0
        for d, v in series.obs:
            if since_d and d < since_d:
                continue
            if until_d and d > until_d:
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=d, vintage=0,
                release_date=now, value=v, ingested_at=now,
            ))
            n_obs += 1
        print(f"  {imdr_code:<45s} {n_obs:>5} obs")

    if unmatched:
        print(f"  WARNING: {len(unmatched)} series with unrecognised description skipped:")
        for desc in unmatched[:10]:
            print(f"    {desc!r}")

    return list(indicators.values()), observations


def main() -> int:
    return run_main(vendor="abs", topic="lf_industry", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
