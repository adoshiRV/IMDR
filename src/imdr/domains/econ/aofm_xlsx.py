"""AOFM XLSX parsing helpers for prod AU econ fetchers.

AOFM files are static XLSX snapshots downloaded manually via Microsoft
Edge from https://www.aofm.gov.au/data-hub (corp firewall blocks Chrome
+ Playwright). The Edge-download tool stays in
``playground/econ/aofm/fetch_xlsx.py`` because it's a manual operator
workflow. Prod fetchers under ``scripts/econ/au/aofm/`` read from
``data/econ/au/aofm/xlsx/`` and parse with the helpers here.

If an expected XLSX is missing, the fetcher returns empty rows and the
au_monthly orchestrator surfaces a ``[AOFM STALE]`` banner via
``aofm_xlsx_age_days()``.
"""
from __future__ import annotations

import datetime
from pathlib import Path

from imdr.domains.econ.schema import IndicatorRow, ObservationRow

UTC = datetime.timezone.utc

_REPO_ROOT = Path(__file__).resolve().parents[4]
XLSX_DIR = _REPO_ROOT / "data" / "econ" / "au" / "aofm" / "xlsx"


def coerce_date(v) -> datetime.date | None:
    """Accept datetime/date/str/Timestamp; return ``date`` or ``None``."""
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    try:
        import pandas as pd
        if pd.isna(v):
            return None
        return pd.to_datetime(v).date()
    except Exception:
        return None


def coerce_float(v) -> float | None:
    """Accept any cell; return float or None for blank/non-numeric (incl. 'TBA')."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            import math
            return float(v) if not math.isnan(float(v)) else None
        except Exception:
            return None
    try:
        import pandas as pd
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


def make_indicator(
    *, imdr_code: str, source_code: str, display_name: str,
    unit: str, frequency: str, category: str = "instr_outstand",
    is_sa: bool = False,
) -> IndicatorRow:
    return IndicatorRow(
        imdr_code=imdr_code, vendor_name="AOFM", source_code=source_code,
        display_name=display_name, unit=unit, frequency=frequency,
        country_iso="AU", category=category, is_seasonally_adjusted=is_sa,
    )


def make_observation(
    *, imdr_code: str, obs_date: datetime.date, value: float | None,
) -> ObservationRow:
    now = datetime.datetime.now(UTC)
    return ObservationRow(
        imdr_code=imdr_code, obs_date=obs_date, vintage=0,
        release_date=now, value=value, ingested_at=now,
    )


def xlsx_age_days() -> float | None:
    """Newest XLSX mtime in ``XLSX_DIR``, in days. ``None`` if dir empty/missing.

    Used by au_monthly._aofm_staleness_check to surface a ``[AOFM STALE]``
    banner when the user hasn't done a manual Edge refresh recently.
    """
    import time
    if not XLSX_DIR.exists():
        return None
    mtimes = [p.stat().st_mtime for p in XLSX_DIR.glob("*.xlsx")]
    if not mtimes:
        return None
    return (time.time() - max(mtimes)) / 86400.0
