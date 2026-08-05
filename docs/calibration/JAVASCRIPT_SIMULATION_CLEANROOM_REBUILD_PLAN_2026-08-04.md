# Clean-Room JavaScript Combat Simulation Rebuild

**Status:** Design proposal for user review. No implementation is authorized by
this document.

**Date:** 2026-08-04

**First milestone:** Render the exact recording map in a new Tailnet-viewable
viewer, with no units and no combat simulation.

## 1. Decision

Build a new JavaScript simulator from an empty mechanics core. Do not fork,
transform, or incrementally clean up either of the existing JavaScript engines:

- `apps/website/static/js/engine/` contains the current force-steering and
  H1/H3-era mechanics.
- `simulation_v2/` is also a fitted transform package. Its documented knobs
  include `RTRUE`, `ADELAY`, `RETARGET`, `CHURN`, `ENVELOP`, `KITE_CATCH`, and
  several unit- or mechanic-specific compensations.

Both remain historical references only. The clean-room simulator may reuse
non-behavioral art assets after their scale is verified, but it must not import
movement, target selection, collision, attack, kiting, arena, or timing code
from either engine.

The proposed home is:

```text
aoe2x/js_simulation/
  README.md
  docs/
  map/
  fixtures/
  src/
  tests/
  viewer/
  tools/
```

Nothing under this directory will be imported by the production website or
production data pipeline while the simulator is being developed.

## 2. Why the previous approach failed

The existing engine allowed outcome errors to be corrected by adding behaviors
that were not independently established:

- fixed post-swing movement pauses;
- extra post-swing recovery;
- collision anchoring during the pause;
- forced clockwise pursuit;
- inner and outer pursuit-lane fractions;
- radial, tangential, cohesion, and heading-blend weights;
- collision padding and repeated post-movement separation;
- ranged cadence quantization and stop overhead.

Those changes could improve a chosen Hand Cannoneer outcome while worsening
unrelated fights. On 21 non-HC ranged-versus-melee matchup families from the
locked FINAL corpus, H1+H3 reduced the number within 25 percentage points from
18 to 16 and reduced correct winners from 20 to 17. This is evidence of
compensating errors rather than a reusable model.

The new project therefore changes the order of work:

1. Reproduce the map and coordinate system.
2. Reproduce one-unit locomotion.
3. Reproduce one-versus-one engagement.
4. Reproduce target selection and retargeting at small group sizes.
5. Reproduce collision, blocking, and group re-engagement.
6. Add different melee bodies and melee ranges.
7. Add stationary ranged combat.
8. Add ranged movement and kiting.
9. Only then compare mass-battle winner HP.

Winner HP remains the final product metric. It is deliberately not the metric
used to choose movement, collision, target-selection, or attack-timing rules.

## 3. What “physics-first” means here

AoE2 combat should not be modeled as Newtonian physics or as a sophisticated
crowd simulation. The intended model is a deterministic, discrete game-state
simulation:

```text
command
  -> target acquisition or retention
  -> route/waypoint decision
  -> movement proposal
  -> collision/blocking result
  -> animation/action-state advance
  -> attack damage frame or projectile launch
  -> death/invalid target
  -> reacquisition or regrouping
```

Official game updates describe command modes, formations, regrouping,
collision-driven stopping, waypoint/path corrections, and bump-triggered
retargeting. They also describe attack delay as being calculated from attack
animation data. These are the kinds of mechanics the new engine should express:

- [Update 81058: pathing, obstruction routes, bump retargeting](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-81058/)
- [Update 153015: pathing/regrouping and animation-derived attack delay](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-153015/)
- [Update 61321: attack-move engagement and regrouping behavior](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-61321/)

The goal is behavioral equivalence for the recorded scenarios, not an
unsupported claim that we have reconstructed the proprietary engine source.

## 4. Non-negotiable modeling rules

### 4.1 No outcome-fitted mechanics

Every behavior-changing number must have a provenance record containing:

| Field | Meaning |
|---|---|
| Name and value | Exact value and unit |
| Scope | Which mechanic and units can read it |
| Source type | Game data, map/scenario data, direct recording measurement, or numerical control |
| Source reference | Exact field, recording IDs, or convergence test |
| Measurement method | How the value was derived without winner-HP fitting |
| Uncertainty | Resolution or observed interval |
| Acceptance test | Test that would fail if the value is wrong |

Permitted values:

- fields extracted from the current game data;
- exact map/scenario facts;
- direct measurements of the mechanic in controlled recordings;
- numerical tolerances that pass convergence tests and do not change game
  behavior when made smaller.

