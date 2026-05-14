"""Shared hive-partitioned parquet writer for FX fact tables.

Both `fx.fact_fx_rate` and `fx.fact_vol` archive to
`data/parquet/fx/{table}/{base}_{quote}/{YYYY-MM}.parquet`. The write
pattern is identical: groupby pair+month → read-existing → concat →
dedup-by-natural-key → atomic tmp+rename → optional manifest JSON.

This module hosts the single implementation; the per-fact wrappers are
just (root, required_columns, file_columns, dedup_key) tuples.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

_log = structlog.get_logger("fx.parquet_store")


def write_partitioned_parquet(
    df: pd.DataFrame,
    root: Path,
    required_columns: list[str],
    file_columns: list[str],
    dedup_key: list[str],
    manifest: dict[str, Any] | None = None,
) -> list[Path]:
    """Write df to hive-partitioned parquet, split by (base_ccy, quote_ccy, month).

    Parameters
    ----------
    df
        Input frame; must contain `required_columns` plus `ts` / `base_ccy` /
        `quote_ccy` (the latter two used as partition keys, the former is
        derived into `obs_date` + `_month`).
    root
        Partition root, e.g. ``data/parquet/fx/fact_vol``.
    required_columns
        Columns the caller promises are present (input validation).
    file_columns
        Columns to slice into each partition file.
    dedup_key
        Subset of `file_columns` used for last-write-wins dedup.
    manifest
        Optional metadata written alongside each partition as
        ``{month}_manifest.json``.

    Returns
    -------
    List of partition file paths written.
    """
    if df.empty:
        return []

    missing = set(required_columns) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df = df.copy()
    df["obs_date"] = pd.to_datetime(df["ts"]).dt.date
    df["_month"] = pd.to_datetime(df["ts"]).dt.strftime("%Y-%m")

    written: list[Path] = []
    for (base_ccy, quote_ccy, month), group in df.groupby(["base_ccy", "quote_ccy", "_month"]):
        partition_dir = root / f"{base_ccy}_{quote_ccy}"
        partition_dir.mkdir(parents=True, exist_ok=True)

        target = partition_dir / f"{month}.parquet"
        tmp = partition_dir / f"{month}.tmp.parquet"

        out = group[file_columns].copy()
        if target.exists():
            existing = pd.read_parquet(target)
            out = pd.concat([existing, out], ignore_index=True)
        out = (
            out.sort_values(dedup_key)
            .drop_duplicates(subset=dedup_key, keep="last")
            .reset_index(drop=True)
        )

        out.to_parquet(tmp, index=False, engine="pyarrow")
        os.replace(str(tmp), str(target))
        written.append(target)
        _log.info("parquet_written", path=str(target), rows=len(out))

    if manifest:
        write_ts = datetime.now(timezone.utc).isoformat()
        for (base_ccy, quote_ccy, month), _ in df.groupby(["base_ccy", "quote_ccy", "_month"]):
            partition_dir = root / f"{base_ccy}_{quote_ccy}"
            manifest_path = partition_dir / f"{month}_manifest.json"
            manifest_data = {
                **manifest,
                "base_ccy": base_ccy,
                "quote_ccy": quote_ccy,
                "month": month,
                "write_ts": write_ts,
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2, default=str)

    return written
