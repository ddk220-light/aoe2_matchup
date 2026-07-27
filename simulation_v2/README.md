# simulation_v2 — the next-generation battle engine (staged, not live)

The V2 simulation engine, packaged so a build machine can pull `staging` and
run it **without touching anything the site serves**. The webapp does not
import this directory; the production engines (`aoe2x/sim/simulation_real.py`,
`aoe2x/sim/simulation.py`, live `apps/website/static/js/simulate.js`) and all
committed DBs remain the source of every number on the site until the full
rerun.

**Read [`CHANGELIST.md`](CHANGELIST.md) first** — it is the authoritative
list of every change, the units each one affects, and the full-rerun
protocol.

## Contents

| File | What |
|---|---|
| `CHANGELIST.md` | Every V2 divergence + affected units + rerun protocol |
| `sim_v2_model.js` | The frozen V2 configuration (all knobs + rationale). Entry point: `require("./sim_v2_model")` → `{ runFight }` |
| `headless_sim.js` | Node harness: loads the browser engine into a sandbox, applies the V2 transforms |
| `run_pool_v2.js` | Batch driver: subject vs an opponent pool at equal-resource arena counts, escalating seeds |
| `extract_combat_dicts.py` | Dumps `combat_dicts_all.json` (every Imperial civ×unit) from `data/golden/aoe2_reference.db` |
| `engine_base/` | Snapshot of the browser engine the transforms patch — `simulate.js` here carries the three engine-bug fixes (CHANGELIST §1) that are NOT yet in the live webapp copy |

Provenance: verbatim from branch `aoe2_ai_for_simulation` @ `e716414`
(2026-07-26), where development continues. If the branch engine moves, refresh
this snapshot rather than editing here.

## Running it

Requires Node ≥18 (no npm deps) and the repo's Python for extraction.

```bash
# 1. Combat dicts for the units you want (from the production ref DB)
python simulation_v2/extract_combat_dicts.py --out /tmp/cd.json \
    --units Incas/elite_champi_warrior Malians/elite_gbeto_malians

# 2. A single fight (21 Champi vs 12 Gbeto, seed 1)
cd simulation_v2 && JSDIR=$PWD/engine_base node -e '
const {runFight} = require("./sim_v2_model");
const cd = require("/tmp/cd.json");
runFight(cd["Incas/elite_champi_warrior"], "elite_champi_warrior", "Incas", 21,
         cd["Malians/elite_gbeto_malians"], "elite_gbeto_malians", "Malians", 12,
         1).then(r => console.log(r));'
```

`JSDIR` points the harness at `engine_base/`; without it the harness reads
`apps/website/static/js/` (the live, unfixed engine — fine on the dev branch,
wrong here). Multi-seed batches: see `run_pool_v2.js` header for the
`SUBJECT/WORKDIR/START/COUNT` env contract (its `combat_dicts_all.json` +
`pool_meta.json` inputs are produced by `build_v2_categorization.py` on the
dev branch, or hand-written — `pool_meta.json` is
`[{"key": "Civ/slug", "n_subject": N, "n_opp": M}, ...]`).

Determinism: `Math.random` is a seeded mulberry32 — same seed, same fight.

## Ground truth

Every calibrated knob traces to in-game arena recordings (ddkMatchupAI patrol
rig). The rig, tape index, and per-fight validation records live on
`aoe2_ai_for_simulation`: `apps/video/UNIT_VIDEO_WALKTHROUGH.md` (the golden
workflow) and `apps/video/sim_v2/results/`.
