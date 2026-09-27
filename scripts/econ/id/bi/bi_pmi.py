"""BI Prompt Manufacturing Index fetcher (PMI-BI).

Quarterly manufacturing diffusion index, 2010 Q1 →. Headline PMI-BI plus its
5 components (T1) and 14 manufacturing sub-sectors (T2) = **20 indicators**.
Cell mapping: 1.4 Macro Core (the PMI sub-bullet).

**Why this matters:** `id_coverage_plan.md` records Manufacturing PMI as
❌ "S&P Global / paid / use SKDU equiv". That is true of the *monthly* S&P
Global series, but BI publishes its own PMI for free and has since 2010. It
is quarterly rather than monthly, so it does not fully replace S&P — but it
is a far closer concept match than the SKDU business-activity balance that
was standing in for it, and it costs nothing. Discovered 2026-09-21 while
inventorying BI's report categories for Track B.

**Two traps this fetcher exists to avoid:**

1. **The archive URL must be discovered, never constructed.** Each edition
   gets its own filename and BI is inconsistent about it —
   `Data-Series-PMI-Triwulan-II-2026.zip`, `PMI-Triwulan-I-2026.zip`
   (no prefix), `Data-Series-PMI-Tw-IV-2025.zip` ("Tw" not "Triwulan").
   `download_data_series_zip` reads the href off the listing.
2. **The last column is a FORECAST.** BI publishes next quarter's estimate
   inside the current edition, flagged `III*` with an "Angka Perkiraan"
   footnote. It parses exactly like an actual. `forecast_periods()` returns
   the dates to drop; without that filter a projection lands in
   `econ.fact_indicator` as though it were a print.

Source: `?Kategori=prompt manufacturing index` → `Tabel PMI-BI *.xlsx`.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_survey import (
    download_data_series_zip,
    forecast_periods,
    parse_survey_rows,
)
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.UTC

KATEGORI = "prompt manufacturing index"
CACHE_NAME = "PMI"

_T1_SHEET = "T1 - Komponen PMI"
_T2_SHEET = "T2 PMI - Sublapangan Usaha"

# T1 — headline + 5 components. Layout: year_row=4, quarter_row=5, data
# starts col 2. Column 69 is a trailing English label, dropped naturally
# because its period cell is empty.
_T1_LAYOUT = dict(year_row=4, month_row=5, first_data_col=2)
_T1_TARGETS: list[tuple[int, str, str]] = [
    (11, "BI.PMI.HEADLINE.ID",
     "Indonesia Prompt Manufacturing Index — PMI-BI headline (BI, index)"),
    (6, "BI.PMI.OUTPUT.ID",
     "Indonesia PMI-BI — Production Volume (BI, index)"),
    (7, "BI.PMI.NEW_ORDERS.ID",
     "Indonesia PMI-BI — Total Order Volume (BI, index)"),
    (8, "BI.PMI.SUPPLIER_DELIVERY.ID",
     "Indonesia PMI-BI — Input Goods Delivery Speed (BI, index)"),
    (9, "BI.PMI.FIN_GOODS_STOCKS.ID",
     "Indonesia PMI-BI — Finished Goods Inventory Volume (BI, index)"),
    (10, "BI.PMI.EMPLOYMENT.ID",
     "Indonesia PMI-BI — Number of Employees (BI, index)"),
]

# T2 — 14 manufacturing sub-sectors. Different layout: this sheet is
# English-label-first (col 0) with the Indonesian label in col 1, and its
# period header sits one row lower than T1's.
_T2_LAYOUT = dict(year_row=4, month_row=5, first_data_col=2)
_T2_TARGETS: list[tuple[int, str, str]] = [
    (6, "BI.PMI.SECTOR.FOOD_BEV.ID", "Food Products and Beverages"),
    (7, "BI.PMI.SECTOR.TOBACCO.ID", "Tobacco Products"),
    (8, "BI.PMI.SECTOR.TEXTILE_APPAREL.ID", "Textiles and Wearing Apparel"),
    (9, "BI.PMI.SECTOR.LEATHER.ID", "Leather and Related Products"),
    (10, "BI.PMI.SECTOR.WOOD.ID", "Wood and Products of Wood"),
    (11, "BI.PMI.SECTOR.PAPER.ID", "Paper and Paper Products"),
    (12, "BI.PMI.SECTOR.CHEM_PHARMA.ID", "Chemicals and Pharmaceuticals"),
    (13, "BI.PMI.SECTOR.RUBBER_PLASTIC.ID", "Rubber and Rubber Products"),
    (14, "BI.PMI.SECTOR.NONMETAL_MINERAL.ID", "Other Non-Metallic Mineral Products"),
    (15, "BI.PMI.SECTOR.BASIC_METALS.ID", "Basic Metals"),
    (16, "BI.PMI.SECTOR.FAB_METAL_ELEC.ID", "Fabricated Metal, Computer and Electronics"),
    (17, "BI.PMI.SECTOR.MACHINERY.ID", "Machinery and Equipment"),
    (18, "BI.PMI.SECTOR.TRANSPORT_EQUIP.ID", "Transport Equipment"),
    (19, "BI.PMI.SECTOR.FURNITURE.ID", "Furniture"),
]


def _emit(
    *,
    path,
    sheet: str,
    layout: dict,
    targets: list[tuple[int, str, str]],
    display_fmt,
    since_dt,
    until_dt,
    now,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    rows_data = parse_survey_rows(
        path, sheet, rows=[r for r, _, _ in targets], **layout
    )
    skip = forecast_periods(path, sheet, **layout)
    if skip:
        print(f"    {sheet}: excluding BI forecast period(s) "
              f"{sorted(d.isoformat() for d in skip)}")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for row_idx, imdr_code, label in targets:
        series = rows_data.get(row_idx) or []
        if not series:
            print(f"    {imdr_code}: row {row_idx} empty — skipping")
            continue
        indicators.append(IndicatorRow(
            imdr_code=imdr_code, vendor_name="BI",
            source_code=f"BI/PMI/{sheet}/row={row_idx}",
            display_name=display_fmt(label), unit="index",
            frequency="QUARTERLY", country_iso="ID", category="sentiment",
            is_seasonally_adjusted=False, bbg_ticker=None,
        ))
        n = 0
        for obs_date, value in series:
            if value is None or obs_date in skip:
                continue
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
            n += 1
        print(f"    {imdr_code}: {n} obs")
    return indicators, observations


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print(f"  discovering + downloading PMI data-series ZIP "
          f"(Kategori={KATEGORI!r}) ...", end=" ", flush=True)
    path = download_data_series_zip(KATEGORI, CACHE_NAME)
    print(path.name)

    ind_a, obs_a = _emit(
        path=path, sheet=_T1_SHEET, layout=_T1_LAYOUT, targets=_T1_TARGETS,
        display_fmt=lambda label: label,
        since_dt=since_dt, until_dt=until_dt, now=now,
    )
    ind_b, obs_b = _emit(
        path=path, sheet=_T2_SHEET, layout=_T2_LAYOUT, targets=_T2_TARGETS,
        display_fmt=lambda label: (
            f"Indonesia PMI-BI by sub-sector — {label} (BI, index)"
        ),
        since_dt=since_dt, until_dt=until_dt, now=now,
    )
    return ind_a + ind_b, obs_a + obs_b


def main() -> int:
    return run_main(vendor="bi", topic="pmi",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="ID")


if __name__ == "__main__":
    import sys
    sys.exit(main())
