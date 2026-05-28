"""Backfill classifier output (asset_class, country_id, context, tags)
for existing rows in ``research.dim_report`` that pre-date the
classifier pipeline.

Approach:

1. Find rows where ``context IS NULL`` — these were ingested before the
   classifier was wired in (rows 1–142 today).
2. Group by vendor + date span; per vendor, re-run
   ``discover_reports(since=min_date, until=max_date)`` once.
   Discovery is read-only against the vendor's listing API; no PDFs
   are fetched, no SharePoint touched.
3. For each existing row, extract the 8-char uuid stub from
   ``pdf_path`` and look it up in the discovery map.
4. If matched: call the vendor's classifier on the enriched ReportRef,
   then UPDATE the row + replace its tags (DELETE + bulk INSERT for
   idempotency on re-run).

Misses (uuid not in current discovery) are reported but left as-is —
the listing API's retention window is the natural bound.

    python playground/research/backfill_classifier.py             # dry-run
    python playground/research/backfill_classifier.py --apply     # write
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ingest._console import force_utf8_stdout  # noqa: E402

# Force stdout/stderr to UTF-8 before any print() so a non-cp1252 char in
# a report title can't crash the run when output is piped to Tee-Object.
force_utf8_stdout()


# ---------------------------------------------------------------------
# Vendor → discover() lookup (mirrors orchestrator's registry, kept
# simple inline so this script can be read top-to-bottom).
# ---------------------------------------------------------------------

VENDOR_CODES = ("anz", "barclays", "goldman", "hsbc", "ms", "nomura")


def _discover_fn(code: str):
    if code == "anz":
        from ingest.crawler_anz import discover_reports
    elif code == "barclays":
        from ingest.crawler_barclays import discover_reports
    elif code == "goldman":
        from ingest.crawler_goldman import discover_reports
    elif code == "hsbc":
        from ingest.crawler_hsbc import discover_reports
    elif code == "ms":
        from ingest.crawler_ms import discover_reports
    elif code == "nomura":
        from ingest.crawler_nomura import discover_reports
    else:
        raise ValueError(f"unknown vendor: {code}")
    return discover_reports


def _short_uuid(uuid: str) -> str:
    """Same algorithm as ingest.paths.short_uuid — first 8 chars of the
    first dash-segment, or the full id if shorter than 8.
    """
    if not uuid:
        return ""
    head = uuid.split("-", 1)[0]
    return head if len(head) <= 8 else head[:8]


_PATH_UUID_RE = re.compile(r"_([A-Za-z0-9]{1,8})\.pdf$")


def _uuid_from_pdf_path(pdf_path: str) -> str:
    """Pull the trailing ``_{uuid8}.pdf`` stub from a SharePoint path."""
    m = _PATH_UUID_RE.search(pdf_path or "")
    return m.group(1) if m else ""


# ---------------------------------------------------------------------
# Engine + DB helpers
# ---------------------------------------------------------------------

def _engine():
    from sqlalchemy import create_engine

    from imdr.config.settings import get_settings
    s = get_settings()
    url = (
        f"mssql+pyodbc://@{s.mssql_host}:{s.mssql_port}/{s.mssql_database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes"
        "&LoginTimeout=60"
    )
    return create_engine(
        url, pool_size=2, max_overflow=2, pool_pre_ping=True,
        echo=False, fast_executemany=True,
    )


def _fetch_rows_to_backfill(engine):
    """Return rows missing classifier output, grouped by vendor.

    Returns dict: vendor_code → list of (id, publish_date, pdf_path,
    title, asset_class_stale, authors).

    ``asset_class_stale`` is the value stored under the OLD code path —
    on those vendors that used pubtype-as-asset-class, it carries the
    vendor's raw publication_type string. The fallback path uses this
    when the uuid match against re-discovery fails.
    """
    from sqlalchemy import text
    # Pick up rows that are missing context OR have empty asset_class.
    # Re-running is idempotent (DELETE+INSERT for tags, UPDATE for the
    # dim_report cols) so it's safe to widen the net after classifier
    # rule improvements.
    sql = text(
        """
        SELECT r.id, v.vendor_code, r.publish_date, r.pdf_path, r.title,
               r.asset_class, r.authors
          FROM research.dim_report r
          JOIN dbo.dim_vendor v ON v.id = r.vendor_id
         WHERE r.context IS NULL OR r.asset_class = ''
         ORDER BY v.vendor_code, r.publish_date, r.id
        """
    )
    by_vendor: dict[str, list[tuple]] = defaultdict(list)
    with engine.connect() as conn:
        for row in conn.execute(sql).all():
            by_vendor[row[1]].append(
                (row[0], row[2], row[3], row[4], row[5], row[6])
            )
    return dict(by_vendor)


class _StaleRef:
    """Minimal ref object reconstructed from DB columns for fallback
    classification when the live listing API no longer has the report.

    All vendor-specific extras (Goldman aemTags, Barclays L1_BRANDING,
    Nomura regions[], etc.) are unavailable — classifiers fall back to
    title/publication_type-only signal in that case.
    """
    def __init__(self, *, title: str, publish_date,
                 publication_type: str, analysts: str = "") -> None:
        self.title = title
        self.publish_date = publish_date
        self.publication_type = publication_type
        self.analysts = analysts
        self.uuid = ""


def _update_report(conn, *, report_id: int, asset_class: str,
                   country_code: str | None, context: str) -> None:
    """UPDATE one dim_report row's classifier fields."""
    from sqlalchemy import text

    from ingest.db import _resolve_country_id

    country_id = _resolve_country_id(conn, country_code)
    conn.execute(
        text(
            """
            UPDATE research.dim_report
               SET asset_class = :asset_class,
                   country_id  = :country_id,
                   context     = :context,
                   updated_at  = SYSDATETIMEOFFSET()
             WHERE id = :id
            """
        ),
        {
            "asset_class": (asset_class or "")[:30],
            "country_id":  country_id,
            "context":     (context or "").strip() or None,
            "id":          report_id,
        },
    )


