#!/usr/bin/env python
"""One-off cleanup: remove seeded 'estimated' placeholder rows from calendar.cb_events.

Context: a handful of `calendar.cb_events` rows were seeded on 2026-03-24 with
`source='estimated'`, `is_estimated=1`, a *guessed* event_date, and no
event_datetime / survey / forecast / actual. They are not backed by any feed
(neither TradingEconomics nor Bloomberg BQL) and carry wrong dates — e.g. the
MAS Monetary Policy Statement placeholder dated 2026-07-14 (the real MPS window
is 24-31 Jul), which mis-dated a daily digest. These rows are pure noise: the
real events arrive via the TE/BQL feeds with correct dates.

This script:
  1. SELECTs every row matching the placeholder signature (guarded).
  2. Backs them up to a timestamped JSON next to this script (reversible).
  3. DELETEs them inside a single transaction (commit/rollback via the connector).
  4. Verifies the count is zero afterward.

Signature (deliberately tight so we never touch a real row): a placeholder is
either explicitly tagged estimated, or has no source at all — AND in both cases
carries no time, no survey/forecast and no actual (i.e. no feed ever populated it):
    (  (source = 'estimated' AND is_estimated = 1)  OR  source IS NULL  )
    AND event_datetime IS NULL AND actual IS NULL
    AND survey IS NULL AND forecast IS NULL

Run:  python playground/econ/cleanup_estimated_cb_events.py            # dry-run (default)
      python playground/econ/cleanup_estimated_cb_events.py --apply    # actually delete
"""
from __future__ import annotations

import argparse
import json
import pathlib

from sqlalchemy import text

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector

WHERE = (
    "((source = 'estimated' AND is_estimated = 1) OR source IS NULL) "
    "AND event_datetime IS NULL AND actual IS NULL "
    "AND survey IS NULL AND forecast IS NULL"
)

SELECT_SQL = text(
    "SELECT id, event_date, event_datetime, country_id, category, event_name, "
    "ticker, survey, forecast, actual, is_estimated, source, created_at, updated_at "
    f"FROM calendar.cb_events WHERE {WHERE} ORDER BY event_date"
)
DELETE_SQL = text(f"DELETE FROM calendar.cb_events WHERE {WHERE}")
COUNT_SQL = text(f"SELECT COUNT(*) FROM calendar.cb_events WHERE {WHERE}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="perform the DELETE (default: dry-run)")
    args = ap.parse_args(argv)

    connector = MSSQLConnector(Settings())

    # 1. read the matching rows
    with connector.engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(SELECT_SQL)]

    print(f"Matched {len(rows)} placeholder row(s):")
    for r in rows:
        print(f"  id={r['id']}  {r['event_date']}  {r['event_name']}  "
              f"source={r['source']}  is_estimated={r['is_estimated']}")

    if not rows:
        print("Nothing to clean. Exiting.")
        return 0

    # 2. back up (JSON, str-coerced for date/datetime)
    backup = pathlib.Path(__file__).with_name("cleanup_estimated_cb_events.backup.json")
    backup.write_text(
        json.dumps([{k: str(v) for k, v in r.items()} for r in rows], indent=2),
        encoding="utf-8",
    )
    print(f"Backup written: {backup}")

    if not args.apply:
        print("\nDRY-RUN — no rows deleted. Re-run with --apply to delete.")
        return 0

    # 3. delete inside a transaction
    with connector.session() as session:
        result = session.execute(DELETE_SQL)
        print(f"\nDELETE executed — {result.rowcount} row(s) removed (committing).")

    # 4. verify
    with connector.engine.connect() as conn:
        remaining = conn.execute(COUNT_SQL).scalar_one()
    print(f"Remaining rows matching the placeholder signature: {remaining}")
    connector.dispose()
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