Forbidden values:

- a pause, multiplier, lane, steering weight, or target-switch delay selected
  because it improves winner HP;
- matchup-specific or Hand-Cannoneer-specific movement behavior;
- a random interval introduced to manufacture tape-like variance;
- a “temporary” override with no independent falsification test.

### 4.2 Deterministic by default

The same initial state and command stream must produce the same simulation.
Randomness is added only when the game mechanic itself is random, such as a
measured projectile-accuracy roll. Every random draw must be seeded, named, and
logged.

### 4.3 Frozen-snapshot ticks

All units make decisions from the same start-of-tick state. The engine must not
update Player 2 and then allow Player 3 to react to Player 2's already-committed
movement in the same tick.

### 4.4 One mechanic at a time

A stage cannot be accepted because a later mechanic cancels its error. For
example, incorrect collision cannot be accepted because a target-switch delay
happens to restore the final HP result.

## 5. Three possible rebuild approaches

### Approach A — clean-room state/event simulator with an instrumented viewer

This is the recommended approach. Build small modules for the map, commands,
movement, collision, targeting, animation, attacks, and projectiles. Add each
only after the previous layer matches controlled recordings.

Advantages:

- mechanics are inspectable and falsifiable;
- no inherited calibration debt;
- group behavior can be traced unit by unit;
- later balance results can be explained from event histories.

Cost: slower initial progress because the first milestones intentionally do
not produce full battles.

### Approach B — trajectory imitation

Train or fit a model to predict the next recorded position and target from
recent frames.

Advantages: it may reproduce seen recordings quickly.

Disadvantages: it is difficult to interpret, is likely to fail when army size
or unit type changes, and can hide the same overfitting problem in a different
form. It can later be useful as a diagnostic oracle, but should not be the
combat engine.

### Approach C — remove knobs from the current engine incrementally

Advantages: fastest route to something that already renders and completes
fights.

Disadvantages: current targeting, force steering, collision repair, attack
timing, and update order are interdependent. Removing one fitted rule exposes
another. It is not a credible clean-room restart.

**Recommendation:** Approach A. Use existing viewers only as UX references and
existing engines only as a catalog of mistakes and edge cases.

## 6. Stage 0 — exact map and viewer

Stage 0 contains no units and no simulator clock.

### 6.1 Required authoritative inputs

To make the map exact rather than inferred, the recording package should
include:

1. The exact `.aoe2scenario` file used by the recording rig.
2. The game build number and scenario-file hash.
3. A full-map screenshot at the recording camera orientation.
4. A short static recording showing the empty map, player colors, and camera.
5. If the scenario file cannot be supplied, an exported object list containing
   terrain tile, elevation, object type, object ID, owner, `x`, `y`, rotation,
   and obstruction footprint for every map object.

The current FINAL combat telemetry records unit positions and combat events,
but does not contain enough map-object information to reproduce the visual map
exactly. Historical documents describe a likely 16-by-16 arena, but those
documents are not authoritative under the current FINAL-only source rule.

### 6.2 Map model

The map module will contain only facts loaded from the scenario artifact:

- width and height in tiles;
- tile terrain and elevation;
- object positions and orientations;
- object obstruction footprints;
- playable and non-playable tiles;
- coordinate conversion between scenario tile space and viewer pixels.

Obstacle geometry must remain literal. A group of blocked tiles must not be
replaced with an area-equivalent circle.

### 6.3 Viewer requirements

The first Tailnet page should provide:

- exact terrain and decorative/obstructing objects;
- the same diamond/isometric presentation as the recording;
- a coordinate grid toggle;
- tile-center and object-origin toggles;
- obstruction-footprint overlay;
- cursor readout in tile coordinates;
- zoom and pan that do not change simulation scale;
- a reference-screenshot overlay with opacity control;
- map/scenario hash and game build displayed on screen.

### 6.4 Stage 0 acceptance

- Every tile, elevation, and object matches the scenario export.
- Tile-to-screen-to-tile round trips stay within `0.001` tile. This is a
  numerical display tolerance, not a combat mechanic.
- Obstruction overlays match scenario footprints exactly.
- A screenshot overlay reveals no unexplained map displacement.
- No existing simulation engine is loaded by the page.

Only after the user approves this map in the Tailnet viewer does unit work
begin.

## 7. Recording protocol

### 7.1 Separate outcome truth from mechanics experiments

The existing locked FINAL archive remains the only outcome-scoring authority:

```text
calibration/source/aoe2_golden_STANDARD_UNITS_FINAL.zip
SHA-256 31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9
```

