# Dedicated golden ranged-versus-melee benchmark — 2026-08-14

This is the active tape comparison for the current JavaScript engine. It uses
only the 17 separately named dedicated golden archives recorded in
`calibration/source/dedicated_ranged_melee_sources.json`.

The corpus contains 17 matchups, five tape ratios per matchup, and five exact
tape repeats per ratio: 85 ratio rows and 425 simulation attempts. Every
simulation starts from the `starting_units` positions of its corresponding
tape repeat. No Standard Units row, generated placement, reversed matchup, or
manually selected viewer count is used as tape evidence.

## Result

- 295/425 attempts produced an engine outcome.
- 130/425 attempts, representing 26 fully unresolved ratio rows, recorded a
  collision-convergence engine exception.
- Of the 59 resolved ratio rows, 50 are at or below 25 percentage points of
  absolute mean tape delta and nine are above 25 points.
- Median absolute row delta is 6.70 points. Mean absolute row delta is 19.19
  points, conditional on the 59 resolved rows.
- Heavy Scorpion accounts for six of the nine rows above 25 points and 20 of
  the 31 wrong-winner attempts.
- Heavy Cavalry Archer versus Champion is fully resolved: 7.84-point mean
  absolute row delta, 21.18-point maximum, and no wrong winners.

Open the self-contained [HTML report](../calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/report.html)
for the charts, complete threshold list, failure accounting, methodology, and
all 85 audit rows.

## Reproducible outputs

- `calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/results.json`
- `calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/results.csv`
- `calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/analysis.json`
- `calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/artifact.json`
- `calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/report.html`

The portable report passed artifact validation, packaging, and structural
verification. The installed desktop Chrome did not satisfy the packager's
headless chart-extraction environment, so per-viewport browser verification
was not available; the report retains its semantic chart tables and is fully
self-contained.

## Future runs

Use `tools/run_recoverable_dedicated_benchmark.mjs`, documented in
[RECOVERABLE_DEDICATED_BENCHMARKS.md](RECOVERABLE_DEDICATED_BENCHMARKS.md).
The older 48-row Standard Units report is retired because its rows are not the
separately named dedicated golden kiting archives required for this comparison.
