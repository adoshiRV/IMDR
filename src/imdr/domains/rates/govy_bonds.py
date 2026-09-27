"""Track B — Govy Monitor SQLite ingest.

Reads a **copy** of the Govy Monitor desktop app's SQLite store (never the
live file — see ``open_readonly_copy``) and maps its three source tables to
the ISIN-grained IMDR bond schema (migrations 112/113/114):

  * ``yield_snapshots``  -> ``rates.fact_bond_instrument_obs`` (quote_type=YIELD, units=PCT)
  * ``asw_snapshots``    -> ``rates.fact_bond_instrument_obs`` (quote_type=ASW,   units=BP)
  * ``auction_calendar`` -> ``rates.fact_bond_auction``

``dbo.dim_bond_instrument`` is auto-seeded from the distinct ISINs seen in
the yield + ASW rows (the same auto-seed pattern ``BloombergRatesPipeline``
uses for ``dim_curve``) before the fact rows are built, since the fact rows
reference the resolved ``instrument_id``, not the raw ISIN.

**Vendor Δ columns are display-only, not authoritative.** Confirmed live
2026-07-20: KTB ``chg_1d`` is ALL ZERO in the source on the latest as-of
date (2026-07-17), while India's are populated normally — i.e. the vendor
never finished wiring KTB's day-over-day calc. We store ``chg_1d/1w/1m/3m``
exactly as Govy reports them (faithful copy) and do **not** attempt to
compute or correct them here; the Quick Monitor recomputes Δ from this
table's own stored yield history downstream.

**Dedup decision — one authoritative row per (isin, obs_date, quote_type).**
The source is heavily over-sampled: the desktop app snapshots each bond many
times a day (distinct ``snapshot_ts``), and historical dates carry extra
Excel-backfill rows under a different ``source`` label. Both ``yield_snapshots``
and ``asw_snapshots`` are collapsed to the single end-of-day observation
(latest ``snapshot_ts`` wins), giving the clean daily-curve grain the Quick
Monitor wants. ``pricing_source`` is descriptive (which feed won), not part
of the dedup grain — see ``_dedupe_latest`` for the fact-key idempotency note.
(``asw_snapshots`` has no ``as_of_date`` column, so its obs_date derives from
``snapshot_ts[:10]``; every ASW row carries ``source='local_asw'``, a single
internal calc, not multiple external brokers.)

**pricing_source width gotcha.** ``rates.fact_bond_instrument_obs.pricing_source``
is VARCHAR(12), but live Govy ``source`` values include
``'Excel history import deepak (1).xlsx'`` (37 chars) and
``'Excel BQL history'`` (18 chars). ``_normalize_pricing_source`` maps known
long labels to short codes and truncates anything unmapped — flagged for
review before the load gate (see docs/admin/development/govt_bond_population.md).

**auction source width gotcha.** ``rates.fact_bond_auction.source`` is
VARCHAR(30); live values like ``'RBI Issuance Calendar H1 FY2026-27 (PIB)'``
(40 chars) exceed it. ``_truncate_source`` clips rather than fails the row —
also flagged for review.

Rules honoured: NO EDITS to Govy Monitor (copy + read-only); no writes to
IMDR happen when ``no_load=True``.
"""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.repository_bond import (
    BondAuctionRepository,
    BondInstrumentObsRepository,
    BondInstrumentRepository,
)
from imdr.models.country import DimCountry
from imdr.models.currency import DimCurrency
from imdr.models.frequency import DimFrequency
from imdr.models.vendor import DimVendor
from imdr.schemas.rates_bond import (
    BondAuctionCreate,
    BondInstrumentCreate,
    BondInstrumentObsCreate,
)

_log = structlog.get_logger("GovyBondsPipeline")

LIVE_DB = Path(r"Z:\Business\Research\Dashboard\Govy Monitor\BBG.Yield.DB")

VENDOR_CODE = "BBG"
FREQUENCY_CODE = "DAILY"
DEFAULT_COUNTRIES = ["IGB", "KTB"]

