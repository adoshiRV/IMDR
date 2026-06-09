"""Tests for region-aware cohort selection in rates ingest."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from imdr.domains.rates.run_cohorts import (
    LATE_PUBLISH_CURVES,
    REGION_ANCHORS,
    REGION_MARKETS,
    STATIC_QUOTE_FIRE_HOURS,
    UTC_FIRE_WINDOWS,
    VALID_REGIONS,
    default_run_label,
    is_static_quote_fire,
    resolve_region_auto,
    select_curves,
    target_for_region,
)
from imdr.universe.rates import get_rates_universe


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def universe():
    return get_rates_universe()


@pytest.fixture(scope="module")
def all_curves(universe):
    return universe.all_curves()


# ── Cohort selection ────────────────────────────────────────────────

class TestSelectCurves:
    def test_all_returns_every_active_curve(self, all_curves):
        result = select_curves(all_curves, "all")
        for c in result:
            assert c.status != "ceased", f"{c.ccy}.{c.curve} is ceased — should be excluded"
        active_count = sum(1 for c in all_curves if c.status != "ceased")
        assert len(result) == active_count

    def test_unknown_region_raises(self, all_curves):
        with pytest.raises(ValueError, match="Unknown region"):
            select_curves(all_curves, "antarctica")

    def test_ceased_curves_excluded_from_all_regions(self, all_curves):
        for region in ("asia", "europe", "americas", "all"):
            result = select_curves(all_curves, region)
            for c in result:
                assert c.status != "ceased", (
                    f"{c.ccy}.{c.curve} is ceased — leaked into {region} cohort"
                )

    def test_late_publish_curves_route_to_americas_only(self, all_curves):
        late_keys = LATE_PUBLISH_CURVES
        for region in ("asia", "europe"):
            result_keys = {(c.ccy, c.curve) for c in select_curves(all_curves, region)}
            for late_key in late_keys:
                assert late_key not in result_keys, (
                    f"{late_key} (late publisher) leaked into {region} cohort"
                )
        americas_keys = {(c.ccy, c.curve) for c in select_curves(all_curves, "americas")}
        for late_key in late_keys:
            assert late_key in americas_keys, (
                f"{late_key} should be in americas cohort but isn't"
            )

    def test_asia_cohort_contents(self, all_curves):
        """Asia cohort should include core APAC + Australasia curves; exclude USD/EUR."""
        result_keys = {(c.ccy, c.curve) for c in select_curves(all_curves, "asia")}
        expected_in = {
            ("AUD", "AONIA"), ("AUD", "BBSW"),
            ("NZD", "NZIONA"), ("NZD", "BKBM"),
            ("JPY", "TONAR"),         # not in late list
            ("HKD", "HIBOR"),
            ("SGD", "SORA"),
            ("THB", "THOR"),
            ("CNH", "CNH_HIBOR"), ("CNY", "SHIBOR"), ("CNY", "NDIRS"),
            ("IDR", "JIBOR"), ("INR", "MIFOR"), ("KRW", "CD"),
            ("MYR", "KLIBOR"), ("PHP", "PHIREF"), ("TWD", "TAIBOR"),
            ("VND", "VND_REF"),
        }
        expected_out = {("USD", "SOFR"), ("EUR", "EUROSTR"), ("GBP", "SONIA")}

        for key in expected_in:
            assert key in result_keys, f"asia missing {key}"
        for key in expected_out:
            assert key not in result_keys, f"asia should not contain {key}"

    def test_europe_cohort_contents(self, all_curves):
        result_keys = {(c.ccy, c.curve) for c in select_curves(all_curves, "europe")}
        expected_in = {
            ("EUR", "EUROSTR"), ("EUR", "EURIBOR"),
            ("GBP", "SONIA"),
            ("CHF", "SARON"),
            ("NOK", "NOWA"), ("NOK", "NIBOR"),
            ("SEK", "STINA"), ("SEK", "STIBOR"),
        }
        expected_out = {
            ("USD", "SOFR"), ("JPY", "TONAR"), ("AUD", "AONIA"),
            ("CAD", "CORRA"),  # late list → americas
        }
        for key in expected_in:
            assert key in result_keys, f"europe missing {key}"
        for key in expected_out:
            assert key not in result_keys, f"europe should not contain {key}"

    def test_americas_cohort_includes_late_list(self, all_curves):
        result_keys = {(c.ccy, c.curve) for c in select_curves(all_curves, "americas")}
        # Every late curve must appear
        for key in LATE_PUBLISH_CURVES:
            assert key in result_keys, f"americas missing late curve {key}"
        # Asia/Europe curves must not appear
        forbidden = {("EUR", "EUROSTR"), ("AUD", "BBSW"), ("HKD", "HIBOR")}
        for key in forbidden:
            assert key not in result_keys, f"americas should not contain {key}"

    def test_jpy_split_across_cohorts(self, all_curves):
        """TONAR routes to ASIA (currency JP); JSCC + LCH route to AMERICAS (late list)."""
        asia = {(c.ccy, c.curve) for c in select_curves(all_curves, "asia")}
        americas = {(c.ccy, c.curve) for c in select_curves(all_curves, "americas")}
        assert ("JPY", "TONAR") in asia
        assert ("JPY", "TONAR_JSCC") in americas
        assert ("JPY", "TONAR_LCH") in americas
        assert ("JPY", "TONAR_JSCC") not in asia
        assert ("JPY", "TONAR_LCH") not in asia

    def test_no_curve_appears_in_two_cohorts(self, all_curves):
        asia = {(c.ccy, c.curve) for c in select_curves(all_curves, "asia")}
        europe = {(c.ccy, c.curve) for c in select_curves(all_curves, "europe")}
        americas = {(c.ccy, c.curve) for c in select_curves(all_curves, "americas")}
        assert asia & europe == set()
        assert asia & americas == set()
        assert europe & americas == set()

    def test_cohorts_partition_active_curves(self, all_curves):
        """Union of three cohorts == all active curves (no orphans)."""
        asia = {(c.ccy, c.curve) for c in select_curves(all_curves, "asia")}
        europe = {(c.ccy, c.curve) for c in select_curves(all_curves, "europe")}
        americas = {(c.ccy, c.curve) for c in select_curves(all_curves, "americas")}
        all_active = {(c.ccy, c.curve) for c in all_curves if c.status != "ceased"}
        union = asia | europe | americas
        orphans = all_active - union
        assert orphans == set(), (
            f"{len(orphans)} active curve(s) not in any region cohort: {orphans}"
        )


# ── UTC auto-resolution ─────────────────────────────────────────────

class TestResolveRegionAuto:
    @pytest.mark.parametrize("hour, expected", [
        (8,  "asia"),       # window start
        (10, "asia"),       # mid-Asia window
        (14, "asia"),       # last hour in window
        (15, None),         # gap before europe
        (16, "europe"),     # window start
        (18, "europe"),
        (20, "europe"),     # last hour in window
        (21, "americas"),   # window start
        (23, "americas"),
        (0,  "americas"),   # midnight UTC, still in americas window
        (5,  "americas"),   # last hour
        (6,  None),         # gap before asia
        (7,  None),         # gap before asia
    ])
    def test_hour_resolution(self, hour, expected):
        now = datetime(2026, 4, 28, hour, 0, tzinfo=timezone.utc)
        assert resolve_region_auto(now) == expected

    def test_uses_now_utc_when_arg_omitted(self):
        # Just confirm it doesn't crash and returns a region or None.
        result = resolve_region_auto()
        assert result is None or result in REGION_MARKETS


# ── Constants integrity ─────────────────────────────────────────────

class TestConstants:
    def test_valid_regions_includes_all_named_regions(self):
        for region in REGION_MARKETS:
            assert region in VALID_REGIONS
        assert "all" in VALID_REGIONS

    def test_region_anchors_are_in_market_codes(self):
        for region, anchor in REGION_ANCHORS.items():
            assert anchor in REGION_MARKETS[region], (
                f"anchor {anchor} for {region} not in its market set"
            )

    def test_fire_windows_dont_overlap(self):
        # ASIA + EUROPE are non-wrapping, AMERICAS wraps midnight.
        # Check no hour falls in two regions.
        for hour in range(24):
            matches = [
                region for region, win in UTC_FIRE_WINDOWS.items()
                if (win[0] < win[1] and win[0] <= hour < win[1])
                or (win[0] >= win[1] and (hour >= win[0] or hour < win[1]))
            ]
            assert len(matches) <= 1, (
                f"hour {hour} matches multiple regions: {matches}"
            )

    def test_late_publish_curves_include_all_overnight_publishers(self):
        # Sanity check — these MUST be in the late list.
        for key in [("USD", "SOFR"), ("USD", "FEDFUND"), ("CAD", "CORRA"),
                    ("JPY", "TONAR_JSCC"), ("JPY", "TONAR_LCH")]:
            assert key in LATE_PUBLISH_CURVES


# ── Helpers ─────────────────────────────────────────────────────────

class TestDefaultRunLabel:
    @pytest.mark.parametrize("region, expected", [
        ("asia", "ASIA_PM"),
        ("europe", "EUROPE_PM"),
        ("americas", "AMERICAS_PM"),
    ])
    def test_label_format(self, region, expected):
        assert default_run_label(region) == expected


class TestTargetForRegion:
    @pytest.mark.parametrize("region", ["asia", "europe", "americas", "all"])
    def test_returns_utc_datetime(self, region):
        result = target_for_region(region)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None


class TestIsStaticQuoteFire:
    @pytest.mark.parametrize("region, hour, expected", [
        ("asia",     12, True),
        ("asia",      9, False),
        ("europe",   18, True),
        ("europe",   16, False),
        ("americas",  3, True),
        ("americas", 21, False),
        ("americas",  0, False),
    ])
    def test_matches_configured_hour(self, region, hour, expected):
        now = datetime(2026, 4, 29, hour, 0, tzinfo=timezone.utc)
        assert is_static_quote_fire(region, now) is expected

    def test_unknown_region_returns_false(self):
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        assert is_static_quote_fire("all", now) is False

    def test_static_hours_are_within_their_window(self):
        for region, hour in STATIC_QUOTE_FIRE_HOURS.items():
            lo, hi = UTC_FIRE_WINDOWS[region]
            in_window = (lo <= hour < hi) if lo < hi else (hour >= lo or hour < hi)
            assert in_window, f"{region} static hour {hour} outside window {(lo, hi)}"