The proposed new recordings are controlled mechanics experiments, not
replacements for or additions to that archive. They should be stored in a
separately versioned mechanics corpus and never silently merged into FINAL.

The current project rule prohibits using any other tape corpus. Before new
recordings are ingested, the user must explicitly authorize a second mechanics
authority and the project policy must be updated. Until that happens, supplied
files can be preserved as unprocessed inputs but cannot be used as calibration
evidence.

### 7.2 Fixed conditions for every recording

Every recording must declare:

- game build and data-mod version;
- exact scenario file hash;
- game speed and recorder tick rate;
- civ, unit, upgrades, stance, formation, and starting HP;
- stable unit IDs and player/owner IDs;
- exact spawn coordinates and facings;
- exact command script and command timestamps;
- RNG seed when the game or rig exposes one;
- which player/color receives each side;
- whether the setup is mirrored or player-swapped.

Commands should be issued by a deterministic scenario script or recording rig.
Manual micro is unsuitable for the mechanics corpus because it adds an
unrecorded decision process.

### 7.3 Required telemetry

The present FINAL summaries are excellent for outcomes, but target selection
and action transitions require richer data. The new recorder should emit a
stable unit snapshot at the highest reliable engine/recorder rate, preferably
60 Hz:

| Per-unit snapshot field | Why it is needed |
|---|---|
| Timestamp and game tick | Align every stream |
| Stable unit ID, owner, and unit type | Track identity through the fight |
| Full-precision `x`, `y`, facing, and velocity | Reconstruct movement and stops |
| HP and alive/dead state | Associate deaths with retargeting |
| Action/order state | Separate pathing, attacking, reloading, regrouping, and idle |
| Active command ID and command type | Connect behavior to the issued order |
| Command target unit ID or destination | Distinguish focus attack from autonomous acquisition |
| Current internal target unit ID | Construct the target graph |
| Animation ID, frame, and progress | Locate windup, damage frame, backswing, and movement release |
| Current waypoint or path, if accessible | Distinguish pathfinding from local collision response |
| Formation and slot ID, if accessible | Measure regrouping and compression |

Required event streams:

- command issued, including recipient unit IDs, target/destination, formation,
  stance, and command sequence ID;
- target acquired, retained, invalidated, and changed;
- path requested, waypoint reached, path blocked, and repath, if hookable;
- animation/action transition;
- attack committed;
- damage frame or projectile launch;
- damage with attacker and target IDs;
- projectile impact, miss, or disappearance;
- unit death;
- collision/bump/contact start and end, if hookable.

If an internal event cannot be captured, the recorder must say that explicitly.
It must not substitute a guessed event inferred during capture.

### 7.4 Replication and symmetry

- Map and single-unit deterministic checks: 3 repeats.
- One-versus-one attack-cycle checks: 5 repeats.
- Symmetric target-selection or retargeting scenarios: 10 repeats because the
  experiment is measuring which of several equivalent targets is selected.
- Later mass fights: at least 5 repeats, increased when the observed behavior
  distribution remains unstable.

For targeting experiments, every geometry should also be:

- mirrored across the relevant map axis;
- repeated with player/color ownership swapped;
- repeated with unit creation order reversed when the rig permits it.

This distinguishes geometry and path cost from player priority, array order,
creation order, or recorder artifacts.

## 8. Recommended experiment ladder

Each stage produces a versioned fixture pack and a written mechanics finding.
The next stage does not start until the current one has an accepted model and
viewer trace.

### Stage 0 — map and coordinate system

Deliver the Stage 0 artifacts listed above. No units.

Question answered: are the viewer and recording rig referring to the same
physical map and coordinate system?

### Stage 1 — locomotion without combat

Use one Champion because it is a simple infantry body and will be the first
combat baseline.

Record:

1. Stationary Champion for 5 seconds.
2. One-tile and five-tile horizontal moves.
3. One-tile and five-tile vertical moves.
4. Diagonal move of equal Euclidean length.
5. Move toward a perimeter obstruction.
6. Move past one side of the central obstruction.
7. Two allied Champions given crossing paths.
8. A trailing Champion walking into a stopped allied Champion.

Questions answered: coordinate scale, actual displacement speed, diagonal
behavior, stopping distance, turning/facing, obstruction clearance, allied
body blocking, and whether units overlap while moving or regrouping.

### Stage 2 — Champion versus Champion, one versus one

Recommended first combat batch:

| ID | Setup | Command | Repeats | Primary question |
|---|---|---|---:|---|
| `C1` | Face-to-face on one horizontal line | Both attack-move through the opponent | 5 | First acquisition, range crossing, reciprocal engagement |
| `C2` | Same geometry | Both patrol through the opponent | 5 | Whether patrol changes initial engagement |
| `C3` | Same geometry | Each explicitly attacks the other | 5 | Focus-command target retention |
| `C4` | Half-tile lateral offset | Both attack-move | 5 | Contact point, turn, and path correction |
| `C5` | Diagonal approach | Both attack-move | 5 | Axis-independent movement and range |
| `C6` | Same as C1, players swapped | Both attack-move | 5 | Player/update-order bias |
| `C7` | Same as C1, spawn sides mirrored | Both attack-move | 5 | Map-direction bias |

For every attack, compare:

- acquisition time and selected target;
- route and distance to contact;
- first animation start;
- damage frame;
- movement during every animation phase;
- interval between damage frames;
- final movement after the target dies.

Outcome HP is recorded, but Stage 2 passes on the event sequence and timing—not
on the final HP alone.

### Stage 3 — target selection with small groups

Keep every unit a Champion so stats do not confound targeting.

| ID | Setup | Repeats | Primary question |
|---|---|---:|---|
| `T1` | 1 versus 2, targets perfectly symmetric | 10 plus mirrors/swaps | Tie-breaking rule |
| `T2` | 1 versus 2, one target 0.25 tile closer | 10 plus mirror | Distance sensitivity |
| `T3` | 2 versus 1 | 10 | Shared-target behavior and approach slots |
| `T4` | 2 versus 2, aligned pairs | 10 | Pairing versus nearest/path-cost acquisition |
| `T5` | 2 versus 2, staggered diamond | 10 | Geometry and reachable-path selection |
| `T6` | 3 versus 3, one front and two rear | 10 | Front-target concentration and rear pathing |

The principal output is a target timeline:

```text
time -> attacker unit ID -> target unit ID -> reason for target invalidation/change
```

Candidate target-selection rules are evaluated against this timeline. They are
not selected by running the full fight and comparing winner HP.

### Stage 4 — death, retargeting, bumping, and re-engagement

Use controlled starting HP so the first death happens predictably without
changing attack behavior.

Record:

1. 3 versus 3 aligned, with the center defender starting one hit from death.
2. 3 versus 3 staggered, with the front defender one hit from death.
3. 4 versus 3, creating one overflow attacker.
4. 4 versus 4 in two ranks.
5. 6 versus 6 in two ranks.
6. 7 versus 6, creating a persistent overflow unit.
7. Front attacker blocked by two allied attackers while its chosen target is
   still alive.
8. Chosen target moves behind another enemy before the attacker's next swing.

Questions answered:

- When is a dead target invalidated?
- Does a unit choose its next target immediately or after completing an
  animation/action state?
- Does it prefer the nearest Euclidean target, shortest reachable path, the
  last attacker, or another rule?
- When a path is blocked by allies, does it wait, repath, or retarget?
- Does a physical bump trigger retargeting?
- Can rear-line units pass, overlap, or compress around planted front-line
  attackers?
- Does a unit resume walking during backswing or only when an action completes?

### Stage 5 — melee property variations

Introduce one changed property at a time:

| Matchup | Property isolated |
|---|---|
| Champion versus Halberdier | Different attack timing/damage while retaining small infantry bodies |
| Champion versus Elite Steppe Lancer | Extended melee reach and mounted movement/body |
| Champion versus Hussar | Faster mounted pursuit and a larger body |
| Champion versus Paladin | Large HP/armor difference and mounted body |
| Champion versus Elite Battle Elephant | Very large body and crowd obstruction |
| Heavy Camel versus Paladin | Bonus-damage correctness after movement mechanics are stable |

Start with 1v1 and 3v3 for each property. Expand only the cases that expose a
new mechanic.

### Stage 6 — ranged combat without kiting

Start with Arbalester because it provides a conventional projectile baseline.

Record:

1. 1v1 Arbalester versus Arbalester on stand ground.
2. 1v1 at exactly inside, exactly outside, and across the nominal range edge.
3. 1v2 and 2v2 target-selection layouts from Stage 3.
4. Explicit focus attack followed by target death.
5. Champion approaching a stand-ground Arbalester.
6. 3 Champions approaching 3 stand-ground Arbalesters.

Questions answered: range test, windup, projectile launch point, flight,
accuracy, reload, ranged target retention, overkill, and ranged retargeting.

### Stage 7 — ranged movement and kiting

Kiting must be decomposed into issued commands and resulting mechanics. “Kite”
is not itself an unexplained force.

