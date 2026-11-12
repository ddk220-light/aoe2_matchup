# aoe2x/matchups — repeatable matchup reruns (build steps 1–2)

Tooling to re-run the unit-vs-unit civilization matchups behind the Matchup
Advisor when a game patch, DLC, new civilization or balance change arrives, or
under different battle conditions. Design: `docs/matchups/RERUN_SYSTEM_PROPOSAL.md`;
how the 2026 campaigns ran: `docs/matchups/HOW_THE_2026_CAMPAIGNS_RAN.md`
(`RB` = `origin/simulations/civ-forecast-recovery-2026-11-10`).

Owner defaults applied: the campaign's engine and unit data are pinned, so the
2026 results stay reusable; frozen V3 engine; no ML forecasts (simulate); bulky
run records stay out of the repo.

**Built:** proposal §12 steps 1 (pinned engine) and 2 (inputs and inventory).
**Not built yet:** steps 3–5 — runner/supervisor/export, serving-DB build and
audit, incremental diff and release. See "Seams for steps 3–5" below.

Nothing here is part of the website: `scripts/migration/prepare_release.py`
packages only a fixed list of `aoe2x/` sub-packages (not `matchups`), and the
pinned engine sits outside `aoe2x/js_simulation/src`, so the live `engine` and
`simulator` release components are unchanged.

## Layout

| Path | What |
|---|---|
| `engines/frozen-civ-matchups-v3/` | The 62 runtime files of the mismatch/forecast campaigns, byte-for-byte from RB commit `6c3049dfd` (1,049,439 bytes), under their original `aoe2x/js_simulation/…` paths, plus `ENGINE.json` (source branch/commit, campaign manifest + hash, per-file sha256, physics `frozen-civ-matchups-v3`, execution `lossless-event-stream-v1`, pinned Node `v24.19.0`, recorded replay evidence per Node version, tick-cap hook targets). Never edit these files. |
| `node/engine.mjs` | Load an engine dir: verify every file hash, the Node-version policy, the `AOE2X_EXP_*` environment. |
| `node/worker-pool.mjs` | Worker pool with per-task wall-clock watchdog and respawn (port of RB `ranking-worker-pool.mjs`, plus `workerData`). |
| `node/battle-worker.mjs` | One seeded battle per message against `workerData.runtimeRoot`; module-load hook lifts the 9,000-tick cap (port of RB `mismatch-validation-worker.mjs`). |
| `node/run-battles.mjs` | Generic runner: jobs JSONL → results JSONL, watchdog steps 180→600→1,800→3,600 s, timeouts never become results. Seam for the step-3 runner. |
| `canonical.py` | Canonical JSON / `hashCanonicalJson` / `combatProfileHash` ports (byte-identical to the JS). |
| `bundle.py` | Mechanics bundles and scenario sets: 2026 importer, reference-DB exporter (ported roster rule + `prepareFull` query), compare. |
| `battle.py` | Army-count formula, scenario/engine families, physical context (ports of `battle-setup.js`, `lab-scenario.js`, `placement.js`, `phase-one.mjs context()`). |
| `config.py` | `aoe2-matchup-run/v1` run-config schema and validation. |
| `inventory.py` | Config + bundle → displayed cells → profile pairs → identity pairs + physical contexts; orientation tables. |
| `results.py` | 2026 result-index importer (first-pass table + mismatch/forecast/recovery snapshots), mapped onto an inventory. |
| `replay.py` | `replay-check`: stratified deterministic sample of archived seeds, exact comparison. |
| `cli.py`, `__main__.py` | `python -m aoe2x.matchups <command>`. |
| `bundles/campaign-2026-185872-188329.json.gz` | 2026 mechanics bundle: 555 variants / 374 profiles / 56 civs, reference DB `234ad0a6…` (149 KB; 1.58 MB raw). |
| `scenarios/frozen-ranking-scenarios-v1.json.gz` | The five 2026 arena scenarios (3 KB). |
| `baselines/campaign-2026/orientation-adaptive-inventory.json.gz` | Physical orientation of the 2026 adaptive inventory (7,859 of 68,871 pairs not in sorted-hash order; 35 KB). |
| `baselines/campaign-2026/orientation-published-results.json.gz` | Orientation of every published 2026 result (26,140 not sorted; 78 KB) — use it for incremental reruns so reused results need no reversal. |
| `baselines/campaign-2026/adaptive-inventory-reproduction.json` | Receipt of `check-inventory-2026`. |
| `baselines/campaign-2026/result-index.json` | Receipt of `import-results` (source hashes, counts, mapping, serving-DB cross-check, index sha256). |
| `configs/*.json` | `full-2026-reproduction`, `single-civ-example` (Franks vs everyone), `units-vs-civs-example` (different conditions), `new-patch-template` (reference-DB input). |

Generated, not committed (default `$MATCHUP_RUNS_STORE`, else `~/.cache/aoe2-matchup-runs`):
run records (`<records>/manifest.json`, `<records>/inventory/{jobs.jsonl.gz, identity-pairs.jsonl.gz, inventory-summary.json}`),
the 2026 result index (`baselines/campaign-2026/result-index.jsonl.gz`, 21.8 MB, sha256 in the receipt) and replay-check reports.

## Commands

