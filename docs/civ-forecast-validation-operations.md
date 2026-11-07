# Validate the remaining matchup forecasts

The owner requested on 2026-11-07: “Keep running more matchups, the ones that
are guesses. The eventual target is to validate all guesses. Start with the
lowest confidence ones.” This expands research to the forecasts remaining in
the deployed dataset. It does not authorize recurring website releases,
forecast retraining, physics changes, ranking changes or recommendation/UI
changes.

The new worktree is `/workspace/aoe2_civ_forecast_validation`, branch
`simulations/civ-forecast-validation-2026-11-07`. The old mismatch campaign and
its five blocked contexts remain stopped. No older paused, blocked or completed
campaign may be restarted by this workflow.

## Frozen scope and order

Campaign: `aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07`.
The source is production commit `c907cc23668611851a2112911893929c3b905696`,
database SHA-256 `36626bc0f74242de5482d98362695cec15226eb87cba8767371841a62bd231d5`.
The exact baseline is retained in the campaign's `sources/production-baseline.db`.

There are **39,148 forecast contexts / 50,228 displayed forecast cells**.
All original evidence is retained in `original-evidence.jsonl.gz`, and
`all-forecast-contexts.jsonl.gz` accounts for every forecast exactly once.
`jobs.jsonl.gz` contains **39,124 runnable contexts**, in this order:

| Original category | Runnable contexts |
|---|---:|
| Uncertain/close forecast | 1 |
| Opponent-specific forecast | 734 |
| Weak model agreement | 7,394 |
| Broader agreement | 9,240 |
| Stronger support | 21,755 |

The single uncertain forecast is handled first, then the categories with the
lowest agreement in the preceding mismatch analysis. Within a category, original
evidence ID is the deterministic tie-breaker. These categories are historical
flags, not calibrated probabilities. No prediction value or confidence label is
changed to construct the queue. Early results from this ordered queue must not
be reported as unbiased global accuracy.

`held-contexts.jsonl.gz` retains **24 unfinished contexts**: the five diagnosed
native stalls with separately owner-supplied winners, and 19 cross-engine
projections of prior blockers. Their native measurements remain incomplete.
They need separately reviewed recovery decisions; this ordinary queue does not
blindly retry them or count their supplied/projected winners as measurements.
The campaign and exports cannot claim full completion while these remain held.

## Measurement and provenance gates

The 62 runtime files are byte-identical to the tested mismatch-validation
runtime: `frozen-civ-matchups-v3` with `lossless-event-stream-v1` event storage.
Combat, collision, pathing, arithmetic, acquisition, scenarios and termination
are unchanged. Node must match the version pinned in the manifest.

Four workers use initial seeds 0, 1, 2; if their winners differ, seeds 3–9 are
required. An independent exact replay of a completed seed is required for every
context. The retry schedule is 180/600/1800/3600 wall seconds. A watchdog,
diagnostic, partial set or exhausted attempt is never a result. Diagnose exhausted
failures from the fsynced snapshots before any further retry or separate inventory.

Preserve physical profile order, counts, weighted costs, family, scenario and
policy, plus `sourceContext`, original predictions, root/rule/source hashes,
low-support flags, validation status and all failures. Canonical display winners
are projected from the physical winner's profile hash; reversing a display must
never reverse or replace its underlying physical battle.

## Duration approval and startup

`AGENTS.md` says: “ask before starting any work estimated to take more than one
hour. Earlier broad authorization does not waive this requirement.” This full
campaign takes longer than an hour. Inventory preparation and short control
checks are ready first; ongoing execution remains gated by explicit duration
approval in `launch-approval.json`. Record the actual user approval there before
launch, without marking incomplete seed sets as complete.

Before any launch/resume, inspect the manifest, queue controls, state, journals,
attempts, pair/phase reviews, progress snapshots, logs, locks and live PIDs.
Only restore a missing supervisor after checking its existing runner and lock.
Never start a duplicate. Resume only through:

```sh
python tools/supervise_civ_forecast_validation.py
```

Runner log: `/workspace/aoe2_civ_forecast_validation.log`.
Supervisor log: `/workspace/aoe2_civ_forecast_supervisor.log`.
The supervisor and runner both enforce the saved duration approval. They stop
on invariant failures or `blocked_needs_diagnosis`; do not repeatedly restart
them without examining the actual cause.

The scheduler keeps four workers occupied across 128-context audit phases.
It checkpoints and pushes completed phases and periodic partial records on the
forecast branch only. Check that failed pushes are recovered without repeating
simulations or losing durable measurements.

## Independent research snapshots and release hold

After pushing source/review checkpoints, export only committed, fully reviewed
contexts to a new immutable path:

```sh
node aoe2x/js_simulation/node/civ-matchups/export-forecast-reviews.mjs \
  --reviewed-only \
  --output aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/correction-snapshots/NNN
```

The exporter independently reconciles journals, required seeds, context hashes,
physical orientation, review hashes and exact replay evidence. It preserves
original evidence and excludes held, partial and diagnostic records. The export
schema is `civ-matchup-forecast-corrections-v1`; do not disguise it as the older
mismatch campaign or import it with a tool that has not reviewed this schema.

Do not apply snapshots to the serving DB, rebuild/export the website, run
release CI/previews, push staging/main, or deploy automatically. The research
branch disables Vercel Git deployments for itself. Production remains at the
already approved consolidated release until the owner explicitly authorizes
another release after reviewing new results.

Keep the old mismatch monitor paused unless its owner explicitly retargets it
to this new frozen inventory after duration approval. Any ongoing monitor must
follow these commands and gates, never resume a historical campaign, and report
concise progress only when requested. At the review point, provide actual counts,
changed/retained winners, close cases, confidence-category results, failures and
limitations with source links. A stopped queue is not full validation.
