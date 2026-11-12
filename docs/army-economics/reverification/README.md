# Re-verification of the 2026-11-12 rebuild

Adapted copies of the independent review's comparison scripts
(`origin/army-economics-review:docs/army-economics-review/scripts/`). They are a
record of method, not a packaged tool: they expect the reviewers' downloaded
online data (aoe2techtree `data.json`, `online_ref.json`, `runtime_rates.json`,
`techtree_missing.json`) and absolute repository paths.

Adaptations: the runtime database is taken from `RUNTIME_DB` (output `OUT_CSV`);
verdicts the reviewers had hard-coded for the defects they found (Kona price,
Mapuche routes, Danes/Poles food, Crenellations/Aznauri, stale README rate rows)
are now computed from the data; `HALF_UP=1` compares prices with the half-up
rule; the arithmetic recompute nets the Wu building rebate; `research/flatten.py`
rebuilds the reviewers' civ x tech extract from a runtime database.

Run on the old `matchup-timings` database, the adapted scripts reproduce the
review's counts exactly; `summary.json` has before/after counts and
`remaining-non-match-rows.csv` every row that is not a match on the rebuilt data.
