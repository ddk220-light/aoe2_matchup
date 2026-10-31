# Phase one: build the civ matchup table from existing evidence

**Status: implemented on 2026-10-31. The completed inference-only dataset and
coverage report are in
[`campaigns/civ-matchups-inference-phase1-2026-10-31`](../../campaigns/civ-matchups-inference-phase1-2026-10-31/README.md).
The design below records the intended behavior and its implementation rationale.**

## 1. The result this phase should produce

Build the entire civilization-versus-civilization unit matrix, fill outcomes that
existing evidence supports, and explicitly mark everything that still needs a
simulation or validation of an inference rule. A row can be complete as an
inventory entry while its combat outcome remains unresolved.

The optimization is opponent-specific, directional inference. If an archer already
beats a particular infantry army, a suitably stronger archer may inherit that win.
If the infantry beats the original archer, replacing it with a stronger archer may
cross the win boundary: that case needs more evidence. Overall unit ranking alone
does not establish either relationship.

Phase one ends with a reviewable table and a deduplicated list of unresolved
questions. It does not start the future simulation queue, change published unit
scores, select a new civilization scoring formula, or release the hidden Advisor.

### Approved scope and measured inventory

| Item | Count / policy |
|---|---|
| Civilization/unit variants | 555, across 56 civilizations |
| Exact mechanics profiles | 374 |
| Unordered civilization matchups | 1,540 |
| Unordered cross-civilization unit-variant cells | 151,223 |
| Distinct cross-civilization profile pairs | 68,916 |
| Identical-profile pairs within that inventory | 45 |
| Historically represented cross-civ profile pairs | 2,373; not automatically accepted outcomes |
| Buffers | Zero |
| Close/uncertain | Allowed; not a substitute for missing evidence or errors |

The 68,916 pairs are the inventory, not a commitment to run that many simulations.
The two directions of a civilization comparison are views of one stored result,
not separate votes or separate fights.

## 2. Freeze the inputs before inferring anything

Create a new inference-build manifest, separate from every battle campaign. It
records input file hashes, target engine source hashes, rule versions, code version,
roster, unit profiles, scenario policy, and the exact build settings.

Primary sources:

- `campaigns/unit-rankings-consolidated-2026-10-29/manifest.json`, `runs.jsonl`,
  `additional-recorded-runs.jsonl`, and the existing validation reports.
- `campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json` for the frozen
  mechanics, scenarios, engine configuration, and corrected source identity.
- `reports/unit-ranking-scores-final-2026-10-29/scores.json` for approved display
  categories and identity mapping. The average score is not a matchup label.
- The corresponding reference database for display names and audited descriptors.
  Resolve actual unit tiers from the data: for example, `Aztecs|halberdier` is a
  Pikeman, not an Aztec Halberdier.

Paths above are relative to `aoe2x/js_simulation/calibration/` unless stated
otherwise. The accepted consolidated dataset hash is
`17a91c8fa14553abbce1f894cbeb4e637d9fe9a82977fc2da2b0bc824cfade3c`.
The corrected campaign hash is
`1ac49a6abf1f3a1a104c7bcf675a3a327b6939d49273ae49c51eb6157264693d`.

The old Advisor's Python results, 30-versus-30 tests, and 3,000-resource tests are
excluded. They have different mechanics and army policies. The accepted current
rankings are evidence for this work, but their underlying records retain their
individual engine provenance.

### Army setup must be calculated for every target pair

Use `deriveRecordedBattleSetup` in `src/battle-setup.js`:

```text
weighted cost = effective food + 0.9 * effective wood + 1.1 * effective gold
cheaper army = 27 physical units
more expensive army = max(1, Math.round(27 * sqrt(cheap cost / expensive cost)))
```

Use fully discounted costs, including batch division, and JavaScript rounding.
Equal costs produce 27 versus 27. Recalculate both army counts when replacing
either unit: even the unchanged opponent can receive a different count.

Preserve the recorded geometry, first-N placement policy, no buffers, disabled
scripted kiting and AI orders, and owner orientation. `loadLabScenario` defaults
to including buffers, so every phase-one scenario construction must explicitly
pass `includeBuffer: false`. Do not infer geometry from the display category.

