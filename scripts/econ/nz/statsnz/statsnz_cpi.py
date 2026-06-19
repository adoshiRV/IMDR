"""Stats NZ — CPI quarterly fetcher.

Pulls the headline CPI All Groups + Level-1 group breakdown (11 sub-groups)
+ key Level-2 subgroups + tradables / non-tradables from two release-page
asset CSVs. Direct `httpx` GET — no Playwright, no ADE key, no Cloudflare
gate (assets path is not JS-rendered).

Release-page assets used:
  - `consumers-price-index-{Month-YYYY-quarter}-index-numbers.csv`
    Full history 1914-Q2 -> latest quarter; All Groups + Level-1 + Level-2 +
    Level-3 + class-level CPI series.
  - `consumers-price-index-{Month-YYYY-quarter}-tradeables-and-non-tradeables.csv`
    Tradables / Non-tradables decomp (post-1999).

Coverage: 17 indicators (1 headline + 11 Level-1 groups + 3 Level-2 subgroups
+ 2 tradables/non-tradables). Quarterly, NSA. Cell 2.4 CPI Pressure.
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_common import (
    StatsNZClient,
    StatsNZSeries,
    parse_release_csv,
    rows_to_indicator_observations,
)
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_BASE = "https://www.stats.govt.nz/assets/Uploads"
_DEFAULT_RELEASE = "march-2026-quarter"

# Stats NZ Series_reference -> (IMDR code, display, unit, freq, category, is_sa)
# CPIQ.SE9A is "CPI All Groups for NZ" — headline NSA index (base 1000 at Jun-2017).
# CPIQ.SE9## are Level-1 groups (11 — sums to All Groups using weights).
# CPIQ.SE90## are Level-2 subgroups — picked the 3 most macro-relevant.
_INDEX_NUMBERS_SPECS = {
    s.source_code: s
    for s in [
        StatsNZSeries("CPIQ.SE9A",  "STATSNZ.CPI.HEADLINE.NZ",
                      "CPI All Groups, NZ", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE901", "STATSNZ.CPI.FOOD.NZ",
                      "CPI Level 1 - Food", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE902", "STATSNZ.CPI.ALCOHOL_TOBACCO.NZ",
                      "CPI Level 1 - Alcoholic beverages and tobacco", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE903", "STATSNZ.CPI.CLOTHING_FOOTWEAR.NZ",
                      "CPI Level 1 - Clothing and footwear", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE904", "STATSNZ.CPI.HOUSING.NZ",
                      "CPI Level 1 - Housing and household utilities", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE905", "STATSNZ.CPI.HOUSEHOLD_CONTENTS.NZ",
                      "CPI Level 1 - Household contents and services", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE906", "STATSNZ.CPI.HEALTH.NZ",
                      "CPI Level 1 - Health", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE907", "STATSNZ.CPI.TRANSPORT.NZ",
                      "CPI Level 1 - Transport", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE908", "STATSNZ.CPI.COMMUNICATION.NZ",
                      "CPI Level 1 - Communication", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE909", "STATSNZ.CPI.RECREATION_CULTURE.NZ",
                      "CPI Level 1 - Recreation and culture", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE910", "STATSNZ.CPI.EDUCATION.NZ",
                      "CPI Level 1 - Education", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE911", "STATSNZ.CPI.MISC_GOODS_SERVICES.NZ",
                      "CPI Level 1 - Miscellaneous goods and services", "index", "QUARTERLY", "cpi"),
        # Macro-relevant Level-2 picks:
        StatsNZSeries("CPIQ.SE9045", "STATSNZ.CPI.HOUSEHOLD_ENERGY.NZ",
                      "CPI Level 2 - Household energy", "index", "QUARTERLY", "energy"),
        StatsNZSeries("CPIQ.SE9041", "STATSNZ.CPI.ACTUAL_RENT.NZ",
                      "CPI Level 2 - Actual rentals for housing", "index", "QUARTERLY", "housing"),
        StatsNZSeries("CPIQ.SE9011", "STATSNZ.CPI.FRUIT_VEG.NZ",
                      "CPI Level 2 - Fruit and vegetables", "index", "QUARTERLY", "cpi"),
    ]
}

# CPIQ.SE9NS6000 / CPIQ.SE9NS6500 = Tradable / Non-Tradable All Groups
# (in the "CPI Non-standard Tradable & Non-tradable Component" group;
#  these are the macro-headline tradables splits, post-1999).
_TRADABLES_SPECS = {
    s.source_code: s
    for s in [
        StatsNZSeries("CPIQ.SE9NS6000", "STATSNZ.CPI.TRADABLES.NZ",
                      "CPI Tradable - All Groups, NZ", "index", "QUARTERLY", "cpi"),
        StatsNZSeries("CPIQ.SE9NS6500", "STATSNZ.CPI.NON_TRADABLES.NZ",
                      "CPI Non-Tradable - All Groups, NZ", "index", "QUARTERLY", "cpi"),
    ]
}


def _url(release: str, slug: str) -> str:
    quarter_title = "Consumers-price-index-" + "-".join(
        w.capitalize() if w != "quarter" else "quarter" for w in release.split("-")
    )
    return (
        f"{_BASE}/Consumers-price-index/"
        f"{quarter_title}/Download-data/consumers-price-index-{release}-{slug}.csv"
    )


def _fetch_csv_specs(
    client: StatsNZClient,
    release: str,
    slug: str,
    specs: dict[str, StatsNZSeries],
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    url = _url(release, slug)
    print(f"[*] fetching {url}")
    text = client.fetch_csv(url)
    _, rows = parse_release_csv(text)
    indicators, observations = rows_to_indicator_observations(rows, specs)
    print(f"  -> {len(rows)} CSV rows  ->  {len(indicators)} indicators, {len(observations)} obs")
    return indicators, observations


def run_fetch(
    since: str | None = None,
    until: str | None = None,
    *,
    release: str = _DEFAULT_RELEASE,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Pull both CPI CSVs and merge into one (indicators, observations) pair.

    `since` / `until` are accepted for CLI uniformity but ignored — the
    release CSV contains the full history; the caller can post-filter in
    parquet / SQL if needed.
    """
    _ = since, until  # noqa: F841
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    with StatsNZClient() as c:
        i1, o1 = _fetch_csv_specs(c, release, "index-numbers", _INDEX_NUMBERS_SPECS)
        indicators.extend(i1)
        observations.extend(o1)
        try:
            i2, o2 = _fetch_csv_specs(c, release, "tradeables-and-non-tradeables", _TRADABLES_SPECS)
            indicators.extend(i2)
            observations.extend(o2)
        except Exception as e:
            print(f"  [!] tradables CSV failed: {e!r} — continuing with index-numbers only")
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="cpi",
        fetch_fn=run_fetch,
        description="Stats NZ CPI — release march-2026-quarter; 17 indicators across All-Groups, Level-1, Level-2, tradables",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