# Govy country_code -> IMDR dim_country.country_code.
GOVY_TO_IMDR: dict[str, str] = {
    "UST": "US", "JGB": "JP", "KTB": "KR", "MGS": "MY", "THAIGB": "TH",
    "INDOGB": "ID", "IGB": "IN", "SIGB": "SG", "RPGB": "PH", "ACGB": "AU",
    "NZGB": "NZ", "CGB": "CN",
}

# rates.fact_bond_instrument_obs.pricing_source is VARCHAR(12); live Govy
# `source` values run much longer (Excel import filenames, history labels).
# Known labels get a short canonical code; anything else is truncated by
# _normalize_pricing_source. Collapsing distinct historical-import labels
# onto one code is fine — pricing_source only needs to disambiguate
# concurrent *live* broker feeds per bond/day (the ASW case), not preserve
# backfill provenance.
_PRICING_SOURCE_MAP: dict[str, str] = {
    "blpapi-bql": "BQL",
    "Excel BQL": "BQL",
    "Excel BQL history": "BQL_HIST",
    "Excel history import deepak (1).xlsx": "EXCEL_IMPORT",
    "workbook_seed": "SEED",
}
_PRICING_SOURCE_MAXLEN = 12

# rates.fact_bond_auction.source is VARCHAR(30); live values (e.g. "RBI
# Issuance Calendar H1 FY2026-27 (PIB)") exceed it. Clip rather than drop —
# provenance stays legible even truncated.
_SOURCE_MAXLEN = 30

# Dry-run-only placeholder so BondInstrumentObsCreate can validate its full
# shape (pricing_source/units/quote_type/etc) without seeding
# dim_bond_instrument, which is a write. Never passed to a repository.
_DRY_RUN_PLACEHOLDER_INSTRUMENT_ID = 1


def open_readonly_copy(src: Path) -> tuple[sqlite3.Connection, Path]:
    """Copy the live DB (+WAL/SHM) to a temp dir and open the copy.

    Copying + opening the copy checkpoints any WAL into a consistent
    snapshot and guarantees we never hold a handle on the live file.
    Mirrors ``playground/bonds/govy_reader.py::open_readonly_copy``.
    """
    tmp = Path(tempfile.mkdtemp(prefix="govy_"))
    dst = tmp / "govy.db"
    shutil.copy2(src, dst)
    for suffix in ("-wal", "-shm"):
        s = src.with_name(src.name + suffix)
        if s.exists():
            shutil.copy2(s, dst.with_name(dst.name + suffix))
    conn = sqlite3.connect(str(dst))
    conn.row_factory = sqlite3.Row
    return conn, dst


def _normalize_pricing_source(raw: str | None) -> str:
    v = (raw or "").strip()
    if v in _PRICING_SOURCE_MAP:
        return _PRICING_SOURCE_MAP[v]
    return v[:_PRICING_SOURCE_MAXLEN] or "UNKNOWN"


def _truncate_source(raw: str | None) -> str | None:
    if raw is None:
        return None
    return raw[:_SOURCE_MAXLEN]


def _none_if_blank(v: Any) -> Any:
    return None if v in (None, "") else v


