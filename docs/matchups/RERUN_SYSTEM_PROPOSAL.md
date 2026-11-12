# Proposal: a repeatable matchup rerun system

**Status:** design only. Nothing here is built yet. It is based on what the
Oct 31 – Nov 11 campaigns actually did; read
[HOW_THE_2026_CAMPAIGNS_RAN.md](HOW_THE_2026_CAMPAIGNS_RAN.md) first. `RB` means the
research branch `origin/simulations/civ-forecast-recovery-2026-11-10`.

## 1. What the system must do

When a new game patch, DLC or balance change arrives, or the owner wants different
conditions (army size, cost weights, seeds, engine flags), the system should:

1. build the unit roster and combat profiles from a named reference DB;
2. work out which battles (contexts) are new or changed;
3. run only those, resumably and in parallel, reusing every unchanged result;
4. classify each context from its seeds;
5. build a new serving DB for the Matchup Advisor and audit it;
6. publish it through `staging` without changing the live Battle Sim's engine identity.

The 2026 campaigns already contain working versions of steps 2–5, but each
campaign hard-codes its own paths, hashes, counts and branch names (for example
`assert.equal(jobs.length,68871)` in `prepare-adaptive.mjs`, `DIR=…/civ-matchups-forecast-validation-2026-11-07`
in `forecast-validation-lib.mjs`, git pushes to `simulations/…` inside the runners).
The work is to generalise them behind one config file, not to invent new mechanics.

## 2. Two facts that shape the design

**(a) The campaign engine is not the live engine.** The table was simulated with
`frozen-civ-matchups-v3` (+ `lossless-event-stream-v1`), whose 62 runtime files
equal `RB` commit `6c3049dfd`. The current branch's `aoe2x/js_simulation/src`
equals the Sept 23 merge base `2581cd353`; 15 `src/` files differ and
`src/combat/unit-defenses.js` is missing. The live site hashes
`aoe2x/js_simulation/src/**/*.js` into its engine version
(`release_metadata()` in `apps/backend/aoe2_api/services/release.py`), and
`scripts/migration/prepare_release.py` refuses to build if that version changes
("An engine change requires an explicit legacy-client compatibility release").
So **the campaign engine cannot share `aoe2x/js_simulation/src`; it needs its own
pinned copy** outside that directory.

**(b) The campaign unit data is not the live unit data.** The campaigns used
`aoe2_reference_simulation.db` SHA-256 `234ad0a6…` (build 185872 + selected 188329
changes, `RB` commit `58e480b76`). The current branch's copy is `b3b2f34d…`; 132 of
the 555 roster profiles differ. That DB is a simulator configuration input
(`SIMULATOR_CONFIGURATION_INPUTS` in `scripts/migration/export_data.py`), so
replacing it changes the live simulator's data version too. **Reruns must read a
separately stored mechanics bundle**, not silently swap `data/golden/aoe2_reference_simulation.db`.

## 3. What to port vs. rewrite

### 3.1 Port byte-for-byte (pinned engine)

Copy the 62 files named in `RB:aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/manifest.json`
(`runtimeFiles`) from commit `6c3049dfd` into a new tree, keeping relative paths:

```
aoe2x/matchups/engines/frozen-civ-matchups-v3/aoe2x/js_simulation/
  src/            48 files, 811,192 bytes   (fight.js, combat/*, battle-setup.js, lab-scenario.js, …)
  fixtures/       3 files, 145,821 bytes    (golden_map.json, golden_formation_27v27.json, current_ranged_golden_formations.json)
  node/, tools/   11 files, 92,426 bytes    (run-job.mjs and ranking-campaign files listed in the manifest)
  ENGINE.json     the 62 {path, sha256} entries + name + source commit
```

Total ≈ 1.05 MB. Keeping the `aoe2x/js_simulation/` sub-layout matters because the
existing workers already import a pinned copy by `workerData.runtimeRoot`
(`collision-validation-worker.mjs`, `mismatch-validation-worker.mjs`), and
`lab-scenario.js` reads fixtures relative to its root. The directory is outside
`aoe2x/js_simulation/src`, and `prepare_release.py` packages only `*.py` from a
fixed list of `aoe2x/` sub-packages, so this copy changes neither the engine
version nor the backend bundle *(verify in build step 1)*.

