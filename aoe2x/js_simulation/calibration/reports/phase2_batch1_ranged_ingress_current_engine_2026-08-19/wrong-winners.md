# Phase 2 Batch 1 — Previous versus current winners

This compares the previous complete 120-row Phase 2 run with the new complete 120-row run. It reports only winners and surviving HP.

- Golden archive: `aoe2_golden_phase2_WITH_TAPES.zip`
- Verified SHA-256: `B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6`
- Previous full run: `phase2_reachable_opening_body_formation_full_2026-08-19` (`46c5a6fed8e0`)
- Current full run: `phase2_batch1_ranged_ingress_current_engine_2026-08-19` (`63399ecb93f6`)
- Scope: 20 unique units, 120 exact golden rows, 680 samples in each run

## Correct previously, wrong now — 9

| Matchup | Tape result | Previous simulation | Current simulation |
|---|---:|---:|---:|
| Elite Conquistador vs Champion | Elite Conquistador 78.44% | Elite Conquistador 57.00% | Champion 36.19% |
| Elite Janissary vs Elite Battle Elephant | Elite Janissary 59.19% | Elite Janissary 50.26% | Elite Battle Elephant 42.31% |
| Elite Keshik vs Champion | Elite Keshik 27.15% | Elite Keshik 2.56% | Champion 5.55% |
| Elite Keshik vs Paladin | Elite Keshik 21.88% | Elite Keshik 2.38% | Paladin 9.37% |
| Elite Mangudai vs Heavy Cavalry Archer | Heavy Cavalry Archer 43.75% | Heavy Cavalry Archer 42.74% | Elite Mangudai 11.38% (3/5 resolved) |
| Elite Rattan Archer vs Champion | Champion 44.76% | Champion 13.06% | Elite Rattan Archer 61.90% |
| Elite Rattan Archer vs Heavy Scorpion | Elite Rattan Archer 33.33% | Elite Rattan Archer 19.37% | Heavy Scorpion 0.70% |
| Elite Shotel Warrior vs Paladin | Elite Shotel Warrior 24.48% | Elite Shotel Warrior 1.75% | Paladin 1.16% |
| Elite War Wagon vs Paladin | Paladin 35.44% | Paladin 39.02% | Elite War Wagon 53.00% |

## Already wrong and still wrong — 3

| Matchup | Tape result | Previous simulation | Current simulation |
|---|---:|---:|---:|
| Elite Karambit Warrior vs Paladin | Elite Karambit Warrior 21.96% | Paladin 16.73% | Paladin 15.84% |
| Elite Throwing Axeman vs Arbalester | Elite Throwing Axeman 19.76% | Arbalester 18.48% | Arbalester 2.72% |
| Elite War Wagon vs Champion | Champion 20.10% | Elite War Wagon 25.31% | Elite War Wagon 85.94% |

## Previously wrong, correct now — 7

| Matchup | Tape result | Previous simulation | Current simulation |
|---|---:|---:|---:|
| Arbalester vs Elite Magyar Huszar | Elite Magyar Huszar 17.35% | Arbalester 10.48% | Elite Magyar Huszar 55.15% |
| Elite Conquistador vs Arbalester | Elite Conquistador 31.90% | Arbalester 31.13% | Elite Conquistador 10.63% |
| Elite Longbowman vs Arbalester | Elite Longbowman 73.75% | Arbalester 22.88% | Elite Longbowman 77.00% |
| Elite Longbowman vs Heavy Cavalry Archer | Elite Longbowman 50.71% | Heavy Cavalry Archer 16.04% | Elite Longbowman 74.24% |
| Elite Longbowman vs Heavy Scorpion | Elite Longbowman 10.57% | Heavy Scorpion 12.45% | Elite Longbowman 33.81% |
| Elite Plumed Archer vs Paladin | Paladin 19.29% | Elite Plumed Archer 24.91% | Paladin 53.64% |
| Heavy Cavalry Archer vs Elite Boyar | Elite Boyar 10.50% | Heavy Cavalry Archer 37.57% | Elite Boyar 6.81% |

## Stable rows without a current result

| Matchup | Tape result | Previous simulation | Current simulation |
|---|---:|---:|---:|
| Elite Conquistador vs Elite Battle Elephant | Elite Conquistador 52.65% | Unresolved | Unresolved |
| Elite War Wagon vs Elite Battle Elephant | Elite Battle Elephant 51.73% | Elite Battle Elephant 49.13% | Unresolved |
| Heavy Cavalry Archer vs Elite Karambit Warrior | Elite Karambit Warrior 39.52% | Elite Karambit Warrior 32.52% | Unresolved |

The comparison above is restricted to stable golden rows. Knife-edge rows are not labeled wrong merely because their mean winner changes sign.

The previous full-run baseline predates several subsequent engine changes. Therefore, the nine regressions are verified full-run flips, but this comparison alone does not attribute each flip exclusively to the most recent ranged-ingress change.
