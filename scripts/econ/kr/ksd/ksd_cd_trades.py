"""KSD — CD (certificate of deposit) trading, buyer/seller by financial sector.

**DORMANT SCAFFOLD** — this is the "who traded" half of the CD picture. It is
NOT yet implemented against a live response schema and stays a clean no-op
until (a) a data.go.kr service key exists and (b) the response is verified.

Source: 금융위원회_단기금융증권거래정보 (Korea Securities Depository), data.go.kr
dataset **#15043446**. Provides ISIN-level short-term-instrument trades (CP/CD)
with 매매금액 (trade value), 매매수익률 (yield), 발행/만기/잔존만기, ISIN, and
crucially **매도·매수 금융업종구분** — the buyer/seller financial-sector split
that answers "who traded" (banks / securities / asset mgmt / insurers / …).
License: KOGL — attribution + NON-COMMERCIAL. Confirm fit before distributing.

Why dormant: freeSIS carries CD *volume* (see kofia_cd_trading.py) but has no
investor dimension, and its by-investor OTC table is bonds-only (no CD). The
sector-level "who traded" cut exists only in this KSD API, which is key-gated
(register on data.go.kr — same pattern as IMDR_KOSIS_API_KEY / IMDR_REB_API_KEY).

Planned indicators once implemented + verified (aggregate the ISIN trades to a
daily net-buy per financial sector):
    KSD.CD.NET_BUY.BANK.KR / .SECURITIES.KR / .ASSET_MGMT.KR / .INSURANCE.KR / ...
stored krw_bn, category liquidity, frequency DAILY.

Activation checklist:
  1. Register key on data.go.kr for dataset 15043446; put IMDR_KSD_API_KEY in .env.
  2. Confirm the exact operation path + response field names (basDt, isinCd,
     trدValAmt, sellFncSctnCd, buyFncSctnCd, …) from the live spec.
  3. Implement run_fetch: page the API by basDt, map sector codes -> names,
     aggregate to daily net-buy per sector, emit IndicatorRow/ObservationRow.
  4. Seed the `ksd` vendor (migration 115 already drafts it) + any new units.
  5. Smoke --no-load, verify a known day, then backfill + wire.

Usage (currently prints the dormant notice and exits 0):
    python -m scripts.econ.kr.ksd.ksd_cd_trades
"""

from __future__ import annotations

import os
from pathlib import Path

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DATASET = "15043446"  # data.go.kr 금융위원회_단기금융증권거래정보 (KSD)


def _load_key() -> str | None:
    key = os.environ.get("IMDR_KSD_API_KEY")
    if key:
        return key
    env = _REPO_ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("IMDR_KSD_API_KEY="):
                return line.split("=", 1)[1].strip() or None
    return None


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    key = _load_key()
    if not key:
        print("  KSD CD-trades: DORMANT — IMDR_KSD_API_KEY not set. "
              f"Register data.go.kr dataset {_DATASET} to activate. Skipping.")
        return [], []

    # Key present but implementation deferred until the response schema is
    # verified against the live API (see the activation checklist in the
    # module docstring). Fail loud rather than emit unverified rows.
    raise NotImplementedError(
        "KSD CD-trades fetcher not implemented yet. A key is present but the "
        "data.go.kr #15043446 response schema must be verified first — see the "
        "activation checklist in this module's docstring."
    )


def main() -> int:
    return run_main(
        vendor="ksd",
        topic="cd_trades",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
        allow_empty=True,  # dormant: no rows without a key is a clean success
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