Optionally also port the recovery variants as separate engine IDs
(`forecast-recovery-local-refinement-v3` = `RB` tip, 66 runtime files), but see
open question Q2 before using them.

### 3.2 Port with light generalisation (campaign library)

| `RB` file | Bytes | Role | Change needed |
|---|---:|---|---|
| `SIM/node/ranking-worker-pool.mjs` | 3,049 | Worker pool with wall watchdog and respawn | Pass `workerData.runtimeRoot` |
| `SIM/node/mismatch-validation-worker.mjs` | 3,106 | Load hook removing the 9,000-tick cap; diagnostic snapshots | None (point at pinned root) |
| `SIM/node/civ-matchups/rolling-validation-queue.mjs` | 675 | Keep N workers busy across phases | None |
| `SIM/node/civ-matchups/forecast-validation-lib.mjs` | 3,310 | `payload()`, `required()`, `canonicalOutcome()`, `exact()` | Read paths from config |
| `SIM/node/civ-matchups/forecast-screening-policy.mjs` | 6,174 | 1/3/10 decision (`screeningDecision`, `terminalMargin`) | Remove amendment-file checks; take the policy from config |
| `SIM/node/civ-matchups/run-forecast-validation.mjs` | 16,310 | Runner: locks, journals, attempts, pair reviews, phase reviews | Remove git commit/push; config-driven paths |
| `SIM/node/civ-matchups/export-forecast-reviews.mjs` | 8,728 | Reviewed-only export with re-verification | Config-driven |
| `SIM/node/ranking-equivalence.mjs` | 2,055 | `combatProfileHash()` | None |
| `SIM/node/civ-matchups/phase-one.mjs` | 55,148 | Profiles → pairs → contexts; rule inference R1–R3 | Split: context builder (needed) vs inference (optional) |
| `SIM/tools/export_ranking_roster.py` | 3,615 | 555-unit roster rule | Config-driven groups/extra lines |
| `RB:tools/supervise_civ_forecast_validation.py` | 2,544 | Supervisor (flock, restart, stop on failure) | Config-driven; keep the approval gate |
| `RB:tools/audit_civ_forecast_validation.mjs` | 14,180 | Read-only integrity/count audit | Config-driven |
| `C/unit-rankings-path-recovery-2026-10-29/manifest.json` | 5,644,587 | Frozen profiles + 5 scenarios + policy | Split into `mechanics bundle` (profiles) and `scenario set` (scenarios); see 3.4 |

Dependencies: Node v24.19.0 (no npm packages; uses `node:sqlite`, `node:zlib`,
`worker_threads`), Python 3 standard library, and `aoe2x.rank.derive_unit_rankings`
/ `aoe2x.sim.unit_lines` for the roster.

### 3.3 Rewrite (small, new)

- `inventory`: one generic builder replacing `prepare-campaign.mjs`,
  `prepare-adaptive.mjs`, `prepare-mismatch-validation.mjs`,
  `prepare-forecast-validation.mjs` and `RB:tools/prepare_civ_forecast_inventory.py`.
- `classify` / `build-db`: build the serving DB directly from run results instead of
  layering importers (`scripts/apply_advisor_matchup_corrections.py` →
  `apply_advisor_forecast_corrections.py` → `apply_advisor_recovery_results.py`).
  The schema stays exactly as `scripts/build_advisor_first_pass.py` creates it, so
  `apps/backend/aoe2_api/services/advisor.py` and the frontend need no change.
- `diff`: compare two mechanics bundles and list affected contexts.

### 3.4 Do not port

The adaptive selector (`select_civ_phase.py`, `build_civ_matchup_estimates.py`,
`plan_civ_*`), the ML forecast (`evaluate_civ_prediction_coverage.py`,
`civ_prediction_first_pass.py`), the sampling-amendment machinery and the git
checkpoint code. They existed to avoid simulating everything; the records show
forecasts were then overturned in 3,476 of 39,112 checked contexts (31 % in the
`weak_model_agreement` tier), and simulating everything costs days, not weeks
(§7). Keep them on `RB` for reference.

## 4. Run-config file

One JSON file per run, committed under `matchups/runs/<runId>/config.json`.
Everything that changes a battle is inside it; its canonical hash becomes the
run's identity.

