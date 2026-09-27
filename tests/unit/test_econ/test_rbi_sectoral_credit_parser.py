"""Unit tests for the RBI Sectoral Deployment of Bank Credit parser.

No network, no DB, no headed Chrome. Fixtures mirror the live XLSX
layouts confirmed 2026-09-15 against three releases spanning the whole
archive (June-2019, August-2022, July-2026).

Covers the things that would silently corrupt the series if they broke:
- the Rs.-billion 2019 era is DECLINED, not mis-scaled into Rs. crore
- Statement 1 carries TWO date-header rows and the second one wins for
  the rows beneath it (the credit block and the sector block disagree on
  the financial-year anchor: `4.Apr,2025` vs `21.Mar,2025`)
- footnote superscripts, glosses in parentheses and the `of which,`
  suffix are stripped out of the slug
- the three Statement-2 `Others` rows are qualified by their parent, and
  the priority-sector memo block is namespaced away from the sectors it
  restates -- without which five rows collapse onto three codes
- a genuine collision RAISES rather than merging two concepts
- `Gross Bank Credit` and `Bank Credit` are one series, not two
"""
from __future__ import annotations

import datetime
import importlib

import pytest

# importlib because the package path contains `in`, a Python keyword.
_mod = importlib.import_module("scripts.econ.in.rbi.rbi_sectoral_credit")

parse_statement = _mod.parse_statement
_slug = _mod._slug
_parse_date = _mod._parse_date
_num = _mod._num
_release_date_from_name = _mod._release_date_from_name

CRORE = ["(Rs. Crore)"]
DATES_A = ["", "26.Jul,2024", "4.Apr,2025", "25.Jul,2025", "31.Mar,2026", "31.Jul,2026"]
DATES_B = ["", "26.Jul,2024", "21.Mar,2025", "25.Jul,2025", "31.Mar,2026", "31.Jul,2026"]


def _sheet(*body: list) -> list[list]:
    """Rows 0-1 are the title and the unit line in every real statement."""
    return [["Statement 1: Deployment of Gross Bank Credit by Major Sector"],
            CRORE, ["Sector", "Outstanding"], *body]


# ---------------------------------------------------------------------------
# Date and number scalars
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cell,expected", [
    ("26.Jul,2024", datetime.date(2024, 7, 26)),
    ("4.Apr,2025", datetime.date(2025, 4, 4)),
    ("28.Aug,2020", datetime.date(2020, 8, 28)),
    ("31.Mar,2026", datetime.date(2026, 3, 31)),
    ("Jun. 23, 2017", datetime.date(2017, 6, 23)),
    ("Mar.29, 2019", datetime.date(2019, 3, 29)),
])
def test_parse_date_accepts_every_era_format(cell, expected):
    assert _parse_date(cell) == expected


@pytest.mark.parametrize("cell", ["Sector", "", "Outstanding as on", "%", "2026"])
def test_parse_date_rejects_non_dates(cell):
    assert _parse_date(cell) is None


@pytest.mark.parametrize("cell,expected", [
    ("1,63,55,330", 16355330.0),
    (16813934.78155797, 16813934.78155797),
    ("-", None), ("..", None), ("", None), ("NA", None), (None, None),
])
def test_num(cell, expected):
    assert _num(cell) == expected


def test_release_date_comes_from_the_filename_stamp():
    url = "https://rbidocs.rbi.org.in/rdocs/content/docs/SIBCSJ26E31082026ENG.xlsx"
    assert _release_date_from_name(url).date() == datetime.date(2026, 8, 31)


