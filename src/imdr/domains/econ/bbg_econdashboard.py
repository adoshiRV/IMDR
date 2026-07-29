"""BBG EconDashboards -> IMDR econ (country-agnostic library).

Reads the APAC EconDashboards local Bloomberg cache -- a SQLite the dashboard
app maintains at ``Z:\\Business\\Research\\Dashboard\\EconDashboards\\data\\
econ_dashboard.sqlite3`` -- and returns canonical ``IndicatorRow`` /
``ObservationRow`` lists for ONE country. The per-country prod fetchers at
``scripts/econ/{cc}/bbg/bbg_econdashboard.py`` wrap this with
``scripts.econ._runner.run_main`` (country-first layout, per econ_to_prod.md).

The SQLite is a READ-ONLY staging layer: the dashboard app owns the Terminal/
BQL pull + release-gating; this library only mirrors its ``series`` catalog +
``observations`` history into IMDR under the BBG vendor.

Identity:  ``BBG.{CONCEPT}.{CC}``   e.g. ``BBG.PMI.HEADLINE.AU``
  vendor      = bbg  (dbo.dim_vendor 'BBG', id 4)
  source_code = raw Bloomberg ticker ("AUCPIYOY Index")  <- loader MERGE key

Units are resolved from Bloomberg's own ``currency`` / ``quote_units`` metadata
(saved in the SQLite), not guessed: trade series carry their true local
currency + native scale (aud_mn, idr_bn, inr_cr, twd_bn, ...).
"""

from __future__ import annotations

import datetime
import sqlite3
import sys
from pathlib import Path

from imdr.domains.econ.schema import IndicatorRow, ObservationRow

UTC = datetime.timezone.utc

DEFAULT_SQLITE = Path(
    r"Z:\Business\Research\Dashboard\EconDashboards\data\econ_dashboard.sqlite3"
)

VENDOR_NAME = "bbg"  # loader lower-cases + resolves via _VENDOR_ALIASES -> 'BBG'

# Categories that have a dedicated, better-structured home in another schema and
# are therefore NOT mirrored into econ:
#   swap_5y     -> rates.fact_observation (per-ccy curve + tenor model)
#   policy_rate -> rates.fact_bench_rates (central-bank benchmark model)
#   oil_price   -> commodities.fact_spot (CO1 Brent; commodity, not econ)
# Keeping market data out of the flat econ indicator table so it lives in its
# proper schema. Anything here is intentionally skipped; anything NOT here and
# NOT in CONCEPT_MAP is an *unhandled* category and is surfaced as a warning
# (so new series the dashboard app adds upstream are never silently dropped).
ECON_EXCLUDED_CATEGORIES = frozenset({"swap_5y", "policy_rate", "oil_price"})

# --------------------------------------------------------------------------
# Dashboard-category -> IMDR mappings. Each of the 17 EconDashboards categories
# maps onto an EXISTING econ.dim_indicator_category theme + dim_unit / dim_
# frequency code, so the loader resolves every FK without a new migration
# (beyond migration 118, which seeded myr_mn/thb_mn/php_mn/twd_bn).
# --------------------------------------------------------------------------

# dashboard category -> econ.dim_indicator_category.category_code.
# swap_5y / policy_rate / oil_price are intentionally absent -- they are routed
# to other schemas via ECON_EXCLUDED_CATEGORIES and never reach these maps.
CATEGORY_MAP: dict[str, str] = {
    "gdp_yoy": "gdp",
    "cpi_yoy": "cpi",
    "core_cpi_yoy": "cpi",        # core / underlying CPI
    "ppi_yoy": "cpi",             # IMDR files producer prices under the price theme
    "current_account": "bop",
    "fiscal_balance": "other",    # no fiscal theme in dim_indicator_category
    "pmi": "sentiment",           # diffusion/survey index
    "exports": "bop",
    "imports": "bop",
    "neer": "fx",
    "reer": "fx",
    "twi": "fx",
    "big_mac": "fx",              # FX-valuation concept
    "surprise": "sentiment",      # Citi economic-surprise index
    "trade_china": "bop",
    "trade_us": "bop",
}