```json
{
  "schema": "aoe2-matchup-run/v1",
  "runId": "2026-12-patch-190123",
  "description": "Balance patch 190123; only changed units re-simulated",

  "game": {
    "referenceDb": "matchups/inputs/aoe2_reference_simulation-190123.db",
    "referenceDbSha256": "<sha256>",
    "mechanicsQuery": "ref_units JOIN ref_unit_mechanics WHERE age='Imperial' AND is_default=1",
    "gameBuild": "190123"
  },

  "roster": {
    "rule": "ranking-roster-v1",
    "groups": {"Infantry": "infantry", "Ranged": "archery", "Cavalry": "stable"},
    "extraLines": {"heavy_mounted_crossbowman": "cav_archer", "elite_jarl_varangians": "gunpowder"},
    "excludeKeys": [],
    "requireModes": {"war_chariot_shu": "focus_fire"}
  },

  "selection": {
    "mode": "incremental",
    "baselineRun": "2026-11-campaigns",
    "onlyCivilizations": null,
    "againstCivilizations": "*"
  },

  "battle": {
    "scenarioSet": "frozen-ranking-scenarios-v1",
    "armyCap": 27,
    "countRule": "cheaper side = cap; dearer = max(1, round(cap*sqrt(cheaper/dearer)))",
    "resourceWeights": {"food": 1, "wood": 0.9, "gold": 1.1},
    "costBasis": "effective cost per physical unit (mechanics.cost)",
    "bufferUnits": 0,
    "disableKiting": true,
    "disableAiOrders": true,
    "preserveOwnerOrientation": true,
    "orientation": "sorted-profile-hash"
  },

  "engine": {
    "id": "frozen-civ-matchups-v3+lossless-event-stream-v1",
    "root": "aoe2x/matchups/engines/frozen-civ-matchups-v3",
    "node": "v24.19.0",
    "maxSimulationTicks": "unbounded",
    "wallTimeoutSteps": [180, 600, 1800, 3600],
    "environment": {}
  },

  "sampling": {
    "policy": "distinct-seeds-1-3-10",
    "forecastSource": "baseline-outcome",
    "singleSeedMinimumWinnerHpFraction": 0.25,
    "initialSeeds": [0, 1, 2],
    "extraSeedsOnMixedWinners": [3, 4, 5, 6, 7, 8, 9],
    "sameSeedReplay": "sample:50"
  },

  "execution": {"workers": 16, "phaseContexts": 128, "maxOldSpaceMb": 3072},

  "output": {
    "records": "${MATCHUP_RUNS_STORE}/2026-12-patch-190123",
    "summary": "matchups/runs/2026-12-patch-190123"
  }
}
```

Notes on fields:

- `battle.*`, `engine.*` and the scenario set are hashed into every context's
  **setup hash**. Changing army cap, weights or engine flags therefore produces new
  contexts automatically; nothing old is reused by mistake.
- `orientation`: the 2026 table used ranking-fight orientation where a ranking
  fight existed and sorted hashes otherwise (`selectContext()` in `phase-one.mjs`).
  A fresh full run should use one rule; an incremental run must reuse the baseline's
  stored orientation for unchanged pairs.
- `sampling.forecastSource`: the 1/3/10 rule accepts a single seed only when it
  agrees with a prior forecast. For incremental runs the prior is the baseline's
  outcome for the same pair (if it existed); new pairs fall back to 3/10. See Q3.
- `sameSeedReplay: "sample:50"` replays 50 random completed seeds at the end as a
  determinism check (the 2026 runs replayed every context at first, then none).
- `environment`: allowed `AOE2X_EXP_*` flags. Empty means none; any value changes
  the setup hash.

## 5. Commands

All commands are new (to be built); names are proposals. Each step is resumable
and writes only inside the run's output directories.

