# Data Cleanup

Automated pruning of old parquet backups and log files from `data/`.

## What it does

`scripts/cleanup_old_data.py` walks `data/parquet/` and `data/logs/`, identifies files older than the retention period (default: **3 months**), deletes them, and removes any resulting empty directories.

## Targeted directories

| Directory | Date source | Cleaned |
|---|---|---|
| `data/parquet/fx/{table}/{YYYY}/{MM}/{DD}/` | Folder path | Yes |
| `data/parquet/rates/.../YYYY-MM.parquet` | Filename (`YYYY-MM`) | Yes (+ `_manifest.json`) |
| `data/logs/{schema}/{table}/*_{YYYYMMDD}_*` | Filename pattern | Yes |
| `data/cache/` | N/A | **No** — reference data, never touched |
| `data/gaps/` | N/A | **No** — excluded |

## Schedule

Registered in `scripts/imdr_weekly.py` and runs automatically as part of the weekly orchestrator with `--execute`.

## Manual usage

```bash
# Dry-run (default) — shows what would be deleted, no changes
python -m scripts.cleanup_old_data

# Actually delete files older than 3 months
python -m scripts.cleanup_old_data --execute

# Custom retention period (e.g. 6 months)
python -m scripts.cleanup_old_data --months 6 --execute
```

## Output

The script prints each file it deletes (or would delete) with its size, followed by a summary:

```
Cleanup mode: DRY-RUN  |  Cutoff date: 2025-12-25  |  Retention: 3 months

DRY  data/parquet/fx/fact_ohlc/2021/01/03/fx_ohlc_20210103_0000.parquet  (42.5 KB)
...

Would delete: 1204 files  (156.3 MB)
  Parquet: 1180 files  (154.1 MB)
  Logs:    24 files  (2.2 MB)
```
