# KOSIS UI exploration — `playground/econ/kosis_explore/`

**Status:** Discovery artifacts. No active fetcher.

Playwright snapshot sandbox used during KOSIS onboarding to figure out the UI flow before the OpenAPI was wired. Kept for reference; no production code depends on it.

## Contents

- **`snapshots.jsonl`** — Playwright page-state snapshots.
- **`pages/`** — captured HTML DOM.
- **`screenshots/`** — timestamped PNGs.

## Why keep it

If KOSIS introduces a new download form variant or the OpenAPI gets a new endpoint we can't reverse-engineer from docs alone, this is where we'd add new probe runs. The active capture script lives at `playground/econ/kosis/capture_download.py`.

## Related

- [`kosis.md`](kosis.md) — the live OpenAPI fetchers
- [`../kosis_openapi_reference.md`](../kosis_openapi_reference.md) — endpoint reference
