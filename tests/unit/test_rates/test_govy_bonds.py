"""Unit tests for the Track B Govy Monitor bond ingest.

Uses an in-memory / temp-file SQLite fixture mimicking the 3 source tables
(yield_snapshots, asw_snapshots, auction_calendar) — never touches the live
Govy Monitor DB. No test in this module writes to IMDR.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from imdr.domains.rates.govy_bonds import (
    _dedupe_auctions_latest,
    _dedupe_latest,
    _normalize_pricing_source,
    _truncate_source,
    build_auction_creates,
    build_instrument_creates,
    build_obs_creates,
    extract_asw_rows,
    extract_auction_rows,
    extract_yield_rows,
    open_readonly_copy,
)
from imdr.domains.rates.repository_bond import _DIM_BOND_INSTRUMENT_SPEC
from imdr.schemas.rates_bond import BondAuctionCreate, BondInstrumentCreate, BondInstrumentObsCreate

_COUNTRY_ID_BY_CODE = {"IN": 24, "KR": 27}
_CURRENCY_ID_BY_CODE = {"INR": 17, "KRW": 16}


def _make_source_db() -> sqlite3.Connection:
    """In-memory SQLite with the 3 Govy source tables + representative rows."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE yield_snapshots (
            id INTEGER PRIMARY KEY, snapshot_ts TEXT, as_of_date TEXT,
            country_code TEXT, currency TEXT, isin TEXT, bbg_ticker TEXT,
            description TEXT, maturity_date TEXT, tenor_years REAL,
            mid_yield REAL, chg_1d REAL, chg_1w REAL, chg_1m REAL, chg_3m REAL,
            source TEXT
        );
        CREATE TABLE asw_snapshots (
            id INTEGER PRIMARY KEY, snapshot_ts TEXT, country_code TEXT,
            currency TEXT, isin TEXT, bbg_ticker TEXT, description TEXT,
            maturity_date TEXT, tenor_years REAL, asw_spread_bps REAL, source TEXT
        );
        CREATE TABLE auction_calendar (
            id INTEGER PRIMARY KEY, country_code TEXT, auction_date TEXT,
            security_type TEXT, term TEXT, isin TEXT, cusip TEXT, coupon REAL,
            maturity_date TEXT, reopening INTEGER, offered_amount REAL,
            currency TEXT, source TEXT, fetched_at TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO yield_snapshots (snapshot_ts, as_of_date, country_code, currency, "
        "isin, bbg_ticker, description, maturity_date, tenor_years, mid_yield, "
        "chg_1d, chg_1w, chg_1m, chg_3m, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            # IGB bond, blpapi-bql source -> pricing_source should map to BQL
            ("2026-07-17T09:00:00", "2026-07-17", "IGB", "INR", "IN0020230010",
             "ZK072458 Corp", "IGB 7.06 04/10/28", "2028-04-10", 1.8, 6.04,
             0.01, 0.02, 0.03, 0.04, "blpapi-bql"),
            # Same isin+day, earlier snapshot_ts -> should be dropped by dedupe
            ("2026-07-17T07:00:00", "2026-07-17", "IGB", "INR", "IN0020230010",
             "ZK072458 Corp", "IGB 7.06 04/10/28", "2028-04-10", 1.8, 6.10,
             0.05, 0.06, 0.07, 0.08, "Excel BQL"),
            # KTB bond, chg_1d == 0.0 (the confirmed-live gotcha)
            ("2026-07-17T09:00:00", "2026-07-17", "KTB", "KRW", "KR103503GE96",
             None, "KTB 20y", "2045-09-10", 19.1, 3.10,
             0.0, 0.0, 0.0, 0.0, "blpapi-bql"),
            # NULL mid_yield -> must be skipped
            ("2026-07-17T09:00:00", "2026-07-17", "IGB", "INR", "IN0020250091",
             "YK553060 Corp", "IGB 6.48 10/06/35", "2035-10-06", 9.3, None,
             None, None, None, None, "blpapi-bql"),
            # NULL isin -> must be skipped
            ("2026-07-17T09:00:00", "2026-07-17", "IGB", "INR", None,
             None, "unmapped", None, 5.0, 6.5,
             None, None, None, None, "blpapi-bql"),
            # NULL tenor_years (valid isin + mid_yield) -> must be skipped:
            # tenor_years is non-optional on the Create model.
            ("2026-07-17T09:00:00", "2026-07-17", "IGB", "INR", "IN0020990099",
             "AA000000 Corp", "IGB tenor-less", "2040-01-01", None, 6.7,
             None, None, None, None, "blpapi-bql"),
        ],
    )
    conn.executemany(
        "INSERT INTO asw_snapshots (snapshot_ts, country_code, currency, isin, "
        "bbg_ticker, description, maturity_date, tenor_years, asw_spread_bps, source) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            # Two intraday snapshots, same isin/day -> later snapshot_ts should win
            ("2026-06-21T08:00:00", "IGB", "INR", "IN0020250091", "YK553060 Corp",
             "IGB 6.48 10/06/35", "2035-10-06", 9.29, 10.0, "local_asw"),
            ("2026-06-21T11:26:04", "IGB", "INR", "IN0020250091", "YK553060 Corp",
             "IGB 6.48 10/06/35", "2035-10-06", 9.29, 16.26, "local_asw"),
        ],
    )
    conn.executemany(
        "INSERT INTO auction_calendar (country_code, auction_date, security_type, term, "
        "isin, cusip, coupon, maturity_date, reopening, offered_amount, currency, "
        "source, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("IGB", "2026-09-25", "G-Sec", "10y", "", "", None, "", 1, 340.0, "INR",
             "RBI Issuance Calendar H1 FY2026-27 (PIB)", "2026-07-17T16:50:43"),
            ("KTB", "2026-06-23", "KTB", "20y", "", "", 2.75, "2045-09-10", 1, None, "KRW",
             "Barclays Auction Calendar 19-Jun-2026", "2026-07-17T16:50:41"),
        ],
    )
    conn.commit()
    return conn


