# RBNZ — `playground/econ/rbnz/`

**Status:** Discovery only. Not loaded. **Playwright required** (Akamai/Cloudflare-style JS challenge).

Reserve Bank of New Zealand. XLSX/CSV statistical tables behind a 403 barrier without browser-context cookies.

## Contents

| File | Purpose |
|---|---|
| `explore.py` | Source discovery — live-verifies RBNZ statistics URLs. |
| `probe_via_playwright.py` | One-shot Playwright probe to discover real XLSX/CSV URLs behind 403 barriers. |
| `discovery/findings.md` | "RBNZ Source-Discovery Findings". |
| `discovery/findings_raw.json` | Raw discovery output. |
| `profile/` | Chromium persistent context (for the JS-challenge bypass). |

## Transport

Playwright + persistent profile. Plain `httpx` GET = 403. Headed Playwright with persistent context → real URLs. Same pattern as RBA — see [`../../australia/_playground/rba.md`](../../australia/_playground/rba.md).

## Why Playwright

`probe_via_playwright.py` docstring: "Playwright's persistent context + Chromium" — JS challenge layer (likely Akamai or Cloudflare Bot Manager) gates the XLSX/CSV URLs. No JSON API.

## Next moves

1. Build a stable XLSX→parquet pipeline (each RBNZ table has its own header layout).
2. Wire into canonical loader: `python -m scripts.migrations.load_econ_indicator_from_playground --vendor rbnz`.
3. **Anti-detection guardrail** ([[feedback-no-anti-detection-research]]): don't add stealth plugins or aggressive parallelism. If profile breaks, warm a fresh one — don't evade.

## Coverage potential

RBNZ tables cover:
- OCR (Official Cash Rate)
- Government bond yields by tenor
- Wholesale + retail interest rates
- FX rates incl. TWI
- Monetary + credit aggregates

## Related

- [`statsnz.md`](statsnz.md) — sibling NZ vendor (real-economy side)
