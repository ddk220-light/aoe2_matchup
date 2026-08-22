# Melee Geometry and Collision Simulation Plan

## Purpose

This is the handoff plan for rebuilding melee movement, contact, and overlap
from direct AoE2:DE observations. It records what the live captures have
established, what remains unknown, and the order in which to collect evidence
and update the JavaScript simulator.

The immediate goal is not to tune final HP outcomes. It is to make low-count
movement, stopping distance, body overlap, and attack initiation match the live
game. Larger battles should then emerge from the same pairwise mechanics rather
than matchup-specific rules.

## Current evidence

The first observation set is one Elite Keshik against one Paladin:

- Evidence log: `docs/MELEE_VS_MELEE_LIVE_OBSERVATIONS_2026-08-21.md`
- Automatic run: `calibration/live_observations/keshik_vs_paladin_1v1_2026-08-21/run_001/`
- Manual angle sweep: `calibration/live_observations/keshik_vs_paladin_1v1_2026-08-21/run_004/`
- Analyzer: `tools/analyze_live_keshik_paladin_1v1.py`
- Game version captured: `180059`

The raw captures are local evidence. The measurements required to resume the
work are reproduced in the observation log and below.

## What has been established

### World movement is continuous and Euclidean-normalized

World positions are continuous X/Y coordinates measured in tiles. Isometric
rendering does not change the physics coordinate system. Movement should use a
normalized direction:

```text
distance = sqrt(dx^2 + dy^2)
vx = speed * dx / distance
vy = speed * dy / distance
```

At 45 degrees, each axis receives `speed / sqrt(2)`. The unit therefore keeps
the same total speed rather than moving `sqrt(2)` times faster diagonally.

The manually steered Elite Keshik measured `1.540128 tiles/s` median moving
speed, matching its `1.54 tiles/s` game stat across the angle sweep.

### Melee body contact is axis-aligned box geometry

The live DAT gives both the Elite Keshik and Paladin collision half-extents of
`0.25 x 0.25` tiles. Their combined body extents are therefore `0.50` on X and
`0.50` on Y.

For two units A and B:

```text
combinedX = halfWidthA + halfWidthB
combinedY = halfHeightA + halfHeightB
overlapX = combinedX - abs(B.x - A.x)
overlapY = combinedY - abs(B.y - A.y)
colliding = overlapX > 0 and overlapY > 0
```

The capture contains exact corner contact at `dx=0.50`, `dy=0.50`. Its
Euclidean center distance is `0.707107`, proving that a single circular radius
is not a correct melee-contact metric.

For reporting, retain both penetration axes. When both are positive, the
minimum translation required to separate the pair is:

```text
penetrationDepth = min(overlapX, overlapY)
```

### Ordinary zero-range approach stops about 0.10 tiles outside body contact

The first three clean manual re-engagements began their attack animations at
max-axis center separations of `0.594561-0.598674` tiles. Subtracting the
combined `0.50` body extent leaves a per-axis gap of
`0.094561-0.098674` tiles.

The current working hypothesis for an ordinary zero-range approach is:

```text
abs(dx) <= halfWidthA + halfWidthB + 0.10
abs(dy) <= halfHeightA + halfHeightB + 0.10
```

This is an axis-aligned expanded box, not a circle. Its Euclidean radius varies
with approach angle automatically; no angle-specific calibration is needed.

### Movement stop, attack eligibility, and physical collision are separate

The existing clean-room engine already distinguishes three concepts:

1. Collision boxes determine physical obstruction.
2. Collision boxes plus the measured stop distance determine when an ordinary
   pursuit stops.
3. Outline boxes plus attack range determine whether an attack is eligible.

The live 1v1 observations cleanly measure the ordinary stop surface. They do
not establish the maximum outer attack envelope for a unit that is already
stopped, blocked, or reloading.

### Transient enemy overlap is possible

During manual crossing, the Elite Keshik entered the Paladin's axis-aligned
body box. Maximum measured axis-aligned penetration was approximately `0.12`
tiles. This establishes that enemy bodies are not always an absolute
never-penetrate barrier.

It does not yet establish why the overlap was permitted, how quickly it is
resolved, or whether the allowance depends on movement, attack, reload, or an
explicit order.

## What is not yet established

- Whether identical unit types use exactly the same contact and stop rules.
- When allied units shrink toward their DAT `min_collision_size_multiplier`.
- Whether enemy overlap differs between moving, stopped, and attacking states.
- Whether a moving unit can pass one ally, multiple allies, or an attacking
  ally under the same rule.
- How three or more simultaneous pair contacts are resolved.
- Whether collision corrections are applied to both units or only the mover.
- Whether units preserve tangential velocity and slide around a blocking body.
- The exact maximum melee attack-eligibility surface based on outline boxes.

No maximum-two-overlaps rule, angle lookup table, or unit-specific exception
should be introduced before these cases are observed.