# ── extraction ────────────────────────────────────────────────────────────


class TestExtractYieldRows:
    def test_skips_null_mid_yield_and_null_isin(self) -> None:
        conn = _make_source_db()
        rows = extract_yield_rows(conn, ["IGB", "KTB"])
        isins = {r["isin"] for r in rows}
        assert "IN0020250091" not in isins  # NULL mid_yield
        assert None not in isins  # NULL isin row dropped entirely
        assert len(rows) == 3  # 2x IN0020230010 dup + 1x KTB

    def test_skips_null_tenor_years(self) -> None:
        conn = _make_source_db()
        rows = extract_yield_rows(conn, ["IGB", "KTB"])
        isins = {r["isin"] for r in rows}
        assert "IN0020990099" not in isins  # NULL tenor_years dropped

    def test_pricing_source_mapped(self) -> None:
        conn = _make_source_db()
        rows = extract_yield_rows(conn, ["IGB", "KTB"])
        sources = {r["pricing_source"] for r in rows}
        assert "blpapi-bql" not in sources
        assert "BQL" in sources

    def test_ktb_chg_1d_stored_as_is_not_computed(self) -> None:
        """The confirmed-live gotcha: KTB chg_1d is 0.0 in the source; we store
        it verbatim rather than recomputing, per the module's documented contract."""
        conn = _make_source_db()
        rows = extract_yield_rows(conn, ["KTB"])
        assert len(rows) == 1
        assert rows[0]["chg_1d"] == 0.0


class TestExtractAswRows:
    def test_maps_asw_spread_as_value_bp(self) -> None:
        conn = _make_source_db()
        rows = extract_asw_rows(conn, ["IGB"])
        assert len(rows) == 2
        assert all(r["quote_type"] == "ASW" and r["units"] == "BP" for r in rows)
        assert all(r["chg_1d"] is None for r in rows)  # no chg columns in asw_snapshots


class TestExtractAuctionRows:
    def test_maps_blank_isin_to_empty_string_sentinel(self) -> None:
        conn = _make_source_db()
        rows = extract_auction_rows(conn, ["IGB", "KTB"])
        assert all(r["isin"] == "" for r in rows)


# ── dedupe ──────────────────────────────────────────────────────────────


