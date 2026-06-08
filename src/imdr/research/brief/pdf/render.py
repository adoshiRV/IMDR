"""Render specific pages from bank PDFs (local OneDrive mirror) to PNG.

The caller passes a mapping ``{report_id: [page1, page2, ...]}``. We
resolve each ``report_id`` to its ``pdf_path`` via
:func:`imdr.research.brief.data.load_report_refs`, open the PDF with
PyMuPDF, and render each page at the configured DPI.

Output filename convention::

    {report_id:04d}_{vendor}_p{page:02d}.png
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import fitz                                                                # PyMuPDF
import structlog

from .._paths import LOCAL_IMDR_ROOT
from ..data.reports import ReportRef


log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PageRender:
    report_id: int
    vendor: str
    page: int                                                                 # 1-indexed
    path: Path                                                                # PNG output


def render_pages(
    refs: Mapping[int, ReportRef],
    pages: Mapping[int, Sequence[int]],
    out_dir: Path,
    *,
    dpi: int = 180,
) -> tuple[list[PageRender], list[tuple[int, str]]]:
    """Render the requested pages to ``out_dir``.

    Returns ``(rendered, skipped)`` where ``skipped`` is a list of
    ``(report_id, reason)`` so callers can show what failed without raising.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[PageRender] = []
    skipped: list[tuple[int, str]] = []

    for rid, page_list in pages.items():
        ref = refs.get(rid)
        if ref is None:
            skipped.append((rid, "no DB row"))
            continue
        pdf_path = LOCAL_IMDR_ROOT / Path(*ref.pdf_path.split("/"))
        if not pdf_path.exists():
            skipped.append((rid, f"missing file {pdf_path}"))
            continue
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            skipped.append((rid, f"open failed: {e}"))
            continue
        for p in page_list:
            if p < 1 or p > doc.page_count:
                skipped.append((rid, f"page {p} out of range (total {doc.page_count})"))
                continue
            page = doc[p - 1]
            mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            out_name = f"{rid:04d}_{ref.vendor}_p{p:02d}.png"
            out_path = out_dir / out_name
            pix.save(str(out_path))
            rendered.append(PageRender(rid, ref.vendor, p, out_path))
            log.debug("pdf-page-rendered", report_id=rid, page=p, vendor=ref.vendor)
        doc.close()

    return rendered, skipped
