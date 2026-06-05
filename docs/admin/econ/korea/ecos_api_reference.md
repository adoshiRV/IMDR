# BOK ECOS / KOSIS — API Reference

Last updated: 2026-06-03

## Source landscape

| System | URL | Auth | Role |
|---|---|---|---|
| **BOK ECOS** | `https://ecos.bok.or.kr` | API key (Korean mobile + citizenship — **blocked for IMDR**) | Authoritative publisher |
| **KOSIS** | `https://kosis.kr` | None | Mirror of BOK series under `orgId=301` |
| **FRED** | `https://api.stlouisfed.org/fred` | API key (free) | OECD-relayed subset; ~6-12 mo lag vs KOSIS |

KOSIS is a 1:1 mirror — the KOSIS `tblId` is the ECOS `STAT_CODE` prefixed
with `DT_`. E.g. ECOS `301Y013` ↔ KOSIS `DT_301Y013`.

## STAT_CODE namespaces (top-level)

ECOS classifies tables under broad numeric prefixes. From discovery
2026-06-03:

| Prefix | Branch | Notes |
|---|---|---|
| `200Y…` | National Income Statistics (Base Year 2020) | SNA: GDP, consumption, investment, savings |
| `301Y…` | Balance of Payments | Master: `301Y013`; SA CA: `301Y017`; regional: `301Y015`/`301Y016` |
| `311Y…` | International Investment Position / External Debt | Stock counterparts |
| `403Y…` | Trade Index / Terms of Trade | |
| `732Y…` | Foreign Exchange Reserves | Stock — counterpart to BoP Reserve Assets flow |
| `901Y…` | Customs Trade Statistics | Korea Customs Service basis (≠ BoP-basis goods trade) |

Full per-branch inventory: see [_playground/bop.md](_playground/bop.md) and
the playground inventory file
[playground/econ/bok_ecos/stat_code_inventory.md](../../../../playground/econ/bok_ecos/stat_code_inventory.md).

## URL patterns

### KOSIS browser-rendered table

```
https://kosis.kr/statHtml/statHtml.do
  ?orgId=301
  &tblId=DT_301Y013
  &vw_cd=MT_ETITLE
  &language=en
  &conn_path=E3
  [&list_id=<path>]
```

`vw_cd=MT_ETITLE` requests the English-titled view; `conn_path=E3` is a
session anchor. Direct HTTP `GET` to this URL TLS-resets from corp network;
use Playwright with the persistent profile at `playground/econ/profiles/kosis/`.

### KOSIS download (form POST, discovered via `playground/econ/kosis/capture_download.py`)

The toolbar Download button triggers `javascript:fn_downGridSubmit()`. The
operator must click through the dialog (EXCEL → Download). The
[`fetch_bop.py`](../../../../playground/econ/kosis/fetch_bop.py) script
auto-clicks where possible and falls back to manual mode otherwise.

**Default range**: KOSIS UI shows only the **last 6 months** unless the
period selector is changed before downloading. To get full history,
expand the period selector to "1980 ~ present" first.

### BOK ECOS Open API (blocked — documented for future)

```
https://ecos.bok.or.kr/api/StatisticSearch/{API_KEY}/{format}/{lang}/
  {start}/{end}/{STAT_CODE}/{cycle}/{startDate}/{endDate}/
  {ITEM_CODE1}/{ITEM_CODE2}/{ITEM_CODE3}/{ITEM_CODE4}
```

- `format`: `json` or `xml`
- `lang`: `kr` or `en`
- `cycle`: `A` annual / `Q` quarterly / `M` monthly / `D` daily
- Up to 4 ITEM_CODEs per request

API key requires Korean mobile + citizenship at registration. Not
available to IMDR. If granted in the future, swap the KOSIS Playwright
path for direct REST.

## ITEM_CODE structure inside `301Y013` (Balance of Payments)

`301Y013` uses **two ITEM_CODE namespaces** depending on section:

| Section | Code prefix | Length |
|---|---|---|
| Current Account (trade / services / primary income / secondary income) | `3…` short hierarchical | 6 chars |
| Financial Account | `BOPF…` | 12 chars |
| Errors & Omissions | `BOPO…` | 12 chars |

### Financial-account code pattern (`BOPF…`)