```sh
# 0. Freeze inputs: roster, mechanics bundle, scenario set, engine check
python -m aoe2x.matchups freeze   matchups/runs/<runId>/config.json
#    -> summary/{roster.json, mechanics-bundle.json.gz, manifest.json}

# 1. Inventory: profiles -> pairs -> contexts; mark reusable results
python -m aoe2x.matchups inventory matchups/runs/<runId>/config.json
#    -> records/jobs.jsonl.gz, summary/inventory-summary.json (new / reused / identity counts)

# 2. Run (parallel, resumable; supervisor restarts the runner, never two)
python -m aoe2x.matchups supervise matchups/runs/<runId>/config.json --approve-duration
#    runs: node --max-old-space-size=3072 aoe2x/matchups/run.mjs <config>
#    -> records/{runs.jsonl, attempts.jsonl, pair-reviews/, reviews/, progress/, state.json}

# 3. Classify + export reviewed contexts (no battles)
node aoe2x/matchups/export.mjs <config> --output records/snapshots/<NNN>

# 4. (optional) Predict: not recommended; omitted by default

# 5. Build serving DB from baseline results + this run's reviews (no battles)
python -m aoe2x.matchups build-db <config> --output data/golden/civ_matchups_first_pass.db

# 6. Audit: full grid, counts, orientation, hashes, size < 100 MiB (no battles)
python -m aoe2x.matchups audit <config> --serving data/golden/civ_matchups_first_pass.db

# 7. Publish (existing release flow)
python scripts/migration/prepare_release.py && npm run build --prefix apps/web
```

The runner keeps the 2026 safety rules: fsync each seed before state, refuse a
duplicate seed, refuse a changed runtime file or Node version, block a context
after the fourth watchdog step, never turn a timeout into a result, and stop with
`blocked_needs_diagnosis` instead of retrying blindly. It does **not** commit or
push to git.

## 6. Incremental reruns

The reuse key for a stored result is

```
resultKey = H( profileHash(owner2), profileHash(owner3), counts, scenarioHash,
               setupHash(battle + engine + sampling), engineId )
```

Because `profileHash` already covers every mechanics field except `civilization`
(`combatProfileHash()`), and counts and costs are derived from mechanics, any
stat, cost, effect or class change produces a new key.

| Change | What the inventory step does |
|---|---|
| **Balance patch** | Rebuild the mechanics bundle from the new reference DB. Profiles whose hash is unchanged keep their results for every pair whose other side is also unchanged. Each changed profile needs its ~370 pairs re-run (68,916 × 2 / 374 ≈ 368 partners per profile). A change that makes two profiles identical turns their pair into an identity pair. |
| **DLC / new civilization** | New variants that hash to an existing profile reuse everything (existing civilizations have 2–10 profiles found in no other civilization, mean 5.9). Variants with a new profile need pairs against every profile of every other civilization: 2,160 new pairs on average for one civ, 3,640 for the most distinctive existing civ (Khitans) *(computed from `variant-profiles.json`)*. Cells grow by about 10 × 545. |
| **Different conditions** | A new army cap, weights, seeds or engine flag changes the setup hash: everything is new. Run it as a separate `runId` with its own serving DB (or keep it as research). |
| **Engine change** | New `engineId`: everything is new. Never mix engine IDs inside one served table without labelling (the 2026 recovery did, for 6 contexts). |

The baseline for the first incremental run is a **result index** imported from the
2026 records: one row per context (`contextHash`, physical profiles, counts,
scenario, outcome, seeds and per-seed winners/HP/hashes, `physicsVersion`). It can
be built from `RB` without running anything: mismatch and forecast `pair-reviews/`,
adaptive `runs/`, and the recovery snapshot `002`. Rows whose `physicsVersion` is a
recovery variant are imported with that label.

## 7. Compute and time estimates

Measured per-seed wall time on the 2026 host (4 workers, five vCPUs): mean 15.1 s
(forecast), 17.3 s (mismatch), 18.1 s (adaptive); median 9–12 s. Seeds per context:
1.56 under 1/3/10 with a prior (forecast campaign: 61,114 seeds / 39,112 contexts);
3.3 under 3/10 (adaptive: 38,326 seeds / ≈ 11,580 pairs). The tables use 15 s/seed
with a prior and 17 s/seed without, and assume linear scaling with workers at the
same per-core speed. Add 5–10 % for the long tail (single seeds up to 3,306 s;
an exhausted seed costs up to 6,180 s across its four attempts).

| Scenario | Contexts | Seeds (1/3/10 with prior) | Worker-h | Seeds (3/10) | Worker-h |
|---|---:|---:|---:|---:|---:|
| (a) Full rerun | 68,871 | ≈ 107,600 | ≈ 450 | ≈ 227,000 | ≈ 1,070 |
| (b) One new civ (typical / distinctive) | 2,160 / 3,640 | — (no prior) | — | 7,100 / 12,000 | 34 / 57 |
| (c) Balance patch, ~20 changed profiles | ≈ 7,300 | ≈ 11,400 | ≈ 48 | ≈ 24,100 | ≈ 114 |

