"""Playwright downloader for RBA statistical-table CSVs.

RBA's statistics server is Akamai-gated — plain HTTP GET returns 403.
Headed Chrome with a warm-up navigation passes the gate.

Downloads CSVs to ``data/econ/au/rba/samples/{table}-data.csv``.

Usage:
  python -m scripts.econ.au.rba.rba_snapshot_refresh            # all tables
  python -m scripts.econ.au.rba.rba_snapshot_refresh --daily-only  # f1 / f2 / f11.1 only
"""
from __future__ import annotations

import argparse
import io
import shutil
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SAMPLES = _REPO_ROOT / "data" / "econ" / "au" / "rba" / "samples"
_PROFILE = _REPO_ROOT / "data" / "econ" / "au" / "rba" / ".playwright_profile"

# (table_code, url)
# Daily tables come first so --daily-only can slice the head of the list.
_DAILY_TABLES = [
    ("f1",   "https://www.rba.gov.au/statistics/tables/csv/f1-data.csv"),
    ("f2",   "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv"),
    ("f11.1","https://www.rba.gov.au/statistics/tables/csv/f11.1-data.csv"),
]

_ALL_TABLES = _DAILY_TABLES + [
    # Monthly
    ("d3",  "https://www.rba.gov.au/statistics/tables/csv/d3-data.csv"),
    ("d2",  "https://www.rba.gov.au/statistics/tables/csv/d2-data.csv"),
    # Quarterly / mixed
    ("g1",  "https://www.rba.gov.au/statistics/tables/csv/g1-data.csv"),
    ("e1",  "https://www.rba.gov.au/statistics/tables/csv/e1-data.csv"),
    ("e2",  "https://www.rba.gov.au/statistics/tables/csv/e2-data.csv"),
    ("a2",  "https://www.rba.gov.au/statistics/tables/csv/a2-data.csv"),
    ("i1",  "https://www.rba.gov.au/statistics/tables/csv/i1-data.csv"),
    ("i2",  "https://www.rba.gov.au/statistics/tables/csv/i2-data.csv"),
    ("f15", "https://www.rba.gov.au/statistics/tables/csv/f15-data.csv"),
    ("f16", "https://www.rba.gov.au/statistics/tables/csv/f16-data.csv"),
    # F17 zero-coupon analytical curve (yields + forward rates + discount factors).
    ("f17-yields",           "https://www.rba.gov.au/statistics/tables/csv/f17-yields.csv"),
    ("f17-forward-rates",    "https://www.rba.gov.au/statistics/tables/csv/f17-forward-rates.csv"),
    ("f17-discount-factors", "https://www.rba.gov.au/statistics/tables/csv/f17-discount-factors.csv"),
]


def _download_tables(tables: list[tuple[str, str]]) -> int:
    from playwright.sync_api import sync_playwright

    _SAMPLES.mkdir(parents=True, exist_ok=True)

    if _PROFILE.exists():
        shutil.rmtree(_PROFILE, ignore_errors=True)
    _PROFILE.mkdir(parents=True, exist_ok=True)

    print(f"[rba_snapshot_refresh] launching headed Chrome ({len(tables)} tables)")
    successes, failures = [], []

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(_PROFILE),
            channel="chrome",
            headless=False,
            accept_downloads=True,
            ignore_https_errors=True,
            args=["--start-maximized"],
            viewport={"width": 1400, "height": 900},
            locale="en-AU",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto("https://www.rba.gov.au/statistics/tables/",
                      wait_until="domcontentloaded", timeout=60_000)
            time.sleep(4.0)
        except Exception as exc:
            print(f"  warm-up FAIL: {exc!s:.140}")
            ctx.close()
            return 2

        for table_code, url in tables:
            target = _SAMPLES / f"{table_code}-data.csv"
            print(f"\n>> {table_code}")
            try:
                tab = ctx.new_page()
                try:
                    with tab.expect_download(timeout=60_000) as dl_info:
                        try:
                            tab.goto(url, timeout=60_000)
                        except Exception:
                            pass
                    dl = dl_info.value
                    dl.save_as(str(target))
                    size = target.stat().st_size
                    print(f"  -> {target.name} ({size:,} B)")
                    successes.append(table_code)
                except Exception:
                    r = ctx.request.get(url, timeout=60_000)
                    if r.status == 200 and len(r.body()) > 1024:
                        target.write_bytes(r.body())
                        print(f"  -> {target.name} ({len(r.body()):,} B) [ctx.request]")
                        successes.append(table_code)
                    else:
                        print(f"  FAIL status={r.status} size={len(r.body())}")
                        failures.append(table_code)
                finally:
                    try:
                        tab.close()
                    except Exception:
                        pass
            except Exception as exc:
                print(f"  FAIL {table_code}: {exc!s:.140}")
                failures.append(table_code)
            time.sleep(4.0)

        ctx.close()

    print(f"\n=== Summary ===")
    print(f"OK    ({len(successes)}): {successes}")
    print(f"FAIL  ({len(failures)}): {failures}")
    return 0 if not failures else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument(
        "--daily-only", action="store_true",
        help="Download only the three daily tables: f1, f2, f11.1.",
    )
    args = p.parse_args()
    tables = _DAILY_TABLES if args.daily_only else _ALL_TABLES
    return _download_tables(tables)


if __name__ == "__main__":
    sys.exit(main())