class TestDedupeLatest:
    def test_asw_dedup_keeps_latest_snapshot_ts(self) -> None:
        conn = _make_source_db()
        rows = extract_asw_rows(conn, ["IGB"])
        deduped = _dedupe_latest(rows)
        assert len(deduped) == 1
        assert deduped[0]["value"] == pytest.approx(16.26)
        assert deduped[0]["obs_ts"] == "2026-06-21T11:26:04"

    def test_yield_dedup_keeps_latest_snapshot_ts(self) -> None:
        conn = _make_source_db()
        rows = extract_yield_rows(conn, ["IGB"])
        deduped = _dedupe_latest(rows)
        # IN0020230010 had 2 same-day rows -> collapses to 1; KTB unaffected here
        matching = [r for r in deduped if r["isin"] == "IN0020230010"]
        assert len(matching) == 1
        assert matching[0]["value"] == pytest.approx(6.04)  # the later snapshot_ts row

    def test_dedup_collapses_across_differing_pricing_source(self) -> None:
        """One authoritative row per (isin, obs_date, quote_type) regardless of source.

        The dedup grain deliberately excludes pricing_source: a bond/day priced
        under two *different* source labels (e.g. a live BQL pull and a historical
        Excel import) must collapse to the single latest-snapshot observation, not
        survive as two rows. Locks in the "one per day" decision (2026-07-20).
        """
        rows = [
            {"isin": "IN0000000001", "obs_date": "2026-07-17", "quote_type": "YIELD",
             "pricing_source": "EXCEL_IMPORT", "obs_ts": "2026-07-17T07:00:00", "value": 6.10},
            {"isin": "IN0000000001", "obs_date": "2026-07-17", "quote_type": "YIELD",
             "pricing_source": "BQL", "obs_ts": "2026-07-17T09:00:00", "value": 6.04},
        ]
        deduped = _dedupe_latest(rows)
        assert len(deduped) == 1
        assert deduped[0]["value"] == pytest.approx(6.04)          # latest snapshot_ts wins
        assert deduped[0]["pricing_source"] == "BQL"               # winner keeps its own source

    def test_auction_dedup_keeps_latest_fetched_at(self) -> None:
        """Duplicate auction natural keys collapse to the latest fetched_at.

        Guards the MERGE: two source rows with an identical
        (country, auction_date, security_type, term, isin) would otherwise be
        handed to SQL Server in one MERGE and error the whole run.
        """
        rows = [
            {"country_code": "IN", "auction_date": "2026-09-25", "security_type": "G-Sec",
             "term": "10y", "isin": "", "fetched_at": "2026-07-16T16:50:43", "offered_amount": 300.0},
            {"country_code": "IN", "auction_date": "2026-09-25", "security_type": "G-Sec",
             "term": "10y", "isin": "", "fetched_at": "2026-07-17T16:50:43", "offered_amount": 340.0},
        ]
        deduped = _dedupe_auctions_latest(rows)
        assert len(deduped) == 1
        assert deduped[0]["offered_amount"] == pytest.approx(340.0)  # latest fetched_at wins


# ── transform / build_* ──────────────────────────────────────────────────


class TestBuildInstrumentCreates:
    def test_one_row_per_distinct_isin(self) -> None:
        conn = _make_source_db()
        yield_rows = extract_yield_rows(conn, ["IGB", "KTB"])
        asw_rows = extract_asw_rows(conn, ["IGB"])
        creates = build_instrument_creates(yield_rows + asw_rows, _COUNTRY_ID_BY_CODE)

        isins = [c.isin for c in creates]
        assert len(isins) == len(set(isins))  # no duplicates
        # IN0020250091 appears in both yield-dup-skip and asw rows -> still 1
        assert isins.count("IN0020250091") == 1
        assert all(isinstance(c, BondInstrumentCreate) for c in creates)

    def test_country_id_resolved(self) -> None:
        conn = _make_source_db()
        rows = extract_yield_rows(conn, ["KTB"])
        creates = build_instrument_creates(rows, _COUNTRY_ID_BY_CODE)
        assert creates[0].country_id == 27

    def test_coupon_left_null(self) -> None:
        conn = _make_source_db()
        rows = extract_yield_rows(conn, ["IGB"])
        creates = build_instrument_creates(rows, _COUNTRY_ID_BY_CODE)
        assert all(c.coupon is None for c in creates)

    def test_bond_curve_id_is_insert_only_not_updated(self) -> None:
        """bond_curve_id must stay out of the MERGE UPDATE set.

        The ingest always supplies it NULL; if it were a value_column a
        re-run would clobber any externally-set curve link back to NULL.
        Locked in so the insert-only guarantee survives future edits.
        """
        assert "bond_curve_id" in _DIM_BOND_INSTRUMENT_SPEC.columns
        assert "bond_curve_id" not in _DIM_BOND_INSTRUMENT_SPEC.value_columns