# dashboard category -> imdr_code concept segment (BBG.{CONCEPT}.{CC})
CONCEPT_MAP: dict[str, str] = {
    "gdp_yoy": "GDP.YOY",
    "cpi_yoy": "CPI.YOY",
    "core_cpi_yoy": "CPI.CORE.YOY",
    "ppi_yoy": "PPI.YOY",
    "current_account": "BOP.CURRENT_ACCOUNT",
    "fiscal_balance": "FISCAL.BALANCE",
    "pmi": "PMI.HEADLINE",
    "exports": "TRADE.EXPORTS",
    "imports": "TRADE.IMPORTS",
    "neer": "FX.NEER",
    "reer": "FX.REER",
    "twi": "FX.TWI",
    "big_mac": "FX.BIGMAC",
    "surprise": "SENTIMENT.CESI",
    "trade_china": "TRADE.CN_BILATERAL",
    "trade_us": "TRADE.US_BILATERAL",
}

# Per-(category, country) concept overrides. The US exports/imports tickers
# (GDPTEXP% / GDPTIMP%) are a GDP-CONTRIBUTION percentage, not an absolute
# trade level like every other country's exports/imports -- so they get a
# distinct concept to keep BBG.TRADE.EXPORTS.{cc} commensurate cross-country.
CONCEPT_OVERRIDES: dict[tuple[str, str], str] = {
    ("exports", "US"): "TRADE.EXPORTS_CONTRIB",
    ("imports", "US"): "TRADE.IMPORTS_CONTRIB",
}

# dashboard category -> dbo.dim_unit.unit_code, for categories whose unit is
# fixed regardless of country. Trade (exports/imports) is NOT here -- its unit
# is the ticker's own local currency + scale, resolved from Bloomberg metadata
# by _resolve_unit() below.
UNIT_MAP: dict[str, str] = {
    "gdp_yoy": "pct_yoy",
    "cpi_yoy": "pct_yoy",
    "ppi_yoy": "pct_yoy",
    "current_account": "pct_of_gdp",   # BBG quote = Percent / % RATIO / % of GDP
    "fiscal_balance": "pct_of_gdp",     # BBG quote = %
    "pmi": "index",                     # diffusion index (50 = neutral)
    "neer": "index_2020_100",           # BIS effective-exchange-rate index
    "reer": "index_2020_100",
    "twi": "index",                     # trade-weighted index (mixed base years)
    "big_mac": "usd",                   # BBG currency = USD
    "surprise": "index",                # Citi economic-surprise index (points)
    "trade_china": "usd_mn",            # bilateral trade, BBG = USD millions
    "trade_us": "usd_mn",
}

# Bloomberg `currency` (ISO) -> IMDR dim_unit currency prefix (trade only).
_CCY_PREFIX: dict[str, str] = {
    "AUD": "aud", "HKD": "hkd", "IDR": "idr", "INR": "inr", "JPY": "jpy",
    "KRW": "krw", "MYR": "myr", "NZD": "nzd", "PHP": "php", "SGD": "sgd",
    "THB": "thb", "TWD": "twd", "USD": "usd",
}

# EconDashboards native_frequency -> dbo.dim_frequency.frequency_code
FREQ_MAP: dict[str, str] = {
    "Daily": "DAILY",
    "Intraday": "SNAPSHOT",
    "Weekly": "WEEKLY",
    "Monthly": "MONTHLY",
    "Quarterly": "QUARTERLY",
    "Yearly": "ANNUAL",
}
# fallback frequency when native_frequency is NULL, keyed by category
FREQ_DEFAULT_BY_CAT: dict[str, str] = {
    "surprise": "DAILY",
    "twi": "DAILY",
    "gdp_yoy": "QUARTERLY",   # GDP is quarterly -- must not fall back to MONTHLY
    "big_mac": "SEMIANNUAL",
    "neer": "MONTHLY",
    "reer": "MONTHLY",
}
FREQ_FALLBACK = "MONTHLY"


# --------------------------------------------------------------------------
# Resolvers
# --------------------------------------------------------------------------

def _concept(category: str, country_iso: str) -> str:
    return CONCEPT_OVERRIDES.get((category, country_iso), CONCEPT_MAP[category])


def _resolve_frequency(native: str | None, category: str) -> str:
    if native and native in FREQ_MAP:
        return FREQ_MAP[native]
    return FREQ_DEFAULT_BY_CAT.get(category, FREQ_FALLBACK)


