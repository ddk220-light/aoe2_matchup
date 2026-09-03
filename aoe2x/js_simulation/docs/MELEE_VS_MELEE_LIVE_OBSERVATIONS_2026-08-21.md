# Melee-vs-Melee Live Observation Log

This document records direct observations from live AoE2:DE gRPC captures.
It is an evidence log only: no simulation rules, calibration targets, or engine
changes are inferred until the observations have been reviewed together.

## Observation 1 — Elite Keshik vs Paladin

- Elite Keshik count: 1
- Paladin count: 1
- Scenario: melee versus melee
- Capture source: CadeRemote gRPC `Frames()` stream
- Raw capture: `calibration/live_observations/keshik_vs_paladin_1v1_2026-08-21/run_001/capture.frames.bin`
- Game version: `180059`
- Scenario setup and commands: scenario was started manually; the captured
  `FrameSequence` stream contained no command messages, so this observation can
  measure the resulting actions but cannot attribute them to a particular
  command packet.

### Capture validation

- Complete frame sequences: 27,288
- Captured game-time span: 30.003 seconds
- Full world snapshots: 1
- Command messages: 0
- Raw stream size: 12,824,482 bytes
- Seed snapshot size: 9,844,393 bytes
- Capture stopped manually after the user reported completion.

### Movement observations

- The Elite Keshik acquired the Paladin at game time `1.265 s` and first changed
  position `4 ms` later. The Paladin acquired the Elite Keshik at `1.328 s` and
  first changed position `1 ms` later.
- Both units went directly from action state 4 (`moving-to-target`) to state 7
  (`attack-animation`) at `2.864 s`. No separate stationary/dwell state appeared
  between pursuit and attack.
- From target acquisition to first attack animation, the Elite Keshik pursued
  for `1.599 s`; the Paladin pursued for `1.536 s`.
- Median observed moving speeds were `1.540013 tiles/s` for the Elite Keshik and
  `1.485119 tiles/s` for the Paladin.
- The Elite Keshik traveled `2.433234 tiles` and the Paladin `2.056881 tiles`
  during the approach. Their total movement (`4.490115 tiles`) accounts for the
  reduction from their initial `5.099020-tile` center separation to their
  `0.608904-tile` attack separation.
- The approach was essentially straight: median heading cosine toward the
  current target was `1.0` for both units, and more than `99.4%` of sampled
  pursuit steps reduced target distance.

### Contact and overlap observations

- The live game DAT reports collision half-sizes/radii of `0.25 tiles` for both
  line records (IDs 1228 and 38), making their combined nominal radius
  `0.50 tiles`.
- Their closest approach occurred exactly when both entered the first attack
  animation, at `2.864 s`. Centers were `0.608904 tiles` apart (`dx=0.119488`,
  `dy=0.597065`).
- On a circular-radius measure, the bodies retained a `0.108904-tile` gap. On
  an axis-aligned half-size measure, the gap was `0.097065 tiles`.
- Neither measure recorded contact or overlap at any point in the fight. The
  two units held the same positions and separation through all subsequent
  attack and recovery cycles.

### Targeting and attack-state observations

- gRPC exposes base-line master IDs 1228 and 38 for these upgraded lines. Their
  initial HP values (`165` and `180`) confirm that the combatants were the Elite
  Keshik and Paladin requested, rather than their unupgraded forms.
- Each unit independently selected the other. The Elite Keshik selected entity
  1763 first; `63 ms` later the Paladin selected entity 1758. Neither retargeted
  while both were alive.
- Target acquisition was followed immediately by pursuit. At the stopping
  distance, both switched from movement to attack in the same recorded
  millisecond; there was no observed pre-engagement dwell.
- The first Paladin hit landed at `3.536 s`, `0.672 s` after its attack animation
  began. The first Elite Keshik hit landed at `3.565 s`, `0.701 s` after its
  attack animation began.
- Subsequent attack-animation starts and damage events repeated every
  approximately `1.901–1.902 s` for both units. Between attacks, each alternated
  from state 7 (`attack-animation`) to state 6 (`recovering/reload`) and back.
- The Paladin dealt eleven full `14 HP` hits plus an `11 HP` final hit, killing
  the Elite Keshik at `24.449 s`. The Elite Keshik landed eleven `10 HP` hits,
  leaving the Paladin at `70/180 HP`.

### Measurements

- Reproducible analyzer:
  `tools/analyze_live_keshik_paladin_1v1.py`
- Saved structured result:
  `calibration/live_observations/keshik_vs_paladin_1v1_2026-08-21/run_001/capture.analysis.json`
