# Hand Cannoneer calibration debt register

Date: 2026-08-03

## Bottom line

The combined `h1_h3` calibration arm now passes the agreed standard
Hand-Cannoneer-versus-melee gate: all seven matchup families retain the FINAL
tape winner and their median signed winner-HP result is within 25 percentage
points of the tape. That statement covers 33 FINAL recordings and five seeds
per recording (165 simulations).

It does **not** mean Hand Cannoneer calibration is finished globally. The
combined arm is opt-in, several active values are heuristics or inherited from
superseded calibration work, the simulation still cannot reproduce the FINAL
tape's context-dependent HC body compression, and HC versus Heavy Scorpion is
still outside the 25-point target.

This document is the audit trail for those assumptions. It separates:

- facts extracted from game data;
- values derived from map geometry or the locked FINAL tape;
- values chosen or retained because they improved outcomes;
- inherited constants whose comments point to old tape corpora and therefore
  are **not** current evidence; and
- experimental rules that remain off or were rejected.

## Evidence boundary

The only tape authority used for the current status and outcome numbers in this
document is:

- archive: `calibration/source/aoe2_golden_STANDARD_UNITS_FINAL.zip`
- SHA-256: `31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9`
- population: 339 recordings, 91 unordered matchups, 14 standard units

The verified fixtures are under `calibration/fixtures/`. Historical archives,
old `data/calibration` outputs, and old experiment reports are not accepted as
truth here. When an active code constant was originally justified by one of
those old reports, this document labels the constant **legacy-derived / FINAL
unverified** instead of repeating the old measurement as evidence.

Relevant code states:

- FINAL-only fixture/viewer gate: main checkout commit `6a11aebb`
- combined H1+H3 engine: worktree commit `94e7140e`
- ordinary simulation default: H1 and H3 are off

## Provenance labels

| Label | Meaning |
|---|---|
| `GAME-DATA` | Read from the current combat dictionary or Genie data. It is an input, not an outcome-fitting knob. |
| `FINAL` | Directly calculated from the locked FINAL archive above. |
| `GEOMETRY` | Deterministic arithmetic from an accepted map/body geometry. The inputs can still be wrong. |
| `CALIBRATED` | Selected or retained partly because it improved signed winner HP. This is a real calibration knob. |
| `HEURISTIC` | A hand-written behavior or number without a direct game-data field or decisive FINAL measurement. |
| `LEGACY` | Active inherited behavior whose current code comments cite a superseded tape corpus. It must be revalidated before being treated as truth. |
| `INACTIVE` | Wired for diagnostics but off in the accepted `h1_h3` arm. |

## Current FINAL outcome gate

Scores are signed from the HC perspective: positive means HC won with that
percentage of its starting army HP; negative means the opponent won with the
absolute percentage. Duration is not scored.

| Standard melee family | FINAL tape | `h1_h3` sim | Absolute gap | Status |
|---|---:|---:|---:|---|
| Champion | +75.36% | +97.50% | 22.14 pp | pass |
| Halberdier | +76.50% | +92.50% | 16.00 pp | pass |
| Elite Battle Elephant | -12.81% | -36.15% | 23.33 pp | pass |
| Elite Steppe Lancer | -8.03% | -26.16% | 18.13 pp | pass |
| Heavy Camel | +68.81% | +64.29% | 4.52 pp | pass |
| Hussar | -11.92% | -13.33% | 1.42 pp | pass |
| Paladin | -17.46% | -5.56% | 11.90 pp | pass |

This result is a family-level outcome acceptance result, not proof that the
intermediate trajectories, collision states, hit cadence, or engagement timing
are game-faithful.

## Active H1 rules: post-swing plant, recovery, and collision anchor

The combined viewer enables all three `C3` flags only for `h1_h3`:

```text
postSwingPlant = true
postSwingRecovery = true
postSwingCollisionAnchor = true
```

All three flags default to `false` in the engine.

### 1. The 0.7-second post-swing movement plant

| Field | Value |
|---|---|
| Constant | `POST_SWING_PLANT_S = 0.7` seconds |
| Trigger | A melee attacker lands a hit on a ranged, non-siege target |
| Effect | The attacker cannot locomote until the lock expires |
| Still allowed | Turning, retargeting, reloading, attacking if in reach, and being hit |
| Applies on killing blow | Yes |
| Excluded | Ranged attackers, melee victims, and Siege Weapons armor class 20 |
| Provenance | `LEGACY` measurement-derived value; not independently re-established from the locked FINAL archive |