Keep three distinct keys:

1. **Variant key:** civilization plus unit identifier; needed for every table cell.
2. **Unordered profile-pair key:** deduplicates identical questions across civs.
3. **Oriented evaluation-context key:** ordered profiles, both counts, scenario,
   policy, and engine identity; determines whether evidence is interchangeable.

Reuse `combatProfileHash` from `node/ranking-equivalence.mjs`. It ignores only the
display civilization and retains costs, collision, effects, and unknown fields.
Do not introduce approximate stat rounding or discard an inconvenient effect to
increase sharing.

### Orientation is a real input

The mixed melee/ranged scenario has separately authored orientations. Reversing
the selected civs in the UI must invert the stored answer without changing the
underlying physical scenario.

Choose and freeze one context per pair using input compatibility, never its
winner: prefer an eligible existing context; break multiple eligible-context ties
by a stable context key. If no eligible context exists, use a deterministic
profile order with the recorded scenario policy. Preserve other contexts as
separate evidence. A conflict between otherwise relevant orientations is flagged
for review; do not resolve it by majority vote across different setups.

This gives reproducible answers under a stated orientation. It does not establish
that a future physically reversed fight would have the same winner. Any desired
side-neutral aggregate is a separate future validation question.

## 3. Build an evidence ledger before building rules

Read raw run records, not just averaged HP scores. Each record retains its source
file and line, source hash, campaign, engine version, mechanics hashes, scenario,
orientation, counts, seed, outcome, and completion/error state.

The offline audit found 7,600 selected runs plus 77 preserved extra runs. The
selected records contain 6,768 original-engine and 832 corrected-engine results.
Across all available records, corrected evidence falls into these source groups:

| Corrected evidence status | Groups |
|---|---:|
| Complete initial seeds; unanimous across all available corrected seeds | 182 |
| Complete ten seeds; outcomes vary | 1 |
| Initial three vary; corrected extension incomplete | 1 |
| Some corrected records; initial three incomplete | 155 |
| No corrected records | 2,059 |
| Total source matchup groups | 2,398 |

These are source-group counts, not the number of distinct cross-civ table cells
that can be filled. Profile sharing, scenario compatibility, and mirror cases
still need to be applied.

The extra records matter: a corrected Champion mirror has three initial losses
from one owner's perspective, but its preserved ten-seed set contains both
winners. Looking only at the selected initial seeds would hide that instability.

### Evidence tiers

| Tier | Meaning | Permitted use |
|---|---|---|
| Exact current evidence | Complete valid seed set, matching corrected source and full evaluation context | Direct observed outcome; eligible root for inference if sufficiently robust |
| Partial current evidence | Matching corrected context, incomplete seed set | Observed provisional evidence and candidate prediction; flag missing validation |
| Prior-engine ranking evidence | Valid recorded ranking fight from another engine/context | Candidate generation, plausibility checks and future test priority; never relabel as a current-engine measurement |
| Legacy Advisor evidence | Old Python engine / population-resource setup | Excluded from labels and validation |

Audit source versions and contexts separately; do not combine one corrected seed
with two original seeds and call it three current-engine wins. Do not count
equivalent-civ copies as independent observations. Deduplicate identical jobs,
preserve retries, and surface conflicting records rather than selecting a favorable
attempt.

Complete initial seeds are 0, 1, 2. When they disagree, the existing policy requires
0 through 9. Always inspect additional available seeds even if the initial three
agreed. No missing seeds are run in this phase.

An intact old source group does not trigger a full ranking rerun. If its evidence
is needed later, the unresolved question can be a particular anchor refresh or a
representative rule check, rather than every dependent matchup.

## 4. Define what a table cell can say

Separate the outcome, evidence type, and follow-up requirement. A single Boolean
`wins` cannot represent the approved task.

| Displayable conclusion | Evidence | Follow-up |
|---|---|---|
| A wins / B wins | Direct, compatible completed records | None unless records conflict |
| A wins / B wins — inferred | Versioned, supported directional rule rooted in eligible records | No individual fight required; retain rule audit status |
| Close/uncertain | Completed compatible seeds have different winners or genuine drawn results | None required simply to force a winner |
| Equivalent mechanics | Both armies have the same complete mechanics and setup policy | No intrinsic profile advantage; not a claim that every seeded fight draws |
| Needs simulation | No adequate outcome evidence | Specific missing question / dependency |

