# Phase 039 event-memory recovery

The phase-039 review identifies two blocked pairs: Tatar Hussar versus Byzantine Imperial Elite Skirmisher (`cm_41be6f97a5add18ee12ed2f2`) and Tatar Hussar versus Saxon Imperial Elite Skirmisher (`cm_45aa0c9f4b68131e7156e62a`). Their seed 1 attempts exhausted the normal 180/600/1800/3600-wall-second retries. Both final attempts completed combat but failed canonical event-log hashing with `RangeError: Invalid string length`; neither is a measurement. Valid V3 seeds 0 and 2 remain preserved.

This separately frozen inventory recomputes every required seed of both pairs under the exact, already-tested event-memory runtime used by the completed phase-038 recovery. All 62 runtime hashes must match that candidate; no new physics or forecasts are introduced. The two jobs use two workers in parallel, own all native records and complete an exact replay review per pair. No V3 outcomes are copied. Each complete result can support only a flagged provisional cross-engine projection.

Check state, journals, lock and PID before running `node --max-old-space-size=3072 aoe2x/js_simulation/node/civ-matchups/recover-phase039-stream-first-pass.mjs`. Failed or timed-out attempts require diagnosis before retry. All prior paused, completed and blocked recovery runners remain stopped.
