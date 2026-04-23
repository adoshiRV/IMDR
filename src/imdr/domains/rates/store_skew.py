"""Hive-partitioned Parquet store for rates swaption skew data.

Layout:
  data/parquet/rates/swaption_skew/{ccy}/{YYYY-MM}.parquet

Each parquet file stores [obs_date, option_expiry, swap_tenor, strike_offset, value].
Partition column (ccy) is reconstructed from the directory path.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from imdr.domains.rates.skew_translate import COLUMNS

_log = structlog.get_logger("RatesSkewParquetStore")

DATA_ROOT = Path("data/parquet/rates/swaption_skew")

_NATURAL_KEY = ["obs_date", "option_expiry", "swap_tenor", "strike_offset"]


def write(
    df: pd.DataFrame,
    data_root: Path | None = None,
    manifest: dict[str, Any] | None = None,
) -> list[Path]:
    """Write skew DataFrame to hive-partitioned parquet, split by ccy + month.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns from skew_translate.COLUMNS
    data_root : Path
        Root directory. Default: data/parquet/rates/swaption_skew/
    manifest : dict
        Optional manifest metadata to write alongside data

    Returns
    -------
    List of parquet file paths written
    """
    root = data_root or DATA_ROOT

    if df.empty:
        return []

    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    written: list[Path] = []

    df = df.copy()
    df["obs_date"] = pd.to_datetime(df["ts"]).dt.date
    df["_month"] = pd.to_datetime(df["ts"]).dt.strftime("%Y-%m")

    store_cols = list(_NATURAL_KEY) + ["vol"]

    for (ccy, month), group in df.groupby(["ccy", "_month"]):
        partition_dir = root / str(ccy)
        partition_dir.mkdir(parents=True, exist_ok=True)

        target = partition_dir / f"{month}.parquet"
        tmp = partition_dir / f"{month}.tmp.parquet"

        write_df = group[store_cols].copy()

        # Merge with existing data
        if target.exists():
            existing = pd.read_parquet(target)
            write_df = pd.concat([existing, write_df], ignore_index=True)

        # Dedup: keep last occurrence per natural key
        write_df = write_df.sort_values(_NATURAL_KEY).drop_duplicates(
            subset=_NATURAL_KEY, keep="last"
        ).reset_index(drop=True)

        # Atomic write
        write_df.to_parquet(tmp, index=False, engine="pyarrow")
        os.replace(str(tmp), str(target))

        written.append(target)
        _log.info("parquet_written", path=str(target), rows=len(write_df))

    # Write manifests
    if manifest:
        for (ccy, month), _ in df.groupby(["ccy", "_month"]):
            partition_dir = root / str(ccy)
            manifest_path = partition_dir / f"{month}_manifest.json"
            manifest_data = {
                **manifest,
                "ccy": ccy,
                "month": month,
                "write_ts": datetime.now(timezone.utc).isoformat(),
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2, default=str)

    return written