For an unresolved cell, retain a separate optional `candidateOutcome` such as
“likely Briton archer win.” It remains unresolved and is not counted as a win in
any consumer. This allows the table to capture useful analysis without silently
turning a prediction into a result.

Use fields such as:

```text
pairKey, contextKey, variantAliases
outcome: a_win | b_win | close_uncertain | equivalent | unresolved
evidenceType: observed | inferred | identity | provisional | none
needsSim, needsReview, reasonCodes
candidateOutcome, sourceRunIds, rootAnchorIds
ruleId, ruleVersion, ruleValidationId, inferenceDepth
featureComparison, blockedConditions, explanation
```

Do not fabricate HP remaining or numerical win probabilities for inferred rows.
Three wins in three seeds are recorded evidence, not a 100% probability claim.
Low survivor HP can block inference without erasing an observed winner. Incomplete
or timed-out jobs stay incomplete; they are not automatically close fights.

## 5. Build opponent-specific features, not a universal strength score

For each candidate relationship, compare the armies against the actual opponent:

| Feature | Why the comparison needs it |
|---|---|
| Actual counts and physical-unit costs | A nominal upgrade can field fewer units; a discount changes the fight |
| Damage per ordinary hit in both directions | Base armor, bonus armor classes, class presence, and resistances can reverse apparent advantages |
| Hits to kill for supported static states | A small damage or HP change can cross an integer breakpoint |
| Attack delay and reload in engine ticks | Initial strike and sustained attacks differ; display decimals hide rounding |
| Accuracy and projectile behavior | Nominal DPS does not capture missed shots hitting neighboring units or pass-through |
| Range, minimum range, movement speed | Affect initial fire and closing; range does not simply multiply DPS |
| HP, regeneration, defenses | Sustained healing or a first-hit block can depend on combat state and attack type |
| Collision, footprint, formation, counts | Affect contact, crowding and how many units can attack |
| Special mechanics and target tags | Armor bypass, anti-cavalry bonuses, charge, splash and transformations break generic ordering |

Reuse pure engine functions such as `calculateDamage`, `attackDelayTicks`, and
`reloadTicks` where their inputs can be represented correctly without advancing
combat. An absent armor class is not interchangeable with an armor class of zero.
Round and apply minimum damage exactly as the engine does.

Closed-form ordinary-hit arithmetic is allowed. It is a descriptor, not a battle
prediction by itself. An estimate such as damage times accuracy divided by reload
is explicitly nominal: it is not a rigorous army DPS bound.

Do not call `estimateTimeToKill` in `src/combat/matchup-summary.js`: it contains a
time-stepping one-versus-one simulation. Do not use the summary builder that calls
it either. No Monte Carlo, pathfinding rollout, shadow battle, or replay execution
is hidden inside this analysis phase.

### Effects need explicit support

Create a registry of effect fields and the rule families that understand them.
Static bonus armor and armor bypass can use exact per-hit adapters. Stateful
effects require their own validated transfer conditions: regeneration while
attacking, damage reflection, independently recharging attacks, armor stripping,
bleeding, charges, first-hit defense, HP transformations, aura-dependent HP, splash,
and pass-through projectiles cannot default to ordinary attacks.

Unknown effects block transfer. They do not block sharing an exact observed pair
between truly identical profiles. Economy effects remain recorded; do not treat
gold generated during battle as extra reinforcements or silently change the
approved purchase-cost formula.

Approved display merges are preserved, but inference families remain mechanical.
For example, elephants, lancers and knights share a display category without
sharing a universal matchup ordering. Jarl's display placement likewise does not
override its actual mechanics.

## 6. The inference rules, in increasing order of uncertainty

### R0: Exact evidence and exact-profile sharing

If ordered mechanics, counts, context and engine all match, carry the observed
result to every alias. This is the strongest saving and does not need a model of
which stat is more important. Opposite views invert the winner once.

