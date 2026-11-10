# Recovery results — November 10, 2026

All **36 contexts / 220 displayed cells** now have complete recovery evidence.
The final battle finished at **7:16:58 a.m. PST**. The original forecast campaign
and the production release are unchanged; this is a separately versioned
research dataset committed locally on `simulations/civ-forecast-recovery-2026-11-10`.

| Evidence | Contexts |
|---|---:|
| Single-seed confirmations | 11 |
| Multi-seed validations | 25 |
| Retained forecasts | 34 |
| Changed outcomes | 2 |
| Mixed-winner sets, included among changed outcomes | 1 |
| Remaining recovery contexts | 0 |

The 19 older-engine contexts were rerun exactly as newly authorized: three
distinct seeds per context, 57 new measurements. Every seed retained its
earlier-engine winner; remaining HP can differ. These are new measurements under
the recovery engine, not exact-repeatability tests or copied older outcomes.

The other 17 contexts consist of the 16 pursuit/patrol failures and the collision
exception. Their completed original seeds were preserved. Across the full
36-context review, there are **80 new recovery measurements plus 13 preserved
original native measurements**, totaling **93 individual seed records**.

## Review the data

- [Full 36-context list (CSV)](correction-snapshots/002/matchups.csv)
- [Every reviewed seed: winner, HP, survivors, timing and hashes (CSV)](correction-snapshots/002/runs.csv)
- [Full per-run records with source references (compressed JSONL)](correction-snapshots/002/runs.jsonl.gz)
- [Complete reviews and earlier-engine comparisons (JSON)](correction-snapshots/002/matchup-reviews.json)
- [Export verification and local source commits](correction-snapshots/002/verification.json)
- [Completion and previous-snapshot preservation receipt](completion.json)

In the per-run CSV, owner **2** is the first named unit in the matchup and owner
**3** is the second. The matchup CSV's `a_win` / `b_win` values use the original
canonical profile-pair order, which can differ from physical owner order.
`close_uncertain` preserves mixed winners instead of selecting a majority winner.
The compressed run file retains each source record, including per-run engine
provenance and all saved terminal measurements. It is not a frame-by-frame event
recording. Original evidence, flags, forecasts and historical replays remain in
their original ledgers and in the source-bound review inputs.

Snapshot 002 preserves all 35 contexts and 90 individual records from immutable
snapshot 001, then adds the final context's complete three-seed set. All export
inputs were checked against local committed Git objects. No simulation was
executed to audit or export a completed result.

## Changed outcomes

| Matchup | Recovery evidence |
|---|---|
| Bohemians Elite Hussite Wagon / Khitans Mounted Trebuchet | Mounted Trebuchet wins all three seeds; original forecast changed. |
| Chinese Elite Chu Ko Nu / Khitans Mounted Trebuchet | Mixed winners across ten seeds: eight Mounted Trebuchet wins and two Chu Ko Nu wins. Retained as `close_uncertain`, not a forced winner. |

These are observed results for this targeted recovery set. Agreement-dependent
stopping and the selection of previously blocked contexts cannot estimate
unbiased global forecast accuracy or a calibrated win probability.

## Engine repairs and verification

The repairs are generic mechanics changes, with no matchup-specific winners,
HP adjustments, seed substitution, timing changes or copied reversed outcomes:

1. Cap an inherited ranged-crowd collision core at its existing separation so
   recovery cannot require additional overlap. The original exception's seed 0
   completed once and was not rerun.
2. Keep a terminal path waypoint until the actor actually reaches its attack
   envelope; use the actor's position instead of assuming its grid-cell centre
   has already been reached. Refine failed routes without changing body sizes.
3. Release dead opening targets so a delayed unit can acquire a living enemy.
4. Reverse an unengaged scenario patrol at its endpoint while preserving combat
   suspension. The [original game manual](https://manuals.plus/m/bede02f48ca7b2aae252168379555520636b871dcd6c6fdba8ba2766ea0186e2.pdf)
   describes patrol as travel between the starting point and patrol point.
5. For the final narrow forest approach, refine a bounded local corridor to
   1/64-tile search cells, aligned with the global grid. Collision surfaces,
   attack range, profiles, contexts, simulation time step and seeds stay fixed.

The latest repair passed **88 focused synthetic regression tests**, including
unreachable passages and swept obstacle clearance. The final Lithuanian Elite
Skirmisher / Gurjara Heavy Camel context preserved original seed 0 and completed
missing seeds 1 and 2 in 12.10 and 14.61 wall seconds. Heavy Camel won both,
retaining 2,193 and 2,179 total HP respectively; the opponent was eliminated.

Two earlier recovery watchdog timeouts on that context remain diagnostic evidence;
the queue stopped at a closed attempt boundary before the final repair. They were
never converted into outcomes or labeled exhausted. An earlier report-serialization
error and its administrative interruptions are also preserved, along with all five
measurements saved before that interruption. No completed recovery seed was rerun.

| Per-run engine version | Records |
|---|---:|
| `frozen-civ-matchups-v3`, preserved original measurements | 13 |
| `forecast-recovery-inherited-ranged-core-v1` | 1 |
| `forecast-recovery-path-patrol-v2` | 77 |
| `forecast-recovery-local-refinement-v3` | 2 |

Six multi-seed sets combine preserved original measurements with new recovery
measurements; their reviews list every version. They are not homogeneous
frozen-engine validations. The tests establish the repaired engine behavior;
they do not constitute a new comprehensive live-game fidelity validation.

Audit receipts: [collision](collision-core-v1/verification.json),
[path/patrol](audits/final-path-patrol-v2.json), and
[final local refinement](audits/final-refinement-v3.json). Each links actual
records, source hashes and local runtime commits. New exact-replay evidence is
`required=false`, `performed=false`, `exact=null`; historical replay evidence is
unchanged.

## Publication and production

All recovery runners exited and removed their locks. Recurring tasks remain
disabled. The research pre-push guard remains installed. This recovery work,
its checkpoints and reviewed-only snapshots are **committed locally, not pushed**.
No new build, deployment or serving-database import occurred.

The approved production release remains `634554b39a46ad9d05081d5efcf1691a8fbd3c39`,
with serving database SHA-256
`eca8b868fa99cacb4789ec9ce6fec7ecb8058f58b587c8ee51fd1969fa10af29`.
The original campaign still records 39,112 complete contexts and 36 historically
unfinished contexts under its frozen protocol. This recovery does not rewrite
that history. Recovery exports are not automatically production-eligible;
publication or another production release requires a new owner instruction.