def _to_utc(ts: str) -> datetime:
    """Parse a Govy ``snapshot_ts``/``fetched_at`` string into a tz-aware UTC datetime.

    Govy stores naive timestamps (no offset in the source); the app's host
    timezone is not recorded anywhere we can read, so we attach UTC as the
    least-assuming choice. Flag for review if the desktop app is confirmed
    to log in a specific local zone.
    """
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _dedupe_latest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep ONE authoritative row per (isin, obs_date, quote_type) — latest obs_ts wins.

    The source carries heavy same-day duplication — the desktop app snapshots
    each bond many times a day (e.g. 24 intraday pulls of one IGB bond, all
    with distinct snapshot_ts), and historical dates additionally carry Excel
    backfill rows. We collapse to the single end-of-day observation per bond
    (the latest snapshot_ts), regardless of which ``source`` label it carries
    — that is the clean daily-curve grain the Quick Monitor wants. The winning
    row keeps whatever ``pricing_source`` it came from (descriptive only).

    Note on the fact table's unique key. The deployed key is
    ``(instrument_id, vendor_id, obs_date, quote_type, pricing_source)`` — a
    *superset* of this dedupe grain — so a single load never collides on it.
    Cross-run idempotency holds in practice: a historical date is not
    re-pulled (its latest snapshot is frozen), and live pulls for recent dates
    are consistently BQL, so the winning source per (isin, date) is stable
    across re-runs. (Were a re-pull ever to change the winning source label on
    an already-loaded date, MERGE would insert a second row for that date; not
    observed in the source, flagged in govt_bond_population.md.)
    """
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["isin"], row["obs_date"], row["quote_type"])
        current = best.get(key)
        if current is None or row["obs_ts"] > current["obs_ts"]:
            best[key] = row
    return list(best.values())


def _dedupe_auctions_latest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one row per (country, auction_date, security_type, term, isin) — latest fetched_at wins.

    Mirrors the fact_bond_auction unique key. The live source has zero
    duplicate auction keys today, but the vendor over-samples the yield/ASW
    tables the same way, so two auction rows sharing this key are plausible;
    without this collapse ``bulk_merge`` would hand SQL Server two source rows
    with an identical MERGE key and the whole run would error out rather than
    degrade gracefully. Blank sentinels ('') already stand in for NULL on the
    text key columns (see extract_auction_rows), so the key is well-defined.
    """
    best: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            row["country_code"], row["auction_date"],
            row["security_type"], row["term"], row["isin"],
        )
        current = best.get(key)
        if current is None or (row["fetched_at"] or "") > (current["fetched_at"] or ""):
            best[key] = row
    return list(best.values())


# ── Extraction (raw source rows -> plain dicts) ──────────────────────────


def extract_yield_rows(conn: sqlite3.Connection, countries: list[str]) -> list[dict[str, Any]]:
    """``yield_snapshots`` -> raw dicts. Skips rows with NULL mid_yield or isin."""
    placeholders = ",".join("?" * len(countries))
    q = f"""SELECT country_code, currency, isin, bbg_ticker, description, maturity_date,
                   tenor_years, mid_yield, chg_1d, chg_1w, chg_1m, chg_3m, source,
                   as_of_date, snapshot_ts
            FROM yield_snapshots WHERE country_code IN ({placeholders})"""
    out: list[dict[str, Any]] = []
    for r in conn.execute(q, countries):
        # A handful of 'workbook_seed' placeholder rows carry isin='' (not
        # NULL) — treat blank the same as NULL, they carry no bond identity.
        # tenor_years is non-optional on BondInstrumentObsCreate, so a NULL
        # would raise ValidationError and abort the whole load; skip it here
        # the same way (0/37k in the source today, defensive for the future).
        if r["mid_yield"] is None or not r["isin"] or r["tenor_years"] is None:
            continue
        out.append({
            "isin": r["isin"],
            "govy_country_code": r["country_code"],
            "country_code": GOVY_TO_IMDR.get(r["country_code"], r["country_code"]),
            "ccy": r["currency"],
            "bbg_ticker": _none_if_blank(r["bbg_ticker"]),
            "description": _none_if_blank(r["description"]),
            "maturity_date": _none_if_blank(r["maturity_date"]),
            "tenor_years": r["tenor_years"],
            "obs_date": r["as_of_date"],
            "obs_ts": r["snapshot_ts"],
            "quote_type": "YIELD",
            "value": r["mid_yield"],
            "chg_1d": r["chg_1d"], "chg_1w": r["chg_1w"],
            "chg_1m": r["chg_1m"], "chg_3m": r["chg_3m"],
            "pricing_source": _normalize_pricing_source(r["source"]),
            "units": "PCT",
        })
    return out