This directly models the user's observed behavior: a melee unit stops to finish
its swing while the ranged unit continues moving. The rule is deliberately a
movement lock, not a universal attack delay. A target that remains in range can
still be hit when the attacker's ordinary cooldown expires.

The **0.7 seconds is calibration debt**. The code describes it as the midpoint
of a historical 0.64–0.74-second range, but that historical measurement is not
accepted as current tape evidence under the FINAL-only policy. It should be
remeasured with the locked FINAL streams where possible, or with a new
controlled recording if the existing streams cannot identify the animation
completion boundary.

### 2. Extra post-swing recovery

`meleeChaseRecovery(target)` adds an attack-cooldown cost after a melee swing
against a ranged, non-siege target:

```text
if target is a foot ranged unit,
and attacker is faster,
and attacker has exactly 0 raw melee range,
and attacker has no charge projectile:
    extra recovery = max(0.7 seconds, attacker reload time)
otherwise:
    extra recovery = 0.7 seconds
```

Mounted targets are detected by armor class 8 or 28. The full-reload branch is
therefore a **hard categorical rule**: some faster zero-range melee attackers
chasing foot HC pay an additional full reload, while extended-range, mounted-
target, charge, or slower cases pay 0.7 seconds.

| Item | Provenance | Risk |
|---|---|---|
| `max(0.7, reloadTime)` | `HEURISTIC` mechanism built around a `LEGACY` duration | High: it materially changes hits landed and survivor HP |
| Faster-than-target comparison | `GAME-DATA` speeds, but hand-written gate | Medium |
| Raw attack range exactly zero | `GAME-DATA` range, but hand-written gate | Medium |
| Mounted armor classes 8/28 | `GAME-DATA` classification | Lower, though the behavioral split still needs validation |
| Siege class 20 exclusion | `GAME-DATA` classification plus a hand-written scope choice | Medium |

This rule is one of the largest forcible interventions in the result. It is not
an animation system extracted from AoE2; it is a deterministic approximation
of lost pursuit cadence.

### 3. Collision anchoring while planted

Ordinary same-team collision resolution divides an overlap 50/50. During the
post-swing plant, if exactly one allied unit is planted, the planted unit stays
in place and the other unit absorbs the full separation. This prevents the
back line from sliding the attacking front line forward while it is supposed
to be finishing its swing.

The anchor does not affect cross-team collision, two planted allies, two
unplanted allies, or an expired plant.

| Number/rule | Function | Provenance |
|---|---|---|
| `dist <= 0.01 px` | Treat almost-coincident centers as exactly overlapping | `HEURISTIC`, inherited |
| `4 px` one-sided nudge | If one exactly-overlapping ally is anchored, move only the other body | `HEURISTIC`; chosen to preserve the old total separation |
| `2 px` per-side nudge | If neither or both are anchored, split an exact overlap | `HEURISTIC`, inherited |
| Three collision passes per tick | Resolve cascaded overlaps repeatedly | `HEURISTIC`, inherited |

The 4-pixel nudge is 0.133 tile and the 2-pixel nudge is 0.067 tile at the
current 30-pixel tile scale. These values matter only in a degenerate exact-
overlap case, but they are still invented numbers and belong in the register.

## Active H3 rules: central obstruction and forced clockwise routing

`h1_h3` uses `TapeBoxWithObstruction`, an opt-in arena. Ordinary simulations do
not use it.

### 1. Map and obstacle geometry

| Number/rule | Effect | Provenance | Calibration concern |
|---|---|---|---|
| `TILE_SIZE = 30 px` | Internal unit conversion | `HEURISTIC` scale only | Ratios are preserved; it should not change tile-space results |
| TapeBox bounds `1.2..14.8` tiles | Hard-clamps unit **centers**; no body-radius wall padding | `LEGACY` | Active and not yet independently re-derived from FINAL |
| Obstacle center `(9.0, 7.0)` tiles | Center of tree/rock cluster | `GEOMETRY` from scenario layout | Low if the scenario extraction is correct |
| 12 blocked tile centers | Visual/map footprint of central cluster | `GEOMETRY` | The physics does not use the literal shape |
| Obstacle radius `1.95` tiles | Replaces the 12-tile diamond with a smooth disc | `GEOMETRY`: `sqrt(12 / pi) = 1.954` | Area-equivalent is not path-equivalent; corners are removed |
| Soft field width `2.0` tiles | Distance outside the body-inclusive surface where steering acts | `HEURISTIC` | High; directly changes when units start turning |
| Radial push weight `3.0` | Pulls units toward the desired lane or away from the obstacle | `HEURISTIC` | High; competes with avoidance and retreat vectors |
| Tangential slide weight `4.0` | Drives circulation around the obstacle | `HEURISTIC` | High; determines how forcibly clockwise motion wins |
| Generic field cap `w <= 2` | Caps obstruction response when a body is inside the surface | `HEURISTIC` | Medium; hard constraint ejects any remaining penetration |
| Center epsilon `1e-6 px` | Degenerate-direction guard | Numerical guard | Negligible in normal fights |

