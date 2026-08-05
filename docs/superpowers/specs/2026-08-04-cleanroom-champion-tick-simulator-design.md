# Clean-room Champion Tick Simulator Design

**Status:** approved for planning on 2026-08-04

## Objective

Build the first deterministic combat layer for the clean-room JavaScript
simulator and validate it against every Chinese Champion-versus-Champion
recording in the authorized basics archive. The simulator must begin with 1v1,
then add only the mechanics required by 2v1, 2v3, 5v3, and 6v3.

The purpose of this phase is to reproduce small-unit engagement through general
mechanics: enemy acquisition, target locking, movement, body contact, attacks,
damage, death, retargeting, and local collision response. Tape outcomes are
acceptance evidence, not sources for fitted delays or steering weights.

## Source authority

The only tape archive permitted by this design is:

`aoe2x/js_simulation/calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip`

Required SHA-256:

`33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE`

The archive has 15 clean recordings, three repeats for each of five ratios.
Every repeat within a ratio uses identical unit IDs and starting coordinates.

| Ratio | Tape winner | Winner HP by repeat | Median winner HP | Survivors | Damage events |
| --- | --- | --- | ---: | --- | --- |
| 1v1 | side3, side2, side2 | 14, 14, 14 of 70 | 20% | 1 | 9 |
| 2v1 | side2 in all repeats | 112, 98, 112 of 140 | 80% | 2 | 7, 8, 7 |
| 2v3 | side3 in all repeats | 126, 126, 126 of 210 | 60% | 2 | 16 |
| 5v3 | side2 in all repeats | 252, 252, 210 of 350 | 72% | 4, 5, 4 | 22, 22, 25 |
| 6v3 | side2 in all repeats | 336, 336, 308 of 420 | 80% | 6, 6, 5 | 21, 21, 23 |

All damage is quantized in 14-HP hits. The 1v1 tapes prove that either side can
win, but three repeats do not establish a winner probability.

## Clock decision

The simulator will use integer ticks and a provisional 60-Hz simulation clock.
This is an explicit engine hypothesis, not a tape-fitted constant.

Public research did not find an authoritative Microsoft or World's Edge
statement publishing a fixed AoE2:DE simulation tick rate. Official support
material distinguishes the adjustable render FPS limit but does not state a
simulation frequency:

- <https://support.ageofempires.com/hc/en-us/articles/4432881214100-Advanced-Graphics-Option-FPS-Limit>

The authorized archive reports a 59.4-Hz recorder stream, and one 1v1 repeat
contains a consistent 0.018-second attack lead. Those observations are
compatible with a 60-Hz simulation or capture cadence but do not prove it.
Therefore:

- engine time is stored as an integer tick;
- `TICKS_PER_SECOND` initially equals `60`;
- `1 tick = 1/60 second` for movement and mechanic timers;
- browser animation and Node timers never define simulation time;
- a clock-forensics report measures how all 15 tapes quantize against 50, 60,
  and other plausible rates;
- changing the rate later requires an explicit provenance update and regression
  run, never an outcome-only adjustment.

## No-randomness rule

This milestone contains no random number generator and no stochastic mechanics.
The same inputs always produce the same state and event log.

When multiple actions are ready on the same tick, they are ordered by:

1. ready tick;
2. actor scenario reference ID;
3. target scenario reference ID;
4. event type.

This is side-neutral because it does not inspect owner number. It is a
deterministic scheduling hypothesis that can be replaced when later evidence
identifies the game's real rule. Mirroring geometry, swapping owners, and
reversing input-array order must not alter the reference-ID ordering result.

The 1v1 acceptance gate does not require a particular owner to win. It requires
the mechanically invariant result: nine 14-HP hits and one 14-HP survivor.

## Simulation boundary

Simulation tick zero is the first tick after the controlled scenario starts the
engagement. Recorder startup and scenario-trigger latency before movement are
kept in diagnostics but are not copied into Champion unit physics.

The viewer's source placement and combat roster are separate inputs:

- the locked scenario fixture supplies map geometry, reference IDs, positions,
  and facing;
- the combat roster replaces the source scenario unit type with Chinese
  Imperial Champion, master `567`;
