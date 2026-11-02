# Incremental event hashing for first-pass recovery

The previous static-memo Kona seed0 failed with ERR_WORKER_OUT_OF_MEMORY after6,971.6 wall seconds at tick196284 (3,271.4 game seconds). Its final hash was streamed, but compact runWorld still retained every historical event object. No valid result was produced. The frozen campaign and its two completed seeds remain unchanged.

This isolated revision hashes each tick's events immediately, preserving exactly the canonical JSON array byte sequence, and discards only historical output objects. Live tick events, combat state, arithmetic, random ordering, collision precision and termination rules are unchanged. Snapshot-retaining and browser calls preserve their previous path. The existing static-geometry memoization is retained. Four runtime files differ from certified V2-stream: collision.js (previous memoization), world.js (optional event consumer), canonical-json.js (incremental array hasher), and fight.js (headless wiring).

## Verification

Six focused tests passed: two canonical hash tests, three incremental/compact-stream tests and the durable progress worker's exact saved-output control. The memory stress hashes one million events inside a32-MiB Node heap. Full/compact runs include initial pre-existing event history, zero tick caps, completed fights, invalid input, empty and sparse arrays, Unicode and batch-boundary parity. The bounded Kona seed0 probe and four complete controls match saved final-state/event-log hashes, ticks and winner exactly; the separate progress-worker control also matches. Exact output parity is evidence for the implementation, not independent game-fidelity validation.

The broader world-tick suite has nine pre-existing failures on the frozen baseline and exactly the same nine on this candidate. Both complete TAP outputs and the comparison are preserved. They concern old attack-timing/avoidance expectations and an error-message regex; none is silently changed or represented as a passing full suite.

## Targeted recovery

A separate frozen campaign `civ-matchups-event-stream-first-pass-2026-11-02` recomputes required seeds for only the failed Kona pair (`cm_b49b88761f519d9bd7d20a07`) and Mapuche Skirmisher/Bengali Elephant pair (`cm_b5c816c87bdc49ea72433cd3`). Two workers run the pairs in parallel with a7200-wall-second cap per seed. It preserves counts, seeds and scenarios; imports no prior outcomes; expands seeds only for initial disagreement; and requires an exact replay review for each completed pair.

The elephant diagnostic shows ongoing damage, not a stalemate: one skirmisher remains at16HP in a forest pocket while elephant HP decreases slowly. Its seed1 previously exhausted7200wall seconds at3,887game seconds. The new recovery's fsynced progress files record HP, positions, event counts and memory every30wall seconds so a later failure can be diagnosed without another blind replay. Progress snapshots are explicitly diagnostic, never measurements.

Run `node --max-old-space-size=3072 aoe2x/js_simulation/node/civ-matchups/recover-event-stream-first-pass.mjs` only after checking its state, lock and PID. Never duplicate original active seeds or restart the blocked static-memo attempt. The independent first-pass exporter must keep this candidate's native measurements in its own ledger and project only a complete reviewed seed set as predicted_unvalidated under frozen V3. No forecast expansion, web change or bulk replay is part of this work.
