"""Track C ingest: econ-monitor BBG store -> rates.fact_bond_yield.

Loads the 45 sovereign 10Y legs (nominal / breakeven / inflation-linked real, 17 markets,
daily back to 1990) held in the econ monitor's Bloomberg store. Companion to migrations
125 (curves) and 126 (ticker -> curve-point map). See
docs/admin/development/govt_bond_population.md.

    python -m scripts.rates.bonds_monitor --no-load        # smoke, zero writes
    python -m scripts.rates.bonds_monitor                  # load
    python -m scripts.rates.bonds_monitor --tickers "GUKG10 Index"

Source handling
---------------
The monitor master is opened READ-ONLY from a scratch COPY, never the live file: the
monitor writes to it from its own scheduled refresh runs, and a copy also yields a stable
sha256 to record alongside the row counts.

Two source properties this corrects for:

* **Calendar-day padding.** The monitor's BDH pull asks ALL_CALENDAR_DAYS +
  PREVIOUS_VALUE, so every leg carries a row for all seven weekdays with the standing
  close republished on non-trading days -- verified flat on BBG.RATES.GOVT_10Y.AU
  (Sun 1913 / Mon 1915 / ... / Sat 1913 of 13,398). Weekends are dropped on calendar
  arithmetic, which works across the whole 1990- span.

  Holidays are deliberately NOT dropped. calendar.market_holidays covers 9 of the 17
  markets and only from 2007, so a holiday filter would be silently uneven across the
  panel; a carried-forward holiday print is ~1%/yr and is a StaleCheck concern
  (flag, don't block) rather than a reason to make coverage inconsistent.

* **Vintages.** fact_market_daily is keyed (series_id, obs_date, vintage); only the
  highest vintage per date is read.

Resolution is by source_ticker through rates.dim_bond_source -- see
BondYieldRepository.resolve_sources for why the (ccy, yield_type, country) tuple is not
usable as a key here.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.repository_bond import BondYieldRepository
from imdr.schemas.rates_bond import BondYieldCreate

MONITOR_DB = Path(r"z:\Business\Research\Dashboard\imdr_econ_monitor\data\bbg.sqlite3")
BBG_VENDOR_ID = 4
DAILY_FREQUENCY_ID = 5
BATCH_ROWS = 50_000


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_readonly(src: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="bonds_monitor.")) / src.name
    shutil.copy2(src, tmp)
    return tmp


def extract(cn: sqlite3.Connection, sources: dict[str, dict],
            tickers: list[str] | None) -> tuple[list[BondYieldCreate], dict]:
    """Read the INDEX legs and shape them onto fact_bond_yield. Pure -- no writes."""
    legs = cn.execute(
        "SELECT series_id, bbg_ticker FROM dim_rate_instrument "
        "WHERE kind = 'INDEX' ORDER BY series_id"
    ).fetchall()
    wanted = {t.strip().upper() for t in tickers} if tickers else None

    rows: list[BondYieldCreate] = []
    stats = {"legs_seen": len(legs), "legs_loaded": 0, "unmapped": [], "weekend_dropped": 0}

    for series_id, ticker in legs:
        key = ticker.strip().upper()
        if wanted and key not in wanted:
            continue
        src = sources.get(key)
        if src is None:
            # KRFRINDX (the KOFR compounded index) is a rate, not a bond, and is
            # deliberately absent from migration 126 -- so this is expected for it.
            stats["unmapped"].append((series_id, ticker))
            continue

        obs = cn.execute(
            "SELECT f.obs_date, f.close FROM fact_market_daily f "
            "WHERE f.series_id = ? AND f.close IS NOT NULL "
            "AND f.vintage = (SELECT MAX(f2.vintage) FROM fact_market_daily f2 "
            "                 WHERE f2.series_id = f.series_id AND f2.obs_date = f.obs_date) "
            "ORDER BY f.obs_date",
            [series_id],
        ).fetchall()
        if not obs:
            continue

        for obs_date, value in obs:
            d = date.fromisoformat(obs_date)
            if d.weekday() >= 5:
                stats["weekend_dropped"] += 1
                continue
            rows.append(BondYieldCreate(
                bond_curve_id=src["bond_curve_id"],
                vendor_id=BBG_VENDOR_ID,
                frequency_id=DAILY_FREQUENCY_ID,
                obs_date=d,
                obs_ts=f"{obs_date}T00:00:00+00:00",
                tenor_code=src["tenor_code"],
                tenor_days=src["tenor_days"],
                quote_type=src["quote_type"],
                spread_anchor=src["spread_anchor"],
                fwd_start=src["fwd_start"],
                horizon=src["horizon"],
                value=float(value),
                units=src["units"],
                source_ticker=ticker,
            ))
        stats["legs_loaded"] += 1

    return rows, stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=MONITOR_DB)
    ap.add_argument("--no-load", action="store_true", help="extract + report, write nothing")
    ap.add_argument("--tickers", nargs="*", help="restrict to these source tickers")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"ERROR: source not found: {args.db}", file=sys.stderr)
        return 2

    connector = MSSQLConnector(Settings())
    with connector.session() as session:
        sources = BondYieldRepository(session).resolve_sources(BBG_VENDOR_ID)
    print(f"resolved {len(sources)} active BBG bond sources from rates.dim_bond_source")

    copy = _copy_readonly(args.db)
    print(f"source : {args.db}")
    print(f"copy   : {copy}")
    print(f"sha256 : {_sha256(copy)}")

    cn = sqlite3.connect(f"file:{copy.as_posix()}?mode=ro", uri=True)
    try:
        rows, stats = extract(cn, sources, args.tickers)
    finally:
        cn.close()

    print(f"legs seen        : {stats['legs_seen']}")
    print(f"legs loaded      : {stats['legs_loaded']}")
    print(f"weekend dropped  : {stats['weekend_dropped']:,}")
    print(f"rows extracted   : {len(rows):,}")
    for series_id, ticker in stats["unmapped"]:
        print(f"  unmapped: {series_id} ({ticker}) -- no dim_bond_source row")

    if args.no_load:
        print("\n--no-load: nothing written.")
        return 0
    if not rows:
        print("\nnothing to load.")
        return 0

    written = 0
    with connector.session() as session:
        repo = BondYieldRepository(session)
        for i in range(0, len(rows), BATCH_ROWS):
            batch = rows[i:i + BATCH_ROWS]
            written += repo.bulk_upsert(batch)
            print(f"  merged {min(i + BATCH_ROWS, len(rows)):>7,} / {len(rows):,}")
    print(f"\nloaded {written:,} rows into rates.fact_bond_yield")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
