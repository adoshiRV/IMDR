"""DJPPR Kepemilikan SBN ownership-by-investor fetcher.

Daily holdings of tradable IDR-denominated government securities (SBN) by
investor category — banks, Bank Indonesia (net + gross), mutual funds,
insurance + pension, foreign (incl. foreign official), individuals, other.
12 categories × 3 instruments (SUN / SBSN / TOTAL) = 36 indicators, unit
``idr_trn`` (trillion Rupiah).

Cell mapping: 1.2 Fiscal Demand (deficit-financing investor base) +
4.4 Policy Reaction (BI's QE-equivalent absorption via burden-sharing).

Sources:
  - 2016-2024: annual XLSX
  - 2025+:     monthly PDF
Both formats are routed through ``imdr.domains.econ.djppr_kepemilikan``.

Pre-2016 legacy XLSX is NOT handled — tracked at IMD-42.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from imdr.domains.econ.djppr_kepemilikan import (
    download,
    fetch_listing,
    imdr_code,
    parse_pdf,
    parse_xlsx,
    CATEGORIES,
    INSTRUMENTS,
    display_name,
)
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# Pre-2016 layouts (combined files 2003-2006 SUN-only and 2007-2015 mixed-
# granularity) use a different bank-subtype taxonomy and would need a parallel
# parser. Skipped here, tracked at IMD-42. Anything tagged with a year strictly
# less than this cutoff is dropped from the listing.
_MIN_YEAR_SUPPORTED = 2016

_CACHE_DIR = (
    Path(__file__).resolve().parents[3]
    / "data" / "econ" / "djppr" / "kepemilikan_raw"
)


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    listing = [
        e for e in fetch_listing()
        if (e.year or 0) >= _MIN_YEAR_SUPPORTED
    ]
    print(f"  listing: {len(listing)} entries from {_MIN_YEAR_SUPPORTED}+")

    indicators: list[IndicatorRow] = [
        IndicatorRow(
            imdr_code=imdr_code(cat.code, instr),
            vendor_name="DJPPR",
            source_code=f"DJPPR/Kepemilikan_SBN/{cat.code}/{instr}",
            display_name=display_name(cat, instr),
            unit="idr_trn",
            frequency="DAILY",
            country_iso="ID",
            category="instr_outstand",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        )
        for cat in CATEGORIES
        for instr in INSTRUMENTS
    ]

    # Last-write-wins dedup: later entries (PDFs published mid-month) override
    # earlier ones for the same (indicator, obs_date). The listing comes back
    # newest-first, so we *reverse* to apply oldest first → newest overrides.
    seen: dict[tuple[str, datetime.date], float] = {}
    for entry in reversed(listing):
        print(f"\n  ── {entry.title[:60]} :: {entry.description}")
        path, ext = download(entry.link, _CACHE_DIR)
        tuples = parse_pdf(path) if ext == "pdf" else parse_xlsx(path)
        rows = 0
        for obs_date, cat, instr, value in tuples:
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            seen[(imdr_code(cat, instr), obs_date)] = value
            rows += 1
        print(f"    parsed {rows:,} rows  →  store size {len(seen):,}")

    observations: list[ObservationRow] = [
        ObservationRow(
            imdr_code=code, obs_date=obs_date, vintage=0,
            release_date=now, value=value, ingested_at=now,
        )
        for (code, obs_date), value in seen.items()
    ]
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="djppr", topic="sbn_ownership",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="ID",
    )


if __name__ == "__main__":
    import sys; sys.exit(main())
