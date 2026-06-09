"""Bloomberg CSV rates extractor — reads R-pipeline IRS + OIS PAR CSVs from Z:\\.

Source CSVs are written by the multi-PC R fetcher described in
``docs/admin/vendors/bbg/``. Format (per curve, e.g. ``IRS/AUD-BBSW-3M/PAR/IRS_PAR_AUD-BBSW-3M.csv``):

    Row 0: Ticker,BBSW 3M INDEX,ADSWFQ BGN Curncy,ADSWIQ BGN Curncy,...
    Row 1: <varies: Tenor|Term|Ticker|Tickers|Date|Dates|rv Iden>,IRS_PAR_AUQ_SPOT_3M,IRS_PAR_AUQ_SPOT_6M,...
    Row 2: Maturity,0.25,0.5,...
    Row 3+: dd/mm/yyyy,<spot>,<col2>,...

Format quirks (audited 2026-04-25 across all 47 in-scope curves; see
plan in ``docs/rates/rates_bbg.md``):

* **Row-1 first cell varies**: 7 distinct labels observed — never
  ``assert == "Tenor"``. Row 1 is treated as the tenor-label source
  regardless of what its first cell says.
* **Tenor-label ccy prefix varies wildly**: AUQ, EUQ, DT6, INR, ILS,
  EUS, SOFR, JPY, JPY_PAR_OIS (mixed), even hardcoded EUR in PLN-WIBOR-6M.
  We extract via trailing ``_TENOR`` regex (``_3M``, ``_18M``, ``_ON``,
  ``_30Y``) and never rely on the prefix.
* **Folder name owns the ccy**, not tenor labels. Same bug class as
  the FX EUR/GBP folder mislabel — PLN-WIBOR-6M's tenor labels say
  ``IRS_PAR_EUR_*`` but underlying tickers are PZSW (Polish Zloty SWap).
* **Mixed label schemes within ONE file**: JPY-TONAR-ON-JSCC has both
  ``JPY_PAR_OIS_SPOT_1D`` (short tenors) and ``OIS_PAR_JPY_SPOT_1Y``
  (long tenors). Trailing-regex extraction handles both.
* **Duplicate tenor columns**: USD-LIBOR-3M has two ``IRS_PAR_USD_SPOT_6M``
  cols (fixings vs swap). Deduped by ``keep='last'``.
* **`-ori.csv` filename suffix**: only USD-LIBOR-3M; allowed by file glob.
* **Negative rates**: CHF-SARON-ON spot has negative values — passed
  through unchanged.

Output DataFrame columns (matches the existing
``CitiVelocityRatesExtractor`` shape per ``rates/schema.py``):
    [ts, ccy, curve, quote, tenor, value]

Plus stamped: `vendor_code='BBG'` and `frequency_code` (caller chooses
SNAPSHOT for live ingest, DAILY for historical backfill).

**HARD RULE — Z:\\BBG\\ is read-only.** This module performs NO
file moves, renames, deletes, or writes. Only ``glob``, ``stat``,
``open(..., "r")``, ``pd.read_csv``. See plan + lock-in test
``tests/unit/test_vendors/test_bbg_rates_snapshot_no_move.py``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import structlog

from imdr.bbg.csv_parser import parse_3hdr_csv

log = structlog.get_logger(__name__)


# ── Tenor handling ────────────────────────────────────────────────────


# Match trailing ``_TENOR`` where TENOR is e.g. ``3M``, ``18M``, ``1D``,
# ``ON``, ``30Y``, ``50Y``. Anchored to end of label so prefix is ignored.
_TENOR_RE = re.compile(r"_(?P<t>\d+[YMWDymwd]|ON)$", re.IGNORECASE)

# Tenor canonicalization — mirror IMDR rates.yml conventions.
# ``12M`` → ``1Y`` (rates.yml uses 1Y, never 12M).
_TENOR_NORMALIZE: dict[str, str] = {
    "12M": "1Y",
}

# Tenor universe accepted by IMDR (union of OIS + IBOR plus ON/35Y/40Y/50Y
# discovered in BBG curves). Any tenor outside this set is logged + dropped.
_ALLOWED_TENORS: set[str] = {
    # Sub-month
    "ON", "1D", "1W", "2W", "3W",
    # Months 1-11
    "1M", "2M", "3M", "4M", "5M", "6M", "7M", "8M", "9M", "10M", "11M",
    # Year 1 + intra-year
    "1Y", "15M", "18M", "21M",
    # Years 2-12
    "2Y", "3Y", "4Y", "5Y", "6Y", "7Y", "8Y", "9Y", "10Y", "11Y", "12Y",
    # Long end
    "15Y", "18Y", "20Y", "25Y", "30Y", "35Y", "40Y", "50Y",
}


def extract_tenor(alias: str) -> str | None:
    """Pull canonical tenor from a BBG row-1 label. None if not extractable.

    Examples
    --------
    >>> extract_tenor("IRS_PAR_AUQ_SPOT_3M")
    '3M'
    >>> extract_tenor("OIS_PAR_SOFR_SPOT_1D")
    '1D'
    >>> extract_tenor("OIS_PAR_CHF_SPOT_ON")
    'ON'
    >>> extract_tenor("JPY_PAR_OIS_SPOT_1Y")
    '1Y'
    >>> extract_tenor("OIS_PAR_JPY_SPOT_30Y")
    '30Y'
    >>> extract_tenor("IRS_PAR_DT6_SPOT_12M")
    '1Y'
    """
    if not isinstance(alias, str):
        return None
    m = _TENOR_RE.search(alias.strip())
    if not m:
        return None
    raw = m.group("t").upper()
    return _TENOR_NORMALIZE.get(raw, raw)


# ── Folder-name → curve-identity parser ───────────────────────────────


# Folder name formats (one per BBG domain):
#
# IRS    `{CCY}-{INDEX}-{RESET}`            AUD-BBSW-3M, KRO-91D_CD-3M
# OIS    `{CCY}-{INDEX}-ON[-{CH}]`          USD-SOFR-ON, JPY-TONAR-ON-JSCC,
#                                            AUD-AONIA.MD-ON
# BASIS  `{LEG1}.{LEG2}` (each leg full)    SGD-SOR-ON.USD-SOFR-ON,
#                                            ILS-SHIR-ON.USD-SOFR-ON
# CCS    `{CCY}-FIXED.{LEG2}`               CNH-FIXED.USD-SOFR-ON
#
# All values stored in `rates.fact_observation`:
#   IRS, OIS, CCS rows  → quote='par',   value in PERCENT
#   BASIS rows          → quote='basis', value in BASIS POINTS
# Curve-type taxonomy: 'ibor', 'rfr', 'basis', 'ccs' (see schemas/rates.py).


@dataclass(frozen=True)
class BBGRatesSourceFile:
    """Resolved source file for one BBG curve (IRS / OIS / BASIS / CCS)."""

    path: Path                # absolute CSV path
    folder: str               # raw folder name
    kind: str                 # "IRS" | "OIS" | "BASIS" | "CCS"
    ccy: str                  # leg-1 ccy — taken from folder name (NOT tenor label)
    curve: str                # IMDR-canonical curve code
    curve_type: str           # "ibor" | "rfr" | "basis" | "ccs"
    obs_ts: datetime          # CSV mtime in UTC


def _strip_on_suffix(rest: str) -> str:
    """``SOFR-ON`` → ``SOFR``; ``TONAR-ON-JSCC`` → ``TONAR_JSCC``."""
    if rest.endswith("-ON"):
        return rest[:-3]
    rest = re.sub(r"-ON-", "_", rest, count=1)
    if rest.endswith("-ON"):
        return rest[:-3]
    return rest


def parse_bbg_rates_folder(kind: str, folder: str) -> tuple[str, str, str]:
    """Parse a BBG folder name into ``(ccy, curve, curve_type)``.

    See module-level taxonomy comment for the four folder formats.
    Examples:
        ("IRS",   "AUD-BBSW-3M")              → ("AUD", "BBSW_3M",         "ibor")
        ("IRS",   "KRO-91D_CD-3M")            → ("KRO", "91D_CD_3M",       "ibor")
        ("OIS",   "USD-SOFR-ON")              → ("USD", "SOFR",            "rfr")
        ("OIS",   "JPY-TONAR-ON-JSCC")        → ("JPY", "TONAR_JSCC",      "rfr")
        ("OIS",   "AUD-AONIA.MD-ON")          → ("AUD", "AONIA_MD",        "rfr")
        ("BASIS", "SGD-SOR-ON.USD-SOFR-ON")   → ("SGD", "BASIS_SOR_VS_SOFR","basis")
        ("BASIS", "ILS-SHIR-ON.USD-SOFR-ON")  → ("ILS", "BASIS_SHIR_VS_SOFR","basis")
        ("CCS",   "CNH-FIXED.USD-SOFR-ON")    → ("CNH", "CCS_VS_SOFR",     "ccs")
    """
    if kind in ("BASIS", "CCS"):
        # Two-leg format: '{leg1}.{leg2}'. Each leg has its own dashes.
        leg_parts = folder.split(".", 1)
        if len(leg_parts) != 2:
            raise ValueError(
                f"BASIS/CCS folder must contain a dot separator: {folder!r}"
            )
        leg1, leg2 = leg_parts
        # leg1 starts with the ccy, e.g. ``SGD-SOR-ON`` or ``CNH-FIXED``
        leg1_parts = leg1.split("-", 1)
        if len(leg1_parts) != 2:
            raise ValueError(f"Cannot parse leg1: {leg1!r}")
        ccy = leg1_parts[0].upper()
        # leg2's INDEX (the rate name within USD-SOFR-ON → SOFR)
        leg2_idx = leg2.split("-")[1] if "-" in leg2 else leg2
        leg2_idx = leg2_idx.upper()
        if kind == "BASIS":
            # leg1 index = the floating rate of the basis pair (e.g. SOR, SHIR)
            leg1_idx = leg1.split("-")[1] if "-" in leg1 else leg1
            curve = f"BASIS_{leg1_idx.upper()}_VS_{leg2_idx}"
            return ccy, curve, "basis"
        else:  # CCS
            # leg1's "INDEX" is the marker (e.g. FIXED) — ignored; ref is leg2
            curve = f"CCS_VS_{leg2_idx}"
            return ccy, curve, "ccs"

    # IRS / OIS: single-leg format ``{CCY}-{REST}``
    parts = folder.split("-", 1)
    if len(parts) != 2:
        raise ValueError(f"Cannot parse folder name: {folder!r}")
    ccy = parts[0].upper()
    rest = parts[1]
    curve_type = "rfr" if kind == "OIS" else "ibor"
    if curve_type == "rfr":
        rest = _strip_on_suffix(rest)
    # else IRS: keep trailing reset tenor — disambiguates 3M vs 6M variants
    curve = rest.replace("-", "_").replace(".", "_")
    return ccy, curve, curve_type


# ── CSV parsing ───────────────────────────────────────────────────────


def parse_bbg_rates_csv(path: Path) -> pd.DataFrame:
    """Parse one BBG rates PAR CSV into a long-form DataFrame.

    Thin wrapper over :func:`imdr.bbg.csv_parser.parse_3hdr_csv`.
    Row 1 col 0 in rates CSVs varies wildly across curves (7 distinct
    labels observed), so we skip header validation and treat row 1 as
    the tenor-alias source regardless of its first-cell label.
    """
    return parse_3hdr_csv(path, validate_headers=False)


# ── Discovery ─────────────────────────────────────────────────────────


# Folder-name suffixes / patterns we explicitly skip during discovery.
_SKIP_FOLDERS: set[str] = {
    "MS",                     # cross-curve aggregate
    "USD-CPURNSA",            # inflation, separate beast
    "AUD-AONIA.MD-ON",        # FOMC/RBA meeting forwards (different format)
    "USD-FEDFUNDS.MD-ON",
    "AUD-BBSW.IAUS-3M",       # empty PAR/ folder
}


def discover_bbg_rates_files(
    bbg_root: Path,
    kinds: tuple[str, ...] = ("IRS", "OIS", "BASIS", "CCS"),
    fresh_only_age_days: int | None = None,
) -> list[BBGRatesSourceFile]:
    """Walk Z:\\...\\BBG_mirror\\{IRS,OIS,BASIS,CCS} and resolve PAR CSV files.

    Parameters
    ----------
    bbg_root : Path
        ``Z:\\Business\\Research\\Dashboard\\DataSources\\BBG_mirror``
    kinds : tuple of "IRS", "OIS", "BASIS", and/or "CCS"
        Domain trees to walk. Default: all four.
    fresh_only_age_days : int or None
        If set, only return files with mtime newer than this many days.
        ``None`` = include all.

    Returns
    -------
    list of BBGRatesSourceFile
    """
    out: list[BBGRatesSourceFile] = []
    now = datetime.now(timezone.utc)

    for kind in kinds:
        domain_root = bbg_root / kind
        if not domain_root.exists():
            log.warning("bbg_rates_domain_missing", kind=kind, path=str(domain_root))
            continue

        for curve_dir in sorted(domain_root.iterdir()):
            if not curve_dir.is_dir():
                continue
            folder = curve_dir.name
            if folder in _SKIP_FOLDERS or "_DEL" in folder or "Backup" in folder:
                continue

            par_dir = curve_dir / "PAR"
            if not par_dir.exists():
                log.debug("bbg_rates_no_par_dir", folder=folder)
                continue

            # Find the canonical PAR CSV. Allow ``-ori`` suffix (USD-LIBOR-3M).
            # Reject ``Copy``, ``old``, ``new`` variants.
            candidates = [
                p for p in par_dir.glob(f"{kind}_PAR_*.csv")
                if "Copy" not in p.name
                and "-old" not in p.name
                and "-new" not in p.name
            ]
            if not candidates:
                log.debug("bbg_rates_no_csv", folder=folder)
                continue

            # Prefer canonical name (no -ori) if multiple
            preferred = next(
                (p for p in candidates if p.stem == f"{kind}_PAR_{folder}"),
                candidates[0],
            )

            mtime = datetime.fromtimestamp(preferred.stat().st_mtime, tz=timezone.utc)
            if fresh_only_age_days is not None:
                age_days = (now - mtime).days
                if age_days > fresh_only_age_days:
                    continue

            try:
                ccy, curve, curve_type = parse_bbg_rates_folder(kind, folder)
            except ValueError as e:
                log.warning("bbg_rates_folder_parse_failed",
                            folder=folder, error=str(e))
                continue

            out.append(BBGRatesSourceFile(
                path=preferred,
                folder=folder,
                kind=kind,
                ccy=ccy,
                curve=curve,
                curve_type=curve_type,
                obs_ts=mtime,
            ))

    return out


# ── Extractor ─────────────────────────────────────────────────────────


# Default DataFrame columns (matches CitiVelocityRatesExtractor output)
_OUTPUT_COLUMNS = ["ts", "ccy", "curve", "quote", "tenor", "value"]


class BloombergCSVRatesExtractor:
    """Extract rates data from BBG R-pipeline PAR CSVs.

    Output DataFrame matches `rates/schema.py:COLUMNS` plus stamped
    ``vendor_code='BBG'`` and ``frequency_code`` (caller-controlled).

    Two read modes:
      - ``mode='live'`` (default) — keeps ONLY the latest data row (most
        recent obs_date) per curve. Each output row's ``ts`` = file mtime
        UTC. Used by the snapshot + daily live pipelines.
      - ``mode='historical'`` — keeps ALL data rows from each CSV (full
        accumulator history). Each output row's ``ts`` = midnight UTC of
        its own obs_date. Used by the one-shot historical backfill.

    Both modes share parsing, tenor extraction, dedupe, and quote
    stamping — only the row scope + ts assignment differ.
    """

    def __init__(self, mode: str = "live") -> None:
        if mode not in ("live", "historical"):
            raise ValueError(f"mode must be 'live' or 'historical', got {mode!r}")
        self._mode = mode
        self._errors: list[dict] = []

    @property
    def errors(self) -> list[dict]:
        return self._errors

    def extract(self, source_files: list[BBGRatesSourceFile]) -> pd.DataFrame:
        """Read every file, concat into one wide DataFrame."""
        if not source_files:
            return pd.DataFrame(columns=_OUTPUT_COLUMNS)

        frames: list[pd.DataFrame] = []
        for src in source_files:
            try:
                df = self._extract_one(src)
                if not df.empty:
                    frames.append(df)
            except Exception as e:
                self._errors.append({
                    "folder": src.folder,
                    "path": str(src.path),
                    "error": str(e),
                })
                log.exception("bbg_rates_extract_failed", folder=src.folder)

        if not frames:
            return pd.DataFrame(columns=_OUTPUT_COLUMNS)
        return pd.concat(frames, ignore_index=True)

    def _extract_one(self, src: BBGRatesSourceFile) -> pd.DataFrame:
        long_df = parse_bbg_rates_csv(src.path)
        if long_df.empty:
            return pd.DataFrame()

        # Map row-1 label → canonical tenor; drop unrecognised
        long_df["tenor"] = long_df["tenor_alias"].map(extract_tenor)
        unknown = long_df[long_df["tenor"].isna()]["tenor_alias"].unique()
        if len(unknown):
            log.warning("bbg_rates_unknown_tenor_alias",
                        folder=src.folder, aliases=list(unknown)[:5])
        long_df = long_df.dropna(subset=["tenor"])
        long_df = long_df[long_df["tenor"].isin(_ALLOWED_TENORS)]
        if long_df.empty:
            return pd.DataFrame()

        # Dedupe duplicate (obs_date, tenor) pairs — covers USD-LIBOR-3M's
        # double 6M cols. ``keep='last'`` matches our FX pattern.
        long_df = long_df.drop_duplicates(
            subset=["obs_date", "tenor"], keep="last"
        )

        if self._mode == "live":
            # Keep only the most recent obs_date in this file (SNAPSHOT/daily-live semantics)
            latest = long_df["obs_date"].max()
            long_df = long_df[long_df["obs_date"] == latest]
            # ts = file mtime UTC (one Timestamp per row, all identical for this fire)
            ts_col = pd.Series(
                pd.DatetimeIndex([pd.Timestamp(src.obs_ts)] * len(long_df), tz="UTC"),
                index=long_df.index,
            )
        else:
            # historical: keep ALL rows. ts = midnight UTC of each row's obs_date.
            ts_col = pd.to_datetime(long_df["obs_date"]).dt.tz_localize("UTC")

        # Quote stamp by curve_type:
        #   IRS, OIS, CCS  → 'par'   (rate in percent)
        #   BASIS          → 'basis' (spread in basis points)
        # Cleaning rule's hard bounds + value-range checks key off `quote`,
        # so this distinction is critical (basis range -300..50 bps).
        quote_value = "basis" if src.curve_type == "basis" else "par"

        out = pd.DataFrame({
            "ts": ts_col.reset_index(drop=True),
            "ccy": src.ccy,
            "curve": src.curve,
            "quote": quote_value,
            "tenor": long_df["tenor"].reset_index(drop=True),
            "value": long_df["value"].astype(float).reset_index(drop=True),
        })
        return out
