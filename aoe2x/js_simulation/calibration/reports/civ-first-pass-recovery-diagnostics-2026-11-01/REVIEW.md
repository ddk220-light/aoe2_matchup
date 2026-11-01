# Recovery retry diagnostics

These reports are diagnostic artifacts, not campaign measurements. Neither a
watchdog nor the diagnostic tick ceiling supplies a winner or a draw.

## Guecha versus Champion: patrol endpoints, not slow attrition

`cm_6827d25d70a06f758cc82ff9:2` uses 22 Muisca Elite Guecha Warriors
against 27 Khitan Champions. Its certified V2-stream attempts exhausted
3,600 and 7,200 wall seconds. The final attempt reached tick 5,409,481,
or 90,158.02 simulated seconds, without a valid outcome.

The bounded report `cm_6827d25d70a06f758cc82ff9-seed2-first600s.json`
completed in 69.03 wall seconds. At game second 100, one Guecha remains
with 31.72 HP at `(2, 13)` and 15 Champions with 702 total HP at `(13, 2)`.
All are idle, with no pursuit or engagement target. Every sampled position,
HP value and cumulative event count is identical from second 100 through
second 600. The armies have reached opposite authored patrol endpoints,
outside each other's vision. Increasing the wall limit cannot fix the
missing patrol return leg.

The existing isolated prototype in `/workspace/aoe2_civ_patrol_repair`,
branch `simulations/civ-matchups-patrol-repair-2026-11-01`, commit
`c066b8dd`, already addresses this generic endpoint behavior. It was built
for the separate Ethiopian Two-Handed Swordsman/Guecha pair
`cm_d9a8fa39591693259171e783`. Its source, 49 focused tests and original
diagnostics are preserved there; no additional physics edit was made here.

A new isolated probe under that prototype, saved there as
`calibration/reports/civ-matchups-patrol-repair-2026-11-01/guecha-champion-seed2-repaired.json`,
completes this Khitan Champion seed at tick 3,633 (60.55 game seconds),
with 15 Champions and 696 HP. This is also **diagnostic only**. The prototype
changes physics and has not been certified against independent late-patrol
game captures. Its result must not be inserted into V2 or V3 journals.

For the currently authorized provisional first pass, any future use of this
repair must have a new frozen campaign, newly computed complete seed sets for
each affected pair, exact replay reviews, a separate evidence ledger, and an
explicit unvalidated cross-engine projection. It cannot claim compatibility
with collision-repair V2. No bulk replay or forecast-model expansion is
authorized. The old prototype review's proposal to replay the entire corpus
belongs to the earlier fully validated scope, not the present first pass.

## Skirmisher versus Kona

`cm_b49b88761f519d9bd7d20a07:0` exhausted its final 7,200-second retry
at tick 133,916 (2,231.93 game seconds). Its subsequent bounded diagnostic
also hit its 300-wall-second ceiling before the first 100-game-second
timeline sample. The report preserves the watchdog and last progress, but
contains no useful HP/position timeline. This does not establish the patrol
cause, a winner, or a draw. Further diagnosis needs more frequent or streamed
read-only snapshots, or a shorter game-duration probe; repeating long wall
retries without that evidence is not justified.

The watcher has its own PID lock and writes only this report directory. It
never restarts a campaign, writes a run journal or duplicates an active seed.

## Targeted patrol recovery follow-through

The separate `civ-matchups-patrol-first-pass-2026-11-01` campaign on the
patrol-repair branch now contains six fresh valid seed records (three per
pair), with one additional exact replay per pair. Its hash is
`2a259f17dc155cb0a9c39967cb8e44087ab810b2f8f8c4dbea1449fa55511bf6`.
Both reviews passed, with the melee side winning all seeds. Original V2/V3
records and these diagnostic files were not imported as measurements.
The delivery builder can use the reviewed records only as unvalidated
cross-engine projections, with a separate patrol-candidate evidence ledger
and explicit game-fidelity limitations. This settles two provisional table
gaps; it does not certify the prototype as a faithful replacement engine.
