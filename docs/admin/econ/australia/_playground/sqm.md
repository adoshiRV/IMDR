# SQM Research — `scripts/econ/au/sqm/` (library: `src/imdr/domains/econ/sqm_research.py`)

Last updated: 2026-07-14

**Status:** DB-LIVE — 1 fetcher, **33 indicators / 21,729 obs** loaded (DB-verified 2026-07-14). New vendor row `sqm research` (`vendor_category='sell_side'`) via migration 109. New unit `aud_pw` (Australian dollars per week) via migration 110. Wired into `au_daily` (no dedicated AU weekly orchestrator exists; idempotent MERGE makes a daily poll of a weekly series harmless).

Why we care: ABS RPPI (residential property prices) is quarterly and sale-price only. SQM Research is the standard free source for **asking rents** (weekly) and **vacancy rates** (monthly) — the demand-side complement to Cotality's HVI and ABS's RPPI.

## Investigation (2026-07-14)

`sqmresearch.com.au` server-renders each city's full historical series as a JSON literal embedded directly in an inline `<script>` tag (`var data = [...]`) feeding a Highcharts chart. There is no separate ajax/JSON endpoint — the chart data is already in the page HTML. The only gated element is a "Buy the data behind this chart" HubSpot lead-gen button, which is decorative and does not block the inline data. Plain `httpx` works — no Playwright, no login.

## Series

**Weekly Asking Rents** (`/property/weekly-rents?region={region}&type=c`) — full history 2009-08-01 → present. Nominally weekly (~87% of gaps are exactly 7 days; the rest are 8–10 day gaps clustered around month boundaries — a source cadence quirk, not a scraping artefact). Per city we take 3 of the 5 fields published (`combined`, `houses_all`, `units_all` — the 3-bed-house / 2-bed-unit cuts are in the same payload but not part of the naming convention used here):

| IMDR code | Series |
|---|---|
| `SQM.RENT.{CITY}.AU` | Combined (houses + units), AUD/week |
| `SQM.RENT.{CITY}_HOUSE.AU` | All houses, AUD/week |
| `SQM.RENT.{CITY}_UNIT.AU` | All units, AUD/week |

8 capitals (`{CITY}` = SYDNEY/MELBOURNE/BRISBANE/ADELAIDE/PERTH/HOBART/DARWIN/CANBERRA) × 3 = 24 series. No national aggregate is published for rents.

**Residential Vacancy Rates** (`/property/vacancy-rates?region={region}&type=c` or `?national=1`) — MONTHLY (one point per `{year, month}`, despite sitting under the same "property" URL section as the weekly rent pages). Full history 2005-01 → present. Source field `vr` is a fraction (e.g. 0.0160 == 1.60%); stored as `vr * 100`, unit `pct`.

| IMDR code | Series |
|---|---|
| `SQM.VACANCY.{CITY}.AU` | Vacancy rate, % |
| `SQM.VACANCY.NATIONAL.AU` | National vacancy rate, % |

8 capitals + National = 9 series.

**Total: 24 + 9 = 33 indicators.**

## Not built (out of scope)

- Asking Property Prices (`/property/asking-property-prices?...`) — a distinct page, same free/public shape, trivial to add later.
- Postcode-level vacancy rates — city (and national) level only here.
- 3-bed-house / 2-bed-unit rent cuts — present in the same rent payload as `houses_all`/`units_all` but not part of the naming convention asked for.

## Transport

Plain `httpx.Client`, 1 request per city per series type, `time.sleep(1.0)` between requests (courtesy delay, not required by any observed rate-limit). No auth, no cookies needed for the data itself.

## Related

- [`../australia_indicator_inventory.md`](../australia_indicator_inventory.md) — 4×4 tracker cells 4.2 / 1.1
- [`cotality.md`](cotality.md) — sibling housing-price vendor (sale-price index vs SQM's rent/vacancy)
- Migrations: `migrations/109_seed_au_sqm_seek_dim_vendor.sql`, `migrations/110_seed_dim_unit_aud_pw.sql`
