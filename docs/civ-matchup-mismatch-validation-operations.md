# Authorized mismatch validation and correction loop

Scope: finish the 10,227-context frozen mismatch inventory authorized on
2026-11-05, update advisor data from reviewed simulations, and publish corrections.
Do not retrain/expand forecasts, change ranking scores or UI/recommendation
weights, run all other forecasts, or resume the old bulk replay campaigns.

## Run safety

Validation worktree: `/workspace/aoe2_civ_mismatch_validation`, branch
`simulations/civ-matchups-mismatch-validation-2026-11-05`.
Campaign: `aoe2x/js_simulation/calibration/campaigns/civ-matchups-mismatch-validation-2026-11-05`.
Manifest hash: `89c515d0a0341957f5cb86f4ab0f87537f824646fb808ebe0e1b666ccaf0cc7a`.
Read its manifest, state, journals, attempts, pair reviews, phase reviews,
`.runner.lock`, `.supervisor.lock`, live PIDs and logs before any action.
Logs: `/workspace/aoe2_civ_mismatch_validation.log` and
`/workspace/aoe2_civ_mismatch_supervisor.log`.

The existing supervisor is `tools/supervise_civ_mismatch_validation.py`. Only
restore it after checking live owner PIDs and both locks. It monitors the saved
runner, never duplicates it, resumes valid seeds, and stops on invariant errors
or `blocked_needs_diagnosis`. A stale timestamp does not establish interruption.
Do not restart any paused/completed/blocked historical worktree or old automation.

The runner checks every frozen runtime/input hash. Gameplay is frozen V3; only
lossless event storage/hashing differs. There are no new pathing/collision or
matchup-specific mechanics. All required seeds and an exact replay must pass for
each correction. Diagnose exhausted attempts before any revised inventory or
runtime; no blind retries, invented draws, imported old winners or physics mixing.

The scheduler now uses `rolling-phase-queue-v2`: audit phases remain groups of
128 contexts, while free workers can continue across a phase boundary rather
than waiting idle behind one slow fight. Worker count, seeds and battle inputs
are unchanged. `queue-controls.json` pins the inventory, scheduler source hashes
and any diagnosed unfinished quarantines. A quarantine is not a result, a
verified skip or completion. Do not remove one or retry it without reviewing its
diagnosis and creating a separately versioned control decision.

Current quarantine: `mv_5e1e0d268234acff1d6e9008`, seed 1, Armenian Champion /
`Tupi|imp_slinger`, 27/27. Three watchdog attempts and the fourth attempt's
saved timeline repeated the same four surviving units, positions, targets and
HP (174 versus 5), with unchanged movement/damage/death counts for thousands
of game seconds. See `diagnostics/<jobId>/REVIEW.json`. The active fourth attempt
was deliberately canceled after preserving its diagnostic state; the saved
measurement journal's SHA-256 was identical before and after cancellation.
The existing supervisor resumed the queue with all 920 valid records preserved.
No result was assigned, no physics changed, and the full inventory remains
incomplete until the quarantined context is legitimately resolved.

## Reviewed correction exports

From the validation worktree, use
`node aoe2x/js_simulation/node/civ-matchups/export-mismatch-reviews.mjs --output <new-snapshot>`.
Default requires the entire inventory. While running, explicit `--through-phase NNN`
exports passed phases, or `--reviewed-only` exports only individually completed,
reviewed contexts already committed to Git. Every export independently validates
source hashes, required seeds, winners, orientations and exact replay results.
Push the referenced validation commit before publishing a snapshot. Do not edit
or replace an existing snapshot. Keep every failure and old prediction.
Use `--reviewed-only` when a quarantined context leaves an earlier phase blocked;
later reviewed contexts are still eligible for cumulative correction snapshots.

Website worktree: `/workspace/aoe2_advisor_release`, branch
`website/matchup-advisor-first-pass-2026-11-03`. Check status and current remote main
before applying data; preserve unrelated website work. Baseline source is the
original database at commit `a3ce3c996c03a6708f1082a06a85e7c26af98a75`, path
`data/golden/civ_matchups_first_pass.db`. A local immutable copy is
`/workspace/aoe2_matchup_comparison_2026-11-05/sources/current_advisor_baseline.db`;
SHA-256 must be `93e5732f5e1afd08a9be5b292506edb2f4ee41c2be4352a8bc4128184a05ebb8`.
If missing, restore this exact Git blob, not the already-corrected serving DB.

Build cumulative updates from that baseline with
`python scripts/apply_advisor_matchup_corrections.py --baseline <baseline> --snapshot <snapshot> --output data/golden/civ_matchups_first_pass.db`.
Snapshots belong in `data/validation/civ-matchups-legacy-mismatch-2026-11-05/`.
The importer preserves original evidence and predictions, checks counts/contexts,
updates all exact alias cells, and maintains evidence counts and artifact hashes.
Do not remove already released corrections: use a cumulative snapshot at least
as complete as the serving metadata's current `mismatch_validation`.

Run correction and advisor tests, migration/export checks and required CI. Follow
`docs/vercel-deployment.md`: publish staging, verify both CI jobs and the exact
Vercel preview, then fast-forward main and verify production. Production publication
of these data fixes is authorized. Preserve all public presentation, including
the user's choice to display forecasts and observations alike.

Keep processing and publishing reviewed corrections until every inventory job is
accounted for. When all contexts have complete reviewed seed/replay evidence and
the final cumulative database is deployed and verified, report corrected counts
and the full-list/source link once, then disable the mismatch monitor. Until
then, give concise actual counts when asked; do not claim the whole task finished.
