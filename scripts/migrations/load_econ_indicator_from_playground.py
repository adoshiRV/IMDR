"""Load econ.dim_indicator + econ.fact_indicator from playground parquet.

Vendor-agnostic. Reads the latest dim + fact parquet files produced by any
playground/econ/{vendor}/ fetcher, resolves FKs against the canonical dims
(dim_vendor / dim_country / dim_frequency / dim_unit /
dim_indicator_category), and upserts into the two econ tables.

Idempotent:
  - dim_indicator: MERGE on (vendor_id, source_code)
  - fact_indicator: staging-table + MERGE on PK (indicator_id, obs_date, vintage)

Aborts loudly on:
  - missing FK resolution (e.g. parquet uses a unit / country / category
    that is not in the canonical dim)
  - missing imdr_code on a fact row (orphan observation)
This is by design -- silent NULL drops would let data quality regress.

Usage:
    # Dry run (resolves FKs, prints counts, no DB writes):
    python -m scripts.migrations.load_econ_indicator_from_playground \
        --vendor fred --dry-run

    # Real load (FRED full sample):
    python -m scripts.migrations.load_econ_indicator_from_playground --vendor fred

    # Use a specific parquet (otherwise picks the newest):
    python -m scripts.migrations.load_econ_indicator_from_playground \
        --vendor fred --dim-parquet path/to/dim.parquet --fact-parquet path/to/fact.parquet
"""

from __future__ import annotations

import argparse
import glob
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector


# ---------------------------------------------------------------------------
# Translation maps -- normalise playground free-text values to canonical dim
# codes. Add entries here as new vendors surface variant spellings.
# ---------------------------------------------------------------------------

# Unit alias -> canonical unit_code in dbo.dim_unit.
_UNIT_ALIASES: dict[str, str] = {
    "%": "pct",
    "persons_thousands": "th_persons",
    "units_thousands": "units_th",   # requires migration 076
    "hours": "hours",                # requires migration 076
}

# Country alias -> canonical country_code in dbo.dim_country.
# Kept defensively for any vendor parquet that hasn't yet aligned to dim_country
# (e.g. ISO 3166-1 alpha-2 'GB' vs IMDR 'UK', 'EZ' vs 'EU'). Currently empty:
# FRED was realigned 2026-06-05 (migration 079); other vendors emit dim_country
# codes natively.
_COUNTRY_ALIASES: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Parquet discovery
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _latest(pattern: str) -> Path:
    matches = sorted(_REPO_ROOT.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"no parquet matches: {pattern}")
    return matches[-1]


def discover_parquets(vendor: str) -> tuple[Path, Path]:
    """Find newest (dim, fact) parquet pair for a vendor's playground output."""
    base = f"playground/econ/{vendor}/sample_output/**"
    dim = _latest(f"{base}/*_dim.parquet")
    fact = _latest(f"{base}/*_fact.parquet")
    return dim, fact


# ---------------------------------------------------------------------------
# Lookup builders (read-only against dims)
# ---------------------------------------------------------------------------

def _build_lookups(connector: MSSQLConnector) -> dict[str, dict[str, int]]:
    """Pre-load (code -> id) lookups for every FK we resolve."""
    queries = {
        "vendor":    "SELECT vendor_code, id FROM dbo.dim_vendor",
        "country":   "SELECT country_code, id FROM dbo.dim_country",
        "frequency": "SELECT frequency_code, id FROM dbo.dim_frequency",
        "unit":      "SELECT unit_code, id FROM dbo.dim_unit",
        "category":  "SELECT category_code, id FROM econ.dim_indicator_category",
    }
    lookups: dict[str, dict[str, int]] = {}
    with connector.engine.connect() as conn:
        for name, sql in queries.items():
            rows = conn.execute(text(sql)).all()
            lookups[name] = {r[0]: int(r[1]) for r in rows}
    return lookups


# ---------------------------------------------------------------------------
# Dim resolution
# ---------------------------------------------------------------------------