# ---------------------------------------------------------------------------
# Slugging
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label,section,slug", [
    ("2.9.1. Fertiliser", "2.9.1", "FERTILISER"),
    ("I. Bank Credit (II + III)", "I", "BANK_CREDIT"),
    # RBI renamed the row mid-archive; both must land on one code.
    ("I. Gross Bank Credit (II + III)", "I", "BANK_CREDIT"),
    ("3.7.1. Wholesale Trade1", "3.7.1", "WHOLESALE_TRADE"),
    ("2.1. Micro and Small1", "2.1", "MICRO_AND_SMALL"),
    ("2. Industry (Micro and Small, Medium and Large )", "2", "INDUSTRY"),
    ("3.9. Non-Banking Financial Companies (NBFCs)2            of which,",
     "3.9", "NON_BANKING_FINANCIAL_COMPANIES"),
    ("4.2. Housing (Including Priority Sector Housing)", "4.2", "HOUSING"),
    ("4.8. Loans against gold jewellery4", "4.8", "LOANS_AGAINST_GOLD_JEWELLERY"),
    ("(x)    Weaker Sections including net PSLC- SF/MF", "x", "WEAKER_SECTIONS"),
    ("(i)     Agriculture and Allied Activities5",
     "i", "AGRICULTURE_AND_ALLIED_ACTIVITIES"),
    # Nested parentheses defeat the gloss-stripper; the alias catches it.
    ("4.3. Advances against Fixed Deposits (Including FCNR              (B), "
     "NRNR Deposits etc.)", "4.3", "ADVANCES_AGAINST_FIXED_DEPOSITS"),
    ("2.18.6. Railways (other than Indian Railways)", "2.18.6", "RAILWAYS"),
])
def test_slug(label, section, slug):
    assert _slug(label) == (section, slug)


# ---------------------------------------------------------------------------
# Statement parsing
# ---------------------------------------------------------------------------

def test_billion_era_is_declined_not_rescaled():
    """The Jun/Jul-2019 files are Rs. billion.

    Parsing them as crore would understate every value 100x, which is far
    worse than not having them -- so the unit line gates the whole sheet.
    """
    rows = [["Statement 1: Deployment of Gross Bank Credit by Major Sector"],
            ["(Rs. billion)"],
            ["Sr.No", "Sector", "Jun. 23, 2017", "Mar. 30, 2018", "Jun.22, 2018"],
            ["I", "Gross Bank Credit", 69279.14, 77302.84, 76948.94]]
    labels, obs = parse_statement(rows, 1)
    assert labels == {}
    assert obs == []


def test_pre_2021_sr_no_layout_is_declined_even_though_it_is_in_crore():
    """Aug-2019 to Dec-2020 is crore, and still a different taxonomy.

    `Agriculture & Allied Activities` / `Micro & Small` slug differently
    from the current `... and ...` spellings, `Aviation` does not exist
    yet, and section 3.5 means Professional Services rather than
    Aviation. Reading it would manufacture parallel half-series.
    """
    rows = [["Statement 1: Deployment of Gross Bank Credit by Major Sectors"],
            ["(Rs.crore)"],
            [],
            ["Sr.No", "Sector", "Aug 31, 2018", "Mar.29, 2019", "Aug 30, 2019"],
            [],
            ["1", "Agriculture & Allied Activities", 1041879, 1111300, 1113026],
            ["2.1", "Micro & Small", 366411, 375505, 358885]]
    labels, obs = parse_statement(rows, 1)
    assert labels == {}
    assert obs == []


@pytest.mark.parametrize("unit_row_index", [1, 2])
def test_unit_line_is_found_wherever_it_sits(unit_row_index):
    """Two 2019 releases shift the unit line down a row.

    Indexing row 1 blindly reads those as "unit unknown" and drops the
    whole release.
    """
    rows = [["Statement 1: Deployment of Gross Bank Credit by Major Sectors"]]
    while len(rows) < unit_row_index:
        rows.append([])
    rows.append(["", "(Rs. Crore)"])
    rows += [DATES_B, ["1. Agriculture and Allied Activities", 1, 2, 3, 4, 5]]
    labels, _ = parse_statement(rows, 1)
    assert set(labels) == {"AGRICULTURE_AND_ALLIED_ACTIVITIES"}


def test_header_dates_and_values_line_up():
    labels, obs = parse_statement(_sheet(
        DATES_B,
        ["1. Agriculture and Allied Activities", 2156319.92, 2287060.09,
         2313847.27, 2644249.77, 2706651.98],
    ), 1)
    assert set(labels) == {"AGRICULTURE_AND_ALLIED_ACTIVITIES"}
    assert dict((d, v) for s, d, v in obs) == {
        datetime.date(2024, 7, 26): 2156319.92,
        datetime.date(2025, 3, 21): 2287060.09,
        datetime.date(2025, 7, 25): 2313847.27,
        datetime.date(2026, 3, 31): 2644249.77,
        datetime.date(2026, 7, 31): 2706651.98,
    }


