# Generic Melee Contact Physics Design

## Goal

Replace the current collection of partially overlapping crowd permissions with
one owner-symmetric, physics-derived contact mechanism for melee units. The
mechanism must reproduce the authorized tapes' allied and enemy overlap
distributions across movement and attack states, improve effective-front access
in the three Phase 2 melee failures, and preserve the already-passing melee and
kiting controls.

The design treats overlap as a measured physical state, not as an outcome
calibration. Unit names, matchup IDs, player numbers, army ratios, and desired
winners may not participate in an overlap decision.

## Current evidence

The active diagnosis uses only the manifested project-local archive:

- archive: `aoe2_golden_phase2_WITH_TAPES.zip`
- SHA-256:
  `B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6`
- report:
  `calibration/reports/phase2_melee_failures_diagnosis_2026-08-18/report.md`

The failing rows are:

| Matchup | Tape mean | Current simulation mean |
| --- | ---: | ---: |
| Elite Keshik vs Champion | -27.15 | +4.90 |
| Elite Keshik vs Paladin | -21.88 | -0.70 |
| Elite Shotel Warrior vs Paladin | -24.48 | +2.60 |

Damage per hit and attack-cycle timing match the tape. The simulation instead
gives the Champion or Paladin side 21-35% more attack starts while the
Keshik/Shotel side receives 5-11% fewer. The divergence begins during opening
contact. Keshik-versus-Paladin additionally recovers from -0.70 to -26.87 when
allied crowd compression is disabled, identifying a reservation-topology defect
without justifying the removal of symmetric melee behavior.

Passing Boyar-versus-Champion and Boyar-versus-Paladin controls also show more
raw overlap than the tape. Therefore overlap frequency alone is not sufficient;
depth, duration, motion state, attack state, and local contact-graph topology
must be measured together.

## Scope

This phase covers dynamic unit-to-unit contact for land combat:

- same-master allied pairs;
- mixed-master allied pairs;
- enemy pairs;
- range-zero melee pursuit and engagement;
- sourced one-range melee closing and wedge behavior;
- melee contact with mobile ranged and ordinary ranged formations;
- inherited legal overlap, release, and separation;
- deterministic crowd topology and owner symmetry.

Static map collision, obstruction routing, formation placement, projectile
collision, damage calculation, reload timing, attack delay, target-order
semantics, and siege minimum range remain unchanged unless a failing test proves
that contact-state output is being consumed incorrectly at one of those
boundaries.

## Non-goals

- No unit-slug, civilization, opponent, ratio, row, or player-number branches.
- No post-fight score correction, forced winner, HP adjustment, or added RNG.
- No global collision-radius reduction.
- No arbitrary maximum based on a single tape frame.
- No replacement of sourced collision geometry with visual outline size.
- No restoration of the earlier owner-specific melee crowd gate.
- No tuning of speed, damage, reload, attack delay, armor, or HP.

## Tape measurement contract

A new reproducible analyzer will compute the same metrics for decoded tape
frames and retained simulation snapshots. It will operate only on manifested
golden sources and will record the archive hash in every output.

### Pair populations

Every live pair-frame is classified as:

1. same-master allies;
2. mixed-master allies;
3. enemies;
4. direct pursuit target and pursuer;
5. non-target enemy corridor contact.

The first three are exhaustive relationship groups. The final two are intent
subclasses used to explain enemy contact, not separate evidence sources.

### State populations

Each pair-frame is classified independently by:

- motion: neither moving, one moving, or both moving;
- attack: neither attacking, one attacking, or both attacking;
- liveness and target relationship;
- entering, persisting, or leaving contact;
- collision-radius pair, expressed both in tiles and normalized by the pair's
  full sourced extent.

At 10 Hz tape resolution, a frame-to-frame displacement is evidence of movement
over the sample interval, not an exact internal motion tick. Contiguous overlap
duration is reported in sampled intervals and may not be used as a sub-frame
engine constant.

### Metrics

For every run and state population the analyzer records:

- pair-frame count and overlap-pair share;
- frames containing at least one overlap;
- separation and overlap depth: minimum, p01, p05, median, p95, p99, maximum;
- normalized depth `depth / (leftRadius + rightRadius)`;
- contiguous overlap-window duration distribution;
- acquisition and release counts;
- maximum simultaneous overlapping pairs;
- per-unit local neighbor count distribution;
- connected-component size;
- deep-edge degree, triangle count, and four-clique count;
- attacking-unit count and target-load distribution during each contact state.

Literal extrema are retained for audit, but robust percentiles and repeat-level
ranges drive design decisions. A one-frame extreme may validate that a state is
possible; it may not by itself define the normal collision floor.

## Physics inputs

The runtime may use only properties available for any unit:

- `collision_size_tiles`;
- `min_collision_size_multiplier`;
- current position and proposed displacement;
- alive, moving, attacking, and captured-swing state;
- pursuit, engagement, and attack target IDs;
- sourced attack range;
- owner equality;
- deterministic pair identity.

The full pair extent is:

`fullExtent = leftCollisionRadius + rightCollisionRadius`

The deepest sourced moving-allied floor is:

`movingFloor = leftRadius * leftMinMultiplier
             + rightRadius * rightMinMultiplier`

Tape analysis determines when the engine is allowed to approach this sourced
floor. It does not create a unit-specific replacement radius.

## Runtime contact state machine

One stateful pair manager becomes the sole authority that grants a collision
extent smaller than the ordinary pair extent. `pair-interactions.js` remains the
immutable geometry snapshot consumed by avoidance, collision, path planning,
and attack reach.

Each dynamic pair is in one of five states:

1. **Separated** — ordinary full collision applies.
2. **Approaching** — projected movement closes the pair but has not received a
   reduced-extent reservation.
3. **Reserved transit** — one moving unit has a valid path or pursuit reason to
   pass its ally or an enemy blocker; the pair may close only to its derived
   extent.
4. **Engagement contact** — a melee attacker and its physically captured enemy
   are in legal attack contact. The reservation preserves the published contact
   but does not allow unrelated units to inherit it.
5. **Releasing** — the qualifying intent ended. Existing legal overlap is
   preserved long enough to separate monotonically; no further deepening is
   permitted.

### Acquisition

A reduced-extent reservation may be acquired only when all applicable
conditions hold:

- at least one unit has non-zero proposed movement;
- the proposed relative motion closes the pair;
- the mover is making progress toward a live pursuit target, engagement
  envelope, or explicit formation destination;
- the pair would cross ordinary full contact during the current swept step or
  is already in inherited legal contact;
- static bounds and obstacles remain valid;
- granting the edge respects the topology invariants below.

Reference ID, owner number, and iteration order are deterministic tie breakers
only after swept time of impact, projected normalized depth, and path progress.

### Depth

For an allied moving pair, the runtime extent is bounded below by
`movingFloor`. Whether it reaches that floor depends on the tape-validated
state transition, not a unit name.

For an enemy pair, the attacker's sourced attack range and the ordinary pair
extent determine legal engagement. Enemy overlap is admitted only by a direct
engagement-contact or corridor-transit reservation. No enemy pair receives a
blanket reduced collision radius.

A reservation can preserve a legal inherited depth but may never deepen below
its derived floor. The collision solver remains authoritative for the final
world geometry.

### Topology invariants

- A unit may have at most one deep-overlap reservation at a time.
- Deep reservations may not form a triangle.
- A shallow physical contact is not itself permission to shrink another edge.
- An unrelated third unit sees both members of a deep pair at their ordinary
  collision extents unless it independently wins a non-deep contact state.
- Connected groups may move and surround, but they cannot collapse into a
  multi-unit stack through transitive permissions.
- When multiple proposals compete for one unit, the manager selects one edge
  from physical priority; rejected edges retain ordinary collision.
- An attacking or stopped pair cannot newly acquire a moving-overlap
  reservation. It may only preserve and release an inherited legal state.

These are geometry invariants. There is no per-army maximum overlap count.
Different unit sizes naturally produce different tile depths while sharing the
same normalized mechanism.

### Release

A pair enters releasing state when its qualifying movement, target, or corridor
relationship ends. During release:

- current legal separation is preserved as the temporary floor;
- proposals may hold or increase separation but may not decrease it;
- the reservation disappears once ordinary full extent is restored;
- death removes the pair after the same-tick captured swing has completed its
  existing lifecycle;
