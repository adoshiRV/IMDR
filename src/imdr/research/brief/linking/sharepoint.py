"""SharePoint URL composition from `research.dim_report.pdf_path`.

The IMDR folder syncs locally via OneDrive. The web-canonical URL for a
file at ``IMDR/{rel}`` is :const:`SHAREPOINT_BASE` + ``/`` + URL-encoded
``{rel}``. We emit two variants:

- ``sp_url``     — direct file URL; SharePoint will preview the PDF.
- ``folder_url`` — opens the parent folder view in SharePoint web.
"""
from __future__ import annotations

from typing import Mapping
from urllib.parse import quote

from .._paths import SHAREPOINT_BASE
from ..data.reports import ReportRef


_FOLDER_VIEW = (
    "https://itbillingrvcapitalfunds.sharepoint.com/teams/TradeKnowledgeCore"
    "/ResearchData1/Forms/AllItems.aspx?id="
)


def sharepoint_url(pdf_relpath: str) -> str:
    """Direct PDF URL on SharePoint (web preview / download)."""
    rel = pdf_relpath.replace("\\", "/")
    return f"{SHAREPOINT_BASE}/{quote(rel, safe='/')}"


def sharepoint_folder_url(pdf_relpath: str) -> str:
    """SharePoint folder-view URL for the folder containing the file."""
    rel = pdf_relpath.replace("\\", "/")
    folder_rel = "/".join(rel.split("/")[:-1])
    return f"{_FOLDER_VIEW}{quote('/teams/TradeKnowledgeCore/ResearchData1/IMDR/' + folder_rel, safe='')}"


def build_report_links(refs: Mapping[int, ReportRef]) -> dict[str, dict[str, str]]:
    """Return ``{str(rid): {vendor, title, pdf_path, sp_url, folder_url}}``.

    Keys are string-typed so the resulting dict is directly usable from
    Jinja templates (``{{ report_links["4694"].sp_url }}``).
    """
    return {
        str(rid): {
            "vendor": ref.vendor,
            "title": ref.title,
            "pdf_path": ref.pdf_path,
            "sp_url": sharepoint_url(ref.pdf_path),
            "folder_url": sharepoint_folder_url(ref.pdf_path),
        }
        for rid, ref in refs.items()
    }
