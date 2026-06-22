"""Invariants for the curated India fresh-food basket mapping."""
from __future__ import annotations

from imdr.domains.econ import india_food_basket as fb


def test_no_duplicate_canonical_names() -> None:
    names = [row[0] for row in fb.FOCUS]
    assert len(names) == len(set(names)), "duplicate canonical name in FOCUS"


def test_focus_subgroups_have_weights() -> None:
    for name, sub, _tier in fb.FOCUS:
        assert sub in fb.CPI_SUBGROUP_WEIGHT_PCT, f"{name}: unknown sub-group {sub!r}"


def test_focus_tiers_valid() -> None:
    for name, _sub, tier in fb.FOCUS:
        assert tier in {"A", "B", "C"}, f"{name}: bad tier {tier!r}"


def test_focus_and_exclude_and_strip_are_disjoint() -> None:
    focus = {row[0] for row in fb.FOCUS}
    excluded = {n for names in fb.EXCLUDE.values() for n in names}
    assert focus.isdisjoint(fb.STRIP), focus & fb.STRIP
    assert focus.isdisjoint(excluded), focus & excluded
    assert fb.STRIP.isdisjoint(excluded), set(fb.STRIP) & excluded


def test_top_trio_is_in_focus() -> None:
    raw = fb.focus_raw_names()
    for c in fb.TOP:
        assert c in raw, f"TOP commodity {c!r} missing from focus"
        assert fb.subgroup_of(c) == "vegetables"


def test_aliases_point_to_canonical_focus_names() -> None:
    focus = {row[0] for row in fb.FOCUS}
    for alias, target in fb.ALIASES.items():
        assert target in focus, f"alias {alias!r} -> unknown canonical {target!r}"
        assert alias not in focus, f"alias {alias!r} also a canonical name"


def test_focus_raw_names_includes_aliases() -> None:
    raw = fb.focus_raw_names()
    assert "Ladies Finger" in raw                      # alias key included
    assert raw.issuperset({row[0] for row in fb.FOCUS})


def test_subgroup_and_tier_resolve_via_alias() -> None:
    # "Ladies Finger" -> "Bhindi(Ladies Finger)" (vegetables, tier A)
    assert fb.canonical("Ladies Finger") == "Bhindi(Ladies Finger)"
    assert fb.subgroup_of("Ladies Finger") == "vegetables"
    assert fb.tier_of("Ladies Finger") == "A"


def test_unknown_name_resolves_to_none() -> None:
    assert fb.subgroup_of("Wheat") is None           # excluded, not focus
    assert fb.tier_of("Wood") is None                # stripped, not focus
    assert fb.canonical("Wheat") == "Wheat"          # identity when not aliased