For identical-profile pairs, record mechanical equivalence rather than promoting
a seeded owner's win into a civilization advantage. Retain any actual runs for
orientation/randomness diagnostics.

### R1: A guarded one-sided improvement or deterioration

Start with an observed result A versus X. Hold X fixed. Compare A with B against
X, including X's recomputed count and damage against B.

| Anchor | Supported relationship | Inference |
|---|---|---|
| A beats X | B no worse against X | B beats X |
| A loses to X | B no better against X | B loses to X |
| A beats X | B weaker against X | Unknown |
| A loses to X | B stronger against X | Unknown |

Apply the same logic when holding the attacker fixed and replacing the opponent.
For example, a win against a harder opponent can transfer to an easier opponent;
a win against an easier opponent says nothing definitive about a harder one.

Start with narrow mechanical families: same attack/projectile behavior, supported
effects, same relevant tags and footprint, compatible geometry, and no unfavorable
changes to either army's count. Compare effective damage and survivability in both
directions, not only attack numbers. A cost change that alters counts is a separate
regime, not an automatic improvement.

Even a favorable stat vector is not a formal proof of monotonicity in a stochastic
multi-unit physics simulation. R1 outcomes are labeled inferred and must pass the
offline counterexample checks below. Broad family slogans such as “all knights
beat all skirmishers” do not qualify as R1.

### R2: Robust transfer with tradeoffs

This is the rule needed for the user's Briton archer example. Higher range can
come with lower firing speed, accuracy, or army size, so there is no simple
component-by-component dominance.

Construct a family-specific comparison with:

1. A robust anchor: inspect every eligible seed's winning margin, not only its
   mean, and exclude seed-sensitive anchors from definite propagation.
2. Both directions of exact ordinary-hit damage and attack breakpoints.
3. Army-count changes and count breakpoints.
4. Explicit changes in range, reload, accuracy, speed, footprint and defenses.
5. Supported effect regime and the same formation/orientation family.
6. A validation envelope learned and checked against existing eligible evidence.

The envelope records which combinations of changes have historically preserved
the winner, and which have caused reversals. A candidate must be within a supported
region; being inside independent minimum/maximum ranges is not enough if the
combination itself has no evidence. A new special effect is outside the envelope.

Winner HP margin is a robustness feature, not a transferable amount of damage or
a mathematical error budget. Do not subtract a guessed DPS penalty from an 82% HP
margin and declare the remaining number a proof. Do not invent universal range,
speed or accuracy weights from one example.

If existing evidence cannot validate a tradeoff, retain the predicted winner and
flag the rule or pair for future validation. The phase is still complete when all
such gaps are explicitly represented.

### R3: Bracketing between observed win and loss cases

For a fixed opponent and a supported family ordering, locate measured wins and
losses around a candidate. Clearly stronger replacements of measured winners,
or clearly weaker replacements of measured losers, can be resolved. The region
between a win and a loss is the unresolved boundary.

This is not interpolation between overall ranking scores. If the order reverses
for that opponent, split the family or stop using the ordering. No binary-search
assumption survives an observed counterexample.

### Evidence that only generates candidates

Similar benchmark-result vectors, overall scores, common category, and ordinary
game knowledge can prioritize plausible transfers. They cannot independently
authorize a definite label. A beats B and B beats C does not imply A beats C.

For phase one, every resolved transfer is at most one substitution away from
direct eligible evidence. Changing both armies or following several inferred
results can generate a candidate, but requires independently supported bounds
before resolution. Inferred cells never become independent training labels.

## 7. Worked case: Britons versus Aztecs

The actual ranking benchmark is **Chinese Arbalester**, rather than Spanish
Arbalester. These existing Aztec results use the corrected engine:

| Aztec army | Army counts against benchmark | Existing result | Mean winner HP |
|---|---|---|---:|
| Pikeman | 27 Pikes / 24 Arbalesters | Arbalesters win 3/3 | 82.15% |
| Elite Eagle Warrior | 26 Eagles / 27 Arbalesters | Eagles win 3/3 | 66.45% |
| Champion | 27 Champions / 27 Arbalesters | Champions win 3/3 | 34.85% |

Relevant archer tradeoffs:

