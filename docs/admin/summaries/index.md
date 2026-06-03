# Topic Summaries — Playbook & Outputs

Last updated: 2026-06-03

This directory holds the **playbook** for producing topic-level deep-dives
(macro-thematic briefings, schema-anchored explainers, single-asset
storyboards) and the **conventions** that govern where the resulting
outputs live.

The deliverable kind here is the *thematic report*: starts with a
one-screen TL;DR that a PM can eyeball, then provides as much appendix
detail as is needed to back every claim. The point is to package one
specific question into one re-readable artifact.

## What's in this section

- **[deep_dive_playbook.md](deep_dive_playbook.md)** — The seven-stage
  workflow + quality checklist + output anatomy. Read this **before**
  starting any deep-dive request.
- **[output_template.md](output_template.md)** — The TL;DR + appendices
  skeleton to drop into `docs/topics/{topic}.md`.

## Worked example

The [Korea Capital Account Outflow](../../topics/korea_capital_outflow.md)
report (2026-06-03) is the reference output produced by this playbook.
It demonstrates:

- Authoritative definition (under BPM6) anchored to BOK source-agency metadata
- 5-component composition table tying to actual ECOS `BOPF…` item codes
- Live numbers from KOSIS + FRED + 12 sell-side desk reports
- Clean separation of TL;DR (one screen) and appendices (B/C/D)
- Honest gotcha calls (translation, gaps, blocked API)

When in doubt about scope or shape, mimic that file.

## When to use this playbook

A user request triggers this workflow when **all of**:

1. The question is a *topic*, not a *task* (not "fix X", not "implement Y")
2. The answer is **not already in `docs/`** — if it is, just point to that file
3. The answer is **substantive** — fits one or more screens of useful content, not one line
4. The answer combines multiple sources — statistical data + agency definitions + sell-side desk views, or similar

If a user asks "*what is X and what is it composed of*", "*explain Y*",
"*do a deep dive on Z*", "*summarise our coverage of W*" — this is the
shape. See [deep_dive_playbook.md](deep_dive_playbook.md) §1 for the
trigger taxonomy.

## Where outputs land

| Output | Location | Notes |
|---|---|---|
| The thematic report | `docs/topics/{topic_slug}.md` | The deliverable. Always front-loaded with a one-page TL;DR. |
| Discovery artifacts (Playwright captures, raw downloads, code probes) | `playground/{domain}/{vendor}/discovery/` | Per the project's PLAYGROUND-ONLY rule. Never in `docs/`. |
| Source-agency reference (schema, codes, API) | `docs/admin/vendors/{vendor}/` | For permanent vendor-level facts (item codes, auth paths, gotchas). |
| Data pulled during the deep-dive | `playground/{domain}/{vendor}/sample_output/{YYYY}/{MM}/{DD}/` | Parquet + raw downloads. Not committed unless small. |
| Memory entries (rules-of-thumb the deep-dive surfaced) | `~/.claude/.../memory/` | One-line nuggets future sessions need; not in repo. |
