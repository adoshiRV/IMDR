"""Citi Velocity FX proprietary-index group -> IMDR (fx.dim_index_series + fx.fact_index_value).

Citi publishes a family of proprietary FX indices under the Velocity tag root
``FX.<PRODUCT>...``. This module is the country-agnostic, PRODUCT-NEUTRAL library
for ingesting them into the generic ``fx.dim_index_series`` (catalog, one row per
leaf tag) + ``fx.fact_index_value`` (vintage-aware daily values) tables
(migrations 120-122).

Products supported today (probed 2026-07-30, see data/cache/fx/fx_indices_probe.json):

  SURPRISE_INDEX  2,415  Economic/Inflation Surprise Indices (branded CESI + siblings)
  NEER_IDX          133  Nominal Effective Exchange Rate (basket x ccy)
  REER_IDX          195  Real Effective Exchange Rate (basket x ccy)
  CTOT               68  Commodity Terms of Trade (DM/EM x ccy)
  MRICITI            23  Macro Risk Index (family x component; no ccy)
  CITIPAIN           10  Citi Pain Index (G10 positioning, one ccy per tag)
  CRFI                2  Citi Risk Factor Index (EM_VALUE / G10_VALUE)
  LIQUIDITY_IDX      28  FX liquidity indices (region [x quote-leg] density)

SC_SCORECARD (460 tags) is DEFERRED to a Phase 2 -- some of its tags return zero
data; it needs a per-tag data probe before ingest (see the exploration doc).

Each product's tag tokens map onto a shared set of nullable semantic columns;
the per-product mapping is in ``_PRODUCT_PARSERS`` below and mirrored in
migration 120's header + docs/admin/vendors/citi/exploration/fx_indices.md.

Public API:
  * ``parse_tag``     -- decompose ONE leaf tag (dispatches on product_code).
  * ``build_series``  -- tag list (+ dim_currency codes) -> SeriesRow list.
  * ``upsert_series`` -- MERGE SeriesRow list into fx.dim_index_series.
  * ``load_values``   -- vintage-aware load into fx.fact_index_value.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, replace

from sqlalchemy import text

from imdr.connectors.mssql import MSSQLConnector
from imdr.utils.vintage import classify_fact_action  # noqa: F401  (re-exported for tests/callers)

VENDOR_CODE = "citi_velocity"  # dbo.dim_vendor id 1
DAILY_FREQUENCY_CODE = "DAILY"  # dbo.dim_frequency

# product_code -> Citi Velocity tag prefix (also the taglisting prefix).
PRODUCT_PREFIXES: dict[str, str] = {
    "SURPRISE_INDEX": "FX.SURPRISE_INDEX",
    "NEER_IDX": "FX.NEER_IDX",
    "REER_IDX": "FX.REER_IDX",
    "CTOT": "FX.CTOT",
    "MRICITI": "FX.MRICITI",
    "CITIPAIN": "FX.CITIPAIN",
    "CRFI": "FX.CRFI",
    "LIQUIDITY_IDX": "FX.LIQUIDITY_IDX",
}

# Human labels for the "index_type" token, per product, for display_name.
_TYPE_LABELS: dict[str, str] = {
    # SURPRISE_INDEX
    "CESI": "Economic Surprise Index", "CECI": "Economic Change Index",
    "CEDI": "Economic Diffusion Index", "CERI": "Economic Revision Index",
    "EFUI": "Economic Fundamental Uncertainty Index",
    "SI_CISI": "Inflation Surprise Index", "SI_CIDI": "Inflation Diffusion Index",
    "SI_CICI": "Inflation Change Index",
}

_PRODUCT_LABELS: dict[str, str] = {
    "SURPRISE_INDEX": "Surprise Index", "NEER_IDX": "NEER", "REER_IDX": "REER",
    "CTOT": "Commodity Terms of Trade", "MRICITI": "Macro Risk Index",
    "CITIPAIN": "Pain Index", "CRFI": "Risk Factor Index",
    "LIQUIDITY_IDX": "Liquidity Index",
}


@dataclass(frozen=True, slots=True)
class SeriesRow:
    """One leaf tag decomposed into fx.dim_index_series columns.

    All decomposition columns are optional: which ones a product populates is
    product-specific (see the per-product parsers). ``region_currency_code`` is
    a *candidate* ISO code resolved to a dim_currency FK at load time; ``None``
    when the series has no currency axis or the code isn't tracked.
    """

    citi_tag: str
    product_code: str
    display_name: str
    series_family: str | None = None
    index_type: str | None = None
    series_group: str | None = None
    component: str | None = None
    region_code: str | None = None
    sector_code: str | None = None
    region_currency_code: str | None = None


@dataclass(frozen=True, slots=True)
class ValueRow:
    """One (tag, date, value) observation staged for the vintage-aware load."""

    citi_tag: str
    obs_date: datetime.date
    value: float


def _ccy_candidate(token: str) -> str | None:
    """Return an upper-case 3-letter ISO code if the token looks like a currency."""
    return token.upper() if len(token) == 3 and token.isalpha() else None


# ---------------------------------------------------------------------------
# Per-product parsers. Each takes the tokens AFTER `FX.<PRODUCT>` and returns a
# dict of SeriesRow fields (minus citi_tag/product_code/display_name, which the
# dispatcher fills). Mapping mirrors migration 120's header comment.
# ---------------------------------------------------------------------------

def _parse_surprise_index(t: list[str]) -> dict:
    # family.type.group.region[.sector]   (ESI 5-token / ISI 4-token after prefix)
    if len(t) < 4:
        raise ValueError("SURPRISE_INDEX tag too short")
    family, index_type, group, region = t[:4]
    sector = t[4] if len(t) >= 5 else None
    ccy = None
    if region.startswith("SI_"):
        ccy = _ccy_candidate(region[3:])
    return {"series_family": family, "index_type": index_type, "series_group": group,
            "region_code": region, "sector_code": sector, "region_currency_code": ccy}


def _parse_eer(t: list[str]) -> dict:
    # NEER/REER: basket.ccy
    if len(t) < 2:
        raise ValueError("NEER/REER tag too short")
    basket, region = t[0], t[1]
    return {"index_type": basket, "region_code": region,
            "region_currency_code": _ccy_candidate(region)}


def _parse_ctot(t: list[str]) -> dict:
    # group.CTOT_<ccy>
    if len(t) < 2:
        raise ValueError("CTOT tag too short")
    group, region = t[0], t[1]
    ccy = _ccy_candidate(region[5:]) if region.startswith("CTOT_") else None
    return {"series_group": group, "region_code": region, "region_currency_code": ccy}


def _parse_mriciti(t: list[str]) -> dict:
    # mri_family.component  (no currency/region)
    if len(t) < 2:
        raise ValueError("MRICITI tag too short")
    return {"index_type": t[0], "component": t[1]}


def _parse_citipain(t: list[str]) -> dict:
    # ccy
    if len(t) < 1:
        raise ValueError("CITIPAIN tag too short")
    return {"region_code": t[0], "region_currency_code": _ccy_candidate(t[0])}


def _parse_crfi(t: list[str]) -> dict:
    # EM_VALUE | G10_VALUE  (no region)
    if len(t) < 1:
        raise ValueError("CRFI tag too short")
    return {"index_type": t[0]}


def _parse_liquidity(t: list[str]) -> dict:
    # region[.quote_leg].DENSITY.CITI  (drop the trailing CITI; DENSITY is the type)
    toks = list(t)
    if toks and toks[-1] == "CITI":
        toks.pop()
    index_type = None
    if toks and toks[-1] == "DENSITY":
        index_type = toks.pop()
    if not toks:
        raise ValueError("LIQUIDITY_IDX tag has no region")
    region = toks[0]
    component = toks[1] if len(toks) > 1 else None  # quote-leg ccy of a pair
    return {"index_type": index_type, "region_code": region, "component": component,
            "region_currency_code": _ccy_candidate(region)}


_PRODUCT_PARSERS = {
    "SURPRISE_INDEX": _parse_surprise_index,
    "NEER_IDX": _parse_eer,
    "REER_IDX": _parse_eer,
    "CTOT": _parse_ctot,
    "MRICITI": _parse_mriciti,
    "CITIPAIN": _parse_citipain,
    "CRFI": _parse_crfi,
    "LIQUIDITY_IDX": _parse_liquidity,
}


def parse_tag(tag: str) -> SeriesRow:
    """Decompose a ``FX.<PRODUCT>...`` leaf tag into fx.dim_index_series columns.

    Dispatches on ``product_code`` (the 2nd tag token). Raises ``ValueError`` for
    non-FX tags, unknown/deferred products (e.g. SC_SCORECARD), or malformed tags.
    """
    parts = tag.split(".")
    if len(parts) < 3 or parts[0] != "FX":
        raise ValueError(f"Not an FX proprietary-index tag: {tag!r}")
    product = parts[1]
    parser = _PRODUCT_PARSERS.get(product)
    if parser is None:
        raise ValueError(f"Unsupported/deferred Citi FX index product: {product!r}")
    fields = parser(parts[2:])
    return SeriesRow(
        citi_tag=tag,
        product_code=product,
        display_name=_display_name(product, fields),
        **fields,
    )


def _display_name(product: str, fields: dict) -> str:
    """Readable label, e.g. 'Citi NEER [BROAD] - AUD' or
    'Citi Economic Surprise Index [CESI] - SI_USD - TOTAL (DM)'."""
    itype = fields.get("index_type")
    # SURPRISE_INDEX: the type code IS the identity (CESI/CECI/...), so lead with
    # its human label and keep the code in brackets. Other products: lead with the
    # product name and bracket the type token (basket/family/etc.).
    if product == "SURPRISE_INDEX" and itype:
        head = f"Citi {_TYPE_LABELS.get(itype, itype)} [{itype}]"
    else:
        head = f"Citi {_PRODUCT_LABELS.get(product, product)}"
        if itype:
            head += f" [{itype}]"
    bits = [head]
    for key in ("region_code", "component", "sector_code"):
        val = fields.get(key)
        if val:
            bits.append(val)
    name = " - ".join(bits)
    group = fields.get("series_group")
    return f"{name} ({group})" if group else name


def build_series(tags: list[str], currency_codes: set[str]) -> list[SeriesRow]:
    """Parse tags to SeriesRow, keeping a per-currency FK only for real currencies.

    ``currency_codes`` is the set of ``code`` values in dbo.dim_currency. A parsed
    currency candidate not in that set (e.g. UAH when untracked) resolves to
    ``None`` rather than forcing a match.
    """
    upper = {c.upper() for c in currency_codes}
    out: list[SeriesRow] = []
    for tag in tags:
        row = parse_tag(tag)
        if row.region_currency_code and row.region_currency_code.upper() not in upper:
            row = replace(row, region_currency_code=None)
        out.append(row)
    return out


# The vintage predicate the fact-load SQL implements lives in
# imdr.utils.vintage.classify_fact_action (shared with the econ loader); imported
# at module top and re-exported so tests/callers can reach it here.


# ---------------------------------------------------------------------------
# Dim upsert
# ---------------------------------------------------------------------------

_DIM_MERGE_SQL = """
MERGE fx.dim_index_series AS tgt
USING (SELECT :citi_tag AS citi_tag) AS src
   ON tgt.citi_tag = src.citi_tag
