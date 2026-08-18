# Shared Pair-Interaction Manager Design

**Date:** 2026-08-18

## Goal

Replace unit-specific and subsystem-specific overlap decisions with one shared,
stateful pair-interaction model. The model must reproduce the tape's transient
enemy penetration and varied allied formation overlap without allowing whole
armies to collapse into one body, changing attack ranges, or introducing
matchup-specific calibration constants.

The first behavior change is general melee enemy transit. Allied formation
overlap migrates only after enemy transit passes its own acceptance gates.

## Evidence

Three independently recorded golden matchup families show the same enemy
overlap signature:

| Golden matchup | Overlap while melee attacks | Melee attacks another unit | Run-level median depth |
|---|---:|---:|---:|
| HCA vs Paladin | 71.68% | 45.13% | 0.038-0.071 tiles |
| War Wagon vs Paladin | 73.39% | 41.80% | 0.068-0.109 tiles |
| War Wagon vs Champion | 67.69% | 29.54% | 0.035-0.101 tiles |

The common property is an attacking melee pursuer entering a ranged formation,
not the identity of the ranged unit. War Wagon and HCA collision half-extents
also differ, yet their conditional overlap depths are similar and both have a
deep tail. That rules out one permanent enemy-box shrink as a satisfactory
model.

The current engine behaves differently:

- HCA-Paladin enemy boxes never overlap. Their minimum simulated Chebyshev
  separation is 0.500685 tiles against a 0.50-tile full pair extent.
- The tape contains enemy overlap in 22.24-33.42% of HCA-Paladin frames and
  individual continuous overlap streaks lasting 2.934-7.530 seconds.
- HCA-HCA overlap is a separate allied defect. It occurs in 31.02% of simulated
  pair-observations versus an 11.53% tape median, but the simulated conditional
  median depth is only 0.020 tiles versus 0.1407 on tape. One simulated pair
  remains overlapped for 104.45 seconds versus a 22.92-second tape maximum.

Primary evidence artifacts:

- `aoe2x/js_simulation/calibration/reports/phase2_boyar_hca_diagnosis_2026-08-17/overlap_analysis.json`
- `aoe2x/js_simulation/calibration/reports/phase2_boyar_hca_diagnosis_2026-08-17/overlap_report.html`
- `aoe2x/js_simulation/calibration/reports/phase2_war_wagon_enemy_overlap_experiment_2026-08-17/tape_overlap.json`
- `aoe2x/js_simulation/calibration/reports/phase2_war_wagon_enemy_overlap_experiment_2026-08-17/contact_state_analysis.json`

## Existing Design Problem

`collision.js` currently answers allied and enemy collision questions through
different special cases. Same-formation allies may return zero obstruction
extent. Enemy pairs use the sum of their full collision radii unless an
`enemyOverlapDepthByMaster` entry applies. The only scenario-level producer of
that map is the War Wagon-specific policy in `world.js`.

That structure has three defects:

1. It assigns a general melee-pursuit behavior to the ranged victim's unit
   master.
2. It represents a crossing event as a permanent numeric depth.
3. Path planning, local avoidance, movement stopping, attacks, final collision,
   and starting-geometry validation can disagree unless the same exception is
   threaded through every call.

The War Wagon override is useful evidence and a working compatibility path,
but it must not become the template for every ranged unit.

## Pair-Interaction Contract

A shared pair resolver classifies every dynamic unit pair for the current tick.
It returns purpose-specific geometry instead of one overloaded radius:

```js
{
  kind,
  collisionExtent,
  pathObstructs,
  attackSurfaceExtent,
  mayDeepen,
  reason,
}
```

- `collisionExtent` controls movement publication and final constraints.
- `pathObstructs` controls chase-path and local-avoidance obstacle treatment.
- `attackSurfaceExtent` remains the physical full extent used by attack and
  stop-range checks unless a real unit mechanic says otherwise.
- `mayDeepen` distinguishes a live transit event from inherited overlap that
  may only persist or separate.
- `reason` is a stable diagnostic enum, not combat behavior.

The resolver supports four interaction kinds:

### Hard contact

Ordinary allied or enemy collision. The required separation is the applicable
full or sourced friendly extent. Static obstacles, buildings, map bounds, idle
enemy pairs, ranged-initiated enemy pairs, and unrelated enemy pairs remain
hard.

### Swept enemy contact

If opposing movement proposals cross the hard contact boundary during the same
tick and at least one body is an active melee or reach-melee pursuer, the solver
may publish the raw endpoints instead of rewinding both bodies exactly to the
boundary. The resulting penetration cannot exceed that tick's relative
attempted motion and cannot deepen on later ticks without a transit reservation.

This is a geometry-derived shallow-contact mechanism. It permits several
shallow contacts around a large body without introducing a fixed overlap depth.

### Reserved enemy transit

