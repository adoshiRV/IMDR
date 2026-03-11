"""Run cleaning dry-run (or execute) across all domains.

Runs each domain's cleaning script in sequence via subprocess,
forwarding common flags (--execute, --year).

Usage:
    python -m scripts.imdr_clean
    python -m scripts.imdr_clean --execute
    python -m scripts.imdr_clean --year 2026
    python -m scripts.imdr_clean --execute --year 2026
"""

from __future__ import annotations

import subprocess
import sys
import time

CLEANING_SCRIPTS = [
    ("FX OHLC", "scripts.fx.clean.clean_fx_fact_ohlc"),
    ("FX Vol", "scripts.fx.clean.clean_fx_fact_vol"),
    ("Rates", "scripts.rates.clean.clean_rates_fact_observation"),
]


def main() -> int:
    # Forward all CLI args to each sub-script
    extra_args = sys.argv[1:]

    failed: list[str] = []
    for label, module in CLEANING_SCRIPTS:
        print(f"\n{'=' * 60}")
        print(f"  {label}")
        print(f"{'=' * 60}")

        cmd = [sys.executable, "-m", module, *extra_args]
        t0 = time.perf_counter()
        result = subprocess.run(cmd)
        elapsed = time.perf_counter() - t0

        if result.returncode != 0:
            print(f"\n  FAIL  {label}  rc={result.returncode}  ({elapsed:.1f}s)")
            failed.append(label)
        else:
            print(f"\n  OK    {label}  ({elapsed:.1f}s)")

    print(f"\n{'=' * 60}")
    if failed:
        print(f"  {len(failed)} domain(s) failed: {', '.join(failed)}")
        return 1
    print("  All domains clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