def extract_asw_rows(conn: sqlite3.Connection, countries: list[str]) -> list[dict[str, Any]]:
    """``asw_snapshots`` -> raw dicts. No as_of_date column: obs_date derives from snapshot_ts."""
    placeholders = ",".join("?" * len(countries))
    q = f"""SELECT country_code, currency, isin, bbg_ticker, description, maturity_date,
                   tenor_years, asw_spread_bps, source, snapshot_ts
            FROM asw_snapshots WHERE country_code IN ({placeholders})"""
    out: list[dict[str, Any]] = []
    for r in conn.execute(q, countries):
        if r["asw_spread_bps"] is None or not r["isin"] or r["tenor_years"] is None:
            continue
        out.append({
            "isin": r["isin"],
            "govy_country_code": r["country_code"],
            "country_code": GOVY_TO_IMDR.get(r["country_code"], r["country_code"]),
            "ccy": r["currency"],
            "bbg_ticker": _none_if_blank(r["bbg_ticker"]),
            "description": _none_if_blank(r["description"]),
            "maturity_date": _none_if_blank(r["maturity_date"]),
            "tenor_years": r["tenor_years"],
            "obs_date": r["snapshot_ts"][:10],
            "obs_ts": r["snapshot_ts"],
            "quote_type": "ASW",
            "value": r["asw_spread_bps"],
            "chg_1d": None, "chg_1w": None, "chg_1m": None, "chg_3m": None,
            "pricing_source": _normalize_pricing_source(r["source"]),
            "units": "BP",
        })
    return out


def extract_auction_rows(conn: sqlite3.Connection, countries: list[str]) -> list[dict[str, Any]]:
    """``auction_calendar`` -> raw dicts."""
    placeholders = ",".join("?" * len(countries))
    q = f"""SELECT country_code, auction_date, security_type, term, isin, cusip,
                   coupon, maturity_date, reopening, offered_amount, currency,
                   source, fetched_at
            FROM auction_calendar WHERE country_code IN ({placeholders})"""
    out: list[dict[str, Any]] = []
    for r in conn.execute(q, countries):
        out.append({
            "govy_country_code": r["country_code"],
            "country_code": GOVY_TO_IMDR.get(r["country_code"], r["country_code"]),
            "auction_date": r["auction_date"],
            "security_type": r["security_type"] or "",
            "term": r["term"] or "",
            "isin": r["isin"] or "",
            "cusip": _none_if_blank(r["cusip"]),
            "coupon": r["coupon"],
            "maturity_date": _none_if_blank(r["maturity_date"]),
            "reopening": bool(r["reopening"]) if r["reopening"] is not None else None,
            "offered_amount": r["offered_amount"],
            "ccy": r["currency"],
            "source": r["source"],
            "fetched_at": r["fetched_at"],
        })
    return out


# ── Transform (raw dicts -> Pydantic Create models) ──────────────────────


def build_instrument_creates(
    obs_rows: list[dict[str, Any]],
    country_id_by_code: dict[str, int],
) -> list[BondInstrumentCreate]:
    """Distinct-isin seed rows for dbo.dim_bond_instrument.

    ``coupon`` is left NULL: neither yield_snapshots nor asw_snapshots
    carries a coupon column, and auction_calendar's isin is blank for most
    IGB/KTB rows so there's nothing reliable to join on. ``bond_curve_id``
    is left NULL — Track A/B curve linking is a later step (see
    docs/admin/development/govt_bond_population.md).
    """
    seen: dict[str, BondInstrumentCreate] = {}
    for row in obs_rows:
        isin = row["isin"]
        if isin in seen:
            continue
        country_id = country_id_by_code.get(row["country_code"])
        if country_id is None:
            _log.warning(
                "govy_bonds_unresolved_country",
                isin=isin, country_code=row["country_code"],
            )
            continue
        seen[isin] = BondInstrumentCreate(
            isin=isin,
            bbg_ticker=row.get("bbg_ticker"),
            country_id=country_id,
            ccy=row["ccy"],
            issuer_code=row["govy_country_code"],
            description=row.get("description"),
            coupon=None,
            maturity_date=row.get("maturity_date"),
        )
    return list(seen.values())


