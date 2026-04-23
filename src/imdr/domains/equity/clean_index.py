"""Cleaning rules for [equities].[fact_index_level].

Simple domain — only hard bound violations and robust outliers.
"""
from __future__ import annotations

from imdr.healthchecks.cleaning import CleaningAction, CleaningRule


class IndexHardBoundViolationRule(CleaningRule):
    """NULL values outside absolute range [min, max]."""

    def __init__(self, min_val: float = 1.0, max_val: float = 100_000.0) -> None:
        self._min = min_val
        self._max = max_val

    @property
    def name(self) -> str:
        return "hard_bound"

    @property
    def action_label(self) -> str:
        return "null_value"

    def detect(self, reader, table, where, params) -> "pd.DataFrame":
        import pandas as pd

        sql = (
            f"SELECT f.id, di.ticker, f.obs_date, f.close_level "
            f"FROM {table} f "
            f"JOIN [equities].[dim_index] di ON di.id = f.index_id "
            f"WHERE (f.close_level < {self._min} OR f.close_level > {self._max})"
        )
        if where:
            sql += f" AND ({where})"
        return reader.query(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        id_list = ", ".join(str(i) for i in ids)
        return (
            f"UPDATE [equities].[fact_index_level] "
            f"SET close_level = NULL, updated_at = SYSDATETIMEOFFSET() "
            f"WHERE id IN ({id_list})"
        )

    def build_action(self, row: "pd.Series") -> CleaningAction:
        return CleaningAction(
            id=row["id"],
            detail=f"ticker={row.get('ticker', '?')} close_level={row['close_level']}",
        )
