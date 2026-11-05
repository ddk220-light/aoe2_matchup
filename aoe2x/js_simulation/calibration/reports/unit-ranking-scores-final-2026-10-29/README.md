# Finalized unit-ranking score tables

**555 civilization/unit variants, 10 categories, zero missing or duplicate entries.** All scores are unchanged from the accepted preview. Only category membership and category ranks changed. Web app implementation remains the next step.

- [Complete score list — CSV](scores.csv)
- [Complete score list — JSON](scores.json)
- [Top 10 in every category](top10-by-category.md)
- [Category counts and leaders](categories.csv)
- [Validation](validation.json)
- [Methodology and provenance](manifest.json)

## Final categories

| Group | Category | Variants |
|---|---|---:|
| Infantry | Militia line | 91 |
| Infantry | Spear line | 56 |
| Ranged | Archer line | 65 |
| Ranged | Skirmisher line | 57 |
| Ranged | Cavalry archer line | 59 |
| Ranged | Scorpion line | 58 |
| Ranged | Gunpowder | 35 |
| Cavalry | Knight line | 70 |
| Cavalry | Light cavalry line | 51 |
| Cavalry | Camel line | 13 |

Militia includes the former Shock Infantry entries. Knight includes the former Elephant and Steppe Lancer entries. Original categories are retained in `sourceLine` for traceability and the later app migration.

## Scoring

A win contributes remaining own HP percentage; a loss contributes negative remaining opponent HP percentage; a draw contributes zero. Average the required seeds within each opponent matchup, then give each agreed opponent equal weight. Display score = 50 + mean signed HP margin / 2. There is no additional speed, range or cost multiplier. Cost and population balance is already represented by the simulated army counts. Group opponent pools remain unchanged.

The consolidated campaign's mixed engine provenance is preserved as explicitly requested. Finalization means the score list and category decisions are complete; the earlier statistical and simulation limitations still apply. No further simulations, engine changes or web app changes were performed.

Rebuild these tables: `python aoe2x/js_simulation/tools/finalize_ranking_scores.py`
