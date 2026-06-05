# RBI exploration artifacts — `playground/econ/rbi_explore/`

**Status:** Discovery artifacts. No active scripts.

Archive of screenshots + HTML DOM snapshots from RBI DBIE Playwright probe runs (dated 2026-06-02). Reference-only — the active probe scripts live next door at `playground/econ/rbi/`.

## Contents

- **`snapshots.jsonl`** — record-store of probe-run state.
- **`screenshots/`** — timestamped PNG screenshots from Playwright runs.
- **`pages/`** — timestamped HTML DOM snapshots.

## Why keep it

When DBIE migrates to CIMS (no firm date), comparing the old DOM/screenshots to the new will help identify which menu paths moved. Without these snapshots, we'd be re-probing from scratch.

## Related

- [`rbi.md`](rbi.md) — the active probe scripts
