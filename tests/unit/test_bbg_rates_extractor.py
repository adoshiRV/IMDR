"""Tests for BloombergCSVRatesExtractor — covers all format quirks.

Quirks validated (cross-reference plan in ``docs/rates/rates_bbg.md``):
 1. Row-1 first cell varies (Date, Dates, Tenor, Term, Ticker, Tickers, rv Iden)
 2. Tenor regex matches all observed prefixes (AUQ, EUQ, DT6, INR, ILS,
    EUS, SOFR, JPY, JPY_PAR_OIS mixed)
 3. ON tenor accepted
 4. Duplicate tenor columns deduped (USD-LIBOR-3M two 6M cols)
 5. Folder ccy wins over tenor-label ccy (PLN file with EUR labels → PLN)
 6. Negative rates pass through (CHF-SARON spot)
 7. Date format dd/mm/yyyy parsed
 8. 12M canonicalises to 1Y
 9. -ori.csv filename accepted (USD-LIBOR-3M)
10. Empty PAR folder handled (AUD-BBSW.IAUS-3M)
11. Maturity row (row 2) ignored
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from imdr.domains.rates.extractors_bbg import (
    BBGRatesSourceFile,
    BloombergCSVRatesExtractor,
    discover_bbg_rates_files,
    extract_tenor,
    parse_bbg_rates_csv,
    parse_bbg_rates_folder,
)


SNAP_TS = datetime(2026, 4, 25, 11, 20, 0, tzinfo=timezone.utc)


# ── Tenor extraction (Quirks #2, #3, #8) ──────────────────────────────


class TestExtractTenor:
    def test_basic_3m(self) -> None:
        assert extract_tenor("IRS_PAR_AUQ_SPOT_3M") == "3M"

    def test_basic_30y(self) -> None:
        assert extract_tenor("IRS_PAR_AUQ_SPOT_30Y") == "30Y"

    def test_dt6_prefix(self) -> None:
        """JPY-DTIBOR uses 'DT6' as ccy-prefix."""
        assert extract_tenor("IRS_PAR_DT6_SPOT_6M") == "6M"

    def test_inr_prefix(self) -> None:
        assert extract_tenor("OIS_PAR_INR_SPOT_3M") == "3M"

    def test_eus_prefix(self) -> None:
        """EUR-ESTR uses 'EUS' as ccy-prefix."""
        assert extract_tenor("OIS_PAR_EUS_SPOT_18M") == "18M"

    def test_jpy_par_ois_short_tenor(self) -> None:
        """JPY-TONAR-JSCC short tenors use JPY_PAR_OIS_* prefix."""
        assert extract_tenor("JPY_PAR_OIS_SPOT_1D") == "1D"

    def test_jpy_par_ois_long_tenor(self) -> None:
        """JPY-TONAR-JSCC long tenors use OIS_PAR_JPY_* prefix."""
        assert extract_tenor("OIS_PAR_JPY_SPOT_30Y") == "30Y"

    def test_overnight_on_tenor(self) -> None:
        assert extract_tenor("OIS_PAR_CHF_SPOT_ON") == "ON"

    def test_overnight_1d(self) -> None:
        assert extract_tenor("OIS_PAR_USD_SPOT_1D") == "1D"

    def test_12m_normalizes_to_1y(self) -> None:
        """12M never appears in IMDR — always 1Y."""
        assert extract_tenor("IRS_PAR_AUQ_SPOT_12M") == "1Y"

    def test_unmatched_returns_none(self) -> None:
        assert extract_tenor("ADSWAP1Q BGN Curncy") is None

    def test_non_string_returns_none(self) -> None:
        assert extract_tenor(None) is None
        assert extract_tenor(42) is None

    def test_lowercase_tenor_normalized(self) -> None:
        assert extract_tenor("X_3y") == "3Y"

    def test_long_tenor_50y(self) -> None:
        assert extract_tenor("OIS_PAR_SOFR_SPOT_50Y") == "50Y"


# ── Folder name parser ────────────────────────────────────────────────


class TestParseBBGRatesFolder:
    def test_aud_bbsw_3m(self) -> None:
        ccy, curve, ct = parse_bbg_rates_folder("IRS", "AUD-BBSW-3M")
        assert (ccy, curve, ct) == ("AUD", "BBSW_3M", "ibor")

    def test_aud_bbsw_6m(self) -> None:
        ccy, curve, ct = parse_bbg_rates_folder("IRS", "AUD-BBSW-6M")
        assert (ccy, curve, ct) == ("AUD", "BBSW_6M", "ibor")

    def test_usd_sofr_on(self) -> None:
        ccy, curve, ct = parse_bbg_rates_folder("OIS", "USD-SOFR-ON")
        assert (ccy, curve, ct) == ("USD", "SOFR", "rfr")

    def test_jpy_tonar_on_jscc(self) -> None:
        """Clearing-house suffix preserved in curve name."""
        ccy, curve, ct = parse_bbg_rates_folder("OIS", "JPY-TONAR-ON-JSCC")
        assert (ccy, curve, ct) == ("JPY", "TONAR_JSCC", "rfr")

    def test_aud_aonia_md_on(self) -> None:
        """Dot in name (.MD) gets normalised to underscore."""
        ccy, curve, ct = parse_bbg_rates_folder("OIS", "AUD-AONIA.MD-ON")
        assert (ccy, curve, ct) == ("AUD", "AONIA_MD", "rfr")

    def test_aud_bbsw_iaus_3m(self) -> None:
        """IRS with dotted index name — preserve all info."""
        ccy, curve, ct = parse_bbg_rates_folder("IRS", "AUD-BBSW.IAUS-3M")
        assert (ccy, curve, ct) == ("AUD", "BBSW_IAUS_3M", "ibor")

    def test_kro_91d_cd_3m(self) -> None:
        """KRO onshore + 91D_CD index with embedded underscore."""
        ccy, curve, ct = parse_bbg_rates_folder("IRS", "KRO-91D_CD-3M")
        assert (ccy, curve, ct) == ("KRO", "91D_CD_3M", "ibor")

    def test_cno_repo_7d(self) -> None:
        """CNO onshore + REPO_7D."""
        ccy, curve, ct = parse_bbg_rates_folder("IRS", "CNO-REPO-7D")
        assert (ccy, curve, ct) == ("CNO", "REPO_7D", "ibor")

    def test_invalid_folder(self) -> None:
        with pytest.raises(ValueError):
            parse_bbg_rates_folder("IRS", "NODASH")

    # ── BASIS folder parsing ──────────────────────────────────────
    def test_basis_sgd_sor_vs_sofr(self) -> None:
        ccy, curve, ct = parse_bbg_rates_folder(
            "BASIS", "SGD-SOR-ON.USD-SOFR-ON"
        )
        assert (ccy, curve, ct) == ("SGD", "BASIS_SOR_VS_SOFR", "basis")

    def test_basis_ils_shir_vs_sofr(self) -> None:
        ccy, curve, ct = parse_bbg_rates_folder(
            "BASIS", "ILS-SHIR-ON.USD-SOFR-ON"
        )
        assert (ccy, curve, ct) == ("ILS", "BASIS_SHIR_VS_SOFR", "basis")

    def test_basis_missing_dot_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_bbg_rates_folder("BASIS", "SGD-SOR-ON-USD-SOFR-ON")

    # ── CCS folder parsing ────────────────────────────────────────
    def test_ccs_cnh_vs_sofr(self) -> None:
        ccy, curve, ct = parse_bbg_rates_folder(
            "CCS", "CNH-FIXED.USD-SOFR-ON"
        )
        assert (ccy, curve, ct) == ("CNH", "CCS_VS_SOFR", "ccs")

    def test_ccs_missing_dot_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_bbg_rates_folder("CCS", "CNH-FIXED-USD-SOFR-ON")


# ── CSV parsing (Quirks #1, #6, #7, #11) ──────────────────────────────


def _write_csv_3hdr(
    path: Path,
    ticker_row: list[str],
    tenor_row: list[str],
    maturity_row: list[str],
    data_rows: list[list[str]],
) -> None:
    """Write a 3-header BBG-style CSV."""
    rows = [ticker_row, tenor_row, maturity_row, *data_rows]
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, header=False)


class TestParseBBGRatesCSV:
    def test_aud_bbsw_3m_canonical(self, tmp_path: Path) -> None:
        """Canonical AUD-BBSW-3M file shape."""
        f = tmp_path / "IRS_PAR_AUD-BBSW-3M.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "BBSW 3M INDEX", "ADSWFQ BGN Curncy", "ADSWAP10Q BGN Curncy"],
            ["Tenor", "IRS_PAR_AUQ_SPOT_3M", "IRS_PAR_AUQ_SPOT_6M", "IRS_PAR_AUQ_SPOT_10Y"],
            ["Maturity", "0.25", "0.5", "10"],
            [["24/04/2026", "4.35", "4.4914", "5.05125"]],
        )
        df = parse_bbg_rates_csv(f)
        assert len(df) == 3
        assert (df["obs_date"] == date(2026, 4, 24)).all()
        assert set(df["tenor_alias"]) == {
            "IRS_PAR_AUQ_SPOT_3M",
            "IRS_PAR_AUQ_SPOT_6M",
            "IRS_PAR_AUQ_SPOT_10Y",
        }

    def test_row1_first_cell_term(self, tmp_path: Path) -> None:
        """Quirk #1: USD-SOFR uses 'Term' not 'Tenor'."""
        f = tmp_path / "OIS_PAR_USD-SOFR-ON.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "SOFRRATE Index", "USOSFR1Z BGN Curncy"],
            ["Term", "OIS_PAR_SOFR_SPOT_1D", "OIS_PAR_SOFR_SPOT_1W"],
            ["Maturity", "0.0028", "0.005"],
            [["24/04/2026", "3.64", "3.6675"]],
        )
        df = parse_bbg_rates_csv(f)
        assert len(df) == 2

    def test_row1_first_cell_date(self, tmp_path: Path) -> None:
        """Quirk #1: CAD-CORRA uses 'Date'."""
        f = tmp_path / "OIS_PAR_CAD-CORRA-ON.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "CORRA Index", "CDOR1W BGN"],
            ["Date", "OIS_PAR_CAD_SPOT_ON", "OIS_PAR_CAD_SPOT_1W"],
            ["Maturity", "0.0028", "0.019"],
            [["24/04/2026", "2.30", "2.34"]],
        )
        df = parse_bbg_rates_csv(f)
        assert len(df) == 2

    def test_negative_rates_pass_through(self, tmp_path: Path) -> None:
        """Quirk #6: CHF-SARON has negative spot."""
        f = tmp_path / "OIS_PAR_CHF-SARON-ON.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "SARON Index"],
            ["Date", "OIS_PAR_CHF_SPOT_ON"],
            ["Maturity", "0.0028"],
            [["24/04/2026", "-0.039025"]],
        )
        df = parse_bbg_rates_csv(f)
        assert len(df) == 1
        assert df["value"].iloc[0] == pytest.approx(-0.039025, abs=1e-6)

    def test_dd_mm_yyyy_dates(self, tmp_path: Path) -> None:
        """Quirk #7: dd/mm/yyyy date format."""
        f = tmp_path / "OIS_PAR_USD-SOFR-ON.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "SOFRRATE Index"],
            ["Term", "OIS_PAR_SOFR_SPOT_1D"],
            ["Maturity", "0.0028"],
            [
                ["24/04/2026", "3.64"],
                ["31/12/2025", "4.10"],  # dd/mm — 31/12 not 12/31
            ],
        )
        df = parse_bbg_rates_csv(f)
        assert set(df["obs_date"]) == {date(2026, 4, 24), date(2025, 12, 31)}

    def test_maturity_row_ignored(self, tmp_path: Path) -> None:
        """Quirk #11: Maturity row 2 is metadata, never appears as data."""
        f = tmp_path / "x.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "X Index"],
            ["Tenor", "OIS_PAR_USD_SPOT_1Y"],
            ["Maturity", "1"],
            [["24/04/2026", "3.7"]],
        )
        df = parse_bbg_rates_csv(f)
        # Only one data row — Maturity row is row 2, skipped
        assert len(df) == 1
        assert df["value"].iloc[0] == 3.7

    def test_nan_values_dropped(self, tmp_path: Path) -> None:
        f = tmp_path / "x.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "X Index", "Y Index"],
            ["Tenor", "OIS_PAR_USD_SPOT_1Y", "OIS_PAR_USD_SPOT_2Y"],
            ["Maturity", "1", "2"],
            [["24/04/2026", "3.7", ""]],
        )
        df = parse_bbg_rates_csv(f)
        assert len(df) == 1
        assert df["tenor_alias"].iloc[0] == "OIS_PAR_USD_SPOT_1Y"

    def test_invalid_dates_dropped(self, tmp_path: Path) -> None:
        f = tmp_path / "x.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "X Index"],
            ["Tenor", "OIS_PAR_USD_SPOT_1Y"],
            ["Maturity", "1"],
            [["not_a_date", "3.7"], ["24/04/2026", "3.8"]],
        )
        df = parse_bbg_rates_csv(f)
        assert len(df) == 1
        assert df["obs_date"].iloc[0] == date(2026, 4, 24)


