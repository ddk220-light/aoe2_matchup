# aoe2x/batch — batch sim runners + patch pipeline (layer 4)

PyPy3 REQUIRED for the runners (CPython is ~10x slower):

```bash
pypy3 -m aoe2x.batch.rebuild_matchup_baseline --out D:/AI/matchup_baseline.db --workers 16   # full, ~4.5h
pypy3 -m aoe2x.batch.run_matchup_battles --db <db> [--changed-units slugs.json --force]      # incremental
pypy3 -m aoe2x.batch.verify_flips ...        # adversarial re-sim of patch-diff candidates
```

**In:** `data/golden/aoe2_reference.db` + `aoe2x.sim.simulation_real`.
**Out:** matchup DBs (LOCAL/external — `data/local/` or `D:/AI/...`, never
committed; rows cache-keyed by `sim_version`, stale rows re-simmed).

`patch_pipeline.py` (CPython) orchestrates a game patch end-to-end:
re-extract → rebuild ref DBs → diff → scoped re-sim → re-derive → record in
`data/golden/patches.db`. Full runbook: `docs/architecture/runbooks.md` §1.
`patches_db.get_current_build()` is the single build resolver the serving
layer uses.
