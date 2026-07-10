"""BI Indonesia SRBI auction-detail fetcher (prod) — maturity-ladder source.

Writes one row per (auction_date × tenor) into ``econ.fact_srbi_auction``:
series code, settlement/maturity dates, awarded nominal (Rp bn) and the
weighted-average winning yield.

This is the SECURITY-LEVEL companion to ``bi_srbi.py``. That fetcher persists
only the WA winning *yield* as an indicator time-series; this one persists the
awarded *nominal* needed to compute the SRBI maturity profile (outstanding by
maturity bucket). SRBI "6/9/12M" auctions are mostly REISSUANCES of existing
364-day series, so the maturity ladder is SUM(awarded) grouped by series_code
(≡ maturity_date), dropping matured series — see migration 108.

Default window is the trailing 21 days (catches the last ~6 auctions on every
run; idempotent MERGE on (auction_date, tenor_months)). Pass
``--since 2023-09-15`` for a full backfill.

  python -m scripts.econ.id.bi.bi_srbi_auctions                 # daily, load
  python -m scripts.econ.id.bi.bi_srbi_auctions --no-load       # smoke, counts only
  python -m scripts.econ.id.bi.bi_srbi_auctions --since 2023-09-15  # full backfill

Cell mapping: 4.3 Financial Conditions — sterilisation paper issuance/maturity.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.econ.bi_srbi import LAUNCH_DATE, fetch_srbi_window, make_session

UTC = datetime.timezone.utc
_DEFAULT_LOOKBACK_DAYS = 21

_REPO_ROOT = Path(__file__).resolve().parents[4]
_TOPIC_ROOT = _REPO_ROOT / "data" / "econ" / "id" / "bi" / "srbi_auctions"

_VENDOR_CODE = "bi"
_COUNTRY_CODE = "ID"

_MERGE_SQL = text("""
MERGE [econ].[fact_srbi_auction] AS tgt
USING (SELECT
    :auction_date         AS auction_date,
    :tenor_months         AS tenor_months,
    :series_code          AS series_code,
    :days_to_maturity     AS days_to_maturity,
    :settlement_date      AS settlement_date,
    :maturity_date        AS maturity_date,
    :awarded_rp_bn        AS awarded_rp_bn,
    :wa_winning_yield_pct AS wa_winning_yield_pct,
    :vendor_id            AS vendor_id,
    :country_id           AS country_id
) AS src
ON tgt.auction_date = src.auction_date AND tgt.tenor_months = src.tenor_months
WHEN MATCHED THEN UPDATE SET
    tgt.series_code          = src.series_code,
    tgt.days_to_maturity     = src.days_to_maturity,
    tgt.settlement_date      = src.settlement_date,
    tgt.maturity_date        = src.maturity_date,
    tgt.awarded_rp_bn        = src.awarded_rp_bn,
    tgt.wa_winning_yield_pct = src.wa_winning_yield_pct,
    tgt.vendor_id            = src.vendor_id,
    tgt.country_id           = src.country_id,
    tgt.updated_at           = SYSDATETIMEOFFSET()