def test_section_42_aggregate_rows_are_not_emitted_here():
    """Rows I-III are a different universe from the sectors below them.

    RBI's own note says bank / food / non-food credit come from the
    fortnightly Section-42 return covering ALL scheduled commercial
    banks, while the sectoral rows come from the SIBC return covering
    ~41 select banks. They belong to `INDIA.SCB_BUSINESS.*`, not here,
    or this prefix silently mixes two universes.
    """
    labels, _ = parse_statement(_sheet(
        DATES_A,
        ["I. Bank Credit (II + III)", 1, 2, 3, 4, 5],
        ["II. Food Credit", 1, 2, 3, 4, 5],
        ["III. Non-food Credit", 1, 2, 3, 4, 5],
        DATES_B,
        ["1. Agriculture and Allied Activities", 1, 2, 3, 4, 5],
    ), 1)
    assert set(labels) == {"AGRICULTURE_AND_ALLIED_ACTIVITIES"}


def test_the_older_gross_bank_credit_spelling_is_also_excluded():
    labels, _ = parse_statement(_sheet(
        DATES_B, ["I. Gross Bank Credit (II + III)", 1, 2, 3, 4, 5],
    ), 1)
    assert labels == {}


def test_second_header_row_rebinds_the_columns_beneath_it():
    """Statement 1 re-declares its dates before the sector block.

    The two blocks disagree on the FY anchor -- `4.Apr,2025` for the
    credit aggregates, `21.Mar,2025` for the sectors -- so a parser that
    latched the first header would date every sector row wrongly.
    """
    _, obs = parse_statement(_sheet(
        DATES_A,
        ["4.1. Consumer Durables", 1.0, 2.0, 3.0, 4.0, 5.0],
        DATES_B,
        ["1. Agriculture and Allied Activities", 10.0, 20.0, 30.0, 40.0, 50.0],
    ), 1)
    by_slug = {}
    for slug, d, v in obs:
        by_slug.setdefault(slug, {})[d] = v
    assert datetime.date(2025, 4, 4) in by_slug["CONSUMER_DURABLES"]
    assert datetime.date(2025, 3, 21) in by_slug["AGRICULTURE_AND_ALLIED_ACTIVITIES"]
    assert datetime.date(2025, 4, 4) not in by_slug["AGRICULTURE_AND_ALLIED_ACTIVITIES"]


def test_generic_others_rows_are_qualified_by_parent():
    """Statement 2 carries three `Others` rows under three parents."""
    rows = [["Statement 2: Industry-wise Deployment of Gross Bank Credit"],
            CRORE, ["Industry", "Outstanding"], DATES_B,
            ["2.2. Food Processing", 1, 2, 3, 4, 5],
            ["2.2.4. Others", 1, 2, 3, 4, 5],
            ["2.9. Chemicals and Chemical Products", 1, 2, 3, 4, 5],
            ["2.9.4. Others", 1, 2, 3, 4, 5],
            ["2.14. All Engineering", 1, 2, 3, 4, 5],
            ["2.14.2. Others", 1, 2, 3, 4, 5]]
    labels, _ = parse_statement(rows, 2)
    assert "FOOD_PROCESSING_OTHERS" in labels
    assert "CHEMICALS_AND_CHEMICAL_PRODUCTS_OTHERS" in labels
    assert "ALL_ENGINEERING_OTHERS" in labels
    assert "OTHERS" not in labels


def test_priority_sector_memo_is_namespaced():
    """The memo block restates sectors on the priority-sector definition.

    Unqualified, `(i) Agriculture` and `(iv) Housing` would overwrite the
    all-bank `1. Agriculture` and `4.2. Housing` rows with a different
    concept carrying the same code.
    """
    labels, _ = parse_statement(_sheet(
        DATES_B,
        ["1. Agriculture and Allied Activities", 1, 2, 3, 4, 5],
        ["4.2. Housing (Including Priority Sector Housing)", 1, 2, 3, 4, 5],
        ["Priority Sector (Memo)"],
        ["(i)     Agriculture and Allied Activities5", 6, 7, 8, 9, 10],
        ["(iv)   Housing", 6, 7, 8, 9, 10],
    ), 1)
    assert set(labels) == {
        "AGRICULTURE_AND_ALLIED_ACTIVITIES", "HOUSING",
        "PRIORITY_SECTOR_AGRICULTURE_AND_ALLIED_ACTIVITIES",
        "PRIORITY_SECTOR_HOUSING",
    }


