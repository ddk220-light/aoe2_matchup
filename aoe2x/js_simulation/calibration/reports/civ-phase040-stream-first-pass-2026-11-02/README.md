# Remaining phase-040 hashing recoveries

The completed phase-040 review identifies Varangian Hussar versus Byzantine and Saxon Imperial Elite Skirmishers (`cm_d56dbdaa4cb6495aa0fd3ec9` and `cm_0dd25801bfaf155ceaf64f7c`) as blocked after their seed 1 attempts exhausted all four V3 retry limits. Both final attempts failed canonical event hashing with `RangeError: Invalid string length` after combat; neither is an outcome. The Aztec Skirmisher/Lithuanian Hussar pair is already covered by its separate completed early recovery and is excluded here.

This separately frozen two-pair inventory recomputes every required native seed using the unchanged, already-tested event-memory runtime. All 62 runtime hashes must match the completed phase-039 recovery. Two workers run the two jobs in parallel, followed by an independent exact replay review per completed pair. No V3 outcomes are copied or reclassified, and no inference or scoring change is introduced. Complete native results may support only flagged provisional cross-engine projections.

Inspect state, journals, lock and live PID before running `node --max-old-space-size=3072 aoe2x/js_simulation/node/civ-matchups/recover-phase040-stream-first-pass.mjs`. The script requires the immutable completed phase-040 review to identify these two blocked pairs. Diagnose failures before retrying. All earlier completed/paused/blocked runners remain stopped.

## Completed targeted inventory

Both pairs completed all three fresh seeds as Varangian Hussar wins at ticks 2052, 124076 and 1988. The Saxon pair exactly replayed seed 0; the Byzantine pair exactly replayed seed 2. All six native records and both reviews are pushed in final campaign checkpoint `df71b217`.

The manifest, immutable source review and all 62 runtime hashes were verified. Do not restart the completed runner. These observations remain in the event-memory ledger with their original campaign hashes; their V3 table projections remain explicitly unvalidated. Original V3 hashing failures remain failures, and independent game-fidelity validation stays open. This completes only this recovery inventory, not the first pass.