An active melee or reach-melee pursuer may temporarily treat one non-target
enemy as non-obstructing when that body lies in the corridor between the
pursuer and its current target. Collision is waived only for that reserved
pair. The unit's actual motion determines the crossing depth.

New transit never targets the unit being attacked. Direct-target attack and
stop range retain the ordinary physical surface extent. A unit that retargets
an already-overlapped blocker converts the pair to inherited overlap rather
than continuing to move through its direct target.

### Inherited overlap

When a swept contact or transit reservation ends before the boxes have fully
separated, the current separation becomes temporarily legal. The pair may
preserve or reduce that overlap but may not deepen it. Normal motion restores
hard contact once separation reaches the ordinary extent.

This prevents snap-apart corrections, oscillation, and invalid starting worlds
when actions change at a tick boundary.

## Enemy-Transit Eligibility

A unit may initiate enemy transit only when all conditions hold:

- It is alive and uses a melee or reach-melee attack mode.
- It has a live enemy pursuit target.
- Its raw proposal makes positive progress toward that target.
- The candidate blocker is an enemy other than the pursuit target.
- The blocker intersects the pursuer's radius-expanded corridor to the target
  and lies longitudinally between pursuer and target.
- The pair contains no static obstacle or building.

Candidate ordering is deterministic:

1. Preserve an eligible existing reservation.
2. Prefer the smallest forward clearance.
3. Prefer the smallest lateral offset from the pursuit corridor.
4. Break remaining ties by pursuer and blocker reference ID.

Deep reservations form a one-to-one matching: each unit may participate in at
most one reserved enemy-transit pair. Multiple shallow swept contacts may
coexist, but a unit cannot be in two simultaneous deep crossings.

## Reservation Lifecycle

The enemy-transit state records:

```js
{
  chaserId,
  blockerId,
  pursuitTargetId,
  acquisitionAxis,
  acquiredTick,
}
```

A reservation persists while the target remains valid and the pair is still
crossing. It releases when any of these geometric or combat events occurs:

- The chaser passes the blocker along the acquisition axis and the pair is
  separating.
- The blocker no longer lies in the corridor to the current target.
- The pursuit target changes and the old blocker is not still geometrically
  relevant.
- Either unit dies or leaves the live world.
- The blocker becomes the direct target.

Release while overlapped creates inherited overlap. No normal-path timeout
controls combat behavior. A separate high failure ceiling may clear corrupt or
non-progressing state defensively, but it must emit a diagnostic and must not be
used to calibrate outcomes.

## Shared Data Flow

Each world tick follows one authoritative sequence:

1. Resolve orders, targets, and raw desired movement.
2. Update allied and enemy pair reservations from the immutable starting
   snapshot and raw proposals.
3. Build a `PairInteractionSnapshot` for the tick.
4. Pass that same snapshot to chase-path planning, local avoidance, contact
   steering, movement proposals, final constraint resolution, attack stopping,
   and geometry validation.
5. Publish the next world and carry only active or inherited pair state.

No subsystem may reconstruct overlap eligibility from unit master IDs or action
labels independently. This makes path choice and final geometry agree.

## Module Boundaries

- `pair-interactions.js`: pure pair classification and purpose-specific extent
  lookup.
- `enemy-transit.js`: deterministic candidate detection, one-to-one matching,
  persistence, crossing release, and inherited-state production.
- `allied-transit.js` and `allied-overlap.js`: remain responsible for allied
  candidate policy initially, then expose their reservations through the shared
  pair snapshot.
- `world.js`: owns pair state across ticks and constructs one snapshot after raw
  movement proposals exist.
- `collision.js`, `chase-path.js`, `local-avoidance.js`, `movement.js`, and
  `attacks.js`: consume the shared resolver and no longer decide eligibility.

The current `enemyOverlapDepthByMaster` interface remains as a compatibility
adapter during the enemy experiment. It is removed from the War Wagon scenario
only after the shared behavior passes both War Wagon golden controls.

## Determinism and Safety Invariants

- Results are invariant to input unit-array ordering.
- Each unit participates in at most one deep enemy-transit reservation.
- Static obstacles, buildings, map bounds, and dead units are never transit
  partners.
- Ranged units cannot initiate enemy transit merely because they are kiting.
- Direct targets retain their sourced attack and stop-range geometry.
- A non-reserved pair cannot deepen inherited overlap.
- Expiring a reservation cannot make the starting snapshot invalid.
- Published positions remain finite and inside map bounds.
- Pair-state cleanup cannot throw because a target died during the tick.
- Diagnostics report acquisition, persistence, release reason, maximum depth,
  and any defensive recovery.

## Staged Delivery

### Stage 1: Shared contract with no behavior change

Introduce the pair snapshot and adapt current hard collision, allied transit,
and War Wagon overlap behavior to it. Existing hashes and focused tests must
remain unchanged.

### Stage 2: Experiment-gated enemy contact and transit

Add swept contact, one-to-one non-target transit, inherited overlap, and viewer
diagnostics behind one scenario experiment flag. Do not change allied formation
behavior or ranged timing in this stage.