The disc approximation was chosen for smooth motion. It prevents units from
catching on literal tile corners, so it is already a pathfinding assumption,
not merely a renderer choice.

### 2. Forced clockwise HC route

Inside the obstruction field, a ranged kiter ignores the sign of its incoming
heading and receives the fixed obstruction-centered tangent:

```text
clockwise tangent = (-radialY, radialX)
```

A radial correction aims the unit at:

```text
obstacle radius + unit radius + 0.5 * field width
```

The correction is divided by half the field and clamped to `[-1, +1]`. The
returned unnormalized vector is:

```text
4.0 * clockwise tangent + 3.0 * clamped radial correction
```

For HC, whose collision radius is 0.20 tile, the nominal lane is therefore
`1.95 + 0.20 + 1.00 = 3.15` tiles from the obstruction center.

This is the most explicit forced behavior in H3. It solved the observed split
where different HCs chose different sides of the cluster or drifted toward a
corner. It is deterministic and adds no random draw, but it is not a general
AoE2 pathfinder: every affected ranged kiter is ordered clockwise inside this
field.

### 3. Forced clockwise melee pursuit lanes

H3 also changes melee units chasing any ranged target, not only units chasing
HC.

- A sufficiently fast pursuer shares the outer midpoint lane.
- A slower or near-speed pursuer takes a shorter inner clockwise lane.
- Melee chasing melee keeps the generic heading-aligned avoidance.

The outer-lane speed threshold is derived from the modeled path radii:

```text
required speed ratio = (surface + field / 2) / surface
surface = obstacle radius + pursuer collision radius
```

For a 0.25-tile mounted body, the required ratio is approximately
`3.20 / 2.20 = 1.455`. Against HC speed 0.96 tile/s, that means the outer-lane
threshold is about 1.396 tile/s. This is why fast cavalry can share the outer
route while a 0.99-tile/s Elephant does not.

The inner target lane is:

```text
surface + (1 / 3) * field width
```

For a 0.25-tile body that is `1.95 + 0.25 + 0.667 = 2.867` tiles.

| Value | Provenance | Calibration concern |
|---|---|---|
| Outer lane fraction `0.5` | `HEURISTIC` midpoint | High |
| Inner lane fraction `1/3` | `CALIBRATED`; selected during the FINAL multi-family sweep | Very high; the most outcome-informed H3 knob |
| Speed-ratio formula | `GEOMETRY` from the two modeled radii | Medium; valid only if the lane geometry is valid |
| Always clockwise for either lane | `HEURISTIC` behavior matching the recorded scenario's circulation | High outside this scenario |

The one-third lane must not be presented as an extracted AoE2 constant. It was
chosen from candidate inner-lane fractions because it restored the Elephant
winner while keeping the full seven-family HC melee gate inside 25 points.

### 4. Final movement composition

The H3 vector is not the final velocity by itself. The engine composes:

1. retreat or pursuit basis;
2. group-kite steering where eligible;
3. unit avoidance;
4. H3 obstacle vector;
5. normalization;
6. heading smoothing; and
7. movement by the unit's game-data speed.

Heading smoothing is hard-coded as:

```text
new heading = 0.3 * previous heading + 0.7 * desired heading
```

That `0.3` is an inherited `HEURISTIC`. It changes turn responsiveness and
therefore the effective orbit, contact time, and number of attacks. It was not
newly fitted during H3, but it materially interacts with every H3 weight.

## Collision radius, overlap, and compression assumptions

### Physics radius versus drawn radius

The current unit body is:

```text
physics radius = max(5 px, collision_size * 30 px/tile)
```

For real HC data, `collision_size = 0.20`, so its physics radius is exactly
6 px or 0.20 tile. The 5-pixel lower clamp is a `HEURISTIC` fallback; it does
not bind HC but can bind smaller units. Hand-built test fixtures lacking
`collision_size` fall back to `outline_size` or 0.20 tile.