- no release may turn a valid published world into a collision-convergence
  failure.

## Architecture and data flow

### New modules

- `tools/measure_pair_contact_states.mjs`
  - decodes comparable tape/simulation pair-state metrics;
  - emits JSON and Markdown reports with source provenance;
  - has no engine-write path.
- `src/combat/contact-reservations.js`
  - pure deterministic acquisition, persistence, topology arbitration, and
    release;
  - owns the dynamic reservation state for allied and enemy pairs;
  - returns diagnostics and data for a `PairInteractionSnapshot`.

### Existing modules

- `pair-interactions.js`
  - remains the common query surface for pair collision extent and contact
    geometry;
  - accepts the unified reservation snapshot instead of reconstructing policy
    from independent feature sets.
- `world.js`
  - calls the contact manager once after raw movement proposals and before
    local avoidance/collision;
  - stores one contact state, not separate per-owner crowd states;
  - publishes acquisition, persistence, release, and rejection diagnostics.
- `collision.js`
  - resolves the exact extents selected by pair interactions;
  - preserves inherited legal contact during release;
  - does not decide policy.
- `local-avoidance.js`, `chase-path.js`, and `attacks.js`
  - consume the same pair snapshot so pathing, movement stops, and engagement
    cannot disagree about the active contact surface.
- `allied-overlap.js`, `allied-transit.js`, and `enemy-transit.js`
  - their proven eligibility helpers may be moved into the unified manager;
  - their independent state stores and overlapping arbitration are retired only
    after parity tests pass.
- scenario builders
  - stop selecting melee crowd behavior by owner;
  - generic melee contact derives from unit mechanics and live intent;
  - kiting and one-range melee provide intent, not alternate collision laws.

### Tick boundary

The movement/combat order remains:

`target validation/acquisition -> orders -> movement proposals -> contact state
 -> avoidance -> collision -> engagement -> attack -> damage`

All decisions use the frozen start-of-tick snapshot. Contact selection does not
recompute targets or movement during the same tick.

## Symmetry and determinism

The implementation must be invariant under:

- swapping owners 2 and 3;
- reversing unit-array order;
- translating reference IDs while preserving their relative physical state;
- substituting another unit with identical mechanics and state;
- running the same scenario repeatedly with the same seed.

Owner and reference ID may settle an otherwise exact physical tie, but aggregate
behavior must not favor one owner or low/high ID cohort. Symmetry tests compare
normalized final states, contact diagnostics, and event logs after relabeling.

## Test-driven implementation

Every production behavior begins with a focused failing test that is observed
failing for the intended reason.

### Pure contact-manager tests

1. A closing moving-allied pair may acquire one mechanics-derived reservation.
2. A stopped pair cannot newly deepen.
3. An attacking pair cannot turn unrelated contact into transit permission.
4. One unit cannot hold two deep reservations.
5. Three units cannot form a deep-overlap triangle.
6. Mixed collision radii use their own sourced floor under the same rule.
7. A direct enemy target and a corridor enemy receive distinct contact modes.
8. A changed or dead target moves the pair to deterministic release.
9. Release separation is monotonic and cannot create invalid geometry.
10. Range-one melee uses sourced reach to form a wedge without a unit slug.

### Integration tests

1. `world.js` publishes one unified pair snapshot to avoidance, collision, and
   attacks.
2. Owner-swapped melee-versus-melee scenarios produce relabeled-identical
   contact diagnostics and outcomes.
3. Reversed unit arrays produce identical hashes.
4. A deep allied pair does not admit a third unit into the same stack.
5. Surplus melee units route around a saturated front rather than stalling or
   inheriting the front's reduced extent.
6. Existing legal starting overlap separates without collision failure.
7. Steppe Lancer and other sourced one-range melee retain generic wedge access.
8. Ranged formations, siege units, and obstacles retain their existing
   non-melee geometry unless they are the enemy member of a valid melee pair.

### Analyzer tests

- synthetic traces lock every relationship and motion/attack state;
- percentile and duration calculations are deterministic;
- unit death, missing frames, and 10 Hz interval semantics are explicit;
- source hash and member identity are mandatory;
- tape and simulation use the same separation and overlap definitions.