- game-data extraction supplies combat statistics and physical dimensions.

This prevents the source formation's Paladin and Elite Steppe Lancer types from
leaking into Champion mechanics.

## Mechanics provenance

Every mechanics fixture field records a source path and raw field name.

Known Chinese Imperial Champion values already supported by the project game
data and the tapes are:

| Field | Value | Role |
| --- | ---: | --- |
| HP | 70 | health state |
| final attack, melee class | 18 | damage input |
| final melee armor, melee class | 4 | damage input |
| derived self-damage | 14 | `max(1, 18 - 4)` |
| final speed | 1.06 tiles/second | movement proposal |
| reload time | 2.0 seconds | attack readiness |

Attack reach, line of sight, collision radius, outline radius, attack graphic,
frame delay, and animation timing must be exported from Genie/game data before
combat code consumes them. Missing required mechanics are fatal input errors;
the simulator must not replace them with guessed defaults.

## Tick pipeline

Each tick processes the world in eight phases:

1. **Snapshot:** freeze all live unit state at the start of the tick.
2. **Target validation:** release dead targets; preserve live locked targets.
3. **Target acquisition:** units without a target choose the reachable enemy
   with the smallest surface distance, breaking exact ties by reference ID.
4. **Movement proposal:** pursuing units propose displacement toward their
   locked target using extracted speed and the fixed tick duration.
5. **Collision/contact resolution:** resolve all proposals from the same
   snapshot, prevent prohibited overlap, and retain valid tangential movement.
6. **Attack progression:** start windup when the target is in reach; advance
   windup and reload counters from extracted mechanics.
7. **Damage commit:** sort ready attacks by the deterministic event key, recheck
   that actor and target are alive, apply class-derived damage, and cancel
   pending actions from units killed earlier in the same tick.
8. **Event publication:** publish an immutable tick snapshot and event records.

Frozen proposals prevent owner update-order advantages. Sequential damage
commit prevents a same-tick fifth exchange from incorrectly producing a double
death.

## Movement and collision

Positions remain in scenario tile coordinates. At each tick, a pursuing unit's
unobstructed displacement magnitude is `speed / 60`.

The range check uses surface distance:

`max(0, center_distance - target_collision_radius) <= attacker_attack_reach`

Dynamic bodies never use viewer marker size. Collision radii come from the
Champion mechanics fixture.

For a proposed movement that would penetrate another body:

- remove the velocity component pointing into the contact normal;
- preserve the remaining tangential component when it is collision-free;
- otherwise stop the unit for that tick;
- never apply a clockwise preference, compression ratio, spring force, or
  post-collision pause.

Static Gaia obstruction uses the locked map fixture. No recorded ratio requires
a hand-authored route around the central rock.

## Target locking and retargeting

Every unit begins under a scenario-level seek-and-destroy engagement order.
This order allows acquisition but does not name an enemy.

A unit retains its target while the target is alive. Blocking by an allied body
does not by itself cause retargeting. A dead target is invalidated during the
next tick's validation phase, after which the normal acquisition rule selects a
new target.

The 1v1 stage validates only unambiguous acquisition. The 2v1 and 2v3 stages are
the first evidence for shared targeting, tie-breaking, collision, death, and
retargeting.

## Component boundaries

| Component | Responsibility |
| --- | --- |
| Tape importer | Verify the sole archive and generate immutable truth fixtures |
| Clock forensics | Analyze recorder/event quantization without changing mechanics |
| Mechanics exporter | Export Champion statistics and raw-field provenance |
| Simulation clock | Integer tick conversion and deterministic stepping |
| Unit state | Health, position, facing, target, action phase, and timers |
| Targeting | Candidate search, distance ranking, locking, and invalidation |
| Movement | Desired displacement toward a locked target |
| Collision | Symmetric dynamic-body and static-obstacle resolution |
| Combat | Reach, windup, reload, damage, death, and pending-event cancellation |
| World | Execute the fixed phase pipeline and publish immutable traces |
| Comparison | Compare one deterministic trace against all three tapes per ratio |
| Viewer adapter | Convert world snapshots into renderer records without advancing physics |