- Geometry definition: Euclidean center distance minus the two `0.25-tile`
  radii is the circular body gap; Chebyshev center distance minus `0.50` is also
  retained as the axis-aligned half-size gap.
- Time values are game-simulation time from the gRPC frames, not wall-clock
  capture time.

### Questions raised

- In this 1v1, melee attack eligibility began about `0.10 tiles` before nominal
  body contact. Further runs are needed to determine whether that stopping gap
  is stable across approach angles and other melee unit radii.
- This single run shows no overlap. Low-count tests with different starting
  offsets, plus 2v2 and denser formations, are needed before drawing any general
  conclusion about when moving or attacking allies may overlap.

### Joint conclusions

- The later angle-sweep capture confirms that the `0.608904` center separation
  in this run is best interpreted as an approximately `0.10`-tile per-axis
  approach gap outside the two collision boxes, not as a circular melee range.
- The straight automatic approach remains the cleanest timing observation:
  acquisition immediately becomes pursuit, pursuit immediately becomes the
  attack animation at the stop surface, and no pre-engagement dwell appears.
- This run still says nothing by itself about crowd compression or how allied
  bodies behave. Those questions require multi-unit captures.

## Observation 2 — Manually steered angled re-engagements

- Elite Keshik count: 1, manually controlled by player 1
- Paladin count: 1, automatically pursuing as player 2
- Raw capture:
  `calibration/live_observations/keshik_vs_paladin_1v1_2026-08-21/run_004/capture.frames.bin`
- Structured analysis:
  `calibration/live_observations/keshik_vs_paladin_1v1_2026-08-21/run_004/capture.analysis.json`
- Complete frame sequences: 30,346
- Selected delta frames: 30,345
- Measured game-time span: `0.823–34.690 s`
- Ten Keshik ground-move-to-attack episodes were separated from ordinary
  reload attacks.

### Attack-start geometry by manually initiated episode

Angles use the Keshik-to-Paladin vector, with 0 degrees pointing along positive
world X. `Axis gap` is `max(|dx|, |dy|) - 0.50`; negative values are overlap.

| # | Angle | Attack time | Euclidean centers | Max-axis centers | Axis gap / overlap |
|---:|---:|---:|---:|---:|---:|
| 1 | 187.54° | 11.060 s | 0.603109 | 0.597900 | gap 0.097900 |
| 2 | 276.68° | 13.159 s | 0.598629 | 0.594561 | gap 0.094561 |
| 3 | 344.83° | 15.062 s | 0.620301 | 0.598674 | gap 0.098674 |
| 4 | 47.99° | 16.963 s | 0.708424 | 0.526385 | gap 0.026385 |
| 5 | 172.09° | 18.510 s | 0.486363 | 0.481730 | overlap 0.018270 |
| 6 | 32.86° | 21.332 s | 0.595261 | 0.500000 | contact |
| 7 | 171.53° | 23.620 s | 0.505516 | 0.500000 | contact |
| 8 | 332.68° | 25.916 s | 0.454344 | 0.403649 | overlap 0.096351 |
| 9 | 166.75° | 29.582 s | 0.543326 | 0.528864 | gap 0.028864 |
| 10 | 24.65° | 31.803 s | 0.632381 | 0.574776 | gap 0.074776 |

### Geometry observations

- The first three clean, attack-ready approaches stop with max-axis center
  separation `0.594561–0.598674`, corresponding to an axis gap of
  `0.094561–0.098674 tiles`. This is consistent with a roughly `0.10-tile`
  attack envelope outside the two `0.25-tile` collision half-sizes.
- A fixed Euclidean attack radius does not fit the angled observations. At
  `47.99°`, attack began with centers `0.708424 tiles` apart while the largest
  individual axis separation was only `0.526385`.
- The capture contains exact corner contact at `12.389 s`: `dx=0.500000` and
  `dy=0.500000`, giving Euclidean separation `0.707107`. This supports treating
  the DAT X/Y collision values as axis half-extents rather than one circular
  radius.
- Axis-aligned overlap first appears at `18.196 s`. The maximum axis-aligned
  overlap is `0.119583 tiles` at `25.802 s` while the manually moved Keshik is
  crossing close to the Paladin.
- The minimum Euclidean separation is `0.451437 tiles` at `31.277 s`, a circular
  overlap depth of `0.048563` and axis-aligned overlap depth of `0.056996`.
- Episodes 4 onward are not clean range-threshold probes because the Keshik is
  sometimes still in its reload/recovery cycle or is manually moved through an
  already close position. They demonstrate permitted close movement and overlap,
  but their attack-start distance should not be interpreted as the outer range
  boundary.

