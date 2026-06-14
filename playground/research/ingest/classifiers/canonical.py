"""Canonical vocabularies + shared helpers used by per-vendor classifiers.

Two sets of constants live here:

* ``ASSET_CLASS_*`` — the controlled vocab written to
  ``research.dim_report.asset_class``. Every vendor classifier must
  return one of these (or ``""``).

* ``REGION_*`` — broad-region labels emitted as ``Tag('region', ...)``.
  Mostly used by classifiers that get a free-text region from the
  vendor (Nomura's ``regions[]``, Barclays' analyst coverageRegions);
  HSBC/ANZ regions are usually derived from publication_type at the
  vendor module.

The country-code dimension is :class:`dbo.dim_country` (2-char codes).
Classifiers emit a 2-char code and the writer resolves it to the FK.
"""
from __future__ import annotations

from collections.abc import Iterable

# ───── Asset-class vocab (single-valued on dim_report.asset_class) ─────
# Keep these short — varchar(30). Add new values cautiously: every
# classifier should agree on the mapping.
ASSET_CLASS_EQUITY      = "EQUITY"
ASSET_CLASS_FX          = "FX"
ASSET_CLASS_RATES       = "RATES"
ASSET_CLASS_CREDIT      = "CREDIT"
ASSET_CLASS_COMMODITIES = "COMMODITIES"
ASSET_CLASS_MACRO       = "MACRO"
ASSET_CLASS_ESG         = "ESG"
ASSET_CLASS_STRATEGY    = "STRATEGY"   # cross-asset, allocation, thematic

ASSET_CLASSES: tuple[str, ...] = (
    ASSET_CLASS_EQUITY, ASSET_CLASS_FX, ASSET_CLASS_RATES,
    ASSET_CLASS_CREDIT, ASSET_CLASS_COMMODITIES, ASSET_CLASS_MACRO,
    ASSET_CLASS_ESG, ASSET_CLASS_STRATEGY,
)

# ───── Region tag values (Tag('region', ...)) ────────────────────────────
# Broad geographic buckets. Per-country still emits Tag('country', 'US').
REGION_AMERICAS = "americas"
REGION_EMEA     = "emea"
REGION_APAC     = "apac"
REGION_LATAM    = "latam"   # subset of americas — emitted when known
REGION_GLOBAL   = "global"


# ───── Region heuristics for free-text labels ────────────────────────────
# Vendor region labels are inconsistent ("Europe", "EMEA", "AsiaExJapan",
# "Asia ex-Japan", "EM Asia"). Lower-case substring match keeps this
# dumb-but-robust. Order matters: more specific first.
_REGION_LOWER_RULES: tuple[tuple[str, str], ...] = (
    ("latam",         REGION_LATAM),
    ("latin",         REGION_LATAM),
    ("americas",      REGION_AMERICAS),
    ("united states", REGION_AMERICAS),
    ("north america", REGION_AMERICAS),
    ("emea",          REGION_EMEA),
    ("europe",        REGION_EMEA),
    ("middle east",   REGION_EMEA),
    ("africa",        REGION_EMEA),
    ("apac",          REGION_APAC),
    ("asia",          REGION_APAC),
    ("japan",         REGION_APAC),
    ("china",         REGION_APAC),
    ("global",        REGION_GLOBAL),
    ("world",         REGION_GLOBAL),
)


def normalize_region(label: str | None) -> str | None:
    """Map a vendor's free-text region label to our broad bucket.

    Returns ``None`` when no rule matches — caller should emit no
    region tag rather than guess.

        >>> normalize_region("Asia ex-Japan")
        'apac'
        >>> normalize_region("EMEA")
        'emea'
        >>> normalize_region("")  # returns None
    """
    if not label:
        return None
    lower = label.strip().lower()
    if not lower:
        return None
    for substr, region in _REGION_LOWER_RULES:
        if substr in lower:
            return region
    return None


# region tag value → dim_report.region column bucket. Tags arrive both
# pre-normalized (apac/emea/...) and as raw vendor labels (AsiaPacific,
# NorthAmerica, Japan, ...) depending on the vendor classifier — map both.
_REGION_TAG_TO_COLUMN: dict[str, str] = {
    REGION_APAC:     REGION_APAC,
    REGION_EMEA:     REGION_EMEA,
    REGION_AMERICAS: REGION_AMERICAS,
    REGION_LATAM:    REGION_LATAM,
    REGION_GLOBAL:   REGION_GLOBAL,
    "AsiaPacific":   REGION_APAC,
    "Japan":         REGION_APAC,
    "Australasia":   REGION_APAC,
    "NorthAmerica":  REGION_AMERICAS,
    "LatinAmerica":  REGION_LATAM,
    "Africa":        REGION_EMEA,
    "MiddleEast":    REGION_EMEA,
}


