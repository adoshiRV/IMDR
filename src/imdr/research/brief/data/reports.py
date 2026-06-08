"""Look up research.dim_report metadata for cited report IDs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class ReportRef:
    report_id: int
    vendor: str           # research.dim_vendor.vendor_code
    title: str
    pdf_path: str         # forward-slash relative


def load_report_refs(cx: Connection, report_ids: Iterable[int]) -> dict[int, ReportRef]:
    """Return ``{report_id: ReportRef}`` for every requested id present in IMDR.

    Missing IDs are simply omitted — caller decides how to handle.
    """
    ids = list(set(int(r) for r in report_ids))
    if not ids:
        return {}
    # safe to inline ints
    ids_sql = ",".join(str(i) for i in ids)
    rows = cx.execute(text(f"""
        SELECT r.id, v.vendor_code, r.pdf_path, r.title
        FROM research.dim_report r
        JOIN dbo.dim_vendor v ON v.id = r.vendor_id
        WHERE r.id IN ({ids_sql})
    """)).fetchall()
    return {
        int(r.id): ReportRef(
            report_id=int(r.id),
            vendor=r.vendor_code,
            title=r.title,
            pdf_path=r.pdf_path.replace("\\", "/"),
        )
        for r in rows
    }