```bash
python -m aoe2x.matchups verify-engine [--against-campaign]     # 62 hashes (+ RB campaign manifest)
python -m aoe2x.matchups replay-check --node /opt/node24/bin/node [--record]   # RB: 60 archived seeds, exact
python -m aoe2x.matchups import-2026 [--check]                  # RB: re-freeze bundle/scenarios/orientation
python -m aoe2x.matchups export-bundle --reference-db X.db --game-build N --out bundle.json.gz
python -m aoe2x.matchups compare-bundles A.json.gz B.json.gz
python -m aoe2x.matchups validate-config full-2026-reproduction
python -m aoe2x.matchups freeze      <config>                   # verify inputs, write <records>/manifest.json
python -m aoe2x.matchups inventory   <config> [--out DIR]       # contexts -> <records>/inventory/
python -m aoe2x.matchups check-inventory-2026 [--write-receipt] # RB: vs adaptive/inventory.jsonl.gz
python -m aoe2x.matchups import-results [--config C] [--write-receipt]   # RB: 2026 result index
```

RB commands print `skipped: research branch … is not available` and exit 0
when the branch is missing (`--require-rb` makes that exit 3). Global options
(`--rb-ref`, `--require-rb`) go before the command. A `<config>` is a path or a
name under `configs/`.

Tests: `pytest tests/test_matchups_tooling.py` (≈2 s) and
`node --test tests/js/matchups/*.test.mjs` (≈9 s; replays two archived seeds).

## Key facts and decisions

- **Engine hash check:** all 62 files equal the forecast-validation manifest's
  `runtimeFiles` (identical to the mismatch manifest's), and commit `6c3049dfd`.
- **Node version:** the campaigns pinned `v24.19.0` and refused anything else.
  `replay-check` reproduced 60/60 archived seeds exactly (ticks, winner,
  starting/remaining HP, survivors, `finalStateHash`, `eventLogHash`) on
  `v24.22.1` and on `v22.23.4`; both are recorded in `ENGINE.json`
  `node.verified`. `engine.nodeVersionPolicy`: `exact` (pinned only),
  `verified` (default: pinned or recorded evidence), `warn` (anything, warned).
  Record a new Node version with `replay-check --node <bin> --record`.
- **Inventory:** from the 2026 bundle: 555 variants, 374 profiles, 151,223 cells,
  1,540 civ pairs, 68,916 profile pairs, 45 identity pairs (820 cells), 68,871
  contexts — identical row for row (ids, teamKeys, orientation, counts, weighted
  costs, scenario hashes, families, policy) to RB `adaptive/inventory.jsonl.gz`
  (sha256 `5d6ca522…`) when the adaptive orientation table is used. With plain
  sorted-hash orientation the pairKey set is the same but 7,859 contexts are
  the other way round (the 2026 orientation came from ranking-fight anchors and
  a proximity heuristic in `phase-one.mjs`, which is not ported).
- **Exporter check:** exporting RB's reference DB `234ad0a6…` gives the same 555
  variants (every field), roster order and 475 exclusions as the frozen bundle,
  and the same 68,871 context hashes. The current branch's
  `data/golden/aoe2_reference_simulation.db` (`b3b2f34d…`) differs in 132 of
  555 variants (368 profiles) — it is not the campaign data.
- **Result index:** 68,916 rows = first-pass layer, replaced by 10,222 mismatch
  reviews (7 of them identity mirrors, kept as identity), 39,112 forecast
  reviews and 36 recovery reviews. Final: 58,678 observed, 10,193 inferred, 45
  identity; 125,683 seed records. Every row maps to exactly one inventory slot:
  47,958 same orientation, 20,913 reversed, 45 identity, 0 unmapped, 0
  inventory pairs without a result. Outcome, evidence type and context agree with
  `data/golden/civ_matchups_first_pass.db` for all 68,916 pairs. 58,544 rows are
  `reusable` (observed on frozen V3 or the physics-identical adaptive engine);
  294 seeds are ranking-era and 80 recovery-variant, labelled per seed.
- **Reversed contexts:** a result is never transferred into the other
  orientation. A reversed row is reusable only by a run whose inventory uses
  its orientation (`orientation-published-results.json.gz`).

## Seams for steps 3–5

- **Runner (step 3):** read `<records>/inventory/jobs.jsonl.gz`; build payloads
  exactly as `replay.payload()` (teamKeys' mechanics from the bundle, counts,
  scenario via `bundle.Scenarios.resolve`); run them with
  `node/run-battles.mjs` (or import `runBattles`/`BattleWorkerPool`); journal
  each seed with fsync; implement the 1/3/10 and 3/10 rules from
  `config.sampling` (`required()`/`screeningDecision()` in RB
  `forecast-validation-lib.mjs`/`forecast-screening-policy.mjs`). `engine.mjs`
  already refuses changed files, unverified Node (policy) and experiment env.
- **Reuse:** `resultKey = digest({contextHash, setupHash})` on both inventory
  rows and reusable index rows; `setupHash` covers battle rules, scenario set,
  engine id + files digest, tick ceiling and environment.
- **Serving DB (step 4):** the index row carries outcome, evidence type,
  context and per-seed records (`seedFields` in the receipt); the serving-DB
  cross-check in `results.check_serving_db` is the template for the audit.
- **Diff (step 5):** `bundle.compare_bundles` lists changed variants; changed
  profile hashes change pairKeys/contexts automatically.