def _replace_tags(conn, *, report_id: int, tags) -> int:
    """Atomic-ish: DELETE existing map rows for this report, then
    upsert the new tag set. Returns count of map rows written.
    """
    from sqlalchemy import text

    from ingest.db import _bulk_insert_report_tags

    conn.execute(
        text("DELETE FROM research.map_report_tag WHERE report_id = :rid"),
        {"rid": report_id},
    )
    payload = tuple((t.category, t.value) for t in tags)
    return _bulk_insert_report_tags(conn, report_id, payload)


# ---------------------------------------------------------------------
# Per-vendor backfill
# ---------------------------------------------------------------------

async def _backfill_vendor(
    vendor_code: str, rows: list[tuple], *, engine, apply_writes: bool,
    llm_fallback: bool = False, llm_api_key: str = "",
) -> dict:
    from ingest.classifiers import get_classifier
    from ingest.classifiers.llm import classify_with_llm
    from sqlalchemy import text  # noqa: F401  (kept for inline use)

    if not rows:
        return {"vendor": vendor_code, "n_rows": 0, "matched": 0,
                "missed": 0, "wrote": 0}

    # Tighten the discovery window to the actual span of rows.
    dates = [r[1] for r in rows]
    since = min(dates)
    until = max(dates)
    print(f"  re-discovering {vendor_code}: {since} .. {until} "
          f"({len(rows)} rows to backfill)")

    profile = HERE / "profiles" / vendor_code
    profile.mkdir(parents=True, exist_ok=True)
    discover = _discover_fn(vendor_code)

    try:
        refs = await discover(profile, since=since, until=until)
    except BaseException as exc:  # noqa: BLE001
        print(f"  [ERROR] discover failed for {vendor_code}: "
              f"{type(exc).__name__}: {exc}")
        return {"vendor": vendor_code, "n_rows": len(rows), "matched": 0,
                "missed": len(rows), "wrote": 0, "error": str(exc)}

    # Build uuid8 → ref index. ``_short_uuid`` returns variable-length
    # output (7 chars for Nomura's 7-digit ids, 8 for everything else),
    # while the path-extraction regex always greedy-matches up to 8 chars
    # before .pdf. We index refs by both their short_uuid AND its first
    # 7 chars so a 7-digit Nomura id matches an 8-char path stub.
    by_short: dict[str, object] = {}
    collisions: dict[str, int] = defaultdict(int)
    for r in refs:
        short = _short_uuid(getattr(r, "uuid", "") or "")
        if not short:
            continue
        collisions[short] += 1
        if short not in by_short:
            by_short[short] = r
        if len(short) >= 7 and short[:7] not in by_short:
            # Prefix index — only filled if no full-key entry exists.
            by_short.setdefault(short[:7], r)
    n_collisions = sum(1 for c in collisions.values() if c > 1)
    if n_collisions:
        print(f"  note: {n_collisions} uuid8 collisions among "
              f"{len(refs)} refs — first-seen wins")

    classify = get_classifier(vendor_code)

    matched = wrote = missed = fallback = llm_wins = 0
    miss_examples: list[str] = []
    with engine.begin() as conn:
        for (report_id, pdate, pdf_path, title,
             stale_asset_class, stale_authors) in rows:
            short = _uuid_from_pdf_path(pdf_path)
            ref = by_short.get(short) if short else None
            # Fallback: try the first 7 chars (handles the Nomura
            # 7-digit-id vs 8-char-path-stub case).
            if ref is None and len(short) >= 7:
                ref = by_short.get(short[:7])
            if ref is None:
                # DB-only fallback — build a synthetic ref from columns
                # we have. Vendor-specific extras (aemTags, regions[],
                # L1_BRANDING) are unavailable; classifier returns what
                # it can from title + publication_type alone.
                ref = _StaleRef(
                    title=title or "",
                    publish_date=pdate,
                    publication_type=stale_asset_class or "",
                    analysts=stale_authors or "",
                )
                fallback += 1
                if len(miss_examples) < 3:
                    miss_examples.append(f"id={report_id} uuid8={short!r} "
                                         f"title={(title or '')[:40]!r} "
                                         f"(stale-fallback)")
            else:
                matched += 1
            result = classify(ref)

            # LLM fallback for residuals: when rule-based asset_class
            # is empty AND --llm-fallback is on, call Gemini. Merge the
            # LLM's asset_class + country + extra tags into the rule
            # result; keep the rule-rendered context untouched.
            if (
                llm_fallback
                and not result.asset_class
                and llm_api_key
            ):
                llm_res = classify_with_llm(
                    vendor_code=vendor_code,
                    title=getattr(ref, "title", "") or "",
                    pubtype=getattr(ref, "publication_type", "") or "",
                    abstract=getattr(ref, "abstract", "") or "",
                    api_key=llm_api_key,
                )
                if llm_res is not None:
                    if llm_res.asset_class:
                        result.asset_class = llm_res.asset_class
                        llm_wins += 1
                    if llm_res.country_code and not result.country_code:
                        result.country_code = llm_res.country_code
                    # Append LLM-emitted tags (themes, country,
                    # classifier_source) — _replace_tags will de-dupe.
                    merged_tags = list(result.tags) + list(llm_res.tags)
                    result.tags = merged_tags
            if not apply_writes:
                continue
            _update_report(
                conn,
                report_id=report_id,
                asset_class=result.asset_class,
                country_code=result.country_code,
                context=result.context,
            )
            _replace_tags(conn, report_id=report_id, tags=result.tags)
            wrote += 1
    missed = 0  # nothing is truly "missed" now — fallback always classifies

    print(f"  {vendor_code}: matched={matched}/{len(rows)}  "
          f"fallback={fallback}  "
          f"llm_filled={llm_wins}  "
          f"{'wrote' if apply_writes else 'would_write'}"
          f"={wrote if apply_writes else (matched + fallback)}")
    for m in miss_examples:
        print(f"    [miss] {m}")
    return {"vendor": vendor_code, "n_rows": len(rows),
            "matched": matched, "fallback": fallback,
            "missed": missed, "wrote": wrote, "llm_wins": llm_wins}


