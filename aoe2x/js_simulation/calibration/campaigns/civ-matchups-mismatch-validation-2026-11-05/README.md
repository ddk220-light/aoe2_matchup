# Targeted validation of legacy/current matchup disagreements

Authorized on 2026-11-05: get the full mismatch list, simulate the disagreements,
and correct the advisor data from reviewed simulation output. This is separate
from the completed provisional first pass and every paused engine-replay queue.

The frozen inventory contains 18,298 distinct displayed cells and 10,227 physical
contexts. It includes opposite winners, decisive/close disagreements, legacy
direction-dependent outcomes, the individual cells behind conflicting old
composition claims, and disagreements with concrete raw ranking-yardstick
margins. Aggregate ranking order and recommendation-only formula changes never
constitute winner evidence. Exact unit names/civilizations are required; missing
legacy scales or unmapped upgrades are not invented.

2,379 contexts have complete frozen V3 seed sets: one new exact replay checks
each existing set and all original source rows are integrity checked. The other
7,848 contexts receive fresh seeds 0..2, extending to 3..9 when initial winners
differ, followed by an independent exact replay. Short ranking-ledger source
identifiers are deliberately not treated as frozen V3 measurements.

Four workers run only this inventory. Each phase contains at most 128 contexts.
Seed journals are fsynced immediately; phase and ten-minute partial checkpoints
are pushed to `simulations/civ-matchups-mismatch-validation-2026-11-05`.
The campaign lock prevents duplicate runners. Interrupted runs reuse their own
valid completed seeds. Exhausted attempts require diagnosis, never classification.

Gameplay stays frozen V3. Only canonical event serialization/storage changes:
`canonical-json.js`, `fight.js`, and the `runWorld` event consumer in `world.js`.
No collision, pathing, attack, scenario, count, seed, or ordering changes are
included. Five focused hash/event tests and eight full exact original/saved/stream
controls passed. See `reviews/runtime-parity.json` and `reviews/stream-tests.tap`.
The runtime manifest records all 62 source hashes and the three output-only diffs.

Corrections must preserve original predictions, low-support flags, evidence,
physical contexts and source hashes. Every result is mapped from its physical
team order to the canonical pair order. Viewer orientation does not change a
battle's physical setup. Identical-profile identities remain identities even
when a seeded, physically oriented mirror battle has a winner. Only complete
reviewed seed sets may replace forecasts/inferences with measurements.

Run from this worktree after checking the state, lock and live PID:

```
node --max-old-space-size=3072 aoe2x/js_simulation/node/civ-matchups/run-mismatch-validation.mjs
```

Original journals and the original website database are immutable inputs. A
versioned correction artifact is built from the reviewed records; the complete
comparison list, reasons, failures, replay hashes and original values remain
inspectable. Neither old winners nor diagnostics become measurements. No
ranking scores or recommendation formula changes are part of this campaign.
