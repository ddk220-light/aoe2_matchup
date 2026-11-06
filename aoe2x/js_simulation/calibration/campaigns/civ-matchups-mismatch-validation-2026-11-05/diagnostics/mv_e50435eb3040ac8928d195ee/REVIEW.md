# Unresolved blocked-pursuit seed: Lithuanian Skirmisher / Gurjara Heavy Camel

This is diagnostic evidence, not a result or correction. No simulations, retries,
probes, journal edits or physics changes were performed for this review. The
existing runner already marks this context blocked and continues other jobs.

- Frozen context: `mv_e50435eb3040ac8928d195ee`, seed 1, 27 Lithuanian Imperial Elite Skirmishers / 20 Gurjara Heavy Camels.
- Context SHA-256: `e50435eb3040ac8928d195ee30dece2d9536b449e84a3e54eadd7e3a461a8cfa`.
- Campaign hash: `89c515d0a0341957f5cb86f4ab0f87537f824646fb808ebe0e1b666ccaf0cc7a`.
- Immutable source commit: `7471207816a612a47bd9759125c5c707e88a4a12`; original evidence ID 44562.
- All four 180/600/1800/3600-wall-second limits exhausted. Final failure: 2026-11-06 17:56:47.466 UTC, tick 2716419 / 45273.65 game seconds.

The first short attempt still showed earlier combat progress; one snapshot alone
does not prove a plateau. The three later attempts repeat a prolonged stall with
one skirmisher at 5 HP versus three camels totaling 384 HP. In the final attempt,
108 snapshots from game second 1892.3 through 44893.9 preserve the same HP,
positions and target fields without further attack, damage or death events.
Blocked events nevertheless increase by 10,320,384, route plans by 946,035,
route invalidations by 430,016 and persisted contact releases by 5,160,192.

The skirmisher stays near the northeastern forest boundary at
(15.010102051443365,2). All three camels retain pursuit of it; one remains engaged.
None of these surviving positions equals its original scenario patrol destination.
This supports a blocked-pursuit nontermination diagnosis rather than the fully
idle patrol-endpoint pattern. The exact collision or targeting cause remains
unverified. It does not establish a real-game draw, winner or validated repair.

Only seed 0 is saved. Required seeds 1 and 2 and the independent exact pair replay
remain missing. Do not copy that seed's winner, blindly retry, modify frozen
physics or use this partial context as a correction. Preserve the original table
evidence and continue the other permitted validation jobs.

REVIEW.json binds all four attempt journal lines (including newline hashes),
closed timelines, seed source line and original physical context to the source
commit. Every referenced byte was checked against Git.
Final failure line 39 SHA-256: `ca701afc006f7f15fcca4e99f6fd522ff7989f32f872f56d2b87c0ca52503bd9`.
Final timeline SHA-256: `cd75353cfef315f9497c4d62733c2a283ae3bc47e2631919a8acb906a9febd9a`.
