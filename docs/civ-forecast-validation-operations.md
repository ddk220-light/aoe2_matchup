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

## Newly exhausted forecast contexts

`fv_c553e033f98149a99dc0ffcf`, seed 1, Bohemian Elite Hussite Wagon /
Khitan Mounted Trebuchet, counts 27/19, exhausted all four prescribed watchdogs
at 2026-11-07T13:59:13.230Z. Its four timelines reproduce fixed surviving
positions, HP, actions and targets while blocked/route-planning counters grow.
The exact routing/acquisition/range cause and real-game outcome remain unknown.
See `diagnostics/fv_c553e033f98149a99dc0ffcf/REVIEW.json` and its reproducible
reader, bound to source commit `43f129b7852722b4d6c8f87928104b34c98e447f`.
Only seed 0 is saved; seeds 1 and 2 and an exact pair replay are missing.
This is an additional dynamic blocked job, separate from the frozen 24 held
contexts. No result is assigned and no further retry is authorized by this
diagnosis. Preserve the live ordinary queue and all existing failures.

## Current execution policy: 1 / 3 / 10 distinct seeds, no replays

The owner explicitly removed all same-seed replays: “In any case, it should
either be one in our case, three if it is, and then ten, no re-running.”
`sampling-policy-v3.json` records amendment `4404ca505096341c2bcea03e1376ed5d7c27f7a1f6d6452bd92a9a526273c30c`.
This supersedes every earlier replay requirement for new research results.

- One execution of seed 0 is sufficient for a clear forecast agreement: losing
  army eliminated and winning army retaining at least 25% of its starting HP.
- Close or disagreeing results require three distinct seeds, 0–2.
- If those winners vary, require ten distinct seeds, 0–9.
- Never rerun a completed seed. There is no fourth or eleventh execution for
  repeatability. Existing completed seeds count toward the required total.
- Existing replay evidence stays intact. New records explicitly say that replay
  was not required and was not performed; never invent a replay success.
- Timeouts are not results. Preserve failures, held contexts and diagnosed
  blockers; no new retry of an exhausted context is authorized here.

At this transition, 651 existing reviews and 2,396 native records were preserved
under `policy-transitions/distinct-seeds-no-replay-v3/`. The previous v2 policy
file, its helper/tests and all earlier reviews and snapshots are immutable.
The same 62 runtime files, physical contexts, frozen forecasts and ordered queue
are retained. Only research execution/verification code changes. The supervisor
command and four-worker setup remain the same. No website change is authorized.
Single-seed confirmations remain distinct from multi-seed validations; this
stopping rule does not establish unbiased forecast accuracy.

## Historical adaptive policy v2 (superseded by v3)

The owner explicitly requested a decisive agreeing first run to stop early, with
additional runs for close or disagreeing results, then instructed: “Use this as
the approach to go forward. Update the scheduled tasks and the runner so that
this is the logic that is used in this process.”

This supersedes the uniform three-seed minimum for new ordinary contexts.
`sampling-policy-v2.json` records the separate amendment
`0760c8fd7ee4274728b2211cf765172daed25551eeb1d4495498a28663602b70`. The original campaign
manifest/hash, production source, inventory order and all 62 runtime hashes stay
frozen. The amendment binds exactly three research orchestration/export source
overrides and new policy/test files; no physics or battle inputs are overridden.

- Run seed 0 first. If its canonical physical winner agrees with every original
  forecast for the context, the losing army is eliminated, and the winning army
  retains at least 25% of its own starting total HP, accept a
  `single_seed_confirmation` after the independent exact replay passes.
- A close/undecisive result, draw, forecast disagreement, or original close
  forecast requires seeds 0–2. If those winners vary, require all seeds 3–9.
- Every accepted result still needs the independent exact replay. The same-seed
  replay verifies reproducibility; it is not another independent seed. Thus a
  straightforward confirmation uses two executions, not four.
