# CREDIT + BOFA

**Running dev-doc.** Started 2026-07-16. Owner: Arjun. Status: **Fold 1 (JPM/Barclays/DB credit recall) + Fold 2a (BofA LIVE, verified) COMPLETE & committed (`149304e`, `c4204c9`). Fold 2b (email revival) OPEN.**

Two-fold initiative:
- **Fold 1 — Credit capture (recall).** Stop dropping single-name / issuer-level credit research across the live portal vendors. Priority = recall (accept noise); the reference corpus for "what good looks like" is the PM library `Z:\Business\Research\Credit` (country → issuer → instrument-theme). Kicked off by JPM `GPS-5333786-0` = QBE Insurance single-name note.
- **Fold 2 — Coverage & plumbing.** (2a) Bring BofA — a dedicated credit house — online via the portal (blocked on MFA login). (2b) Revive the email/desk-commentary channel (stalled 2026-06-29). **Emails are worked last, per instruction.**

> Linear: this needs an `IMD-` project (imdr-pm to file). This markdown is the durable design/context per the dev-doc convention.

---

## 1. Ground truth (verified 2026-07-16, from logs + files)

| Channel | Script | Cadence | State |
|---|---|---|---|
| **Portal** | `playground/research/ingest_today.py` | every 3h (0130…2230) | ✅ **healthy** — 14 vendors, running today |
| **Email** | `playground/research/ingest_outlook.py` (`--load`, conda env) | separate scheduled job | ⛔ **stalled since 2026-06-29** (all 11 email vendors) |
| **BofA portal** | `crawler_bofa.py` / `crawler_bofa_firehose.py` | — | ⛔ **not wired** into orchestrator (PROD-HOLD, MFA) |

Portal orchestrator vendor list (from `logs/research_ingest_20260716_1630.log` header) — **no bofa, no email**:
```
anz, barclays, bnp, citi, db, goldman, hsbc, jpm, ms, nomura, socgen, stanc, ubs, westpac
```
Proof portal is live: `…/2026/07/16/barclays/` has 11 PDFs incl. credit (*Asia Credit Alpha*, *Macro Credit Views: iTraxx*, *Emerging Asia Sovereign Credit: Pakistan*) — these are the allowlist-**kept** barclays credit; the same run shows `[DROP] equity-vendor-default-drop:barclays` lines.

**Correction to earlier claim:** "BofA is live via email" was wrong — email was already stalled, and BofA email carries FX/macro/rates desk chatter with **zero credit** (see `bofa.md` status note, updated 2026-07-16).

---

## 2. Reference paths

| Thing | Path |
|---|---|
| Portal orchestrator | `playground/research/ingest_today.py` |
| Email orchestrator | `playground/research/ingest_outlook.py` (+ `playground/research/outlook/README.md`) |
| Daily run logs | `logs/research_ingest_{YYYYMMDD}_{HHMM}.log` (per-run summary) |
| Per-vendor run logs | `playground/research/logs/ingest_today/{YYYYMMDD}/{vendor}.log` |
| **Credit dry-run harness** | `playground/research/_dry_credit.py` (no fetch/parse/load) |
| Relevance filter | `playground/research/ingest/relevance.py` |
| Discovery filters | `playground/research/ingest/filters/{vendor}.py` |
| Classifiers | `playground/research/ingest/classifiers/{vendor}.py` |
| Crawlers | `playground/research/ingest/crawler_{vendor}.py` |
| BofA login | `playground/research/ingest/login_bofa.py` |
| Outlook client | `src/imdr/vendors/sessions/outlook.py` (`Win32OutlookClient`) |
| Portal PDF output (OneDrive→SharePoint) | `C:\Users\adoshi\OneDrive - RV Capital Management Private Ltd\Trade Knowledge Core - IMDR\{YYYY}\{MM}\{DD}\{vendor}\` |
| Playwright profiles | `playground/research/profiles/{vendor}` |
| **PM credit corpus (READ-ONLY)** | `Z:\Business\Research\Credit` (country/issuer/theme; multi-vendor + `.msg`) |
| Vendor scraper docs | `docs/admin/research/scrapers/{vendor}.md` |
| Python / env | `C:/Users/adoshi/.conda/envs/imdr/python.exe`; `PYTHONDONTWRITEBYTECODE=1`; `.env` keys `IMDR_RESEARCH_{VENDOR}_USERNAME/PASSWORD` (JPM also `IMDR_RESEARCH_JPM_USERNAME` → `janus_user`) |
| DB | `research.dim_report`, `research.fact_chunk`; `dbo.dim_vendor` (jpm=16, bofa=42) |

**Run the dry-run harness:**
```bash
PYTHONDONTWRITEBYTECODE=1 C:/Users/adoshi/.conda/envs/imdr/python.exe \
  playground/research/_dry_credit.py --vendors jpm --days 4 --show credit