The ordinary production renderer still has a separate display-radius formula.
The HC Field Lab instead draws `unit.radius` exactly, so the visible disc is the
same disc used for collision. This UI change affects no simulation result.

### Current hard and soft body floors

| Number/rule | Effect | Provenance |
|---|---|---|
| Hard floor `radiusA + radiusB + 1 px` | End-of-tick collision separation | `HEURISTIC`, inherited |
| Soft floor `radiusA + radiusB + 2 px` | Movement avoidance begins one pixel farther out | `HEURISTIC`, inherited |
| Social band `< 1.5 * soft floor` | Adds avoidance even without overlap | `HEURISTIC`, inherited |
| Overlap force `3 + 5 * overlapFraction` | Separation strength inside soft floor | `HEURISTIC`, inherited |
| Non-overlap social force `0.5` | Separation strength in outer social band | `HEURISTIC`, inherited |
| `COMBAT_PACK_FACTOR = 1.0` | No same-team collision-floor compression | Explicitly disabled behavior |
| `COMBAT_PACK_SLACK_TILES = 1.5` | Defines how far behind contact a unit is considered engaged | `HEURISTIC`, inherited |
| `COMBAT_PACK_RANGED = true` | Allows ranged units into the pack predicate | Active but inert while factor is 1.0 |

Two HCs therefore have a hard center-distance floor of
`6 + 6 + 1 = 13 px = 0.433 tile`. The locked FINAL tape contradicts that
geometry in melee contexts:

- HC overall same-owner nearest-neighbor median: 0.308 tile;
- HC versus melee family medians: 0.223–0.309 tile;
- 72.5% of HC observations are below the nominal 0.40-tile diameter.

The current Genie `min_collision_size_multiplier` is not a solution by itself:
HC's value is 1.0. The simulation does not currently carry or apply that field.
The surviving hypothesis is a runtime formation/regroup/contact state that
temporarily permits same-team ranged overlap. No such rule was implemented in
the accepted H1+H3 result.

This means the passing melee outcome gate may contain compensating errors:
H1/H3 can produce the correct survivor margin even while the HC formation is
too physically spread out.

## Inherited ranged firing and kiting constants that affect HC

H3 did **not** shorten HC reload or windup. A regression test confirms that an
in-range HC whose cooldown is ready begins its windup on the first eligible
60 Hz tick. The following inputs and inherited rules still control its shots.

### Game-data HC inputs

| Field | Current value | Provenance |
|---|---:|---|
| HP per unit | 40 | `GAME-DATA` |
| Range | 7.0 tiles | `GAME-DATA` |
| Movement speed | 0.96 tile/s | `GAME-DATA` |
| Attack delay/windup | 0.25 s | `GAME-DATA` |
| Attack rate | 0.289855 attacks/s | `GAME-DATA` |
| Reload time | 3.45 s | Derived from game-data attack rate |
| Accuracy | 75% | `GAME-DATA` |
| Projectile speed | 7.5 tiles/s | `GAME-DATA` |
| Collision radius | 0.20 tile | `GAME-DATA` |
| Outline radius | 0.20 tile | `GAME-DATA`, visual only |

### Active inherited firing values

| Number/rule | Effect | Provenance/status |
|---|---|---|
| `FIRE_CYCLE_QUANTUM = 2/3 s` | A moved ranged unit's next shot is aligned to a cadence quantum | `LEGACY`; active and FINAL-unverified |
| `RANGED_STOP_OVERHEAD = 0.15 s` | Extra pre-shot delay after moving | `LEGACY`; active and FINAL-unverified |
| HC post-fire recovery `0.33 s` | HC cannot move immediately after launch | `LEGACY`; active and FINAL-unverified |
| Projectile radius `0.10 tile` | Arrival collision adds projectile body to target body | `GAME-DATA` |
| HC accuracy dispersion `0.50 tile` | Failed accuracy rolls displace the aim point within this radius | `GAME-DATA`, but currently pinned by slug because extraction drops the field |
| Legacy fallback miss spread `2.0 tiles` | Used only for projectiles without an extracted/pinned dispersion | `HEURISTIC`; does not apply to HC |
| Ballistic lead | Aim at an intercept and resolve against target position at arrival | Active inherited mechanism |
| In-flight damage accounting | Avoid firing at a target already covered by friendly projectiles | Active inherited mechanism |
| One-body approach margin | Ranged unit approaches to `reach - 2 * own radius` | Active inherited mechanism |