- Every previously collected seed/review stays intact. The 615 reviewed contexts
  at the transition retain their original multi-seed reviews. The three saved
  unfinished contexts are explicitly grandfathered into the old seed requirement;
  the exhausted one remains blocked and is not retried. Additional collected
  evidence can never be ignored to qualify for an early stop.

The immutable transition archive retains 2,250 native records, prior attempts
and the stopped state under `policy-transitions/decisive-agreement-v2/`, bound
to source commit `1398877b3000af777413a427799f778b01cf2e18`. No old review or snapshot
is relabeled. State, phase reviews and v2 correction exports count
`singleSeedConfirmations` separately from `multiSeedValidations` (state keys use
`singleSeedConfirmedJobs` and `multiSeedValidatedJobs`). A single confirmation
does not demonstrate seed robustness. Agreement-dependent stopping introduces
selection bias: report observed changes by evidence level and never present the
combined retained percentage as an unbiased forecast-accuracy estimate.

## Measurement and provenance gates

The 62 runtime files are byte-identical to the tested mismatch-validation
runtime: `frozen-civ-matchups-v3` with `lossless-event-stream-v1` event storage.
Combat, collision, pathing, arithmetic, acquisition, scenarios and termination
are unchanged. Node must match the version pinned in the manifest.

Four workers use the current 1 / 3 / 10 distinct-seed policy above. No same-seed
replay is performed for a new result. The retry schedule for unfinished attempts
is 180/600/1800/3600 wall seconds. A watchdog,
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

The owner explicitly approved the ongoing four-worker campaign and research-only
monitor with “Yes start” on 2026-11-07. That approval is recorded in
`launch-approval.json`; it remains valid for safe resumes of this frozen scope.
Do not ask for the same duration approval again. Website deployment and physics
changes remain outside this approval.

Before any launch/resume, inspect the base manifest, current v3 amendment and retained v2 amendment,
queue controls, state, journals,
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
contexts complete under their recorded sampling protocol to a new immutable path:

```sh
node aoe2x/js_simulation/node/civ-matchups/export-forecast-reviews.mjs \
  --reviewed-only \
  --output aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07/correction-snapshots/NNN
```

The exporter independently reconciles journals, required seeds, context hashes,
physical orientation and review hashes. Historical replay evidence is verified
without executing a simulation; new v3 rows must explicitly record no replay. It preserves
original evidence and excludes held, partial and diagnostic records. New exports
use `civ-matchup-forecast-corrections-v3`, preserving earlier rows verbatim while
recording the current amendment hash, separate evidence-level counts, actual
historical replay checks and contexts with no replay. Existing snapshots retain
their original schema and bytes. The reviewed-only exporter pins a single committed
source revision for its journals and reviews. In either schema, do not disguise it as the older
mismatch campaign or import it with a tool that has not reviewed this schema.

Do not apply snapshots to the serving DB, rebuild/export the website, run
release CI/previews, push staging/main, or deploy automatically. The research
branch disables Vercel Git deployments for itself. Production remains at the
already approved consolidated release until the owner explicitly authorizes
another release after reviewing new results.

Keep the old mismatch monitor paused unless its owner explicitly retargets it
to this new frozen inventory after duration approval. Any ongoing monitor must
follow these commands and gates and never resume a historical campaign. The
owner additionally authorized a concise status report after each new 1,000
reviewed contexts, detected by the existing hourly check. Use the durable cursor
in `monitor-reporting.json`, starting with the 1,000 milestone, and preserve
issued report records under immutable `monitor-reports/milestone-NNNNNN.json`
paths. Combine multiple boundaries crossed between checks into one report using
current actual counts. Update the cursor only for a report being issued, push
reporting metadata on the research branch, and suppress duplicate milestones.
No new milestone means no routine progress report. Keep the previous status
format: reviewed/total and percent, single/multi counts, changed/retained,
remaining with held/exhausted counts, workers/replays and push/production status.
This changes reporting only; the live four-worker 1/3/10 no-replay queue continues. At the review point, provide actual counts,
changed/retained winners, close cases, confidence-category results, failures and
limitations with source links. A stopped queue is not full validation.
