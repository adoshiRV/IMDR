"""bloomberg/smoke_test.py — verify blpapi can talk to the local Bloomberg Terminal.

What it does:
    1. Connects to the Terminal on localhost:8194.
    2. Pulls the current yield for the 2y / 5y / 10y / 30y US Treasury benchmarks.
    3. Prints the result to stdout.
    4. Writes a CSV snapshot to:
           <repo>/data/bloomberg/{user}/smoke_test_{YYYYMMDD}_{HHMMSS}.csv

Requires (on the machine running this script):
    - Bloomberg Terminal running and logged in
    - bbcomm.exe listening on port 8194 (default — comes with the Terminal)
    - `blpapi` Python package installed:
        pip install --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi

Run:
    # shared terminal (default — Arjun's typical case)
    python bloomberg/smoke_test.py

    # named user
    python bloomberg/smoke_test.py --user dsuri
    python bloomberg/smoke_test.py --user rmahadevan
    python bloomberg/smoke_test.py --user rwu
    python bloomberg/smoke_test.py --user spanda

Exit codes:
    0  success — got a price for every ticker, snapshot written
    1  could not connect to the Terminal (is bbcomm.exe running? is the user logged in?)
    2  connected but at least one ticker errored
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

try:
    import blpapi
except ImportError:
    print(
        "ERROR: `blpapi` is not installed.\n"
        "Install with:\n"
        "  pip install --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi",
        file=sys.stderr,
    )
    sys.exit(1)


HOST = "localhost"
PORT = 8194

TICKERS = [
    "USGG2YR Index",
    "USGG5YR Index",
    "USGG10YR Index",
    "USGG30YR Index",
]
FIELDS = ["PX_LAST", "NAME", "LAST_UPDATE_DT", "CRNCY"]

KNOWN_USERS = {"adoshi", "dsuri", "rmahadevan", "rwu", "spanda", "shared_term"}

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_ROOT = REPO_ROOT / "data" / "bloomberg"


def _read(field_data, name: str) -> str:
    if not field_data.hasElement(name):
        return ""
    return field_data.getElement(name).getValueAsString()


def _pull_treasuries() -> tuple[dict[str, dict[str, str]], list[tuple[str, str]], int]:
    """Returns (rows, errors, exit_code_hint). exit_code_hint != 0 on connection failure."""
    opts = blpapi.SessionOptions()
    opts.setServerHost(HOST)
    opts.setServerPort(PORT)

    session = blpapi.Session(opts)
    if not session.start():
        print(
            f"ERROR: could not start a session at {HOST}:{PORT}.\n"
            "Check that the Bloomberg Terminal is running and logged in,\n"
            "and that bbcomm.exe is listening on port 8194.",
            file=sys.stderr,
        )
        return {}, [], 1

    try:
        if not session.openService("//blp/refdata"):
            print("ERROR: could not open //blp/refdata service.", file=sys.stderr)
            return {}, [], 1

        svc = session.getService("//blp/refdata")
        req = svc.createRequest("ReferenceDataRequest")
        for t in TICKERS:
            req.append("securities", t)
        for f in FIELDS:
            req.append("fields", f)

        session.sendRequest(req)

        rows: dict[str, dict[str, str]] = {}
        errors: list[tuple[str, str]] = []

        while True:
            ev = session.nextEvent(timeout=2000)
            for msg in ev:
                if msg.messageType() != blpapi.Name("ReferenceDataResponse"):
                    continue
                securities = msg.getElement("securityData")
                for i in range(securities.numValues()):
                    sec = securities.getValueAsElement(i)
                    ticker = sec.getElementAsString("security")
                    if sec.hasElement("securityError"):
                        errors.append(
                            (ticker, sec.getElement("securityError").getElementAsString("message"))
                        )
                        continue
                    fd = sec.getElement("fieldData")
                    rows[ticker] = {f: _read(fd, f) for f in FIELDS}
            if ev.eventType() == blpapi.Event.RESPONSE:
                break

        return rows, errors, 0
    finally:
        session.stop()


def _write_snapshot(user: str, rows: dict[str, dict[str, str]], pulled_at: dt.datetime) -> Path:
    user_dir = CACHE_ROOT / user
    user_dir.mkdir(parents=True, exist_ok=True)
    stamp = pulled_at.strftime("%Y%m%d_%H%M%S")
    out_path = user_dir / f"smoke_test_{stamp}.csv"
    tmp_path = out_path.with_suffix(".csv.tmp")

    with tmp_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker", "pulled_at_utc", "terminal_user", *FIELDS])
        for t in TICKERS:
            r = rows.get(t, {})
            writer.writerow(
                [t, pulled_at.isoformat(timespec="seconds"), user, *[r.get(f, "") for f in FIELDS]]
            )

    tmp_path.replace(out_path)
    return out_path


def _print_table(rows: dict[str, dict[str, str]]) -> None:
    print()
    print(f"Bloomberg Terminal at {HOST}:{PORT} — US Treasury benchmarks")
    print("-" * 78)
    print(f"{'TICKER':<18}{'YIELD':>10}  {'NAME':<28}{'AS OF':<20}")
    print("-" * 78)
    for t in TICKERS:
        r = rows.get(t, {})
        print(
            f"{t:<18}"
            f"{r.get('PX_LAST', 'N/A'):>10}  "
            f"{r.get('NAME', '')[:27]:<28}"
            f"{r.get('LAST_UPDATE_DT', '')[:19]:<20}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--user",
        default="shared_term",
        help=f"Terminal user this run is attributed to. One of: {sorted(KNOWN_USERS)}. "
        "Default: shared_term.",
    )
    args = parser.parse_args()

    if args.user not in KNOWN_USERS:
        print(
            f"ERROR: unknown --user '{args.user}'. Allowed: {sorted(KNOWN_USERS)}",
            file=sys.stderr,
        )
        return 1

    rows, errors, rc = _pull_treasuries()
    if rc != 0:
        return rc

    _print_table(rows)

    pulled_at = dt.datetime.now(dt.timezone.utc)
    snapshot = _write_snapshot(args.user, rows, pulled_at)

    print()
    print(f"Snapshot written: {snapshot}")

    if errors:
        print()
        print("Errors:")
        for t, e in errors:
            print(f"  {t}: {e}")
        return 2

    print("OK — smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
