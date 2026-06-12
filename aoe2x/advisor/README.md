# aoe2x/advisor — matchup advisor (layer 4)

**In:** `data/golden/aoe2_reference.db`, `derived_data.db`,
`pool_scores.db`, `civ_power_units/<build>.json` (build resolved via
`aoe2x.batch.patches_db.get_current_build()`).
**Out (live):** `best_units.get_matchup_sims(civ_left, civ_right, age)` /
`get_matchup_recommendations(...)` — seeded (deterministic) abstract-engine
sims between the two civs' power armies; serves POST `/api/matchup-sims`.
**Out (offline):** `best_units.save_civ_power_units('<build>')` regenerates
the committed power-unit rosters; `python -m aoe2x.advisor.top_units`
regenerates `civ_top_units.json`.

Siege/treb and naval lines are excluded from live sims (percentiles only);
`CIVS_WITHOUT_TREBUCHET` carries the hardcoded exceptions.