| Archer | Range | Reload seconds | Accuracy | Weighted cost |
|---|---:|---:|---:|---:|
| Chinese Arbalester | 8 | 1.7 | 100% | 72 |
| Briton Arbalester | 11 | 2.0 | 90% | 72 |
| Briton Elite Longbowman | 12 | 2.0 | 80% | 75.5 |

The Longbowman also has different attack, spearman bonus, attack delay and armor.
It is not simply the same Arbalester with more range.

The table builder should produce this reasoning for each of the six new cells:

| New pair | Directional conclusion | Phase-one decision |
|---|---|---|
| Briton Arbalester vs Aztec Pikeman | A large archer win is the anchor; range improves but reload/accuracy worsen | Primary candidate for inferred Briton win if R2 passes; otherwise predicted Briton win, flagged for rule validation |
| Elite Longbowman vs Aztec Pikeman | Same anchor; additional damage/count/accuracy differences | Evaluate separately under R2; do not copy the Arbalester conclusion by unit category |
| Briton Arbalester vs Elite Eagle | Infantry already beats benchmark; archer improvement might flip it | Needs simulation unless another eligible anchor independently brackets the answer |
| Elite Longbowman vs Elite Eagle | Same unresolved boundary, different mechanics | Needs simulation unless independently resolved |
| Briton Arbalester vs Champion | Champions beat benchmark; replacing the archer can change winner | Needs simulation unless independently resolved |
| Elite Longbowman vs Champion | Same directional uncertainty | Needs simulation unless independently resolved |

This captures the requested optimization without hardcoding the expected result
for Britons or assuming every improvement preserves a particular winner.

The recorded Aztec anchor IDs are `m_3190b1285f9cabca27af` (Pikeman),
`m_96afa0257b13847d3957` (Eagle), and `m_3fc8c437e3d62a2ed940` (Champion).

## 8. Validate the inference using existing data only

Rule validation is an offline prediction exercise over recorded fights. It must
not invoke the engine to recreate a fight.

1. Freeze each proposed rule and its applicability conditions before evaluating
   its held-out cases. Define its features and any margin cutoffs from development
   data; do not tune thresholds to make the test set pass.
2. Remove a target pair's label, all equivalent-civ copies, all its seeds and
   reverse-view copies. Infer it using other roots, then compare with its recorded
   outcome. Keep different-engine records of that target out of training too.
3. Also hold out entire profiles or related families where the evidence allows;
   otherwise disclose that the check measures interpolation among familiar units.
4. Evaluate current-engine and prior-engine strata separately. Prior-engine
   agreement can guide a rule but cannot certify current-engine performance.
5. Record resolved coverage, abstentions, wrong-winner count, invented certainty
   on close fights, and errors by count regime, effect family and direction.
6. Include hostile cases: armor breakpoints, cost discounts, slow high-HP armies,
   bonus damage, altered ranges and observed rank reversals.

For a rule to be enabled, require no known applicable counterexample, a documented
validation region, successful held-out checks within that region, and disclosure
of the actual independent support. Any wrong-winner counterexample blocks the
rule in that region until the predicate is corrected and retested. A region with
no held-out support remains a candidate rule, not an enabled one.

Do not manufacture a universal statistical confidence from a small clean sample.
The 182 unanimous corrected groups are sparse and were not a random sample of the
whole matrix. Share support counts and any defensible confidence interval with
its assumptions; do not treat thousands of aliases as thousands of validations.
No minimum HP-margin threshold or probability percentage is silently inherited
from the old Advisor. Any numeric rule cutoff is versioned with its calibration.

This may leave useful-looking shortcuts unvalidated in phase one. Record those
as shared validation dependencies so a future representative fight can potentially
unlock many cells. Do not respond by launching new tests or refreshing the entire
rankings dataset.

## 9. Resolve conflicts and preserve explanations

Generate all applicable candidate explanations before assigning a final decision.
Do not accept the first convenient anchor found in file order.

Resolution precedence:

1. Exact, compatible measured evidence determines the observed result.
2. Any inference that contradicts that evidence is a rule counterexample, not
   an additional vote against the measurement.
3. Compatible measured seed variation gives close/uncertain; missing required
   seeds are recorded separately as incomplete evidence.