def _resolve_dim_row(
    row: pd.Series,
    lookups: dict[str, dict[str, int]],
    seen_missing: dict[str, set],
) -> dict | None:
    """Translate a parquet dim row to fully-resolved FK form. None on error."""
    vendor_code = row["vendor_name"].lower()
    unit_code = _UNIT_ALIASES.get(row["unit"], row["unit"])
    freq_code = row["frequency"]
    cat_code = row["category"]
    country_raw = row.get("country_iso")
    country_code = (
        _COUNTRY_ALIASES.get(country_raw, country_raw)
        if pd.notna(country_raw) and country_raw is not None
        else None
    )

    vendor_id = lookups["vendor"].get(vendor_code)
    if vendor_id is None:
        seen_missing["vendor"].add(vendor_code); return None
    freq_id = lookups["frequency"].get(freq_code)
    if freq_id is None:
        seen_missing["frequency"].add(freq_code); return None
    unit_id = lookups["unit"].get(unit_code)
    if unit_id is None:
        seen_missing["unit"].add(unit_code); return None
    cat_id = lookups["category"].get(cat_code)
    if cat_id is None:
        seen_missing["category"].add(cat_code); return None
    country_id: int | None = None
    if country_code is not None:
        country_id = lookups["country"].get(country_code)
        if country_id is None:
            seen_missing["country"].add(country_code); return None

    bbg = row.get("bbg_ticker")
    if pd.isna(bbg):
        bbg = None

    # `display_name` is the new column on dim_indicator (was 'description').
    # Some older parquets still serialise as 'description' -- accept both.
    display_name = (
        row["display_name"] if "display_name" in row.index else row.get("description")
    )

    return {
        "imdr_code": row["imdr_code"],
        "vendor_id": vendor_id,
        "source_code": row["source_code"],
        "bbg_ticker": bbg,
        "display_name": display_name,
        "unit_id": unit_id,
        "frequency_id": freq_id,
        "country_id": country_id,
        "category_id": cat_id,
        "is_seasonally_adjusted": bool(row.get("is_seasonally_adjusted", False)),
        "is_active": bool(row.get("is_active", True)),
    }


# ---------------------------------------------------------------------------
# Dim load (small N, row-by-row MERGE)
# ---------------------------------------------------------------------------

_DIM_MERGE_SQL = """
MERGE [econ].[dim_indicator] AS tgt
USING (SELECT
    :imdr_code             AS imdr_code,
    :vendor_id             AS vendor_id,
    :source_code           AS source_code,
    :bbg_ticker            AS bbg_ticker,
    :display_name          AS display_name,
    :unit_id               AS unit_id,
    :frequency_id          AS frequency_id,
    :country_id            AS country_id,
    :category_id           AS category_id,
    :is_seasonally_adjusted AS is_seasonally_adjusted,
    :is_active             AS is_active
) AS src
ON tgt.vendor_id = src.vendor_id AND tgt.source_code = src.source_code
WHEN MATCHED THEN UPDATE SET
    tgt.imdr_code              = src.imdr_code,
    tgt.bbg_ticker             = src.bbg_ticker,
    tgt.display_name           = src.display_name,
    tgt.unit_id                = src.unit_id,
    tgt.frequency_id           = src.frequency_id,
    tgt.country_id             = src.country_id,
    tgt.category_id            = src.category_id,
    tgt.is_seasonally_adjusted = src.is_seasonally_adjusted,
    tgt.is_active              = src.is_active,
    tgt.updated_at             = SYSDATETIMEOFFSET()
WHEN NOT MATCHED THEN INSERT (
    imdr_code, vendor_id, source_code, bbg_ticker, display_name,
    unit_id, frequency_id, country_id, category_id,
    is_seasonally_adjusted, is_active
) VALUES (
    src.imdr_code, src.vendor_id, src.source_code, src.bbg_ticker, src.display_name,
    src.unit_id, src.frequency_id, src.country_id, src.category_id,
    src.is_seasonally_adjusted, src.is_active
);
"""