def build_obs_creates(
    rows: list[dict[str, Any]],
    instrument_id_by_isin: dict[str, int],
    vendor_id: int,
    frequency_id: int,
) -> tuple[list[BondInstrumentObsCreate], int]:
    """Dedupe + validate raw yield/ASW dicts into BondInstrumentObsCreate rows.

    Returns ``(validated, skipped_unresolved)`` — rows whose isin has no
    resolved ``instrument_id`` (not yet seeded) are counted, not raised.
    """
    deduped = _dedupe_latest(rows)
    out: list[BondInstrumentObsCreate] = []
    skipped = 0
    for row in deduped:
        instrument_id = instrument_id_by_isin.get(row["isin"])
        if instrument_id is None:
            skipped += 1
            continue
        out.append(BondInstrumentObsCreate(
            instrument_id=instrument_id,
            vendor_id=vendor_id,
            frequency_id=frequency_id,
            obs_date=row["obs_date"],
            obs_ts=_to_utc(row["obs_ts"]),
            quote_type=row["quote_type"],
            tenor_years=row["tenor_years"],
            value=row["value"],
            chg_1d=row["chg_1d"], chg_1w=row["chg_1w"],
            chg_1m=row["chg_1m"], chg_3m=row["chg_3m"],
            pricing_source=row["pricing_source"],
            units=row["units"],
        ))
    return out, skipped


def build_auction_creates(
    rows: list[dict[str, Any]],
    country_id_by_code: dict[str, int],
    currency_id_by_code: dict[str, int],
) -> tuple[list[BondAuctionCreate], int]:
    """Validate raw auction dicts into BondAuctionCreate rows.

    Returns ``(validated, skipped_unresolved_country)``.
    """
    out: list[BondAuctionCreate] = []
    skipped = 0
    for row in _dedupe_auctions_latest(rows):
        country_id = country_id_by_code.get(row["country_code"])
        if country_id is None:
            skipped += 1
            continue
        out.append(BondAuctionCreate(
            country_id=country_id,
            auction_date=row["auction_date"],
            security_type=row["security_type"],
            term=row["term"],
            isin=row["isin"],
            cusip=row["cusip"],
            coupon=row["coupon"],
            maturity_date=row["maturity_date"],
            reopening=row["reopening"],
            offered_amount=row["offered_amount"],
            currency_id=currency_id_by_code.get(row["ccy"]),
            source=_truncate_source(row["source"]),
            fetched_at=_to_utc(row["fetched_at"]),
        ))
    return out, skipped


