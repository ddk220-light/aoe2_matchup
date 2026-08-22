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