def _load_dim(
    connector: MSSQLConnector,
    resolved_rows: list[dict],
) -> dict[str, int]:
    """MERGE resolved dim rows; return imdr_code -> id map after the write."""
    with connector.engine.begin() as conn:
        for row in resolved_rows:
            conn.execute(text(_DIM_MERGE_SQL), row)
        # Re-read the imdr_code -> id map for the loaded rows.
        codes = [r["imdr_code"] for r in resolved_rows]
        # Chunk the IN clause to avoid >2100 params.
        result: dict[str, int] = {}
        for i in range(0, len(codes), 500):
            chunk = codes[i:i+500]
            params = {f"c{j}": c for j, c in enumerate(chunk)}
            placeholders = ", ".join(f":c{j}" for j in range(len(chunk)))
            rows = conn.execute(
                text(f"SELECT imdr_code, id FROM econ.dim_indicator WHERE imdr_code IN ({placeholders})"),
                params,
            ).all()
            for r in rows:
                result[r[0]] = int(r[1])
    return result


# ---------------------------------------------------------------------------
# Fact load (large N, staging-table MERGE)
# ---------------------------------------------------------------------------

_STG_CREATE_SQL = """
IF OBJECT_ID('tempdb..##stg_econ_fact') IS NOT NULL DROP TABLE ##stg_econ_fact;
CREATE TABLE ##stg_econ_fact (
    indicator_id   INT             NOT NULL,
    obs_date       DATE            NOT NULL,
    vintage        SMALLINT        NOT NULL,
    release_date   DATETIMEOFFSET  NOT NULL,
    value          DECIMAL(28, 10)     NULL,
    is_preliminary BIT             NOT NULL
);
"""

_STG_INSERT_SQL = """
INSERT INTO ##stg_econ_fact (indicator_id, obs_date, vintage, release_date, value, is_preliminary)
VALUES (?, ?, ?, ?, ?, ?)
"""

_FACT_MERGE_SQL = """
MERGE [econ].[fact_indicator] AS tgt
USING ##stg_econ_fact AS src
ON tgt.indicator_id = src.indicator_id
   AND tgt.obs_date = src.obs_date
   AND tgt.vintage  = src.vintage
WHEN NOT MATCHED THEN INSERT (
    indicator_id, obs_date, vintage, release_date, value, is_preliminary
) VALUES (
    src.indicator_id, src.obs_date, src.vintage, src.release_date, src.value, src.is_preliminary
);
"""


