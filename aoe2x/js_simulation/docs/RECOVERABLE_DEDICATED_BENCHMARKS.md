# Recoverable dedicated-golden benchmark runner

`tools/run_recoverable_dedicated_benchmark.mjs` is the required runner for
future long dedicated-golden comparisons.

## What it guarantees

- Uses `os.availableParallelism()` and targets 80% of available CPU capacity.
  Each matchup runs in an independent Node process, so the CPU-bound JavaScript
  engine can use multiple cores. PyPy is not used because it cannot accelerate
  the JavaScript simulation.
- The checkpoint unit is one complete matchup: five ratios × five exact tape
  repeats, or 25 attempts.
- A completed matchup is flushed to a temporary file and atomically renamed to
  `checkpoints/<matchup-id>.json` before it is counted complete.
- Every checkpoint contains a run signature covering engine source, mechanics
  fixtures, map data, the authorized archive manifest, and imported truth.
- Resume validates the signature, matchup id, five rows, and 25 attempts. A
  valid checkpoint is skipped; missing work alone is dispatched. Malformed or
  stale checkpoints stop the run instead of being silently mixed.
- Per-attempt engine exceptions are saved as unresolved result rows. A worker
  process crash leaves already committed matchup checkpoints intact.
- `progress.json` is updated atomically with completed, active, and pending
  matchups plus elapsed time and ETA.
- Final merge rejects duplicate or incomplete coverage and requires exactly 19
  matchups, 95 rows, and 475 attempts for the current corpus.

## Run and resume

From the repository root:

```powershell
node aoe2x/js_simulation/tools/run_recoverable_dedicated_benchmark.mjs `
  --output-dir aoe2x/js_simulation/calibration/reports/<run-name>
```

If it stops, run the exact same command again. The runner reuses every valid
checkpoint and starts only missing matchups.

The automatic worker count is `floor(availableParallelism × 0.8)`, capped by
pending matchups. Override it only when memory pressure or interactive work
requires a smaller limit:

```powershell
node aoe2x/js_simulation/tools/run_recoverable_dedicated_benchmark.mjs `
  --output-dir aoe2x/js_simulation/calibration/reports/<run-name> `
  --workers 8
```

`--seed-results <results.json>` may convert one already validated completed
report into per-matchup checkpoints. This was used once to preserve the
historical 2026-08-14 four-shard result; a second invocation reused all 17
then-current checkpoints and executed zero simulations. That historical seed
does not satisfy the current 19-matchup corpus or a different run signature.

## Selective mechanic reruns

Use `tools/run_recoverable_dedicated_rows.mjs` when an engine change can affect
only named matchup families. Its checkpoint unit is one ratio row: five exact
tape repeats. The runner accepts a comma-separated `--matchup-ids` selection,
validates every requested identifier against the dedicated corpus, and merges
only the selected coverage. It retains the same engine-signature validation,
atomic checkpoint writes, resume behavior, 80%-CPU target, and progress file.

```powershell
node aoe2x/js_simulation/tools/run_recoverable_dedicated_rows.mjs `
  --output-dir aoe2x/js_simulation/calibration/reports/<run-name> `
  --matchup-ids arbalester_vs_elite_steppe,imp_elite_skirm_vs_elite_steppe,heavy_cav_archer_vs_elite_steppe
```

The one-range melee experiment used this form because only the three Steppe
families could enter that policy. It checkpointed 15 ratio rows and did not
rerun the other 70 rows in the then-current 17-matchup portfolio. The same
selective runner later checked both Hand Cannoneer families: 10 ratio rows and
50 exact tape repeats.

## Current Hand Cannoneer example

```powershell
node tools/run_recoverable_dedicated_rows.mjs `
  --output-dir calibration/reports/hand_cannoneer_current_engine_2026-08-15 `
  --workers 10 `
  --matchup-ids hand_cannoneer_vs_champion,hand_cannoneer_vs_paladin
```

This run used 10 workers on a machine reporting 24 available CPUs and finished
all 50 simulations in 277.8 seconds. See the
[result summary](../calibration/reports/hand_cannoneer_current_engine_2026-08-15/README.md).

For archive authorization, hash verification, exact-repeat import, scoring,
and final arithmetic checks, use the
[golden tape comparison workflow](GOLDEN_TAPE_COMPARISON_WORKFLOW.md).

## Recovery test

`tests/dedicated-benchmark-rig.test.mjs` simulates a process failure after two
matchups, verifies those two atomic checkpoints remain readable, resumes the
same run, and proves that only the missing matchup executes. It also rejects a
malformed committed checkpoint and validates seed-and-merge coverage.
