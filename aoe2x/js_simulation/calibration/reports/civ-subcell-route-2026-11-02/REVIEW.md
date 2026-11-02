# Terminal chase-goal recovery candidate

The original event-memory Kona seed 0 exhausted 7,200 wall seconds at 4,066.75 simulated seconds. Its retained snapshots show one 23-HP skirmisher and 18 Kona with 2,460 HP for almost the entire run. This failure and its snapshots remain in the original frozen campaign, not as an outcome.

The causal routing defect is terminal waypoint smoothing: a route into the physical attack-stop envelope was discarded as soon as the mover was within 0.1875 tiles of its last waypoint. That can leave the mover outside attack distance and return it to the blocked direct approach indefinitely. The candidate retains the terminal goal until the mover actually reaches the route's existing physical stop envelope. Ordinary detour smoothing stays unchanged. It does not enlarge a unit, change any collision tolerance, extend an attack, remove obstacles, override a winner, or add a combat timeout/draw.

Prototype v1 checked continuous start positions against rounded grid cells; 24 routing tests passed, but the Kona probe still timed out. Prototype v2 also refined the raster near blocked static contacts and kept terminal goals; Kona completed, but the refinement was unnecessary. Prototype v3 removes both prototype changes and retains only the terminal-goal condition. It also completes Kona seed 0 at tick 1785. Only v3 is the candidate runtime. The earlier source snapshots and failed diagnostics stay archived under v1/v2 and never provide campaign measurements. No no-route cache or BFS experiment was adopted.

The minimal candidate passes 25 routing tests, covering the melee and projectile stop metrics and unchanged ordinary waypoint smoothing. Its nine world-tick failures exactly match the frozen baseline; there are no new failures in that suite. Complete Kona and Elephant controls preserve winners but change ticks/hashes; this is intentionally different physics and must stay separate from old V2/V3 records. The initial bounded Kona result and all controls are diagnostics only.

The separately frozen `civ-matchups-terminal-goal-first-pass-2026-11-02` campaign recomputes all required Kona seeds, followed by an exact replay of seed 0. Only a complete reviewed set can support an explicitly unvalidated first-pass cross-engine projection. Independent game-fidelity validation remains open.

## Completed targeted recovery

All three fresh Kona seeds completed as Mapuche wins at ticks 1785, 2159 and 1742. Seed 0 passed its independent exact replay; its final-state and event-log hashes also match the earlier bounded v3 diagnostic. The diagnostic is not a campaign record. All 62 frozen runtime hashes pass verification. Campaign hash: `ad724f10cc4d74e11d53e43ebd4e6860a29c247fa6c4b21161f080afff63c2aa`.

This completes only the targeted candidate inventory. Its single table projection must remain `predicted_unvalidated`, with native observations in the separate terminal-goal ledger. Independent game-fidelity validation remains open; no broad replay or forecast validation is authorized by this result. Do not restart the completed runner.
