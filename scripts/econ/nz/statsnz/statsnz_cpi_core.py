"""Stats NZ — CPI core / analytical series, via Infoshare.

The standard CPI release CSV (``statsnz_cpi.py``) carries only the standard
class hierarchy + tradables/non-tradables — it has NO core measure. Stats NZ's
analytical "non-standard" CPI series (exclusion-based cores and the statistical
trimmed-mean / weighted-percentile cores) live ONLY behind Infoshare, so this
fetcher rides the shared Playwright driver (`statsnz_infoshare.py`).

Two source tables under ``Economic indicators › Consumers Price Index - CPI``:

  1. "CPI Non-standard All Groups Less/Plus Selected Groupings" — 27 exclusion
     series as INDEX levels (same base as headline, 1988-Q4→). The macro-core
     analog is *All groups less food group, household energy subgroup and
     vehicle fuels* (ex-food-&-energy); also ex-food, ex-fuel, ex-housing, etc.
     YoY is computed downstream from the index (consistent with headline).

  2. "CPI Non-standard Trimmed Means and Weighted Percentiles" — the statistical
     cores as quarterly % change: 5/10/15/20/25/30% trimmed means, weighted
     median (incl. tradable/non-tradable splits), and the 10/25/75/90th
     weighted percentiles. We keep only the 15 "Quarterly *" series; the 93
     "Annual *" columns are superseded weight-base vintages published at annual
     cadence (sparse) and are dropped wholesale.

Coverage: cell 2.4 CPI Pressure (core). Quarterly. IMDR codes:
  STATSNZ.CPI.EXCL.{grouping}.NZ   (index)
  STATSNZ.CPI.TRIM.{measure}.NZ    (pct, QoQ)
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_infoshare import InfoshareClient, fetch_table_rows
from scripts.econ._runner import run_main


_CAT, _GROUP = "Economic indicators", "Consumers Price Index - CPI"


def _keep_quarterly(indicators, observations):
    """Keep only the 'Quarterly *' trim series; drop the sparse 'Annual *'
    weight-base vintages (93 columns). The keeper codes carry the slugified
    'QUARTERLY_' prefix (see statsnz_infoshare.slugify)."""
    keep = {
        ind.imdr_code for ind in indicators
        if ".TRIM.QUARTERLY_" in ind.imdr_code
    }
    inds = [i for i in indicators if i.imdr_code in keep]
    obs = [o for o in observations if o.imdr_code in keep]
    print(f"  -> kept {len(inds)} quarterly trim series (dropped "
          f"{len(indicators) - len(inds)} annual-vintage columns)")
    return inds, obs


def run_fetch(since: str | None = None, until: str | None = None):
    indicators, observations = [], []
    with InfoshareClient(headless=True) as client:
        # 1) Exclusion-based cores — index levels.
        print("[*] CPI core: 'All Groups Less/Plus Selected Groupings' (index)")
        ind, obs = fetch_table_rows(
            client,
            [_CAT, _GROUP,
             "CPI Non-standard All Groups Less/Plus Selected Groupings for New Zealand"],
            code_prefix="STATSNZ.CPI.EXCL",
            unit="index", frequency="QUARTERLY", category="cpi",
            display_prefix="CPI core (exclusion) - ",
        )
        indicators += ind
        observations += obs

        # 2) Statistical cores — quarterly % change (Quarterly series only).
        print("[*] CPI core: 'Trimmed Means and Weighted Percentiles' (QoQ %)")
        ind, obs = fetch_table_rows(
            client,
            [_CAT, _GROUP,
             "CPI Non-standard Trimmed Means and Weighted Percentiles for New Zealand"],
            code_prefix="STATSNZ.CPI.TRIM",
            unit="pct", frequency="QUARTERLY", category="cpi",
            display_prefix="CPI core (statistical) - ",
        )
        ind, obs = _keep_quarterly(ind, obs)
        indicators += ind
        observations += obs
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="cpi_core",
        fetch_fn=run_fetch,
        description="Stats NZ CPI core (Infoshare) — exclusion cores (index) + trimmed-mean/weighted-percentile cores (QoQ %), quarterly 1988-Q4 ->",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
