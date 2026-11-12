# aoe2x/matchups — repeatable matchup reruns (build steps 1–5)

Tooling to re-run the unit-vs-unit civilization matchups behind the Matchup
Advisor when a game patch, DLC, new civilization or balance change arrives, or
under different battle conditions. Design: `docs/matchups/RERUN_SYSTEM_PROPOSAL.md`;
how the 2026 campaigns ran: `docs/matchups/HOW_THE_2026_CAMPAIGNS_RAN.md`
(`RB` = `origin/simulations/civ-forecast-recovery-2026-11-10`).

Owner defaults applied: the campaign's engine and unit data are pinned, so the
2026 results stay reusable; frozen V3 engine; no ML forecasts (simulate); bulky
run records stay out of the repo.

**Built:** proposal §12 steps 1 (pinned engine), 2 (inputs and inventory),
3 (runner, supervisor, status, export), 4 (serving-DB build and audit) and 5
(bundle diff, incremental plan, release path). Step-by-step operations:
[`docs/matchups/RUNBOOK.md`](../../docs/matchups/RUNBOOK.md). Which run records to keep:
[`docs/matchups/RECORDS_TRIAGE.md`](../../docs/matchups/RECORDS_TRIAGE.md).

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
| `node/run-battles.mjs` | Batch mode: jobs JSONL → results JSONL, watchdog steps 180→600→1,800→3,600 s, timeouts never become results. `--serve` mode (used by `run`): one attempt per stdin request, one reply line each; exits on stdin EOF or when its parent dies. |
| `runner.py` | `run`: inventory → `run-battles.mjs --serve`; seed journal, attempts log, escalation, blocked state, pair/phase reviews, `state.json`, lock, reuse, `--dry-run` plan. |
| `sampling.py` | `three-then-ten` / `one-three-ten` policies and the 2026 classification (ports of RB `required()`, `screeningDecision()`, `terminalMargin()`, `canonicalOutcome()`). |
| `journal.py` | fsynced JSONL journal with torn-line repair, atomic JSON writes, PID + start-time runner lock. |
| `supervisor.py` | `supervise`: restart with backoff, adopt an orphaned runner, `STOP` file / SIGTERM, `supervisor.json` heartbeat. |
| `status.py` | `status`: counts, rate, ETA, blocked contexts, liveness, stale-lock hint. |
| `export.py` | `export`: re-verified, deterministic reviewed-results snapshot + manifest of hashes. |
| `reproduce.py` | `reproduce-2026`: stratified sample of archived 2026 contexts → two run configs; `--compare` checks every seed exactly. |
| `canonical.py` | Canonical JSON / `hashCanonicalJson` / `combatProfileHash` ports (byte-identical to the JS). |
| `bundle.py` | Mechanics bundles and scenario sets: 2026 importer, reference-DB exporter (ported roster rule + `prepareFull` query), compare. |
| `battle.py` | Army-count formula, scenario/engine families, physical context (ports of `battle-setup.js`, `lab-scenario.js`, `placement.js`, `phase-one.mjs context()`). |
| `config.py` | `aoe2-matchup-run/v1` run-config schema and validation. |
| `inventory.py` | Config + bundle → displayed cells → profile pairs → identity pairs + physical contexts; orientation tables. |
| `results.py` | 2026 result-index importer (first-pass table + mismatch/forecast/recovery snapshots), mapped onto an inventory. |
| `replay.py` | `replay-check`: stratified deterministic sample of archived seeds, exact comparison. |
| `servingdb.py` | `build-db`: the advisor serving DB (same schema as `scripts/build_advisor_first_pass.py`) from a result index + run snapshots; merge rules, stable ids, compact evidence, flag 4. |
| `audit.py` | `audit-db`: verify a built DB against its inputs; compare two DBs; markdown release summary. |
| `apicheck.py` | The advisor API responses of any DB file through the Flask test client (service unchanged) and the export `advisor` component version. |
| `plan.py` | `diff-bundles`: variant/profile diff, per-pair schedule (simulate/reuse/keep/identity), cost estimate, `contexts.json`, run config, optional `priors-file`; also the `run --dry-run` estimate. |
| `archive.py` | `archive`: deterministic essential-records tarball of a run or of the 2026 campaigns; the RB triage rules. |
| `cli.py`, `__main__.py` | `python -m aoe2x.matchups <command>`. |
| `bundles/campaign-2026-185872-188329.json.gz` | 2026 mechanics bundle: 555 variants / 374 profiles / 56 civs, reference DB `234ad0a6…` (149 KB; 1.58 MB raw). |
| `scenarios/frozen-ranking-scenarios-v1.json.gz` | The five 2026 arena scenarios (3 KB). |
| `baselines/campaign-2026/orientation-adaptive-inventory.json.gz` | Physical orientation of the 2026 adaptive inventory (7,859 of 68,871 pairs not in sorted-hash order; 35 KB). |
| `baselines/campaign-2026/orientation-published-results.json.gz` | Orientation of every published 2026 result (26,140 not sorted; 78 KB) — use it for incremental reruns so reused results need no reversal. |
| `baselines/campaign-2026/adaptive-inventory-reproduction.json` | Receipt of `check-inventory-2026`. |
| `baselines/campaign-2026/result-index.json` | Receipt of `import-results` (source hashes, counts, mapping, serving-DB cross-check, index sha256). |
| `baselines/campaign-2026/serving-dataset.json` | The `dataset` metadata of the 2026 serving DB, verbatim (11.7 KB; served in `/api/advisor-catalog`): the base `build-db` updates. |
| `baselines/campaign-2026/records-archive.json` | Receipt of `archive --rb-2026 --with-index` (sha256, sizes by class/kind; no file list). |
| `configs/*.json` | `full-2026-reproduction`, `single-civ-example` (Franks vs everyone, reusing the 2026 result index), `units-vs-civs-example` (different conditions), `new-patch-template` (reference-DB input). |