## Planned simulator model

### 1. Represent boxes explicitly

Replace geometry assumptions based on one scalar radius with explicit data:

```text
collisionHalfExtent = { x, y }
outlineHalfExtent = { x, y }
minimumCollisionMultiplier
```

The existing scalar helpers happen to work for the Keshik and Paladin because
their X and Y extents are equal. The general model should not require that.

### 2. Keep metrics separate

- Movement and path length: Euclidean distance.
- Body collision and zero-to-one-range melee contact: per-axis box geometry.
- Projectile range: Euclidean distance from the appropriate outline surface.
- Reporting: retain Euclidean center distance, max-axis distance, X/Y gaps,
  X/Y penetration, and minimum translation depth.

No one distance function should be reused for all four purposes.

### 3. Resolve contacts pairwise and symmetrically

For each simulation tick:

1. Calculate every unit's intended Euclidean-normalized movement.
2. Use the spatial index to find only nearby unit pairs.
3. Build all body-contact constraints from the same pre-resolution snapshot.
4. Calculate corrections for every pair.
5. Apply accumulated corrections simultaneously and deterministically.
6. Preserve movement along an unblocked axis so units slide instead of stall.

This avoids player-number and reference-ID behavior differences caused by
sequentially moving one side before the other.

### 4. Derive crowd density from pair constraints

Larger formations should not use a global overlap counter as their primary
physics rule. Every pair must satisfy its effective box constraint. A three- or
four-unit cluster is then the result of all pair relationships, not one shared
blob radius.

If captures show that allies shrink while moving, use the DAT minimum collision
multiplier as the lower physical bound and determine the activation state from
the observations. Do not invent different shrink values for individual
matchups.

### 5. Keep attack state separate from contact resolution

Being within attack reach does not require physical body overlap. Conversely,
a transient overlap caused by movement does not automatically authorize an
attack. Target acquisition, movement stop, attack eligibility, windup, damage,
and reload remain separate state transitions.

## Next live-capture sequence

Collect a small number of controlled examples before editing the collision
engine:

1. Elite Keshik versus Paladin, automatic 1v1 at cardinal and near-45-degree
   starting offsets. This confirms the outer stop surface without manual reload
   interference.
2. Elite Keshik versus Elite Keshik, automatic 1v1 at the same offsets.
3. Paladin versus Paladin, automatic 1v1 at the same offsets.
4. Two identical melee units versus one enemy. Observe allied compression,
   attack positions, and whether the rear unit slides or stalls.
5. Two versus two with a straight-line start, then a staggered/diagonal start.
6. Manual movement through a friendly unit while that ally is moving, stopped,
   and attacking.
7. Repeat one small-unit and one large-unit pairing after the basic rules are
   stable, to verify that collision extents—not unit names—drive the result.

Three clean repeats per setup are enough initially. Increase the count only if
the captured behavior genuinely varies.

## Measurements required from every capture

For each relevant pair and frame, record:

- game time and entity IDs;
- owner, unit master, action state, and target ID;
- X/Y positions and movement vector;
- Euclidean and max-axis center distance;
- collision and outline half-extents from the live DAT;
- X/Y body gap or penetration;
- minimum translation depth when overlapping;
- pair angle;
- moving, stopped, attacking, reload, and damage transitions;
- number of simultaneous contacts per unit;
- connected component size for multi-unit contact clusters.

Summaries must be split by same-side/opposing-side and by movement/attack state.

## Evidence gate before implementation

Implement the box-based collision update after the controlled captures answer
the unresolved state questions. The first implementation should be accepted
only if it reproduces:

- 1v1 stop positions by angle;
- the observed absence or presence of overlap by state;
- 2v1 and 2v2 packing without stalls or unit collapse;
- symmetrical results when player sides are exchanged;
- the same behavior from unit data without matchup-specific constants.

Only after those low-count checks should the engine be rerun against larger
golden matchups and evaluated by final HP.

## Resume on another machine

1. Check out `codex/experiment-steppe-reach-wedges` and pull its latest commit.
2. Install the machine's CadeRemote gRPC prerequisites and place its local mTLS
   credentials beside `aoe2x/grpc/grpc_hp_log.py`. The key and certificate files
   are intentionally gitignored and must not be committed.
3. From the repository root, arm a capture with:

   ```text
   python aoe2x/grpc/grpc_hp_log.py <output-prefix> <maximum-seconds>
   ```

4. Start the scenario after the recorder reports that it is armed, then stop
   the recorder after the test is complete.
5. Analyze the new capture using
   `aoe2x/js_simulation/tools/analyze_live_keshik_paladin_1v1.py`, extending
   only its unit-selection arguments or output schema needed for the next
   controlled setup.
6. Append direct measurements to the observation log before changing the
   simulator.

The original engine implementation remains untouched by this documentation
update.
