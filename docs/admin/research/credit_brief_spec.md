# Credit Brief — spec (single-name issuer credit memo)

The **Credit Brief** is a ~2-page internal credit memo on **one issuer**, written
for an international bond credit analyst, **as a credit investor**. It is authored
by the [`credit`](../../../.claude/agents/credit.md) sub-agent, who produces
**grounded markdown only** — rendering is deferred to [Picasso](../../../.claude/agents/picasso.md)
(no credit-memo house look exists yet; ship the MD).

Where Mercator/Smith work the country-macro layer and explicitly refuse to call
direction, the Credit Brief is different: a credit analyst is **paid to conclude** —
the memo ends with an explicit **credit view** (rating trajectory, spread/relative
value, where to sit in the capital structure). The view is still grounded — every
number and every desk attribution traces to a source.

---

## 1. The deliverable

A single issuer, decomposed the way a buy-side credit analyst decomposes a name
before deciding whether to own its bonds (and where in the cap structure). Two
A4 pages of dense, cited prose + tables. It answers, at minimum:

1. **Strengths & weaknesses** of the credit
2. **Competition** — market position + sector context
3. **Credit profile** — the balance sheet + the fundamentals
4. **Profit matrix** — the profitability decomposition (margins, returns, trend)
5. **Debt profile** — capital structure, maturity wall, subordination
6. **History** — what the issuer is, how it got here, the inflection points

…plus the three comparison lenses the user named: **balance sheet**, **sector
comparison**, and **peer- ("pair-") group comparison**.

It is a **credit** memo, not an equity note: no equity price targets, no
per-share anything. The question is always *"do I get paid back, and am I paid
enough for the risk — and where in the stack?"*

---

## 2. Two tracks — pick one per issuer (universal-adaptive)

Bank/insurer credit and corporate credit are decomposed with **different ratios**.
Determine the issuer type first, state which track you are on in the snapshot, and
do not force corporate metrics onto a financial (or vice-versa).

| | **Corporate track** (non-financial) | **Financials track** (banks / insurers) |
|---|---|---|
| **Leverage / capital** | Gross & Net Debt / EBITDA; Debt / (Debt+Equity) | Banks: CET1, Tier-1, Total Capital, leverage ratio. Insurers: solvency / PCR ratio |
| **Coverage / earnings quality** | EBITDA / Interest; EBIT / Interest; FFO / Debt | Banks: NIM, cost/income, PPOP. Insurers: combined ratio, investment yield |
| **Cash / asset quality** | FCF, FCF / Debt, capex intensity, working-capital swing | Banks: NPL ratio, coverage ratio, cost of risk, Stage-2/3. Insurers: reserve adequacy |
| **Liquidity** | Cash + undrawn RCF vs ST maturities | Banks: LCR, NSFR, LDR, deposit mix, wholesale reliance. Insurers: liquid-asset cover |
| **Returns** | ROIC, ROCE | ROE, ROA, ROTE |

Shared across both tracks (always covered): **ratings + outlook** (all three
agencies where rated), **capital structure & subordination**, **maturity
profile / refinancing wall**, **currency mix of debt**, **covenants / structural
features**, **event & ESG risk**, **parent / sovereign linkage**.

---

## 3. Section spine (fixed order)

The memo is a fixed 9-section spine. Keep it to ~2 A4 pages — dense, not padded.

