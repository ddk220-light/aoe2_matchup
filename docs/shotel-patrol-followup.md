# Shotel patrol investigation — 2026-09-07

The Shotel winner mismatch remains open. One generic melee recovery defect is repaired; a separate, substantial missing behavior is the patrol formation transition. No Shotel speed, damage, armor, reload, or windup was changed.

## Confirmed recovery defect

When another attacker kills its target, a melee bystander abandons its attack animation on the following update, including after its own damage has released. The actual killer normally retains its recovery animation. V3 previously retained both animations after release.

Recorded examples at game time 12.674 seconds:

| Shotel | Swing began | Target died | Leaves animation after death | Interpretation |
|---|---:|---:|---:|---|
| 2141 | 11.420 | 12.674 | 0.014 s | Released bystander; cancels remaining recovery |
| 2149 | 11.652 | 12.674 | 0.014 s | Released bystander; cancels remaining recovery |
| 2164 | 11.918 | 12.674 | 0.746 s | Probable killer; completes recovery |

Killer attribution here is inferred from target, animation entry, and the sourced 0.750-second delay; this recording has no EntityKilled events. Other bystanders show the same next-sample departure. These observations support distinguishing the actual killer from other attackers, rather than shortening every melee attack animation.

`world.js` now records the killer at the engine's lethal-damage boundary. A released ordinary melee bystander may cancel recovery but still owes its weapon reload. An unreleased swing retains the existing refund. Projectile and charge handling retain their existing rules. The regression exercises both released and unreleased bystanders and checks that the killer retains its backswing.

## Why the larger mismatch remains

The archived game uses one non-looping Starting trigger with Patrol effects for both armies. Both combat players have the empty NoneAi script. Repeated target switches are not explained by a repeating scenario trigger or a strategic AI attack script.

The game reforms the armies into columns before contact. V3's opening patrol sends the original broad placement toward its destination without this regrouping phase. This difference is visible at three seconds, before any damage. It changes the contact surface and the units exposed to early attacks.

This is an actual game rule, not an inferred Shotel-specific exception: [World's Edge update 107882](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-107882/) explicitly documents Patrol forming a column regardless of distance. The precise slot assignment, moving formation anchor, and release into individual combat still require validation before a production implementation. A speculative slot arrangement could reproduce a winner while representing the wrong movement.

The immutable trace contains 138 changes between living targets. Some occur in groups, and some abandon nearby targets for farther ones. These cannot all be represented by nearest-body contact capture. They must be distinguished from deaths and ordinary contact retargeting when validating the formation transition.

Measured median moving speeds are 1.485 tiles/s for Tiger and 1.320 for Shotel, matching their sourced profiles. Shotel has some faster formation movement samples; that does not justify changing its base speed. Installed DAT movement fields also give both units zero rotation time and effectively unlimited yaw, so a speculative Shotel turning delay is unsupported.

The game permits more than four Shotels to be in attack animation on the same target. Removing V3's engagement-capacity gate was tested as an isolated diagnostic, but did not resolve the winner and was not promoted. Animation occupancy is also not sufficient by itself to establish simultaneous legal attack slots.

## Outcome check

| Run | Winner | Winner HP | Duration |
|---|---|---:|---:|
| Recorded | Shotel | 474 | 34.242 s to Tiger elimination |
| Previous campaign seed 1 | Tiger | 25 | 54.300 s |
| Recovery correction, seed 1 | Tiger | 150 | 42.033 s |
| Diagnostic only: unlimited engagement capacity | Tiger | 131 | 41.433 s |

The recovery correction does **not** improve aggregate HP agreement: signed HP delta increases from +36.26 to +42.01 percentage points. It is retained for the local behavior demonstrated by the recording, not selected to fit the winner. These are individual deterministic runs, not an estimate of live outcome variance. No claim of a complete Shotel repair is warranted.

## Trace integrity and validation

The earlier diagnostic retained mutable action dictionaries. Later patches could overwrite earlier target histories. Position and HP scalars were already copied. The Rust schema parser also missed raw identifiers such as `r#type`.

The production decoder now accepts `decode(run, include_combat=True)` and creates detached action/animation snapshots. The schema parser recognizes Rust raw identifiers. Two Python regressions verify scalar field typing and snapshot immutability. Existing overlay decoding keeps its default compact output.

The Ghulam attribution audit was regenerated using immutable snapshots: 345 candidates, 344 agreements, one ambiguous event. Excluding the whole ambiguous event leaves 340 passing recipient checks, including 14 positives. The earlier mutable-target counts are superseded; the blast implementation itself was unchanged.

Validation: 40 focused engine tests and two Python tests pass. A broader 71-test selection has 56 passes and 15 failures; a control run with only this turn's recovery changes removed has the same 15 failing test names. These older timing/target-state failures remain and are not represented as a green full suite.

Local evidence is under `aoe2x/js_simulation/calibration/lab/analysis/shotel-retarget/`. The current seed is `after-bystander/seed_001.json`; raw recordings and original campaign results are preserved. Exploratory helpers in `.tools` are not production movement models.