# --show all | credit | credit+eq ; --since/--until YYYY-MM-DD ; loads repo .env
```

---

## 3. Credit dry-run findings (4-day window 2026-07-12 → 07-16, all 14 live vendors)

| Vendor | Discovered | CREDIT kept | CREDIT dropped | eq-1name | Bottleneck layer |
|---|--:|--:|--:|--:|---|
| jpm | 903 | 65 | **39** | 303 | relevance + discovery |
| barclays | 184 | 33 | **17** | 0 | relevance |
| db | 147 | 12 | **8** | 3 | relevance |
| citi | 414 | 10 | 0 | **207** | classifier (credit→eq) |
| goldman | 503 | 15 | 0 | 3 | (ok) |
| ms | 123 | 6 | 0 | 0 | classifier |
| ubs | 124 | **0** | 0 | 0 | classifier (no credit) |
| nomura | 65 | **0** | 0 | 0 | classifier (no credit) |
| hsbc | 17 | 1 | 0 | 0 | discovery scope |
| socgen / stanc | 27 / 14 | 2 / 2 | 0 | 0 | low volume |
| bnp / anz / westpac | 24 / 28 / 22 | **0** | 0 | 0 | classifier / low vol |

**Three failure modes** (the "each vendor's credit rules" answer):
1. **Relevance keep-allowlist default-drop** — kills named-issuer credit we want. Only JPM/Barclays/DB.
2. **Classifier has no/narrow CREDIT bucket** — UBS/Nomura/BNP/ANZ/Westpac → 0 credit; Citi funnels credit into single-name EQUITY (then dropped). Structural.
3. **Discovery gate (JPM)** — `isResearch=N` kills desk credit before classification; `noise:chart-pack` kills credit data products; `cjk` kills JP names.

---

## 4. FOLD 1 — Credit capture (code review + exact changes)

### 1a. Relevance keep-allowlists → keep-by-default  *(highest value, lowest risk)*
File: `playground/research/ingest/relevance.py`. Function `is_single_name_equity(vendor_code, result, title)`.

| Vendor | Current logic (lines) | Regexes | Change |
|---|---|---|---|
| **JPM** | 707–715 | `n_tickers==1`→drop; `_JPM_INDUSTRY_DROP` (64–93)→drop; `_JPM_CREDIT_KEEP` (111–124) else `credit-vendor-default-drop` | Remove `n_tickers==1` drop; flip terminal branch to **keep** (`return False`); retain `_JPM_INDUSTRY_DROP` + admin/event drops |
| **DB** | 688–691 | `_DB_CREDIT_KEEP` (155–162) else `credit-vendor-default-drop` | Flip to keep-by-default; retain an industry/admin drop |
| **Barclays** | 676–679 | `_BARCLAYS_CREDIT_KEEP` (388–512) else `credit-vendor-default-drop:barclays`; `_BARCLAYS_CREDIT_SINGLE_NAME` (318) | Flip to keep-by-default; retain industry/admin drop |

Dry-run recovers: JPM 39 (9 `:1-ticker` — BofA/GS/WFC/Citi/MS/PNC/Zhongsheng/Amprion/Ashton Woods; 5 `:industry`; 25 default incl. APAC Credit Roundup, Asia Credit Analytics, Indonesian Credit, Curveball HG Credit Curve). Barclays 17 (ZIGGO, Schaeffler, Baker Hughes, HCA, IBM, Thames Water, Indika). DB 8 (Antolin, Stonegate, Ubisoft, Goodyear, Modulaire).
Validation: `_dry_credit.py --vendors jpm,barclays,db --days 4` before/after; write/extend tests (see `playground/research/test_*relevance*`); forward-only.

### 1b. Classifier credit-blindness  *(needs per-vendor probe)*
Files: `playground/research/ingest/classifiers/{ubs,nomura,bnp,anz,westpac,citi}.py`. Each references CREDIT but emits ~0 in the window. Step: `_dry_credit.py --vendors ubs --days 4 --show all` to see what credit-looking titles get tagged (UBS emits only EQUITY/MACRO/RATES/FX/ESG/STRATEGY; Nomura only EQUITY/FX/MACRO/RATES; Citi → 207 single-name EQUITY). Then confirm each vendor exposes corporate credit via the scraped hub and add/repair the CREDIT mapping so issuer credit isn't mis-dropped as equity. Open per-vendor.

### 1c. JPM discovery `isResearch=N` bypass
File: `playground/research/ingest/crawler_jpm.py`. `_unfetchable_reason` (402–418): line 416 keeps titles matching `_MACRO_DESK_KEEP` (imported line 66 from `filters/jpm.MACRO_DESK_KEEP`), else 418 returns `"isResearch=N"`. Extend `MACRO_DESK_KEEP` in `filters/jpm.py` with credit-desk patterns (EM Credit Rundown, EMEA Sovereign Repo, iTraxx Index Vol Commentary). Lower priority than 1a.

---

## 5. FOLD 2 — Coverage & plumbing

### 2a. BofA portal (dedicated credit house — currently NOT wired)
DB: `dim_vendor.bofa=42`; 189 portal rows from June smoke incl. **8 CREDIT** (only channel that ever carried BofA credit). Code all built + Phase-8 complete (`docs/admin/research/scrapers/bofa.md`).

Touch-point state (verified 2026-07-16):
- `ingest_today.py:119` (import) + `:163` (`VendorSpec`) — **still commented** ← the only remaining gate.
- `classifiers/__init__.py:38` (`_VENDOR_CODES`) + `:61-63` (dispatcher) — **already active** ("LIVE 2026-06-22").
- `pipeline.py:36,196` (`fetch_bofa_pdf` dispatch) — **already active**.

Blocker: **MFA on portal login** (observed 2026-06-15). `login_bofa.py` `login()` (95–169; MFA would surface at the failure check 156–164) has no MFA handler; no vendor has a working email-OTP poll (Barclays' is a stub; every loginflow's policy is "revert to manual on MFA"). `Win32OutlookClient` (`src/imdr/vendors/sessions/outlook.py`) only extracts *links*, not codes — needs a code-reader.
**Hard dependency:** no BofA OTP email exists in the mailbox to reverse-engineer sender/subject/format (searched `ml.com`/`baml.com`/"Mercury/portal token"/"verification code" back to June — none). Capturing the format needs **one live portal login with the user present**. Ongoing cost: unattended daily login would need a fresh OTP each run.
Also decide: `crawler_bofa.py` (hub, ~6/day) vs `crawler_bofa_firehose.py` (~14/day) vs both (dedup by `report_id`). Credit hubs: `high-grade`, `high-yield-distressed`, `em-corporate-credit`, `credit-strategy-americas`, `mbs`, `municipal`.

### 2b. Email channel revival  *(EMAILS LAST)*
File: `playground/research/ingest_outlook.py` (dry-run by default; `--load` runs full pipeline in conda env). Separate from the portal orchestrator. **Stalled 2026-06-29** — last email-sourced `dim_report` row across all 11 email vendors (goldman/anz/nomura/ms/hsbc/jpm/db/stanc/citi/westpac/bofa). CBA + CACIB held out. Diagnose the stopped scheduled task / broken Outlook auth. Note: for BofA this only restores FX/macro/rates desk commentary, **not** credit.

---

## 6. Task checklist

- [x] **1a** Relevance keep-by-default for JPM/Barclays/DB CREDIT — **DONE 2026-07-16** (`relevance.py` `_CREDIT_ADMIN_DROP` + unified keep-by-default branch; 193 tests pass; dry-run before→after JPM 65→108 kept / 39→2 drop, Barclays 33→54 / 17→0, DB 12→19 / 8→1; only admin/calendar drops remain). Live on next 3-hourly run; not yet git-committed.
- [x] **1b** Classifier credit-path probe — **DONE 2026-07-16, mostly a non-issue.** `--show all` on UBS/Nomura/Citi: the "0 credit / 207 eq-1name" is largely correct. UBS credit-keyword hits are genuine EQUITY (sector/stock); Citi's 207 eq-1name are real single-stock equity (Citi credit already tags CREDIT=10); Nomura's only real mis-tag is **"Securitized Products" → RATES (should be CREDIT)**, ~1/window. No large credit hiding behind mislabels. → **Optional small fix**: map securitized/ABS/CLO/CMBS → CREDIT in `classifiers/nomura.py` (low value). Skip UBS/Citi classifier work. UBS corporate-credit *discovery-scope* (is there an un-scraped Neo credit hub?) is a separate, deferred question.
- [x] **1c** JPM `isResearch=N` credit-desk bypass — **DONE 2026-07-16**. Extended `filters/jpm.py MACRO_DESK_KEEP` with `macro credit | performing credit | credit rundown | itraxx | sovereign repo`; `_unfetchable_reason` now keeps EM Credit Rundown, EMEA/NA Macro Credit Weekly, Macro Credit Perspectives Call, Performing Credit (IG/HY), iTraxx Vol Commentary, EMEA Sovereign Repo. +7 keep-tests in `test_jpm_unfetchable.py`; 150 JPM tests pass. Live-in-working-tree (gitignored).
- [x] **2a** BofA portal — **COMPLETE & LIVE, verified 2026-07-17.** Second factor = **email security token** (`bofamarkets@bofa.com`, subject "BofA Mercury Portal Token", 8-digit, 5-min, Outlook `Research\BOFA`). `login_bofa.py`: `_resolve_post_submit` handles token page (→ `_read_portal_token` via `asyncio.to_thread`, attempt-scoped freshness, poll-continues-on-miss → `_submit_token`) AND trusted-session direct landing (positive `_title_is_home` check). Credit hubs keep-by-default (`crawler_bofa._drop_reason` + `filters/bofa.credit_hub_drop_reason` relaxed). Wired firehose-only, `auth_realm=rv-pingfed`. Code-reviewed (4 blocking login bugs fixed) + tests. **Verified in the scheduled cycle**: unattended login OK, 64 ins/0 fail, `smoke_bofa_retrieval.py` 3/3. Committed `c4204c9`. Residual noise (accepted, recall-first): event-invites + MBS data-packs may leak — tune later.
- [ ] **2b** Email channel revival (diagnose `ingest_outlook.py` stall) — LAST
- [ ] Docs: verify `outlook_email_channel.md` live-claim; keep `bofa.md` status current
- [ ] File Linear `IMD-` project (imdr-pm)

---

## 7. Changelog
- **2026-07-17 (d)** — **Fold 2a VERIFIED LIVE + code-review hardening.** Scheduled 13:30 cycle ran BofA unattended ("login OK" — reworked MFA login works headless), inserted 64/0-failed (66 discovered, filter_removed=0), all asset classes incl. CREDIT. `smoke_bofa_retrieval.py` **3/3 PASS** (Qdrant). 64 PDFs uploaded (spread by publish_date 07/14-17). imdr-code-reviewer found 4 blocking login bugs (event-loop block, weak landed check, token freshness race, poll-abort-on-miss) — all fixed; +`test_bofa_credit_relax.py`, 23 stale `test_bofa_filters.py` tests flipped to keep-by-default; 284 tests pass. Committed `c4204c9`.
- **2026-07-17 (c)** — **Fold 2a: BofA WIRED LIVE.** `ingest_today.py` registers `bofa` via `crawler_bofa_firehose` with `auth_realm="rv-pingfed"`. Orchestrator smoke (`EMBED=false LIMIT=2`) inserted `dim_report` ids 19325-6 (fetch→parse→chunk→OneDrive→DB, 0 failed). Added `smoke_bofa_retrieval.py`. Flipped `vendors.yml` probe→production, `index.md` + `bofa.md` PROD-HOLD→LIVE (went through bofa.md line-by-line). Embed+Qdrant+retrieval finish on the next scheduled `--embed` cycle. Op-note: ~8 BofA logins/day (one token email each) — reduce cadence if fraud-flagged.
- **2026-07-17 (b)** — **Fold 2a: end-to-end DOWNLOAD proven + credit-drop relaxed.** Relaxed `crawler_bofa._drop_reason` (keep single-name issuers in `credit_*` hubs) + `filters/bofa.credit_hub_drop_reason` (keep-by-default). Single live test (`_test_bofa_download_e2e.py`, firehose, EM Credit + Credit Strategy, 1 login): discovered **10 credit refs** (Indonesia sovereign call, quasi-sovereign cross-asset, Türkiye electricity, 1H26 labelled-bond issuance, "Who's got credit in 2H?"), fetched a real PDF via SAML (`%PDF-1.5`, 183KB, verified content = BofA Global Research "Asia Gaming" note). **Not wired** into orchestrator (per decision). Noise note: BofA event-invites (Conference/Expert call) now leak through credit keep-by-default — tune later. Crawler choice: **firehose only**.
- **2026-07-17** — **Fold 2a: BofA MFA login SOLVED.** Second factor = emailed 8-digit security token (`bofamarkets@bofa.com` → Outlook `Research\BOFA`). Added `_read_portal_token` (win32com poll of `Research\BOFA`), `_is_token_page`, `_submit_token`, `_resolve_post_submit` to `login_bofa.py`. `_resolve_post_submit` handles BOTH outcomes — trusted-session direct-to-home (no token) AND the token challenge (with render-lag tolerance). E2E live test passed (`is_authenticated=True`, Home - BofA Markets). Caution honoured: single live test, no rapid re-login. Remaining: prod-wiring OK, `filters/bofa.py` single-name relaxation for credit hubs, hub-vs-firehose.
- **2026-07-16 (d)** — **Fold 1c shipped to working tree.** `filters/jpm.py MACRO_DESK_KEEP` extended with credit-desk patterns; `test_jpm_unfetchable.py` +7 keep-tests; 150 JPM tests pass. Fold 1 (credit recall on live portal) now COMPLETE (1a+1b+1c). Next: Fold 2a BofA (needs live login).
- **2026-07-16 (c)** — **Fold 1b probed → mostly a non-issue.** `--show all` on UBS/Nomura/Citi shows the credit-blindness doesn't lose material credit (those houses publish equity/macro/rates in scope; real credit is tiny or already tagged). Only genuine mis-tag: Nomura Securitized Products→RATES. Fold 1a committed (`149304e`, branch `research/credit-single-name-1a`) — tracked artifacts only; the gitignored `relevance.py` change is live-in-working-tree. Re-prioritised: real remaining credit levers are 1c (JPM `isResearch=N` desk bypass) + Fold 2a (BofA, the dedicated credit house).
- **2026-07-16 (b)** — **Fold 1a shipped to working tree.** `relevance.py`: retired the JPM/DB/Barclays credit keep-allowlists + single-name/industry drops; added `_CREDIT_ADMIN_DROP` + a unified keep-by-default CREDIT branch. Tests: flipped `test_barclays_credit_single_name_drops`→`_now_keeps`, added `test_jpm_credit_relevance.py`, added Barclays admin-drop test — **193 pass**. Dry-run confirms recovery (see checklist 1a). EQUITY path untouched. Not git-committed yet.
- **2026-07-16** — Doc created. Investigation complete: portal healthy (14 vendors/3h), email stalled 06-29 (separate `ingest_outlook.py`), BofA not wired (MFA). Dry-run harness `_dry_credit.py` built + run across 14 vendors; 3 failure modes identified. `bofa.md` stale "email is live source" line corrected. Nothing shipped to prod filters yet.