### Stage 3: Replace the War Wagon override

When the shared model passes HCA-Paladin and both War Wagon controls, remove the
War Wagon-specific runtime depth and rerun the focused result set. A true
unit-specific collision mechanic can still be represented in sourced mechanics;
this change removes only matchup calibration.

### Stage 4: Migrate allied formation overlap

Expose existing allied reservation types through the same pair snapshot, then
replace unconditional same-formation transparency with bounded transit and
inherited overlap. This stage targets the HCA-HCA frequency, depth, and duration
mismatch without changing the accepted enemy rule.

### Stage 5: Make the accepted model the default

Remove the experiment gate only after the full ranged-versus-melee regression
set, focused collision tests, determinism tests, and viewer inspection pass.

## Verification Strategy

Implementation follows test-driven development. Focused unit tests must first
fail for the absent shared behavior and then pass after each isolated stage.

### Geometry and state tests

- A melee chaser blocked by a non-target enemy acquires a reservation and
  crosses it.
- A direct target is not selected as a new transit blocker.
- Two chasers competing for one blocker receive one deterministic reservation.
- A third unit cannot join an active deep pair.
- Several simultaneous swept contacts remain shallow.
- Reversing input arrays yields identical pair keys and final positions.
- Target death, retargeting, crossing, and separation release correctly.
- Release while overlapped becomes non-deepening inherited contact.
- Static obstacles, buildings, and map bounds remain hard.
- Attack and stop range remain unchanged for the direct target.
- Collision resolution and starting-geometry validation accept the same pair
  snapshot.

### Golden overlap gates

HCA-Paladin 20v15 must reproduce the observed shape across five golden repeats:

- frames with any enemy overlap: 22.24-33.42%;
- all-pair overlap observations: 0.335-0.500%;
- contact observations at or below 0.51 tiles: 0.515-0.706%;
- conditional run-level median depth: 0.038-0.071 tiles;
- continuous pair-overlap maximums within the observed 2.934-7.530-second
  repeat band;
- attacking remains the majority state and attacking another HCA remains the
  largest single state.

War Wagon-Champion must preserve:

- frames with any overlap: 28.64-35.53%;
- all-pair overlap observations: 0.44-0.66%;
- conditional run-level median depth: 0.035-0.101 tiles;
- the correct Champion winner.

War Wagon-Paladin must preserve:

- all-pair overlap observations: 0.72-1.06%;
- conditional run-level median depth: 0.068-0.109 tiles;
- the correct Paladin winner.

The initial enemy stage must leave HCA-HCA metrics unchanged. The later allied
stage targets the tape bands:

- frames with any HCA-HCA overlap: 71.83-81.86%;
- all-pair overlap observations: 10.50-13.89%;
- deep overlap observations below 0.40 separation: 6.07-8.69%;
- conditional median depth: 0.125-0.146 tiles;
- longest continuous pair overlap: 14.058-22.918 seconds.

### Outcome regression gates

- No currently correct ranged-versus-melee winner may flip.
- No newly introduced absolute tape delta may exceed 25 points without explicit
  review.
- HCA-Paladin, HCA-Boyar, HCA-Steppe Lancer, HCA-Hussar, ranged-Champion,
  Scorpion-Paladin, War Wagon-Paladin, and War Wagon-Champion are mandatory
  focused controls.
- Use five simulation samples per golden row by default and never exceed the
  previously agreed 15-sample ceiling. A long unresolved fight is reported as
  knife's edge rather than sampled indefinitely.
- The recoverable parallel runner checkpoints every completed row.
- No engine failure, non-finite position, invalid geometry, or unresolved
  collision state is acceptable.

## Viewer Diagnostics

The experiment viewer exposes, without changing battle behavior:

- active enemy-transit pair lines;
- chaser, blocker, and pursuit-target IDs;
- pair state (`hard`, `swept`, `transit`, or `inherited`);
- current full extent, separation, and overlap depth;
- acquisition and release reason;
- current deep reservation count and largest contact component.

The viewer defaults to accepted engine behavior. The experiment uses a stable
query parameter until the general model becomes the default.

## Failure Handling

- An invalid pair snapshot fails before movement publication with the pair IDs
  and reason.
- A stale reservation is removed deterministically when either unit is absent.
- A non-progressing reservation that reaches the defensive ceiling emits a
  recovery diagnostic and becomes inherited contact; it never grants a new
  deeper overlap.
- Golden runner failures checkpoint the completed rows and retain the exact
  scenario, seed, pair diagnostics, and final state for recovery.

## Non-Goals

- No unit-, civilization-, or matchup-specific overlap depth.
- No attack, armor, speed, reload, kiting-clock, or target-selection tuning.
- No change to static-obstacle or building collision.
- No direct-target attack-range reduction.
- No attempt to solve allied formation packing in the enemy-transit stage.
- No production deployment or production data change.
