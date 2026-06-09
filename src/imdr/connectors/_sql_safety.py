"""Shared SQL-identifier validators for the connectors package.

`bulk.py` (temp-table → MERGE) and `reader.py` (analytical reads) both
build dynamic SQL by interpolating table / column / staging names. Without
strict validation those interpolations would be classic SQL-injection
vectors. The regexes below define the only shapes we accept:

  * `IDENTIFIER_RE` — `[schema].[name]` or `[name]`. Used for fully-qualified
    table and view names.
  * `COLUMN_RE`     — bare alphanumeric / underscore. Used for column names.
  * `STAGING_RE`    — `#temp_name`. Used for session-scoped temp tables.

`bulk.py` and `reader.py` import from here; do not import from outside the
connectors package (underscore-prefixed module name signals "internal").
"""
from __future__ import annotations

import re

IDENTIFIER_RE = re.compile(r"^\[[\w]+\](?:\.\[[\w]+\])?$")
COLUMN_RE = re.compile(r"^[\w]+$")
STAGING_RE = re.compile(r"^#[\w]+$")


def validate_identifier(value: str, label: str) -> None:
    """Raise ValueError if `value` is not a `[schema].[name]` identifier."""
    if not IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid {label}: {value!r}. Expected [schema].[name] format.")


def validate_column(value: str, label: str) -> None:
    """Raise ValueError if `value` is not a bare alphanumeric column name."""
    if not COLUMN_RE.match(value):
        raise ValueError(f"Invalid {label}: {value!r}. Expected alphanumeric column name.")


def validate_staging(value: str, label: str) -> None:
    """Raise ValueError if `value` is not a `#temp_name` staging table name."""
    if not STAGING_RE.match(value):
        raise ValueError(f"Invalid {label}: {value!r}. Expected #temp_name format.")
