"""Generate idempotent SQL migration scripts from read_optimization.yml.

Usage:
    python -m scripts.generate_optimization_sql
    python -m scripts.generate_optimization_sql --output migrations/generated_optimization.sql

Reads the config and produces CREATE INDEX / CREATE VIEW DDL that can
be reviewed and run manually against the IMDR database.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from imdr.config.read_optimization_config import (
    ColumnstoreConfig,
    ViewConfig,
    load_read_optimization_config,
)


def generate_columnstore_sql(cfg: ColumnstoreConfig) -> str:
    """Generate idempotent NCCI creation SQL."""
    cols = ",\n        ".join(cfg.columns)
    return f"""-- Columnstore index on {cfg.fully_qualified_table}
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = '{cfg.index_name}'
      AND object_id = OBJECT_ID('{cfg.fully_qualified_table}')
)
BEGIN
    CREATE NONCLUSTERED COLUMNSTORE INDEX [{cfg.index_name}]
    ON {cfg.fully_qualified_table} (
        {cols}
    );
    PRINT 'Created NCCI {cfg.index_name} on {cfg.fully_qualified_table}.';
END
ELSE
BEGIN
    PRINT 'NCCI {cfg.index_name} already exists.';
END
GO
"""


def generate_view_index_sql(cfg: ViewConfig) -> str:
    """Generate index creation SQL for indexed views."""
    if cfg.type != "indexed" or not cfg.index_columns:
        return f"-- View {cfg.fully_qualified_name} is a regular view (no index needed).\n"

    index_name = f"uci_{cfg.name}"
    cols = ", ".join(cfg.index_columns)
    return f"""-- Unique clustered index on indexed view {cfg.fully_qualified_name}
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = '{index_name}'
      AND object_id = OBJECT_ID('{cfg.fully_qualified_name}')
)
BEGIN
    CREATE UNIQUE CLUSTERED INDEX [{index_name}]
    ON {cfg.fully_qualified_name} ({cols});
    PRINT 'Created index {index_name} on {cfg.fully_qualified_name}.';
END
ELSE
BEGIN
    PRINT 'Index {index_name} already exists.';
END
GO
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate optimization SQL from config")
    parser.add_argument("--output", type=Path, help="Write SQL to file instead of stdout")
    args = parser.parse_args()

    config = load_read_optimization_config()

    lines: list[str] = [
        "-- ============================================================",
        "-- Auto-generated read optimization SQL",
        "-- Source: src/imdr/config/read_optimization.yml",
        "-- Review before running against the IMDR database.",
        "-- ============================================================",
        "",
    ]

    # Columnstore indexes
    for cs in config.columnstore_indexes:
        lines.append(generate_columnstore_sql(cs))

    # View indexes (view DDL itself is hand-written in migrations)
    for view in config.views:
        lines.append(generate_view_index_sql(view))

    output = "\n".join(lines)

    if args.output:
        args.output.write_text(output)
        print(f"Written to {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
