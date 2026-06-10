"""BI Indonesia SBN position by holder (SEKI Table IV.4).

Source: BI SEKI TABEL4_4 (sheet "4.4") — POSISI SURAT BERHARGA NEGARA, monthly.

Cell mapping: 4.2 Balance Sheets — government securities outstanding by
investor category, finer-than-DJPPR bank breakdown:

  - Bank Pemerintah (state-owned commercial banks)
  - Bank Swasta Nasional (national private banks)
  - Bank Campuran (joint-venture banks)
  - Bank Asing (foreign-bank branches)
  - Bank Pembangunan Daerah (regional development banks)
  - Bank Indonesia
  - Nasabah (non-bank customers — includes MF/insur/pension/foreign/retail)
  - Institusi Lainnya (other institutions)

Complements the DJPPR Kepemilikan SBN feed (already in IMDR via
`djppr.SBN.HOLD.*`), which uses a different taxonomy (DJPPR
single-bank category vs BI's 5-bank-type cut).

Emits 16 holder indicators (8 SUN + 7 SPN, plus the BI line where present)
plus 3 headline totals (SUN, SPN, SBSN). Tenor cut is NOT in this table —
BI publishes SBN-by-type (fixed/variable/ORI/etc.) and SBN-by-holder as
separate 1D cuts. The 2D matrix of (tenor × investor) is not in the public
SEKI file.

Unit: Miliar Rp / IDR billion. Monthly cadence; observation date is
end-of-month. History begins 2008-Dec (annual through 2010, monthly
thereafter).
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_seki import download_seki, parse_seki_wide_sheet
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# TABEL4_4 uses standard SEKI offsets: year=row 4, month=row 5, data=row 6
_TABLE_OFFSETS = (4, 5, 6)

# BI taxonomy: SUN (umbrella) = ON (Obligasi Negara, bonds) + SPN (T-bills).
# Holder breakdowns sit under ON and SPN separately, not under the SUN parent.
# SBSN (Sukuk) is the other umbrella; only its type-cut is in this table.
#
# (line_no, imdr_code, display_name)
_TARGETS: list[tuple[int, str, str]] = [
    # ── Headline totals ──────────────────────────────────────────────
    (1, "BI.SBN.POSITION.SUN.TOTAL.IDR.ID",
     "Indonesia SUN outstanding — umbrella total = ON + SPN (BI SEKI IV.4, IDR bn)"),
    (2, "BI.SBN.POSITION.ON.TOTAL.IDR.ID",
     "Indonesia Obligasi Negara outstanding — conventional bonds total (BI SEKI IV.4, IDR bn)"),
    (18, "BI.SBN.POSITION.SPN.TOTAL.IDR.ID",
     "Indonesia SPN outstanding — T-bills total (BI SEKI IV.4, IDR bn)"),
    (27, "BI.SBN.POSITION.SBSN.TOTAL.IDR.ID",
     "Indonesia SBSN outstanding — sukuk total (BI SEKI IV.4, IDR bn)"),

    # ── ON (Obligasi Negara) by ownership ────────────────────────────
    (10, "BI.SBN.POSITION.ON.HOLD.BANK_GOV.IDR.ID",
     "Indonesia ON holdings — state-owned banks Bank Pemerintah (BI SEKI IV.4, IDR bn)"),
    (11, "BI.SBN.POSITION.ON.HOLD.BANK_PRIV.IDR.ID",
     "Indonesia ON holdings — national private banks Bank Swasta Nasional (BI SEKI IV.4, IDR bn)"),
    (12, "BI.SBN.POSITION.ON.HOLD.BANK_MIX.IDR.ID",
     "Indonesia ON holdings — joint-venture banks Bank Campuran (BI SEKI IV.4, IDR bn)"),
    (13, "BI.SBN.POSITION.ON.HOLD.BANK_FOREIGN.IDR.ID",
     "Indonesia ON holdings — foreign-bank branches Bank Asing (BI SEKI IV.4, IDR bn)"),
    (14, "BI.SBN.POSITION.ON.HOLD.BANK_REGIONAL.IDR.ID",
     "Indonesia ON holdings — regional development banks BPD (BI SEKI IV.4, IDR bn)"),
    (15, "BI.SBN.POSITION.ON.HOLD.BI.IDR.ID",
     "Indonesia ON holdings — Bank Indonesia (BI SEKI IV.4, IDR bn)"),
    (16, "BI.SBN.POSITION.ON.HOLD.NASABAH.IDR.ID",
     "Indonesia ON holdings — non-bank customers Nasabah (BI SEKI IV.4, IDR bn)"),
    (17, "BI.SBN.POSITION.ON.HOLD.INST_OTHER.IDR.ID",
     "Indonesia ON holdings — other institutions Institusi Lainnya (BI SEKI IV.4, IDR bn)"),

    # ── SPN (T-bills) by ownership ───────────────────────────────────
    (20, "BI.SBN.POSITION.SPN.HOLD.BANK_GOV.IDR.ID",
     "Indonesia SPN holdings — state-owned banks Bank Pemerintah (BI SEKI IV.4, IDR bn)"),
    (21, "BI.SBN.POSITION.SPN.HOLD.BANK_PRIV.IDR.ID",
     "Indonesia SPN holdings — national private banks Bank Swasta Nasional (BI SEKI IV.4, IDR bn)"),
    (22, "BI.SBN.POSITION.SPN.HOLD.BANK_MIX.IDR.ID",
     "Indonesia SPN holdings — joint-venture banks Bank Campuran (BI SEKI IV.4, IDR bn)"),
    (23, "BI.SBN.POSITION.SPN.HOLD.BANK_FOREIGN.IDR.ID",
     "Indonesia SPN holdings — foreign-bank branches Bank Asing (BI SEKI IV.4, IDR bn)"),
    (24, "BI.SBN.POSITION.SPN.HOLD.BANK_REGIONAL.IDR.ID",
     "Indonesia SPN holdings — regional development banks BPD (BI SEKI IV.4, IDR bn)"),
    (25, "BI.SBN.POSITION.SPN.HOLD.BI.IDR.ID",
     "Indonesia SPN holdings — Bank Indonesia (BI SEKI IV.4, IDR bn)"),
    (26, "BI.SBN.POSITION.SPN.HOLD.NASABAH.IDR.ID",
     "Indonesia SPN holdings — non-bank customers Nasabah (BI SEKI IV.4, IDR bn)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading TABEL4_4 ...", end=" ", flush=True)
    path = download_seki("TABEL4_4")
    yr_row, mo_row, data_start = _TABLE_OFFSETS
    parsed = parse_seki_wide_sheet(
        path, sheet="4.4",
        year_row=yr_row, month_row=mo_row, data_start_row=data_start,
    )
    print(f"{len(parsed)} line items")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for line, imdr_code, display in _TARGETS:
        series = parsed.get(line) or []
        if not series:
            print(f"    {imdr_code}: line {line} missing — skipping")
            continue

        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BI",
            source_code=f"BI/SEKI/TABEL4_4/sheet=4.4/line={line}",
            display_name=display, unit="idr_bn", frequency="MONTHLY",
            country_iso="ID", category="balance_sheet",
            is_seasonally_adjusted=False, bbg_ticker=None,
        )
        obs_emitted = 0
        for obs_date, value, _label in series:
            if value is None:
                continue
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
            obs_emitted += 1
        if obs_emitted == 0:
            continue
        indicators.append(indicator)
        print(f"    {imdr_code}: {obs_emitted} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="bi", topic="sbn_position",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")


if __name__ == "__main__":
    import sys; sys.exit(main())