Wall-clock time:

| Scenario | 4 workers | 16 workers | 32 workers |
|---|---|---|---|
| (a) full, with prior | ≈ 4.7 days | ≈ 28 h | ≈ 14 h |
| (a) full, 3/10 | ≈ 11 days | ≈ 2.8 days | ≈ 34 h |
| (b) one civ, 3/10 | 9–14 h | 2–4 h | 1–2 h |
| (c) 20 profiles, with prior | ≈ 12 h | ≈ 3 h | ≈ 1.5 h |
| (c) 20 profiles, 3/10 | ≈ 28 h | ≈ 7 h | ≈ 3.6 h |

"20 units" in a patch can mean 20 profiles or one change applied to every
civilization's version of a unit (for example 30 Arbalester profiles exist). Use
**≈ 2.4 worker-hours per changed profile** (with prior) or **≈ 5.8** (3/10) to scale.

## 8. Where the records live

Recorded sizes on `RB` (4.37 GB total): adaptive `predictions/` 1.0 GB, forecast
`correction-snapshots/` 0.96 GB (cumulative copies), `progress/` diagnostics
0.77 GB, `monitor-reports/` 0.29 GB, all `runs` journals ≈ 0.16 GB, pair reviews
≈ 0.15 GB, inventories and jobs ≈ 0.01 GB.

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| In the repo on `staging` | Simple | Bloats every clone and every Vercel build; GitHub 100 MB file limit | No |
| Separate git branch | Versioned | The 2026 research branches triggered ≥ 300 Vercel preview builds and the owner's cost hold; the current `vercel.json` does not disable git deployments | Only with deployments disabled for that branch, and still heavy |
| External object storage (one archive per run, fetched by URL and checked by SHA-256, as `scripts/migration/restore_retained.py` already does for the retained release archive) | No build cost; any size | Needs credentials; must pin hashes | **Recommended** |

Commit on `staging` per run, small enough to review:

```
matchups/runs/<runId>/
  config.json              run definition
  manifest.json            input, engine, roster and record-archive hashes; archive URL
  inventory-summary.json   new / reused / identity / held counts
  results.jsonl.gz         one compact row per context (≈ 70k rows, a few MB)
  summary.md               plain-language result: changed cells, close calls, blocked
```

`results.jsonl.gz` is enough to rebuild the serving DB and to act as the next
run's baseline; the full archive is needed only for audits.

Keep `progress/` diagnostics only for exhausted attempts, and write snapshots as
deltas, not cumulative copies; those two choices remove most of the 4.37 GB.

## 9. From rerun to website (on `staging`)

1. Run on a dedicated machine or branch that is never pushed to a Vercel-connected
   remote while running.
2. `build-db` writes a new `data/golden/civ_matchups_first_pass.db` with the same
   schema. Only the **advisor** export component changes version
   (`scripts/migration/export_data.py`); the `engine` component (hash of
   `aoe2x/js_simulation/src`) and the `simulator` component (hash of
   `SIMULATOR_CONFIGURATION_INPUTS`) stay the same, because the pinned engine lives
   under `aoe2x/matchups/engines/` and the mechanics bundle under `matchups/`.
   The audit step asserts both versions are unchanged.
3. Keep the file under GitHub's 100 MiB limit. It is 99.19 MB today with 5.6 MB of
   headroom; one new civilization (~3,600 new evidence rows, ~5,500 cells) could
   exceed it. `build-db` should store compact evidence (outcome, seeds,
   per-seed winner/HP, hashes, run ID) instead of the cumulative `originalEvidence`
   chains, and fail if the file reaches 95 MiB.
4. Copy `matchups/runs/<runId>/` (small files only) and add a release note in
   `docs/releases/`, then `python scripts/migration/prepare_release.py`, run the
   advisor tests (`tests/test_advisor_*.py`, `tests/advisor_model.test.mjs`), commit on
   `staging`, verify the preview, and ask the owner before promoting to `main`
   (CLAUDE.md git rules).
5. `units.data.costs` is read from `data/golden/aoe2_reference_simulation.db` by
   `build_advisor_first_pass.py`. If the run used a different reference DB, take the
   costs from the run's mechanics bundle so the advisor shows the costs that were simulated.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Results differ on other CPUs or Node builds (not tested in 2026) | Pin Node v24.19.0; before any run, replay 50 archived seeds and require identical `finalStateHash`/`eventLogHash`; refuse to start otherwise |