### Joint conclusions

- AoE2 world movement should remain Euclidean-normalized, but melee body
  contact must be measured per axis. For two `0.25 x 0.25` collision
  half-extents, the combined body boundary is `0.50` on X and Y; the ordinary
  approach surface observed here is approximately `0.60` on X and Y after the
  measured `0.10` stop tolerance is added.
- Different Euclidean center distances at different approach angles do not by
  themselves mean that the game changes a unit's collision size. They are the
  natural radial distances to different points on an axis-aligned square
  boundary. Side contact is `0.50` tiles center-to-center, while exact corner
  contact is `sqrt(0.50^2 + 0.50^2) = 0.707107` tiles.
- Physical overlap must therefore be recorded as X and Y penetration, with the
  minimum positive penetration representing the shortest separation needed.
  A circular `center distance - radii` value is retained only as a comparison
  metric and must not drive melee collision.
- Episodes 4 onward establish that close movement and transient enemy-body
  overlap can occur. They do not establish an angle-dependent overlap rule,
  because manual orders and reload state confound the outer attack threshold.
- No engine change is justified from the angle sweep alone. The next evidence
  needed is same-unit and low-count multi-unit capture data covering moving,
  stopped, and attacking pairs.

## Observation 3 — Manually steered Elite Keshik vs Battle Elephant

- Elite Keshik count: 1, manually controlled by player 1
- Battle Elephant count: 1, automatically pursuing as player 2
- Raw capture:
  `calibration/live_observations/keshik_vs_elephant_1v1_2026-08-23/run_001/capture.frames.bin`
- Structured analysis:
  `calibration/live_observations/keshik_vs_elephant_1v1_2026-08-23/run_001/capture.analysis.json`
- Reproducible analyzer: `tools/analyze_live_melee_1v1.py`
- Complete frame sequences: 1,986
- Selected duel frames: 1,722
- Measured game-time span: `1.072–30.014 s` (`28.942 s`)
- The manually interrupted stream retained all complete records through
  `30.014 s`, followed by one record header whose `135-byte` payload was not
  written. No kill event is claimed from the incomplete final record.

### Unit identity and distinct size fields

- The captured units expose live base-line master IDs 1228 and 1132. Initial
  HP (`165` and `270`) identify the requested Elite Keshik and Battle Elephant.
- The installed game DAT has SHA-256
  `CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF`,
  matching the DAT provenance of the project unit-mechanics fixtures used for
  the size fields below.
- The elephant is larger in its DAT outline/selection footprint, but not in
  its physical collision or clearance footprint:

| DAT half-extent | Elite Keshik | Battle Elephant | Observed/established role |
|---|---:|---:|---|
| Collision X/Y | 0.25 / 0.25 | 0.25 / 0.25 | Physical obstruction, packing, and body overlap |
| Clearance X/Y | 0.25 / 0.25 | 0.25 / 0.25 | Movement clearance |
| Outline X/Y | 0.40 / 0.40 | 0.50 / 0.50 | Selection/visual footprint and attack eligibility |

- The name “outline” must not be treated as meaning cosmetic-only. Existing
  stationary melee observations establish that attack eligibility is measured
  from the two outline boxes plus attack range and the measured `0.10-tile`
  tolerance. Physical obstruction and ordinary pursuit stopping remain tied to
  collision boxes. This Keshik-versus-elephant run is consistent with that
  distinction, but its manually steered motion does not independently locate
  the outer attack-eligibility boundary.
- For this pair, the outline-based zero-range attack envelope reaches a
  max-axis center separation of `0.40 + 0.50 + 0.10 = 1.00 tiles`. The ordinary
  collision-based approach surface is only
  `0.25 + 0.25 + 0.10 = 0.60 tiles`. A larger elephant outline can therefore
  make it attackable at a greater center separation without making it push
  other units farther away.

### Automatic opening and manual movement

- The units first entered their attack animations at `2.546 s`, with
  `dx=0.000000` and `dy=0.577124`. Their physical collision boxes retained a
  `0.077124-tile` gap, while their larger combined outlines already penetrated
  by `0.322876 tiles`.
- Before that first attack, the Keshik traveled `2.269968 tiles` and the
  elephant `1.164227 tiles`. Afterward, the manually controlled Keshik traveled
  another `16.765018 tiles`, while the elephant traveled only `0.770219 tiles`.
  The later overlap episodes are therefore manual-crossing evidence, not a
  measurement of the clean automatic stopping position.
- Median moving speeds were `1.540003 tiles/s` for the Keshik and
  `0.989985 tiles/s` for the elephant, matching their sourced movement stats.

### Physical collision-box overlap

