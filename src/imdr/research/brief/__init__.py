"""Macro research brief generator.

Produces RV-Capital-styled HTML briefs from IMDR data + research PDFs.
Two report types share a common design system, components, and pipeline:

  * **weekly** — Sunday/Monday preview of the trading week ahead (deep).
  * **daily**  — pre-open brief on today's prints + yesterday's surprises (lite).

Public surface::

    from imdr.research.brief import (
        WeeklyConfig, DailyConfig,           # YAML-mapped Pydantic models
        BriefPipeline,                       # orchestrator
        build_weekly, build_daily,           # convenience entry points
    )

CLI::

    python -m imdr.research.brief weekly --date 2026-06-08 --config <path>
    python -m imdr.research.brief daily  --date 2026-06-09 --config <path>

Each invocation is read-only against IMDR + the OneDrive PDF mirror; it
writes only under ``data/research_summaries/{weekly|daily}/{Y}/{M}/{D}/``.
"""
from __future__ import annotations

from .config import BriefConfig, DailyConfig, WeeklyConfig
from .pipeline import BriefPipeline, build_daily, build_weekly

__all__ = [
    "BriefConfig",
    "BriefPipeline",
    "DailyConfig",
    "WeeklyConfig",
    "build_daily",
    "build_weekly",
]