4. Supported, agreeing inference rules can resolve a cell when no direct outcome
   exists. Their shared roots are deduplicated; agreement is not independence.
5. Conflicting eligible inferences leave the cell unresolved and invalidate or
   narrow the relevant rule region. An older incompatible observation is retained
   as a warning rather than mixed into a vote.
6. Unsupported predictions remain candidates with `needsSim: true`.

Each result must explain: the tested anchor, its observed outcomes, which side was
replaced, what improved or worsened, recomputed army counts, the rule's evidence,
and why it is safe to infer or necessary to abstain.

Store dependency edges from roots and rule versions to derived cells. When a rule
is withdrawn, invalidate all its dependents and regenerate them. Acyclic direct
root dependencies prevent circular support and repeated amplification of one
mistaken inference. Shuffling input order must not change the decisions.

## 10. Mark unresolved work as questions, not one job per cell

Every unresolved cell gets one or more machine-readable reasons:

- `no_eligible_anchor`
- `incomplete_current_seeds`
- `prior_engine_only`
- `possible_win_boundary`
- `unvalidated_tradeoff`
- `count_or_formation_change`
- `unsupported_effect`
- `orientation_conflict`
- `conflicting_inferences`

Build a separate requirement table. A requirement can be a direct pair test, a
particular missing anchor, or validation of a narrowly defined transfer rule.
Several cells can depend on the same requirement. They remain unresolved until
that requirement is actually satisfied; identifying a representative is not
itself permission to infer all of its dependents.

For later review, record the unique profile pairs and displayed civ cells each
requirement might unlock, whether a win and a loss would each be informative,
mechanical novelty, and historical processing-time evidence when comparable.
Potential reach is not a promised skip count. Runtime estimates remain unknown
where the recorded sample does not support them.

Future scheduling can prioritize expected uncertainty reduction per second, then
update the table after each new anchor. Phase one only exports these dependencies
and candidate representatives. It does not schedule, seed, or execute battles.

## 11. Storage, performance and reproducibility

Use one new versioned output directory, for example
`calibration/campaigns/civ-matchups-inference-<build-id>/`. It is derived analysis,
not a replacement for a source campaign. Source journals remain read-only.

Recommended outputs:

- `manifest.json`: immutable identities, input hashes and build/rule versions.
- `matchups.sqlite`: profiles, variants, contexts, source records, anchors,
  rule validations, explanations, decisions, aliases, and requirements.
- `profile-matchups.jsonl`: one decision for each of the 68,916 profile pairs.
- `civ-matchups.csv`: all 151,223 expanded variant cells, including unresolved.
- `needs-sim.jsonl`: unique unresolved requirements and affected pair keys.
- `rule-validation.json`, `conflicts.json`, and `coverage.json`.
- `review.md`: readable reasoning, including every Britons–Aztecs cell and examples
  of resolved, uncertain, equivalent, and blocked cases.

For the first implementation, normalized JSONL can be the canonical exchange
format and SQLite a derived index. Hash canonical records, not nondeterministic
SQLite file bytes. Atomically publish the completed build manifest after integrity
checks; checkpoints must never masquerade as a final table.

Compute each distinct profile pair once, then expand aliases. Index anchors by
opponent, scenario and mechanical family. Cache static directed damage/features;
374 profiles require at most 139,876 directed profile comparisons before filtering.
Do not compare every civ cell with every source row repeatedly. Use bounded
candidate lists and known-anchor adjacency to generate transfer candidates.

Separate input normalization, feature extraction, candidate generation, validation,
and materialization checkpoints. Resume only if input and rule hashes match;
otherwise write a new build. The stopped simulation supervisor stays stopped.

This is finite static computation over a moderate table, not an hours-long battle
campaign. Measure its actual runtime during implementation. Any proposed work
estimated to exceed one hour requires the owner's approval before starting.

## 12. Concrete implementation sequence

Proposed modules live in `aoe2x/js_simulation/node/civ-matchups/`; keep them separate
from the existing worker and campaign runners.