- Collision-box overlap occurred in four windows:
  `4.106–4.176 s`, `19.700–20.074 s`, `20.110–22.328 s`, and
  `27.020–27.152 s`.
- The windows total `2.794 s`. Overlap was present in 170 of 1,722 selected
  frames (`9.872%`). It was intermittent rather than the units' normal held
  combat posture.
- Maximum physical penetration occurred at `27.086 s`, where
  `dx=0.418118` and `dy=0.406816`. Against the combined `0.50 x 0.50`
  collision extents, the overlap was `0.081882 tiles` on X and
  `0.093184 tiles` on Y. The shortest separation movement was therefore
  `0.081882 tiles`.
- At that instant, the overlapping collision rectangle occupied approximately
  `3.05%` of either unit's `0.50 x 0.50` collision-box area. The shallow-axis
  penetration was `16.38%` of one full collision-box width.

### Outline overlap, kept separate from physical overlap

- Using the sourced `0.40` Keshik and `0.50` elephant outline half-extents,
  outline overlap was present in 1,574 of 1,722 frames (`91.405%`) and spanned
  `26.422 s` across four windows. This is expected because ordinary melee units
  walk well inside the outline attack envelope before their collision-based
  approach stops.
- At the maximum physical-penetration sample, outline overlap was
  `0.481882 tiles` on X and `0.493184 tiles` on Y. The corresponding overlap
  rectangle was approximately `37.13%` of the Keshik outline area and `23.77%`
  of the elephant outline area.
- These larger outline numbers describe overlapping selection/attack
  footprints; they must not be reported as physical collision penetration.
  Literal animated sprite-pixel overlap cannot be recovered from gRPC center
  positions alone, so the DAT outline is only a source-backed visual proxy.

### Questions raised

- A stationary or blocked pair held between `0.60` and `1.00` max-axis center
  separation would isolate the larger outline-based attack envelope for this
  exact matchup without manual movement confounding the result.
- More unit families with unequal collision and outline sizes are needed before
  generalizing how visual size, physical size, and attack eligibility interact.
- This entry records evidence and terminology only. It does not prescribe or
  authorize an engine change.

## Observation 4 - Continuously retargeted 27-unit group movement

- Selected cohort: 27 Elite Keshiks, player 1, live base-line master ID 1228,
  all initially at `165 HP`
- Context unit: one enemy Elite Ghulam, player 2, master ID 1749
- Raw capture:
  `calibration/live_observations/group_movement_20_units_2026-08-23/run_001/capture.frames.bin`
- Structured analysis:
  `calibration/live_observations/group_movement_20_units_2026-08-23/run_001/capture.movement.analysis.json`
- Reproducible analyzer: `tools/analyze_live_group_movement.py`
- The directory name reflects the planned approximately-20-unit test. The
  actual gRPC cohort was 27 units, and all measurements use that observed
  count.

### Capture validation and command stream

- Raw stream SHA-256:
  `2AB471CBA2A4B703CFD06E3393F412A60D8D77B8B835A0E8EFDBE25D6904B198`
- The stream contains 5,538 complete frame sequences and 5,537 complete cohort
  frames spanning `10-92,874 ms` (`92.864 s`). The manually interrupted tail
  consists of one 4-byte record header declaring an unwritten 158-byte payload;
  no partial payload is used.
- gRPC recorded 89 `Move` commands, each naming all 27 Keshiks and marked as a
  human order. It also recorded two `Game` commands and a final `Interact`
  command against entity 1667 at `87.122 s`.
- The isolated ground-movement phase therefore runs from the first move at
  `3.282 s` through the last complete frame before that interaction at
  `87.106 s`, for `83.824 s` and 5,000 sampled frames.
- The user continuously changed the destination. Consecutive move commands
  were a median `745 ms` apart (`332-3,342 ms`), and the clicked locations
  traced `101.935 tiles` in total. This is a continuous steering test, not a
  clean settle-at-one-destination test.

### Group-level response to repeated right-clicks

- The group centroid traveled `100.534 tiles`. Its final position was only
  `4.865 tiles` from its initial position because the clicked path looped back
  repeatedly; net-displacement/path straightness for the complete run was only
  `0.0484`.
- Within each command interval, however, centroid motion was usually close to
  a straight segment toward the current click: median segment straightness was
  `0.9911`. The centroid reduced its distance to the click in 84 of 89 command
  intervals.
- Across individual moving-unit steps, `87.280%` reduced distance to the common
  click, and 86 of 89 commands had a majority of unit steps doing so. The
  median individual step heading cosine toward the click was only `0.7142`,
  with a fifth-percentile value of `-0.5591`. Individual Keshiks therefore
  make substantial sideways and temporarily backwards moves while the cohort
  as a whole follows the requested direction.