def _load_fact(
    connector: MSSQLConnector,
    fact_df: pd.DataFrame,
    imdr_to_id: dict[str, int],
) -> dict[str, int]:
    """Bulk-stage fact rows then MERGE into econ.fact_indicator.

    Returns counts dict: {staged, inserted}.
    """
    # Resolve imdr_code -> indicator_id; drop any orphans loudly.
    unknown = sorted(set(fact_df["imdr_code"]) - set(imdr_to_id))
    if unknown:
        raise RuntimeError(
            f"{len(unknown)} fact imdr_codes have no dim row after MERGE; "
            f"e.g. {unknown[:5]}"
        )
    df = fact_df.copy()
    df["indicator_id"] = df["imdr_code"].map(imdr_to_id).astype("int64")

    # Coerce types for pyodbc.
    df["obs_date"] = pd.to_datetime(df["obs_date"]).dt.date
    df["vintage"] = df["vintage"].astype("int16")
    df["release_date"] = pd.to_datetime(df["release_date"], utc=True)
    # DATETIMEOFFSET via pyodbc needs Python datetime with tzinfo; pyodbc
    # accepts the pandas Timestamp directly when use_setinputsizes=False.
    df["release_date"] = df["release_date"].apply(lambda t: t.to_pydatetime() if pd.notna(t) else None)
    # Decimal-friendly: keep value as Python float / None.
    df["value"] = df["value"].astype(object).where(df["value"].notna(), None)
    df["is_preliminary"] = df.get("is_preliminary", False).astype(bool)

    # Pre-MERGE count for reporting.
    raw_conn = connector.engine.raw_connection()
    inserted = 0
    try:
        cursor = raw_conn.cursor()
        cursor.fast_executemany = True

        # Staging table.
        for stmt in _STG_CREATE_SQL.strip().split(";"):
            if stmt.strip():
                cursor.execute(stmt)
        raw_conn.commit()

        # Bulk insert into staging.
        cols = ["indicator_id", "obs_date", "vintage", "release_date", "value", "is_preliminary"]
        rows = list(df[cols].itertuples(index=False, name=None))
        cursor.executemany(_STG_INSERT_SQL, rows)
        raw_conn.commit()

        # Pre-MERGE: how many rows already exist (will be skipped)?
        cursor.execute("""
            SELECT COUNT(*) FROM ##stg_econ_fact s
            WHERE EXISTS (
                SELECT 1 FROM econ.fact_indicator f
                WHERE f.indicator_id = s.indicator_id
                  AND f.obs_date     = s.obs_date
                  AND f.vintage      = s.vintage
            )
        """)
        skipped = cursor.fetchone()[0]

        # MERGE into target.
        cursor.execute(_FACT_MERGE_SQL)
        inserted = cursor.rowcount  # rows actually inserted (NOT MATCHED branch)
        raw_conn.commit()

        # Clean up staging.
        cursor.execute("DROP TABLE ##stg_econ_fact")
        raw_conn.commit()
        cursor.close()
    finally:
        raw_conn.close()

    return {"staged": len(df), "inserted": inserted, "skipped": skipped}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load econ.dim_indicator + fact_indicator from playground parquet"
    )
    parser.add_argument("--vendor", required=True, help="e.g. fred, hkma, rbi, statsnz")
    parser.add_argument("--dim-parquet", default=None, help="Override auto-discovered dim parquet path")
    parser.add_argument("--fact-parquet", default=None, help="Override auto-discovered fact parquet path")
    parser.add_argument("--dry-run", action="store_true", help="Resolve FKs and print counts only; no DB writes")
    args = parser.parse_args(argv)

    if args.dim_parquet and args.fact_parquet:
        dim_path = Path(args.dim_parquet)
        fact_path = Path(args.fact_parquet)
    else:
        dim_path, fact_path = discover_parquets(args.vendor)
    print(f"vendor    : {args.vendor}")
    print(f"dim       : {dim_path}")
    print(f"fact      : {fact_path}")

    dim_df = pd.read_parquet(dim_path)
    fact_df = pd.read_parquet(fact_path)
    print(f"dim rows  : {len(dim_df):,}")
    print(f"fact rows : {len(fact_df):,}")

    settings = get_settings()
    connector = MSSQLConnector(settings)
    lookups = _build_lookups(connector)
    print(f"lookups   : vendor={len(lookups['vendor'])} country={len(lookups['country'])} "
          f"freq={len(lookups['frequency'])} unit={len(lookups['unit'])} cat={len(lookups['category'])}")

    # ---- Resolve dim FKs ----
    seen_missing: dict[str, set] = {k: set() for k in ("vendor", "country", "frequency", "unit", "category")}
    resolved: list[dict] = []
    for _, row in dim_df.iterrows():
        r = _resolve_dim_row(row, lookups, seen_missing)
        if r is not None:
            resolved.append(r)

    if any(seen_missing.values()):
        print("\n!! FK resolution failures:")
        for k, v in seen_missing.items():
            if v:
                print(f"   {k:9s}: {sorted(v)}")
        print("Aborting -- fix translation maps or seed missing dim rows, then re-run.")
        return 2

    print(f"\nresolved dim rows: {len(resolved):,} (all FKs OK)")

    if args.dry_run:
        print("[dry-run] no DB writes.")
        return 0

    # ---- Load dim ----
    t0 = time.time()
    imdr_to_id = _load_dim(connector, resolved)
    print(f"dim MERGE done -- {len(imdr_to_id):,} imdr_codes resolved to ids in {time.time()-t0:.1f}s")

    # ---- Load fact ----
    t1 = time.time()
    stats = _load_fact(connector, fact_df, imdr_to_id)
    print(f"fact MERGE done in {time.time()-t1:.1f}s -- "
          f"staged={stats['staged']:,}  inserted={stats['inserted']:,}  skipped={stats['skipped']:,}")

    print("\nVerify with:")
    print(f"  SELECT COUNT(*) FROM econ.dim_indicator   WHERE vendor_id = (SELECT id FROM dbo.dim_vendor WHERE vendor_code='{args.vendor}');")
    print(f"  SELECT COUNT(*) FROM econ.fact_indicator f JOIN econ.dim_indicator d ON d.id=f.indicator_id WHERE d.vendor_id = (SELECT id FROM dbo.dim_vendor WHERE vendor_code='{args.vendor}');")
    return 0


if __name__ == "__main__":
    sys.exit(main())