```
BOPF { funct } { side } { instrument } { counterparty } { sub-counterparty }
 4ch     1ch     1ch        2ch              2ch                1ch
```

| Position | Field | Values |
|---|---|---|
| 5 | Functional category | `1` Direct Investment · `2` Securities Investment (equity) · `3` Securities Investment (debt securities) · `4` Other Investment · `5` Reserve Assets · `0` parent |
| 6 | Side | `1` Assets · `2` Liabilities |
| 7-8 | Instrument | OI: `10` Trade credit · `20` Loans · `30` Cash & deposits · `40` Other · `50` Other equity · `60` SDRs<br>DI: `10` Stocks · `20` Reinvested earnings · `30` Debt instruments<br>SI Equity: `10` Stocks |
| 9-10 | Counterparty sector | `10` Central bank · `20` General government · `30` Deposit-taking institutions · `40` Other categories |
| 11 | Sub-counterparty (under "Other") | `1` Other financial corporations · `2` Non-financial corporates |

For loans (instrument=`20`), positions 7-8 also encode maturity:
- `BOPF42210000` = Liab / Loans / **long-term**
- `BOPF42220000` = Liab / Loans / **short-term**

### Headline codes

| Code | Meaning |
|---|---|
| `BOPF00000000` | Financial Account — parent |
| `BOPF10000000` | Direct Investment — parent |
| `BOPF11000000` | DI Assets (outward FDI) |
| `BOPF12000000` | DI Liabilities (inward FDI) — UI labels this "(debt)" |
| `BOPF20000000` | Securities Investment Equity — parent |
| `BOPF21000000` | SI Equity Assets |
| `BOPF22000000` | SI Equity Liabilities |
| `BOPF3xxxxxxx` | Securities Investment Debt Securities sub-tree |
| `BOPF40000000` | Other Investment — parent |
| `BOPF41000000` | OI Assets |
| `BOPF42000000` | OI Liabilities |
| `BOPF50000000` | Reserve Assets |
| `BOPO00000000` | Errors and Omissions |

### Translation gotcha

BOK's English ECOS UI translates Korean **부채 (liabilities)** as
**"debt"**. Without this knowledge, half the Financial-account series
are misread.

| UI label | Actual meaning |
|---|---|
| Direct investment **(asset)** | Assets — **outward** FDI |
| Direct investment **(debt)** | **Liabilities** — **inward** FDI (NOT debt securities) |
| Stock **(Debt)** at `BOPF12100000` | Equity stocks on liabilities side |
| debt instruments **(debt)** at `BOPF12300000` | Intercompany loans, liabilities |

Note: the **KOSIS English UI uses BPM6 standard labels** ("Liabilities",
"Portfolio investment") rather than BOK's custom translation. Same
underlying data, different vocabulary.

| BOK ECOS English | KOSIS English / BPM6 |
|---|---|
| Securities investment | Portfolio investment |
| (asset) / (debt) | Assets / Liabilities |

## Source-agency metadata (BoP)

- **Agency**: Bank of Korea, Balance of Payments Team, Bureau of Economic Statistics
- **Email**: `bokdesb@bok.or.kr`
- **Phone**: Current Account: +82-2-759-4370 · Capital + Financial Account: +82-2-759-4333
- **Legal**: Article 86, Bank of Korea Act · Statistics Korea Approval No. 301008
- **Compilation basis**: BPM6 since 2005 (BPM7 migration under review per March 2025 release)
- **Frequency**: Monthly
- **Lag**: T+2 months (e.g., March data → released early May)
- **History**: 1980 → present

## Related modules

- [`playground/econ/fred/seed.yml`](../../../../playground/econ/fred/seed.yml) — FRED `KORB6*CXCUM` Korea BoP series (Bucket 11b)
- [`playground/econ/kosis/fetch_bop.py`](../../../../playground/econ/kosis/fetch_bop.py) — KOSIS Playwright downloader
- [`playground/econ/kosis/capture_download.py`](../../../../playground/econ/kosis/capture_download.py) — Endpoint-discovery harness (for new tables)
- [`playground/econ/bok_ecos/discover_bop.py`](../../../../playground/econ/bok_ecos/discover_bop.py) — ECOS tree explorer
- [`playground/econ/bok_ecos/stat_code_inventory.md`](../../../../playground/econ/bok_ecos/stat_code_inventory.md) — Growing inventory of explored ECOS codes