def region_from_tags(tags: Iterable[tuple[str, str]]) -> str:
    """Collapse a report's region tags into the single dim_report.region value.

    ``tags`` is the (category, value) pairs as written to map_report_tag.
    Region lives multi-valued in tags but single-valued on the column, so:
    a lone 'global' stays 'global'; an explicit regional bucket wins over a
    co-occurring 'global'; two or more distinct regional buckets collapse to
    'global'. Returns ``""`` when no region tag is present (column stays
    blank — never guess).

        >>> region_from_tags([("region", "apac"), ("author", "X")])
        'apac'
        >>> region_from_tags([("region", "apac"), ("region", "global")])
        'apac'
        >>> region_from_tags([("region", "apac"), ("region", "emea")])
        'global'
        >>> region_from_tags([("theme", "rates")])
        ''
    """
    buckets = {
        _REGION_TAG_TO_COLUMN[value]
        for category, value in tags
        if category == TAG_REGION and value in _REGION_TAG_TO_COLUMN
    }
    if not buckets:
        return ""
    regional = buckets - {REGION_GLOBAL}
    if len(regional) == 1:
        return next(iter(regional))
    return REGION_GLOBAL


# ───── Country code helpers ──────────────────────────────────────────────
# Common vendor strings → 2-char codes from dbo.dim_country.
# Pseudo-countries: WW=Worldwide, XX=Non-sovereign/metals, EU=Eurozone.
_COUNTRY_NAME_MAP: dict[str, str] = {
    "united states":  "US",
    "us":             "US",
    "usa":            "US",
    "united kingdom": "UK",
    "uk":             "UK",
    "great britain":  "UK",
    "eurozone":       "EU",
    "europe":         "EU",
    "japan":          "JP",
    "china":          "CN",
    "india":          "IN",
    "australia":      "AU",
    "new zealand":    "NZ",
    "singapore":      "SG",
    "hong kong":      "HK",
    "south korea":    "KR",
    "korea":          "KR",
    "taiwan":         "TW",
    "indonesia":      "ID",
    "malaysia":       "MY",
    "thailand":       "TH",
    "philippines":    "PH",
    "vietnam":        "VN",
    "brazil":         "BR",
    "mexico":         "MX",
    "argentina":      "AR",
    "chile":          "CL",
    "colombia":       "CO",
    "germany":        "DE",
    "france":         "FR",
    "italy":          "IT",
    "spain":          "ES",
    "switzerland":    "CH",
    "norway":         "NO",
    "sweden":         "SE",
    "denmark":        "DK",
    "russia":         "RU",
    "turkey":         "TR",
    "south africa":   "ZA",
    "uae":            "AE",
    "global":         "WW",
    "worldwide":      "WW",
}


def normalize_country(label: str | None) -> str | None:
    """Map a free-text country/region label to a 2-char dim_country code.

    Returns ``None`` when no match — never guesses. The writer will
    leave ``country_id`` NULL on that report.

        >>> normalize_country("Japan")
        'JP'
        >>> normalize_country("United States")
        'US'
        >>> normalize_country("South Korea")
        'KR'
    """
    if not label:
        return None
    lower = label.strip().lower()
    if not lower:
        return None
    # Exact-match table is fastest path
    direct = _COUNTRY_NAME_MAP.get(lower)
    if direct is not None:
        return direct
    # Two-char codes pass through if they look like one
    if len(lower) == 2 and lower.isalpha():
        return lower.upper()
    return None


# ───── Tag-category constants ────────────────────────────────────────────
# Match research.dim_tag.tag_category (varchar(30)). Keep these short.
TAG_TICKER         = "ticker"
TAG_COMPANY        = "company"
TAG_INDUSTRY       = "industry"
TAG_REGION         = "region"
TAG_COUNTRY        = "country"
TAG_THEME          = "theme"
TAG_FORMAT         = "format"
TAG_DISCIPLINE     = "discipline"
TAG_VENDOR_PUBTYPE = "vendor_pubtype"   # raw, never lossy
TAG_AUTHOR         = "author"


# ───── Vendor display names (for context strings) ────────────────────────
VENDOR_DISPLAY: dict[str, str] = {
    "anz":      "ANZ Research",
    "barclays": "Barclays Research",
    "bnp":      "BNP Paribas Markets360",
    "bofa":     "BofA Securities Research",
    "citi":     "Citi Velocity Research",
    "db":       "Deutsche Bank Research",
    "goldman":  "Goldman Sachs Research",
    "hsbc":     "HSBC Global Research",
    "jpm":      "J.P. Morgan Markets",
    "ms":       "Morgan Stanley Research",
    "nomura":   "Nomura Research",
    "socgen":   "Societe Generale Research",
    "stanc":    "Standard Chartered Research",
    "ubs":      "UBS Neo",
    "westpac":  "Westpac IQ",
}
