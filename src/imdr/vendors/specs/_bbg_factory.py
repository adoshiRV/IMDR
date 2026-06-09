"""Shared factories for BBG vendor specs.

All four BBG VendorFeeds (FX snapshot / FX daily / rates snapshot /
rates daily) build the same shape:

  - ``LocalFilesystemSpec`` rooted under ``Z:\\BBG_mirror\\``
  - ``LocalFilesystemAcquirer`` wrapping the spec
  - ``min_mtime_age=72h``, ``min_matches=N//2`` (or 15 for rates)
  - ``archive_after_load=False`` (R pipeline owns the source tree)
  - ``email_on_zero_rows=False`` (idempotent re-fires shouldn't email)

This factory collapses that boilerplate so each ``vendors/specs/bbg_*``
module just supplies the per-feed bits: pipeline_builder, formatter,
success_context_builder, staleness pipeline name, and the source
patterns.

Module name is underscore-prefixed so ``vendors/specs/__init__.py`` —
which imports each spec module by name to register it — won't pick
this up as a feed.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any, Callable

from imdr.vendors.acquirers.filesystem import (
    LocalFilesystemAcquirer,
    LocalFilesystemSpec,
)
from imdr.vendors.base import PipelineBuilder, VendorFeed
from imdr.notifications.formatters.base import EmailFormatter

VENDOR_CODE = "BBG"
DEFAULT_MIN_MTIME_AGE = timedelta(hours=72)

# Filesystem layout under Z:\BBG_mirror\.
BBG_MIRROR_ROOT = Path(r"Z:\Business\Research\Dashboard\DataSources\BBG_mirror")
BBG_FX_ROOT = BBG_MIRROR_ROOT / "FX"

# Shared rates glob shape — 4 BBG rates domains, one PAR CSV per curve folder.
RATES_KINDS: tuple[str, ...] = ("IRS", "OIS", "BASIS", "CCS")
RATES_PATTERNS: list[str] = [f"{k}/*/PAR/{k}_PAR_*.csv" for k in RATES_KINDS]


def fx_patterns_from_universe() -> list[str]:
    """Build per-pair FX glob patterns from the IMDR universe.

    BBG names files by the non-USD leg (``FX_{CCY}.csv`` per pair); the
    universe's ``fx_rate_pairs()`` already enumerates the pairs we want.
    Used by both ``bbg_fx_snapshot`` and ``bbg_fx_daily`` specs.
    """
    from imdr.universe.fx import get_fx_universe

    universe = get_fx_universe()
    bbg_ccys = sorted({
        quote if base == "USD" else base
        for base, quote in universe.fx_rate_pairs()
    })
    return [f"{ccy}/FX_{ccy}.csv" for ccy in bbg_ccys]


def build_bbg_feed(
    *,
    name: str,
    root: Path,
    patterns: list[str],
    pipeline_builder: PipelineBuilder,
    success_formatter: EmailFormatter,
    staleness_pipeline_name: str,
    success_context_builder: Callable[[Any, int], dict[str, Any]],
    min_matches: int,
    min_mtime_age: timedelta = DEFAULT_MIN_MTIME_AGE,
) -> tuple[LocalFilesystemSpec, VendorFeed]:
    """Assemble (SPEC, FEED) for a BBG_mirror-backed feed.

    The two ``False`` flags are intentional and should never be flipped:
      * ``archive_after_load=False`` — R pipeline overwrites the source
        files in place; archiving them breaks the next fire.
      * ``email_on_zero_rows=False`` — idempotent re-fires within the
        same BBG batch window land 0 rows; emailing on every one would
        be spam.

    Each lock-in test (``tests/unit/test_vendors/test_bbg_no_move.py``)
    asserts these stay False on every registered BBG feed.
    """
    spec = LocalFilesystemSpec(
        name=name,
        vendor_code=VENDOR_CODE,
        root=root,
        patterns=patterns,
        min_mtime_age=min_mtime_age,
        min_matches=min_matches,
    )
    feed = VendorFeed(
        name=name,
        vendor_code=VENDOR_CODE,
        acquirer=LocalFilesystemAcquirer(spec),
        pipeline_builder=pipeline_builder,
        success_formatter=success_formatter,
        staleness_pipeline_name=staleness_pipeline_name,
        success_context_builder=success_context_builder,
        archive_after_load=False,
        email_on_zero_rows=False,
    )
    return spec, feed


def fx_success_context(
    pipeline: Any, rows_loaded: int, *, mode_label: str, frequency: str
) -> dict[str, Any]:
    """Per-pair breakdown for BBG FX feeds (snapshot + daily share this shape).

    Reads ``pipeline._raw_df`` (set by both BBG FX pipelines) and groups
    by ``(base_ccy, quote_ccy)``, surfacing the latest ``obs_ts`` so the
    email recipient can see which BBG batch we just captured.
    """
    pair_data: list[dict[str, Any]] = []
    df = getattr(pipeline, "_raw_df", None)
    run_date = None
    if df is not None and not df.empty:
        for (base, quote), grp in df.groupby(["base_ccy", "quote_ccy"]):
            pair_data.append({
                "pair": f"{base}{quote}",
                "ccy_class": "g10",
                "n_obs": int(len(grp)),
                "n_tenors": int(grp["tenor"].nunique()),
                "latest_obs_ts": grp["obs_ts"].max().isoformat()
                                  if not grp["obs_ts"].isna().all() else None,
            })
        latest = df["obs_date"].max() if "obs_date" in df.columns else None
        if latest is not None:
            run_date = (
                latest.to_pydatetime() if hasattr(latest, "to_pydatetime") else latest
            )
    ctx: dict[str, Any] = {
        "pair_data": pair_data,
        "n_pairs": len(pair_data),
        "mode": mode_label,
        "frequency": frequency,
    }
    if run_date is not None:
        ctx["run_date"] = run_date
    return ctx


def rates_success_context(
    pipeline: Any, rows_loaded: int, *, mode_label: str, frequency: str
) -> dict[str, Any]:
    """Per-curve breakdown for BBG rates feeds (snapshot + daily share this shape).

    Reads ``pipeline._raw_df`` (set by both BBG rates pipelines) and
    groups by ``(ccy, curve)``. Surfaces tenor count + observed quotes
    so the email recipient sees which curves landed.
    """
    curves: list[dict[str, Any]] = []
    df = getattr(pipeline, "_raw_df", None)
    if df is not None and not df.empty:
        for (ccy, curve), grp in df.groupby(["ccy", "curve"]):
            curves.append({
                "ccy": ccy,
                "curve": curve,
                "status": "active",
                "tenors": int(grp["tenor"].nunique()),
                "quotes": list(grp["quote"].unique()),
                "rows": int(len(grp)),
                "classification": "BBG",
            })
    return {
        "curves": curves,
        "n_curves": len(curves),
        "mode": mode_label,
        "frequency": frequency,
    }
