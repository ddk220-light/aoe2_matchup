# Unresolved patrol-endpoint seed: Muisca Guecha / Viking Champion

This is diagnostic evidence, not a result or a correction. No simulations,
retries, probes, journal edits or physics changes were performed for this review.
The existing runner has already marked this context blocked and continues other jobs.

- Frozen context: `mv_c72552550f46f7a6f193d254`, seed 2, 22 Muisca Elite Guecha Warriors / 27 Viking Champions.
- Context SHA-256: `c72552550f46f7a6f193d254742286e61967613d00cee4ea7594462d522a7f3c`.
- Campaign hash: `89c515d0a0341957f5cb86f4ab0f87537f824646fb808ebe0e1b666ccaf0cc7a`.
- Immutable source commit: `9c4a5eba96dace1b7d89347624ec968ee4e37621`.
- Evidence ID: 61949; original physical profile order and scenario are retained in REVIEW.json.
- All four 180/600/1800/3600-wall-second attempts exhausted. Final failure: 2026-11-06 13:05:20.567 UTC, tick 3143892 / 52398.2 game seconds.

All four fsynced timelines repeat a static state after combat. In the final
attempt, 119 snapshots from game second 312.85 through 51999.85 preserve one
Guecha at 31.722222222222896 HP and fifteen Champions totaling 854 HP. Every
survivor is idle without a pursuit, engagement or attack target. The Guecha stays
at (2,13); all Champions stay at (13,2). These are exactly the patrol destinations
in the frozen source scenario. Positions, HP and all recorded event counters
(including movement and blocked counters) remain unchanged throughout that suffix.

This supports a frozen-runtime patrol-endpoint nontermination diagnosis. It does
not establish a real-game draw, winner or independently validated repair. The
precise reacquisition mechanism remains unverified. Do not blindly retry, change
the frozen runtime, import a historical outcome, or use this partial set as a correction.

Seeds 0 and 1 are saved valid native records; seed 2 and the independent exact
pair replay remain missing. The preserved original prediction stays unchanged.
The full inventory is still unfinished. Other permitted validation work continues.

REVIEW.json binds all four exact attempt journal lines (including newline hashes),
closed timeline bytes, source seed lines, original context and scenario patrol
targets to the source commit. Every referenced byte was checked against Git.
Final attempt line 35 SHA-256: `b8d53fd4eae8acaacc81694ffb77d5d4ae2607ab6f5fe045040e22dced570c1e`.
Final timeline SHA-256: `8e4fcdcddd75e91c03ba82528d74e96df66bc18bc6254ba65a025304bee4d66f`.