WHEN NOT MATCHED THEN INSERT (
    auction_date, tenor_months, series_code, days_to_maturity,
    settlement_date, maturity_date, awarded_rp_bn, wa_winning_yield_pct,
    vendor_id, country_id
) VALUES (
    src.auction_date, src.tenor_months, src.series_code, src.days_to_maturity,
    src.settlement_date, src.maturity_date, src.awarded_rp_bn, src.wa_winning_yield_pct,
    src.vendor_id, src.country_id
);
""")


def _resolve_id(conn, table: str, code_col: str, code: str) -> int:
    row = conn.execute(
        text(f"SELECT id FROM dbo.{table} WHERE {code_col} = :c"), {"c": code}
    ).first()
    if row is None:
        raise RuntimeError(f"dbo.{table}.{code_col} = {code!r} not found — seed it first.")
    return int(row[0])


def _to_rows(auctions, vendor_id: int, country_id: int) -> tuple[list[dict], int]:
    """Build MERGE param dicts; skip legs lacking an awarded amount or maturity."""
    rows: list[dict] = []
    skipped = 0
    for a in auctions:
        if a.awarded_rp_bn is None or a.maturity_date is None:
            skipped += 1
            continue
        rows.append({
            "auction_date": a.auction_date,
            "tenor_months": a.tenor_months,
            "series_code": a.series_code,
            "days_to_maturity": a.days_to_maturity,
            "settlement_date": a.settlement_date,
            "maturity_date": a.maturity_date,
            "awarded_rp_bn": round(a.awarded_rp_bn, 2),
            "wa_winning_yield_pct": a.wa_winning_yield_pct,
            "vendor_id": vendor_id,
            "country_id": country_id,
        })
    return rows, skipped


def _write_parquet(rows: list[dict], now_utc: datetime.datetime) -> Path:
    folder = _TOPIC_ROOT / now_utc.strftime("%Y/%m/%d")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"bi_srbi_auctions_{now_utc.strftime('%Y%m%d_%H%M')}.parquet"
    df = pd.DataFrame(rows)
    df["ingested_at"] = now_utc
    df.to_parquet(path, index=False)
    return path


def _merge(connector: MSSQLConnector, rows: list[dict]) -> None:
    with connector.engine.begin() as conn:
        for r in rows:
            conn.execute(_MERGE_SQL, r)


def main() -> int:
    # Make stdout UTF-8 safe (display strings carry non-ASCII), mirroring
    # scripts.econ._runner.run_main. Idempotent; suppressed if the harness
    # already owns stdout.
    if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding.lower() != "utf-8":
        with contextlib.suppress(AttributeError, ValueError):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--since", help="Earliest auction_date, YYYY-MM-DD.")
    p.add_argument("--until", help="Latest auction_date, YYYY-MM-DD.")
    p.add_argument("--no-parquet", action="store_true", help="Skip parquet snapshot.")
    p.add_argument("--no-load", action="store_true", help="Skip DB MERGE (counts only).")
    args = p.parse_args()

    today = datetime.date.today()
    since = (
        datetime.date.fromisoformat(args.since) if args.since
        else max(LAUNCH_DATE, today - datetime.timedelta(days=_DEFAULT_LOOKBACK_DAYS))
    )
    until = datetime.date.fromisoformat(args.until) if args.until else today
    now = datetime.datetime.now(UTC)

    print(f"  window: {since} -> {until}")
    auctions = fetch_srbi_window(since, until, session=make_session())

    settings = get_settings()
    connector = MSSQLConnector(settings)
    with connector.engine.connect() as conn:
        vendor_id = _resolve_id(conn, "dim_vendor", "vendor_code", _VENDOR_CODE)
        country_id = _resolve_id(conn, "dim_country", "country_code", _COUNTRY_CODE)

    rows, skipped = _to_rows(auctions, vendor_id, country_id)
    print(f"  parsed {len(auctions)} legs -> {len(rows)} loadable, {skipped} skipped (no amount/maturity)")
    if rows:
        total = sum(r["awarded_rp_bn"] for r in rows) / 1000.0
        print(f"  awarded in window: Rp {total:,.1f} tn across {len(rows)} legs")

    if not rows:
        print("No auction rows in window — nothing to write.")
        return 0  # empty trailing window is normal (weekends / non-auction days)

    if not args.no_parquet:
        path = _write_parquet(rows, now)
        print(f"  wrote {path}")

    if args.no_load:
        print("--no-load set; skipping DB MERGE.")
        return 0

    _merge(connector, rows)
    print(f"  MERGEd {len(rows)} rows into econ.fact_srbi_auction")
    return 0


if __name__ == "__main__":
    sys.exit(main())