| Step | Proposed module / deliverable | Review condition before proceeding |
|---|---|---|
| 1 | `inputs.mjs`, `inventory.mjs`: source manifest, roster, aliases, pair contexts | Exact inventory totals; no missing units; setup matches policy |
| 2 | `evidence.mjs`: all run provenance, seed sets and evidence tiers | Reproduce audited counts; expose conflicting and extra records |
| 3 | `features.mjs`, `effects.mjs`: pure static comparisons and support registry | Damage/count boundary checks; unknown effects abstain |
| 4 | `rules.mjs`: exact sharing and conservative directional candidates | Worked Britons–Aztecs reasoning and counterexamples are correct |
| 5 | `validate-rules.mjs`: offline holdouts and permitted regions | Every enabled rule has documented support; unsupported rules remain candidates |
| 6 | `infer.mjs`: deterministic conflict handling and dependency graph | No circular inference; no unresolved cell counted as a win |
| 7 | `export.mjs`: complete table, coverage and deduplicated requirements | All cells accounted for, provenance/explanations intact |

Entry point: `node/build-civ-matchup-inference.mjs --phase infer-only`. It should
have no execution flag and no dependency on a simulation runner. Source review
and tests check its import graph and prevent worker-pool or combat-advance calls.
Do not execute an existing end-to-end test suite that secretly runs battles as
part of this phase; use the dedicated static-analysis tests.

First populate the full matrix as unresolved with identity matches and direct
evidence. Then add inference passes. That makes every improvement measurable and
avoids an attractive partial table that silently omits difficult units.

## 13. Acceptance checks for phase one

- All 555 variants and 56 civilizations appear; all 1,540 civ matchups have every
  cross-product row. Counts reconcile to 151,223 cells and 68,916 profile pairs.
- Exact-profile sharing preserves every unknown mechanics field and cost.
- Counts, rounding, discounts, batches, equal-cost cases, buffers, scenarios and
  orientation are checked against existing helpers and frozen inputs.
- Both views of a pair agree by inversion; equivalent/uncertain statuses are
  symmetric. No physical reverse fight is claimed to have been measured.
- Every observed label points to complete compatible records; all extra records
  are considered. No mixed-engine seed set is presented as current-engine evidence.
- Every inferred label has a rule version, eligible direct roots, conditions,
  validation scope, and readable explanation. Every unknown has a concrete reason.
- Unsupported effects, conflicting rules, count changes, and low-margin/unstable
  anchors exercise abstention paths rather than defaulting to wins or losses.
- Holdouts do not leak through equivalent civs, reverse views, alternate engines,
  seeds, or inferred labels. Validation support is counted by independent roots.
- Seed variation and mirror cases are visible; errors/timeouts are never draws.
- Status totals reconcile at both profile and displayed-cell levels. Coverage is
  reported per civ, family and evidence tier, exposing concentrated blind spots.
- Input permutations and clean rebuilds produce identical canonical decisions.
- Source files and existing run journals are unchanged; zero new simulations,
  replays, worker jobs, browser ranking changes, or production releases occurred.

## 14. What to review after this phase

Review how much of the matrix is observed, inferred, equivalent, close, or still
unresolved; inspect the actual explanations and failed shortcuts; then decide
which remaining questions are worth simulating. Show both the number of distinct
questions and the number of displayed cells they affect.

The first review should include Britons–Aztecs, a conventional cavalry/skirmisher
case, a discount-driven count reversal, an unsupported special effect, and an
inference conflict. Do not claim a percentage of simulations saved before this
materialized audit exists.

The old Advisor currently computes population/resource wins on demand and uses
them for counters and two-unit coverage. A future integration must read stored
outcomes, understand unresolved/close statuses, and use the new setup. Two units
covering different enemy counters does not establish mixed-army combat strength.
Those UI and recommendation changes belong to a later phase; this phase delivers
the complete, explainable evidence table they will consume.

## Supporting offline artifacts

- [Inventory audit](audit.json), generated by [audit.mjs](audit.mjs).
- [Source evidence audit](source-evidence-audit.json), generated by
  [source-evidence-audit.mjs](source-evidence-audit.mjs).
- [Overlapping historical contexts](overlapping-results.json).
- [Earlier overall plan](PLAN.md); phase one here supersedes any suggestion to
  start a pilot before reviewing the inference-only table.