class GovyBondsPipeline:
    """Track B ingest: Govy Monitor SQLite (read-only copy) -> IMDR ISIN-grain bond tables.

    ``run(no_load=True)`` extracts + validates the full shape (including a
    placeholder instrument_id so obs rows validate) and reports counts —
    it never calls a repository upsert method, so it never writes.
    ``run(no_load=False)`` additionally seeds ``dim_bond_instrument`` and
    upserts both fact tables.
    """

    def __init__(
        self,
        connector: MSSQLConnector,
        countries: list[str] | None = None,
        db_path: Path | None = None,
    ) -> None:
        self._connector = connector
        self._countries = countries or list(DEFAULT_COUNTRIES)
        self._db_path = db_path

    def extract(self) -> dict[str, list[dict[str, Any]]]:
        """Copy (or reuse) the Govy SQLite file, read the 3 source tables."""
        tmp_dir: Path | None = None
        if self._db_path is not None:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
        else:
            if not LIVE_DB.exists():
                raise FileNotFoundError(f"Govy live DB not found: {LIVE_DB}")
            conn, dst = open_readonly_copy(LIVE_DB)
            tmp_dir = dst.parent
        try:
            return {
                "yield": extract_yield_rows(conn, self._countries),
                "asw": extract_asw_rows(conn, self._countries),
                "auction": extract_auction_rows(conn, self._countries),
            }
        finally:
            conn.close()
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _resolve_dims(self, session: Session) -> dict[str, Any]:
        vendor = session.execute(
            select(DimVendor).where(DimVendor.vendor_code == VENDOR_CODE)
        ).scalar_one_or_none()
        if vendor is None:
            raise RuntimeError(f"Vendor '{VENDOR_CODE}' missing from dbo.dim_vendor")
        frequency = session.execute(
            select(DimFrequency).where(DimFrequency.frequency_code == FREQUENCY_CODE)
        ).scalar_one_or_none()
        if frequency is None:
            raise RuntimeError(f"Frequency '{FREQUENCY_CODE}' missing from dbo.dim_frequency")
        country_id_by_code = {
            c.country_code: c.id for c in session.scalars(select(DimCountry)).all()
        }
        currency_id_by_code = {
            c.code: c.id for c in session.scalars(select(DimCurrency)).all()
        }
        return {
            "vendor_id": vendor.id,
            "frequency_id": frequency.id,
            "country_id_by_code": country_id_by_code,
            "currency_id_by_code": currency_id_by_code,
        }

    def transform(
        self,
        raw: dict[str, list[dict[str, Any]]],
        dims: dict[str, Any],
        instrument_id_by_isin: dict[str, int],
    ) -> dict[str, Any]:
        instrument_creates = build_instrument_creates(
            raw["yield"] + raw["asw"], dims["country_id_by_code"]
        )
        yield_obs, y_skipped = build_obs_creates(
            raw["yield"], instrument_id_by_isin, dims["vendor_id"], dims["frequency_id"]
        )
        asw_obs, a_skipped = build_obs_creates(
            raw["asw"], instrument_id_by_isin, dims["vendor_id"], dims["frequency_id"]
        )
        auctions, auc_skipped = build_auction_creates(
            raw["auction"], dims["country_id_by_code"], dims["currency_id_by_code"]
        )
        return {
            "instruments": instrument_creates,
            "obs": yield_obs + asw_obs,
            "auctions": auctions,
            "skipped_unresolved_obs": y_skipped + a_skipped,
            "skipped_unresolved_auctions": auc_skipped,
        }

    def run(self, no_load: bool = False) -> dict[str, Any]:
        raw = self.extract()
        report: dict[str, Any] = {
            "countries": self._countries,
            "yield_rows_extracted": len(raw["yield"]),
            "asw_rows_extracted": len(raw["asw"]),
            "auction_rows_extracted": len(raw["auction"]),
        }

        with self._connector.session() as session:
            dims = self._resolve_dims(session)

            if no_load:
                instrument_creates = build_instrument_creates(
                    raw["yield"] + raw["asw"], dims["country_id_by_code"]
                )
                placeholder_ids = {
                    c.isin: _DRY_RUN_PLACEHOLDER_INSTRUMENT_ID for c in instrument_creates
                }
                transformed = self.transform(raw, dims, placeholder_ids)
                report.update({
                    "instruments_would_seed": len(transformed["instruments"]),
                    "obs_would_upsert": len(transformed["obs"]),
                    "auctions_would_upsert": len(transformed["auctions"]),
                    "skipped_unresolved_obs": transformed["skipped_unresolved_obs"],
                    "skipped_unresolved_auctions": transformed["skipped_unresolved_auctions"],
                    "sample_instrument": (
                        transformed["instruments"][0].model_dump()
                        if transformed["instruments"] else None
                    ),
                    "sample_obs": (
                        transformed["obs"][0].model_dump() if transformed["obs"] else None
                    ),
                    "sample_auction": (
                        transformed["auctions"][0].model_dump() if transformed["auctions"] else None
                    ),
                })
                _log.info("govy_bonds_dry_run_complete", **{
                    k: v for k, v in report.items()
                    if not k.startswith("sample_")
                })
                return report

            instrument_repo = BondInstrumentRepository(session)
            instrument_creates = build_instrument_creates(
                raw["yield"] + raw["asw"], dims["country_id_by_code"]
            )
            instrument_id_by_isin = instrument_repo.seed_and_resolve(instrument_creates)

            transformed = self.transform(raw, dims, instrument_id_by_isin)
            obs_count = BondInstrumentObsRepository(session).bulk_upsert(transformed["obs"])
            auction_count = BondAuctionRepository(session).bulk_upsert(transformed["auctions"])

        report.update({
            "instruments_seeded": len(instrument_id_by_isin),
            "obs_upserted": obs_count,
            "auctions_upserted": auction_count,
            "skipped_unresolved_obs": transformed["skipped_unresolved_obs"],
            "skipped_unresolved_auctions": transformed["skipped_unresolved_auctions"],
        })
        _log.info("govy_bonds_load_complete", **report)
        return report
