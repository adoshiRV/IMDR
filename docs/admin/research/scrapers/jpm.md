# J.P. Morgan — Markets research scraper

Status: **NOT YET BUILT** — explorer wrapper in place; waiting on
JPM portal credentials, then capture snapshots.

## Portal

| | |
|---|---|
| Hostname | `markets.jpmorgan.com` |
| SSO | redirect via `nwas.jpmorgan.com` (observed in audit) |
| Username | `<JPM_USERNAME>` (audit-derived; not in `.env` yet) |

The pre-existing playwrights profile (`Z:\...\playwrights\jpm-playwright`)
showed 102 visits to `markets.jpmorgan.com` — well-used but no
Chrome-saved password. We use a fresh profile under
`playground/research/profiles/jpm/`.

## Profile

```
playground/research/profiles/jpm/
```

## To do

1. Add `IMDR_RESEARCH_JPM_*` entries to `.env` (URL, username,
   password) once IT confirms credentials.
2. Run `python playground/research/explore_jpm.py`. Complete the
   SSO/MFA dance interactively. Capture snapshots of: post-login
   landing, research home, per-asset-class pages, one actual report.
3. Inspect `playground/research/jpm_explore/snapshots.jsonl` and
   saved HTML to identify URL/DOM patterns.
4. **Fill in this doc** with: URL patterns, DOM structure, fetch
   strategy, hub URL list, quirks.
5. Build `crawler_jpm.py` + `ingest_today_jpm.py`.
6. Seed `dbo.dim_vendor`:
   ```sql
   INSERT INTO dbo.dim_vendor
       (vendor_code, display_name, vendor_type, is_active, created_at, updated_at)
   VALUES ('jpm', 'J.P. Morgan', 'web', 1, SYSDATETIMEOFFSET(), SYSDATETIMEOFFSET());
   ```

## Sections to fill in

See [`goldman.md`](goldman.md) / [`anz.md`](anz.md) for the structure
this doc should adopt once patterns are confirmed.