- A centroid turn aligned to within cosine `0.8` was observable before the
  next click in 52 of 89 intervals. For those measurable intervals the median
  delay was `16 ms`, one sampled simulation frame. The other 37 intervals were
  retargeted before meeting that threshold, so this capture does not establish
  one universal command-latency value.
- No reliable per-unit slot coordinates appeared in the decoded Action target
  fields. The command packets expose the shared click location, while the
  internal mechanism that chooses local formation trajectories remains an
  inference from the resulting motion.

### Speed modulation within the moving group

- Every unit's median moving speed was effectively its sourced
  `1.54 tiles/s`: per-unit medians ranged only
  `1.539998-1.540006 tiles/s`.
- Instantaneous movement was not fixed at that speed. Relative to the measured
  `1.540003 tiles/s` reference, `52.51%` of usable steps were within the rounded
  `1.00x` band and `20.05%` were in a distinct `0.83x` band. The latter is the
  exact `5/6` tier (`1.28333 tiles/s`) to sampling precision.
- Faster steps form a broad catch-up band: the fifth-to-95th percentile speed
  range was `1.283325-1.774895 tiles/s` (`0.8333x-1.1526x`), with observed
  maxima near `2.309031 tiles/s` (`1.4994x`). The overall mean remained
  `1.538247 tiles/s`, close to base speed, because slowed leaders and faster
  repositioning units balance over time.
- The strong `5/6` plateau, base-speed plateau, and continuous faster band are
  evidence for per-unit formation speed modulation. This run does not reveal
  the exact slot-error thresholds or acceleration formula, so only the observed
  bands should be treated as established.

### Cohesion, compression, and allied pass-through

- At the first move the selected units spanned `6.449 x 6.526 tiles`. During
  the continuously moving phase, median bounds were only
  `2.776 x 2.888 tiles`; the median unit-to-centroid radius was `1.053 tiles`.
  The shape was cohesive but elastic, with 95th-percentile width and height of
  `4.826` and `3.819 tiles`.
- A median 27 of 27 units moved in each sampled frame; even the fifth percentile
  was 22 units. Median per-unit path length was `124.381 tiles`, about 24%
  longer than the centroid path, quantifying the local reordering hidden by
  the smooth group-level trajectory.
- The Keshik collision half-extents are `0.25 x 0.25 tiles`, so two nominal
  allied bodies fill `0.50 x 0.50 tiles`. Applying the sourced
  `minimum_collision_size_multiplier = 0.5` gives a putative shrunken combined
  floor of `0.25 x 0.25 tiles`.
- Across all 351 allied pairs, a median 38 pairs per frame (`10.83%`) were
  inside the nominal combined collision extents, and a median 10 pairs
  (`2.85%`) were even inside the `0.25` shrunken combined extents. This shows
  that group motion does not enforce either size as an inviolable pairwise
  separation on every frame.
- The nearby Ghulam is a genuine confound: it was within two Euclidean tiles of
  some Keshik for `87.72%` of the movement phase, and known swing/reload action
  states occurred in 69 frames. The result survives a conservative spatial
  filter, though. In the 614 frames with every Keshik at least two tiles from
  the Ghulam, median nominal-overlap and below-shrunken-floor counts were still
  35 (`9.97%`) and 7 (`1.99%`) pairs per frame.
- Away from the Ghulam there were no exact same-coordinate stacks, but one pair
  came within `0.00285 tiles` on its larger axis at `26.718 s`, consistent with
  two allied paths crossing through one another. Near the enemy, the maximum
  exact-coordinate pile-up was seven Keshiks at `(6.5, 2.5)` at `59.232 s`;
  that extreme should be classified as enemy-contact congestion rather than
  ordinary open-field formation spacing.

### Evidence boundary and implications to test next

- This run establishes a two-level behavior: the group centroid follows the
  current shared destination smoothly, while individual units use elastic,
  locally indirect trajectories, temporary speed scaling, and substantial
  friendly-body interpenetration to keep the cohort together and reorder it.
- A rigid translated formation, fixed-speed movement, or a hard pairwise
  minimum-collision floor would each contradict this observation. Those are
  evidence constraints for a future engine model, not a complete algorithm.
- The clean next capture is the same repeated-click procedure with no enemy
  unit present, followed by one long single-click move that is allowed to
  settle. Those two controls can separate formation transit, slot assignment,
  arrival behavior, and combat-induced pile-up.

## Observation 5 - Five repeated Champion vs Halberdier fights

