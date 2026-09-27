# KR short-term money-market data (KOFIA freeSIS · FSC · KSD) — execution tracker

**Status:** ✅ **KOFIA PROD-LIVE 2026-07-20** · ✅ **CD issuance BUILT + WIRED 2026-08-04**
(vendor `ksd` via FSC data.go.kr 1160100; loaded + in `kr_daily`) · KSD who-traded still dormant ·
**not yet committed to git**
**Owner:** adoshi · **Linear:** _pending (draft in §7)_

Sister trackers: [`kr_govt_filings.md`](kr_govt_filings.md) (Track B filings). Ops runbook:
[`../econ/korea/korea_prod_pipeline.md`](../econ/korea/korea_prod_pipeline.md). Coverage:
[`../econ/korea/kosis_kr_coverage_plan.md`](../econ/korea/kosis_kr_coverage_plan.md) §4.3a.

## 1. Why

Desk questions unanswerable from the existing corpus: Korean **CD** trading (volume,
yield, who-traded, issuance) and **MMF** (flows, net assets), plus the asset-management
**fund AUM by asset class** ("Bond / Equity / MMF" chart). KOSIS/BOK-ECOS carry only the
CD 91-day *rate* (monthly). The volume / flow / AUM cuts live in **KOFIA freeSIS** (no
auth) and **KSD** (data.go.kr, key-gated).

## 2. What shipped (KOFIA — vendor `kofia`, dim_vendor id=85)

25 active indicators / ~114.3k obs in `econ.fact_indicator`, all DAILY. 5 fetchers under
`scripts/econ/kr/kofia/`, transport `src/imdr/domains/econ/kofia_http.py`.

| Fetcher | Indicators | freeSIS service | History | Category |
|---|---|---|---|---|
| `kofia_cd_trading` | `KOFIA.CD.TRADE_{TOTAL,SELL,BUY}.KR` | STATBND0100000050 | 2003-01→ | liquidity |
| `kofia_cd_yield` | `KOFIA.CD.YIELD{,.SPECIAL_BANK}.KR` | STATBND0100000320 | 2009-01→ | rates |
| `kofia_mmf_flows` | `KOFIA.MMF.{INFLOW,OUTFLOW,NET_FLOW}.KR` | STATFND0100100030 (T1111=05) | 2006-05→ | liquidity |
| `kofia_mmf_level` | `KOFIA.MMF.NAV{,.INDIV,.CORP}.KR` | STATFND0400000050 (tmpV39=2) | 2010-01→ | liquidity |
| `kofia_fund_aum` | `KOFIA.FUND_AUM.{EQUITY,BOND,MMF,HYBRID_EQUITY,HYBRID_BOND,DERIVATIVES,REAL_ESTATE,FOF,SPECIAL_ASSET,MIXED_ASSET,COMMODITY,CONTRACT,GROWTH,TOTAL}.KR` (14) | STATFND0100100130 (tmpV35=0) | 2004-01→ | balance_sheet |

- **freeSIS mechanism** (reverse-engineered, no browser needed in prod): `POST /meta/getMenuData.do` (catalogue) · `POST /meta/getSrvData.do` (param spec + grid headers) · `POST /meta/getMetaDataList.do` (data, rows in `ds1`). Values in 억원 → ×0.1 = krw_bn. Daily period code `tmpV35=0` works even though the portal dropdown shows only monthly/yearly.
- **Wiring:** all 5 in `scripts/econ/kr/kr_daily.py` Track A (now dual-track A+B) with a `track_a_snapshot` email section. `kr_daily` already registered in `scripts/imdr_daily.py:PIPELINES` → live on the daily cron.
- **Migrations:** `115_seed_kofia_ksd_dim_vendor.sql` (applied) · `116_deactivate_kofia_mmf_setup_principal.sql` (applied — MMF principal now lives in `KOFIA.FUND_AUM.MMF`, daily/longer).
- **Identity check:** the 13 fund-AUM types sum to `FUND_AUM.TOTAL` within rounding.

## 3. Code review (high effort, 2026-07-20) — 5 findings

