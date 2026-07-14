"""No-network tests for the ABS LF/LF_UNDER age-group and state breakdowns.

Covers ``scripts.econ.au.abs.abs_labour`` (age via LF_AGES, state via LF)
and ``scripts.econ.au.abs.abs_lf_under`` (age + state, both natively on
LF_UNDER). Pure spec-building -- no network calls.
"""

from __future__ import annotations


class TestAbsLabourAgeBreakdown:
    def _specs(self):
        from scripts.econ.au.abs.abs_labour import _build_age_series

        return {s.imdr_code: s for s in _build_age_series()}

    def test_age_codes_present_for_all_bands_and_measures(self) -> None:
        specs = self._specs()
        for measure in ("UNEMPLOYMENT_RATE", "PARTICIPATION_RATE", "EMPLOYED"):
            for band in ("15_24", "25_34", "35_44", "45_54", "55_64", "65_PLUS", "15_64"):
                tsest = "SA" if band in ("15_24", "15_64") else "ORIG"
                code = f"ABS.LF.{measure}_AGE_{band}_{tsest}.AU"
                assert code in specs, f"missing {code}"

    def test_age_series_use_lf_ages_dataflow(self) -> None:
        specs = self._specs()
        assert all(s.dataflow == "LF_AGES" for s in specs.values())

    def test_sa_only_for_15_24_and_15_64(self) -> None:
        specs = self._specs()
        for code, spec in specs.items():
            if code.endswith("_AGE_15_24_SA.AU") or code.endswith("_AGE_15_64_SA.AU"):
                assert spec.is_sa is True
                assert ".20.AUS.M" in spec.key
            elif "_AGE_" in code:
                assert spec.is_sa is False
                assert ".10.AUS.M" in spec.key

    def test_no_collision_with_headline_codes(self) -> None:
        from scripts.econ.au.abs.abs_labour import _build_series

        headline = {s.imdr_code for s in _build_series()}
        age = set(self._specs())
        assert headline.isdisjoint(age)


class TestAbsLabourStateBreakdown:
    def _specs(self):
        from scripts.econ.au.abs.abs_labour import _build_state_series

        return {s.imdr_code: s for s in _build_state_series()}

    def test_state_codes_present_for_all_states_and_measures(self) -> None:
        specs = self._specs()
        sa_states = ("NSW", "VIC", "QLD", "SA", "WA", "TAS")
        orig_states = ("NT", "ACT")
        for measure in ("UNEMPLOYMENT_RATE", "PARTICIPATION_RATE", "EMPLOYED"):
            for state in sa_states:
                assert f"ABS.LF.{measure}_STATE_{state}_SA.AU" in specs
            for state in orig_states:
                assert f"ABS.LF.{measure}_STATE_{state}_ORIG.AU" in specs

    def test_state_series_use_lf_dataflow_and_total_age(self) -> None:
        specs = self._specs()
        for spec in specs.values():
            assert spec.dataflow == "LF"
            assert ".1599." in spec.key

    def test_south_australia_state_code_disjoint_from_national_sa_flag(self) -> None:
        # South Australia's state abbreviation is "SA", which collides
        # textually with the "_SA" seasonally-adjusted suffix already used
        # by the national headline codes -- the STATE_ token plus a second
        # trailing SA/ORIG tag keeps `..._STATE_SA_SA.AU` unambiguous and
        # distinct from the plain `..._SA.AU` national code.
        from scripts.econ.au.abs.abs_labour import _build_series

        specs = self._specs()
        headline = {s.imdr_code for s in _build_series()}
        assert "ABS.LF.UNEMPLOYMENT_RATE_STATE_SA_SA.AU" in specs
        assert "ABS.LF.UNEMPLOYMENT_RATE_SA.AU" in headline
        assert specs["ABS.LF.UNEMPLOYMENT_RATE_STATE_SA_SA.AU"].imdr_code != \
            "ABS.LF.UNEMPLOYMENT_RATE_SA.AU"

    def test_nt_act_are_original_only(self) -> None:
        specs = self._specs()
        for state in ("NT", "ACT"):
            spec = specs[f"ABS.LF.UNEMPLOYMENT_RATE_STATE_{state}_ORIG.AU"]
            assert spec.is_sa is False
            assert ".10." in spec.key


class TestAbsLfUnderAgeAndStateBreakdown:
    def _age_specs(self):
        from scripts.econ.au.abs.abs_lf_under import _build_age_series

        return {s.imdr_code: s for s in _build_age_series()}

    def _state_specs(self):
        from scripts.econ.au.abs.abs_lf_under import _build_state_series

        return {s.imdr_code: s for s in _build_state_series()}

    def test_age_codes_present(self) -> None:
        specs = self._age_specs()
        sa_bands = ("15_24", "25_34", "35_44", "45_54", "15_64")
        orig_bands = ("55_64", "65_PLUS")
        for measure in ("UNDEREMPLOYMENT_RATE", "UNDERUTILISATION_RATE"):
            for band in sa_bands:
                assert f"ABS.LF_UNDER.{measure}_AGE_{band}_SA.AU" in specs
            for band in orig_bands:
                assert f"ABS.LF_UNDER.{measure}_AGE_{band}_ORIG.AU" in specs

    def test_age_series_use_lf_under_dataflow(self) -> None:
        specs = self._age_specs()
        assert all(s.dataflow == "LF_UNDER" for s in specs.values())
        assert all(".AUS.M" in s.key for s in specs.values())

    def test_state_codes_present(self) -> None:
        specs = self._state_specs()
        sa_states = ("NSW", "VIC", "QLD", "SA", "WA", "TAS")
        orig_states = ("NT", "ACT")
        for measure in ("UNDEREMPLOYMENT_RATE", "UNDERUTILISATION_RATE"):
            for state in sa_states:
                assert f"ABS.LF_UNDER.{measure}_STATE_{state}_SA.AU" in specs
            for state in orig_states:
                assert f"ABS.LF_UNDER.{measure}_STATE_{state}_ORIG.AU" in specs

    def test_source_codes_unique(self) -> None:
        from scripts.econ.au.abs.abs_lf_under import (
            _build_series, _build_age_series, _build_state_series,
        )

        all_specs = _build_series() + _build_age_series() + _build_state_series()
        codes = [s.imdr_code for s in all_specs]
        assert len(codes) == len(set(codes)), "duplicate imdr_code in LF_UNDER specs"
        src = [s.source_code for s in all_specs]
        assert len(src) == len(set(src)), "duplicate source_code in LF_UNDER specs"