WHEN MATCHED THEN UPDATE SET
    series_family      = :series_family,
    index_type         = :index_type,
    series_group       = :series_group,
    component          = :component,
    region_code        = :region_code,
    sector_code        = :sector_code,
    region_currency_id = (SELECT id FROM dbo.dim_currency WHERE code = :region_currency_code),
    display_name       = :display_name,
    is_active          = 1,
    updated_at         = SYSDATETIMEOFFSET()
WHEN NOT MATCHED THEN INSERT
    (vendor_id, citi_tag, product_code, series_family, index_type, series_group,
     component, region_code, sector_code, region_currency_id, frequency_id, display_name)
VALUES (
    (SELECT id FROM dbo.dim_vendor WHERE vendor_code = :vendor_code),
    :citi_tag, :product_code, :series_family, :index_type, :series_group,
    :component, :region_code, :sector_code,
    (SELECT id FROM dbo.dim_currency WHERE code = :region_currency_code),
    (SELECT id FROM dbo.dim_frequency WHERE frequency_code = :frequency_code),
    :display_name
);
"""


def upsert_series(connector: MSSQLConnector, series: list[SeriesRow]) -> dict[str, int]:
    """MERGE series into fx.dim_index_series; return {citi_tag: id} for all rows."""
    if not series:
        return {}
    with connector.engine.begin() as conn:
        for s in series:
            conn.execute(text(_DIM_MERGE_SQL), {
                "vendor_code": VENDOR_CODE,
                "frequency_code": DAILY_FREQUENCY_CODE,
                "citi_tag": s.citi_tag,
                "product_code": s.product_code,
                "series_family": s.series_family,
                "index_type": s.index_type,
                "series_group": s.series_group,
                "component": s.component,
                "region_code": s.region_code,
                "sector_code": s.sector_code,
                "region_currency_code": s.region_currency_code,
                "display_name": s.display_name,
            })
        tags = [s.citi_tag for s in series]
        result: dict[str, int] = {}
        for i in range(0, len(tags), 500):  # keep IN-clause params under 2100
            chunk = tags[i:i + 500]
            params = {f"t{j}": t for j, t in enumerate(chunk)}
            placeholders = ", ".join(f":t{j}" for j in range(len(chunk)))
            rows = conn.execute(
                text(f"SELECT citi_tag, id FROM fx.dim_index_series WHERE citi_tag IN ({placeholders})"),
                params,
            ).all()
            for r in rows:
                result[r[0]] = int(r[1])
    return result


# ---------------------------------------------------------------------------
# Vintage-aware fact load (staging temp table + set-based INSERTs)
#
# Same contract as econ.fact_indicator (docs econ §3.3): vintage 0 is the first
# reading for a (series_id, obs_date); a re-pull whose value materially differs
# from the current latest vintage appends a NEW row at cur_vintage+1 (Citi
# restandardizations are captured, not overwritten); an unchanged value is
# skipped. "Latest belief" = MAX(vintage) per (series_id, obs_date), exposed by
# fx.vw_fact_index_value_latest (migration 122). value is NOT NULL in this
# fact, so there's no NULL-clobber case to guard (Citi returns no NULL points).
# ---------------------------------------------------------------------------

_STG_CREATE_SQL = """
IF OBJECT_ID('tempdb..#stg_index_val') IS NOT NULL DROP TABLE #stg_index_val;
CREATE TABLE #stg_index_val (
    series_id INT           NOT NULL,
    obs_date  DATE          NOT NULL,
    value     DECIMAL(18,6) NOT NULL
);
"""

_STG_INSERT_SQL = "INSERT INTO #stg_index_val (series_id, obs_date, value) VALUES (?, ?, ?)"

# Collapse intra-batch dupes to one row per (series_id, obs_date) so the
# computed cur_vintage+1 can't collide within a single load. A full-history
# backfill returns each (series, date) once, but the last daily point can
# recur across overlapping catch-up windows.
_DEDUP_SQL = """
IF OBJECT_ID('tempdb..#stg_dedup') IS NOT NULL DROP TABLE #stg_dedup;
SELECT series_id, obs_date, value
INTO #stg_dedup
FROM (
    SELECT series_id, obs_date, value,
           ROW_NUMBER() OVER (PARTITION BY series_id, obs_date ORDER BY value) AS rn
    FROM #stg_index_val
) q
WHERE rn = 1;
"""

# Current latest (vintage, value) per staged pair -- restricted to the pairs in
# this batch so it seeks ix_fact_index_value_series_date, not a full scan.
_CURLATEST_SQL = """
IF OBJECT_ID('tempdb..#cur_latest') IS NOT NULL DROP TABLE #cur_latest;
SELECT f.series_id, f.obs_date, f.vintage AS cur_vintage, f.value AS cur_value
INTO #cur_latest
FROM fx.fact_index_value f
JOIN (
    SELECT f2.series_id, f2.obs_date, MAX(f2.vintage) AS mv
    FROM fx.fact_index_value f2
    JOIN (SELECT DISTINCT series_id, obs_date FROM #stg_dedup) sp
      ON sp.series_id = f2.series_id AND sp.obs_date = f2.obs_date
    GROUP BY f2.series_id, f2.obs_date
) m ON m.series_id = f.series_id AND m.obs_date = f.obs_date AND m.mv = f.vintage;
"""

_INSERT_NEW_SQL = """
INSERT INTO fx.fact_index_value (series_id, obs_date, vintage, value)
SELECT s.series_id, s.obs_date, 0, s.value
FROM #stg_dedup s
LEFT JOIN #cur_latest c ON c.series_id = s.series_id AND c.obs_date = s.obs_date
WHERE c.series_id IS NULL;
"""

# Both sides DECIMAL(18,6) -> exact equality, no float noise.
_INSERT_REVISION_SQL = """
INSERT INTO fx.fact_index_value (series_id, obs_date, vintage, value)
SELECT s.series_id, s.obs_date, c.cur_vintage + 1, s.value
FROM #stg_dedup s
JOIN #cur_latest c ON c.series_id = s.series_id AND c.obs_date = s.obs_date
WHERE s.value <> c.cur_value;
"""


def load_values(
    connector: MSSQLConnector,
    values: list[ValueRow],
    tag_to_id: dict[str, int],
) -> dict[str, int]:
    """Vintage-aware load of observations into fx.fact_index_value.

    Returns {staged, inserted_new, inserted_revision, skipped, duplicates_collapsed}.
    """
    unknown = sorted({v.citi_tag for v in values} - set(tag_to_id))
    if unknown:
        raise RuntimeError(
            f"{len(unknown)} value tags have no dim row; e.g. {unknown[:5]}"
        )
    rows = [(tag_to_id[v.citi_tag], v.obs_date, float(v.value)) for v in values]
    if not rows:
        return {"staged": 0, "inserted_new": 0, "inserted_revision": 0,
                "skipped": 0, "duplicates_collapsed": 0}

    raw_conn = connector.engine.raw_connection()
    inserted_new = inserted_revision = staged_dedup = 0
    try:
        cursor = raw_conn.cursor()
        cursor.fast_executemany = True

        for stmt in _STG_CREATE_SQL.strip().split(";"):
            if stmt.strip():
                cursor.execute(stmt)
        raw_conn.commit()

        cursor.executemany(_STG_INSERT_SQL, rows)
        raw_conn.commit()

        cursor.execute(_DEDUP_SQL)
        cursor.execute(_CURLATEST_SQL)
        raw_conn.commit()

        cursor.execute("SELECT COUNT(*) FROM #stg_dedup")
        staged_dedup = cursor.fetchone()[0]

        cursor.execute(_INSERT_NEW_SQL)
        inserted_new = cursor.rowcount
        cursor.execute(_INSERT_REVISION_SQL)
        inserted_revision = cursor.rowcount
        raw_conn.commit()

        cursor.execute("DROP TABLE IF EXISTS #cur_latest")
        cursor.execute("DROP TABLE IF EXISTS #stg_dedup")
        cursor.execute("DROP TABLE IF EXISTS #stg_index_val")
        raw_conn.commit()
        cursor.close()
    finally:
        raw_conn.close()

    return {
        "staged": len(rows),
        "inserted_new": inserted_new,
        "inserted_revision": inserted_revision,
        "skipped": staged_dedup - inserted_new - inserted_revision,
        "duplicates_collapsed": len(rows) - staged_dedup,
    }
