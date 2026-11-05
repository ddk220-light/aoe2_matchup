# Civ-versus-civ matchup table: optimize around known matchup outcomes

Status: first phase implemented as an inference-only dataset. No new simulations launched.

The current authorized first phase is **inference only**: build the complete
table from existing ranking evidence and mark unresolved questions. See the
[detailed phase-one implementation plan](PHASE_1_IMPLEMENTATION_PLAN.md).
Any new-fight pilot, simulation scheduling, or live UI integration mentioned
below is future work, outside phase one.

## Agreed scope

- All 555 fully upgraded land-unit variants across 56 civilizations, including
  trash units and scorpions; retain the approved display category merges.
- Cheaper side 27 physical units; expensive side
  `round(27 * sqrt(cheaper weighted cost / expensive weighted cost))`.
  Food/wood/gold weights 1/0.9/1.1; zero buffers; scripted kiting disabled.
- Allow close/uncertain results. Missing, timeout and error remain distinct.
- Use the corrected V3 engine for new runs, with frozen source/input hashes.
- Ask before beginning any work estimated to exceed one hour.

## Which existing evidence can be used

The owner's Britons-versus-Aztecs example clarifies the intended optimization:
use the CURRENT unit rankings' individual opponent results as anchors, then
infer related matchup outcomes where the direction of the change is reliable.
Do not use the older Advisor's Python/30v30/3k results.

The earlier blanket prohibition on using any ranking evidence was too broad.
The accepted ranking dataset contains original and corrected engine records.
Check each proposed anchor's engine hashes, mechanics, army counts, map,
formations, orientation and combat policy against the new campaign. Compatible
corrected-engine records can provide direct anchor evidence; old/incompatible
records can suggest useful tests but cannot certify a winner. Revalidate only
needed incompatible anchors, not the whole previous campaign.

The inventory contains 2,373 historically represented profile pairs. This is a
coverage count, not an automatic reduction in required work. An overlapping pair
with different engines/orientations has opposite winner majorities, illustrating
why the eligibility check must precede inference.

## Core optimization: directional outcome transfer

A ranking score is not the ordering. Build an opponent-specific comparison of
army effectiveness, using the actual cost-balanced counts and relevant mechanics.
For a proposed change from a tested baseline to another unit, assess damage
against the particular armor classes, bonuses, firing cycle and accuracy,
range/opening volleys, closing speed, durability, collision and special effects.

For an eligible tested anchor, apply these directional rules:

| Known result | Validated relationship | Decision |
|---|---|---|
| Archer A beats infantry I | Archer B is at least as effective against I | Infer B beats I; skip its simulation |
| Archer A loses to infantry I | Archer B is stronger against I | Unresolved: B may cross the win boundary; test |
| Archer A loses to infantry I | Archer B is no more effective against I | Infer B loses; skip |
| Unit U beats opponent S | Opponent W is no harder for U to beat | Infer U beats W; skip |
| Unit U loses to opponent W | Opponent S is no easier for U to beat | Infer U loses; skip |
| Anchor is close, source-incompatible or relationship is unknown | Any | Do not propagate a definite outcome |

"At least as effective" is a validated comparison against the particular enemy,
not merely a higher overall score or one better stat. Changes involving tradeoffs
need a calibrated family rule. Damage/cost/count discontinuities and exceptional
abilities split families or prevent transfer. Grouping units together in a display
category does not make their combat behavior interchangeable.

### Worked case: Britons versus Aztecs

The actual benchmark is Chinese Arbalester (not Spanish Arbalester).
The accepted opponent-specific records show:

| Aztec unit | Benchmark result | Evidence | Proposed scheduling decision |
|---|---|---|---|
| Pikeman | Loses 3/3 | Corrected engine; Arbalesters retain 82.15% HP on average | Strong candidate to skip Briton Arbalester/Longbow tests after validating the archer transfer rule |
| Elite Eagle Warrior | Wins 3/3 | Corrected engine | Test against stronger Briton archers; the win may flip |
| Champion | Wins 3/3 | Corrected engine | Test against stronger Briton archers; the win may flip |