`LEAD_WINDOW_SECONDS = 0.3` exists but trailing-window lead is off in `h1_h3`,
so it does not affect the accepted result. Reduced-damage displaced hits are
also off.

### Active inherited group-kite values

| Number | Effect | Provenance/status |
|---|---|---|
| `KITE_TANGENTIAL_WEIGHT = 0.8` | Adds circulation around the group centroid | `LEGACY` and historically outcome-tuned |
| `KITE_COHESION_WEIGHT = 3.0` | Pulls ranged units back toward their group | `LEGACY` and historically outcome-tuned |
| `KITE_COHESION_RAMP_TILES = 2.0` | Ramps cohesion from zero at centroid to full strength | `HEURISTIC`/`LEGACY` |

These values are upstream of H3 and compete with its `4.0` tangential and
`3.0` radial obstruction weights. They must be included in any future H3
sensitivity analysis; changing only the H3 weights does not isolate the final
route.

## Scoring and harness numbers

| Number/rule | Purpose | Provenance |
|---|---|---|
| 25 percentage points | Maximum accepted absolute difference in signed winner HP | User-approved calibration target |
| Five seeds per recording | Simulation repeat count | User-requested |
| Median | Aggregates tape and simulation signed winner HP | User-selected robustness statistic |
| Winner sign | Positive for HC win, negative for HC loss | Analysis convention |
| 60 Hz (`dt = 1/60`) | Deterministic simulation step | Inherited engine choice |
| 600 seconds | Harness termination cap | `HEURISTIC` safety cap |
| Exact FINAL first-frame spawns | Initial unit positions for each recording | `FINAL` |

For the seven-family gate, every FINAL recording is simulated with five seeds.
The median is taken over the resulting signed outcomes. A family fails if the
winner sign is wrong or the signed HP gap exceeds 25 points. Fight duration is
reported only for diagnosis and is not optimized.

The 600-second cap can turn a non-resolving fight into a zero signed outcome,
so it is not entirely neutral. No HC-versus-melee gate run hit it, but any
future capped HC result must be treated as a termination failure, not a close
HP match.

## Viewer-only numbers

The HC Field Lab's physics renderer draws the actual simulation radius and a
30-pixel one-tile ruler. The following values are visual only and cannot change
winner HP:

- inward outline width: at most 1.5 px;
- kiting dot radius: `max(1 px, 0.32 * body radius)`;
- HP bar width: at least 12 px and otherwise one body diameter;
- HP bar height: 3 px;
- HP bar offset: 6 px above the body.

They are listed so they are not confused with collision or compression
settings.

## Experiments not kept in the accepted result

| Experiment | What it did | Current decision |
|---|---|---|
| H2 lane-aware kill handoff | After a melee unit killed a ranged unit, prefer the nearest ranged target with a clear lane; if all were blocked, defer one acquisition attempt | Rejected; off and not part of H1+H3 |
| H4 tape-heading oracle | Calibration harness could replace HC's high-level retreat heading with recorded headings while leaving local collision/avoidance intact | Diagnostic seam only; no steering behavior retained |
| E1 fight-center orbit | Replaced radial retreat with a fight-center clockwise orbit; optional 1.77:1 tangent/radial blend | Off in H1+H3 |
| C4 flee during reload | Let a hunted foot ranged unit keep fleeing through reload | Off in H1+H3 |
| Generic melee swing recovery | `MELEE_SWING_RECOVERY_S` | Set to 0; inactive |
| Permanent HC radius shrink | Would reduce HC collision radius in every context | Rejected; contradicted by ranged/siege spacing |
| Always apply Genie minimum collision multiplier | Would globally multiply collision floors | Not implemented; HC's multiplier is 1.0 anyway |
| Matchup-specific damage/reload tuning | Change HC damage or fire rate to hit a score | Not done |
| Duration fitting | Tune rules to match fight time | Explicitly not an objective |

## What remains for Hand Cannoneer calibration

### 1. HC versus standard melee: outcome gate complete, mechanism provisional

The agreed seven-family, 25-point, five-seed FINAL gate passes. No additional
winner-HP tuning is required for that narrow acceptance criterion.

However, the 0.7-second rule, full-reload recovery branch, one-third pursuit
lane, H3 steering weights, TapeBox bounds, and inherited group-kite/firing
constants remain calibration debt. They should not be promoted as accurate
AoE2 mechanics solely because the aggregate outcome passes.

### 2. HC versus Heavy Scorpion: still outside goal

