# PICASSO — RV Capital Briefing
*Agent onboarding file · maintained by the design desk · last updated 2026-06-09*

You are picking up design/production work for **RV Capital Management Private Ltd** — a Singapore-based hedge fund manager focused on long/short Asian fixed income (interest rates, FX, credit). Everything below is the working knowledge accumulated on this project. Read fully before touching any file.

---

## 1. Brand fundamentals

### Colour tokens (canonical values)
| Token | Hex | Use |
|---|---|---|
| RV Green `--accent` | `#004527` | Primary brand colour. Headlines, accents, the daily masthead, positive semantics |
| RV Dark Blue `--dark-blue` | `#001830` | Flagship/premium surfaces: weekly masthead, slice pull-quotes, footers |
| Cream `--cream` | `#E1D7C0` | Eyebrows/metadata **on dark surfaces only** — never as a page background |
| Light Blue | `#85A2BE` | Secondary data series, foreign/external concepts in charts, footer metadata on dark blue |
| Light Green | `#B2D0B9` | The "dot" on dark surfaces, tertiary accents |
| Ink `--fg` | `#3D3E3E` | Body text |
| Muted | `#7A7C7C` · faint `#A7A8A8` | Secondary text, captions, axis labels |
| Surfaces | bg `#FFFFFF` · surface `#FBFBFA` · panel `#F4F5F3` | Crisp near-whites. **Never beige/ivory** — an earlier draft used `#F4F1EA`-style beige; it was explicitly rejected |
| Borders | `#E0E0DE` / strong `#C9CAC8` / soft `#EEEEEC` | Hairlines everywhere; 1px |
| Green tints | 15% `#E0E9E4` · 40% `#99B3A8` · 70% `#4D806A` | TL;DR panel bg, chart supporting series |
| Negative | `#B23A2B` | Down moves, breach lines. (Not the old `#8B2E1E`) |
| Warn | `#B8862F` | Caution callouts, suspension-year bars |

Shadows are green-tinted and subtle: `0 2px 6px -3px rgba(0,69,39,0.16)` (sm), `0 6px 18px -10px rgba(0,69,39,0.22)` (md).

### Typography
- **Display serif: Quinn** (licensed brand face). Web deliverables substitute **Newsreader** (Google Fonts, optical sizing, weights 400–600) — closest available match. Used for: h1/h2/h3, pull-quotes, **all display numerals** (KPI values).
- **Body sans: Public Sans** — weights 300–700. Body 15–16px, line-height ~1.6.
- The signature is the **high-contrast pairing**: serif display at low weight (400) over sans body. All-sans documents read "generic fintech" and are off-brand.
- Eyebrows/labels: Public Sans 10–11px, uppercase, letter-spacing 0.12–0.18em, weight 600.
- Numerals in data contexts always get `font-variant-numeric: tabular-nums`.

### Brand devices
1. **25° slice** — dark band clipped with `clip-path: polygon(0 0, 100% 0, 100% 100%, 0 calc(100% - 2.6rem))`, used for pull-quotes and the weekly masthead. Always paired with a **light-green dot** placed in the open corner.
2. **Line + dot** — a short rule (≈64px, 2px) ending in a 6px circle. Green on light surfaces; cream line + light-green dot on dark. Appears: under hero ledes, on h2s (40px bar + dot over the hairline), at subsection dividers (`hr.rv-rule` — green tick fading to hairline, dot at ~36px), above the footer logo. The line always flows left→right and *finishes* in the dot.
   - ⚠️ `<hr>` defaults to `overflow: hidden` — set `overflow: visible` or the dot gets clipped. We hit this bug once.
3. **Cityscape imagery** — monochrome city photographs (Hong Kong skyline in `assets/cityscape-hongkong.png`) used as ~14% opacity overlays on green/dark mastheads. Never full-colour hero photos.
4. **Logos** — `assets/RV_Logo_Colour.png` (light surfaces), `assets/rv-logo-negative.png` (dark surfaces; in footers may also use `filter: brightness(0) invert(1)`).

### Hard "no" list (user-rejected or off-brand)
- ❌ `§` section markers and circled numbers (①②③) — explicitly called "yuck". Section numbering is a small sans `01 ·`-style numeral via `.section-num`.
- ❌ Left-border accent callouts (the rounded-corner left-stripe trope). Use cards with a **top accent rule** + hairline border + soft shadow instead.
- ❌ Beige/parchment backgrounds.
- ❌ Emoji, gradient washes, Inter/Roboto.
- ❌ "From the desk" beige/blue eyebrow treatment (removed on request).

---

## 2. The newsletter family — three editions, one system

Three sibling documents live at project root. **Structure is shared; the masthead voice distinguishes them.** Distinction is deliberate but subtle.

| | **Weekly Macro Preview** | **Daily Summary** | **Topical Brief** |
|---|---|---|---|
| File | `Weekly Macro Preview - RV.html` | `Daily Summary - RV.html` | `Indonesia Fiscal & SBN - RV.html` |
| Role | Flagship, bolder look | Quick derivative of weekly, day-focused | Deep dive (Mycroft research) |
| Masthead | **Dark blue** with 25° slice, biggest serif | **Green band**, compact | **White dateline** — quietest, lets content lead |
| Note | The green↔topical masthead assignment was swapped *to* daily on user request | | Has the tweaks panel (masthead style / density / brand devices) |