def _resolve_unit(category: str, currency: str | None, quote_units: str | None) -> str:
    """Accurate unit from Bloomberg metadata.

    Fixed-unit categories come from UNIT_MAP. exports/imports carry the ticker's
    own local currency at Bloomberg's native scale (Million/Billion/Crore), e.g.
    AUNAEXP -> aud_mn, IDGECEX -> idr_bn, IGQREXP -> inr_cr, TWEDCHIN -> twd_bn.
    The US trade contribution tickers (GDPTEXP%/GDPTIMP%) print as a % with no
    currency -> pct.
    """
    q = (quote_units or "").strip().lower()
    if category == "core_cpi_yoy":
        # mostly YoY %, but a few markets carry a rebased index level instead;
        # detect an index by a base-year tag ("2010=100") or the literal word.
        return "index" if ("=100" in q or q.endswith("100") or "index" in q) else "pct_yoy"
    if category in UNIT_MAP:
        return UNIT_MAP[category]
    if not currency or q in ("%", "percent"):
        return "pct"                       # US GDPTEXP% / GDPTIMP% contribution
    prefix = _CCY_PREFIX.get(currency.upper())
    if prefix is None:
        return "usd_mn"                     # defensive fallback (shouldn't hit)
    if "crore" in q:
        return "inr_cr"                     # INR reports in crore, not mn/bn
    scale = "bn" if "billion" in q else "mn"
    return f"{prefix}_{scale}"


def read_ticker_observations(
    tickers: list[str],
    sqlite_path: Path | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, list[tuple[datetime.date, float]]]:
    """Low-level read: (obs_date, value) history for a set of raw BBG tickers.

    Shared by the econ mirror and the rates-schema landing (policy rates) so the
    EconDashboards SQLite access lives in one place. Returns {ticker: [(date,
    value), ...]} ordered by date, value-non-null only.
    """
    path = Path(sqlite_path) if sqlite_path else DEFAULT_SQLITE
    if not path.exists():
        raise FileNotFoundError(f"EconDashboards SQLite not found: {path}")
    if not tickers:
        return {}
    params: list[str] = list(tickers)
    clause = ""
    if since:
        clause += " AND observation_date >= ?"
        params.append(since)
    if until:
        clause += " AND observation_date <= ?"
        params.append(until)
    placeholders = ",".join("?" for _ in tickers)
    con = sqlite3.connect(str(path))
    try:
        rows = con.execute(
            f"""
            SELECT ticker, observation_date, value FROM observations
            WHERE ticker IN ({placeholders}) AND value IS NOT NULL{clause}
            ORDER BY ticker, observation_date
            """,
            params,
        ).fetchall()
    finally:
        con.close()
    out: dict[str, list[tuple[datetime.date, float]]] = {}
    for ticker, obs_date, value in rows:
        out.setdefault(ticker, []).append(
            (datetime.date.fromisoformat(obs_date[:10]), float(value))
        )
    return out


def _parse_release(raw: str | None, obs_date: datetime.date) -> datetime.datetime:
    if raw:
        try:
            dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            pass
    return datetime.datetime(obs_date.year, obs_date.month, obs_date.day, tzinfo=UTC)


# --------------------------------------------------------------------------
# Fetch (one country)
# --------------------------------------------------------------------------