Generated, not committed (default `$MATCHUP_RUNS_STORE`, else `~/.cache/aoe2-matchup-runs`):
run records (see "Runner" below; `inventory/` holds `jobs.jsonl.gz`, `identity-pairs.jsonl.gz`,
`inventory-summary.json`), the 2026 result index (`baselines/campaign-2026/result-index.jsonl.gz`,
21.8 MB, sha256 `d672f226…` in the receipt) and replay-check reports.

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
python -m aoe2x.matchups run       <config> [--workers N] [--records DIR] [--force] [--retry-blocked] [--dry-run]
python -m aoe2x.matchups supervise <config> [--records DIR] [--heartbeat 30] [--max-failures 5]
python -m aoe2x.matchups status    <config> [--records DIR] [--json]
python -m aoe2x.matchups unlock    <config> [--records DIR]     # remove a dead runner's lock (refuses if alive)
python -m aoe2x.matchups export    <config> [--records DIR] [--out DIR]
python -m aoe2x.matchups reproduce-2026 DIR [--per-stratum 3]  # RB: sample 2026 contexts -> DIR/<rule>/config.json
python -m aoe2x.matchups reproduce-2026 DIR --compare          # RB: after running both configs
python -m aoe2x.matchups diff-bundles OLD NEW [--config C] [--out DIR [--run-id ID] [--priors]] [--resimulate-kept]
python -m aoe2x.matchups build-db  <config> --out X.db [--snapshot DIR]... [--previous-db PUB] [--carry-unsimulated] [--costs reference-db|bundle] [--no-index]
python -m aoe2x.matchups audit-db  X.db [--config C --snapshot DIR...] [--previous-db PUB | --compare DB] [--api] [--md F] [--json F]
python -m aoe2x.matchups archive   <records> --out F.tar.gz [--config C]     # or --rb-2026 [--with-index] / --triage
```

Typical run: `inventory <config>` (or let `run` build it), `run <config> --dry-run`
(reused vs scheduled), then `supervise <config>` in a terminal multiplexer;
`status <config>` at any time; `touch <records>/STOP` (or SIGTERM the
supervisor) to stop; remove `STOP` and `supervise` again to resume; `export`
when done (or at any point for a partial snapshot). Nothing commits, pushes or
uses the network.

RB commands print `skipped: research branch … is not available` and exit 0
when the branch is missing (`--require-rb` makes that exit 3). Global options
(`--rb-ref`, `--require-rb`) go before the command. A `<config>` is a path or a
name under `configs/`.

Tests: `pytest tests/test_matchups_tooling.py tests/test_matchups_release.py` (≈15 s + ≈5 s; the runner tests drive
an in-process scripted backend; sampling tables come from real 2026 seed sets in
`tests/fixtures/matchups/sampling-2026.json`) and `node --test tests/js/matchups/*.test.mjs`
(≈12 s; replays archived seeds, also through `--serve`).

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

## Runner (step 3)

```
supervise (Python; flock .supervisor.lock; restarts with backoff 5 s → 5 min; STOP file / SIGTERM)
  └─ run (Python; .runner.lock = PID + process start time; journals, sampling, reviews, state)
       └─ node run-battles.mjs --serve (pinned engine; one attempt per request)
            └─ BattleWorkerPool → battle-worker.mjs × execution.workers
```

Everything comes from the run config: inventory (`selection`, incl. the
optional `selection.contexts` list), engine and Node policy, wall-timeout
steps, sampling policy and its priors, workers, records directory. The
journals' `campaignHash` is the **run hash** (`config.run_hash`: the config
without `output`, `execution` and `description`), so moving records or
changing the worker count does not fork a run, while any change that could
change a result refuses to resume into old records.

**Records** (`<records>`, outside the repo):

| File | Content |
|---|---|
| `runs.jsonl` | One line per completed seed, appended + fsynced before anything that depends on it. The 2026 fields (`campaignHash, matchupId, pairKey, contextHash, physicsVersion, executionVersion, seed, startedAt, finishedAt, wallSeconds, purpose, samplingPolicyHash, counts, profileHashes, scenarioHash, outcome, winnerOwner, unitStartingHp, opponentStartingHp, unitRemainingHp, opponentRemainingHp, unitSurvivors, opponentSurvivors, ticks, simulationSeconds, finalStateHash, eventLogHash`) plus `runId, resultKey, engineId, nodeVersion, attempt, limitSeconds, samplingPolicy, unitCount, opponentCount`. |
| `attempts.jsonl` | One line per failed attempt (2026 fields: `matchupId, seed, purpose, attempt, startedAt, finishedAt, wallSeconds, limitSeconds, watchdog, error, lastProgress, exhausted, progressPath`, plus `contextHash, unfinishedOutcome, nodeVersion`); `{"unblocked": true}` lines from `run --retry-blocked`. |
| `pair-reviews/<jobId>.json` | `aoe2-matchup-review/v1`, a superset of the 2026 pair review: `context, contextHash, pairKey, resultKey, jobId, physicsVersion, validationMode, evidenceLevel, samplingDecision, seedCount, requiredSeeds, seedResults[{seed, winnerOwner, ticks, finalStateHash, eventLogHash, winnerHpFraction, recordHash}], exactReplay, outcome, priorOutcomes, priorSource, changed, displayedCells, reviewHash`. |
| `reviews/NNN.json` | Phase review per `execution.phaseContexts` contexts (planned/reviewed/reused/blocked, review hashes, `passed`/`complete_with_blocked`). |
| `reuse.json` | Contexts not run because the baseline index has a reusable result (`[jobId, resultKey, outcome, source]`). |
| `state.json` | `aoe2-matchup-run-state/v1`: status (`running`, `interrupted`, `complete`, `complete_with_blocked`, `failed`), pid, `contexts{total, complete, reviewed, reused, blocked, remaining, active}`, `seeds{saved, savedThisSession, failedAttempts}`, outcomes, evidence levels, `blockedJobs`, `active` attempts, journal repair. Atomic rewrite. |
| `sessions.jsonl`, `logs/` | Runner starts/ends (repairs, stale locks cleared); Node stderr, supervisor events and heartbeat (`supervisor.json`). |
| `progress/` | 30-s diagnostic snapshots, by default only for attempts after a first timeout (`execution.diagnostics`). Never results. |

**Rules.** Work order is the inventory order (sorted `pairKey`); all
decisions are pure functions of the journals, so a kill at any point followed
by a restart reproduces the uninterrupted journal (only timestamps, wall
seconds and attempt numbers can differ). A torn trailing journal line is cut
off on restart; any other corrupt line, a duplicate `(context, seed)` line, a
line of another run or a review that does not follow from the journal stops
the runner (exit 2) — the supervisor does not restart integrity errors. A
seed gets one attempt per `engine.wallTimeoutSteps` step; each failure is
logged before the next attempt, so escalation survives restarts; after the
last step the context is **blocked** (reported by `status`, exported in
`blocked.jsonl.gz`, never retried unless `run --retry-blocked`). If the Node
backend dies or hangs (no reply 120 s past its watchdog), its in-flight
attempts are logged as failures (`BackendExit`/`BackendHang`) and it is
restarted. Exit codes: 0 finished, 1 crashed, 2 integrity/config, 75 lock
held, 143 stopped.

**Sampling** (`sampling.py`): `three-then-ten` = seeds 0–2, then 3–9 when the
three `winnerOwner`s differ (RB `forecast-validation-lib.mjs required()`);
`one-three-ten` = seed 0 alone only with a prior that agrees, the loser wiped
out and the winner ≥ 25 % HP (RB `forecast-screening-policy.mjs
screeningDecision()`), else the 3 → 10 rule. Priors: `forecastSource`
`baseline-outcome` (the index row with the same `contextHash`), `priors-file`
(`{contextHash|pairKey, outcomes}` rows), or `none`. A context with no prior
never takes the shortcut (and its first three seeds start together).
Classification: unanimous winner → `a_win`/`b_win` in `pairKey` order, else
`close_uncertain` (mixed sets are not voted; all-draw is `close_uncertain`).

**Reuse.** With `selection.baselineResults` (`{"index", "sha256"}` of the
`import-results` output) every inventory context whose `resultKey` has a
reusable index row is recorded in `reuse.json` and not run; `--force` or
`selection.rerunReusable: true` runs them. `run --dry-run` prints the split.

**Export** (`aoe2-matchup-run-snapshot/v1`): `manifest.json` (config, run,
bundle, scenario-set, setup, engine id/files digest/Node versions, inventory,
result-index, journal and per-file hashes, counts, `snapshotHash`),
`results.jsonl.gz` (one row per reviewed context **in result-index row shape**,
seeds as `SEED_FIELDS` lists), `reused.jsonl.gz`, `blocked.jsonl.gz`. Every
review is re-verified against the journal first. No timestamps or wall times,
sorted rows, sorted keys, gzip mtime 0: the same journals give the same bytes.

### Step-3 acceptance (this machine: 4 vCPUs, Node v22.23.4)

| Check | Result |
|---|---|
| Reproduction (`reproduce-2026`, sampler `reproduce-2026-strata-v1`, 3 per stratum, fast fights only: ≤ 20/45/150 archived wall-s per 1/3/10-seed context) | **102 contexts, 468 seeds, 0 mismatches**: `three-then-ten` 38 contexts / 212 seeds (31 mismatch + 7 pre-amendment forecast reviews; 24 three-seed, 14 ten-seed incl. 4 with draws); `one-three-ten` 64 / 256 (24 single-seed, 24 three-seed, 16 ten-seed incl. 4 with draws; priors = the 2026 forecast outcomes). Every seed's outcome, winner, ticks, starting/remaining HP, survivors, `finalStateHash`, `eventLogHash` equals the archived `runs.jsonl` line; seed sets, classifications and (one-three-ten) the full `samplingDecision` equal the archived reviews. All four families; a_win 36, b_win 36, close_uncertain 30. |
| Kill test (32 one-three-ten contexts, 126 seeds, 4 workers) | Uninterrupted 345.6 s. Runner SIGKILLed 3 times (after 26.6, 42.8, 36.0 s) then resumed; separately under `supervise`: runner SIGKILLed twice (restarted after 5 s), supervisor SIGKILLed (its orphaned runner was adopted by the next supervisor), runner SIGKILLed again. All three journals: 126 lines, 126 unique `(context, seed)`, sorted content identical (timestamps/wall excluded); state `complete`, 32 reviewed, 126 saved; `export` results byte-identical; no Node process left behind. |
| Lock | Second runner exits 75 while the first lives; `unlock` refuses a live owner; after SIGKILL `status` reports the stale lock, `unlock` clears it; a runner also clears a dead owner's lock itself (logged); SIGTERM → exit 143, `interrupted`, lock removed. |
| Timeout path (`wallTimeoutSteps` [4, 5, 6, 8] s, 6 contexts) | The ~40-s context: seeds 0–2 each failed at 4, 5, 6 and 8 s (12 attempts logged, diagnostics from the 2nd attempt) → `blocked`; 5 other contexts complete (3 after one 4-s timeout); run `complete_with_blocked`, exit 0; `status` and `export` (`blocked.jsonl.gz`) list it. |
| Reuse (`single-civ-example`, 2026 index) | 3,670 contexts: **2,992 reused, 678 scheduled** (657 rule-inferred, 19 ranking-era seeds, 2 recovery-engine seeds: none has a reusable frozen-V3 result); `--force`: 0 reused, 3,670 scheduled. |
| Export determinism | Two exports of each reproduction run byte-identical (all four files). 102 contexts: results 63.8 KB + manifests 11.3 KB. The 58,678 observed 2026 rows in snapshot row shape: 19.8 MB → ≈ 23 MB for 68,871 contexts (2.1 seeds/context); ≈ 30 MB if every context needed 3.3 seeds. |
| Throughput (4 workers) | three-then-ten 1,652 seeds/h (mean 8.6 s/seed), one-three-ten 1,375 seeds/h (10.3 s/seed; seed 0 runs alone before 1–2), 1,488 overall; per-seed wall 1.01× / 1.10× the 2026 host. With the 2026 per-seed means (15.1 s / 17.3 s): full rerun with prior ≈ 107,600 seeds ≈ 5 days, full 3/10 ≈ 227,000 seeds ≈ 12 days, one new civilization (no prior, 3/10) 7,100–12,000 seeds ≈ 9–16 h. Scales roughly linearly with workers on more cores. |

## Serving DB and release (steps 4–5)

**`build-db <config>`** builds `civ_matchups_first_pass.db` (schema of
`scripts/build_advisor_first_pass.py`, 32 KiB pages) for the roster of the
config's bundle from the result index plus `--snapshot` dirs. Merge rules
(`servingdb.py` docstring): snapshot rows replace index rows by `pairKey`
(manifest, file, bundle, setup, engine and index hashes checked first);
`reused` rows keep the index row (checked); a `blocked` pair keeps its index
row if it has one, else its cells keep the **previous release's** result
(`--previous-db`); both get `flags` bit **4 = not re-simulated** (the site reads
only columns 0–5 of a cell row, so it ignores the flag) and the evidence gets
`rerun` / `carriedTo`. Cells of a pair with no result fail the build unless
`--carry-unsimulated`. Every stored context must equal this config's context for
the two profiles (a result from other battle rules is refused). Ids: without
`--previous-db` the 2026 rule (units by key, evidence by first appearance);
with it, every surviving unit key and `pairKey` keeps its id, new ones are
appended, so untouched civilization pairs stay byte-identical in the API. The
`dataset` metadata (served in the catalog) is the previous DB's (or the 2026
one in `baselines/`) with recomputed counts, `matchupRuns` and
`notResimulatedCells`; unchanged when nothing changed. A `matchup_build`
metadata row (not served) records every input hash. Refuses ≥ 95 MiB.

**Compact evidence** (`aoe2-advisor-evidence-compact/v1`). The 2026 DB is
99.19 MB, 89.3 MB of it the `evidence` table (originalEvidence 97 MB raw,
forecastValidation 70 MB, mismatchValidation 26 MB, …). `/api/advisor-evidence/<id>`
has no caller in `apps/web` (grep). The compact row keeps `pairKey`, `outcome`,
`evidenceType`, physical `context`, `source`, `jobId`, `evidenceLevel`,
`validationMode`, `ruleId`/`ruleVersion`, engine labels `physics`, per-seed
`[seed, winnerOwner, ticks, unit/opponent remaining HP, survivors, starting HP]`
and mirror-validation seeds. It **drops**: per-seed `finalStateHash`/`eventLogHash`
and record hashes (still in the result index and run snapshots, pinned by hash in
`matchup_build`), `contextHash` (= digest of `context`), and the 2026 chains
(`originalEvidence`, `originalPrediction`/`prediction*`, `sourceContext`,
`sourceOutcome`, `rootAnchorIds`, `reasonCodes`, `sourceRunIds`/`validationRunIds`,
`verified`/`needsValidation`, the forecast/mismatch/recovery review blocks with
`reviewFile`, `reviewHash`, campaign hashes, exact-replay records); those stay in
git history of the DB (`bdbbeacf…`) and in the records archive. Better zlib
dictionary (profile + scenario hashes + vocabulary, 25.5 KB). Result: **19.56 MB**.
Per added civilization (≈ 10 units): ≈ 5,550 cells × 62 B ≈ 0.34 MB plus 2,200–3,600
new evidence rows × ≈ 160–170 B ≈ 0.4–0.6 MB, i.e. **≈ 0.7–1.0 MB per civilization**
(60 MB would be reached after ≈ 40 more). The dictionary holds ≈ 110 more profiles
before older hashes fall out (then ≈ +60 B per row that names them).

**`audit-db`** verifies a DB against its inputs (inputs/hashes, roster, every
displayed cell once, cell → evidence → index/snapshot row, orientation, counts,
type, setup context, seed classification, dataset counts, flags, size) and,
with `--previous-db`/`--compare`, compares two DBs by unit key (cells by status,
civilization and evidence-type transition; re-simulated and carried contexts;
`--api`: response-level and civilization-pair-level byte identity and the
`advisor` component version). Writes a markdown release summary (`--md`).

**`diff-bundles OLD NEW`**: variants changed (with the mechanics fields) /
added / removed, profiles new/gone, and every profile pair of the new roster as
`simulate` / `reuse` / `keep` (rule-inferred, ranking-era or recovery-engine
result of two unchanged profiles) / `identity`; cost (expected seeds 3.3 per
context without prior, 1.56 with; worker-hours at 1,490 seeds/h per 4 workers and
conservatively 17.3 s/seed/worker) by civilization; `--out` writes `plan.md`,
`plan.json`, `contexts.json` (for `selection.contexts`) and with `--run-id` a ready
`config.json`; `--priors` a `priors-file` (previous outcomes of the same cells in
the new pair order; off by default, owner Q3). `run --dry-run` prints the same
estimate and a one-line `summary`.

**`archive`**: [`docs/matchups/RECORDS_TRIAGE.md`](../../docs/matchups/RECORDS_TRIAGE.md).

### Step 4–5 acceptance (this machine)

E2E_PLACEHOLDER