Start on open ground:

1. Arbalester versus Champion: foot ranged unit that cannot freely outrun the
   pursuer.
2. Heavy Cavalry Archer versus Champion: mounted ranged speed advantage.
3. Hand Cannoneer versus Champion: gunpowder firing and infantry pursuit.
4. Hand Cannoneer versus Elite Steppe Lancer: faster, longer-reaching pursuer.

For each matchup, separately record:

- scripted move-then-attack commands;
- patrol;
- attack-move;
- explicit focus attack with scripted retreat commands.

Only after open-ground behavior is understood should the same scenarios be run
near the perimeter and central obstruction. Route direction must emerge from
the map, command destination, pathing, and collision—not a forced clockwise
rule.

### Stage 8 — group ranged-versus-melee expansion

Progress through 1v1, 2v2, 3v3, 4v4, 6v6, and the final equal-resource counts.
At every size, compare target graphs, contact graphs, melee attackers in range,
ranged movement/fire cycles, path lengths, and retargeting transitions.

Hand Cannoneer is included here as a normal ranged unit. It receives no
HC-specific rule.

### Stage 9 — outcome validation

After every earlier mechanics stage passes:

- run five seeded simulations for each locked FINAL recording;
- aggregate to matchup-family median signed winner HP;
- require the correct winner;
- require the median to be within 25 percentage points of FINAL;
- reject every time-cap/stalemate result;
- run melee-versus-melee, ranged-versus-ranged, and ranged-versus-melee
  regressions before promotion.

An outcome failure reopens the earliest mechanics metric that explains it. It
does not authorize a new outcome-fitted timer or steering weight.

## 9. Simulator observability

The viewer and headless runner must produce the same structured event log. A
fight should be explainable without watching it in real time.

Required simulator outputs:

- per-tick unit state;
- active command and target IDs;
- target-acquisition and invalidation events;
- route and waypoint decisions;
- contact and blocking events;
- movement proposal and committed displacement;
- attack-animation phase changes;
- damage and projectile events;
- death and reacquisition events;
- seeded random draws, when any exist.

The later comparison viewer should support:

- tape and simulation side by side;
- optional tape “ghost” positions over the simulation;
- selected-unit target lines;
- contact-radius and attack-range overlays;
- current command, action state, animation phase, and target ID;
- pause, single tick, event step, and variable playback speed;
- a target-graph timeline below the map.

This instrumentation is part of the simulator design, not optional debugging
work added after discrepancies appear.

## 10. Acceptance gates by layer

| Layer | Acceptance evidence |
|---|---|
| Map | Exact scenario data and screenshot overlay |
| Coordinates | Invertible transform and measured tape positions |
| Movement | Trajectory, speed, turns, stops, and obstacle clearance |
| Collision | Contact distance, blocked displacement, overlap, and release behavior |
| Targeting | Unit-ID target timeline across symmetric/mirrored experiments |
| Attacks | Animation start, damage frame, movement release, reload, projectile timeline |
| Retargeting | Death/block/bump-to-new-target transition |
| Formation | Slot movement, regrouping, spacing, and compression by command state |
| Kiting | Issued command sequence, path, stop/fire/move phases, and pursuit contact |
| Final outcome | Correct winner and family median signed HP within 25 percentage points |

No layer passes solely because the final winner is correct.

## 11. First requested delivery from the user

The smallest useful initial package is:

1. Exact recording `.aoe2scenario` file or complete map-object export.
2. Static full-map screenshot and short empty-map capture.
3. Game build number and hashes for the scenario and recorder.
4. Stage 1 locomotion recordings for one Champion.
5. Stage 2 Champion-versus-Champion recordings C1 through C7.
6. Rich telemetry schema/sample containing stable unit IDs, command recipients,
   command target/destination, current target ID, action state, animation
   information, full-precision position, damage, and death events.

The map artifacts can be delivered first. The locomotion and combat recordings
do not need to wait for the map viewer, but they should not be ingested until
the separate mechanics-corpus policy is explicitly authorized.

## 12. Immediate next step after approval

After the user approves this design:

1. Create a detailed implementation plan for Stage 0 only.
2. Create `aoe2x/js_simulation/` with no imports from existing simulator code.
3. Implement the scenario/map loader, coordinate transform, and map-only viewer.
4. Add the Stage 0 verification tests.
5. Start a local Tailnet-accessible server and provide the exact URL for user
   inspection.
6. Stop at the map approval gate before adding units.

The remaining stages will each receive their own design/implementation plan
after the previous stage is observed and accepted.
