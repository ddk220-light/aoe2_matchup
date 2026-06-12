# aoe2x/rank — unit ranking / pool scoring (layer 4)

**In:** a matchup baseline DB (`--matchup-db`, REQUIRED — e.g.
`D:/AI/matchup_baseline_<build>.db`; a pre-flight guard rejects partial
DBs) + `data/golden/aoe2_reference.db`.
**Out:** `data/golden/derived_data.db` (`battle_scores` role/composite
scores) and `data/golden/pool_scores.db` (multi-scale pool scores).
**Run:**

```bash
python -m aoe2x.rank.derive_unit_rankings --matchup-db <db> --build <N>
python -m aoe2x.rank.derive_pool_scores   --matchup-db <db> --build <N>
python -m aoe2x.rank.derive_siege_scores  --build <N>
```

INVARIANT: `pool_scores_lib.weighted_cost` is intentionally FROZEN at
wood=0.8 (the committed pool_scores.db was generated with it). Do NOT unify
with `aoe2x.sim.simulation_real.weighted_cost` (wood=0.7).

`compute_battle_scores.py` is RETIRED as a pipeline (kept for its siege
helpers used by derive_siege_scores).