async def _amain(args) -> int:
    engine = _engine()
    by_vendor = _fetch_rows_to_backfill(engine)
    total_pending = sum(len(rs) for rs in by_vendor.values())
    print(f"backfill candidates: {total_pending} rows across "
          f"{len(by_vendor)} vendor(s)")
    if args.vendors.strip():
        wanted = {v.strip().lower() for v in args.vendors.split(",")}
        by_vendor = {k: v for k, v in by_vendor.items() if k in wanted}
        print(f"  filtered to vendors: {sorted(by_vendor)}")

    llm_api_key = ""
    if args.llm_fallback:
        from imdr.config.settings import get_settings
        llm_api_key = (get_settings().gemini_key or "").strip()
        if not llm_api_key:
            raise SystemExit(
                "--llm-fallback requires IMDR_GEMINI_KEY (or "
                "settings.gemini_key) — not set"
            )
        print(f"  llm fallback: ON  (model="
              f"{os.environ.get('IMDR_RESEARCH_LLM_CLASSIFY_MODEL', 'gemini-2.0-flash')})")
    print()

    summaries = []
    for code in sorted(by_vendor):
        s = await _backfill_vendor(
            code, by_vendor[code], engine=engine,
            apply_writes=args.apply,
            llm_fallback=args.llm_fallback,
            llm_api_key=llm_api_key,
        )
        summaries.append(s)
        print()

    print("=" * 72)
    print(f"  {'vendor':<10} {'rows':>6} {'matched':>8} {'fallback':>10} "
          f"{'wrote':>8}")
    print("  " + "-" * 60)
    for s in summaries:
        print(f"  {s['vendor']:<10} {s['n_rows']:>6} {s['matched']:>8} "
              f"{s.get('fallback', 0):>10} {s['wrote']:>8}")
    if not args.apply:
        print()
        print("  DRY RUN — pass --apply to write")
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="Actually UPDATE the rows. Without this it's a dry-run.")
    p.add_argument("--vendors", default="",
                   help="Comma-separated subset (anz,barclays,...). "
                        "Default: all vendors with pending rows.")
    p.add_argument("--llm-fallback", action="store_true",
                   help="When the rule-based classifier returns no "
                        "asset_class, call Gemini. Costs ~$0.0001/report "
                        "and is cached on disk. Requires IMDR_GEMINI_KEY.")
    args = p.parse_args()
    sys.exit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
