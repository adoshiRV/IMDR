"""No-network tests for the CPI quarterly-core additions.

Covers:
  - AU: the quarterly Trimmed Mean / Weighted Median specs added to
    ``scripts.econ.au.abs.abs_cpi`` ride the dedicated ``CPI_Q`` dataflow
    (TSEST=20 SA), and their source_codes don't collide with the monthly
    analytical series on the legacy ``CPI`` dataflow.
  - NZ: ``statsnz_cpi_core._keep_quarterly`` keeps only the ``QUARTERLY_``
    trim series and drops the sparse ``Annual`` weight-base vintages.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.schema import IndicatorRow, ObservationRow


class TestAbsQuarterlyAnalyticalSpecs:
    def _specs(self):
        from scripts.econ.au.abs.abs_cpi import _build_series

        return {s.imdr_code: s for s in _build_series()}

    def test_quarterly_analytical_codes_present(self) -> None:
        specs = self._specs()
        for code in (
            "ABS.CPI.TRIMMED_MEAN_Q_INDEX.AU",
            "ABS.CPI.TRIMMED_MEAN_Q_QOQ.AU",
            "ABS.CPI.TRIMMED_MEAN_Q_YOY.AU",
            "ABS.CPI.WEIGHTED_MEDIAN_Q_INDEX.AU",
            "ABS.CPI.WEIGHTED_MEDIAN_Q_QOQ.AU",
            "ABS.CPI.WEIGHTED_MEDIAN_Q_YOY.AU",
        ):
            assert code in specs, f"missing quarterly analytical spec {code}"

    def test_all_quarterly_analytical_use_cpi_q_dataflow_and_are_sa(self) -> None:
        # Cover ALL 6 new specs, not just the YoY pair — a key/dataflow/is_sa
        # regression on the index or QoQ specs must not slip through.
        specs = self._specs()
        for measure_infix in ("INDEX", "QOQ", "YOY"):
            for stat in ("TRIMMED_MEAN", "WEIGHTED_MEDIAN"):
                s = specs[f"ABS.CPI.{stat}_Q_{measure_infix}.AU"]
                assert s.dataflow == "CPI_Q"
                assert s.frequency == "QUARTERLY"
                assert s.is_sa is True
                assert s.unit == ("index" if measure_infix == "INDEX" else
                                  "pct_yoy" if measure_infix == "YOY" else "pct")
                # SA national: TSEST=20, REGION=50, FREQ=Q
                assert s.key.endswith(".20.50.Q")

    def test_measure_digit_matches_infix(self) -> None:
        # INDEX→MEASURE 1, QOQ→2, YOY→3, for both stats.
        specs = self._specs()
        for stat in ("TRIMMED_MEAN", "WEIGHTED_MEDIAN"):
            assert specs[f"ABS.CPI.{stat}_Q_INDEX.AU"].key.startswith("1.")
            assert specs[f"ABS.CPI.{stat}_Q_QOQ.AU"].key.startswith("2.")
            assert specs[f"ABS.CPI.{stat}_Q_YOY.AU"].key.startswith("3.")

    def test_index_code_matches_stat(self) -> None:
        # Trimmed Mean = 999902, Weighted Median = 999903.
        specs = self._specs()
        for infix in ("INDEX", "QOQ", "YOY"):
            assert ".999902." in specs[f"ABS.CPI.TRIMMED_MEAN_Q_{infix}.AU"].key
            assert ".999903." in specs[f"ABS.CPI.WEIGHTED_MEDIAN_Q_{infix}.AU"].key

    def test_source_codes_unique_across_dataflows(self) -> None:
        # The monthly analytical series (CPI dataflow) and quarterly (CPI_Q)
        # share the 999902/999903.20.50 stem but must differ via the dataflow
        # prefix — assert separation for BOTH stats.
        specs = self._specs()
        src = [s.source_code for s in specs.values()]
        assert len(src) == len(set(src)), "duplicate source_code in ABS CPI specs"
        for stat in ("TRIMMED_MEAN", "WEIGHTED_MEDIAN"):
            m = specs[f"ABS.CPI.{stat}_M_YOY.AU"].source_code
            q = specs[f"ABS.CPI.{stat}_Q_YOY.AU"].source_code
            assert m != q
            assert m.startswith("ABS.CPI.")
            assert q.startswith("ABS.CPI_Q.")


class TestNzKeepQuarterly:
    def _ind(self, code: str) -> IndicatorRow:
        return IndicatorRow(
            imdr_code=code, vendor_name="statsnz", source_code=code,
            display_name=code, unit="pct", frequency="QUARTERLY",
            country_iso="NZ", category="cpi", is_seasonally_adjusted=False,
        )

    def _obs(self, code: str) -> ObservationRow:
        now = datetime.datetime.now(datetime.timezone.utc)
        return ObservationRow(
            imdr_code=code, obs_date=datetime.date(2026, 3, 31),
            vintage=0, release_date=now, value=0.4, ingested_at=now,
        )

    def test_keeps_quarterly_drops_annual(self) -> None:
        from scripts.econ.nz.statsnz.statsnz_cpi_core import _keep_quarterly

        codes = [
            "STATSNZ.CPI.TRIM.QUARTERLY_WEIGHTED_MEDIAN.NZ",
            "STATSNZ.CPI.TRIM.QUARTERLY_10_PERCENT_TRIM.NZ",
            "STATSNZ.CPI.TRIM.ANNUAL_WEIGHTED_MEDIAN.NZ",
            "STATSNZ.CPI.TRIM.ANNUAL_30_PERCENT_TRIM_JUNE_2020_QTR_WEIGHTS.NZ",
        ]
        inds = [self._ind(c) for c in codes]
        obs = [self._obs(c) for c in codes]
        kept_i, kept_o = _keep_quarterly(inds, obs)
        kept_codes = {i.imdr_code for i in kept_i}
        assert kept_codes == {
            "STATSNZ.CPI.TRIM.QUARTERLY_WEIGHTED_MEDIAN.NZ",
            "STATSNZ.CPI.TRIM.QUARTERLY_10_PERCENT_TRIM.NZ",
        }
        # observations filtered in lock-step with indicators
        assert {o.imdr_code for o in kept_o} == kept_codes

    def test_empty_input(self) -> None:
        from scripts.econ.nz.statsnz.statsnz_cpi_core import _keep_quarterly

        assert _keep_quarterly([], []) == ([], [])
