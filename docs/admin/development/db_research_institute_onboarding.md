# DB Research Institute (`dbresearch.com`) — follow-up onboarding

**Status**: Deferred — captured during the main DB onboarding (2026-06-01)
so the information surfaced in Phase 1 isn't lost. Not currently
scheduled.

**Parent initiative**: [`db` research vendor onboarding](../research/scrapers/db.md).

---

## Why this is separate

During Phase 1 exploration of the Deutsche Bank research scraper
(2026-06-01), the operator's browsing surfaced a second DB-owned
research property at `www.dbresearch.com`. It has a **completely
different URL scheme** from `research.db.com` and is positioned as the
"Deutsche Bank Research **Institute**" — longer-horizon thought
leadership, mega-trend pieces, ESG, demographics — not the analyst
desk research flow that `research.db.com` carries.

Treating it as a separate vendor (`db_institute`) per the playbook's
"one portal per vendor code" convention keeps audits, classifier
mapping, and dim_vendor accounting clean. The main `db` vendor
onboarding (the analyst-desk firehose) is the priority; this Institute
site is a smaller, slower-cadence add-on for after `db` is live.

---

## What we already know (preserved from Phase 1 snapshots)

Captured in [`playground/research/db_explore/`](../../../playground/research/db_explore/),
snapshots indexed via `snapshots.jsonl`. The following snapshot URLs
are from the Institute site (everything not starting with
`research.db.com`):

```
https://www.dbresearch.com/PROD/IE-PROD/HOME.alias
https://www.dbresearch.com/PROD/IE-PROD/Macro__Research_Institute/RI_MAC.alias
https://www.dbresearch.com/PROD/IE-PROD/PROD0000000000628951/Themes_and_trades_for_the_summer.xhtml
https://www.dbresearch.com/PROD/IE-PROD/PDFVIEWER.calias?pdfViewerPdfUrl=PROD0000000000629103&rwnode=REPORT
```

### URL patterns observed

| Kind | Pattern |
|---|---|
| Home | `https://www.dbresearch.com/PROD/IE-PROD/HOME.alias` |
| Topic landing | `https://www.dbresearch.com/PROD/IE-PROD/{Topic}__Research_Institute/RI_{TAG}.alias` (e.g. `Macro__Research_Institute/RI_MAC.alias`) |
| Article (HTML view) | `https://www.dbresearch.com/PROD/IE-PROD/{PROD_ID}/{slug}.xhtml` |
| PDF viewer | `https://www.dbresearch.com/PROD/IE-PROD/PDFVIEWER.calias?pdfViewerPdfUrl={PROD_ID}&rwnode=REPORT` |

`{PROD_ID}` is a fixed-width identifier like
`PROD0000000000628951` — 20 chars, zero-padded incrementing number,
**not** the Crockford-ULID format used on `research.db.com`. Suggests
a different backend product / CMS entirely.

The `.alias` / `.calias` extensions and `IE-PROD` path segment
strongly suggest an older Java EE / WebObjects-style alias router
(maybe a SiteMinder-fronted CMS). The page slugs are URL-encoded
double-underscore (`__`) separated.

### Auth

The operator was already authenticated when the Institute pages
loaded — same SSO cookie blanket. If the production scraper inherits
the `db` persistent profile, auth should work transparently; if not,
a separate `C:/IMDR_LOCAL/research_profiles/db_institute/` may be
needed.

### Cadence (hypothesised)

Thought-leadership pieces tend to be ~weekly to monthly; expected
daily volume <<1 per day. The Institute site likely won't move the
needle on coverage but is worth ingesting for the strategic/macro
mega-trend angle the desk-research firehose doesn't cover.

---

## Decision when this resumes

1. **Confirm scope** with the user: is the Institute material
   actually wanted in the IMDR research RAG, or does the desk
   already get this via other channels?
2. **Probe listing API** the same way as Phase 2 of the main
   playbook. The `PROD0000000000{nnnnnn}` ids strongly imply a
   different backend → almost certainly a different listing endpoint
   from `research.db.com`.
3. **Spawn a fresh playbook pass** — new vendor code `db_institute`,
   new entry in `vendors.yml`, separate `scrapers/db_institute.md`.

---

## Action

When promoting `db` to production (Phase 7 of the main playbook),
revisit this doc and either:

* file a Linear issue under the `research` label to schedule the
  Institute onboarding, **or**
* if the desk doesn't want it, mark this doc *abandoned* and delete
  with a short rationale.

Either way: don't let the Phase-1 information rot. The snapshots in
`db_explore/` will eventually be cleaned up; the URL patterns above
are the durable record.

---

## References

* Main `db` scraper doc: [`docs/admin/research/scrapers/db.md`](../research/scrapers/db.md)
* Vendor registry entry: [`playground/research/vendors.yml`](../../../playground/research/vendors.yml) (look for the `db:` block)
* Phase-1 snapshots: [`playground/research/db_explore/`](../../../playground/research/db_explore/)
* Onboarding playbook: [`docs/admin/research/onboarding_new_vendor.md`](../research/onboarding_new_vendor.md)