The map renderer remains a presentation component. Simulation modules do not
import DOM, canvas, timers, or viewer code.

## Stage sequence

### Stage A: 1v1

Validate direct enemy acquisition, straight-line pursuit, physical reach,
attack progression, 14-HP damage, deterministic same-tick ordering, death, and
pending-action cancellation.

Required outcome: exactly nine damage events and one Champion at 14 HP. Either
owner is acceptable; input order must not decide the result.

### Stage B: 2v1

Add multiple attackers pursuing one target, shared-target contact, and
deterministic approach around an allied body.

Required outcome: side2 wins with median aggregate HP 112/140 (80%), two
survivors, and a damage-event count within the observed 7-8 range.

### Stage C: 2v3

Add target death, reacquisition, minority-side elimination, and uneven local
crowding.

Required outcome: side3 wins with aggregate HP 126/210 (60%), two survivors,
and exactly 16 damage events.

### Stage D: 5v3

Exercise multi-rank approach, allied blocking, target concentration, local
sliding, repeated deaths, and retargeting.

Required outcome: side2 wins with median aggregate HP 252/350 (72%), survivor
count in the observed set `{4, 5}`, and damage-event count in `22..25`.

### Stage E: 6v3

Exercise attacker overflow, additional body congestion, and inactive attackers
finding usable contact paths.

Required outcome: side2 wins with median aggregate HP 336/420 (80%), survivor
count in the observed set `{5, 6}`, and damage-event count in `21..23`.

Each stage keeps all earlier stages green. A mismatch reopens the earliest
mechanics trace that explains it; it does not authorize a ratio-specific
constant.

## Comparison rules

The comparison report contains both strict outcome gates and diagnostic traces.

Strict gates:

- correct winner for every asymmetric ratio;
- exact median aggregate winner HP for each ratio;
- observed survivor-count and damage-event-count bounds;
- every landed hit deals exactly 14 HP;
- no timeout, stalemate, overlap, or invalid target;
- identical final state and event-log hash across repeated executions.

Diagnostics, not tuning targets:

- recorder-relative first movement time;
- first damage and final kill time;
- per-unit trajectory error sampled at tape timestamps;
- center and surface separation at attack release;
- target graph and damage attacker/victim timeline;
- per-unit blocked ticks, distance traveled, and attacks canceled by death.

If exact median HP fails while the mechanics trace is otherwise plausible, the
stage remains open and the discrepancy is documented. No hidden one-hit
tolerance is used to declare success.

## Viewer

The existing approved map remains unchanged. The viewer adds:

- ratio selector for 1v1, 2v1, 2v3, 5v3, and 6v3;
- play, pause, reset, single-tick, and next-event controls;
- current tick and simulation seconds;
- target lines, collision circles, attack reach, HP, and action state;
- simulation event timeline;
- selection among the three tape traces for diagnostic comparison;
- simulation-only playback with no random seed control in this milestone.

The viewer advances the world by requesting integer steps. Browser frame rate
changes only how quickly stored snapshots are presented.

## Error handling and invariants

The system stops with a descriptive error when:

- the tape archive hash is wrong;
- a truth fixture names another archive hash;
- a required decoded member is absent;
- a mechanics field lacks provenance;
- a starting unit overlaps Gaia or another starting unit;
- a unit targets a friendly unit, or retains a dead target after the next
  target-validation phase;
- HP increases or damage is not an integer 14-HP increment;
- a fight exceeds 3,600 ticks without a winner.

The 3,600-tick limit is a one-minute safety failure, not a simulated outcome.

## Deferred work

Random or seeded scheduling is explicitly deferred. The existing three-repeat
variation remains visible in reports, but the simulator produces one
deterministic trace per ratio.

Also deferred:

- fitting a probability to the 1v1 winner split;
- ranged combat and projectiles;
- user-issued kiting commands;
- full pathfinding around the center obstacle;
- formations and 21v21 combat;
- unit-specific special rules;
- claiming the target-selection policy is complete beyond the tested small
  Champion configurations.

Later evidence may justify a deterministic engine rule or a real seeded game
mechanic. Any such change receives its own provenance entry, tests, and
cross-ratio regression before acceptance.