### Shared components (keep visually identical across editions)
- **Hero band** — full-bleed colour band, logo + uppercase meta top row, cream eyebrow, white serif headline (clamp ~34–56px), 300-weight lede with `strong` emphasis, line+dot close.
- **Brief-meta bar** (`#brief-meta`) — the conviction/horizon/data-as-of strip below the masthead. Current settled design after several iterations: **compact and centre-aligned** — `display:grid; grid-template-columns: repeat(N, max-content); width: fit-content; margin: 22px auto 0;` with 1px `--border` gap/border, slim single-line ~40px cells (`padding: 8px 16px`). Conviction gets a 5-step **heat scale** (`.heat-scale`, 56px wide). Stacks to one column below the breakpoint (1100px weekly/daily; Indonesia ~1230px). **Never** equal-width stretched columns — they force internal wrapping and look "sad"; never leave orphan cells next to grey voids.
- **KPI stripe** — hairline grid of stat cells: 10px uppercase label, serif value (~26–34px), small signed delta (`pos`=green, `neg`=red, `flat`=muted). Only colour deltas where sign is a genuine judgment.
- **Desk pull-quote** — dark-blue 25° slice, serif quote ~23–38px, light-blue eyebrow, cream attribution, light-green dot bottom-right.
- **Section heads** — serif green h2 over hairline with 40px green bar + dot; small `.section-num`.
- **Callouts** — `.callout` (surface bg, hairline border, 2px top accent; `warn`/`alert` recolour the top rule only). TL;DR panel uses green-15 bg + 3px green top rule.
- **Figures** (`.figure`) — inline SVG charts, see §4.
- **Footer** — dark-blue band: line+dot, negative logo, ~48ch about text, light-blue uppercase meta right, hairline-separated base row "© 2026 RV Capital Management Private Ltd · Internal / Private & Confidential".

---

## 3. Content & editorial rules
- Internal research vehicle is **Mycroft** (briefs are "Mycroft · Topical Brief"); data layer is **IMDR** (cite as `econ.fact_indicator`, `FX.fact_fx_rate`, etc.).
- Every chart/claim carries a source caption (DJPPR, BI SEKI, IMDR) and a data-as-of date.
- Never invent numbers — charts are built strictly from the document's own tables.
- Badges exist as a component (`Badge`, tones incl. neutral) — prefer them for verification/status chips. Keep copy short ("Re-verified 9 Jun", not "IMDR · re-verified 9 Jun" — trimmed for fit).
- Humans say "slide 5"/"section 5" 1-indexed.

---

## 4. Chart style (inline SVG, no libraries)
- Hand-built SVG in a 720-wide viewBox, `role="img"` + `aria-label`, Public Sans labels (10–11px), `--border-soft` gridlines, tabular numerals.
- Semantic colour mapping: **RV green = BI/domestic/primary**, **light blue = foreign/external**, green tints for supporting series, amber `#B8862F` for flagged/suspension periods, red `#B23A2B` dashed lines for caps/breach thresholds (e.g. −3% fiscal cap, USD/IDR 18,000).
- Direct line-end labels (no legend boxes); precompute label y-offsets to avoid collisions; widen the viewBox rather than letting end labels clip.
- Wrap in `<figure class="figure">` with uppercase `fig-title` ("Fig 1 · …") and muted `fig-caption` citing source + caveats.
- Bold value labels get a white paint-order stroke for legibility over bars.
- Inline SVG (not `<img>`) so print/PDF/export always work.

### Missing-image fallback (production pipeline images)
Weekly references `charts/*.png` and `bank_pdfs/*.png` generated by the data pipeline — absent in preview, expected in production. A script swaps failed images for labelled dashed `.img-fallback` placeholders using error events **plus** an IntersectionObserver + 5s grace timer (hung requests never fire `error`), and restores the real image on late `load`. Don't "fix" the 404 warnings; they're expected here.

---

## 5. Engineering notes
- Single-file HTML documents; Google Fonts via `<link>` (Newsreader + Public Sans).
- Print support: `print-color-adjust: exact` on coloured bands; `clip-path: none` for the slice in `@media print`.
- Full-bleed bands use negative margins matching the page padding: `margin: 0 calc(-1 * clamp(16px,4vw,40px))`.
- Indonesia brief has a **Tweaks panel** (React + tweaks_panel starter) — controls for masthead style, density, brand devices. `<style id="__om-edit-overrides">` blocks may hold user direct-edits with `!important`; respect/edit them rather than fighting them.
- Entrance/visual end-state must be the base style (no `opacity:0` traps for print).
- The full **RV Capital Design System** project (tokens, components, slides, marketing-site kit) is linked to this workspace — pull token/component definitions from there; copy assets into `assets/` before referencing.

## 6. File inventory (project root)
```
Indonesia Fiscal & SBN - RV.html   topical brief — tweakable, 4 SVG figures
Weekly Macro Preview - RV.html     flagship weekly — dark-blue slice masthead
Daily Summary - RV.html            compact daily — green masthead
uploads/indonesia-fiscal-sbn.html  original pre-redesign source (do not edit)
assets/                            logos + cityscape imagery (local copies)
screenshots/                       QA captures from past iterations
PICASSO.md                         this file
```

## 7. Working style this user expects
- Subtle, restrained moves; "sleek" and compact over airy. When something looks spacious or ragged they will flag it — fix the *system* (grid model, content sizing), not just the pixel.
- Preserve old versions when doing significant rewrites.
- Verify after every change (layout at multiple widths, console clean) before handing back.
- When they say "go back to old design", revert faithfully — don't re-litigate.
