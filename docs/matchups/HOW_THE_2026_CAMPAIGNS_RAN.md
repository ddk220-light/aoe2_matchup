# How the Oct 31 – Nov 11, 2026 matchup campaigns ran

This document records how the simulation campaigns behind the Matchup Advisor
table were set up, run, checked and published. The goal is that someone with no
prior context can rebuild the run files. Every setting below is traced to a file.
Where something was **inferred** rather than found verbatim, it is marked
*(inferred)*. Gaps are collected in [§10 Not determined](#10-not-determined).

**Path conventions used throughout**

| Short form | Meaning |
|---|---|
| `RB` | the research branch `origin/simulations/civ-forecast-recovery-2026-11-10` (tip `3344324fa`). All earlier campaign branches are its ancestors. Read it with `git show RB:<path>`. |
| `SIM/` | `aoe2x/js_simulation/` on `RB` |
| `C/` | `SIM/calibration/campaigns/` on `RB` |
| *current branch* | `matchup-runs` (created from `staging`); this is where `scripts/`, `data/golden/`, `data/validation/` and `docs/releases/` are read from |

Statistics marked *(computed)* were calculated for this document from the
committed journals on `RB` (for example, the sum of `wallSeconds` across every
`runs*.jsonl` row). They are not quoted from a campaign report.

---

## 1. Plain-language overview

**What was run.** Every fully upgraded Imperial land unit of every civilization
(555 "variants" across 56 civilizations) was matched against every unit of every
*other* civilization: 151,223 displayed cells across 1,540 civilization pairs.
Many variants are mechanically identical across civilizations (for example, most
civilizations' Champions), so those 151,223 cells collapse to **68,916 distinct
pairs of combat profiles**. 45 of those pairs are the same profile on both sides
(nothing to simulate), leaving **68,871 physical battles** that could be run.

Each battle puts up to 27 units of each type on a fixed 16×16-tile arena. The
cheaper unit always fields 27; the more expensive side fields fewer, scaled by
cost. Each battle is repeated with different random "seeds" (the seed changes
each unit's first target choice and reaction delay). Results were stored seed by
seed, with fingerprints (hashes) of the final state and every event.

**Headline numbers** *(computed from `RB` journals)*

| | Value |
|---|---:|
| Individual seeded battle records saved | **127,794** |
| Sum of per-battle wall time | ≈ **586 worker-hours** |
| Workers used | 4 (on a five-vCPU host; `C/civ-matchups-campaign-2026-10-31/CAMPAIGN_PLAN.md`) |
| Calendar time with simulations running | ≈ 7.5 days across Oct 31 – Nov 10 |
| Final table | 151,223 cells, 0 unresolved, every forecast validated or recovered |

**The campaigns, in order, and why each existed**

| # | Campaign (directory under `C/`) | Dates | Why it existed | Result |
|---|---|---|---|---|
| 0 | Ranking campaigns `unit-rankings-*-2026-10-29` | Oct 29 | Unit rankings vs ten benchmark units. They froze the 555 unit profiles, the arena scenarios and the army-size rule that every later campaign reused. | Frozen definition `unit-rankings-path-recovery-2026-10-29/manifest.json` (campaign hash `1ac49a6a…`) |
| 1 | `civ-matchups-inference-phase1-2026-10-31` | Oct 31 | Build the full table **without running anything**: use the ranking fights plus logic rules ("if A beats X and B is strictly better than A, B beats X"). | 182 observed, 319 inferred, 45 equivalent, **68,370 unresolved** profile pairs |
| 2 | `civ-matchups-campaign-2026-10-31/pilot` | Oct 31 | Prove the setup on 24 representative pairs and prove that removing the 150-second game-time limit did not change finished fights. | 79 seeds, all complete |
| 3 | `civ-matchups-campaign-2026-10-31/adaptive` | Oct 31 – Nov 2 | Simulate the unresolved pairs that would "unlock" the most other cells through the inference rules, in 48 phases of 128–256 pairs. | 38,326 seeds; stopped `blocked_needs_review` with **45,896** pairs still unresolved and 19 pairs blocked by engine stalls |
| 4 | `civ-matchups-adaptive-rule-v1-2026-11-01`, `civ-matchups-prediction-first-pass-v1/v2-2026-11-01` | Nov 1 | Make the remaining ~46k pairs usable: a common-opponent selection rule (from phase 20), then frozen machine-learning plus rule forecasts for un-simulated pairs. | 45,896 forecasts, flagged `predicted_unvalidated` |
| 5 | First-pass delivery (`SIM/calibration/reports/civ-matchups-first-pass-provisional-2026-11-02`) | Nov 2–3 | Package a complete table and publish it on the website. | Released Nov 3 (`docs/releases/2026-11-03-matchup-advisor-first-pass.md`) |
| 6 | `civ-matchups-mismatch-validation-2026-11-05` | Nov 5–6 | The old (Python-engine) advisor and the new table disagreed on 18,298 cells. Simulate every disagreement before trusting either. | 10,222 of 10,227 contexts reviewed; 1,164 changed; 5 blocked. Released Nov 7 |
| 7 | `civ-matchups-forecast-validation-2026-11-07` | Nov 7–10 | Owner: "Keep running more matchups, the ones that are guesses … validate all guesses. Start with the lowest confidence ones." | 39,112 of 39,148 forecasts reviewed; 3,476 changed; 36 unfinished. Released Nov 8 (partial) and Nov 10 |
| 8 | `civ-matchups-forecast-recovery-2026-11-10` | Nov 10 | Fix the 36 battles that stalled or ran on an older engine, using separately versioned engine repairs. | All 36 complete; 2 changed. Released Nov 11 |

The net effect: every one of the 45,896 first-pass guesses was eventually
replaced by a real simulation (mismatch campaign plus forecast campaign plus
recovery), so the published table contains only observed, inferred-by-rule or
identical-profile results (`data/golden/civ_matchups_first_pass.db`, `cells`
table: 130,756 observed, 19,647 inferred, 820 identity cells; *computed*).

An older, unrelated pipeline is described in `docs/matchup-baseline.md`
(Python `simulation_real.py`, build 177723, 8–40 seeds). It is **not** how these
campaigns ran.

---

## 2. Inputs

### 2.1 Game build and reference data

| Item | Value | Source |
|---|---|---|
| Reference DB | `data/golden/aoe2_reference_simulation.db`, SHA-256 `234ad0a6c40e413563f737886f6eed2e71c0de41a6a373b569d34dbcaa5c0216` | `referenceDb`/`referenceDbSha256` in `C/unit-rankings-path-recovery-2026-10-29/manifest.json` and every later manifest |
| Game data | All 555 profiles carry `sourceBuild` = DAT SHA-256 `4aa2f0a719e88e5f1502517eddb27c669aeb40c2fe9d8c4f3eec7751c01e7baa`, documented as build **185872** | `profiles[*].sourceBuild` in the frozen manifest; `RB:docs/audits/2026-10-28-v3-unit-model.md` |
| Balance overlay | Selected **188329** changes only: Elephant Archer HP/cost and non-elite Bolas speed | `RB:aoe2x/dbgen/patch188329_stats.py` (docstring), added in commit `58e480b76` |
| DB commit | `58e480b76` "Fix V3 unit mechanics and add resumable ranking pilot" (unit-stat, unique-effect, combat-resolution and projectile changes, refreshed DBs) | `git log RB -- data/golden/aoe2_reference_simulation.db` |
| Mechanics row used | `ref_units` joined to `ref_unit_mechanics` where `age='Imperial'` and `is_default=1`; `mechanics_json` | `prepareFull()` in `SIM/node/full-ranking-campaign.mjs` |

**The current branch does not have this data.** `data/golden/aoe2_reference_simulation.db`
on `matchup-runs` has SHA-256 `b3b2f34d…` (unchanged since `2581cd353`, Sept 23).
Comparing the default Imperial mechanics row for the 555 roster units *(computed)*:
**132 of 555 profiles differ** between the current DB and the campaign DB (130 in
`effects`, 3 in `cost`, 3 in `hp`, 3 in `balance_overrides`). The campaign DB's
mechanics equal the frozen manifest's `profiles[*].mechanics` for all 555.
`aoe2x/dbgen/patch188329_stats.py`, `refresh_v3_effects.py` and `audit_v3_units.py`
exist only on `RB`.

During a campaign the reference DB is not read: every runner takes mechanics from
the frozen definition `C/unit-rankings-path-recovery-2026-10-29/manifest.json`
(5.6 MB; keys `profiles`, `scenarios`, `matchups`, `policy`, `roster`). Each
runner loads it as `FROZEN` (for example `SIM/node/civ-matchups/forecast-validation-lib.mjs`).

### 2.2 The 555-variant roster

Built by `SIM/tools/export_ranking_roster.py` (`export_roster()`), stored as
`roster` in the frozen manifest:

- Every `ref_units` row with `age='Imperial'`, one default mechanics mode per (civ, slug).
- A unit is included when its line maps to group **Infantry** (`UNIT_LINES['infantry']`),
  **Ranged** (`'archery'`) or **Cavalry** (`'stable'`), using `build_slug_to_line()`
  from `aoe2x.rank.derive_unit_rankings` ("first-line-wins") plus `PATCH_LINES`:
  `heavy_mounted_crossbowman→cav_archer`, `elite_varangian_guard`, `elite_hearth_troop_saxons`,
  `elite_jomsviking_danes→militia`, `elite_jarl_varangians→gunpowder` ("Ranged, as
  specified by the owner"; manifest `policy.groupConvention`: "Jarl is Ranged").
- Excluded: `CIV_MISSING_UNITS`, and everything with no land group (naval, Onager,
  Siege Ram, Trebuchet, demolition and fire ships). The frozen roster lists 475
  exclusions, all with reason "naval or anti-building/siege group outside agreed land pools".
- The War Chariot (`war_chariot_shu`) must be in `focus_fire` mode (assertion).
- Result: 555 units (Ranged 274, Infantry 147, Cavalry 134), 56 civilizations.
  Heavy Scorpion and the Khitan Mounted Trebuchet are in the roster (Ranged).

The group label matters only for the ranking campaigns' opponent pools. For civ
matchups every variant meets every variant of every other civilization regardless of group.

### 2.3 Profiles, pairs, contexts and their hashes

All hashes are SHA-256 of canonical JSON (keys sorted, no whitespace), from
`hashCanonicalJson()` in `SIM/src/canonical-json.js`.

| Concept | Definition | Source |
|---|---|---|
| **Profile hash** | Hash of a unit's `mechanics` object with only the `civilization` key removed ("Unknown future fields therefore prevent sharing by default") | `combatProfileHash()` in `SIM/node/ranking-equivalence.mjs` |
| 555 → **374** profiles | Variants with identical profile hashes collapse (assert `profiles.size === 374`) | `profilesAndPairs()` in `SIM/node/civ-matchups/phase-one.mjs` |
| **Displayed cell** | Unordered pair of variants from *different* civilizations: 151,223 cells, 1,540 civ pairs (asserted) | same |
| **Profile pair / `pairKey`** | `"<hashA>|<hashB>"` with the two profile hashes sorted lexicographically; 68,916 pairs (asserted). `a_win`/`b_win` always refer to this order | `key2()` in `phase-one.mjs` |
| **Identity pair** | `hashA === hashB` (two civs' identical units): outcome `equivalent`, evidence type `identity`, never simulated. 45 pairs / 820 cells | `buildDecisions()` in `phase-one.mjs`; `prepare-adaptive.mjs` skips `outcome==='equivalent'` |
| **Physical jobs** | 68,916 − 45 = **68,871** (asserted `jobs.length === 68871`) | `SIM/node/civ-matchups/prepare-adaptive.mjs` |
| **Context** | `{profiles:[owner2Hash, owner3Hash], counts:[n2,n3], scenarioHash, family, engineFamily, weightedCosts:[c2,c3], policy:"27-geometric-cost-v3; zero buffers; disableAiOrders; disableKiting; preserveOwnerOrientation"}` | `context()` in `phase-one.mjs` |
| **Physical orientation** | `profiles[0]` is player 2, `profiles[1]` is player 3. If a corrected-engine ranking fight already existed, its orientation (ranking unit first, benchmark second) was kept; otherwise the two hashes in sorted order | `selectContext()` in `phase-one.mjs` |
| **`contextHash`** | Hash of the context object | `prepare-forecast-validation.mjs` asserts `job.contextHash === digest(job.context)` |
| Job IDs | Adaptive: `cm_` + first 24 hex of `digest({profiles,counts,scenarioHash,policy})`; mismatch `mv_…` and forecast `fv_…` are the first 24 hex of the `contextHash` | `prepare-campaign.mjs`, `prepare-adaptive.mjs`; job rows in `C/*/jobs.jsonl.gz` |
| **Scenario hash** | Hash of the scenario object. Five scenarios exist in the frozen definition; other family/engine-family combinations clone the family's scenario with a different `engineFamily` (pilot manifest has six) | `context()` and `contextScenario()` in `phase-one.mjs` / `run-adaptive.mjs` |

**A result is never transferred into a reversed physical context.** Display
reversal only flips the viewer's perspective (`advisor_matchups()` in
`apps/backend/aoe2_api/services/advisor.py`; stated in the forecast operations doc
"Measurement and provenance gates").

### 2.4 Hashes recorded in the manifests

| Manifest | Key hashes |
|---|---|
| Frozen definition `C/unit-rankings-path-recovery-2026-10-29/manifest.json` | `campaignHash 1ac49a6a…`, `sourceCommit`/`engineBaseCommit 6ee3f32c…`, `nodeVersion v24.19.0`, `referenceDbSha256 234ad0a6…` |
| Inference `C/civ-matchups-inference-phase1-2026-10-31/manifest.json` | `buildHash 5274d7ad…` (asserted by later scripts); `profile-matchups.jsonl.gz` SHA `d628be81…` (recorded in adaptive manifest `phaseOneInput`) |
| Pilot `C/civ-matchups-campaign-2026-10-31/pilot/manifest.json` | `campaignHash b17fefae…`, `sourceCommit 6a00e873…`, 62 `runtimeFiles` |
| Adaptive `…/adaptive/manifest.json` | `campaignHash a864a8c4…`, `sourceCommit 85ac79df…`, `matchupInventory.sha256 5d6ca522…` (68,871 rows) |
| Mismatch `C/civ-matchups-mismatch-validation-2026-11-05/manifest.json` | `campaignHash 89c515d0…`, `physicsVersion frozen-civ-matchups-v3`, `executionVersion lossless-event-stream-v1`, `nativeCampaignHash a864a8c4…`, 62 `runtimeFiles`, 3 `changedOutputFiles` |
| Forecast `C/civ-matchups-forecast-validation-2026-11-07/manifest.json` | `campaignHash d6c03bd7…`, manifest file SHA `063c7328…`, baseline website commit `c907cc23…`, baseline DB `36626bc0…`, the same 62 `runtimeFiles`, 81 `inputFiles` |
| Sampling amendments | v2 `amendmentHash 0760c8fd…`; v3 `4404ca50…` |
| Recovery manifests (`collision-core-v1`, `path-patrol-v2`, `path-patrol-v2-resume-001`, `local-refinement-v3`) | `manifestHash` `82dd1bd4…`, `161a25a6…`, `bca8e2f9…`, `1bc425de…`; each lists `changedRuntimeFiles` |

Every runner re-verifies these at start-up: manifest self-hash, `process.version ===
manifest.nodeVersion`, every runtime/input file SHA-256, and that no `AOE2X_EXP_*`
environment variable is set (`simulationEnvironment: {}`). See `loadManifest()` in
`run-adaptive.mjs` and `verifyManifest()` in `mismatch-validation-lib.mjs` /
`forecast-validation-lib.mjs`.

---

## 3. Battle setup

### 3.1 Army size and cost

From `deriveRecordedBattleSetup()` in `SIM/src/battle-setup.js` (called with
`{cap:27}`) and `policy` in every manifest:

```
weighted(unit) = food + 0.9 × wood + 1.1 × gold        (per physical unit)
cheaper side   = 27
dearer side    = max(1, round(27 × sqrt(cheaperWeighted / dearerWeighted)))
```

| Setting | Value | Source key |
|---|---|---|
| Cap | 27 | `policy.cap` |
| Resource weights | food 1, wood 0.9, gold 1.1 | `policy.weights` |
| Cost basis | "runtime cost per physical unit, full civilization discounts and batch division" (the profile's `mechanics.cost`) | `policy.costBasis`; `effectiveCost: mechanics.cost` in `prepareFull()` |
| Buffer units (player 4) | 0 | `policy.bufferUnits`; `prepareFull()` throws on an auxiliary army |
| Equal cost | both sides 27 (e.g. 27 vs 27 heavy scorpions) | formula |

Example (pilot manifest, matchup `cm_355bc1b4…`): Armenian Halberdier (57.5) vs
Armenian Paladin (142.5) → counts `[27, 17]`.

### 3.2 Arena, formation and engagement

| Setting | Value | Source |
|---|---|---|
| Map | `fixtures/golden_map.json`: 16×16 tiles, 152 obstacle cells | scenario `map` in frozen manifest |
| Formation | 27 recorded cells per side (`placementByOwner`); a smaller army uses the first N cells ("recorded map and first-N formation") | scenarios; `CAMPAIGN_PLAN.md` |
| Placement sources | `current-melee-golden` (melee vs melee, `fixtures/golden_formation_27v27.json`); `current-ranged-golden` (all others, `fixtures/current_ranged_golden_formations.json`) | `scenarios[*].placementSource` |
| Scenario families | `family` = `melee_vs_melee`, `ranged_vs_ranged`, `ranged_vs_melee`, `melee_vs_ranged` (ranged = class `mobile_ranged` or `siege_ranged`); `engineFamily` = `waves`, `rvr`, `kite`, `siege` | `scenarioFamilyFor()`/`isRangedClass()` in `SIM/src/lab-scenario.js`; `resolveFamily()` in `SIM/src/placement.js` |
| Opening move | Melee: `openingPatrolByOwner` 2→(2,13), 3→(13,2). Ranged families: a "Starting" trigger with `patrol` effects to the same points, enemy diplomacy, one victory team per owner | scenarios in frozen manifest |
| Orientation | `preserveOwnerOrientation: true` | job payloads (`jobPayload()` in `run-adaptive.mjs`, `payload()` in the libs) |
| Kiting / AI orders | `disableKiting: true`, `disableAiOrders: true` (no scripted kiting, no AI micro orders) | job payloads; `policy.disableKiting`, `policy.disableAiOrders` |
| Engine config | `{"engagement":"pursuit","pursuit":"","orders":true,"avoid":"","step":"chaser","minRange":"","kiteEngage":"","chasePath":"grid"}` | `engineConfig` in frozen/pilot/adaptive manifests |
| Experiment flags | none allowed (`simulationEnvironment: {}`; runners refuse any `AOE2X_EXP_*` variable) | manifests; `loadManifest()` |
| Seed | `openingSeed` (uint32): drives only the seeded opening acquisition policy (first target and delay before first acquisition) | `runHeadlessJob()` in `SIM/node/run-job.mjs`; `RB:AGENTS.md` "Simulation modeling invariant" |
| Outcome | `win`/`draw`; a fight ends when one side is eliminated. A row stores winner, starting/remaining HP and survivors per side, `ticks` (60 per game second), `finalStateHash`, `eventLogHash` | `runPhase()` in `run-adaptive.mjs`; `record()` in `run-*-validation.mjs` |

### 3.3 Time limits

| Limit | Value | Source |
|---|---|---|
| Game-time ceiling in the shipped engine | `MAX_TICKS = 9000` (150 s) in `src/fight.js`; `MAX_WORLD_TICKS = 9000` in `src/combat/world.js` (still true on the current branch) | source files |
| Ceiling during campaigns | **none**: `maxSimulationTicks: 9007199254740991` | `policy.maxSimulationTicks` |
| How it was removed | Not by editing `src/`. The worker installs a Node module-load hook that rewrites `maxTicks: MAX_TICKS,` and `const MAX_WORLD_TICKS = 9000;` at import time, and adds a progress callback ("Validation-only stop controls and progress reporting. Physics stays untouched.") | `SIM/node/collision-validation-worker.mjs`, `mismatch-validation-worker.mjs`, `recovery-validation-worker.mjs` |
| Proof it changed nothing | Pilot `ceiling-parity.json`: one finished corrected-engine seed per scenario family replayed under the unlimited ceiling; final-state hash, event hash and winner all identical | `SIM/node/civ-matchups/verify-ceiling-parity.mjs` |
| Wall-clock watchdog | Pilot 180 s. Adaptive, mismatch, forecast and recovery: escalating attempts **180 → 600 → 1,800 → 3,600 s**; after the fourth the seed is "exhausted" | `policy.wallTimeoutSteps` |
| Watchdog meaning | "A wall-clock watchdog remains to recover stuck workers; it is not an outcome classifier." Timeouts never become results | `CAMPAIGN_PLAN.md` |

### 3.4 Engine versions: what differs, and where the code lives

| Version name | Used by | Code (exact bytes) | Difference from the previous row |
|---|---|---|---|
| *(unlabelled)* frozen V3, "corrected engine" | Pilot, adaptive | 62 `runtimeFiles` in the adaptive manifest; byte-identical to `RB` commit `85ac79df5` and to `207c31283` *(computed)* | Baseline: ranking-campaign engine from `58e480b76` + collision/pursuit commits of Oct 29 (`c44b1e35e`, `01e810420`, `06d084056`, `302f56bc8`) |
| `frozen-civ-matchups-v3` + `lossless-event-stream-v1` | Mismatch, forecast | 62 `runtimeFiles` in the mismatch manifest = tree of commit `6c3049dfd` *(computed)* | Only `src/canonical-json.js` (streaming canonical hasher), `src/fight.js` (6 lines: hash events in batches instead of retaining them) and `src/combat/world.js` (`retainEvents`/`onEvents` options). "Gameplay stays frozen V3." Proven by `C/civ-matchups-mismatch-validation-2026-11-05/reviews/runtime-parity.json` (`passed: true, physicsUnchanged: true`; 8 exact controls) and `reviews/stream-tests.tap`. The prepare script asserts that only these three files differ |
| `forecast-recovery-inherited-ranged-core-v1` | 1 recovery context | Commit `1ba6aeb88` (manifest `collision-core-v1/manifest.json`, 64 runtime files) | `src/combat/ranged-crowding.js`: cap a ranged-crowd reservation's collision core at the pair's current separation, so an inherited overlap cannot trigger the "starting overlap" error |
| `forecast-recovery-path-patrol-v2` | 77 recovery seeds | Commit `e5526a47e` (cumulative over v1) | `src/combat/chase-path.js`, `src/combat/world.js`: keep a terminal path waypoint until the actor reaches its attack envelope, use the actor position instead of its cell centre, refine failed routes without changing body sizes, release dead opening targets, reverse an unengaged scenario patrol at its endpoint (`RESULTS.md` repairs 2–4) |
| `forecast-recovery-local-refinement-v3` | 2 recovery seeds | Commit `043974137` (cumulative); identical to the `RB` tip *(computed)* | `src/combat/chase-path.js`: refine a bounded narrow corridor to 1/64-tile search cells (`RESULTS.md` repair 5) |

**Comparison with the live engine on the current branch** *(computed by hashing
each manifest's `runtimeFiles` against the working tree of `matchup-runs`)*:

- `aoe2x/js_simulation/src` on the current branch is byte-identical to the merge
  base `2581cd353` (Sept 23, "Integrate patch 185872 simulator…"). It has not
  received any of the research-branch engine commits.
- Against `frozen-civ-matchups-v3`: **15 `src/` files differ** (`combat/attacks.js`,
  `chase-path.js`, `collision.js`, `contact-reservations.js`, `projectile-mechanics.js`,
  `unit-state.js`, `world.js`, `canonical-json.js`, `fight.js`, `dedicated-golden-comparison.js`,
  `matchup-playback.js`, `mechanics-schema.js`, `phase2-batch1-comparison.js`,
  `phase2-wrong-winner-review.js`, `standard-units-comparison.js`), and
  `src/combat/unit-defenses.js` is missing. `node/run-job.mjs` differs, and the
  ten campaign `node/` files plus `tools/export_ranking_roster.py` are absent.
  The three fixtures are identical.
- **Conclusion: the matchup table was produced by an engine and unit data that
  the live Battle Sim does not run.** Reproducing or extending it requires the
  campaign engine and data as a separately pinned copy (see the proposal).

---

## 4. Sampling

### 4.1 Seeds and escalation by campaign

| Campaign | Rule | Source |
|---|---|---|
| Pilot, adaptive | Seeds 0, 1, 2. If those three completed outcomes (`win`/`loss`/`draw`) are not all the same, add seeds 3–9 | `required()` in `run-adaptive.mjs`; `policy.initialSeeds`/`extraSeeds`/`expansionRule` |
| Mismatch | Same 3 → 10 rule, comparing `winnerOwner`; then one **independent exact replay** of the fastest completed seed. Contexts that already had a complete frozen-V3 seed set got only a `native_exact_replay` of one seed plus a source-integrity check | `required()` in `mismatch-validation-lib.mjs`; `reviewJob()` in `run-mismatch-validation.mjs` |
| Forecast, before 14:35Z on Nov 7 | 3 → 10 plus independent exact replay (base manifest) | manifest `policy` |
| Forecast, sampling-policy **v2** `decisive-agreement-screen-v2` (Nov 7 14:35Z) | Run seed 0. If its winner agrees with every original forecast for the context, the loser is eliminated, and the winner keeps **≥ 25 %** of its own starting HP → `single_seed_confirmation`, plus an exact replay. Otherwise seeds 0–2, and 3–9 if winners vary | `C/…forecast-validation-2026-11-07/sampling-policy-v2.json`; `screeningDecision()` in `SIM/node/civ-matchups/forecast-screening-policy.mjs` |
| Forecast, sampling-policy **v3** `distinct-seeds-no-replay-v3` (Nov 7 14:46Z) | Same 1 / 3 / 10 rule, **no same-seed replays**; new reviews record `exactReplay: {required:false, performed:false, exact:null}`. Owner: "it should either be one in our case, three if it is, and then ten, no re-running" | `sampling-policy-v3.json`; `SIM/node/civ-matchups/forecast-no-replay-policy.mjs` |
| Recovery | v3 rule. The 19 older-engine contexts were rerun with seeds 0–2 (they were in `legacyInProgressJobs` or explicitly authorized as `authorizedCrossEngineReruns`) | recovery manifests; `RESULTS.md` |

Both amendments may override only three orchestration/export files
(`forecast-validation-lib.mjs`, `run-forecast-validation.mjs`, `export-forecast-reviews.mjs`)
and assert that no runtime file changes (`verifyPolicyInputs()` in both policy files).
Three contexts in progress at the v2 switch were grandfathered into the old rule
(`legacyInProgressJobs`). Completed seeds always count; a completed seed is never rerun.

### 4.2 Replay verification

`exact()` in `mismatch-validation-lib.mjs` / `forecast-validation-lib.mjs`: a replay
must reproduce `ticks`, `winnerOwner`, `finalStateHash` and `eventLogHash`. The
adaptive runner replayed one completed seed per phase (`runPhase()`); a mismatch
aborts the phase ("exact replay failed"). Purposes recorded per row:
`fresh_measurement`, `native_exact_replay` (mismatch only), `missing_seed_recovery`,
`owner_authorized_cross_engine_rerun`, `fresh_recovery_measurement` (recovery).
Independent replays of new seed sets were stored inside the pair review
(`exactReplay.result`), not as extra `runs.jsonl` rows. 651 forecast reviews carry
a historical replay (`exactReplayChecks` in snapshot 070's manifest).

### 4.3 Ordering

| Campaign | Order | Source |
|---|---|---|
| Pilot | Two pairs per behaviour-class pairing, then by score `1000·[has candidate] + 5·aliases + 20·[unsupported_effect]`, tie-break `pairKey`; 24 pairs | `prepare-campaign.mjs` |
| Adaptive phases 1–19 | Unresolved pairs by `100000·[has candidate] + degree(a) + degree(b) + 10·aliases`; phase 001 = 128 pairs, later 256 | `selectPhase()` in `run-adaptive.mjs`; `policy.phaseOnePairs`/`regularPhasePairs` |
| Adaptive phases 20–48 | `SIM/tools/select_civ_phase.py` (policy `common-c-adaptive-v1`, trained through phase 19): common-opponent estimates (`build_civ_matchup_estimates.py`), inference-gain priority (`plan-active-tests.mjs`), hard cases (`plan_civ_hard_cases.py`), refinement probes (`plan_civ_refinement_loop.py`, from phase 25), and from phase 27 a 32-pair sample of first-pass forecasts per phase. Pairs with verified estimates or deferred predictions were skipped | `select_civ_phase.py`; `C/civ-matchups-adaptive-rule-v1-2026-11-01/manifest.json` |
| Mismatch | Frozen job order in `jobs.jsonl.gz`; 128-context audit phases; "rolling" queue keeps 4 workers busy across phase boundaries | `rolling-validation-queue.mjs`; `queue-controls.json` (`rolling-phase-queue-v2`) |
| Forecast | By frozen forecast tier: `predicted_close` (1), `opponent_specific_forecast` (734), `weak_model_agreement` (7,394), `broader_agreement` (9,240), `stronger_support` (21,755); tie-break original evidence ID | `ORDER` in `RB:tools/prepare_civ_forecast_inventory.py`; `inventory-summary.json` |

### 4.4 Hold rules

- **Exhausted:** after the fourth watchdog/error attempt the context is blocked
  (`blocked.add(...)`); the runner ends `blocked_needs_diagnosis` when only blocked
  work remains. Each blocked case got a written diagnosis
  (`C/*/diagnostics/<jobId>/REVIEW.json`) before any further action.
- **Quarantine:** `queue-controls.json` lists `quarantinedContexts` with the
  diagnosis file and its hash; the runner refuses to run them.
- **Held contexts (forecast):** 24 not queued at all: 5 diagnosed native stalls
  (with owner-supplied winners, recorded as declarations, not measurements) and 19
  "cross-engine projections" (results measured on a repaired engine). File
  `held-contexts.jsonl.gz`; policy text `heldPolicy` in `inventory-summary.json`.
- **Duration gate:** `RB:AGENTS.md`: "ask before starting any work estimated to
  take more than one hour". The forecast supervisor refuses to start unless
  `launch-approval.json` has `durationApproved: true` (approved "Yes start", Nov 7).
- **Cost hold:** see §8.

### 4.5 Classifying a context from its seeds

| Result | Rule | Source |
|---|---|---|
| `a_win` / `b_win` | Every required seed has the same winning owner; that owner's profile hash is compared with the `pairKey` order | `canonicalOutcome()` in the libs; `screeningOutcome()` |
| `close_uncertain` | Winners differ across the completed set (the ten-seed set is kept as mixed, never majority-voted), or no seed has a winner | same |
| `equivalent` | Identity pair (same profile both sides), even if a seeded mirror battle had a winner | `reviewJob()` in `run-mismatch-validation.mjs` |
| Draw | A `draw` row is a completed result; a unanimous draw set classifies as `close_uncertain` *(derived from the code above)* | same |
| Decisive (single-seed rule) | Loser has 0 survivors and 0 HP; winner keeps ≥ 0.25 of its starting total HP | `terminalMargin()` in `forecast-screening-policy.mjs` |
| Never a result | Timeouts, watchdogs, errors, partial seed sets, diagnostics, owner declarations, cross-engine projections | `CAMPAIGN_PLAN.md`; ops docs |

---

## 5. Prediction and inference

### 5.1 Rule inference (no simulation)

`SIM/node/civ-matchups/phase-one.mjs` (`RULE_VERSION = 'phase1-direct-root-inert-group-v5c'`),
rebuilt by `build-civ-matchup-inference.mjs --phase infer-only` after every adaptive
phase and validated by `SIM/tools/validate_civ_matchups_phase_one.py`.

- **Roots** are only completed corrected-engine fights. Original-engine ranking
  records are used to validate rules and flag contradictions, never as results
  (`civ-matchups-inference-phase1-2026-10-31/README.md`).
- **R1_STATIC_DIRECTION:** if a replacement unit is at least as good on every
  static axis (damage dealt to and taken from the fixed opponent, HP, attack delay,
  reload, accuracy, count, opponent count) as the root's unit, the root's winner
  carries over. Only for units with no special effects (`staticSafe()`), the same
  unit master/slug/mode/class, same speed and range (`comparable()`), same scenario
  and the same physical side (`relation()`).
- **R2_ROBUST_TRADEOFF:** transfer robust wins within explicit limits for count,
  damage, durability, range, speed and first-attack delay. After phase 003 it
  abstains when a transferred winner faces more opponents
  (`adaptive/PHASE_003_INFERENCE_REVIEW.md`).
- **R3_TWO_SIDED_STATIC:** both sides replaced, static comparison on both.
- Held-out validation at phase one: R1 13/13 correct on 8 targets; R2
  stronger-winner 99 original + 7 corrected targets, weaker-loser 203 + 6, no
  wrong winners (`README.md`, `rule-validation.json`, `tradeoff-validation.json`).

Growth: 319 inferred pairs at phase one → **11,197** at the end of the adaptive
campaign (first-pass `README.md`).

### 5.2 Forecasts for the remaining pairs

Frozen in `C/civ-matchups-prediction-first-pass-v2-2026-11-01/` (generator
`generator-source.py` = `SIM/tools/civ_prediction_first_pass.py` at freeze time;
`witness-source.py` = `civ_prediction_witnesses.py`; 51,382 predictions, frozen
after phase 28). v1 (40,166 predictions, after phase 27) was superseded.

**Model** (`SIM/tools/evaluate_civ_prediction_coverage.py`):
`HistGradientBoostingClassifier(max_iter=60, max_leaf_nodes=11, max_bins=63,
learning_rate=0.05, l2_regularization=5, random_state=42)` and
`ExtraTreesClassifier(n_estimators=96, min_samples_leaf=4, max_features=0.6,
random_state=42)`, three classes (b win / close / a win). Training: observed
pairs from phases ≤ 20; calibration 21–22; test 23–24. Features (`features()`):
counts and count ratio, unit-line IDs, stat vectors and differences, static
full-health damage each way and derived DPS/time-to-kill (from
`export-static-damage.mjs` output), old-engine ranking HP margins against the ten
benchmark units ("features only, never measurements"), common-opponent outcome and
margin graphs (overall and per line).

**Tiers** (`choose()` / `choose_extended()` in `generator-source.py`):

| Tier | Rule |
|---|---|
| `stronger_support` | At least one non-model method (e.g. two-benchmark rule, common-opponent candidate from the earlier "fifty-percent-v2" pool) agrees, possibly with model agreement; all methods agree |
| `broader_agreement` | Only model agreement: both models pick the same winner, mean top score ≥ 0.775, each ≥ 0.60, close score ≤ 0.15 |
| `weak_model_agreement` | Both models favour the same winner over the other winner and over "close" |
| `opponent_specific_forecast` | Models undecided; all observed-witness directions (shared opponents, close same-opponent neighbours) agree |
| `predicted_close` | Both models favour "close" and no witness |
| `repaired_engine_projection` | 19 pairs whose only evidence was a complete seed set on a repaired side-branch engine (first-pass `README.md` "Separate recovery evidence") |

A cavalry-archer vs light-cavalry guard drops the two-benchmark rule unless shared
melee benchmarks confirm it (`freeze()`). Every forecast carries
`status: predicted_unvalidated`, `verified: false`, its context, rule hash and scores.

### 5.3 How forecasts were checked and overturned

| Check | Numbers | Source |
|---|---|---|
| Frozen-policy screening during adaptive phases | 880 checks, 133 wrong-winner or close-called-decisive | first-pass `README.md` |
| Later prospective checks | 682 checks, 106 such cases; 3,489 surviving forecasts flagged contested | same |
| Mismatch campaign | 10,222 contexts reviewed (7,882 of the 18,298 cells had forecast evidence); 1,164 contexts changed (842 opposite winners, 322 mixed/close) | `state.json`; `docs/releases/2026-11-07-consolidated-matchup-results.md` |
| Forecast campaign | 39,112 reviewed: 31,895 single-seed, 7,217 multi-seed (6,136 three-seed, 1,081 ten-seed); **3,476 changed** (8.9 %), 35,636 retained, 1,081 mixed | `closeout/2026-11-10/analysis.json` |
| Forecast campaign by tier (changed / reviewed) | stronger_support 148 / 21,752 (0.7 %); broader_agreement 822 / 9,235 (8.9 %); weak_model_agreement 2,298 / 7,391 (31 %); opponent_specific 207 / 733 (28 %); predicted_close 1 / 1 | same, `originalConfidenceCategories` |
| Recovery | 36 contexts: 34 retained, 2 changed (one mixed 8–2 over ten seeds) | `RESULTS.md` |

The campaign documents warn that agreement-dependent stopping and tier-ordered
selection mean these rates are **not** unbiased accuracy estimates.

---

## 6. Execution mechanics

### 6.1 Processes

```
supervisor (Python, polls every 30 s, restarts the runner, never two at once)
  └─ runner (Node, one per campaign, holds .runner.lock)
       └─ RankingWorkerPool (4 worker_threads; per-task wall-clock watchdog)
            └─ *-validation-worker.mjs (load hook removes tick cap) → run-job.mjs → src/fight.js
```

| Piece | Adaptive | Mismatch | Forecast | Recovery |
|---|---|---|---|---|
| Runner | `SIM/node/civ-matchups/run-adaptive.mjs` | `run-mismatch-validation.mjs` | `run-forecast-validation.mjs` | `run-targeted-recovery.mjs` (collision), `run-recovery-batch.mjs` (path/patrol, refinement) |
| Supervisor | `SIM/tools/supervise_civ_matchups.py` (stops on `blocked_needs_review` or integrity errors; `.stop` file disables restarts) | `RB:tools/supervise_civ_mismatch_validation.py` | `RB:tools/supervise_civ_forecast_validation.py` (flock on `.supervisor.lock`; requires `launch-approval.json`) | none (one-off) |
| Worker module | `collision-validation-worker.mjs` | `mismatch-validation-worker.mjs` (adds 30-s fsynced diagnostic snapshots to `progress/`) | same | `recovery-validation-worker.mjs` (more diagnostic fields) |
| Node flags | — | `--max-old-space-size=3072` | same | — |
| Workers | 4 (`policy.workers`) | 4 | 4 | 4 |
| Phase size | 128 then 256 pairs | 128 contexts | 128 contexts | one batch |

The pool (`SIM/node/ranking-worker-pool.mjs`) kills and respawns a worker whose
task exceeds its watchdog and returns `{watchdog:true, lastProgress}`.

### 6.2 Checkpointing, resume and locks

- **Write order:** each completed seed is appended to the journal and `fsync`ed
  before any state update (`append()`); `state.json` is written atomically
  (temp file + rename).
- **Resume:** on start the runner re-reads all journals, rejects duplicate seeds,
  rebuilds pending work from `required()`, and continues. Adaptive also rebuilds
  inference from journals ("The phase journals, not the large generated table, are
  the checkpoint source").
- **Locks:** `.runner.lock` holds the PID (stale locks are cleared only if the PID
  is dead or a zombie); `.supervisor.lock` uses `flock`.
- **Git checkpoints:** commit and push the campaign directory to its
  `simulations/…` branch after every phase and every 250 runs or 10 minutes
  (adaptive), or every completed phase and every 10 minutes (mismatch, forecast).
  A failed push sets `remotePending` and the runner continues (`pushCheckpoint()`,
  `checkpoint()`). From Nov 10 a local pre-push hook blocked these pushes (§8).
- **Monitoring:** an hourly scheduled task followed `RB:docs/civ-forecast-validation-monitor-prompt.md`,
  read state, locks and PIDs, and issued a status report per 1,000 reviewed contexts
  (`monitor-reporting.json`, `monitor-reports/milestone-NNNNNN.json`). Live checks
  without running fights: `node tools/audit_civ_forecast_validation.mjs --output <new-path>`.
- **Worktrees/logs:** each campaign ran in its own worktree, e.g.
  `/workspace/aoe2_civ_forecast_validation`, logs `/workspace/aoe2_civ_forecast_validation.log`
  and `/workspace/aoe2_civ_forecast_supervisor.log` (forecast operations doc).
  Recovery manifests reference ledgers by these absolute paths.

### 6.3 Records and schemas

| File | Content |
|---|---|
| `manifest.json` | Frozen definition: policy, runtime/input file hashes, Node version, source commit, inventory hash; self-hash `campaignHash` (or `manifestHash`) |
| `inventory.jsonl.gz` (adaptive) / `jobs.jsonl.gz` | One job per context: `id, pairKey, teamKeys, profileHashes, counts, weightedCosts, scenarioHash, family, engineFamily, policy`; later campaigns add `context, contextHash, evidenceIds, displayedCells, predictionTier, priority, validationMode, nativeMatchupId, categories` |
| `runs/NNN.jsonl` (adaptive) / `runs.jsonl` | One row per completed seed. Common fields: `campaignHash, matchupId, pairKey, seed, startedAt, finishedAt, wallSeconds, outcome (win/loss/draw from player 2's view), winnerOwner, counts, unitCount, opponentCount, profileHashes, scenarioHash, unitStartingHp, opponentStartingHp, unitRemainingHp, opponentRemainingHp, unitSurvivors, opponentSurvivors, ticks, simulationSeconds (= ticks/60), finalStateHash, eventLogHash`. Mismatch/forecast add `contextHash, physicsVersion, executionVersion, purpose`; forecast adds `samplingPolicyHash`; recovery adds `manifestHash, sourceCommit, rawResult, frozenCampaignResult` |
| `attempts.jsonl` | Each failed attempt: `matchupId, seed, purpose, attempt, startedAt, finishedAt, wallSeconds, limitSeconds, watchdog, error, lastProgress{tick, simulationSeconds}, exhausted, progressPath` |
| `progress/<job>-<seed>-<purpose>-<ms>.jsonl` | Diagnostic snapshots every 30 s: tick, memory, per-owner units/HP, event counts, unit positions, actions and targets. Never results |
| `pair-reviews/<jobId>.json` | One per completed context: `context, contextHash, pairKey, physicsVersion, validationMode, samplingPolicyHash, evidenceLevel, samplingDecision, seedCount, requiredSeeds, seedResults[{seed, winnerOwner, ticks, finalStateHash, eventLogHash, winnerHpFraction, recordHash}], exactReplay, outcome, originalEvidenceIds, originalOutcomes, changed, displayedMismatchCells, reviewHash` |
| `reviews/NNN.json` | Phase review: planned/reviewed/changed/blocked jobs, review hashes, status `passed` or `complete_with_blocked` |
| `state.json` | `status, pid, completedPhases, reviewedJobs, savedFreshSeeds, changedJobs, blockedJobs, active, remotePending, lastPushError, singleSeedConfirmedJobs, multiSeedValidatedJobs, samplingPolicyHash` |
| `correction-snapshots/NNN/` | Immutable reviewed-only exports (§7) |
| `diagnostics/<jobId>/REVIEW.json` | Written diagnosis of an exhausted context with a reproducible reader |

### 6.4 Runtime and total compute *(computed)*

| Campaign | Seed rows | Σ wall (h) | Mean / median / p90 / p99 / max (s) | First start → last finish (UTC) |
|---|---:|---:|---|---|
| Pilot | 79 | 0.2 | 9.5 / 6.9 / 12.9 / 43.8 / 47.3 | Oct 31 05:50 → 05:54 |
| Adaptive (48 phases) | 38,326 | 192.8 | 18.1 / 12.2 / 36.2 / 72.2 / 2,060 | Oct 31 06:00 → Nov 2 19:02 (61 h) |
| Mismatch | 28,195 | 135.4 | 17.3 / 11.0 / 35.4 / 66.0 / 2,947 | Nov 5 01:18 → Nov 6 23:29 (46 h) |
| Forecast | 61,114 | 256.9 | 15.1 / 9.3 / 32.1 / 56.6 / 3,306 | Nov 7 12:02 → Nov 10 11:13 (71 h, includes the SIGSTOP pause) |
| Recovery | 80 | 0.5 | 21.1 / 11.0 / 71.0 / 102 / 109 | Nov 10 14:15 → 15:16 |
| **Total** | **127,794** | **≈ 586** | | |

Not included: independent replays stored only inside pair reviews (≈ 7,843 in the
mismatch campaign = 10,222 reviews − 2,379 native replays, *derived*; plus the 651
historical forecast replays), failed attempts (adaptive 125 rows, mismatch 39,
forecast 91), and 57 side-branch recovery seeds that fed the first pass. Simulated
game time totalled ≈ 1,465 h. Throughput on 4 workers: 610–860 seeds per hour.

Hardware: "four on this five-vCPU host" (`CAMPAIGN_PLAN.md`). Node **v24.19.0**
in every manifest; runners refuse any other version. (This session's container
has Node v22.23.4, which the runners would reject.)

---

## 7. Publication: from campaign output to the website

### 7.1 Chain

```
campaign journals + pair-reviews (RB)
  → reviewed-only export (immutable correction snapshot, RB)
  → copy into data/validation/<campaign>/<date or checkpoint>/ (current branch)
  → scripts/apply_advisor_*.py  baseline DB + snapshot → new data/golden/civ_matchups_first_pass.db
  → scripts/audit_advisor_forecast_release.py / verify_advisor_*.mjs (no battles)
  → scripts/migration/prepare_release.py → export_data.py advisor component → Astro build → Vercel
```

| Step | Command (verbatim unless marked) | Notes |
|---|---|---|
| First-pass bundle | `python aoe2x/js_simulation/tools/build_civ_first_pass_delivery.py --campaign … --prediction-dir … --output … --require-complete` *(flags from argparse; values inferred)* | Output `SIM/calibration/reports/civ-matchups-first-pass-provisional-2026-11-02/` (`profile-table.jsonl.gz`, `civilization-table.jsonl.gz`, `variant-profiles.json`, `summary.json`, `manifest.json`) |
| Build serving DB | `python scripts/build_advisor_first_pass.py --source /path/to/civ-matchups-first-pass-provisional-2026-11-02` | `docs/releases/2026-11-03-matchup-advisor-first-pass.md`; pins source commit `207c31283` |
| Mismatch export | `node aoe2x/js_simulation/node/civ-matchups/export-mismatch-reviews.mjs --output <new-snapshot>` (`--through-phase NNN` or `--reviewed-only`) | `docs/civ-matchup-mismatch-validation-operations.md` |
| Mismatch import | `python scripts/apply_advisor_matchup_corrections.py --baseline <baseline> --snapshot <snapshot> --output data/golden/civ_matchups_first_pass.db` | same; baseline must be DB `93e5732f…` |
| Forecast export | `node aoe2x/js_simulation/node/civ-matchups/export-forecast-reviews.mjs --reviewed-only --output …/correction-snapshots/NNN` | forecast operations doc |
| Forecast import | same `apply_advisor_matchup_corrections.py` command; it dispatches to `apply_forecast()` in `scripts/apply_advisor_forecast_corrections.py` when the snapshot `version` is `civ-matchup-forecast-corrections-v3` *(derived from code)* | baseline must be DB `36626bc0…` |
| Forecast audit | `python scripts/audit_advisor_forecast_release.py --baseline … --serving … --snapshot … --output … [--previous-snapshot …]` *(flags from argparse)*; `node scripts/verify_advisor_forecast_snapshot.mjs <snapshot>` *(argv)* | full-grid audit; hash-only check |
| Recovery export | `node SIM/node/civ-matchups/audit-recovery-batch.mjs <dir> <output>`; `python SIM/node/civ-matchups/export-recovery-reviews.py --audit … --audit … --collision … --output …` *(argv/argparse)* | `C/…recovery…/correction-snapshots/002` |
| Recovery import | `python scripts/apply_advisor_recovery_results.py --baseline … --snapshot … --output … --report …` *(argparse)*; `node scripts/verify_advisor_recovery_bundle.mjs <release-bundle.json.gz>` *(argv)* | `data/validation/civ-matchups-forecast-recovery-2026-11-10/2026-11-11/` |
| Release | `python scripts/migration/prepare_release.py`, CI, staging preview, fast-forward `main` | `CLAUDE.md`, `docs/vercel-deployment.md` |

### 7.2 Serving DB `data/golden/civ_matchups_first_pass.db`

Schema (`build()` in `scripts/build_advisor_first_pass.py`):

| Table | Columns |
|---|---|
| `metadata` | `key, value`: `compression_dictionary` (zlib dictionary: profile hashes + preserved keys), `dataset` (JSON summary: counts, `forecast_validation`, `recovery_validation`, `forecastCoverage`, source commit) |
| `units` | `id, key ("Civ|slug"), civilization, data` (JSON: name, line, group, profileHash, icon, costs from `ref_units.final_cost_*`) |
| `evidence` | `id, data` (zlib with dictionary): one row per profile pair (68,916) with `pairKey, outcome, evidenceType`, preserved context/forecast/rule/run fields, and later `originalEvidence`, `mismatchValidation`, forecast and `recovery_validation` provenance |
| `cells` | `a, b, outcome, evidence_type, count_a, count_b, tier, flags, evidence_id`; PK `(a,b)`; 151,223 rows |

- `outcome`: `a_win`, `b_win`, `close_uncertain`, `equivalent` (orientation = cell's `a`, `b`).
- `evidence_type`: `observed`, `inferred`, `identity` (and `predicted_unvalidated` before validation).
- `flags`: bit 1 = contested forecast, bit 2 = weak model agreement; importers set
  `tier=''` and `flags=0` once a cell is measured. Today every cell has `tier=''`, `flags=0`.
- Pages are 32 KiB (`PRAGMA page_size=32768`) so the file stays under GitHub's 100 MiB
  limit; it is now 99,188,736 bytes, SHA-256 `bdbbeacf…`.
- Read by `apps/backend/aoe2_api/services/advisor.py`; exported as the `advisor`
  component by `scripts/migration/export_data.py` (only that component's version
  changes on a data release; engine and simulator components stay the same).

### 7.3 Releases

| Date | What | Serving DB | Note |
|---|---|---|---|
| Nov 3 | First pass | `93e5732f…` (mismatch baseline) | `docs/releases/2026-11-03-matchup-advisor-first-pass.md` |
| Nov 5 | Mismatch checkpoints 001–013 | — | `docs/releases/2026-11-05-*.md`, `data/validation/civ-matchups-legacy-mismatch-2026-11-05/checkpoint-*` |
| Nov 7 | Consolidated 10,222 mismatch reviews | `36626bc0…` (commit `c907cc23`) | `2026-11-07-consolidated-matchup-results.md` |
| Nov 8 | Forecast snapshot 029 (11,478 contexts) | — (commit `a2c96346`) | `2026-11-08-reviewed-forecast-results.md` |
| Nov 10 | Forecast snapshot 070 (39,112) | `eca8b868…` (commit `634554b3`) | `2026-11-10-final-reviewed-forecast-results.md` |
| Nov 11 | Recovery snapshot 002 (36) | `bdbbeacf…` (production `baf6c71c`) | `2026-11-11-recovered-forecast-results.md` |

Every release was a separate explicit owner instruction, recorded as
`authorization.json` with production verification receipts under the campaign's
`website-releases/`.

---

## 8. Known problems and lessons

| Problem | What happened | Handling | Source |
|---|---|---|---|
| 150-s game-time cap | Long fights would end as timeouts | Removed by worker load hook; parity proven on finished fights | `CAMPAIGN_PLAN.md`, `pilot/ceiling-parity.json` |
| Ranged-crowd collision error | Heavy Scorpion mirror (and later Chinese Heavy Scorpion / Polish Heavy Mounted Crossbowman) failed with "starting overlap … separation 0.0245 … extent 0.025" deterministically | Kept blocked; fixed only in `forecast-recovery-inherited-ranged-core-v1` | `adaptive/PHASE_009_COLLISION_DIAGNOSTIC.md`; forecast ops doc |
| Pursuit / patrol stalls | Survivors idle with null targets while blocked/route counters grow; or units keep moving without HP progress (Skirmisher vs Kona/Cavalier/Light Cavalry; Jomsviking vs Guecha) | 12 forecast contexts exhausted, each diagnosed; fixed in `path-patrol-v2` and `local-refinement-v3` | forecast ops doc "Newly exhausted forecast contexts"; `recovery-review/2026-11-10/` |
| Blocked pairs | Adaptive ended with 19 blocked pairs; mismatch with 5 | Never classified; held | `adaptive/state.json`, mismatch `state.json` |
| Mixed-engine contexts | 19 first-pass pairs had results only from side-branch repaired engines; 6 recovery seed sets mix frozen-V3 and recovery seeds | Kept labelled per run (`physicsVersion`); held from the frozen campaign; recovery reviews list every version | first-pass `README.md`; `RESULTS.md` |
| Owner-supplied outcomes | Owner gave winners for the 5 mismatch blockers | Stored as declarations (`user-reviews/2026-11-07-five-blocked-winners.json`), never as measurements | consolidated release note |
| Rule bug | R2 ignored that the fixed opponent's count changes when both armies are recalculated | Rule repaired; validator checks the count condition | `adaptive/PHASE_003_INFERENCE_REVIEW.md` |
| Memory / string limits | Event logs of long fights exceeded V8 string limits | Streaming hash (`lossless-event-stream-v1`), `--max-old-space-size=3072` | `6c3049dfd`; mismatch `README.md` |
| **Cost hold** | ≥ 300 Vercel preview deployments were built from pushes to the mismatch research branch (Nov 5–7). Owner: "Stop deploying to vercel!!? … This is analysis, no prod deployments." | Supervisor and runner suspended with SIGSTOP, later resumed with rebased timers (in-flight `wallSeconds` include the pause); local pre-push hook blocks `refs/heads/simulations/*`; research `vercel.json` sets `git.deploymentEnabled: false` | forecast ops doc "Owner cost hold"; `cost-holds/2026-11-10/` |
| Bias | Agreement-dependent stopping and tier ordering | Report evidence levels separately; no accuracy claims | sampling-policy v2/v3 `limitations` |
| Owner approvals | Long runs and every release needed explicit approval | `launch-approval.json`, `authorization.json` files | `RB:AGENTS.md` |

---

## 9. To reproduce (checklist)

Run from a checkout of the commit recorded in each manifest (or a worktree whose
files match every `runtimeFiles` hash). Install Node **v24.19.0** and Python with
`numpy`/`scikit-learn` (for the forecast step). Unset every `AOE2X_EXP_*` variable.

1. **Freeze roster and profiles** (ranking era, already frozen in
   `C/unit-rankings-path-recovery-2026-10-29/manifest.json`):
   `python aoe2x/js_simulation/tools/export_ranking_roster.py --database data/golden/aoe2_reference_simulation.db --output <roster.json>` *(inferred invocation; flags from argparse)*.
   The manifest itself came from `prepareFull()` in `full-ranking-campaign.mjs` (exact CLI not determined).
2. **Inference table:** from `aoe2x/js_simulation`:
   `node node/build-civ-matchup-inference.mjs --phase infer-only` then
   `python tools/validate_civ_matchups_phase_one.py` (verbatim, inference `README.md`).
   Expect build hash `5274d7ad…`.
3. **Pilot:** `node aoe2x/js_simulation/node/civ-matchups/prepare-campaign.mjs` *(inferred, no args)*;
   `node aoe2x/js_simulation/node/civ-matchups/verify-ceiling-parity.mjs` *(inferred)*; run with
   `node aoe2x/js_simulation/node/full-ranking-campaign.mjs run --campaign aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31/pilot --publish true` (verbatim from `pilot/README.md`).
4. **Adaptive:** `node aoe2x/js_simulation/node/civ-matchups/prepare-adaptive.mjs` *(inferred)*;
   `python aoe2x/js_simulation/tools/supervise_civ_matchups.py` *(inferred)*, which launches
   `node aoe2x/js_simulation/node/civ-matchups/run-adaptive.mjs` (verbatim in the supervisor).
5. **Forecasts:** `python aoe2x/js_simulation/tools/civ_prediction_first_pass.py freeze --campaign … --phase 27 --audit … --output aoe2x/js_simulation/calibration/campaigns/civ-matchups-prediction-first-pass-v2-2026-11-01 --first-untouched-phase 29`
   *(mode and flags from argparse; `--phase 27` and `--first-untouched-phase 29` inferred from the v2 manifest's `reviewedThroughPhase: 27` and `introducedAfterPhase: 28`; the audit inputs are not committed)*.
   Per-phase sampling uses mode `plan`, called from `select_civ_phase.py`.
6. **First-pass bundle and site DB:** §7.1 rows 1–2.
7. **Mismatch:** `python aoe2x/js_simulation/tools/prepare_civ_mismatch_validation.py --comparison … --current-db …` *(argparse)*;
   `node aoe2x/js_simulation/node/civ-matchups/prepare-mismatch-validation.mjs` *(inferred)*;
   run `node --max-old-space-size=3072 aoe2x/js_simulation/node/civ-matchups/run-mismatch-validation.mjs` (verbatim, mismatch `README.md`) under
   `python tools/supervise_civ_mismatch_validation.py`. Export and import: §7.1.
8. **Forecast:** `python tools/prepare_civ_forecast_inventory.py --database <db 36626bc0…>` *(argparse)*;
   `node aoe2x/js_simulation/node/civ-matchups/prepare-forecast-validation.mjs` *(inferred)*; record approval in
   `launch-approval.json`; `python tools/record_forecast_sampling_amendment.py` *(inferred; arguments not determined)*;
   `python tools/supervise_civ_forecast_validation.py` (verbatim). Export, audit, import: §7.1.
9. **Recovery:** `node aoe2x/js_simulation/node/civ-matchups/run-targeted-recovery.mjs <collision-core-v1/manifest.json> --verify-only` (verbatim), then without `--verify-only`;
   `node aoe2x/js_simulation/node/civ-matchups/run-recovery-batch.mjs <path-patrol-v2/manifest.json>` *(argv)*; manifests built by
   `path-patrol-v2/prepare.mjs` and `local-refinement-v3/prepare.mjs`. Audit, export, import: §7.1.
10. **Check:** for any reproduced seed, `ticks`, `winnerOwner`, `finalStateHash` and
    `eventLogHash` must equal the archived row.

---

## 10. Not determined

- The exact command lines for `prepareFull()`, `prepare-campaign.mjs`,
  `prepare-adaptive.mjs`, `prepare-mismatch-validation.mjs`, `prepare-forecast-validation.mjs`,
  `record_forecast_sampling_amendment.py`, the prediction freeze, and the first-pass
  delivery (only argument names were found).
- The prediction model's training inputs: the audit directory with
  `granular-model-predictions.jsonl.gz`, `fifty-percent-v2-candidate-guesses.jsonl.gz`
  and `static-damage.json` is not committed on `RB` (only SHA-256 hashes in the v2
  manifest). The forecasts themselves cannot be regenerated byte-for-byte from the branch.
- The runner that wrote the pilot's `runs/` (its rows have `playbackPath`,
  `partialSimulationTime`, `reason`, which match the ranking-campaign runner, not
  `run-adaptive.mjs`); only the README resume command was found.
- Host details beyond "five-vCPU": CPU model, memory, OS. Whether results are
  bit-identical on other CPUs or Node builds was not tested in the records read.
- How long the Nov 10 SIGSTOP pause lasted (the receipt under
  `cost-holds/2026-11-10/resume-local-only/` was not read in detail).
- Wall time spent on independent replays and failed attempts (not in `runs` files).
- Whether the 57 side-branch recovery seeds (patrol, event-stream, terminal-goal
  ledgers) used one or several engine variants; their source branches were listed
  but not inspected.
