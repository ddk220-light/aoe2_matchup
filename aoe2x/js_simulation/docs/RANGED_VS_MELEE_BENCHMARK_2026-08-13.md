# Ranged-versus-melee exact-ratio benchmark — 2026-08-13

## Result

The latest checked-out JavaScript engine completed all 810 scheduled battles
with no unresolved runs. Across all 48 authorized ranged-versus-melee tape
rows:

- 11 rows have more than 25 score points of mean delta.
- 11 simulation means are inside the recorded tape min/max band.
- One stable tape row changes winner: Elite Skirmisher versus Heavy Camel.
- Mean absolute mean-score delta is 16.42 points; median is 11.70.

The Heavy Cavalry Archer work generalizes well across this slice: none of its
eight rows exceeds 25 points, five means land inside the tape band, and its
mean absolute delta is 9.31 points. Heavy Scorpion is the closest family at
5.49 points. Hand Cannoneer and Siege Onager account for eight of the eleven
remaining large deltas.

## Exact execution contract

- Golden archive:
  `calibration/source/aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip`
- Verified SHA-256:
  `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`
- Population: 6 ranged owner-2 families × 8 melee owner-3 families = 48
  exact tape rows.
- Counts and owner order: copied from each tape row; no synthetic ratios and no
  reversed matchups.
- Sampling: five simulations for 42 stable rows and 100 simulations for six
  split-winner tape rows, for 810 total.
- Seed: `20260411`.
- Start lane: `tape_conditioned_canonical_start`.
- Engine timeout: 9,000 ticks; no run reached an unresolved outcome.

Signed winner score is negative for a ranged/owner-2 win and positive for a
melee/owner-3 win. Signed delta is simulation mean minus tape mean: a positive
value means the simulation favors melee more than the tape, and a negative
value favors ranged more.

## Rows above 25 points

| Rank | Exact tape matchup | Ratio | Tape mean | Sim mean | Signed delta | Tape-band error | Winner grading |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Hand Cannoneer vs Elite Battle Elephant | 21v12 | 2.38 | 72.34 | +69.96 | 40.05 | volatile |
| 2 | Siege Onager vs Elite Battle Elephant | 7v14 | 14.73 | 72.48 | +57.75 | 57.75 | match |
| 3 | Hand Cannoneer vs Hussar | 14v21 | 5.63 | 59.41 | +53.78 | 41.52 | volatile |
| 4 | Hand Cannoneer vs Elite Steppe Lancer | 21v19 | 8.03 | 59.87 | +51.84 | 51.84 | match |
| 5 | Elite Skirmisher vs Heavy Camel Rider | 21v8 | 39.82 | -3.80 | -43.62 | 43.62 | mismatch |
| 6 | Hand Cannoneer vs Paladin | 21v14 | 15.44 | 52.40 | +36.96 | 20.26 | volatile |
| 7 | Arbalester vs Elite Steppe Lancer | 21v14 | 9.19 | 45.91 | +36.72 | 21.91 | volatile |
| 8 | Siege Onager vs Elite Steppe Lancer | 7v21 | 62.99 | 31.11 | -31.88 | 31.88 | match |
| 9 | Siege Onager vs Heavy Camel Rider | 8v20 | 62.81 | 32.23 | -30.57 | 29.24 | match |
| 10 | Siege Onager vs Halberdier | 3v21 | 78.27 | 51.46 | -26.81 | 25.23 | match |
| 11 | Arbalester vs Hussar | 18v21 | 29.74 | 56.13 | +26.39 | 20.89 | match |

## Ranged-family summary

| Ranged family | Rows | Mean absolute delta | Rows >25 | Means inside tape band | Wrong stable winners |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hand Cannoneer | 8 | 31.18 | 4 | 1 | 0 |
| Siege Onager | 8 | 27.21 | 4 | 0 | 0 |
| Arbalester | 8 | 14.11 | 2 | 2 | 0 |
| Elite Skirmisher | 8 | 11.22 | 1 | 1 | 1 |
| Heavy Cavalry Archer | 8 | 9.31 | 0 | 5 | 0 |
| Heavy Scorpion | 8 | 5.49 | 0 | 2 | 0 |

## Interpretation and next work

Preserve the current HCA crowd and engagement behavior while investigating
other families. The four large Hand Cannoneer deltas all point in the same
direction—melee does much better in simulation than on tape—so they are a
coherent family-level diagnostic. Siege Onager errors point in both directions,
which suggests siege-specific projectile, blast, targeting, or engagement
mechanics rather than one global kiting bias. Elite Skirmisher versus Heavy
Camel is the first stable row to inspect because it is the only winner flip.

Outcome agreement alone does not prove that movement, target acquisition, or
attack timing matches `frames.bin`. Rows selected for engine changes still need
frame-level and visual review before modifying physics.

## Reproducible outputs

- Full per-sample output: `calibration/reports/ranged_vs_melee_current_engine_2026-08-13/results.json`
- Row-level analysis: `calibration/reports/ranged_vs_melee_current_engine_2026-08-13/analysis.json`
- CSV audit table: `calibration/reports/ranged_vs_melee_current_engine_2026-08-13/results.csv`
- Self-contained report: `calibration/reports/ranged_vs_melee_current_engine_2026-08-13/report.html`
- Canonical report artifact: `calibration/reports/ranged_vs_melee_current_engine_2026-08-13/artifact.json`

Run again from `aoe2x/js_simulation` with:

```powershell
node tools/run_ranged_vs_melee_suite.mjs
node tools/build_ranged_vs_melee_report.mjs
```

The portable report passed artifact validation, packaging, and structural
verification. Chromium visual QA was unavailable on this machine, so the
generated HTML retains its semantic no-script fallback table and source
inventory but does not claim browser-layout verification.