Date: 2026-08-28

- Matchup: 23 Spanish Champions (player 2) vs 27 Spanish Halberdiers
  (player 3), using equal unweighted total resource cost and the cheaper side
  capped at 27.
- Golden source:
  `calibration/live_observations/current_melee_golden_2026-08-28/source/meleevsmelee.aoe2scenario`
- Golden SHA-256:
  `31F3BED38CE0512B484124D89D5AA4E97318B3EA55C398BB8DAD27242C769F4E`
- Capture set:
  `calibration/live_observations/spanish_champion_vs_halberdier_5x_2026-08-28/`
- Reproducible gRPC analyzer:
  `tools/analyze_live_melee_group_variance.py`
- Reproducible engine comparator:
  `tools/compare_live_champion_halberdier_5x.mjs`

### Capture validation and outcomes

- Every run began with exactly 23 Champions and 27 Halberdiers on game build
  180059. The generated scenarios all use the literal first 23 and first 27
  authored golden slots respectively; no centroid re-sorting was used.
- All five raw frame streams have distinct SHA-256 hashes. Their hashes,
  generated scenario hashes, raw videos, roster checks, and result summaries
  are recorded in the capture manifest.
- Champions won all five runs. Their surviving counts were
  `21, 21, 23, 22, 23`; surviving HP was
  `1224, 1290, 1244, 1198, 1310`.
- The rich damage decoder found `173, 162, 169, 177, 158` damage events. The
  result variance is therefore real despite identical matchup, position order,
  and trigger setup.

### Initial target acquisition and engagement variance

- First damage was exceptionally stable at `5.696-5.730` raw gRPC game
  seconds (mean `5.7144`). Four runs began with Halberdier slot 24 damaging
  Champion slot 23; one began with Halberdier slot 15 damaging Champion slot
  7. This is a discrete opening branch, not broad timing noise.
- All 50 units acquired an enemy target in every run. Forty of the 50 authored
  starting slots selected the same first target in all five runs; only ten
  varied. Initial targeting is consequently 80% slot-stable.
- Champion targeting was highly concentrated: only 3-4 distinct Halberdier
  slots received all 23 first-target assignments, and 10-11 Champions shared
  the most popular target. There were 12-16 pre-contact target changes.
- Halberdier targeting was even more concentrated: exactly three Champion
  slots received all 27 first-target assignments, and 22-24 Halberdiers shared
  the most popular target. There were 8-21 pre-contact target changes.
- During the first two game seconds after initial damage, only 7-9 damage hits
  occurred and they formed 7-9 distinct attacker-victim pairs. The opening
  engagement graph varies slightly but stays narrow.

### Approach movement and overlap

- The mean per-unit path accumulated before that unit dealt its own first
  damage was `9.3266-11.1214 tiles` for Champions and
  `9.7204-11.6501 tiles` for Halberdiers. These paths are much longer than a
  simple straight approach and capture local reordering and delayed access to
  a target.
- For this comparison, overlap is deliberately a circular collision-radius
  proxy: two units overlap when their centre distance is less than the sum of
  their sourced `0.2-tile` collision radii. It is not a claim about selection
  outlines or literal rendered-sprite overlap.
- Before first damage, a frame contained an average of
  `15.4618-16.3679` overlapping allied pairs. Overlap occurred in
  `80.35%-86.79%` of those frames, with 30-32 simultaneous allied pairs at the
  peak and 42-45 of the 50 units overlapping an ally at least once.
- Maximum allied penetration was `0.3778-0.3965 tiles` against a `0.4-tile`
  combined radius, so some allies were nearly co-located. No cross-team pair
  overlapped before first damage; the first-two-second cross-team peak was
  only 0-1 pairs.

### Current engine comparison

- Direct scenario inspection found the missing opening mechanic: the enabled
  `Starting` trigger gives the full P2 army a PATROL to `(2, 13)` and the full
  P3 army a PATROL to `(13, 2)`. Both cohorts therefore reform and cross their
  own members before ordinary attack pursuit takes over.
- The five decoded unit streams put first movement at `0.814-0.934 s` (median
  `0.842`, mean `0.8502`). By three seconds, per-slot reformation paths already
  produce the observed deep allied overlap. `opening_profile.json` is generated
  reproducibly from those streams and preserves five coherent run variants.
- In the profiled engine, shared PATROL members have zero-obstruction transit.
  When a unit acquires its measured attack target it leaves the move order;
  overlapping pairs inherit an exact monotonically releasing surface, and
  attack-directed allies become path-obstructing DAT bodies. This implements
  the observed distinction between move-order phasing and attack pursuit.