**Page 1**
- **Masthead** — issuer name + a one-line **credit thesis** (the call in a sentence).
- **§0 Snapshot box** — sector · country · issuer type + **track** · approx. size
  (revenue/assets) · **ratings** (Moody's / S&P / Fitch + outlook) · key benchmark
  instrument(s) & where they trade (spread/yield, if sourceable) · **bottom-line
  credit view** (one line).
- **§1 Business & history** — what they do, how they make money, ownership /
  group structure, the inflection points that made the credit what it is today.
- **§2 Strengths & weaknesses** — credit-relevant, two columns, ranked. Not a
  generic SWOT — every bullet must bear on ability/willingness to service debt.
- **§3 Competition & sector position** — market position, named competitors,
  sector structure and cycle, and the **sector comparison** (how the issuer's key
  credit metrics sit vs the sector median/aggregate).

**Page 2**
- **§4 Credit profile & profit matrix** — the balance sheet + the fundamentals on
  the chosen **track** (§2 table). The **profit matrix** lives here: a compact
  table of revenue / earnings / margins / returns over ≥3 periods showing the
  **trend**, not a single snapshot. State reported-vs-adjusted and whose
  adjustment.
- **§5 Debt profile & capital structure** — the cap-structure ladder (secured →
  senior unsecured → sub / T2 / AT1 / hybrids / equity), the **maturity wall**
  (refinancing schedule), currency mix, covenants / structural subordination,
  and the **key decision for a bond analyst: where in the stack to sit**.
- **§6 Peer- ("pair-") group comparison** — a table of the issuer vs 3–5 **named**
  closest comparables (same sector / region / rating band) on the track's key
  metrics **+ ratings + where the bonds/CDS trade**. This is the relative-value core.
- **§7 Sell-side desk views** — what the banks are saying, **cited**. Blend
  portal corpus + the PM credit library + emails/desk commentary. Note agreement
  and dispersion; name the house on every view.
- **§8 Credit view** — the synthesis, as a credit investor: rating trajectory
  (upgrade/stable/downgrade path + triggers), spread / relative-value read (rich
  or cheap vs peers and vs its own history/rating), **recommended stance and
  instrument** (which bond / which point on the curve / which cap-structure layer;
  or CDS), and the **top 3–5 risks & catalysts to watch**.
- **§ Sources** — appendix; every number and every attribution traced (see §6 below).

---

## 4. Grounding — where each layer comes from

IMDR holds **no** corporate/issuer fundamentals. The official layer therefore
comes from the web, cited. The sell-side layer comes from the research corpus and
the PM library.

| Layer | Source | How |
|---|---|---|
| Business / history / competition | Company filings, IR site, exchange announcements | WebSearch / WebFetch |
| **Balance sheet · profit matrix · debt profile** | Annual & interim reports, regulatory filings (EDGAR / ASIC / SEBI / local reg), bond prospectus / OM | WebFetch (cite the filing + period) |
| Ratings + outlook | Moody's / S&P / Fitch press releases & rating actions | WebSearch / WebFetch (cite agency + date) |
| **Sell-side views** | Research corpus (Qdrant) | `python playground/research/retrieve.py "<issuer> credit"` via Bash |
| Sell-side metadata / provenance | `research.dim_report`, `research.fact_chunk` | `mcp__imdr-db__query` |
| **PM credit library** (what-good-looks-like + desk `.msg`) | `Z:\Business\Research\Credit` (country → issuer → theme; **READ-ONLY**) | Read / Glob |
| Spreads / CDS / market color | Sell-side + web (IMDR has no single-name credit spreads) | corpus / web; **flag when unsourceable** rather than inventing a level |

> The research MCP (Qdrant) is owner-only and not always reachable in headless
> runs — reach the corpus via `retrieve.py` (Bash) + the DB tables + the PM
> library. If none return anything for the issuer, say so; don't fabricate a
> desk view.

**Run order**
1. **Pin the issuer** (one per memo) — resolve ticker / legal entity / which entity
   in the group actually issues the bonds. Confirm if ambiguous.
2. **Set the track** (corporate vs financials) from issuer type.
3. **Check the PM library first** — `Z:\Business\Research\Credit\{country}\{issuer}`
   often already holds the canonical desk notes and `.msg` desk commentary.
4. **Pull the official layer** (web) — latest annual + interim, ratings actions,
   prospectus/maturity schedule. Cite each.
5. **Pull the sell-side layer** — `retrieve.py` + `dim_report`/`fact_chunk` + PM
   library. Name every house.
6. **Build the peer set** — 3–5 real comparables; pull the same metrics for each.
7. **Write the 9-section spine**, separating FACTS (filings) from VIEWS (sell-side
   + your synthesis).
8. **Write the § Sources appendix.**
9. **Pre-ship checklist** (§7). Fix what fails.
10. **Write the MD** (§5 path). Report back (§8).

---

## 5. Output

```
data/credit_briefs/{issuer_slug}/{issuer_slug}-credit-brief-{YYYY-MM-DD}.md
data/credit_briefs/{issuer_slug}/{issuer_slug}-latest.md   # maintained pointer
```

`{issuer_slug}` = issuer name sanitised to lowercase alphanumeric + hyphens
(e.g. `qbe-insurance`, `adani-ports`). **Accumulate** — never overwrite a prior
dated memo; refresh `-latest.md` to the newest.

Frontmatter (top of the MD) carries the routing + snapshot facts:

```yaml
---
issuer: QBE Insurance Group
slug: qbe-insurance
track: financials          # corporate | financials
sector: Insurance
country: AU
as_of: 2026-07-17
ratings: { moodys: "A3 sta", sp: "A- sta", fitch: "A- sta" }
credit_view: "Neutral — fairly valued sub vs AU insurer peers; prefer T2 to AT1"
---
```

---

## 6. Sources appendix discipline

Every number and every attribution is traced, split by layer:

- **§6.1 Filings / official** — company report (name, period, page/section) or
  regulatory filing or rating-agency action (agency + date + URL).
- **§6.2 Sell-side** — `[vendor, report_id or filename, publish_date]` for each
  cited desk view (corpus report_id, or PM-library file path).
- **§6.3 Web** — URL + retrieval timestamp for anything else.

A number with no §6 entry does not ship. Distinguish **reported** vs **adjusted**
figures and name whose adjustment (company / rating agency / a named desk).

---

## 7. Pre-ship checklist

- [ ] One issuer; correct **issuing entity** resolved (not just the group brand).
- [ ] **Track** stated and internally consistent (no corporate ratios on a bank).
- [ ] All 9 sections present; fits ~2 A4 pages; dense not padded.
- [ ] The **6 required topics** all covered: strengths/weaknesses · competition ·
      credit profile · profit matrix · debt profile · history.
- [ ] The **3 comparison lenses** present: balance sheet · sector comp · peer comp.
- [ ] **Every number cited** (§6); reported-vs-adjusted flagged.
- [ ] Ratings shown for all three agencies where rated (+ outlook).
- [ ] Peer set = **real, named** comparables; same metrics pulled for each.
- [ ] Every desk view **attributed to a real cited report**, or removed.
- [ ] FACTS (filings) separated from VIEWS (sell-side + synthesis).
- [ ] §8 credit view is explicit: rating path · RV read · stance + instrument ·
      top risks/catalysts. No equity price targets.
- [ ] Where a level (spread/CDS) is unsourceable, it is **flagged**, not invented.
- [ ] Accumulated to a new dated file; `-latest.md` updated.

---

## 8. Report-back

One tight closing message:
- MD output path (one line).
- 5–6 stat lines: issuer + track · one-line credit view · ratings (3 agencies) ·
  peer set (named) · source counts (filings · sell-side · web) · any flagged gaps
  (e.g. no sourceable spread) · pre-ship pass/fail.
- Note that rendering (Picasso credit-memo look) is a deferred follow-up.

---

## 9. Hard rules

1. **Content only** — grounded MD; no HTML/CSS/A4 layout (Picasso; deferred).
2. **One issuer per memo**; resolve the real issuing entity.
3. **Track-adaptive** — corporate or financials, stated; don't cross the ratios.
4. **Every number cited** (filing / agency / corpus / web); reported-vs-adjusted flagged.
5. **FACTS separated from VIEWS** (mirrors the daily-digest grounding discipline).
6. **Desk attributions are real cited reports, or removed.**
7. **A credit view IS expected** — but grounded, framed as a credit investor
   (rating path · RV · cap-structure placement); **no equity price targets**.
8. Peer set = real, named comparables (same sector/region/rating band).
9. **Accumulate versions** — never overwrite a prior dated memo.
10. The PM credit library `Z:\Business\Research\Credit` is **READ-ONLY**.
11. No DDL; read-only DB. No prod-wiring / git commits without explicit user OK
    (git via `imdr-git`). Don't touch `memory/` or `docs/admin/development/`
    without permission.