# ── Extractor end-to-end ──────────────────────────────────────────────


def _build_source_file(
    path: Path, kind: str, folder: str, ccy: str, curve: str, curve_type: str
) -> BBGRatesSourceFile:
    return BBGRatesSourceFile(
        path=path,
        folder=folder,
        kind=kind,
        ccy=ccy,
        curve=curve,
        curve_type=curve_type,
        obs_ts=SNAP_TS,
    )


class TestBloombergCSVRatesExtractor:
    def test_live_mode_keeps_only_latest_date(self, tmp_path: Path) -> None:
        """Live mode: each file contributes only its newest data row."""
        f = tmp_path / "IRS_PAR_AUD-BBSW-3M.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "BBSW", "X"],
            ["Tenor", "IRS_PAR_AUQ_SPOT_3M", "IRS_PAR_AUQ_SPOT_10Y"],
            ["Maturity", "0.25", "10"],
            [
                ["24/04/2026", "4.35", "5.05"],   # latest
                ["23/04/2026", "4.36", "5.06"],
                ["22/04/2026", "4.37", "5.07"],
            ],
        )
        src = _build_source_file(f, "IRS", "AUD-BBSW-3M", "AUD", "BBSW_3M", "ibor")
        out = BloombergCSVRatesExtractor().extract([src])
        # 2 tenors × 1 latest date = 2 rows
        assert len(out) == 2
        assert (out["ts"] == SNAP_TS).all()
        assert (out["ccy"] == "AUD").all()
        assert (out["curve"] == "BBSW_3M").all()
        assert (out["quote"] == "par").all()
        assert set(out["tenor"]) == {"3M", "10Y"}

    def test_pln_eur_mislabel_uses_folder_ccy(self, tmp_path: Path) -> None:
        """Quirk #5: PLN-WIBOR-6M file has tenor labels saying EUR.
        Folder name is the source of truth — output ccy must be PLN.
        """
        f = tmp_path / "IRS_PAR_PLN-WIBOR-6M.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "WIB3M index", "PZSW1VF CMPN CURNCY"],
            ["Ticker", "IRS_PAR_EUR_SPOT_6M", "IRS_PAR_EUR_SPOT_1Y"],  # mislabeled!
            ["Maturity", "0.5", "1"],
            [["24/04/2026", "3.85", "4.167"]],
        )
        src = _build_source_file(f, "IRS", "PLN-WIBOR-6M", "PLN", "WIBOR_6M", "ibor")
        out = BloombergCSVRatesExtractor().extract([src])
        # All rows must have ccy='PLN' even though tenor labels say EUR
        assert (out["ccy"] == "PLN").all()
        assert set(out["tenor"]) == {"6M", "1Y"}

    def test_duplicate_tenor_columns_deduped(self, tmp_path: Path) -> None:
        """Quirk #4: USD-LIBOR-3M has two IRS_PAR_USD_SPOT_6M cols.
        Dedupe via keep='last'.
        """
        f = tmp_path / "IRS_PAR_USD-LIBOR-3M-ori.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "USS Index", "USSWF Curncy", "USSWI Curncy", "USSW1 Curncy"],
            ["Tenor", "IRS_PAR_USD_SPOT_6M", "IRS_PAR_USD_SPOT_6M",
             "IRS_PAR_USD_SPOT_9M", "IRS_PAR_USD_SPOT_1Y"],
            ["Maturity", "0.25", "0.5", "0.75", "1"],
            [["25/03/2024", "5.59412", "5.6899", "5.6351", "5.6698"]],
        )
        src = _build_source_file(f, "IRS", "USD-LIBOR-3M", "USD", "LIBOR_3M", "ibor")
        out = BloombergCSVRatesExtractor().extract([src])
        # 6M deduped to keep='last' → 5.6899 (the second col), then 9M, 1Y = 3 rows
        tenors = sorted(out["tenor"].tolist())
        assert tenors == ["1Y", "6M", "9M"]
        sixm = out[out["tenor"] == "6M"]["value"].iloc[0]
        assert sixm == pytest.approx(5.6899, abs=1e-4)

    def test_mixed_label_schemes_in_one_file(self, tmp_path: Path) -> None:
        """Quirk: JPY-TONAR-JSCC has both JPY_PAR_OIS_SPOT_* and OIS_PAR_JPY_SPOT_*."""
        f = tmp_path / "OIS_PAR_JPY-TONAR-ON-JSCC.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "MUTKCALM Index", "JYSO1Z BGN", "JYSO1 BGN", "JYSO10 BGN"],
            ["Term",
             "JPY_PAR_OIS_SPOT_1D",
             "JPY_PAR_OIS_SPOT_1W",
             "OIS_PAR_JPY_SPOT_1Y",
             "OIS_PAR_JPY_SPOT_10Y"],
            ["Maturity", "0.0028", "0.019", "1", "10"],
            [["24/04/2026", "0.727", "0.7375", "1.06", "2.226"]],
        )
        src = _build_source_file(f, "OIS", "JPY-TONAR-ON-JSCC", "JPY",
                                 "TONAR_JSCC", "rfr")
        out = BloombergCSVRatesExtractor().extract([src])
        tenors = sorted(out["tenor"].tolist())
        assert tenors == ["10Y", "1D", "1W", "1Y"]

    def test_unknown_tenor_dropped(self, tmp_path: Path) -> None:
        """Tenor label that doesn't match _TENOR_RE is dropped + warned."""
        f = tmp_path / "x.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "A", "B"],
            ["Tenor", "ADSWAP1Q BGN Curncy", "OIS_PAR_USD_SPOT_1Y"],  # first is BBG ticker
            ["Maturity", "0.25", "1"],
            [["24/04/2026", "4.35", "3.7"]],
        )
        src = _build_source_file(f, "IRS", "USD-X-3M", "USD", "X_3M", "ibor")
        out = BloombergCSVRatesExtractor().extract([src])
        # Only the recognised one remains
        assert len(out) == 1
        assert out["tenor"].iloc[0] == "1Y"

    def test_empty_input_returns_empty_df(self, tmp_path: Path) -> None:
        out = BloombergCSVRatesExtractor().extract([])
        assert out.empty
        assert list(out.columns) == ["ts", "ccy", "curve", "quote", "tenor", "value"]

    # ── BASIS extraction ──────────────────────────────────────────────
    def test_basis_stamps_quote_basis(self, tmp_path: Path) -> None:
        """BASIS curves must stamp `quote='basis'` (bps unit) — not 'par'.
        The cleaning hard-bounds rule keys on `quote`, so the wrong quote
        would null out the row."""
        f = tmp_path / "BASIS_PAR_SGD-SOR-ON.USD-SOFR-ON.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "SDSF66M Curncy", "SDSF65Y Curncy"],
            ["Tenor", "BASIS_PAR_SGD_SPOT_6M", "BASIS_PAR_SGD_SPOT_5Y"],
            ["Maturity", "0.5", "5"],
            [["29/04/2026", "2.5", "-13.75"]],
        )
        src = _build_source_file(
            f, "BASIS", "SGD-SOR-ON.USD-SOFR-ON",
            "SGD", "BASIS_SOR_VS_SOFR", "basis",
        )
        out = BloombergCSVRatesExtractor().extract([src])
        assert len(out) == 2
        assert (out["quote"] == "basis").all()
        assert (out["ccy"] == "SGD").all()
        assert (out["curve"] == "BASIS_SOR_VS_SOFR").all()
        # Sanity: values are bps (negative spreads, double-digit magnitudes)
        v_5y = float(out[out["tenor"] == "5Y"]["value"].iloc[0])
        assert v_5y == pytest.approx(-13.75, abs=1e-6)

    # ── CCS extraction ────────────────────────────────────────────────
    def test_ccs_stamps_quote_par(self, tmp_path: Path) -> None:
        """CCS curves are normal swap rates in % — quote stays 'par'."""
        f = tmp_path / "CCS_PAR_CNH-FIXED.USD-SOFR-ON.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "CNHSQQF BGN Curncy", "CNHSQQ5 BGN Curncy"],
            ["Tenor", "CCS_PAR_CNH_SPOT_6M", "CCS_PAR_CNH_SPOT_5Y"],
            ["Maturity", "0.5", "5"],
            [["29/04/2026", "1.185", "1.31"]],
        )
        src = _build_source_file(
            f, "CCS", "CNH-FIXED.USD-SOFR-ON",
            "CNH", "CCS_VS_SOFR", "ccs",
        )
        out = BloombergCSVRatesExtractor().extract([src])
        assert len(out) == 2
        assert (out["quote"] == "par").all()  # CCS is %, so 'par' (not 'basis')
        assert (out["ccy"] == "CNH").all()
        assert (out["curve"] == "CCS_VS_SOFR").all()
        v_5y = float(out[out["tenor"] == "5Y"]["value"].iloc[0])
        assert v_5y == pytest.approx(1.31, abs=1e-6)

