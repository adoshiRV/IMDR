"""Bloomberg CSV FX rate extractor — reads R-pipeline outputs from Z:\\.

Source CSVs are written by the multi-PC R fetcher described in
``docs/admin/vendors/bbg/``. Format (per pair, e.g. ``FX/JPY/FX_JPY.csv``):

    Row 0: Ticker,JPY curncy,JPY1W curncy,JPY1M curncy,...
    Row 1: Tenor,FX_JPY_SPOT,FX_JPY_1W,FX_JPY_1M,...
    Row 2: Maturity,0,0.020833333,0.083333333,...
    Row 3+: dd/mm/yyyy,<spot>,<col2>,<col3>,...

The CSVs store **outright levels post-conversion**, not raw forward
points. The R pipeline applies ``outright = spot + points / divisor`` per
ccy. To reconstruct ``fwd_points`` for the IMDR schema we apply the
inverse: ``points = (outright - spot) * divisor``.

Divisor table (from ``FX/bbg_refresh.R`` lines 243-256):
    JPY, THB                                : ÷ 100  (2-dp pairs)
    G10 + metals + MXN + ILS + IDO          : ÷ 10000 (4-dp pairs)
    NDFs (KRW/INR/IDR/PHP/TWD/MYR), HKD,
        CNY family (CNH/CNY/CNO/CCO+ tickers): no conversion (already outright)

The extractor's output DataFrame matches ``CitiVelocityFXRateExtractor``:
columns ``[ts, base_ccy, quote_ccy, tenor, mid_rate, fwd_points]``, plus
``obs_ts`` (carried separately as the file's mtime UTC, since each row of
a single CSV shares the same snapshot moment).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import structlog
import yaml

from imdr.bbg.csv_parser import parse_3hdr_csv

log = structlog.get_logger(__name__)


# ── Conversion lookup ──────────────────────────────────────────────
#
# Maps the BBG output-CSV folder name (== currency code in the BBG
# universe) to the divisor used to recover forward POINTS from the
# stored outright + spot. ``None`` means "tickers are already outright,
# no inverse conversion needed".
#
# Source of truth: ``bbg_points_divisor.yml`` next to this file.
# Loaded once at import time — keep both this loader and the yml file
# in sync with the upstream R script (``FX/bbg_refresh.R``).
_DIVISOR_YML = Path(__file__).parent / "bbg_points_divisor.yml"


def _load_bbg_points_divisor() -> dict[str, float | None]:
    with _DIVISOR_YML.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(
            f"{_DIVISOR_YML}: expected top-level mapping, got {type(raw).__name__}"
        )
    return {str(k): (float(v) if v is not None else None) for k, v in raw.items()}


BBG_POINTS_DIVISOR: dict[str, float | None] = _load_bbg_points_divisor()


# BBG's tenor aliases are stripped of their "FX_{CCY}_" prefix and looked
# up here. Identity passthroughs are handled by the dict-get fallback in
# alias_to_tenor() — only genuine renames live here.
_TENOR_NORMALIZATION: dict[str, str] = {
    "12M": "1Y",  # BBG sometimes labels 12-month forward as 12M
}

# Tenors the IMDR schema understands. Anything not in this set is dropped
# at extract-time with a warning (the BBG tenor grid is wider than ours).
_ALLOWED_TENORS = {
    "SPOT", "ON", "TN", "SN",
    "1W", "2W", "3W",
    "1M", "2M", "3M", "4M", "5M", "6M", "7M", "8M", "9M", "10M", "11M",
    "1Y", "2Y", "5Y", "10Y",
}

# Output column shape — matches CitiVelocityFXRateExtractor (rate_translate.WIDE_COLUMNS)
# plus the BBG-only obs_ts/obs_date columns carried for the snapshot semantic.
_OUTPUT_COLUMNS = [
    "ts", "obs_ts", "obs_date", "base_ccy", "quote_ccy",
    "tenor", "mid_rate", "fwd_points",
]


@dataclass(frozen=True)
class BBGFXSourceFile:
    """Resolved source file for one BBG FX pair."""

    path: Path                      # absolute CSV path
    ccy: str                        # the non-USD leg, e.g. "JPY", "EUR"
    base_ccy: str                   # IMDR base ccy, e.g. "USD" or "EUR"
    quote_ccy: str                  # IMDR quote ccy
    obs_ts: datetime                # CSV mtime in UTC (the snapshot moment)


def resolve_pair_orientation(ccy: str) -> tuple[str, str]:
    """Map a BBG single-ccy code to (base, quote) in IMDR convention.

    BBG always names files by the non-USD leg (e.g. ``FX_EUR.csv``,
    ``FX_JPY.csv``). IMDR's convention follows Citi:
      - EUR, GBP, AUD, NZD are non-USD base → returns (CCY, USD)
      - everything else is USD-base → returns (USD, CCY)
    """
    non_usd_base = {"EUR", "GBP", "AUD", "NZD"}
    if ccy in non_usd_base:
        return (ccy, "USD")
    return ("USD", ccy)


def parse_bbg_csv(path: Path) -> pd.DataFrame:
    """Parse one BBG FX CSV into a long-form DataFrame.

    Thin wrapper over :func:`imdr.bbg.csv_parser.parse_3hdr_csv`
    with header validation enabled — every BBG FX CSV we've ever seen
    has ``"Ticker"`` at row 0 col 0 and ``"Tenor"`` at row 1 col 0.

    Tenor aliases look like ``FX_JPY_SPOT, FX_JPY_1W, FX_JPY_3M, ...``;
    caller applies :func:`alias_to_tenor` to canonicalize them.
    """
    return parse_3hdr_csv(
        path,
        validate_headers=True,
        expected_row0_col0="Ticker",
        expected_row1_col0="Tenor",
    )


def alias_to_tenor(alias: str, ccy: str) -> str | None:
    """Strip ``FX_{ccy}_`` prefix and normalize tenor. Returns None if mismatch.

    Strict prefix match against the file's ccy. Files whose tenor labels
    use a different ccy prefix (e.g. CNO using FX_CNY_*) won't parse —
    rows are skipped with a warning, no silent contamination.
    """
    prefix = f"FX_{ccy}_"
    if not alias.startswith(prefix):
        return None
    raw = alias[len(prefix):].upper()
    return _TENOR_NORMALIZATION.get(raw, raw)


class BloombergCSVFXRateExtractor:
    """Extract FX rates from BBG-pipeline CSVs into IMDR's wide DataFrame shape.

    Output columns: ``[ts, base_ccy, quote_ccy, tenor, mid_rate, fwd_points]``.
    ``ts`` is set to ``obs_ts`` (file mtime UTC) — the same value for every
    row from a given CSV. ``fwd_points`` is reconstructed from ``outright -
    spot`` per pair, then divided by the per-ccy divisor.
    """

    def __init__(self) -> None:
        # Public diagnostic list — pipeline aliases this by reference so
        # partial state survives a mid-extract exception.
        self.errors: list[dict] = []

    def extract(self, source_files: list[BBGFXSourceFile]) -> pd.DataFrame:
        if not source_files:
            return pd.DataFrame(columns=_OUTPUT_COLUMNS)

        rows: list[pd.DataFrame] = []
        for src in source_files:
            try:
                df = self._extract_one(src)
                if not df.empty:
                    rows.append(df)
            except Exception as exc:
                self.errors.append({"path": str(src.path), "error": str(exc)})
                log.exception("bbg_csv_extract_failed", path=str(src.path))

        if not rows:
            return pd.DataFrame(columns=_OUTPUT_COLUMNS)
        return pd.concat(rows, ignore_index=True)

    def _extract_one(self, src: BBGFXSourceFile) -> pd.DataFrame:
        long_df = parse_bbg_csv(src.path)
        if long_df.empty:
            return pd.DataFrame()

        # Map alias → canonical tenor; drop unknowns
        long_df["tenor"] = long_df["tenor_alias"].map(
            lambda a: alias_to_tenor(a, src.ccy)
        )
        unknown = long_df[long_df["tenor"].isna()]["tenor_alias"].unique()
        if len(unknown):
            log.warning(
                "bbg_unknown_tenor_alias",
                ccy=src.ccy,
                aliases=list(unknown)[:5],
            )
        long_df = long_df.dropna(subset=["tenor"])
        long_df = long_df[long_df["tenor"].isin(_ALLOWED_TENORS)]
        if long_df.empty:
            return pd.DataFrame()

        # Single boolean mask — avoid the three repeated `tenor == "SPOT"` scans.
        spot_mask = long_df["tenor"] == "SPOT"
        spot_rows = long_df[spot_mask].copy()
        non_spot = long_df[~spot_mask].copy()

        # No-spot CSVs silently drop every forward (the merge below filters on
        # the missing spot key). Surface it so a malformed upstream file is
        # visible instead of producing zero rows.
        if spot_rows.empty and not non_spot.empty:
            log.warning(
                "bbg_no_spot_row",
                ccy=src.ccy,
                path=str(src.path),
                n_non_spot=len(non_spot),
            )

        # Spot lookup table for the (outright - spot) merge below.
        spot = spot_rows[["obs_date", "value"]].rename(columns={"value": "spot"})

        # Build mid_rate (= outright for forwards, = spot for SPOT row)
        # and fwd_points (= NULL for SPOT, derived for forwards).
        spot_rows["mid_rate"] = spot_rows["value"]
        spot_rows["fwd_points"] = pd.NA

        if not non_spot.empty:
            merged = non_spot.merge(spot, on="obs_date", how="left")
            merged = merged.dropna(subset=["spot"])
            merged["mid_rate"] = merged["value"]
            divisor = BBG_POINTS_DIVISOR.get(src.ccy)
            if divisor is None:
                # Tickers are already outright — no points to recover. Leave NULL.
                merged["fwd_points"] = pd.NA
            else:
                # Round to 6dp — float subtraction yields trailing-precision
                # artefacts (e.g. -52.139999999999986) that overflow the
                # DECIMAL(18,10) schema.
                merged["fwd_points"] = (
                    (merged["value"] - merged["spot"]) * divisor
                ).round(6)
        else:
            merged = pd.DataFrame(
                columns=["obs_date", "tenor", "mid_rate", "fwd_points"]
            )

        # Concatenate SPOT + forwards
        out = pd.concat(
            [spot_rows[["obs_date", "tenor", "mid_rate", "fwd_points"]],
             merged[["obs_date", "tenor", "mid_rate", "fwd_points"]]],
            ignore_index=True,
        )

        # Stamp identity columns
        out["base_ccy"] = src.base_ccy
        out["quote_ccy"] = src.quote_ccy
        out["obs_ts"] = src.obs_ts
        out["ts"] = src.obs_ts  # alias for downstream pipeline compat

        return out[_OUTPUT_COLUMNS]


def discover_bbg_fx_files(
    root: Path,
    ccys: list[str],
) -> list[BBGFXSourceFile]:
    """Resolve ``Z:\\...\\BBG_mirror\\FX\\{CCY}\\FX_{CCY}.csv`` for each requested ccy.

    Skips ccys whose CSV is missing (caller decides whether that's OK).
    """
    out: list[BBGFXSourceFile] = []
    for ccy in ccys:
        path = root / ccy / f"FX_{ccy}.csv"
        if not path.exists():
            log.warning("bbg_csv_missing", ccy=ccy, path=str(path))
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        base, quote = resolve_pair_orientation(ccy)
        out.append(
            BBGFXSourceFile(
                path=path,
                ccy=ccy,
                base_ccy=base,
                quote_ccy=quote,
                obs_ts=mtime,
            )
        )
    return out
