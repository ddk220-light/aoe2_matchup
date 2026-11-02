# Phase 038 event-memory recovery

The Gurjara Hussar / Aztec Imperial Elite Skirmisher pair `cm_8b6d8cf86a0ecd56ddc35bc2` exhausted frozen V3 retries for seeds 0 and 2 because final event-log canonicalization exceeded the JavaScript string limit. Seed 1 has a valid V3 result; neither failed seed is an outcome.

This new frozen inventory recomputes every required seed of this one pair under the byte-identical runtime of the separately tested event-memory candidate. No new physics or model changes are introduced. It owns its own manifest, journals, snapshots and exact replay review. Existing V3 results are retained and never copied as candidate evidence. A complete candidate result may contribute only a flagged provisional cross-engine projection.

Run `node --max-old-space-size=3072 aoe2x/js_simulation/node/civ-matchups/recover-phase038-stream-first-pass.mjs` only after inspecting state, journals, lock and PID. The script requires the immutable phase-038 review to identify the pair as blocked and verifies all runtime and source hashes.

## Completed targeted inventory

All three fresh repaired-runtime seeds completed as Hussar wins at ticks 53730, 2130 and 120273 (895.5, 35.5 and 2004.55 simulated seconds). Their own final state and event-log hashes were saved successfully. The independent exact replay of seed 1 passed. The final campaign checkpoint is `964ae737`; no V3 failed seed was converted into a result or copied into this campaign.

The inventory is complete and the runner must not be restarted. Its native records remain event-stream measurements, with their original campaign and input hashes. A first-pass table entry is only a `predicted_unvalidated` cross-engine projection. Independent source-engine game-fidelity validation remains open.