| # | Finding | Resolution |
|---|---|---|
| 1 | Live fetchers ingested the current, incomplete day; insert-only loader would lock the partial value | **FIXED** — live mode caps `until` at **T-1**; deleted the one already-locked partial day (2026-07-20 CD volume) for clean re-ingest |
| 2 | NULL observations stored for empty fund types (COMMODITY/실물) | **FIXED** — skip `None` values (fund_aum, cd_yield, mmf_level) |
| 3 | `kofia_mmf_level` fetched each snapshot twice (resolve + loop) | **FIXED** — `_resolve_snapshot` returns the row it found |
| 4 | freeSIS transport retried ReadTimeout but not ConnectTimeout | **FIXED** — catches `requests.exceptions.Timeout` |
| 5 | MMF NAV backfilled month-end vs fund_aum daily | **Documented trade-off** (daily NAV backfill = ~5k snapshot calls); NAV is daily live going forward |

## 4. CD **issuance** — BUILT + WIRED 2026-08-04 (vendor `ksd`, via FSC data.go.kr org 1160100)

The CD **issuance** cut is served by the **FSC (금융위원회) 단기금융증권 발행정보** open API on
data.go.kr (org **1160100**, `getCdIssuBasiInfo_V2`) — the same KSD registration data as #15059591,
deeper via the FSC org. **Implemented in the existing `scripts/econ/kr/ksd/ksd_cd_issuance.py`,
reusing the seeded `ksd` vendor** (no new vendor/migration). Source ref: [`../econ/korea/fsc_short_term_securities.md`](../econ/korea/fsc_short_term_securities.md).

- **Verified live 2026-08-04** with the loaded `IMDR_KSD_API_KEY`: `getCdIssuBasiInfo_V2` → 200,
  `resultCode 00`, ~576.9k ISIN-level CD-issue rows (2020-04→).
- **Snapshot semantics (load-bearing):** `basDt` = daily snapshot of CDs *outstanding* (each ISIN
  recurs issue→maturity). Fetcher **dedups by `isinCd` → groups by `codpIssuDt`** (issuance FLOW) and
  **sums `codpIssuAmt` per `basDt`** (OUTSTANDING stock).
- **4 indicators (DAILY), LOADED 2026-08-11:** `KSD.CD.ISSUANCE.{VOLUME,COUNT,AVG_RATE}.KR` (1,154 obs, 2020-01-09→) + `KSD.CD.OUTSTANDING.KR` (2,107 obs, 2020-04-08→); 5,569 obs total.
- **Gotcha:** key is the **URL-encoded** variant — must go **raw in the URL** (not `requests(params=)`); use `https`. Handled by the reusable `src/imdr/domains/econ/datagokr_http.py` transport.
- **Supersedes KSD #15059591** (same data). CP/ABCP/ABSTB + rate/balance ops available, not yet built.

## 4b. KSD (vendor `ksd` id=86) — who-traded only, still DORMANT

CD **who-traded** (buyer/seller by financial sector) is **not** in freeSIS **or** the FSC API —
KSD data.go.kr **#15043446** is the only source. ECOS (CD outstanding) is registration-blocked.