| Accidental engine-identity change | Audit asserts `engine` and `simulator` component versions unchanged; CI already refuses an engine change |
| Pathing stalls (36 of 39,148 forecast contexts, ≈ 0.1 %) | Keep the four-step watchdog and blocked state; publish the baseline outcome with a "not re-simulated" flag or run a separately labelled recovery engine |
| Vercel cost from pushes of run data | External storage; never push run records to a deployable branch |
| Mixing engine versions or orientations in one table | `engineId` and orientation in every result key; audit counts per engine |
| Long unattended runs | Supervisor with approval gate (as `launch-approval.json`); stop on integrity errors |

## 11. Open questions for the owner

| # | Question | Recommendation |
|---|---|---|
| Q1 | The matchup table uses newer unit data (patch 188329 overlay, 132 profiles differ) and a newer engine than the live Battle Sim. Should future reruns keep the campaign's data and engine, or should the live simulator be brought forward first? | Keep the campaign engine and data pinned for reruns now (so the 127,794 existing results stay reusable). Treat updating the live simulator as a separate project. |
| Q2 | Which engine for future runs: frozen V3 (all existing results) or the recovery engine `local-refinement-v3` (fixes the 36 stalls, but only 80 seeds of experience)? | Frozen V3 for incremental reruns. Switch engines only together with a full rerun, and only after a sample comparison. |
| Q3 | For a new civilization there is no prior outcome, so the 1-seed shortcut does not apply. Accept a single decisive seed (winner keeps ≥ 25 % HP) without a prior, or always run 3? | Always run at least 3 seeds for new pairs; use 1/3/10 only where a baseline outcome exists. |
| Q4 | Drop machine-learning forecasts and simulate everything? | Yes. A full rerun is about 1–5 days depending on workers; forecasts needed 3,476 corrections. |
| Q5 | Where to store run records (≈ 0.3–0.5 GB per full run after pruning diagnostics and cumulative snapshots; estimate from the 2026 journal and review sizes)? | External object storage with hashes in the repo; no data branches on Vercel-connected remotes. |
| Q6 | Run on the 4-worker host or a larger machine? | Use 16–32 workers for full reruns after the determinism check; 4 workers is fine for patches. |

## 12. Build plan

Each step ends with a check that needs no website build.

| Step | Work | Done when |
|---|---|---|
| 1. Pinned engine | Copy the 62 runtime files from `RB` commit `6c3049dfd` to `aoe2x/matchups/engines/frozen-civ-matchups-v3/` with `ENGINE.json`; port the pool and worker with `runtimeRoot`. | All 62 hashes match the forecast manifest. Replaying 50 archived seeds (from forecast and mismatch `runs.jsonl`) reproduces `ticks`, `winnerOwner`, `finalStateHash`, `eventLogHash`. `release_metadata()` engine hash and `export_data.py` simulator inputs are unchanged. |
| 2. Inputs and inventory | Mechanics bundle export (from the frozen definition and from a reference DB), roster rule, config schema, inventory builder, result-index importer from `RB`. | From the frozen definition the builder reproduces 555 variants, 374 profiles, 151,223 cells, 68,916 pairs, 45 identity pairs and the 68,871 `pairKey`s in `adaptive/inventory.jsonl.gz`; every imported result maps to exactly one context. |
| 3. Runner and supervisor | Generalised runner (journals, attempts, reviews, 1/3/10 and 3/10 policies, watchdog steps), supervisor, export. | A 100-context run reproduces archived outcomes; killing the runner mid-phase and restarting creates no duplicate seed and finishes the phase; a second runner refuses to start. |
| 4. Serving DB and audit | `build-db` from the result index plus run reviews; compact evidence; `audit`. | The DB built from the 2026 index has the same 151,223 `cells` outcomes and counts as the current `data/golden/civ_matchups_first_pass.db`; advisor tests pass; file < 95 MiB; engine/simulator component versions unchanged. |
| 5. Incremental diff and release | `diff` between mechanics bundles; staging release steps in a runbook (`docs/architecture/runbooks.md`). | A synthetic patch changing one unit schedules exactly that profile's partners (~370 contexts) and reuses everything else; a dry run produces a staging-ready commit with only `data/golden/civ_matchups_first_pass.db*`, `matchups/runs/<runId>/` and a release note changed. |
