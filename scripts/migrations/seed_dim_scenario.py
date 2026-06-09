"""Seed dbo.dim_scenario + scenario_window + dim_stress_tag + scenario_stress_tag.

Usage:
    python -m scripts.migrations.seed_dim_scenario

Idempotent — safe to re-run. For each scenario:
  * insert into dim_scenario if missing (matched on display_name), else update
    stress_focus_raw only if it actually changed
  * replace all rows in scenario_window for that scenario (so date corrections
    re-sync)
  * upsert each scenario's canonical tags (sc.tags) into dim_stress_tag, then
    rebuild the scenario_stress_tag bridge

Tags are curated, not parsed. The PM's raw comma-string stays in
dim_scenario.stress_focus_raw for human reading; the dim_stress_tag bridge uses
the controlled vocabulary in CANONICAL_TAGS so analytics queries can group
cleanly (e.g. "all credit-stress scenarios since 2020").

PM-curated source list lives in SCENARIOS below. Add a row here when a new
scenario is identified, then re-run.

Transaction semantics: a single commit covers the entire 25-scenario batch.
If the script crashes mid-loop the whole batch rolls back, leaving the DB in
its pre-run state — no partial windows or orphan tag links can persist.

Date conventions:
  * "to live"  → end_date None (open window)
  * single date → start == end
  * year-month  → start = first day of month, end = last day of month
  * quarter     → resolved to last day of last month in quarter
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector

# ─── Canonical tag taxonomy (23 tags, curated 2026-05-20) ─────────────────
# Three axes: asset class, theme, region. The module-load assertion at the
# bottom enforces that every tag used on a Scenario is in this set.
CANONICAL_TAGS: frozenset[str] = frozenset(
    {
        # Asset class
        "fx", "rates", "credit", "equities", "commodities", "vol",
        # Theme
        "inflation", "liquidity", "duration", "banking-stress",
        "sovereign-stress", "carry-unwind", "risk-off", "oil-shock",
        "geopolitical",
        # Region
        "us", "europe", "uk", "japan", "china", "asia-em", "em", "middle-east",
    }
)


# ─── Source data (PM-curated 2026-05-20, tags LLM-curated same day) ────────
@dataclass(frozen=True)
class Scenario:
    name: str
    windows: tuple[tuple[date, date | None], ...]
    stress_focus: str  # PM-provided freetext → dim_scenario.stress_focus_raw
    tags: tuple[str, ...]  # canonical tags → scenario_stress_tag bridge


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="US-Iran war / Hormuz-oil shock",
        windows=((date(2026, 2, 28), None),),
        stress_focus="Oil, inflation breakevens, Asia importers, front-end rates, FX pass-through",
        tags=("oil-shock", "commodities", "inflation", "rates", "fx",
              "geopolitical", "middle-east", "asia-em"),
    ),
    Scenario(
        name="2025 tariff / trade shock",
        windows=((date(2025, 4, 1), date(2025, 6, 30)),),
        stress_focus="Asia exporters, KRW/TWD/CNH, equities, growth-sensitive rates",
        tags=("fx", "equities", "rates", "asia-em", "china", "geopolitical"),
    ),
    Scenario(
        name="US CRE / NYCB regional-bank scare",
        windows=((date(2024, 1, 31), date(2024, 3, 7)),),
        stress_focus="US regional banks, CRE credit, risk-off duration",
        tags=("banking-stress", "credit", "rates", "duration", "risk-off", "us"),
    ),
    Scenario(
        name="Yen carry unwind / Japan equity crash",
        windows=((date(2024, 8, 5), date(2024, 8, 5)),),
        stress_focus="USDJPY, JPY crosses, Nikkei, global momentum unwind",
        tags=("fx", "equities", "carry-unwind", "japan", "risk-off"),
    ),
    Scenario(
        name="SVB / US regional bank crisis",
        windows=((date(2023, 3, 8), date(2023, 3, 24)),),
        stress_focus="Regional banks, front-end rates, credit, USD funding",
        tags=("banking-stress", "rates", "credit", "liquidity", "us"),
    ),
    Scenario(
        name="Credit Suisse / AT1 shock",
        windows=((date(2023, 3, 15), date(2023, 3, 24)),),
        stress_focus="European banks, AT1/financial credit, CHF",
        tags=("banking-stress", "credit", "fx", "europe"),
    ),
    Scenario(
        name="US debt ceiling 2023 / Fitch downgrade",
        windows=(
            (date(2023, 5, 1), date(2023, 6, 5)),
            (date(2023, 8, 1), date(2023, 8, 4)),
        ),
        stress_focus="Bills, UST curve, USD liquidity",
        tags=("rates", "sovereign-stress", "liquidity", "us"),
    ),
    Scenario(
        name="Israel-Hamas / Gaza / Red Sea",
        windows=((date(2023, 10, 7), date(2024, 2, 29)),),
        stress_focus="Oil, shipping/freight, gold, Middle East risk premium",
        tags=("oil-shock", "commodities", "geopolitical", "risk-off", "middle-east"),
    ),
    Scenario(
        name="Russia-Ukraine invasion",
        windows=((date(2022, 2, 24), None),),
        stress_focus="Energy, EUR, inflation breakevens, EM importers",
        tags=("oil-shock", "commodities", "fx", "inflation", "em", "europe",
              "geopolitical"),
    ),
    Scenario(
        name="Global inflation / Fed shock / 2022 bear market",
        windows=((date(2022, 1, 1), date(2022, 10, 31)),),
        stress_focus="Global duration, USD, equities, credit",
        tags=("inflation", "rates", "duration", "fx", "equities", "credit",
              "risk-off"),
    ),
    Scenario(
        name="UK gilt / LDI crisis",
        windows=((date(2022, 9, 23), date(2022, 10, 14)),),
        stress_focus="Long-end rates, pension/LDI deleveraging, global duration",
        tags=("rates", "duration", "sovereign-stress", "uk"),
    ),
    Scenario(
        name="BoJ YCC shock",
        windows=((date(2022, 12, 20), date(2023, 1, 18)),),
        stress_focus="JGBs, USDJPY, global long-end spillover",
        tags=("rates", "duration", "fx", "japan"),
    ),
    Scenario(
        name="China property stress / Evergrande",
        windows=((date(2021, 9, 1), date(2022, 11, 30)),),
        stress_focus="CN credit, CNH, HK equities, Asia beta",
        tags=("credit", "fx", "equities", "china", "asia-em"),
    ),
    Scenario(
        name="COVID crash / liquidity crisis",
        windows=((date(2020, 2, 20), date(2020, 3, 23)),),
        stress_focus="Everything: USD funding, equities, rates, FX basis, credit",
        tags=("liquidity", "equities", "rates", "fx", "credit", "vol", "risk-off"),
    ),
    Scenario(
        name="WTI negative / oil crash",
        windows=((date(2020, 4, 20), date(2020, 4, 20)),),
        stress_focus="Oil-linked FX, breakevens, energy credit",
        tags=("oil-shock", "commodities", "fx", "credit", "inflation"),
    ),
    Scenario(
        name="Volmageddon",
        windows=((date(2018, 2, 5), date(2018, 2, 5)),),
        stress_focus="Equity vol, short-vol unwind, rates vol",
        tags=("vol", "equities", "rates", "carry-unwind"),
    ),
    Scenario(
        name="US-China trade war phase 1",
        windows=((date(2018, 3, 1), date(2019, 10, 31)),),
        stress_focus="CNY/CNH, KRW/TWD, Asian exporters, equities",
        tags=("fx", "equities", "china", "asia-em", "geopolitical"),
    ),
    Scenario(
        name="Q4-2018 Fed/risk crash",
        windows=((date(2018, 10, 1), date(2018, 12, 31)),),
        stress_focus="Equities, credit, front-end repricing",
        tags=("equities", "credit", "rates", "risk-off", "us"),
    ),
    Scenario(
        name="Brexit referendum",
        windows=((date(2016, 6, 23), date(2016, 6, 24)),),
        stress_focus="GBP, EUR, risk-off, global duration rally",
        tags=("fx", "rates", "duration", "risk-off", "uk", "europe", "geopolitical"),
    ),
    Scenario(
        name="China RMB deval / China equity shock",
        windows=((date(2015, 8, 11), date(2016, 2, 29)),),
        stress_focus="CN/HK/Asia FX, commodities, EM equities",
        tags=("fx", "commodities", "equities", "china", "asia-em", "em"),
    ),
    Scenario(
        name="China Black Monday",
        windows=((date(2015, 8, 24), date(2015, 8, 24)),),
        stress_focus="Equity crash, CNH, Asia beta",
        tags=("equities", "fx", "china", "asia-em", "risk-off"),
    ),
    Scenario(
        name="Oil collapse / deflation scare",
        windows=((date(2014, 6, 1), date(2016, 2, 29)),),
        stress_focus="Oil beta, breakevens, CAD/MYR/IDR, energy credit",
        tags=("oil-shock", "commodities", "fx", "credit", "inflation", "em"),
    ),
    Scenario(
        name="Taper tantrum",
        windows=((date(2013, 5, 22), date(2013, 9, 6)),),
        stress_focus="EM FX/rates beta, USD duration shock",
        tags=("fx", "rates", "duration", "em", "us"),
    ),
    Scenario(
        name="US debt ceiling / S&P downgrade",
        windows=((date(2011, 8, 5), date(2011, 8, 5)),),
        stress_focus="UST rally/risk-off, USD, equities, gold",
        tags=("rates", "sovereign-stress", "fx", "equities", "commodities",
              "risk-off", "us"),
    ),
    Scenario(
        name="Euro sovereign crisis",
        windows=((date(2010, 5, 1), date(2012, 9, 6)),),
        stress_focus="EUR rates, peripheral spreads, USD funding, global bank beta",
        tags=("rates", "sovereign-stress", "credit", "banking-stress", "fx",
              "liquidity", "europe"),
    ),
)


# Module-load taxonomy guard: catches typos/dead tags at import time, so
# `sc.tags` callers don't need to re-validate.
_unknown = {t for sc in SCENARIOS for t in sc.tags} - CANONICAL_TAGS
assert not _unknown, f"SCENARIOS uses non-canonical tags: {sorted(_unknown)}"
_unused = CANONICAL_TAGS - {t for sc in SCENARIOS for t in sc.tags}
assert not _unused, f"CANONICAL_TAGS never used by any scenario: {sorted(_unused)}"
del _unknown, _unused


def _upsert_scenario(session, sc: Scenario) -> tuple[int, bool]:
    """Insert or update dim_scenario row. Returns (scenario_id, was_new).

    Only writes updated_at when stress_focus actually changed — avoids spurious
    audit churn on idempotent re-runs.
    """
    row = session.execute(
        text(
            "SELECT id, stress_focus_raw FROM dbo.dim_scenario "
            "WHERE display_name = :name"
        ),
        {"name": sc.name},
    ).fetchone()
    if row is None:
        result = session.execute(
            text(
                "INSERT INTO dbo.dim_scenario (display_name, stress_focus_raw) "
                "OUTPUT INSERTED.id "
                "VALUES (:name, :focus)"
            ),
            {"name": sc.name, "focus": sc.stress_focus},
        )
        return int(result.scalar_one()), True
    scenario_id, current_focus = int(row[0]), row[1]
    if current_focus != sc.stress_focus:
        session.execute(
            text(
                "UPDATE dbo.dim_scenario "
                "SET stress_focus_raw = :focus, updated_at = SYSDATETIMEOFFSET() "
                "WHERE id = :id"
            ),
            {"focus": sc.stress_focus, "id": scenario_id},
        )
    return scenario_id, False


# Legacy "SQL Server" ODBC driver cannot bind datetime.date or None to DATE
# columns (HYC00 SQLBindParameter). Project convention is to bind dates as ISO
# strings — SQL Server converts implicitly. See src/imdr/connectors/bulk.py and
# MEMORY.md (ODBC driver: legacy `SQL Server`).
_INSERT_WINDOW_DATED = text(
    "INSERT INTO dbo.scenario_window (scenario_id, seq, start_date, end_date) "
    "VALUES (:sid, :seq, :start, :end)"
)
_INSERT_WINDOW_OPEN = text(
    "INSERT INTO dbo.scenario_window (scenario_id, seq, start_date, end_date) "
    "VALUES (:sid, :seq, :start, NULL)"
)


def _replace_windows(session, scenario_id: int, sc: Scenario) -> None:
    """Delete + reinsert all windows for this scenario."""
    session.execute(
        text("DELETE FROM dbo.scenario_window WHERE scenario_id = :id"),
        {"id": scenario_id},
    )
    for seq, (start, end) in enumerate(sc.windows, start=1):
        if end is None:
            session.execute(
                _INSERT_WINDOW_OPEN,
                {"sid": scenario_id, "seq": seq, "start": start.isoformat()},
            )
        else:
            session.execute(
                _INSERT_WINDOW_DATED,
                {
                    "sid": scenario_id,
                    "seq": seq,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
            )


def _upsert_tag(session, tag: str) -> int:
    row = session.execute(
        text("SELECT id FROM dbo.dim_stress_tag WHERE tag = :tag"),
        {"tag": tag},
    ).fetchone()
    if row is not None:
        return int(row[0])
    result = session.execute(
        text("INSERT INTO dbo.dim_stress_tag (tag) OUTPUT INSERTED.id VALUES (:tag)"),
        {"tag": tag},
    )
    return int(result.scalar_one())


def _rebuild_bridge(session, scenario_id: int, sc: Scenario) -> None:
    """Delete + reinsert scenario_stress_tag bridge rows for this scenario."""
    session.execute(
        text("DELETE FROM dbo.scenario_stress_tag WHERE scenario_id = :id"),
        {"id": scenario_id},
    )
    for tag in sc.tags:
        tag_id = _upsert_tag(session, tag)
        session.execute(
            text(
                "INSERT INTO dbo.scenario_stress_tag (scenario_id, tag_id) "
                "VALUES (:sid, :tid)"
            ),
            {"sid": scenario_id, "tid": tag_id},
        )


def main() -> None:
    settings = get_settings()
    connector = MSSQLConnector(settings)

    inserted = updated = 0
    total_windows = sum(len(sc.windows) for sc in SCENARIOS)
    total_tag_links = sum(len(sc.tags) for sc in SCENARIOS)
    try:
        with connector.session() as session:
            for sc in SCENARIOS:
                scenario_id, was_new = _upsert_scenario(session, sc)
                _replace_windows(session, scenario_id, sc)
                _rebuild_bridge(session, scenario_id, sc)
                inserted += was_new
                updated += not was_new
            session.commit()
    finally:
        connector.dispose()

    print(
        f"Seeded scenarios: {inserted} new, {updated} updated. "
        f"Windows: {total_windows}. Tag links: {total_tag_links}."
    )


if __name__ == "__main__":
    main()
