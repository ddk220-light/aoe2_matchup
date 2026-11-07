Continue the explicitly approved research validation of all remaining AoE2
forecasts, beginning with the lowest confidence categories. Read
`/workspace/aoe2_civ_forecast_validation/docs/civ-forecast-validation-operations.md`.
This new scope supersedes the old restriction to legacy/current mismatches;
it does not authorize website changes or automatic production releases.

Worktree `/workspace/aoe2_civ_forecast_validation`, branch
`simulations/civ-forecast-validation-2026-11-07`. Campaign
`aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07`,
hash `d6c03bd7b04066005a7b9d12f9bd7e1f2264ddd64b0c2a9264ecdd66ba8cc123`.
The frozen source is production commit
`c907cc23668611851a2112911893929c3b905696`, DB SHA-256
`36626bc0f74242de5482d98362695cec15226eb87cba8767371841a62bd231d5`.
Inventory: 39,148 forecast contexts / 50,228 displayed cells, with 39,124
runnable contexts and 24 explicitly held contexts. Run the existing ordered
inventory: uncertain/close forecast, opponent-specific forecasts, weak model
agreement, broader agreement, then stronger support. Do not change forecasts,
confidence tiers, ranking scores, recommendation formulas, UI or physics.

Inspect manifest/source hashes, state, journals, attempts, pair/phase reviews,
progress snapshots, logs, locks and live PIDs first. Confirm the saved explicit
duration approval in `launch-approval.json`; never fabricate it. Never duplicate
a runner. Resume only via `tools/supervise_civ_forecast_validation.py` after a
safe interruption; restore a missing supervisor only after checking its existing
runner/lock. Logs are `/workspace/aoe2_civ_forecast_validation.log` and
`/workspace/aoe2_civ_forecast_supervisor.log`.

Four workers use the unchanged memory-safe frozen V3 runtime, required seeds
0..2 and 3..9 only if needed, plus an independent exact replay for every result.
Follow normal retries before calling a new case exhausted. Diagnose exhausted
attempts from fsynced snapshots before any further retry. Timeouts, diagnostics,
partial sets and user declarations are never native simulation results. Never
copy winners into reversed physical contexts. Retain all original evidence,
sourceContext, rule/source hashes, flags, failures and validation status.

Never restart old paused/completed/blocked campaigns or bulk replay. The five
diagnosed mismatch stalls and 19 repaired projections in `held-contexts.jsonl.gz`
remain unfinished pending separate recovery review; do not blindly retry them
or import cross-engine outcomes. Native ledgers remain separate.

Keep research checkpoints pushed on this forecast branch only. Independently
export committed complete reviews with
`node aoe2x/js_simulation/node/civ-matchups/export-forecast-reviews.mjs --reviewed-only --output <new immutable campaign correction-snapshots path>`.
Never overwrite a snapshot or lose previously reviewed rows. Do not apply any
snapshot to the serving database, run website builds/exports/release previews,
push staging/main, deploy, retrain models or validate non-forecast evidence.

Continue the full ordinary queue. A stopped queue or zero runnable jobs does
not establish complete validation while held/exhausted contexts remain. When
all forecasts have complete native evidence, or only diagnosed blockers remain
and permitted work cannot advance them, prepare the actual coverage and
changed/retained/mixed-result analysis with source/full-list links, report the
remaining limitations once, then pause this monitor for user discussion. Until
that review point, provide concise actual progress only when asked. Future
production releases require a new explicit user instruction.