class TestBuildObsCreates:
    def test_unresolved_instrument_is_skipped_and_counted(self) -> None:
        conn = _make_source_db()
        rows = extract_yield_rows(conn, ["IGB", "KTB"])
        creates, skipped = build_obs_creates(rows, {}, vendor_id=4, frequency_id=5)
        assert creates == []
        assert skipped == len(_dedupe_latest(rows))

    def test_resolved_rows_validate_as_bond_instrument_obs_create(self) -> None:
        conn = _make_source_db()
        rows = extract_yield_rows(conn, ["KTB"])
        instrument_map = {"KR103503GE96": 999}
        creates, skipped = build_obs_creates(rows, instrument_map, vendor_id=4, frequency_id=5)
        assert skipped == 0
        assert len(creates) == 1
        obs = creates[0]
        assert isinstance(obs, BondInstrumentObsCreate)
        assert obs.instrument_id == 999
        assert obs.quote_type == "YIELD"
        assert obs.units == "PCT"
        assert obs.pricing_source == "BQL"


class TestBuildAuctionCreates:
    def test_long_source_truncated_to_30_chars(self) -> None:
        conn = _make_source_db()
        rows = extract_auction_rows(conn, ["IGB"])
        creates, skipped = build_auction_creates(rows, _COUNTRY_ID_BY_CODE, _CURRENCY_ID_BY_CODE)
        assert skipped == 0
        assert len(creates[0].source) <= 30
        assert isinstance(creates[0], BondAuctionCreate)

    def test_currency_id_resolved(self) -> None:
        conn = _make_source_db()
        rows = extract_auction_rows(conn, ["KTB"])
        creates, _ = build_auction_creates(rows, _COUNTRY_ID_BY_CODE, _CURRENCY_ID_BY_CODE)
        assert creates[0].currency_id == 16


class TestNormalizePricingSource:
    def test_known_labels_mapped(self) -> None:
        assert _normalize_pricing_source("blpapi-bql") == "BQL"
        assert _normalize_pricing_source("Excel BQL history") == "BQL_HIST"

    def test_unmapped_long_label_truncated_to_12(self) -> None:
        out = _normalize_pricing_source("some totally novel 40-char vendor label")
        assert len(out) <= 12

    def test_none_or_empty_becomes_unknown(self) -> None:
        assert _normalize_pricing_source(None) == "UNKNOWN"
        assert _normalize_pricing_source("") == "UNKNOWN"


class TestTruncateSource:
    def test_truncates_to_30(self) -> None:
        long = "RBI Issuance Calendar H1 FY2026-27 (PIB)"
        assert len(long) > 30
        assert len(_truncate_source(long)) == 30

    def test_none_passthrough(self) -> None:
        assert _truncate_source(None) is None


# ── no-write lock-in ──────────────────────────────────────────────────────


class TestOpenReadonlyCopyNeverWritesSource:
    def test_copy_never_opens_source_for_write(self, tmp_path: Path) -> None:
        """Mark the fake 'live' file read-only on disk; open_readonly_copy must
        still succeed (it only ever shutil.copy2's the source, then opens the
        *copy*). If the code ever tried to open the source itself in write
        mode, this would raise PermissionError."""
        src = tmp_path / "fake_govy.db"
        conn = sqlite3.connect(str(src))
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        conn.close()

        before_hash = hashlib.sha256(src.read_bytes()).hexdigest()
        os.chmod(src, stat.S_IREAD)
        try:
            copy_conn, copy_path = open_readonly_copy(src)
            try:
                rows = copy_conn.execute("SELECT x FROM t").fetchall()
                assert [r["x"] for r in rows] == [1]
            finally:
                copy_conn.close()
                copy_path.parent.chmod(stat.S_IWRITE | stat.S_IREAD)
                for f in copy_path.parent.iterdir():
                    f.chmod(stat.S_IWRITE | stat.S_IREAD)
                import shutil
                shutil.rmtree(copy_path.parent, ignore_errors=True)

            after_hash = hashlib.sha256(src.read_bytes()).hexdigest()
            assert before_hash == after_hash
        finally:
            os.chmod(src, stat.S_IWRITE | stat.S_IREAD)
