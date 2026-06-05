# BOK ECOS direct API — `playground/econ/bok_ecos/`

**Status:** BLOCKED. ECOS direct API registration requires Korean mobile number + Korean citizenship. Folder holds Playwright-driven discovery of the underlying STAT_CODE / ITEM_CODE structure so we can mirror it via KOSIS (which carries ECOS 1:1).

Use KOSIS as the live path — see [kosis.md](kosis.md). This folder is reference-only.

## Contents

- **`discover_bop.py`** — Playwright-headed discovery of BoP STAT_CODEs on `ecos.bok.or.kr`. Crawls the ECOS catalogue tree, captures the Financial-Account item-code hierarchy (the `BOPF…` 12-char keys + `BOPO…` Errors & Omissions codes). Headed only because corp TLS resets on the ECOS edge.
- **`discovery/`** — captured tree dumps under `discover_bop_{TIMESTAMP}/`.
- **`stat_code_inventory.md`** — full ECOS STAT_CODE inventory by branch (Current Account, Capital Account, Financial Account, IIP, FX reserves, customs trade, national accounts, policy rates). Source of truth for `tblId` candidates fed into [`../kosis_kr_coverage_plan.md`](../kosis_kr_coverage_plan.md).

## Why keep it

- KOSIS sometimes lags BOK on bleeding-edge revisions. If we ever need same-day data, ECOS direct is the only path.
- BoP item-code structure (`BOPF…` Financial Account assets/liabilities, `BOPO…` E&O) is non-obvious from KOSIS URLs alone — `stat_code_inventory.md` is the decoder ring.

## Related

- [`../ecos_api_reference.md`](../ecos_api_reference.md) — ECOS Open API, STAT_CODE namespaces, dual ITEM_CODE structure
- [`bop.md`](bop.md) — BPM6 framework + Korea's BoP composition (uses these codes)
- [[korea-mods-no-bop]] — MODS does NOT carry BoP; don't scaffold MODS-based BoP fetchers
