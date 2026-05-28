# SOV_CMT — Sovereign Constant-Maturity Yields: Deep Exploration

- **Explored**: 2026-03-26
- **Total tags**: 8,250
- **DO NOT re-run** — all results documented here

---

## Tag Format

`RATES.SOV_CMT.{COUNTRY}.{TENOR}.YIELD`

Single metric (YIELD) at each tenor. Countries use ISO-3166 alpha-3 codes.

---

## Countries (34)

32/34 return data. RUS and AUTFULL return nothing.

### G7

| Country | Code | 2Y | 5Y | 10Y | 30Y |
|---|---|---|---|---|---|
| United States | USA | 3.89% | 4.00% | 4.34% | 4.90% |
| Germany | DEU | 2.58% | 2.71%* | 2.98% | 3.19%* |
| United Kingdom | GBR | 4.29% | — | 4.84% | — |
| France | FRA | — | — | 3.67% | — |
| Japan | JPN | 1.30% | — | 2.24% | — |
| Canada | CAN | — | — | 3.48% | — |
| Italy | ITA | — | — | 3.82% | — |

*Estimated from curve shape — only 10Y explicitly probed for non-USA.

### Core Europe

| Country | Code | 10Y Yield |
|---|---|---|
| Austria | AUT | 3.25% |
| Belgium | BEL | 3.49% |
| Switzerland | CHE | 0.34% |
| Denmark | DNK | 2.81% |
| Spain | ESP | 3.45% |
| Finland | FIN | 3.30% |
| Ireland | IRL | 3.17% |
| Luxembourg | LUX | 3.18% |
| Netherlands | NLD | 3.08% |
| Norway | NOR | 4.35% |
| Sweden | SWE | 2.85% |

### Periphery / CEE Europe

| Country | Code | 10Y Yield |
|---|---|---|
| Cyprus | CYP | 3.54% |
| Czech Republic | CZE | 4.77% |
| Greece | GRC | 3.85% |
| Hungary | HUN | 7.33% |
| Poland | POL | 5.62% |
| Portugal | PRT | 3.37% |
| Romania | ROU | 7.09% |
| Slovakia | SVK | 3.69% |
| Slovenia | SVN | 3.45% |

### Other DM

| Country | Code | 10Y Yield |
|---|---|---|
| Australia | AUS | 4.95% |
| New Zealand | NZL | 4.70% |
| Israel | ISR | 4.04% |

### EM

| Country | Code | 10Y Yield |
|---|---|---|
| Turkey | TUR | 31.13% |
| South Africa | ZAF | 9.10% |
| Russia | RUS | NO DATA |

---

## Full USA Yield Curve (30 tenors)

All 30 tenors return data daily (22 pts / 30 days):

| Tenor | Yield | | Tenor | Yield |
|---|---|---|---|---|
| 1M | 3.650% | | 10Y | 4.344% |
| 3M | 3.684% | | 11Y | 4.415% |
| 6M | 3.782% | | 12Y | 4.492% |
| 9M | 3.819% | | 13Y | 4.570% |
| 1Y | 3.842% | | 14Y | 4.647% |
| 18M | 3.905% | | 15Y | 4.716% |
| 2Y | 3.891% | | 16Y | 4.777% |
| 3Y | 3.882% | | 17Y | 4.826% |
| 4Y | 3.929% | | 18Y | 4.866% |
| 5Y | 3.998% | | 19Y | 4.895% |
| 6Y | 4.077% | | 20Y | 4.915% |
| 7Y | 4.150% | | 25Y | 4.935% |
| 8Y | 4.215% | | 30Y | 4.897% |
| 9Y | 4.277% | | 40Y | 4.909% |
| | | | 50Y | 4.915% |
| | | | 1B* | 3.632% |

*1B = 1 business day (overnight rate proxy)

All countries appear to share the same 30-tenor grid, though not all tenors will have data for every country.

---

## Key Structure Notes

- **DEU.10Y** has *additional* children beyond YIELD — forward-starting yield nodes (e.g. `DEU.10Y.5Y` = 10Y5Y forward). USA.10Y only has YIELD. This means the SOV_CMT dataset includes embedded forward curves for some European issuers.
- **AUTFULL** = Austria full curve (separate from AUT) — returns no data, possibly discontinued.
- **RUS** = no data (likely sanctions-related).
- 30 tenors × 34 countries × 1 metric = 1,020 base tags. Remaining ~7,230 tags are likely the forward-starting yield variants (European countries).

---

## Pipeline Considerations

- **Core universe**: Focus on the ~15 countries that matter for macro (G7 + AUS/NZL/CHE/NOR/SWE + maybe POL/HUN/ZAF/TUR)
- **Tenor grid**: For initial ingest, use the standard set: 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 15Y, 20Y, 25Y, 30Y (13 tenors)
- **Daily frequency**: ~22 data points per 30-day window
- **Tags per day**: 15 countries × 13 tenors = 195 tags (well within quota)