def fetch_econdashboard(
    country_code: str,
    since: str | None = None,
    until: str | None = None,
    sqlite_path: Path | None = None,
    existing_codes: dict[str, str] | None = None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Return (indicators, observations) for one country from the SQLite.

    ``country_code`` is a 2-letter ISO code (e.g. ``"AU"``); matched against the
    SQLite ``series.country_code`` (upper-case). ``since`` / ``until`` bound
    ``obs_date`` (inclusive, YYYY-MM-DD).

    ``existing_codes`` maps a raw Bloomberg ticker (``source_code``) to the
    ``imdr_code`` already persisted for it in ``econ.dim_indicator``. Pass it
    (the prod ingest reads it from the DB) so that a code -- including a
    collision-disambiguation suffix like ``.AU.2`` -- assigned on a prior run is
    REUSED verbatim and never migrates to a different ticker when the upstream
    catalogue grows. Without it, assignment is stable only within a single run.
    """
    cc = country_code.strip().upper()
    path = Path(sqlite_path) if sqlite_path else DEFAULT_SQLITE
    if not path.exists():
        raise FileNotFoundError(f"EconDashboards SQLite not found: {path}")
    since_d = datetime.date.fromisoformat(since) if since else None
    until_d = datetime.date.fromisoformat(until) if until else None

    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    try:
        series = con.execute(
            """
            SELECT s.ticker, s.country_code, s.country_name, s.category,
                   s.category_label, s.native_frequency, s.seasonality_transform,
                   s.currency, s.quote_units
            FROM series s
            WHERE s.country_code = ?
              AND EXISTS (SELECT 1 FROM observations o WHERE o.ticker = s.ticker)
            ORDER BY s.category, s.ticker
            """,
            (cc,),
        ).fetchall()

        # Eligible rows: skip excluded categories silently, unmapped ones loudly.
        eligible: list[tuple[sqlite3.Row, str, str]] = []  # (row, category, base_code)
        for s in series:
            cat = s["category"]
            if cat in ECON_EXCLUDED_CATEGORIES:
                continue  # routed to a dedicated schema (rates / commodities)
            if cat not in CONCEPT_MAP:
                # New category added upstream that we don't yet map -- surface it
                # loudly rather than silently dropping the series.
                print(
                    f"WARN [bbg_econdashboard] unhandled category {cat!r} "
                    f"(ticker {s['ticker']}, {cc}) -- skipped; add to CONCEPT_MAP "
                    f"or ECON_EXCLUDED_CATEGORIES.",
                    file=sys.stderr,
                )
                continue
            eligible.append((s, cat, f"BBG.{_concept(cat, cc)}.{cc}"))

        # Assign imdr_codes so a suffix, once persisted, NEVER moves. Pass 1
        # reuses any code already in the DB for this ticker; pass 2 mints codes
        # for genuinely-new tickers, disambiguating a rare (concept, cc)
        # collision against codes already taken (persisted + freshly minted).
        existing = existing_codes or {}
        ticker_to_code: dict[str, str] = {}
        used_codes: set[str] = set()
        for s, _cat, _base in eligible:
            tk = s["ticker"]
            if tk in existing:
                ticker_to_code[tk] = existing[tk]
                used_codes.add(existing[tk])
        for s, _cat, base in eligible:
            tk = s["ticker"]
            if tk in ticker_to_code:
                continue
            code, n = base, 2
            while code in used_codes:  # rare (concept, cc) collision
                code, n = f"{base}.{n}", n + 1
            used_codes.add(code)
            ticker_to_code[tk] = code

        indicators: list[IndicatorRow] = []
        for s, cat, _base in eligible:
            transform = (s["seasonality_transform"] or "").upper()
            is_sa = "SA" in transform and "NSA" not in transform
            indicators.append(
                IndicatorRow(
                    imdr_code=ticker_to_code[s["ticker"]],
                    vendor_name=VENDOR_NAME,
                    source_code=s["ticker"],
                    bbg_ticker=s["ticker"],
                    display_name=f"{s['country_name']}: {s['category_label']} (Bloomberg {s['ticker']})",
                    unit=_resolve_unit(cat, s["currency"], s["quote_units"]),
                    frequency=_resolve_frequency(s["native_frequency"], cat),
                    country_iso=cc,
                    category=CATEGORY_MAP[cat],
                    is_seasonally_adjusted=bool(is_sa),
                    is_active=True,
                )
            )

        if not ticker_to_code:
            return [], []

        placeholders = ",".join("?" for _ in ticker_to_code)
        params = list(ticker_to_code)
        clauses = ""
        if since_d:
            clauses += " AND observation_date >= ?"
            params.append(since_d.isoformat())
        if until_d:
            clauses += " AND observation_date <= ?"
            params.append(until_d.isoformat())
        obs_rows = con.execute(
            f"""
            SELECT ticker, observation_date, value, source_updated_at
            FROM observations
            WHERE ticker IN ({placeholders}) AND value IS NOT NULL{clauses}
            ORDER BY ticker, observation_date
            """,
            params,
        ).fetchall()
    finally:
        con.close()

    observations: list[ObservationRow] = []
    for o in obs_rows:
        obs_date = datetime.date.fromisoformat(o["observation_date"][:10])
        observations.append(
            ObservationRow(
                imdr_code=ticker_to_code[o["ticker"]],
                obs_date=obs_date,
                vintage=0,
                release_date=_parse_release(o["source_updated_at"], obs_date),
                value=float(o["value"]) if o["value"] is not None else None,
                is_preliminary=False,
            )
        )
    return indicators, observations
