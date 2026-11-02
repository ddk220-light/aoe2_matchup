# Streamed Kona recovery diagnosis — 2026-11-02

This is read-only diagnostic evidence, never a completed campaign seed. The frozen repaired V2 runtime remains unchanged. All 62 runtime hashes were verified before execution. The observer's completed seed-1 control exactly matched the saved final-state/event-log hashes, winner and tick; the CPU-profiled seed-0 bounded run exactly matched the independent unprofiled 40-second baseline.

## Why seed 0 is slow

At game second 30, Armenian Imperial Elite Skirmisher 9021 remains alone with 23 HP at (15.006, 4.004), against 18 Mapuche Elite Kona with 2,460 total HP. These HP totals and the 235 damage-event count remain unchanged through second 80. The skirmisher sits in a narrow forest pocket. Three close Kona meet outline engagement reach, but their physical Chebyshev gaps (0.121–0.183 tiles) exceed the 0.1-tile stop gate for a range-zero attack. Trees and allied crowd prevent direct closing. Repeated escape movement and route attempts do not clear the geometry during this observation. The skirmisher's minimum range also prevents shooting its closest target.

This is a crowded-contact geometry stall, not the patrol-endpoint issue. No result can be inferred from the diagnostic cutoff or timeout, and removing the attack-distance gate would require independent physics validation.

## Where processing time goes

The bounded profile took 69.19 wall seconds for 40 game seconds on the shared cloud worker. Collision resolution accounts for 74.36% of sampled time; final static/body geometry validation alone accounts for 45.66%, and static constraints for 15.92%. Persistent chase routing is 2.59%. `profile-summary.json` contains the source-level profile breakdown; raw samples are preserved.

Separate performance experiments are on `simulations/civ-matchups-path-cache-2026-11-02`, never in campaign journals. Exact no-route memoization was slower and rejected. A BFS reachability precheck preserved the tested outputs but improved only 1.25x; it is not adopted. The profile directs the next bounded experiment to reuse identical static geometry checks inside a single movement solve, preserving all tolerances and arithmetic. Any adoption requires separate frozen provenance and exact parity checks.

## Artifacts and limits

`kona-seed0-stream.jsonl` records 10-game-second snapshots through second 80 before its 180-wall-second watchdog. `kona-seed0-profile40.*` records the bounded CPU profile. `kona-seed1-control.*` is the completed exact-output observer control. None belongs in the frozen campaign journal. The full failed seed remains unresolved.

## Elephant recovery, seed 1

The failed Mapuche Imperial Elite Skirmisher versus Bengali Elite Elephant seed received a fresh, read-only, bounded diagnostic through 150 game seconds (`elephant-seed1-stream.*`). By game second 60, skirmisher 9008 is alone at 16 HP near (15.0101, 6), against 15 elephants. The skirmisher stays at 16 HP through second150, while elephant total HP decreases from 4,575.3 to 4,536.9. It can fire out of the forest pocket while elephants repeatedly replan routes; this is an extremely slow ongoing fight, not a demonstrated stalemate. At second150 the closest inspected elephant has physical gap0.369 and outline gap0.119, outside the attack envelope. The observation ends at the diagnostic tick cap, with no combat result. Both prior 3600/7200 wall watchdogs remain failed attempts.

The independent static-memo Kona attempt later failed with ERR_WORKER_OUT_OF_MEMORY at tick196284 (3,271.4 game seconds) after6,971.6 wall seconds. It retained the full event object array despite streaming the final JSON hash. An isolated incremental event-hash implementation is being tested on branch `simulations/civ-matchups-event-stream-2026-11-02`; no old outcomes are imported and no failed seed is relabeled.
