"""Backfill research.dim_report.region + country_id from existing tags.

Discoverability fix: sell-side reports carry ``Tag('region', ...)`` and
``Tag('country', ...)`` (extracted by the per-vendor classifiers) but the
``region`` column is blank and ``country_id`` is NULL on most of them. That
makes well-covered topics (BoJ, RBA, ...) invisible to any region/country
filter even though the documents are present.

This script propagates the tag signal into the columns. It does NOT touch:

  * rows whose ``region`` column is already populated — those are the
    govt/econ filings tagged ``ASIA-EM`` / ``ASIA-DM`` (a separate vocab,
    no region tag), so the WHERE clause never selects them; and
  * rows whose ``country_id`` is already set.

Region tag vocab -> canonical column bucket (americas/emea/apac/latam/global,
per ingest/classifiers/canonical.py). A report with multiple distinct
regional buckets collapses to 'global'; a lone 'global' tag stays 'global';
an explicit regional tag wins over a co-occurring 'global' tag.

Country tag (2-char) -> dbo.dim_country.id. Only reports with exactly one
resolvable country code are set (multi-country is left NULL as ambiguous).

DRY-RUN by default. Pass --commit to write.

    python playground/research/backfill_region_country.py            # dry-run
    python playground/research/backfill_region_country.py --commit   # write
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from sqlalchemy import text

# Single source of truth for the region tag → column collapse — shared with
# the live ingest path (ingest_today.py builds dim_report.region this way).
from ingest.classifiers.canonical import region_from_tags


def _research_engine(settings):
    """Research-only engine on ODBC Driver 18 (same as ingest_one.py)."""
    from sqlalchemy import create_engine  # noqa: PLC0415

    url = (
        f"mssql+pyodbc://@{settings.mssql_host}:{settings.mssql_port}"
        f"/{settings.mssql_database}"
        f"?driver=ODBC+Driver+18+for+SQL+Server"
        f"&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes"
        f"&LoginTimeout=60"
    )
    return create_engine(url, pool_pre_ping=True, pool_timeout=60,
                         fast_executemany=True, connect_args={"timeout": 60})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true",
                    help="write the UPDATEs (default: dry-run, report only)")
    args = ap.parse_args()

    from imdr.config.settings import get_settings  # noqa: PLC0415

    engine = _research_engine(get_settings())

    with engine.begin() as conn:
        # dim_country code -> id
        country_id_by_code = {
            code: cid for cid, code in conn.execute(
                text("SELECT id, country_code FROM dbo.dim_country")
            )
        }

        # ── region: reports with blank column + a region tag ──────────────
        region_rows = conn.execute(text(
            """
            SELECT m.report_id, t.tag
            FROM research.dim_report r
            JOIN research.map_report_tag m ON m.report_id = r.id
            JOIN research.dim_tag t ON t.id = m.tag_id AND t.tag_category = 'region'
            WHERE r.region = ''
            """
        )).fetchall()
        region_tags: dict[int, set[str]] = defaultdict(set)
        for rid, tag in region_rows:
            region_tags[rid].add(tag)
        region_updates = {
            rid: val for rid, tags in region_tags.items()
            if (val := region_from_tags(("region", t) for t in tags))
        }

        # ── country: reports with NULL country_id + exactly 1 resolvable tag
        country_rows = conn.execute(text(
            """
            SELECT m.report_id, t.tag
            FROM research.dim_report r
            JOIN research.map_report_tag m ON m.report_id = r.id
            JOIN research.dim_tag t ON t.id = m.tag_id AND t.tag_category = 'country'
            WHERE r.country_id IS NULL
            """
        )).fetchall()
        country_codes: dict[int, set[str]] = defaultdict(set)
        for rid, tag in country_rows:
            code = (tag or "").strip().upper()
            if code in country_id_by_code:
                country_codes[rid].add(code)
        country_updates = {
            rid: country_id_by_code[next(iter(codes))]
            for rid, codes in country_codes.items() if len(codes) == 1
        }
        ambiguous_country = sum(1 for codes in country_codes.values() if len(codes) > 1)

        # ── report ────────────────────────────────────────────────────────
        print(f"REGION   : {len(region_updates):>5} reports to set")
        for val, n in Counter(region_updates.values()).most_common():
            print(f"             {val:<10} {n}")
        print(f"COUNTRY  : {len(country_updates):>5} reports to set "
              f"({ambiguous_country} multi-country skipped)")
        code_by_id = {v: k for k, v in country_id_by_code.items()}
        for cid, n in Counter(country_updates.values()).most_common(15):
            print(f"             {code_by_id.get(cid, cid):<10} {n}")

        if not args.commit:
            print("\nDRY-RUN — no rows written. Re-run with --commit to apply.")
            return

        conn.execute(
            text("UPDATE research.dim_report SET region=:region, "
                 "updated_at=SYSDATETIMEOFFSET() WHERE id=:id"),
            [{"id": rid, "region": val} for rid, val in region_updates.items()],
        )
        conn.execute(
            text("UPDATE research.dim_report SET country_id=:cid, "
                 "updated_at=SYSDATETIMEOFFSET() WHERE id=:id"),
            [{"id": rid, "cid": cid} for rid, cid in country_updates.items()],
        )
        print(f"\nCOMMITTED — region={len(region_updates)} country={len(country_updates)}")


if __name__ == "__main__":
    main()