- The engine now produces five distinct state/event-log hashes. Champions win
  all five with `21, 22, 22, 22, 22` survivors and
  `1260, 1240, 1228, 1216, 1204` HP. Mean survivors are `21.8` versus `22.0`
  in-game; mean HP is `1229.6` versus `1253.2`, a `23.6 HP` (`1.9%`) shortfall.
  The prior deterministic engine was `95.2 HP` below the game mean.
- First damage is now `5.600-5.700 s` (mean `5.6633`) versus the game's mean
  `5.7144`. Target distributions match: 3-4 Champion targets with 10-11 maximum
  focus, and exactly three Halberdier targets with 22-24 maximum focus.
- Pre-damage allied overlap now averages `12.3878-14.2878` pairs per frame,
  peaks at 31-33, involves 42-44 units, and penetrates `0.3630-0.3821 tiles`.
  The game ranges are `15.4618-16.3679`, 30-32, 42-45, and
  `0.3778-0.3965 tiles` respectively.
- Remaining differences are localized after acquisition. The engine produces
  9-11 opening engagement pairs versus 7-9, and mean paths before each unit's
  own first damage remain only `6.4086-7.0192` Champion tiles and
  `7.1939-7.6758` Halberdier tiles. Full simulated fights end in
  `28.75-32.75 s`, so post-contact traffic is still too efficient.

### Implication for engine variance

- The evidence does not support unconstrained random noise. The implementation
  uses the five real openings as deterministic variants, preserving correlated
  position, timing, and target choices within each run instead of independently
  sampling marginals into combinations that never occurred.
- The current gRPC command stream shows the first `AiOrder` at
  `5.966-6.012 s` (mean `5.984`), but its decoded command rows do not yet expose
  enough recipient/designation semantics. The older generic distinct-target
  sweep is disabled for this profile because it immediately disperses the
  measured focus and worsens HP. This is an explicit evidence boundary, not a
  claim that the game issues no AI orders.
- Next work should decode those current AI orders and model the post-contact
  access queue. Preserve the now-matched first-contact timing, target
  concentration, and overlap envelope; improve the 9-11 versus 7-9 opening
  engagement gap and the remaining `23.6 HP` mean error without modifying
  sourced damage or HP values.

## Observation 6 - Five repeated Champion vs Paladin fights

Date: 2026-08-28

- Matchup: 27 Spanish Champions (player 2) vs 16 Spanish Paladins
  (player 3). Both sides cost 2160 under the unweighted resource rule:
  `27 * 80 = 16 * 135`.
- The same verified current melee golden source was used, with SHA-256
  `31F3BED38CE0512B484124D89D5AA4E97318B3EA55C398BB8DAD27242C769F4E`.
  Units occupy the literal first 27 and first 16 authored slots.
- Capture set:
  `calibration/live_observations/spanish_champion_vs_paladin_5x_2026-08-28/`
- Detailed comparison: `GAME_VS_ENGINE_REPORT.md` inside that capture set.

### Game result and variance

- Paladins won all five runs with `9, 5, 10, 12, 11` survivors and
  `1373, 549, 1072, 1432, 1486` HP. Mean survivors were `9.4`; mean HP was
  `1182.4`. The broad endpoint band is real despite identical authored slots.
- Raw gRPC game-clock elimination times were
  `40.992, 46.726, 36.530, 35.774, 34.398 s` (mean `38.884`). Video-relative
  elimination times are lower and are not used for engine-clock comparisons.
- Every raw stream has a distinct SHA-256 hash.

### Targeting, contact, and overlap

- First damage occurs at `5.012-5.038 s` (mean `5.0236`) and is identical in
  topology: Paladin slot 1 deals 14 to Champion slot 5 in all five runs.
- Every Champion initially targets Paladin slot 1. Paladins distribute their
  first targets over 3-4 Champion slots, with 5-7 Paladins sharing the most
  popular target. Thirty-eight of 43 authored slots keep the same first target
  across all five runs (`88.37%`).
- Only 3-4 unique attacker-victim pairs exchange damage during the first two
  seconds after first damage. The game therefore combines extreme Champion
  focus with a very narrow initial contact front.
- Before damage, peak allied-overlap pairs are `37, 34, 29, 31, 32` (mean
  `32.6`). Maximum penetration is approximately `0.44-0.49 tiles` using
  sourced collision radii of `0.20` for Champions and `0.25` for Paladins.
  No cross-team overlap occurs before damage.

### Engine model and comparison

- The generated opening profile preserves two position samples for every
  authored slot: a 3-second compression waypoint and a 4.5-second contact
  waypoint. First-target assignments and timings remain correlated within
  each of the five real runs.
