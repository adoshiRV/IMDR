"""Filesystem conventions for the macro brief module.

Output layout::

    data/daily_research_summary/
      weekly/{YYYY}/{MM}/{DD}/
        weekly_preview.html
        assets/             (rv_theme.css + RV_Logo_Colour.png, copied for portability)
        charts/
        bank_pdfs/
        _report_links.json
        _audit.json
      daily/{YYYY}/{MM}/{DD}/
        daily_brief.html
        assets/
        charts/
        _report_links.json
        _audit.json

Date is the *period anchor* — the Friday-prior for a weekly brief, or
today for a daily brief.

The folder name is a holdover from when this directory only held the
ad-hoc daily-research markdown. Both weekly and daily briefs now live
under it as ``weekly/`` and ``daily/`` siblings.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

BriefType = Literal["weekly", "daily"]

# Repo-relative root; deliberately not absolute so the module is portable.
_OUTPUT_ROOT = Path("data/daily_research_summary")

# Local OneDrive mirror of TradeKnowledgeCore/ResearchData1/IMDR/.
# Same root the ingest pipeline writes to (see playground/research/ingest/upload.py).
LOCAL_IMDR_ROOT = Path(
    r"C:\Users\adoshi\OneDrive - RV Capital Management Private Ltd"
    r"\Trade Knowledge Core - IMDR"
)

# SharePoint web-URL base for direct PDF links.
SHAREPOINT_BASE = (
    "https://itbillingrvcapitalfunds.sharepoint.com"
    "/teams/TradeKnowledgeCore/ResearchData1/IMDR"
)


def output_dir(brief_type: BriefType, anchor: date) -> Path:
    """Return the output directory for a given brief type + date."""
    return _OUTPUT_ROOT / brief_type / f"{anchor:%Y}" / f"{anchor:%m}" / f"{anchor:%d}"


def output_path(brief_type: BriefType, anchor: date) -> Path:
    """Final HTML path."""
    name = "weekly_preview.html" if brief_type == "weekly" else "daily_brief.html"
    return output_dir(brief_type, anchor) / name


def charts_dir(brief_type: BriefType, anchor: date) -> Path:
    return output_dir(brief_type, anchor) / "charts"


def bank_pdfs_dir(brief_type: BriefType, anchor: date) -> Path:
    return output_dir(brief_type, anchor) / "bank_pdfs"


def report_links_path(brief_type: BriefType, anchor: date) -> Path:
    return output_dir(brief_type, anchor) / "_report_links.json"


def audit_path(brief_type: BriefType, anchor: date) -> Path:
    return output_dir(brief_type, anchor) / "_audit.json"