The current `h1_h3` representative five-seed screen gives:

| Matchup | FINAL tape median | Sim median | Gap | Winner |
|---|---:|---:|---:|---|
| HC vs Heavy Scorpion | -42.12% | -1.92% | 40.19 pp | Correct: Heavy Scorpion |

This is a ranged-versus-siege problem. H1 deliberately excludes siege targets,
while H3 can still alter HC motion. The full five-recording family should be
run at five seeds per recording before choosing a fix.

### 3. HC context-dependent compression: unresolved

The highest-value mechanism experiment is a calibration-only state-gated
same-team ranged collision floor, tested against all FINAL contexts. A
permanent HC radius change is not acceptable. Controlled new recordings should
separate idle, move, formation change, patrol, interact/focus, and melee-contact
states at higher command and position fidelity.

### 4. Full HC matrix: not yet certified under H1+H3

The locked FINAL set contains 50 HC recordings across 13 opponent families.
Only all seven standard melee families and a representative HC–Scorpion screen
have been freshly judged here under the combined arm. Arbalester, Heavy
Cavalry Archer, Elite Skirmisher, Elite Fire Lancer, Siege Onager, and the full
Heavy Scorpion family still require the same five-seed family-level check.

### 5. Revalidate legacy-derived active constants against FINAL

At minimum, remeasure or sensitivity-test:

- `POST_SWING_PLANT_S = 0.7`;
- `FIRE_CYCLE_QUANTUM = 2/3`;
- `RANGED_STOP_OVERHEAD = 0.15`;
- HC post-fire recovery `0.33`;
- `KITE_TANGENTIAL_WEIGHT = 0.8`;
- `KITE_COHESION_WEIGHT = 3.0`;
- `KITE_COHESION_RAMP_TILES = 2.0`;
- TapeBox center bounds `1.2..14.8`; and
- movement smoothing `0.3`.

This is necessary because their old derivations cannot be carried forward as
evidence under the FINAL-only rule.

### 6. Full standard-unit regression and integration: not done

Before any ordinary simulation enables H1 or H3, run the complete 339-recording
standard-unit matrix with five seeds and check for regressions outside HC. H3's
pursuit rule is class-scoped (melee chasing ranged), not matchup-scoped, so it
can affect other ranged units. H1 similarly affects melee chasing any
non-siege ranged unit.

The accepted mechanics remain local calibration/viewer behavior. They have not
been promoted to the ordinary simulation, deployed, pushed, or merged into a
production branch.

## Completion verification

Fresh verification on 2026-08-03:

- locked FINAL HC-versus-melee gate: pass, seven of seven families, 165
  simulations, source SHA-256 matched;
- combined H1+H3 engine suite: 424 tests passed, zero failed;
- FINAL viewer/source/collision checks: 12 tests passed, zero failed; and
- HC–Heavy Scorpion representative screen: correct winner but 40.19-point
  signed HP gap, therefore still outside goal.

No deployment, production mutation, push, or merge was part of this process.

## Recommended closure order

1. Run the combined arm over all 50 FINAL HC recordings, five seeds each.
2. Treat any wrong winner first, then any signed winner-HP gap above 25 points.
3. Investigate the full HC–Heavy Scorpion family before changing Scorpion or HC
   globally.
4. Test a state-gated HC compression mechanism; reject any version that also
   compresses HC in ranged/siege contexts where the FINAL tape does not.
5. Revalidate the high-impact legacy constants and H3 lane fractions with
   controlled measurements and sensitivity sweeps.
6. Run the full 339-recording standard-unit regression before considering
   integration into ordinary simulation behavior.

## References

- `calibration/docs/TAPE_SOURCE_OF_TRUTH.md`
- `calibration/analysis/collision_behavior_diagnostics.md`
- `calibration/viewer/hc_variant_smoke.mjs`
- `calibration/viewer/physics_renderer.js`
- `.worktrees/hc-h3-obstacle/apps/website/static/js/engine/arena.js`
- `.worktrees/hc-h3-obstacle/apps/website/static/js/engine/battle_unit.js`
- `.worktrees/hc-h3-obstacle/apps/website/static/js/engine/constants.js`
- `.worktrees/hc-h3-obstacle/apps/website/static/js/engine/sim.js`
- [Official AoE2:DE Update 81058](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-81058/) — formation pathing, bump retargeting, collision/stutter, and obstruction fixes
- [Official AoE2:DE Update 153015](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-153015/) — pathfinding and group-collision changes, illustrating why these rules are version-sensitive
