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

# Pre-cutover tree. Still refreshed by the R pipeline, and the ONLY place the
# onshore EM forward curves exist: BBG_mirror\FX was provisioned with 22
# currency folders and no CNY/CNO/MYO/IDO, so those pairs went dark the day
# the FX feed cut over to the mirror -- last obs 2026-04-24 against a mirror
# created 2026-04-28. Read-only, exactly like the mirror.
BBG_LEGACY_ROOT = Path(r"Z:\Business\Research\Dashboard\DataSources\BBG")
BBG_LEGACY_FX_ROOT = BBG_LEGACY_ROOT / "FX"

# Onshore EM ccys served from the legacy tree instead of the mirror.
#
# CNO is deliberately ABSENT. Its file labels tenors ``FX_CNY_*`` while its
# folder is ``CNO``, so ``alias_to_tenor`` rejects every row -- which is why
# USD/CNO has never held a single fact row, before or after the cutover.
# Including it here would acquire the file just to skip all of it and log a
# warning per run. Making CNO work needs an explicit per-ccy tenor alias in
# the extractor; that is a new curve, not part of restoring this outage.
ONSHORE_FX_CCYS: tuple[str, ...] = ("CNY", "IDO", "MYO")

# Shared rates glob shape — 4 BBG rates domains, one PAR CSV per curve folder.
RATES_KINDS: tuple[str, ...] = ("IRS", "OIS", "BASIS", "CCS")
RATES_PATTERNS: list[str] = [f"{k}/*/PAR/{k}_PAR_*.csv" for k in RATES_KINDS]


def _fx_ccys_from_universe() -> list[str]:
    """Non-USD leg of every FX rate pair in the universe, sorted."""
    from imdr.universe.fx import get_fx_universe

    universe = get_fx_universe()
    return sorted({
        quote if base == "USD" else base
        for base, quote in universe.fx_rate_pairs()
    })


def fx_patterns_from_universe() -> list[str]:
    """Per-pair FX glob patterns for the MIRROR root.

    BBG names files by the non-USD leg (``FX_{CCY}.csv`` per pair); the
    universe's ``fx_rate_pairs()`` already enumerates the pairs we want.
    Used by both ``bbg_fx_snapshot`` and ``bbg_fx_daily`` specs.

    The onshore ccys are excluded because the mirror has no folder for them --
    asking for them here matched nothing and logged a silent
    ``bbg_source_file_missing`` warning on every run. They come from
    ``onshore_fx_extra_source()`` instead.
    """
    return [
        f"{ccy}/FX_{ccy}.csv"
        for ccy in _fx_ccys_from_universe()
        if ccy not in ONSHORE_FX_CCYS and ccy != "CNO"
    ]


def onshore_fx_extra_source() -> tuple[tuple[Path, tuple[str, ...]], ...]:
    """``extra_sources`` entry pulling the onshore ccys from the legacy tree.

    Restricted to ``ONSHORE_FX_CCYS`` so the legacy tree's other folders --
    including the unparseable ``CNO`` and the untracked ``KRO`` -- are not
    acquired. Only ccys actually in the universe are requested, so dropping a
    pair from ``fx.yml`` stops asking for its file without a second edit here.
    """
    in_universe = set(_fx_ccys_from_universe())
    patterns = tuple(
        f"{ccy}/FX_{ccy}.csv"
        for ccy in ONSHORE_FX_CCYS
        if ccy in in_universe
    )
    if not patterns:
        return ()
    return ((BBG_LEGACY_FX_ROOT, patterns),)


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
    extra_sources: tuple[tuple[Path, tuple[str, ...]], ...] = (),
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
        extra_sources=extra_sources,
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
