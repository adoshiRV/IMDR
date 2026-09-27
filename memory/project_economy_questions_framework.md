---
name: project-economy-questions-framework
description: New 4th econ analytical layer — the country-decomposition question framework (economy_questions.md)
metadata:
  type: project
---

**Economy Questions framework — authored 2026-06-26** at
`docs/admin/econ/economy_questions.md` (registered in `docs/admin/econ/index.md`
quick links). The **4th econ layer**, the *analytical/reasoning* one, sitting on
top of the three structural layers it deliberately reuses (does NOT re-implement):
wiring map (where data lives) · [[project_rates_playbook_engine]]'s 8-driver
taxonomy `macro_driver_taxonomy.md` (how a surprise scores) · Mercator
`cluster_map_spec.md` (what to track).

The model = **3 axes**: **Axis 1** = 8 domains (D1 Inflation · D2 Growth/output ·
D3 Labour · D4 Housing/credit · D5 External/FX · D6 Fiscal · D7 CB reaction
function · D8 Global transmission), anchored to the 4 wiring-map loops. **Axis 2**
= 6 question archetypes (Q1 Decompose · Q2 Driver · Q3 Sensitivity/elasticity · Q4
History/regime · Q5 Surprise&vol · Q6 Reaction&pricing) — the genuinely new part.
**Axis 3** = country overlay (domain weights incl. explicit "may-not-matter" Low
tag, country-specific Qs, data anchor). Standing question set = domain×archetype,
written country-generic in §4 with KR/AU/NZ/IN/JP illustrative anchors.

Mapping to infra: Q1≈cluster map · Q5≈8-driver engine + cb_events +
rates.fact_observation (conditional rates vol on a 1σ surprise; most-vol-inducing
release; rolling-beta vol-regime leading indicator — **§5, NOT built yet, analysis
spec**) · Q6≈rates playbook composite.

User decisions 2026-06-26 (AskUserQuestion): **format = framework spec doc** (not
agent/YAML yet); **country = generic only** (no single country fully worked).

**2026-06-28 — agent created.** New agent **Smith** (`.claude/agents/smith.md`) =
RV Capital's country economist, the *answering* sibling to Mercator (Mercator draws
the map/what-to-track; **Smith fills it in**/the answers — decomposes, estimates
elasticities, states what's priced; Mercator never does). Deliverable = **Country
Economy Profile** (durable per-country, refreshed on regime/structural shift).
User picked **format = plain structured MD, no render** (Picasso deferred). Output
`data/economy_profiles/{cc}/{cc}-economy-profile-{YYYY-MM}.md` (accumulate +
`{cc}-latest.md`). Spec §8 (deliverable contract + pre-ship checklist) added to
economy_questions.md; §8 hard rules → §9. Smith invoke: "Smith, decompose Korea" /
`/smith <country>`. Name swappable (Adam Smith). NO country profile authored yet.

**2026-07-10 — per-country tracked questions split into a building log.** New doc
`docs/admin/econ/economy_questions_building.md` = living, append-only per-country
question lists (IN credit-growth/rural-urban/FCNR · US core-PCE/surprises/1y-Fed-
pricing · KR wealth-effect-flywheel), each mapped to domain×archetype + data-status
flag; research numbers flagged as theses-to-verify not facts. economy_questions.md
§6.1 now just POINTS to it (generic spec stays country-agnostic). Smith reads the
building log (smith.md source-of-truth updated). NOTE: index.md quick-links were
intentionally reverted (user/linter) to NOT list economy_questions* docs — don't
re-add them. New per-country questions append to the building log, not the spec.

Remaining/optional: author first profile (AU/US/KR have deepest data for
Q3/Q4/Q5); build the Q5 conditional-vol computation (still analysis-spec only);
later a Picasso render identity + YAML question bank. All UNCOMMITTED — offer
imdr-git (economy_questions.md, smith.md, index.md).

**2026-06-28 — agent-roster simplification RECOMMENDED but DEFERRED ("stop for
now").** Diagnosis: 8 content agents do only 4 real jobs. Recommended collapse:
merge **Mercator+Smith** → one Country agent (what-to-track + decomposition);
merge **Atlas+Perry+Lois+Jonah** → one Brief agent (cadence daily/weekly + scope
country/all as params; Perry already commissions Atlas+Lois); keep **Mycroft**
(one-off Q&A) + **Picasso** (render). Infra (7: engineer/dbm/doc-manager/git/
security/pm/code-reviewer) lower-pain, optional later trim (security→code-reviewer,
drop pm+doc-manager standalone). User deferred the refactor — do NOT execute until
asked. When revisited, note it touches specs + agent files + memory + skills + the
`data/` output paths (partly destructive).
