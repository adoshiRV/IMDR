"""Tests for BloombergCSVFXRateExtractor — inverse FxSwap→FxFwd math."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from imdr.domains.fx.extractors_rate_bbg import (
    BBG_POINTS_DIVISOR,
    BBGFXSourceFile,
    BloombergCSVFXRateExtractor,
    alias_to_tenor,
    discover_bbg_fx_files,
    parse_bbg_csv,
    resolve_pair_orientation,
)

# Use a fixed snapshot timestamp for determinism
SNAP_TS = datetime(2026, 4, 23, 11, 20, 0, tzinfo=timezone.utc)


def _write_jpy_csv(path: Path) -> None:
    """JPY: 2-dp pair, divisor 100. spot=159.55, 1M outright=159.1444."""
    path.write_text(
        "Ticker,JPY curncy,JPY1W curncy,JPY1M curncy,JPY3m curncy,JPY6m curncy,JPY12m curncy\n"
        "Tenor,FX_JPY_SPOT,FX_JPY_1W,FX_JPY_1M,FX_JPY_3M,FX_JPY_6M,FX_JPY_12M\n"
        "Maturity,0,0.020833333,0.083333333,0.25,0.5,1\n"
        "23/04/2026,159.55,159.4146,159.1444,158.3355,157.1785,155.0571\n"
        "22/04/2026,159.48,159.3863,159.0474,158.2668,157.0886,154.9774\n"
    )


def _write_eur_csv(path: Path) -> None:
    """EUR: G10 4-dp pair, divisor 10000. spot=1.18, 1M=1.1819 (19 pips)."""
    path.write_text(
        "Ticker,EUR curncy,EUR1W curncy,EUR1M curncy,EUR3M curncy\n"
        "Tenor,FX_EUR_SPOT,FX_EUR_1W,FX_EUR_1M,FX_EUR_3M\n"
        "Maturity,0,0.020833333,0.083333333,0.25\n"
        "23/04/2026,1.1800,1.1805,1.1819,1.1850\n"
    )


def _write_hkd_csv(path: Path) -> None:
    """HKD: NDF-like, no divisor. Tickers are already outright."""
    path.write_text(
        "Ticker,HKD curncy,HKD+1M FMD curncy,HKD+3M FMD curncy\n"
        "Tenor,FX_HKD_SPOT,FX_HKD_1M,FX_HKD_3M\n"
        "Maturity,0,0.083333333,0.25\n"
        "23/04/2026,7.8322,7.8233,7.8059\n"
    )


def _write_krw_ndf_csv(path: Path) -> None:
    """KRW NDF: no inverse conversion; tickers return outright."""
    path.write_text(
        "Ticker,KRW BSYN curncy,KWN+1W curncy,KWN+1M curncy\n"
        "Tenor,FX_KRW_SPOT,FX_KRW_1W,FX_KRW_1M\n"
        "Maturity,0,0.020833333,0.083333333\n"
        "23/04/2026,1380.00,1381.50,1384.00\n"
    )


def _write_mxn_csv(path: Path) -> None:
    """MXN: divisor 10000 per active R script (line 252)."""
    path.write_text(
        "Ticker,MXN curncy,MXN1M curncy\n"
        "Tenor,FX_MXN_SPOT,FX_MXN_1M\n"
        "Maturity,0,0.083333333\n"
        "23/04/2026,17.0000,17.0500\n"
    )


class TestPairOrientation:
    def test_eur_is_base(self) -> None:
        assert resolve_pair_orientation("EUR") == ("EUR", "USD")

    def test_gbp_is_base(self) -> None:
        assert resolve_pair_orientation("GBP") == ("GBP", "USD")

    def test_aud_is_base(self) -> None:
        assert resolve_pair_orientation("AUD") == ("AUD", "USD")

    def test_nzd_is_base(self) -> None:
        assert resolve_pair_orientation("NZD") == ("NZD", "USD")

    def test_jpy_is_quote(self) -> None:
        assert resolve_pair_orientation("JPY") == ("USD", "JPY")

    def test_krw_is_quote(self) -> None:
        assert resolve_pair_orientation("KRW") == ("USD", "KRW")

    def test_mxn_is_quote(self) -> None:
        assert resolve_pair_orientation("MXN") == ("USD", "MXN")


class TestAliasToTenor:
    def test_strip_prefix(self) -> None:
        assert alias_to_tenor("FX_JPY_1M", "JPY") == "1M"

    def test_spot(self) -> None:
        assert alias_to_tenor("FX_JPY_SPOT", "JPY") == "SPOT"

    def test_12m_normalizes_to_1y(self) -> None:
        assert alias_to_tenor("FX_JPY_12M", "JPY") == "1Y"

    def test_unknown_ccy_returns_none(self) -> None:
        # Strict prefix match: alias ccy must match the file's ccy, no
        # fall-through. Files whose tenor labels use a different prefix
        # (e.g. CNO file with FX_CNY_* labels) won't parse — rows skipped
        # with warning, no silent contamination.
        assert alias_to_tenor("FX_USD_1M", "JPY") is None
        assert alias_to_tenor("FX_CNY_1M", "CNO") is None  # CNO file uses CNY labels — won't load

    def test_lowercase_normalized(self) -> None:
        assert alias_to_tenor("FX_JPY_1m", "JPY") == "1M"


class TestParseBBGCsv:
    def test_jpy_parses(self, tmp_path: Path) -> None:
        f = tmp_path / "FX_JPY.csv"
        _write_jpy_csv(f)
        df = parse_bbg_csv(f)
        # 2 rows × 6 tenor cols = 12 long rows
        assert len(df) == 12
        assert set(df.columns) == {"obs_date", "tenor_alias", "value"}
        spots = df[df["tenor_alias"] == "FX_JPY_SPOT"]
        assert len(spots) == 2
        assert spots["value"].iloc[0] == pytest.approx(159.55)

    def test_uk_date_format(self, tmp_path: Path) -> None:
        f = tmp_path / "FX_JPY.csv"
        _write_jpy_csv(f)
        df = parse_bbg_csv(f)
        from datetime import date
        assert date(2026, 4, 23) in set(df["obs_date"])
        assert date(2026, 4, 22) in set(df["obs_date"])

    def test_too_short_file_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "short.csv"
        f.write_text("Ticker,EUR curncy\n")
        with pytest.raises(ValueError, match="fewer than 4 rows"):
            parse_bbg_csv(f)

    def test_wrong_header_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "wrong.csv"
        f.write_text("WrongHeader,col1\nrow1,val1\nrow2,val2\nrow3,val3\n")
        with pytest.raises(ValueError, match="expected 'Ticker'"):
            parse_bbg_csv(f)


class TestExtractorConversion:
    def test_jpy_inverse_conversion_2dp(self, tmp_path: Path) -> None:
        """JPY: divisor 100. 1M outright 159.1444 vs spot 159.55 → points = -40.56"""
        f = tmp_path / "FX_JPY.csv"
        _write_jpy_csv(f)
        src = BBGFXSourceFile(
            path=f, ccy="JPY", base_ccy="USD", quote_ccy="JPY", obs_ts=SNAP_TS,
        )
        df = BloombergCSVFXRateExtractor().extract([src])

        # SPOT row should have NULL fwd_points
        spot = df[(df["obs_date"].astype(str) == "2026-04-23") & (df["tenor"] == "SPOT")]
        assert len(spot) == 1
        assert pd.isna(spot["fwd_points"].iloc[0])
        assert spot["mid_rate"].iloc[0] == pytest.approx(159.55)

        # 1M: outright preserved, fwd_points = (159.1444 - 159.55) * 100 = -40.56
        m1 = df[(df["obs_date"].astype(str) == "2026-04-23") & (df["tenor"] == "1M")]
        assert len(m1) == 1
        assert m1["mid_rate"].iloc[0] == pytest.approx(159.1444)
        assert float(m1["fwd_points"].iloc[0]) == pytest.approx(-40.56, abs=0.01)

    def test_eur_inverse_conversion_4dp(self, tmp_path: Path) -> None:
        """EUR: divisor 10000. 1M=1.1819, spot=1.18 → points = 19"""
        f = tmp_path / "FX_EUR.csv"
        _write_eur_csv(f)
        src = BBGFXSourceFile(
            path=f, ccy="EUR", base_ccy="EUR", quote_ccy="USD", obs_ts=SNAP_TS,
        )
        df = BloombergCSVFXRateExtractor().extract([src])

        m1 = df[df["tenor"] == "1M"]
        assert len(m1) == 1
        assert m1["mid_rate"].iloc[0] == pytest.approx(1.1819)
        assert float(m1["fwd_points"].iloc[0]) == pytest.approx(19.0, abs=0.01)

        m3 = df[df["tenor"] == "3M"]
        # (1.1850 - 1.1800) * 10000 = 50
        assert float(m3["fwd_points"].iloc[0]) == pytest.approx(50.0, abs=0.01)

    def test_hkd_no_conversion(self, tmp_path: Path) -> None:
        """HKD tickers are already outright (FMD); fwd_points should be NULL."""
        f = tmp_path / "FX_HKD.csv"
        _write_hkd_csv(f)
        src = BBGFXSourceFile(
            path=f, ccy="HKD", base_ccy="USD", quote_ccy="HKD", obs_ts=SNAP_TS,
        )
        df = BloombergCSVFXRateExtractor().extract([src])

        # All non-SPOT rows should have NULL fwd_points
        non_spot = df[df["tenor"] != "SPOT"]
        assert len(non_spot) > 0
        assert non_spot["fwd_points"].isna().all()

        # mid_rate is the outright (no transformation)
        m1 = non_spot[non_spot["tenor"] == "1M"]
        assert m1["mid_rate"].iloc[0] == pytest.approx(7.8233)

    def test_krw_ndf_no_conversion(self, tmp_path: Path) -> None:
        """KRW NDF: tickers return outright. fwd_points NULL."""
        f = tmp_path / "FX_KRW.csv"
        _write_krw_ndf_csv(f)
        src = BBGFXSourceFile(
            path=f, ccy="KRW", base_ccy="USD", quote_ccy="KRW", obs_ts=SNAP_TS,
        )
        df = BloombergCSVFXRateExtractor().extract([src])

        non_spot = df[df["tenor"] != "SPOT"]
        assert non_spot["fwd_points"].isna().all()
        m1 = non_spot[non_spot["tenor"] == "1M"]
        assert m1["mid_rate"].iloc[0] == pytest.approx(1384.00)

    def test_mxn_inverse_conversion_4dp(self, tmp_path: Path) -> None:
        """MXN: divisor 10000. 1M=17.05, spot=17.0 → points = 500"""
        f = tmp_path / "FX_MXN.csv"
        _write_mxn_csv(f)
        src = BBGFXSourceFile(
            path=f, ccy="MXN", base_ccy="USD", quote_ccy="MXN", obs_ts=SNAP_TS,
        )
        df = BloombergCSVFXRateExtractor().extract([src])

        m1 = df[df["tenor"] == "1M"]
        assert m1["mid_rate"].iloc[0] == pytest.approx(17.05)
        assert float(m1["fwd_points"].iloc[0]) == pytest.approx(500.0, abs=0.01)


class TestExtractorOutputShape:
    def test_obs_ts_stamped_consistently(self, tmp_path: Path) -> None:
        f = tmp_path / "FX_JPY.csv"
        _write_jpy_csv(f)
        src = BBGFXSourceFile(
            path=f, ccy="JPY", base_ccy="USD", quote_ccy="JPY", obs_ts=SNAP_TS,
        )
        df = BloombergCSVFXRateExtractor().extract([src])
        # Every row should have the SAME obs_ts (one snapshot moment per file)
        assert (df["obs_ts"] == SNAP_TS).all()
        assert (df["ts"] == SNAP_TS).all()

    def test_columns_match_citi_extractor(self, tmp_path: Path) -> None:
        f = tmp_path / "FX_EUR.csv"
        _write_eur_csv(f)
        src = BBGFXSourceFile(
            path=f, ccy="EUR", base_ccy="EUR", quote_ccy="USD", obs_ts=SNAP_TS,
        )
        df = BloombergCSVFXRateExtractor().extract([src])
        # Should be a superset of Citi WIDE_COLUMNS
        for col in ("ts", "base_ccy", "quote_ccy", "tenor", "mid_rate", "fwd_points"):
            assert col in df.columns

    def test_empty_input_returns_empty_df(self) -> None:
        df = BloombergCSVFXRateExtractor().extract([])
        assert df.empty
        assert "tenor" in df.columns

    def test_multiple_files_concatenated(self, tmp_path: Path) -> None:
        eur_path = tmp_path / "FX_EUR.csv"
        jpy_path = tmp_path / "FX_JPY.csv"
        _write_eur_csv(eur_path)
        _write_jpy_csv(jpy_path)
        srcs = [
            BBGFXSourceFile(path=eur_path, ccy="EUR", base_ccy="EUR",
                            quote_ccy="USD", obs_ts=SNAP_TS),
            BBGFXSourceFile(path=jpy_path, ccy="JPY", base_ccy="USD",
                            quote_ccy="JPY", obs_ts=SNAP_TS),
        ]
        df = BloombergCSVFXRateExtractor().extract(srcs)
        assert {"EUR", "USD"} == set(df["base_ccy"])

    def test_per_file_error_isolated(self, tmp_path: Path) -> None:
        good = tmp_path / "FX_EUR.csv"
        bad = tmp_path / "FX_BAD.csv"
        _write_eur_csv(good)
        bad.write_text("BAD\n")  # malformed; will raise

        ext = BloombergCSVFXRateExtractor()
        srcs = [
            BBGFXSourceFile(path=bad, ccy="BAD", base_ccy="USD",
                            quote_ccy="BAD", obs_ts=SNAP_TS),
            BBGFXSourceFile(path=good, ccy="EUR", base_ccy="EUR",
                            quote_ccy="USD", obs_ts=SNAP_TS),
        ]
        df = ext.extract(srcs)
        # Good file still loads; bad file logged in errors
        assert len(df) > 0
        assert len(ext.errors) == 1
        assert "FX_BAD" in ext.errors[0]["path"]

    def test_csv_without_spot_row_logs_warning_and_returns_empty(
        self, tmp_path: Path,
    ) -> None:
        """A CSV with forward tenors but no SPOT row would silently produce
        zero rows (the (outright - spot) merge drops everything). The extractor
        now logs `bbg_no_spot_row` so the malformed upstream file is visible.
        """
        import structlog

        path = tmp_path / "FX_EUR.csv"
        # Forward tenors only — no SPOT column.
        path.write_text(
            "Ticker,EUR1W curncy,EUR1M curncy\n"
            "Tenor,FX_EUR_1W,FX_EUR_1M\n"
            "Maturity,0.020833333,0.083333333\n"
            "23/04/2026,1.1810,1.1819\n"
        )
        src = BBGFXSourceFile(
            path=path, ccy="EUR", base_ccy="EUR",
            quote_ccy="USD", obs_ts=SNAP_TS,
        )

        with structlog.testing.capture_logs() as logs:
            df = BloombergCSVFXRateExtractor().extract([src])

        # No rows produced — the merge drops every forward when spot is empty.
        assert df.empty
        # The warning event was emitted with the expected payload.
        warnings = [e for e in logs if e["event"] == "bbg_no_spot_row"]
        assert len(warnings) == 1
        assert warnings[0]["ccy"] == "EUR"
        assert warnings[0]["n_non_spot"] == 2
        assert warnings[0]["log_level"] == "warning"


class TestDiscoverBBGFXFiles:
    def test_resolves_existing_files(self, tmp_path: Path) -> None:
        for ccy in ("EUR", "JPY"):
            (tmp_path / ccy).mkdir()
            (tmp_path / ccy / f"FX_{ccy}.csv").write_text("data")

        srcs = discover_bbg_fx_files(tmp_path, ["EUR", "JPY", "MISSING"])
        # MISSING is silently skipped (caller decides)
        assert len(srcs) == 2
        assert {s.ccy for s in srcs} == {"EUR", "JPY"}
        assert srcs[0].obs_ts.tzinfo is not None  # tz-aware

    def test_pair_orientation_applied(self, tmp_path: Path) -> None:
        (tmp_path / "EUR").mkdir()
        (tmp_path / "EUR" / "FX_EUR.csv").write_text("data")
        (tmp_path / "JPY").mkdir()
        (tmp_path / "JPY" / "FX_JPY.csv").write_text("data")

        srcs = discover_bbg_fx_files(tmp_path, ["EUR", "JPY"])
        eur = next(s for s in srcs if s.ccy == "EUR")
        jpy = next(s for s in srcs if s.ccy == "JPY")
        assert (eur.base_ccy, eur.quote_ccy) == ("EUR", "USD")
        assert (jpy.base_ccy, jpy.quote_ccy) == ("USD", "JPY")


class TestDivisorTable:
    def test_g10_have_10000(self) -> None:
        for ccy in ("AUD", "EUR", "GBP", "NZD", "CAD", "CHF", "NOK", "SEK", "SGD"):
            assert BBG_POINTS_DIVISOR[ccy] == 10000.0

    def test_jpy_thb_have_100(self) -> None:
        assert BBG_POINTS_DIVISOR["JPY"] == 100.0
        assert BBG_POINTS_DIVISOR["THB"] == 100.0

    def test_ndf_and_hkd_have_none(self) -> None:
        for ccy in ("HKD", "KRW", "INR", "IDR", "PHP", "TWD", "MYR"):
            assert BBG_POINTS_DIVISOR[ccy] is None

    def test_cny_family_have_none(self) -> None:
        for ccy in ("CNH", "CNY", "CNO"):
            assert BBG_POINTS_DIVISOR[ccy] is None

    def test_mxn_pln_ils_have_10000(self) -> None:
        # Per active R script (line 252): MXN, ILS, IDO use 4-dp divisor.
        # PLN added by us to align with G10 deliverable convention.
        assert BBG_POINTS_DIVISOR["MXN"] == 10000.0
        assert BBG_POINTS_DIVISOR["PLN"] == 10000.0
        assert BBG_POINTS_DIVISOR["ILS"] == 10000.0
