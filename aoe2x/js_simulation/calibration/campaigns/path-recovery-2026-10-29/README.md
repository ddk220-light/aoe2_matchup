# Remaining simulation faults: investigation and corrections

The original 7,656-run ranking campaign remains immutable. This branch contains behavior corrections and requires a fresh ranking dataset before scoring. The prior exact-preserving optimization is documented separately in `collision-performance-full-2026-10-29`.

## Static-obstacle geometry disagreement

The movement solver treats map obstacles as circles and enforces swept clearance. Both path grids instead rasterized inflated squares; local recovery also checked square endpoint clearance. A physically legal corner position could therefore appear blocked to the planner. Correct the two path grids to use circles for static obstacles, retain boxes for dynamic units, and use swept circular clearance for the local recovery step. No radii, collision tolerances, tick rates, damage rules or attack speeds change.

The previously unresolved Inca Elite Skirmisher–Spanish Champion seed 1 completes from its original starting formation in **6.20 processing seconds**, **34.55 game seconds / 2,073 ticks**. Champions win with 21 survivors and 1,355 HP. The previous engine exceeded its 120-second processing budget. See `inca-champion-circular/result.json`; `source-manifest.json` supplements the initial trace's omitted chase-path fingerprint. Moving the distance-function selection outside the inner grid loops afterward does not change its arithmetic.

An additional exploratory replay from the *old engine's already-jammed* tick-3,600 world did not finish in the next 1,800 ticks. Fresh-start validation is the acceptance criterion; this change does not promise migration or recovery of arbitrary older engine snapshots.

## Allied collision fallback omission

Wider testing exposed an existing inconsistency in `collision.js`: final geometry checks enforce all published pair surfaces, but `invalidBodyReferences` ignored allied pairs. When iterative resolution exhausted its budget, recovery could return without repairing an allied overlap, and final validation then threw.

Remove that allied-pair exclusion. The existing deterministic recovery now restores only invalid contacts and any contacts affected by those restorations. It keeps independent valid movement; it does not relax the published collision surfaces or remove the final safety check.

The captured Aztec Elite Skirmisher–Turkish Cavalier seed 2 failed at tick 1,823 with an allied overlap of 0.0044315 tiles. Applying only this fallback correction to the circular-geometry candidate completes in **8.95 processing seconds**, **33.10 game seconds / 1,986 ticks**, with 17 Cavaliers and 2,076 HP. Raw input, baseline failure and candidate output are in `all-pairs-fallback/`; the fixture in `fixtures/collision/allied-fallback-residual.json` reproduces the failure without replaying the whole battle. Candidate evidence records the original source hashes and exact in-memory patch explicitly.

## Three stale regression expectations

- The old hand-copied collision fixture contained starting overlaps but omitted their contact reservations. Replace it with the existing complete residual capture, and test safe movement preservation plus recovery on the next tick.
- The large mobile-ranged test assumed the requested inward step was accepted unchanged. Crowd steering actually rotates it sideways. Test the intended contract directly: committing a non-siege ranged unit must leave its compliant geometry and steering unchanged relative to the same uncommitted crowd.
- The old HCA–Steppe test asserted a historical simulated score (-41.875) and duration (4,072 ticks); even the frozen campaign engine already returns a different score (29). Replace this collision-safety test's historical outcome assertion with successful completion and exact deterministic replay. This does **not** establish a new live-game calibration target or claim to resolve a live-game discrepancy.

New regressions distinguish circular static corners from dynamic box corners and reproduce allied fallback while checking all resulting pair surfaces.

## Validation and consistent data refresh

The initial circular-only batch is preserved in `../path-recovery-validation-2026-10-29/`, marked superseded after the fallback failure. The complete combined-engine batch is `../path-recovery-final-validation-2026-10-29/`: all 107 previously flagged runs plus all 37 pilot controls, with every source file fingerprinted and every result journaled. It is still running at this checkpoint.

The campaign runner can now prepare a separately versioned full refresh after validation passes. It copies the approved matrix, unit profiles, counts, equivalence groups and phases, importing **zero** old outcomes. Four workers, automatic phase checks, resumable SQLite/JSONL storage and periodic Git publication remain in place. Headless runs use the existing stop-control worker to remove the practical game-time cap while retaining the 120-second processing watchdog. Both game and processing time are saved, including partial game time from watchdog heartbeats. Browser integration and scoring remain deferred.