These are existing observations, not newly simulated Briton outcomes. Briton
Arbalesters have range 11 versus 8 but reload 2.0 seconds versus 1.7 and accuracy
90% versus 100%. Elite Longbowmen have range 12, reload 2.0 and accuracy 80%.
Thus range alone does not prove dominance. The large Pikeman anchor margin can
support a robust-win transfer rule after validation on other cases; it must not
be silently treated as a mathematical guarantee.

Existing HP margins may help identify robust anchors. The new table does not
require optimizing or precisely estimating remaining HP for every inferred cell.

## Optimize inference now and future testing later

1. Build a small set of interpretable transfer rules for common interactions:
   ordinary foot archers versus ordinary infantry, melee cavalry versus skirmishers,
   standard cavalry variants, and other sufficiently uniform families.
2. In phase one, validate each rule on eligible independent existing results only.
   Mark unsupported rules and affected cells for later validation. A bounded sample
   of new fights belongs to a future phase, including unfavorable corners,
   unit-count breakpoints and examples close to the predicted win boundary. Hold out
   entire unit profiles where possible so duplicated civilizations do not inflate
   validation coverage. Report error and coverage separately by family.
3. Once a rule passes its acceptance criteria, apply it to all eligible pairs.
   Individual inferred cells do not each require a simulation; that would defeat
   the optimization. Unknown tradeoffs and special abilities stay in the sim queue.
4. For a future phase, identify candidate simulations by expected reduction of unresolved cells per
   second of processing. Prefer a representative whose win or loss can resolve
   many related pairs, rather than processing civilizations in alphabetical order.
5. Within a validated ordered family, test a middle/boundary case and narrow the
   win/loss boundary. Use binary-search-like scheduling only while the ordering
   holds. A detected reversal breaks that ordering and isolates affected pairs.
6. Feed newly measured results back into the inference pass immediately. One
   measured result can resolve other pending pairs across many civilizations.
   Keep a dependency chain back to measured evidence; never promote an inferred
   result to independent ground truth or use circular support.
7. Continue small stratified audits of inferred outcomes. A failed rule invalidates
   its dependent predictions and queues them for review, preserving measured runs.

This is the primary saving after exact-profile sharing: simulate the unresolved
boundaries and exceptions, not every cell in every civilization matchup.

## Inventory and durable execution

There are 151,223 unordered cross-civilization unit-variant pairs. Exact mechanics
sharing reduces these to 68,916 profile pairs, serving 1,540 civilization matchups.
This includes 45 identical-profile pairs; one seeded victory must not become a
claim of inherent civilization advantage.

The 68,916 count is the inventory before anchor eligibility and validated
inference. It is not a commitment to simulate all of them. Produce a dry-run
ledger distinguishing eligible measured anchors, inferred candidates, close cases,
and genuinely unresolved pairs, with a reason and source for every decision.

Proposed stages (only stage one is the current phase):

1. Freeze inputs; audit all existing records and anchor eligibility; build the full
   inference table, offline rule validation, and deduplicated unresolved questions.
   No simulations, replay executions, or reduced battles are allowed in this phase.
2. After reviewing phase one, consider a bounded pilot to validate transfer rules,
   calibrate close/uncertain handling, examine side-swap sensitivity, and measure
   worker throughput. This pilot has not been authorized by the inference-only
   request. Final rule acceptance criteria must precede publication.
3. Present the measured skip coverage, likely new run count and ETA. Obtain approval
   before any campaign estimated to exceed one hour.
4. Run approved phases using a persistent worker pool, resumable seed queues,
   append-only per-run records and periodic durable checkpoints. Recompute the
   unresolved queue after every phase as new anchors enable additional inference.
5. Serve the completed table from stored outcomes rather than on-demand legacy
   simulations. Both UI perspectives read the same recorded outcome. Preserve
   engine/setup hashes, evidence type, rule version, support and confidence.

Proposed sampling: three initial seeds for unresolved matchups; extend to ten if
outcomes differ. Three matching outcomes alone are not a statistical guarantee.
A timeout never becomes a loss, draw or completed close result.

Win-only output leaves the full combat calculations intact. Avoid per-tick replay
exports for routine runs; optimize how many fights and seeds are necessary rather
than stopping a fight merely because one side has a large lead.

## Scope boundary

This plan does not alter published rankings, historical data or browser behavior.
Counter-coverage recommendations do not establish actual mixed-army performance.
No campaign has been started, and the stopped full ranking rerun stays stopped.
