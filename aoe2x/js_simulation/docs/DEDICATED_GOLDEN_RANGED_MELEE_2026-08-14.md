# Dedicated golden ranged-versus-melee benchmark — 2026-08-14 (historical)

> This report is the last full 17-archive portfolio run before the current
> native-siege, minimum-range-retreat, exclusive allied-overlap, and Hand
> Cannoneer corpus changes. The active corpus now contains 19 archives, 95
> ratio rows, and 475 tape repeats. Use the
> [current engine guide](CURRENT_ENGINE_2026-08-15.md),
> [golden tape workflow](GOLDEN_TAPE_COMPARISON_WORKFLOW.md), and
> [Hand Cannoneer current-engine result](../calibration/reports/hand_cannoneer_current_engine_2026-08-15/README.md)
> for current-state claims.

This is the historical tape comparison for the JavaScript engine with generic
one-range melee reach-wedge transit. It uses only the 17 separately named
dedicated golden archives recorded in
`calibration/source/dedicated_ranged_melee_sources.json`.

The corpus contains 17 matchups, five tape ratios per matchup, and five exact
tape repeats per ratio: 85 ratio rows and 425 simulation attempts. Every
simulation starts from the `starting_units` positions of its corresponding
tape repeat. No Standard Units row, generated placement, reversed matchup, or
manually selected viewer count is used as tape evidence.

## Result

- 420/425 attempts produced an engine outcome. The only unresolved row is the
  accepted 9,000-tick Elite Skirmisher-versus-Champion 10v5 knife-edge case.
- Of 84 resolved rows, 72 are at or below 25 percentage points of absolute
  mean tape delta and 12 are above 25.
- Median absolute row delta is 4.58 points and mean absolute row delta is 17.77
  points, conditional on resolved rows.
- Heavy Scorpion accounts for nine of the 12 rows above 25 and 30 of the 31
  wrong-winner attempts. It is the dominant remaining engine gap.
- HCA versus Elite Steppe Lancer is repaired: 9.16-point family mean, 25.00
  maximum, no wrong winners, and no unresolved runs.
- Elite Skirmisher versus Elite Steppe Lancer has a 0.55-point family mean and
  no wrong winners. Arbalester versus Elite Steppe Lancer has an 18.06-point
  family mean, no wrong winners, and one 28.20-point row at 10v5.

The detailed [one-range melee report](../calibration/reports/experiment_one_range_melee_wedge_2026-08-14/README.md)
contains the Steppe table, the complete remaining-gap classification,
methodology, and links to all 85 audit rows.
The same evidence is packaged as a self-contained
[HTML report](../calibration/reports/experiment_one_range_melee_wedge_2026-08-14/report.html).

## What remains

Scorpion is not literally the only residual, but it is overwhelmingly the
largest one. Outside Scorpion, three resolved rows exceed 25 points:

| Matchup | Ratio | Absolute mean delta | Wrong winners |
|---|---:|---:|---:|
| Elite Skirmisher vs Champion | 20v15 | 33.75 | 0 |
| Arbalester vs Champion | 20v20 | 29.63 | 0 |
| Arbalester vs Elite Steppe Lancer | 10v5 | 28.20 | 0 |

HCA versus Elite Fire Lancer 20v20 has one repeat-level wrong winner, but its
mean delta is only 2.02 and the tape itself crosses the winner boundary. The
Elite Skirmisher-versus-Champion timeout and 20v15 residual remain explicitly
accepted for now rather than being calibration targets.

## Reproducible outputs

- `calibration/reports/experiment_one_range_melee_wedge_2026-08-14/results.json`
- `calibration/reports/experiment_one_range_melee_wedge_2026-08-14/results.csv`
- `calibration/reports/experiment_one_range_melee_wedge_2026-08-14/analysis.json`
- `calibration/reports/experiment_one_range_melee_wedge_2026-08-14/artifact.json`
- `calibration/reports/experiment_one_range_melee_wedge_2026-08-14/report.html`
- `calibration/reports/experiment_one_range_melee_wedge_2026-08-14/recoverable/`

The HTML artifact passed validation, packaging, payload equality, and
structural verification. No compatible installed Chromium headless shell was
available, so viewport and source-dialog interaction checks were not run; the
semantic fallback remains embedded and readable.

## Future runs

Use `tools/run_recoverable_dedicated_benchmark.mjs` for full-corpus runs or
`tools/run_recoverable_dedicated_rows.mjs --matchup-ids ...` for mechanically
bounded reruns, documented in
[RECOVERABLE_DEDICATED_BENCHMARKS.md](RECOVERABLE_DEDICATED_BENCHMARKS.md).
The older 48-row Standard Units report is retired because its rows are not the
separately named dedicated golden kiting archives required for this comparison.

The current corpus adds Hand Cannoneer versus Champion and Hand Cannoneer
versus Paladin. Those 10 rows were run separately against the newer engine and
are documented in the linked 2026-08-15 result. A full current 19-archive run
has not yet replaced this historical portfolio report.
