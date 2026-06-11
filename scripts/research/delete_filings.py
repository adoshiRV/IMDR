"""Delete one or more research filings cleanly.

Removes every trace of a ``research.dim_report`` row:

  1. Qdrant vectors — filter ``payload.report_id == X`` across every
     collection.
  2. ``research.fact_chunk`` rows — FK on ``report_id``.
  3. ``research.dim_report`` row.
  4. Local SharePoint PDF under ``LOCAL_IMDR_ROOT / pdf_path`` (the
     OneDrive client propagates the delete to SharePoint).

Use cases: removing noise items caught after the discovery filter was
tightened, removing a vendor-replaced report (vendor reused the same
slug for new bytes), removing a hand-curated mistake.

NOT a vendor-cascade delete — this only removes the listed report IDs.
seen.json under ``data/econ/{cc}/govt/{vendor}/`` is NOT touched, so
the orchestrator will NOT re-ingest the same source_url. If you want
to allow re-ingest, edit seen.json manually.

Usage:
    python -m scripts.research.delete_filings --ids 7907 7920 7944 7954 7958
    python -m scripts.research.delete_filings --ids 7907 --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from imdr.config.settings import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLAYGROUND = _REPO_ROOT / "playground"
if str(_PLAYGROUND) not in sys.path:
    sys.path.insert(0, str(_PLAYGROUND))

from research.ingest.qdrant_writer import QdrantWriter  # noqa: E402
from research.ingest.upload import LOCAL_IMDR_ROOT  # noqa: E402


def _engine():
    s = get_settings()
    url = (
        f"mssql+pyodbc://@{s.mssql_host}:{s.mssql_port}/{s.mssql_database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes"
        "&LoginTimeout=60"
    )
    return create_engine(url, pool_pre_ping=True, fast_executemany=True)


def _delete_qdrant_points(writer: QdrantWriter, report_id: int) -> dict[str, int]:
    """Delete every point with payload.report_id == report_id across all collections.

    Returns ``{collection: deleted_count}``. Counts come from Qdrant's
    delete response when available; otherwise the post-delete recount.
    """
    from qdrant_client.http import models as qm

    out: dict[str, int] = {}
    try:
        collections = [c.name for c in writer._client.get_collections().collections]
    except Exception as exc:
        print(f"  WARN  could not list Qdrant collections: {exc!s:.120}")
        return out

    for name in collections:
        filt = qm.Filter(must=[
            qm.FieldCondition(key="report_id", match=qm.MatchValue(value=int(report_id)))
        ])
        # Count first so we know what we're deleting.
        try:
            pre = writer._client.count(
                collection_name=name, count_filter=filt, exact=True
            ).count
        except Exception as exc:
            print(f"  WARN  count {name} failed: {exc!s:.120}")
            continue
        if pre == 0:
            continue
        writer._client.delete(
            collection_name=name,
            points_selector=qm.FilterSelector(filter=filt),
            wait=True,
        )
        out[name] = int(pre)
    return out


def _delete_local_pdf(pdf_path: str) -> tuple[bool, str]:
    """Delete the local-OneDrive PDF mirror. Returns (deleted, message)."""
    if not pdf_path:
        return False, "(no pdf_path on dim_report row)"
    if pdf_path.startswith(("/", "\\")) or ".." in pdf_path.replace("\\", "/").split("/"):
        return False, f"unsafe pdf_path refused: {pdf_path!r}"
    target = (LOCAL_IMDR_ROOT / pdf_path).resolve()
    root = LOCAL_IMDR_ROOT.resolve()
    if root not in target.parents and target != root:
        return False, f"refused delete outside IMDR root: {target}"
    if not target.exists():
        return False, f"(file not on disk: {target})"
    try:
        target.unlink()
        return True, str(target)
    except OSError as exc:
        return False, f"OS error deleting {target}: {exc!s}"


def _delete_one(eng, writer: QdrantWriter, report_id: int, dry: bool) -> dict:
    """Plan + execute a clean delete of one report. Returns a status dict."""
    with eng.connect() as conn:
        row = conn.execute(
            text("""
                SELECT r.id, r.title, r.pdf_path,
                       v.vendor_code,
                       (SELECT COUNT(*) FROM research.fact_chunk c WHERE c.report_id = r.id) AS chunks
                FROM research.dim_report r
                JOIN dbo.dim_vendor v ON v.id = r.vendor_id
                WHERE r.id = :rid
            """),
            {"rid": report_id},
        ).first()
    if row is None:
        return {"id": report_id, "status": "not_found"}

    print(f"\n[report_id={report_id}] {row.vendor_code} — {row.title[:100]}")
    print(f"  pdf_path : {row.pdf_path}")
    print(f"  chunks   : {row.chunks}")

    if dry:
        # Probe Qdrant + filesystem so the dry-run gives a real plan.
        from qdrant_client.http import models as qm
        for name in (c.name for c in writer._client.get_collections().collections):
            filt = qm.Filter(must=[
                qm.FieldCondition(key="report_id",
                                  match=qm.MatchValue(value=int(report_id)))
            ])
            try:
                n = writer._client.count(
                    collection_name=name, count_filter=filt, exact=True
                ).count
            except Exception:
                n = -1
            print(f"  qdrant   : {name}  would-delete={n}")
        target = (LOCAL_IMDR_ROOT / row.pdf_path).resolve() if row.pdf_path else None
        if target:
            exists = target.exists()
            print(f"  pdf file : {target}  exists={exists}")
        return {"id": report_id, "status": "planned",
                "chunks": int(row.chunks), "vendor_code": row.vendor_code,
                "pdf_path": row.pdf_path}

    # 1) Qdrant points
    qdr_deleted = _delete_qdrant_points(writer, report_id)
    for name, n in qdr_deleted.items():
        print(f"  qdrant   : deleted {n} point(s) from {name}")

    # 2) Child FK rows + dim_report (single transaction, order matters).
    # Children FK'd to dim_report (see sys.foreign_keys probe 2026-06-11):
    #   research.fact_chunk           (one chunk per text segment)
    #   research.map_report_tag       (one row per emitted tag)
    #   research.map_report_market    (market-classification mapping)
    with eng.begin() as conn:
        tag_n = conn.execute(
            text("DELETE FROM research.map_report_tag WHERE report_id = :rid"),
            {"rid": report_id},
        ).rowcount
        market_n = conn.execute(
            text("DELETE FROM research.map_report_market WHERE report_id = :rid"),
            {"rid": report_id},
        ).rowcount
        chunk_n = conn.execute(
            text("DELETE FROM research.fact_chunk WHERE report_id = :rid"),
            {"rid": report_id},
        ).rowcount
        report_n = conn.execute(
            text("DELETE FROM research.dim_report WHERE id = :rid"),
            {"rid": report_id},
        ).rowcount
    print(f"  fact_chk : deleted {chunk_n} row(s)")
    print(f"  map_tag  : deleted {tag_n} row(s)")
    print(f"  map_mkt  : deleted {market_n} row(s)")
    print(f"  dim_repo : deleted {report_n} row(s)")

    # 3) local OneDrive PDF
    pdf_ok, pdf_msg = _delete_local_pdf(row.pdf_path)
    if pdf_ok:
        print(f"  pdf file : deleted {pdf_msg}")
    else:
        print(f"  pdf file : SKIPPED — {pdf_msg}")

    return {
        "id": report_id,
        "status": "deleted",
        "vendor_code": row.vendor_code,
        "chunks": int(row.chunks),
        "qdrant_deleted": qdr_deleted,
        "pdf_path": row.pdf_path,
        "pdf_deleted": pdf_ok,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--ids", nargs="+", type=int, required=True,
        help="research.dim_report.id values to delete",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="probe Qdrant + filesystem; don't delete anything",
    )
    args = ap.parse_args(argv)

    eng = _engine()
    writer = QdrantWriter.from_env()
    print(f"Qdrant mode: {writer.mode}")
    print(f"Local IMDR root: {LOCAL_IMDR_ROOT}")
    print(f"Target IDs: {args.ids}  (dry_run={args.dry_run})")

    results = [_delete_one(eng, writer, rid, args.dry_run) for rid in args.ids]

    eng.dispose()
    writer.close()

    n_ok = sum(1 for r in results if r["status"] == "deleted")
    n_planned = sum(1 for r in results if r["status"] == "planned")
    n_missing = sum(1 for r in results if r["status"] == "not_found")
    print(
        f"\n=== summary === deleted={n_ok} planned={n_planned} "
        f"not_found={n_missing} of {len(results)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
