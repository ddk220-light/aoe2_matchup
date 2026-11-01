# Phase-019 patrol-endpoint timeout

Matchup `cm_d9a8fa39591693259171e783` is Ethiopians/Mayans
Two-Handed Swordsman (27) versus Muisca Elite Guecha Warrior (22). Seed 0
exhausted the frozen V3 wall watchdogs of 180, 600, 1,800, and 3,600 seconds.
The last attempt reached 4,668,414 ticks (77,806.9 simulated seconds) with
no terminal result. Seeds 1 and 2 are valid swordsman wins, but do not settle
seed 0. Phase 019 recorded one missing seed and marked the pair blocked.

The bounded, **diagnostic-only** first-100-second replays are
`guecha-swordsman-seed0-v3-first100s.json` under frozen V3 and
`guecha-swordsman-seed0-first100s.json` under V2-stream. They use the same
seed, counts, and scenario, but deliberately stop at tick 6,000. Their final
state hashes, event-log hashes, HP/position timelines, and event counts match
exactly across the two physics versions. Their `timeout` label is only the
diagnostic stop, not a campaign outcome. At that point 10 swordsmen remain with 363 total HP and one
Guecha remains with 14.14 HP. Every swordsman is idle at `(2, 13)`; the
Guecha is idle at `(13, 2)`. None has a pursuit or engaged target. The two
coordinates are precisely the opposite patrol destinations in the frozen
scenario. These units have reached the end of their patrol paths on opposite
sides of the map, out of sight of each other.

The same `world.js` SHA-256
`ee4f333822df501cb47135fb3f5a198d9ff8c2b16e6a376b26efa9d5488d1915`
is present in frozen V3, collision-repaired V2, and V2-stream. Its
`scenario-patrol` order is suspended during pursuit and resumed toward the
authored point afterward. At the point, the movement delta is zero; there is
no endpoint reversal or other command to re-engage a distant enemy. This is a
distinct **patrol endpoint / no-contact stalemate**, unlike the phase-015
forest-pocket melee reach problem. Increasing the wall watchdog will continue
simulating the separated armies without creating a valid winner.

Do not infer a win from seeds 1 and 2, insert the diagnostic as a source run,
or mark the missing seed close/uncertain. A true looping patrol or another
generic re-engagement behavior needs independent fidelity review and a
separately versioned physics dataset. Compare the repaired seed and unaffected
exact replays, then replay all eligible source seeds before combining results.
The existing V3 and V2 journals remain intact.
