# Recovery of 36 unfinished forecast contexts

The owner authorized fixing the 36 after the reviewed-data production release.
That release is verified at `634554b39a46ad9d05081d5efcf1691a8fbd3c39`.
Recovery is local research on `simulations/civ-forecast-recovery-2026-11-10`.
The research pre-push guard and disabled recurring tasks remain in place.
No further build, deployment or serving database import is authorized.

The frozen campaign, its complete results and all held/exhausted statuses are
unchanged. Read the original campaign's `recovery-review/2026-11-10/review.json`
for the full list: 19 different-engine projections, eight fixed-position pursuit
stalls, six moving without combat, two idle patrol endpoints and one collision
exception. Results from different physics versions must remain distinguishable.

## First repair: inherited ranged crowd overlap

`collision-core-v1` contains the source-bound preparation for
`fv_d94fee4147c5053486b13687`: Chinese Heavy Scorpion (23) versus Poles Heavy
Mounted Crossbowman (27), one displayed cell. All four original seed-0 attempts
failed with a geometry exception; neither native ledger contains a completed
seed for this physical context. The original snapshots and diagnosis are linked
and hashed in the new manifest; they remain diagnostics, never outcomes.

The reservation minimum could exceed the units' existing legal separation. The
generic repair caps that minimum at the current separation, preserving the
nonzero core for fresh movement and preventing inherited overlap from deepening.
Collision assertions, attack reach, siege-body handling, time step, scenario,
profiles, counts and physical orientation remain unchanged. Two synthetic
regressions reproduced the exception before the repair; all 47 focused collision,
crowding and interaction tests passed afterward. No completed campaign seed was
used as a regression replay.

The candidate physics version is `forecast-recovery-inherited-ranged-core-v1`.
The one-off runner has an exclusive lock, verifies local committed runtime
objects and frozen source hashes, and refuses completed original or recovery
seeds, unclosed attempts and previously exhausted recovery attempts. It uses
the unchanged four-worker memory-safe pool and normal watchdog retry steps.
Only the selected context runs; the frozen ordinary queue stays stopped.

The existing V3 policy determines exactly 1, 3 or 10 distinct seeds. New replay
evidence is `required=false, performed=false, exact=null`. Any completed result
is candidate-engine evidence; it does not replace the original ledger or become
production-eligible automatically. Remaining contexts require separate diagnosed
mechanics work or fidelity review of existing different-engine evidence.

```sh
node aoe2x/js_simulation/node/civ-matchups/run-targeted-recovery.mjs \
  aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-recovery-2026-11-10/collision-core-v1/manifest.json \
  --verify-only
```

Omitting `--verify-only` executes only missing seeds authorized by that manifest.
Inspect the lock and live process first; never start a second runner. Original
ledger paths currently refer to the frozen local worktree and must remain
available for the no-rerun checks. Source hashes are recorded for portability.

## First recovery result — November 10, 2026, 6:15 a.m. PST

The sole seed-0 execution completed normally with no failed recovery attempts:
Chinese Heavy Scorpion won, with 13 survivors and 620 of 1,380 starting HP
(44.93%); all 27 opponents were eliminated. The battle ended at tick 3,067
(51.12 simulated seconds). This agrees with the original forecast and satisfies
the recorded single-seed rule. Seeds 1..9 are not required and seed 0 must never
be rerun, including under another engine version.

`collision-core-v1/verification.json` independently checks the saved record,
attempt journal, review hashes, local source commit and unchanged frozen files.
The runtime source commit is `1ba6aeb88c01b9c79e02d0068410ff776193bcf5`.
The runner exited and removed its lock. This new result is committed locally,
not pushed, and is not included in production.

Recovery has produced a complete candidate result for one of the 36 contexts.
The other 35 have no new recovery result. The frozen campaign still records
39,112 complete contexts and 36 unfinished contexts: this separate repair is
not a retroactive change to that campaign's physics or coverage. Broader
mechanics/fidelity review and an explicit future release are still required
before considering candidate evidence for the website.