- Target assignment no longer discards the measured PATROL trajectory. A unit
  can hold its attack target while finishing the measured move-order path;
  profiled movement divides remaining displacement over remaining profile
  ticks. This is scoped to observed profiles and does not change DAT speeds for
  ordinary fights.
- Paladins win all five engine variants with `11, 12, 10, 7, 10` survivors and
  `1200, 1575, 1254, 987, 1306` HP. Mean survivors are `10.0` versus `9.4`
  in-game; mean HP is `1264.4` versus `1182.4`, an `82 HP` (`6.9%`) excess.
- Engine first damage is `5.1833 s`, with the correct Paladin slot 1,
  Champion slot 5, and 14 damage. Target fan-out matches the five game runs
  exactly. Pre-damage allied-overlap peaks are 28-33 (mean `31.0`) versus the
  game's 29-37 (mean `32.6`).
- Engine eliminations average `42.800 s`, `3.916 s` later than the game. The
  engine creates 5-6 opening engagement pairs versus the game's 3-4. That
  remaining excess contact width, rather than sourced combat stats, is the
  next mechanism to investigate.

## Observation 7 - Five repeated Paladin vs Elite Battle Elephant fights

Date: 2026-08-28

- Matchup: 27 Spanish Paladins (player 2) vs 21 Burmese Elite Battle
  Elephants (player 3), using the current melee golden's literal first-N slots.
- The unweighted purchase is 3645 resources versus 3570. Exact parity is
  impossible with whole units under the 27-unit cap; the floored difference is
  75 resources (`2.06%`).
- The source SHA-256 remains
  `31F3BED38CE0512B484124D89D5AA4E97318B3EA55C398BB8DAD27242C769F4E`.
- Capture set:
  `calibration/live_observations/spanish_paladin_vs_burmese_elephant_5x_2026-08-28/`
- Detailed comparison: `GAME_VS_ENGINE_REPORT.md` inside that capture set.

### Game outcome and variance

- Burmese Elite Battle Elephants won all five runs with `13, 11, 10, 11, 14`
  survivors and `2924, 3076, 2492, 2536, 2692` HP. Mean survivors were `11.8`
  and mean HP was `2744.0`.
- Raw gRPC elimination times were
  `77.984, 82.280, 81.350, 86.908, 78.398 s` (mean `81.384`). Each frame
  archive has a distinct SHA-256 hash.

### Targeting, overlap, and trample contact

- The first decoded HP loss is consistently Elephant slot 18 into Paladin slot
  4 at `5.304-5.512 s`. Four runs expose the combined 13 direct plus 3.25
  trample decrement (`16.25`); one exposes the `3.25` trample component first.
- Paladins acquire exactly three initial Elephant targets in every run, with
  17-20 units sharing the most popular. Elephants acquire only 1-2 initial
  Paladin targets, with 20-21 sharing the most popular. First targets are
  stable for 38 of 48 slots (`79.17%`).
- Pre-damage allied-overlap peaks at exactly 26 pairs in all five runs.
  Penetration reaches `0.4851-0.4967 tiles` against a combined physical radius
  of `0.50`. Both units have a `0.25` collision radius; the Elephant's `0.50`
  outline remains selection-only evidence.
- The first two seconds contain only 7-9 unique engagement pairs despite the
  extreme target concentration.

### Engine comparison and rejected transition

- The active five opening variants preserve measured movement start, 3-second
  compression, 4.5-second approach, and first-target vectors. The engine
  reproduces all five first-target fan-out distributions exactly and peaks at
  24-28 allied-overlap pairs (mean 27 versus the game's 26).
- Elephants win all five engine variants with `12, 11, 10, 14, 10` survivors
  and `2976, 2692, 2372, 3196, 2144` HP. Mean survivors are `11.4` versus
  `11.8`; mean HP is `2676` versus `2744`, a `68 HP` (`2.5%`) shortfall.
- Simulated eliminations average `76.137 s`, `5.247 s` faster than the game.
  First damage averages `5.223 s`, `0.147 s` early. The simulated opening has
  14-20 engagement pairs (mean 16.4) versus the game's 7-9 (mean 8.2).
- The forensic decoder now also records the last enemy target before first
  damage. Most Elephants switch from initial Paladin slot 26 to slots 4 or 5,
  and 11-14 Paladins switch among Elephant slots 1, 15, and 18.
- Applying those switches without an access-queue model was rejected: it moved
  mean Elephant HP to 346 above the game and duration to 12.5 seconds short.
  The transition is retained as evidence but is not executable. Target choice
  and physical access must be implemented together.