- Scaffold: `scripts/econ/kr/ksd/ksd_cd_trades.py` (#15043446). `ksd_cd_issuance.py` (#15059591) is now
  **redundant** (FSC covers issuance) — retire or repoint.
- No-ops until the response schema is verified; the `IMDR_KSD_API_KEY` is now set (works for #15043446 too — apply for the dataset on data.go.kr).
- License: KOGL — attribution + non-commercial (confirm before anything client-facing).

## 4c. Build status — CD issuance → prod (DONE 2026-08-04, vendor `ksd`)

Built end-to-end per the onboarding playbook (user authorized full prod incl. wiring):

1. ✅ **Transport** — `src/imdr/domains/econ/datagokr_http.py` (reusable data.go.kr client:
   raw-key-in-URL, `https`, JSON, pagination over `totalCount`, TLS/retry). Serves KSD #15043446 later too.
2. ✅ **Fetcher** — `scripts/econ/kr/ksd/ksd_cd_issuance.py` (replaced the dormant scaffold): live mode
   probes the latest `basDt` snapshot; `--since` backfill pages the whole dataset, dedups by isin,
   builds FLOW (by `codpIssuDt`) + STOCK (by `basDt`). No new vendor/migration (reused `ksd`;
   indicators auto-create from `IndicatorRow`).
3. ✅ **Tests** — `tests/unit/test_econ/test_ksd_cd_issuance.py` + `test_datagokr_http.py` (25 pass):
   dedup, flow aggregation, amount-weighted rate, outstanding Σ, raw-key handling, pagination, empty/error.
4. ✅ **Backfill + load** — full history into `econ.fact_indicator` (2026-08-11): paged 579,075 raw snapshot rows → 2,900 unique CDs → **5,569 obs** (86 overlap rows no-op, verified matching live). `KSD.CD.ISSUANCE.{VOLUME,COUNT,AVG_RATE}.KR` = 1,154 obs each, **2020-01-09 → 2026-08-07**; `KSD.CD.OUTSTANDING.KR` = 2,107 obs, **2020-04-08 → 2026-08-10** (latest ₩27.6tn).
5. ✅ **Wired** — added to `scripts/econ/kr/kr_daily.py` Track A (already registered in `imdr_daily.py`).
6. ⏳ **Security review (imdr-security)** — new external API + key: confirm no key in logs/printed URLs;
   confirm KOGL license type before any client-facing use. *(recommended follow-up)*
7. ⏳ **Optional later** — CP/ABCP/ABSTB issuance + issuance-rate/maturity-balance ops; maturity-bucket
   / issuing-bank cuts of CD.

## 5. Verify / re-run

```
# smoke (no DB write)
python -m scripts.econ.kr.kofia.kofia_fund_aum --no-load
# backfill (one-off)
python -m scripts.econ.kr.kofia.kofia_cd_trading --since 2003-01-01
python -m scripts.econ.kr.kofia.kofia_fund_aum   --since 2004-01-01
# live daily (what kr_daily runs)
python -m scripts.econ.kr.kr_daily --no-email
```

Discovery record + probes: [`../../../playground/econ/kr/kofia/`](../../../playground/econ/kr/kofia/)
(`SOURCES.md`, `dump_freesis_catalog.py`, `replay_requests.py`).

## 6. Open follow-ups

- [ ] **Commit** the tree (KOFIA 5 fetchers + `datagokr_http` transport + `ksd_cd_issuance` impl + tests + migrations 115/116 + `kr_daily` wiring + docs) — currently uncommitted.
- [x] ~~Register `IMDR_KSD_API_KEY`~~ — done; loaded + verified 2026-08-04.
- [x] ~~Build CD issuance → prod~~ — **DONE 2026-08-04** (§4c): vendor `ksd`, 4 indicators, backfilled + loaded + wired into `kr_daily`.
- [ ] Apply for KSD **#15043446** (who-traded, the one cut FSC lacks) on data.go.kr → verify schema → implement `ksd_cd_trades` (reuse `datagokr_http`).
- [ ] (Optional) CP/ABCP/ABSTB issuance + issuance-rate ops from the same FSC service; CD maturity-bucket / bank-group cuts.
- [ ] (Optional) daily MMF NAV backfill if intra-month NAV history is needed.
- [ ] `imdr-security` review of the data.go.kr key handling + KOGL license before client-facing use.

## 7. Linear issue (draft — paste when authenticated)

> **Title:** KR KOFIA freeSIS onboarding (CD / MMF / fund-AUM) — PROD-LIVE; KSD who-traded+issuance pending key
> **Team:** IMD- · **Status:** Done (KOFIA) + follow-ups open
> **Body:** Onboarded KOFIA freeSIS to prod as vendor `kofia` (25 daily indicators / ~114k obs): CD trading volume + yield, MMF flows + net assets, fund AUM by asset class. Migrations 115/116 applied; wired into `kr_daily` (Track A). Code-reviewed (5 findings, 4 fixed). KSD CD "who traded" (#15043446) + issuance (#15059591) are dormant scaffolds pending a data.go.kr key (`IMDR_KSD_API_KEY`, one key both). Follow-ups: commit tree; register KSD key + implement; optional daily MMF-NAV backfill. Docs: `docs/admin/development/kr_kofia_onboarding.md`.