def test_statement_2_industry_total_is_skipped_as_a_restatement():
    """`Industries (2.1 to 2.19)` is Statement 1's `2. Industry` again."""
    rows = [["Statement 2: Industry-wise Deployment of Gross Bank Credit"],
            CRORE, ["Industry", "Outstanding"], DATES_B,
            ["2.1. Mining and Quarrying (incl. Coal)", 1, 2, 3, 4, 5],
            ["Industries (2.1 to 2.19)", 9, 9, 9, 9, 9]]
    labels, _ = parse_statement(rows, 2)
    assert set(labels) == {"MINING_AND_QUARRYING"}


def test_notes_block_terminates_parsing():
    labels, _ = parse_statement(_sheet(
        DATES_B,
        ["1. Agriculture and Allied Activities", 1, 2, 3, 4, 5],
        ["Notes: (1) Data are provisional."],
        ["1 Wholesale trade includes food procurement credit", 1, 2, 3, 4, 5],
    ), 1)
    assert set(labels) == {"AGRICULTURE_AND_ALLIED_ACTIVITIES"}


def test_rows_with_no_numeric_cells_produce_nothing():
    labels, obs = parse_statement(_sheet(
        DATES_B,
        ["5. Priority Sector (Memo)", "-", "-", "-", "-", "-"],
    ), 1)
    assert labels == {}
    assert obs == []


def test_a_real_collision_raises_rather_than_merging():
    """Two RBI rows landing on one code must fail, not silently merge."""
    rows = [["Statement 2: Industry-wise Deployment of Gross Bank Credit"],
            CRORE, ["Industry", "Outstanding"], DATES_B,
            ["2.1. Widgets", 1, 2, 3, 4, 5],
            ["2.2. Widgets", 6, 7, 8, 9, 10]]
    with pytest.raises(ValueError, match="slug collision"):
        parse_statement(rows, 2)


# ---------------------------------------------------------------------------
# Which of a month's five candidate columns wins
# ---------------------------------------------------------------------------

resolve_months = _mod.resolve_months

APR = datetime.date(2025, 4, 1)
JUL = datetime.date(2025, 7, 1)


def test_month_end_beats_the_financial_year_anchor():
    """The FY2024-25 anchor prints as `4.Apr,2025` and is not April.

    The April-2025 release reports `18.Apr,2025`. Letting the anchor win
    would replace April's month-end level with a financial-year-end one
    that belongs to March.
    """
    out = resolve_months([
        # the April-2025 release's own print
        ("MEDIUM", datetime.date(2025, 4, 18), APR, 365377.87),
        # the same month as an FY anchor inside a much later release
        ("MEDIUM", datetime.date(2025, 4, 4), datetime.date(2026, 7, 1), 363245.02),
    ])
    assert out[("MEDIUM", APR)][0] == datetime.date(2025, 4, 18)
    assert out[("MEDIUM", APR)][2] == 365377.87


def test_a_restatement_of_the_same_date_supersedes_the_first_print():
    """RBI's own YoY uses the year-ago figure as restated today.

    Services printed 5,113,966 for 25-Jul-2025 in the July-2025 release
    and 5,040,440 for the same date a year later. Keeping the first
    print reproduces a 21.2% YoY against RBI's published 22.9%.
    """
    out = resolve_months([
        ("SERVICES", datetime.date(2025, 7, 25), JUL, 5113965.74),
        ("SERVICES", datetime.date(2025, 7, 25), datetime.date(2026, 7, 1),
         5040439.96),
    ])
    assert out[("SERVICES", JUL)][2] == 5040439.96


def test_order_of_arrival_does_not_change_the_winner():
    args = [
        ("SERVICES", datetime.date(2025, 7, 25), datetime.date(2026, 7, 1), 2.0),
        ("SERVICES", datetime.date(2025, 7, 25), JUL, 1.0),
    ]
    assert resolve_months(args) == resolve_months(list(reversed(args)))


def test_each_month_of_each_series_resolves_to_exactly_one_value():
    out = resolve_months([
        ("A", datetime.date(2025, 7, 25), JUL, 1.0),
        ("A", datetime.date(2025, 7, 31), JUL, 2.0),
        ("B", datetime.date(2025, 7, 25), JUL, 3.0),
    ])
    assert set(out) == {("A", JUL), ("B", JUL)}
    assert out[("A", JUL)][2] == 2.0
