"""bloomberg/refresh.py — central orchestrator that pulls BBG data for one user.

Reads the per-domain ticker files under ``bloomberg/tickers/{rates,bonds,fx}.csv``,
filters to the rows assigned to ``--user`` and matching ``--schedule`` (and
optionally ``--domain``), pulls them via blpapi from the local Bloomberg
Terminal, writes a CSV snapshot to ``data/bloomberg/{user}/``, and sends an
Outlook email summarising the run (using the existing IMDR notifications
system).

This is the ONLY script Task Scheduler ever calls. Each row's ``schedule``
column tells the orchestrator which rows belong to which scheduled run;
``domain`` is derived from the source file, not from a row column.

Requires (on the executing machine):
    - Bloomberg Terminal running and logged in (localhost:8194)
    - `imdrbbg` conda env active (see docs/admin/vendors/bbg/terminal_python_setup.md)
    - `.env` at the repo root with IMDR_EMAIL_TO / IMDR_EMAIL_ENABLED if you
      want email summaries

Run:
    conda activate imdrbbg
    python Z:\\Business\\Personnel\\Arjun\\GitHub\\IMDR\\bloomberg\\refresh.py \\
        --user dsuri --schedule hourly

CLI:
    --user       one of dsuri / rmahadevan / rwu / spanda / shared_term
    --schedule   one of daily / hourly / snapshot
                 (matches the `schedule` column in the per-domain ticker files;
                 `snapshot` pulls every enabled row for the user across the
                 selected domains)
    --domain     OPTIONAL: one of rates / bonds / fx — filter to a single
                 ticker file. Omit to pull all three (scheduled-run default).
                 App-driven calls should usually pass this.
    --no-email   skip the summary email even if IMDR_EMAIL_ENABLED=true
    --dry-run    parse the ticker files and print what *would* be pulled;
                 no BBG, no write

Exit codes:
    0  all tickers pulled, snapshot written
    1  could not connect to Terminal / no tickers matched the filter
    2  partial — some tickers errored, snapshot still written with successes
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import socket
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass  # .env loading is best-effort; env vars may still be set externally

try:
    import blpapi
except ImportError:
    print(
        "ERROR: `blpapi` is not installed in this env.\n"
        "Activate imdrbbg: conda activate imdrbbg\n"
        "Or install:        pip install --index-url "
        "https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi",
        file=sys.stderr,
    )
    sys.exit(1)


HOST = "localhost"
PORT = 8194

KNOWN_USERS = {"adoshi", "dsuri", "rmahadevan", "rwu", "spanda", "shared_term"}
# `snapshot` is the on-demand mode — pulls every enabled row for the user
# (any schedule). Rows tagged `schedule=snapshot` are pulled *only* in this
# mode; rows tagged `hourly`/`daily` are pulled on schedule AND on snapshot.
KNOWN_SCHEDULES = {"hourly", "daily", "snapshot"}
KNOWN_DOMAINS = {"rates", "bonds", "fx"}

TICKERS_DIR = REPO_ROOT / "bloomberg" / "tickers"
# Per-domain ticker files, each with its own schema. `domain` is injected
# by the loader (not read from the file) so the downstream snapshot CSV
# can carry it through to the sweeper consumer.
TICKER_FILES: dict[str, str] = {
    "rates": "rates.csv",
    "bonds": "bonds.csv",
    "fx":    "fx.csv",
}
CACHE_ROOT = REPO_ROOT / "data" / "bloomberg"


def _load_tickers(
    user: str, schedule: str, domain_filter: str | None = None
) -> list[dict[str, str]]:
    """Return enabled rows for (user, schedule) across the selected ticker files.

    Reads ``bloomberg/tickers/{rates,bonds,fx}.csv`` and concatenates.
    Each row gets a synthetic ``domain`` key set from the source file
    so the snapshot writer + downstream sweeper can route by domain.

    Parameters
    ----------
    user, schedule
        Filter as before (``schedule == "snapshot"`` ignores the row's
        ``schedule`` column and returns everything enabled for the user).
    domain_filter
        Optional ``rates`` / ``bonds`` / ``fx``. When set, only that one
        ticker file is read. Omit (None) to read all three — the scheduled-
        run default. App-driven calls should usually pass a domain.
    """
    if not TICKERS_DIR.exists():
        raise FileNotFoundError(f"tickers dir not found at {TICKERS_DIR}")

    rows: list[dict[str, str]] = []
    for domain, fname in TICKER_FILES.items():
        if domain_filter is not None and domain != domain_filter:
            continue
        path = TICKERS_DIR / fname
        if not path.exists():
            print(f"WARN: {path} not present, skipping", file=sys.stderr)
            continue
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("user", "").strip() != user:
                    continue
                if row.get("enabled", "").strip().lower() != "true":
                    continue
                if schedule != "snapshot" and row.get("schedule", "").strip() != schedule:
                    continue
                # Normalize: keep every column the file carries, plus inject `domain`.
                # _pull only needs `ticker` and `fields`; _write_snapshot needs `domain`.
                normalized = {k: (v or "").strip() for k, v in row.items()}
                normalized["domain"] = domain
                rows.append(normalized)
    return rows


def _read_field(field_data, name: str) -> str:
    if not field_data.hasElement(name):
        return ""
    return field_data.getElement(name).getValueAsString()


def _pull(tickers_with_fields: list[tuple[str, list[str]]]) -> tuple[
    dict[str, dict[str, str]], list[tuple[str, str]], int
]:
    """Issue one ReferenceDataRequest covering every (ticker, field) we need.

    Returns (values_by_ticker, errors, exit_code_hint).
    exit_code_hint != 0 only on session failure.
    """
    opts = blpapi.SessionOptions()
    opts.setServerHost(HOST)
    opts.setServerPort(PORT)

    session = blpapi.Session(opts)
    if not session.start():
        print(
            f"ERROR: could not start a session at {HOST}:{PORT}.\n"
            "Check the Bloomberg Terminal is running and logged in.",
            file=sys.stderr,
        )
        return {}, [], 1

    try:
        if not session.openService("//blp/refdata"):
            print("ERROR: could not open //blp/refdata service.", file=sys.stderr)
            return {}, [], 1

        svc = session.getService("//blp/refdata")
        req = svc.createRequest("ReferenceDataRequest")

        all_fields: set[str] = set()
        for ticker, fields in tickers_with_fields:
            req.append("securities", ticker)
            all_fields.update(fields)
        for f in sorted(all_fields):
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
                            (
                                ticker,
                                sec.getElement("securityError").getElementAsString("message"),
                            )
                        )
                        continue
                    fd = sec.getElement("fieldData")
                    rows[ticker] = {f: _read_field(fd, f) for f in sorted(all_fields)}
            if ev.eventType() == blpapi.Event.RESPONSE:
                break

        return rows, errors, 0
    finally:
        session.stop()


def _write_snapshot(
    user: str,
    schedule: str,
    config_rows: list[dict[str, str]],
    pulled_values: dict[str, dict[str, str]],
    pulled_at: dt.datetime,
) -> Path:
    user_dir = CACHE_ROOT / user
    user_dir.mkdir(parents=True, exist_ok=True)
    stamp = pulled_at.strftime("%Y%m%d_%H%M%S")
    out = user_dir / f"bbg_{schedule}_{stamp}.csv"
    tmp = out.with_suffix(".csv.tmp")

    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["ticker", "terminal_user", "pulled_at_utc", "host", "domain", "field", "value"]
        )
        for row in config_rows:
            ticker = row["ticker"]
            domain = row["domain"]
            values = pulled_values.get(ticker, {})
            for field in [f.strip() for f in row["fields"].split(",") if f.strip()]:
                writer.writerow(
                    [
                        ticker,
                        user,
                        pulled_at.isoformat(timespec="seconds"),
                        socket.gethostname(),
                        domain,
                        field,
                        values.get(field, ""),
                    ]
                )

    tmp.replace(out)
    return out


def _print_table(
    config_rows: list[dict[str, str]],
    pulled_values: dict[str, dict[str, str]],
) -> None:
    print()
    print(f"Bloomberg Terminal at {HOST}:{PORT} — refresh snapshot")
    print("-" * 78)
    print(f"{'TICKER':<22}{'DOMAIN':<14}{'FIELD':<22}{'VALUE':>18}")
    print("-" * 78)
    for row in config_rows:
        ticker = row["ticker"]
        domain = row["domain"]
        values = pulled_values.get(ticker, {})
        for field in [f.strip() for f in row["fields"].split(",") if f.strip()]:
            print(f"{ticker:<22}{domain:<14}{field:<22}{values.get(field, 'N/A'):>18}")


def _send_email_summary(
    user: str,
    schedule: str,
    config_rows: list[dict[str, str]],
    pulled_values: dict[str, dict[str, str]],
    errors: list[tuple[str, str]],
    pulled_at: dt.datetime,
    duration_s: float,
    output_path: Path,
) -> None:
    """Best-effort: send a summary email via the IMDR notifications system."""
    if os.environ.get("IMDR_EMAIL_ENABLED", "").strip().lower() != "true":
        return
    to = os.environ.get("IMDR_EMAIL_TO", "").strip()
    if not to:
        return

    try:
        from imdr.notifications.email import send_outlook_email
        from imdr.notifications.formatters.bbg_refresh import BBGRefreshFormatter
    except ImportError as e:
        print(f"WARN: could not import IMDR notifications system: {e}", file=sys.stderr)
        return

    n_total = len(config_rows)
    n_ok = sum(1 for r in config_rows if r["ticker"] in pulled_values)

    rows_for_email: list[dict[str, str]] = []
    for r in config_rows:
        ticker = r["ticker"]
        if ticker not in pulled_values:
            continue
        values = pulled_values[ticker]
        rows_for_email.append(
            {
                "ticker": ticker,
                "domain": r["domain"],
                "fields": r["fields"],
                "values": ", ".join(
                    f"{f}={values.get(f, '')}"
                    for f in (s.strip() for s in r["fields"].split(","))
                    if f
                ),
            }
        )

    fmt = BBGRefreshFormatter()
    subject = fmt.format_subject(
        user=user,
        schedule=schedule,
        run_time_utc=pulled_at,
        n_ok=n_ok,
        n_total=n_total,
    )
    body = fmt.format_body(
        user=user,
        host=socket.gethostname(),
        schedule=schedule,
        run_time_utc=pulled_at,
        duration_s=duration_s,
        n_ok=n_ok,
        n_total=n_total,
        rows=rows_for_email,
        errors=errors,
        output_path=str(output_path),
    )

    importance = 2 if n_ok < n_total else 1
    send_outlook_email(to=to, subject=subject, html_body=body, importance=importance)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--user", required=True, help=f"One of: {sorted(KNOWN_USERS)}")
    parser.add_argument(
        "--schedule",
        required=True,
        help=f"One of: {sorted(KNOWN_SCHEDULES)}. "
        "'snapshot' pulls every enabled row for the user.",
    )
    parser.add_argument(
        "--domain",
        default=None,
        help=f"Optional filter: one of {sorted(KNOWN_DOMAINS)}. "
        "Omit to pull all 3 domains (scheduled-run default). "
        "App-driven calls should usually pass this.",
    )
    parser.add_argument("--no-email", action="store_true", help="Skip the summary email.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print which tickers would be pulled; no BBG call, no write, no email.",
    )
    args = parser.parse_args()

    if args.user not in KNOWN_USERS:
        print(f"ERROR: unknown --user '{args.user}'. Allowed: {sorted(KNOWN_USERS)}", file=sys.stderr)
        return 1
    if args.schedule not in KNOWN_SCHEDULES:
        print(
            f"ERROR: unknown --schedule '{args.schedule}'. Allowed: {sorted(KNOWN_SCHEDULES)}",
            file=sys.stderr,
        )
        return 1
    if args.domain is not None and args.domain not in KNOWN_DOMAINS:
        print(
            f"ERROR: unknown --domain '{args.domain}'. Allowed: {sorted(KNOWN_DOMAINS)}",
            file=sys.stderr,
        )
        return 1

    config_rows = _load_tickers(args.user, args.schedule, args.domain)
    if not config_rows:
        scope = f"domain={args.domain}" if args.domain else "all domains"
        print(
            f"No enabled tickers in {TICKERS_DIR} for user={args.user} schedule={args.schedule} ({scope}).",
            file=sys.stderr,
        )
        return 1

    tickers_with_fields = [
        (r["ticker"], [f.strip() for f in r["fields"].split(",") if f.strip()])
        for r in config_rows
    ]

    if args.dry_run:
        print(f"DRY RUN — would pull {len(config_rows)} tickers for user={args.user}, schedule={args.schedule}:")
        for r in config_rows:
            print(f"  {r['ticker']:<22} fields={r['fields']:<32} domain={r['domain']}")
        return 0

    t0 = time.perf_counter()
    pulled_values, errors, rc = _pull(tickers_with_fields)
    duration_s = time.perf_counter() - t0
    if rc != 0:
        return rc

    _print_table(config_rows, pulled_values)

    pulled_at = dt.datetime.now(dt.timezone.utc)
    out = _write_snapshot(args.user, args.schedule, config_rows, pulled_values, pulled_at)
    print(f"\nSnapshot written: {out}")
    print(f"Duration: {duration_s:.2f} s")

    if not args.no_email:
        _send_email_summary(
            user=args.user,
            schedule=args.schedule,
            config_rows=config_rows,
            pulled_values=pulled_values,
            errors=errors,
            pulled_at=pulled_at,
            duration_s=duration_s,
            output_path=out,
        )

    if errors:
        print("\nErrors:")
        for t, e in errors:
            print(f"  {t}: {e}")
        return 2

    print("OK — refresh complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
