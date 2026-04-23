"""One-off migration applier.

Splits a SQL migration file on GO boundaries and executes each batch
against the IMDR database using pyodbc.

Usage:
    python -m scripts.migrations.apply_migration migrations/023_create_dim_frequency.sql
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pyodbc

from imdr.config.settings import get_settings


def split_on_go(sql: str) -> list[str]:
    """Split SQL on GO statements (case-insensitive, whole-line only)."""
    batches = re.split(r"^\s*GO\s*$", sql, flags=re.IGNORECASE | re.MULTILINE)
    return [b.strip() for b in batches if b.strip()]


def apply(path: Path) -> None:
    settings = get_settings()
    conn_str = (
        f"DRIVER={{{settings.mssql_driver.replace('+', ' ')}}};"
        f"SERVER={settings.mssql_host},{settings.mssql_port};"
        f"DATABASE={settings.mssql_database};"
        f"Trusted_Connection=yes;"
    )

    sql = path.read_text()
    batches = split_on_go(sql)

    print(f"Applying {path} ({len(batches)} batches)")
    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        cur = conn.cursor()
        for i, batch in enumerate(batches, 1):
            print(f"  [{i}/{len(batches)}] executing {len(batch)} chars...")
            cur.execute(batch)
            # Drain any result sets
            try:
                while cur.nextset():
                    pass
            except pyodbc.ProgrammingError:
                pass
        print(f"OK {path.name}")
    finally:
        conn.close()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.migrations.apply_migration <path>")
        return 1
    apply(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