## Calibration and validation sequence

### Stage 1: Baseline measurement

Generate a versioned tape-versus-current-simulation contact report for:

- Elite Keshik vs Champion;
- Elite Keshik vs Paladin;
- Elite Shotel Warrior vs Paladin;
- Elite Boyar vs Champion;
- Elite Boyar vs Paladin;
- Elite Woad Raider controls where their tape ratios supply a useful density
  contrast;
- HCA/Arbalester versus Paladin or Champion controls affected by enemy contact;
- Steppe Lancer rows affected by one-range melee transit.

The baseline is preserved before engine edits.

### Stage 2: Physics gate

For each relationship and state population, compare run-level tape and
simulation distributions. Success means:

- overlap-pair share and robust depth percentiles move into the tape repeats'
  observed range, or improve without crossing the opposite side of that range;
- overlap-window duration and local graph topology move toward tape;
- no persistent three-unit deep stack appears where none exists in tape;
- movement and attacking subpopulations improve together rather than one
  aggregate hiding the other;
- owner-swapped physical metrics remain equal.

Sparse populations are reported as insufficient evidence and cannot be used to
invent a rule.

### Stage 3: Outcome gate

Use exact golden counts and starting positions. Stable rows receive five
deterministic simulation samples. Only tape-classified knife-edge rows may use
up to 15 samples.

- The three diagnosed rows must recover the tape's stable winner.
- Keshik-versus-Paladin must recover the tape winner and its simulation mean
  must fall within the tape repeat range after the generic mechanism replaces
  the isolated no-crowd A/B.
- Passing Boyar controls must keep the correct winner and must not newly exceed
  25 points absolute mean delta.
- No previously passing impacted row may flip a stable winner.
- No previously passing impacted row at or below 25 points delta may cross
  above 25; an individual absolute-mean-delta regression greater than five
  points requires diagnosis before acceptance.
- A regression is diagnosed as a separate physical mismatch; symmetry is never
  disabled to hide it.

### Stage 4: Impacted portfolio

After focused gates pass, run the recoverable parallel benchmark only for
manifested golden rows whose scenarios contain melee units. Each completed row
is atomically checkpointed. Existing checkpoints with a different engine
signature are not reused. The final report lists every wrong stable winner,
row above 25 points delta, unresolved run, and contact-distribution regression.

## Failure handling

- Any unmanifested or hash-mismatched archive stops tape analysis.
- Missing mechanics required for a derived extent is a construction error, not
  a fallback constant.
- Conflicting reservations are deterministically rejected, never silently
  merged.
- Collision non-convergence records the involved pair states and fails the
  sample; it is not retried with weaker geometry.
- Analyzer output is written atomically and is resumable per completed matchup.
- Three failed implementation hypotheses trigger an architectural review before
  further engine changes.

## Documentation and migration

The implementation will update:

- `docs/CURRENT_ENGINE_2026-08-15.md` with the unified contact state machine;
- `docs/GOLDEN_TAPE_COMPARISON_WORKFLOW.md` with the pair-state report;
- the Phase 2 diagnosis with before/after overlap and outcome tables;
- tests and source comments that currently describe owner-selected crowding.

Independent legacy reservation stores are removed only after their behavior is
represented by tests and the unified engine passes focused and portfolio gates.
No compatibility flag remains in the final engine: melee contact is a shared
physics rule.

## Acceptance criteria

- The analyzer reproducibly reports same-unit, any-allied, and enemy overlap by
  movement and attack state for tape and simulation.
- Unit-specific behavior comes only from sourced mechanics fields.
- One shared contact mechanism applies to both owners and all melee units.
- Deep overlap remains pairwise; transitive multi-unit stacking is impossible.
- All new tests were observed failing before production implementation.
- Focused unit and integration tests pass.
- The three diagnosed stable winners match tape.
- Passing Boyar, HCA, Arbalester, Woad, and Steppe controls satisfy the declared
  winner, 25-point, and five-point-regression gates.
- The impacted manifested-golden portfolio has no new wrong stable winner or
  engine failure.
- Reports and checkpoints are durable, recoverable, and source-hash pinned.
- No production deployment or push to `main` occurs without separate explicit
  user approval.
