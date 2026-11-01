# Provisional first-pass completion

The owner requested first-pass completion with the existing unvalidated
predictions, and parallel simulation of the remaining gaps. Bulk cross-engine
replay is deferred, with its 5,179 completed records preserved. It is not a
prerequisite for this provisional export. This is not the fully validated,
single-physics second-pass dataset.

The main frozen V3 runner continues its four-worker phase queue. A separate
targeted recovery campaign on branch
`simulations/civ-matchups-first-pass-parallel-2026-11-01` recomputes only the
blocked pairs' missing repaired-engine seeds. It uses two workers while the main
runner is active, subtracts the previous recovery worker until its in-flight
seed finishes, and can use four workers after the main runner stops. Exclusive
locks, active-seed reservations, and the paused bulk replay prevent duplicates.
The worker orchestration passed three exact concurrent fight comparisons and
seven scheduling/seed/provenance tests. Frozen combat files are unchanged.

## Evidence boundaries

The main table retains frozen V3 observed/inferred results and the approved
`predicted_unvalidated` forecasts. A repaired-engine pair can contribute only
after a complete repaired seed set and an exact replay review. Its observations
are bundled in a separate `repaired-evidence-ledger.jsonl.gz`, with their
original campaign hashes. The projection into the V3 first-pass table is
`predicted_unvalidated`, tier `repaired_engine_projection`, with explicit
source/target physics versions. It is never a measured V3 result. Failed or
missing seeds cannot produce a projection.

Two Guecha matchups also expose a separate patrol endpoint bug: survivors
reach opposite destinations and idle out of sight indefinitely. The existing
generic patrol-loop prototype is frozen in the targeted campaign
`civ-matchups-patrol-first-pass-2026-11-01` on branch
`simulations/civ-matchups-patrol-repair-2026-11-01`. It recomputes the complete
required seed sets for only those two pairs and independently repeats one
seed per pair. It imports no V2/V3 outcomes or diagnostic results.

This is a distinct physics version, `collision-repair-v2-patrol-candidate-v1`.
Its records are bundled separately in `patrol-candidate-evidence-ledger.jsonl.gz`;
they never enter the V2 ledger. Its table projections remain
`predicted_unvalidated` and retain the explicit limitation that late-patrol
behavior has not been independently validated against game captures. The
exporter checks all 62 source files against the parent certificate and frozen
candidate; only `world.js` is allowed to differ. This targeted recovery does
not retrain forecasts or require bulk engine replay.

The forecast model, frozen prediction file, and rule hashes are unchanged.
Some derived inference suggestions reversed physical orientation between
phases. Dropping an existing forecast merely because that suggestion changed
inflated the queue. The exporter now preserves the approved forecast's original
context, records the different suggestion as `sourceContext`, and only selects
validation probes whose frozen simulation job actually matches the forecast.
It does not transfer the forecast to the reversed fight. Changed army sizes,
costs, or settings still abstain. Original predictions and subsequent validation
status remain attached when an observed result replaces a forecast.

On the phase-029 snapshot, this preserves 1,212 forecast contexts, leaving
1,919 gaps (including 13 recovery cases), rather than 3,131. Coverage is 7,489
observed, 10,901 inferred, 45 equivalent, and 48,562 unvalidated predictions.
The prospective screening has 8 wrong-or-close calls among 78 comparisons;
those failures remain archived. This preview is incomplete.

## Completion procedure

After the latest completed phase has its prediction archive, run
`tools/build_civ_first_pass_delivery.py` with `--campaign`, `--prediction-dir`,
and `--output`; its default `--recovery` points to the parallel recovery
campaign. Use `--require-complete` for final delivery. The builder checks source
hashes, repaired seed completeness and outcomes, exact-replay provenance,
distinct physics ledgers, all 555 variants / 1,540 civ pairs / 151,223 cells /
68,916 profile pairs, and display orientation. Publish the final bundle and all
referenced source checkpoints, report its evidence counts and unvalidated
forecast work, and disable the first-pass automation. Do not start exhaustive
prediction validation or resume bulk engine replay without the next discussion.
The default `--patrol-recovery` reads the separately versioned two-pair
campaign. Unfinished or unreviewed candidate pairs cannot fill a table gap.