# ── Discovery ─────────────────────────────────────────────────────────


class TestDiscoverBBGRatesFiles:
    def test_skips_known_skip_folders(self, tmp_path: Path) -> None:
        """Quirk #10: empty PAR folder + known-skip folders excluded."""
        bbg_root = tmp_path / "BBG"
        # Create a valid IRS curve
        (bbg_root / "IRS" / "AUD-BBSW-3M" / "PAR").mkdir(parents=True)
        f1 = bbg_root / "IRS" / "AUD-BBSW-3M" / "PAR" / "IRS_PAR_AUD-BBSW-3M.csv"
        _write_csv_3hdr(
            f1,
            ["Ticker", "X"],
            ["Tenor", "IRS_PAR_AUQ_SPOT_3M"],
            ["Maturity", "0.25"],
            [["24/04/2026", "4.35"]],
        )
        # Create an empty PAR folder (AUD-BBSW.IAUS-3M anomaly)
        (bbg_root / "IRS" / "AUD-BBSW.IAUS-3M" / "PAR").mkdir(parents=True)
        # Create a skip-folder
        (bbg_root / "IRS" / "MS" / "PAR").mkdir(parents=True)
        f2 = bbg_root / "IRS" / "MS" / "PAR" / "IRS_PAR_MS.csv"
        _write_csv_3hdr(
            f2,
            ["Ticker", "X"],
            ["Tenor", "IRS_PAR_USD_SPOT_3M"],
            ["Maturity", "0.25"],
            [["24/04/2026", "4.35"]],
        )

        results = discover_bbg_rates_files(bbg_root)
        assert len(results) == 1
        assert results[0].folder == "AUD-BBSW-3M"

    def test_ori_filename_accepted(self, tmp_path: Path) -> None:
        """Quirk #9: USD-LIBOR-3M file uses -ori suffix."""
        bbg_root = tmp_path / "BBG"
        (bbg_root / "IRS" / "USD-LIBOR-3M" / "PAR").mkdir(parents=True)
        f = bbg_root / "IRS" / "USD-LIBOR-3M" / "PAR" / "IRS_PAR_USD-LIBOR-3M-ori.csv"
        _write_csv_3hdr(
            f,
            ["Ticker", "X"],
            ["Tenor", "IRS_PAR_USD_SPOT_3M"],
            ["Maturity", "0.25"],
            [["25/03/2024", "5.59"]],
        )
        results = discover_bbg_rates_files(bbg_root)
        assert len(results) == 1
        assert results[0].folder == "USD-LIBOR-3M"

    def test_excludes_copy_old_new(self, tmp_path: Path) -> None:
        bbg_root = tmp_path / "BBG"
        (bbg_root / "IRS" / "AUD-BBSW-3M" / "PAR").mkdir(parents=True)
        # Create canonical + Copy + old variants
        for stem in [
            "IRS_PAR_AUD-BBSW-3M",
            "IRS_PAR_AUD-BBSW-3M - Copy",
            "IRS_PAR_AUD-BBSW-3M-old",
            "IRS_PAR_AUD-BBSW-3M-new",
        ]:
            f = bbg_root / "IRS" / "AUD-BBSW-3M" / "PAR" / f"{stem}.csv"
            _write_csv_3hdr(
                f,
                ["Ticker", "X"],
                ["Tenor", "IRS_PAR_AUQ_SPOT_3M"],
                ["Maturity", "0.25"],
                [["24/04/2026", "4.35"]],
            )
        results = discover_bbg_rates_files(bbg_root)
        # Only one result, prefer canonical
        assert len(results) == 1
        assert results[0].path.stem == "IRS_PAR_AUD-BBSW-3M"
