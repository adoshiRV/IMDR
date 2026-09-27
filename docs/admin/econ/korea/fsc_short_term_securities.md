# FSC Short-Term Securities Issuance — source reference (data.go.kr org 1160100)

**Status:** ✅ **CD issuance BUILT + WIRED 2026-08-04; full history LOADED 2026-08-11** (5,569 obs, 2020→; live leg in `kr_daily`).
· **Vendor:** **`ksd`** (reused the already-seeded vendor — this is the same KSD registration data as
#15059591, reached via the FSC-published org 1160100; no new vendor/migration). · **Cadence:** daily, T+1.
· CP/ABCP/ABSTB + rate/balance operations remain **available but not yet ingested**.

> What it is: the **금융위원회 (FSC) 단기금융증권 발행정보** open API — ISIN-level issuance records for
> the whole Korean short-term money-market complex: **CD (양도성예금증서), CP (기업어음), ABCP,
> ABSTB (자산유동화전자단기사채)**, plus issuance rates and maturity/balance rollups. Sourced from KSD
> (한국예탁결제원) registration data, published via FSC on data.go.kr. This is the **verified path for
> the CD-issuance leg** of the KR money-market build ([`kosis_kr_coverage_plan.md`](kosis_kr_coverage_plan.md)
> §4.3a) — it supersedes the dormant KSD dataset #15059591 (same underlying data, deeper here).

Guide: `오픈API 활용가이드_금융위원회_단기금융증권발행정보_1912.docx` (in Downloads; V2 endpoints below,
newer than the guide's V1).

## Endpoint

```
https://apis.data.go.kr/1160100/GetShorTermSecuIssuInfoService_V2/{operation}
```

- **serviceKey** — the data.go.kr account key. Our `.env` holds the **URL-encoded ("Encoding")**
  variant (ends `%3D%3D`). ⚠️ It must go **raw into the URL string**, NOT through
  `requests(params=…)` — `params` re-encodes the `%` and auth fails. (Build the query string by hand
  or pre-decode the key.)
- Use **`https`** (http/port-80 timed out from this box).
- Common request params (all operations): `serviceKey` (req), `pageNo`, `numOfRows`,
  `resultType` (`json`|`xml`), and `basDt` (기준일자, `yyyymmdd`) to filter one base date. Some ops
  also accept `isinCd` / `crno` (법인등록번호) filters.
- Response is the standard data.go.kr envelope: `response.header.resultCode` (`00`=NORMAL) +
  `response.body.{items.item[], numOfRows, pageNo, totalCount}`. **Paginate** on `totalCount`.

## Operations (all `_V2`, verified 2026-08-04)

| Operation | Content | totalCount (2026-08-04) |
|---|---|---:|
| **`getCdIssuBasiInfo_V2`** | **CD 발행 기본정보** (ISIN-level CD issuance) | **576,925** |
| `getShorTermCpBasiInfo_V2` | CP (기업어음) 발행 기본정보 | 656,330 |
| `getAbcpIssuBasiInfo_V2` | ABCP 발행 기본정보 | — |
| `getAbstbIssuBasiInfo_V2` | ABSTB (자산유동화전자단기사채) 발행 기본정보 | — |
| `getIssuInteRate_V2` | 발행 금리 / 이자율 | 72,834 |
| `getIssuShorTermSecuMatuIssuBala_V2` | 만기별 발행잔액 (issuance balance by maturity) | 312,275 |
| `getIssuShorTermSecuMontMatuAmou_V2` | 월별 만기도래 금액 (monthly maturity amount) | — |
| `getIssuTypeIssuBala_V2` | 발행유형별 발행잔액 | — |
| `getKindIssuBala_V2` | 종류별 발행잔액 | — |

History: CD issuance rows go back to **2020-04** in probes (per-issue). Data is daily, published T+1.

## `getCdIssuBasiInfo_V2` — response fields (the CD parameter list)

One row per CD issue (ISIN). Sample: KDB (`산업`) CD, issued 2020-01-22, ₩130bn, discount 1.455%.

| Field | Meaning | Notes |
|---|---|---|
| `basDt` | 기준일자 (base date) | `yyyymmdd` |
| `isinCd` / `isinCdNm` | ISIN code / issue name | name = bank + branch + date + serial |
| `scrsDcd` / `scrsDcdNm` | 증권구분 코드 / 명 | `13` = `CD` |
| `codpIssuBnkNm` | 발행은행명 (issuing bank) | e.g. 산업/국민/신한… |
| `codpIssuHdofNo` | 발행 본점 번호 | |
| `codpIssuDt` | 발행일자 (issue date) | |
| `codpExprDt` | 만기일자 (maturity date) | tenor = expr − issu |
| `codpParPrc` | 액면가 (par) | KRW |
| `codpSaleAmt` | 매출금액 (sale/proceeds) | KRW |
| `codpIssuAmt` | 발행금액 (issue amount) | KRW — the volume field |
| `codpDcRat` | 할인율 (discount rate) | **%** — the rate field |
| `codpIssuFrmtNm` | 발행형태명 | e.g. 전액등록 |
| `codpRdptDt` | 상환 관련 | small int; meaning to confirm |
| `codpIssuCurCd` / `codpIssuCurCdNm` | 발행통화 | KRW |
| `codpPayBnkNm` / `codpPayBnkBrofCd` | 지급은행명 / 지점코드 | |
| `codpRegDt` | 등록일자 | |

(CP/ABCP/ABSTB operations mirror this with `cp*` / `abcp*` / `abstb*` prefixes — issuing company
`*IssuCmpyNm` + KSD custody no, dealer `*DcInstNm`, dates, amount, currency.)

## Aggregation target (for `econ.fact_indicator`)

Raw is ISIN-level per-issue, but note the **snapshot semantics**: `basDt` is a *daily snapshot of CDs
outstanding*, so each ISIN recurs on every day it's live (issue→maturity). `isinCd` is the unique key;
`codpIssuDt` is the real issue date. The built fetcher therefore:
- **dedups by `isinCd`, then groups by `codpIssuDt`** for the issuance FLOW series, and
- **sums `codpIssuAmt` per `basDt` snapshot** for the OUTSTANDING stock series.

Indicators built (vendor `ksd`, DAILY, `econ.fact_indicator`; loaded 2026-08-11):
- `KSD.CD.ISSUANCE.VOLUME.KR` — Σ `codpIssuAmt` per issue date (krw_bn) — 1,154 obs, 2020-01-09→
- `KSD.CD.ISSUANCE.COUNT.KR` — new-issue count per issue date — 1,154 obs
- `KSD.CD.ISSUANCE.AVG_RATE.KR` — amount-weighted avg `codpDcRat` per issue date (%) — 1,154 obs
- `KSD.CD.OUTSTANDING.KR` — Σ `codpIssuAmt` per `basDt` snapshot (krw_bn stock) — 2,107 obs, 2020-04-08→ (latest ₩27.6tn)

Note: the ~2020 history is genuine — every `basDt` is a real daily outstanding snapshot (~150→400 CDs, up to ~1yr of issue dates each, growing with the market). Backfill paged 579k raw rows → 2,900 unique CDs.

Fetcher `scripts/econ/kr/ksd/ksd_cd_issuance.py`, transport `src/imdr/domains/econ/datagokr_http.py`
(reusable data.go.kr client — raw-key-in-URL, pagination). Optional future cuts (maturity bucket,
issuing-bank group, CP/ABCP) not yet built.

## License

data.go.kr / KSD-originated → **KOGL (공공누리)**: typically attribution + (often) non-commercial.
**Confirm the exact KOGL type on the dataset page before any client-facing use.**

## Relationship to the other CD sources

| Cut | Source | Status |
|---|---|---|
| CD **issuance** (ISIN, amount, rate, maturity, bank) | **FSC 1160100 `getCdIssuBasiInfo_V2`** | ✅ **BUILT + WIRED** — vendor `ksd`, `KSD.CD.ISSUANCE.*` + `KSD.CD.OUTSTANDING.KR` |
| CD **secondary volume** (daily total) | KOFIA freeSIS `STATBND0100000050` | ✅ PROD-LIVE (`KOFIA.CD.TRADE_*`) |
| CD **91d yield** (daily) | KOFIA freeSIS `STATBND0100000320` | ✅ PROD-LIVE (`KOFIA.CD.YIELD*`) |
| CD **who-traded** (buyer/seller by sector) | KSD data.go.kr **#15043446** | ⏳ dormant — **not covered by FSC**; still the only source |
| CD issuance (KSD portal copy) | KSD data.go.kr **#15059591** | ⛔ redundant — superseded by FSC above |
