"""Shared runtime for prod econ fetchers.

Every fetcher under `scripts/econ/{cc}/{vendor}/` follows the same shape:
  1. Pull from vendor and build (indicators, observations).
  2. Write a (dim, fact) parquet pair under
     `data/econ/{cc}/{vendor}/{topic}/{Y}/{M}/{D}/`.
  3. Invoke the canonical loader (scripts.migrations.load_econ_indicator_from_playground)
     on that pair to MERGE into econ.dim_indicator + econ.fact_indicator.

`run_main` wires those three steps to a CLI shape (--since / --until /
--no-parquet / --no-load), so each topic script only needs to provide its
`run_fetch()` callback plus the (country_code, vendor, topic) triple.

`country_code` is MANDATORY -- it pins each fetcher's on-disk artefacts under
the country-first ``data/econ/{cc}/...`` layout. There is no fallback; a
missing or empty ``country_code`` is a programming error and raises.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pandas as pd

from imdr.domains.econ.schema import (
    IndicatorRow,
    ObservationRow,
    indicators_to_records,
    observations_to_records,
)


UTC = datetime.timezone.utc

# Repo root: scripts/econ/_runner.py -> parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_ECON_ROOT = _REPO_ROOT / "data" / "econ"


FetchFn = Callable[[str | None, str | None],
                   tuple[list[IndicatorRow], list[ObservationRow]]]


def _normalise_country_code(country_code: str) -> str:
    """Lowercase + validate a 2-letter ISO country code.

    Raises ValueError on missing / wrong-shaped input. The filesystem layout
    is ``data/econ/{cc}/...`` with a 2-letter lowercase ``cc`` -- enforce
    that contract at the entry point rather than letting bad values silently
    create rogue folders.
    """
    # Type errors (None / non-string) raise TypeError; shape errors (wrong
    # length, non-alpha, whitespace-only) raise ValueError. Keeps the
    # contract consistent with how Python's stdlib draws the same line.
    if country_code is None or not isinstance(country_code, str):
        raise TypeError(
            "country_code must be a 2-letter ISO string "
            f"(e.g. 'KR'); got {type(country_code).__name__}"
        )
    cc = country_code.strip().lower()
    if len(cc) != 2 or not cc.isalpha():
        raise ValueError(
            f"country_code must be a 2-letter ISO code; got {country_code!r}"
        )
    return cc


def _topic_root(country_code: str, vendor: str, topic: str) -> Path:
    """Resolve `data/econ/{cc}/{vendor}/{topic}/` (created on demand)."""
    cc = _normalise_country_code(country_code)
    return _DATA_ECON_ROOT / cc / vendor / topic


def write_parquet(
    country_code: str,
    vendor: str,
    topic: str,
    indicators: list[IndicatorRow],
    observations: list[ObservationRow],
    now_utc: datetime.datetime | None = None,
) -> tuple[Path, Path]:
    """Write (dim, fact) parquet pair under `data/econ/{cc}/{vendor}/{topic}/{Y}/{M}/{D}/`.

    Returns (dim_path, fact_path). History is preserved by the timestamped
    filename inside the daily folder -- repeated runs do not overwrite.
    """
    now_utc = now_utc or datetime.datetime.now(UTC)
    folder = _topic_root(country_code, vendor, topic) / now_utc.strftime("%Y/%m/%d")
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{vendor}_{topic}_{now_utc.strftime('%Y%m%d_%H%M')}"

    dim_df = pd.DataFrame(indicators_to_records(indicators))
    fact_df = pd.DataFrame(observations_to_records(observations))
    dim_df["ts"] = now_utc
    fact_df["ts"] = now_utc

    dim_path = folder / f"{stem}_dim.parquet"
    fact_path = folder / f"{stem}_fact.parquet"
    dim_df.to_parquet(dim_path, index=False)
    fact_df.to_parquet(fact_path, index=False)
    return dim_path, fact_path


def invoke_loader(vendor: str, dim_path: Path, fact_path: Path) -> int:
    """Run the canonical parquet -> DB loader on a single (dim, fact) pair.

    Uses --dim-parquet / --fact-parquet so the loader targets exactly the
    pair we just wrote (its auto-discovery picks the newest match across the
    whole tree, which is the wrong behaviour when many topics share the
    same vendor).
    """
    cmd = [
        sys.executable, "-m",
        "scripts.migrations.load_econ_indicator_from_playground",
        "--vendor", vendor,
        "--dim-parquet", str(dim_path),
        "--fact-parquet", str(fact_path),
    ]
    print(f"\n  → invoking loader: {' '.join(cmd)}")
    return subprocess.call(cmd)


def _summary(
    indicators: list[IndicatorRow],
    observations: list[ObservationRow],
) -> None:
    print(f"\nSummary: {len(indicators)} indicators, {len(observations)} observations")
    by_code: dict[str, tuple[int, datetime.date, datetime.date, float | None]] = {}
    for o in observations:
        cur = by_code.get(o.imdr_code)
        if cur is None:
            by_code[o.imdr_code] = (1, o.obs_date, o.obs_date, o.value)
        else:
            n, lo, hi, _ = cur
            by_code[o.imdr_code] = (n + 1, min(lo, o.obs_date), max(hi, o.obs_date), o.value)
    for code in sorted(by_code):
        n, lo, hi, last_val = by_code[code]
        print(f"  {code}: n={n} window={lo} → {hi} latest={last_val}")


def run_main(
    vendor: str,
    topic: str,
    fetch_fn: FetchFn,
    description: str = "",
    *,
    country_code: str,
) -> int:
    """Entry point for a prod econ fetcher.

    Wires the standard --since / --until / --no-parquet / --no-load CLI
    around `fetch_fn`. Each topic script's `main()` should be a one-liner
    that delegates here.

    ``country_code`` is keyword-only and MANDATORY -- the 2-letter ISO code
    (e.g. ``"KR"``) used to anchor the on-disk artefact path under
    ``data/econ/{cc}/{vendor}/{topic}/``. See ``_normalise_country_code``.
    """
    # Validate eagerly so a misconfigured fetcher fails before it hits the
    # network rather than after producing a half-written parquet tree.
    cc = _normalise_country_code(country_code)

    # Make stdout safe for the Korean characters that show up in display
    # names. Idempotent if already wrapped. AttributeError / ValueError fire
    # when running under a harness that already owns stdout -- not fatal.
    if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding.lower() != "utf-8":
        with contextlib.suppress(AttributeError, ValueError):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )

    p = argparse.ArgumentParser(description=description or f"{vendor} {topic} fetcher")
    p.add_argument("--since", help="Earliest obs_date, YYYY-MM-DD.")
    p.add_argument("--until", help="Latest obs_date, YYYY-MM-DD.")
    p.add_argument("--no-parquet", action="store_true",
                   help="Skip parquet write (counts only, no DB load).")
    p.add_argument("--no-load", action="store_true",
                   help="Write parquet but skip the DB load step.")
    args = p.parse_args()

    indicators, observations = fetch_fn(args.since, args.until)
    _summary(indicators, observations)
    if not observations:
        print("No observations -- nothing to write.")
        return 1

    if args.no_parquet:
        print("\n--no-parquet set; skipping write and load.")
        return 0

    dim_path, fact_path = write_parquet(cc, vendor, topic, indicators, observations)
    print(f"\nWrote {dim_path}")
    print(f"Wrote {fact_path}")

    if args.no_load:
        print("--no-load set; skipping DB MERGE.")
        return 0

    rc = invoke_loader(vendor, dim_path, fact_path)
    if rc != 0:
        print(f"\n!! loader exited rc={rc}")
        return rc
    return 0
