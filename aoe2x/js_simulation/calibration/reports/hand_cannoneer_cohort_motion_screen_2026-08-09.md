# Hand Cannoneer cohort contact-motion five-sample screen

- Decision: **REJECT before 100-sample acceptance run**
- Source SHA-256: `38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D`
- Seed: `20260411`
- Starts: exact canonical starts imported from each row's first authorized `frames.bin` run
- Candidate: explicit calibration-only `cohortMotion: "contact_heading"`
- Samples: five for each of the eight HC-versus-melee rows
- Timeouts: zero
- HCA-vs-Champion identity control: five of five scores, final-state hashes, and event-log hashes identical
- Product profile: candidate disabled

Negative scores are Hand Cannoneer wins (owner 2); positive scores are melee-side wins (owner 3).

| Matchup | Tape mean / band | Baseline mean | Cohort mean | Baseline band error | Cohort band error | Mean blocked events: baseline -> cohort |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Hand Cannoneer vs Halberdier | -76.500 / -76.500…-76.500 | -89.500 | -75.600 | 13.000 | 0.900 | 12,435.0 -> 6,993.4 |
| Hand Cannoneer vs Hussar | 5.626 / -18.750…17.895 | 59.374 | 68.797 | 41.479 | 50.902 | 17,888.0 -> 8,838.4 |
| Hand Cannoneer vs Champion | -76.607 / -82.500…-73.214 | -86.357 | -58.786 | 3.857 | 14.429 | 13,844.4 -> 9,346.4 |
| Hand Cannoneer vs Elite Fire Lancer | -60.921 / -60.921…-60.921 | -68.658 | -64.605 | 7.737 | 3.684 | 12,196.8 -> 7,652.8 |
| Hand Cannoneer vs Heavy Camel Rider | -67.520 / -73.571…-61.310 | -57.548 | -51.738 | 3.762 | 9.571 | 21,769.0 -> 7,900.0 |
| Hand Cannoneer vs Paladin | 15.444 / -9.048…32.143 | 47.520 | 51.587 | 15.377 | 19.444 | 24,891.4 -> 7,953.0 |
| Hand Cannoneer vs Elite Battle Elephant | 2.384 / -38.333…32.292 | 77.526 | 76.958 | 45.234 | 44.667 | 22,080.4 -> 9,415.4 |
| Hand Cannoneer vs Elite Steppe Lancer | 8.026 / 8.026…8.026 | 63.395 | 56.895 | 55.368 | 48.868 | 13,466.0 -> 9,259.0 |

## Gate result

- Aggregate eight-row tape-band error: **185.816 baseline -> 192.466 cohort** (**6.650 worse**).
- Stable winners: no flips.
- Timeouts: none.
- Baseline-good-row regression: **Champion regressed 10.571 points**, exceeding the approved 10-point limit.
- Candidate rows still more than 25 points outside the tape band: Hussar (50.902), Elite Battle Elephant (44.667), Elite Steppe Lancer (48.868).
- The candidate therefore fails both aggregate improvement and the good-row regression gate. The approved plan stops before the 100-sample run.

## Root-cause finding

The cohort planner materially reduced blocked events in every row (about 31-68%) but did not improve aggregate outcomes. It therefore solved its immediate collision objective while exposing the next upstream mismatch: the synthetic ring waypoint and absolute slot trajectory do not preserve the tape's attack opportunities when the formation is allowed to execute them freely.

Sample 0 illustrates the separation:

| Matchup | Baseline ticks / blocked / damage events | Cohort ticks / blocked / damage events | Baseline score -> cohort score |
| --- | --- | --- | ---: |
| Halberdier | 1,950 / 12,849 / 69 | 1,993 / 7,458 / 85 | -91.000 -> -67.500 |
| Hussar | 2,305 / 17,658 / 163 | 2,434 / 11,735 / 152 | 62.256 -> 67.845 |
| Champion | 1,941 / 14,711 / 91 | 2,661 / 10,644 / 109 | -90.000 -> -47.500 |
| Fire Lancer | 1,701 / 11,710 / 163 | 1,752 / 7,104 / 168 | -68.158 -> -61.316 |
| Heavy Camel | 2,918 / 21,001 / 261 | 3,626 / 7,497 / 273 | -56.786 -> -46.310 |
| Paladin | 3,455 / 23,151 / 193 | 2,786 / 7,151 / 188 | 54.563 -> 54.960 |
| Battle Elephant | 3,940 / 27,341 / 242 | 2,784 / 10,171 / 189 | 72.083 -> 79.271 |
| Steppe Lancer | 1,526 / 13,460 / 158 | 1,754 / 8,584 / 168 | 62.684 -> 57.658 |

`damage events` counts both sides and is diagnostic context, not a damage-share conclusion. A follow-up needs owner/volley-participation attribution plus tape-vs-sim centroid and slot trajectories before changing movement again.

## Reproduction command

From `aoe2x/js_simulation`, run the eight canonical HC rows through `runTapeConditioned(root, row, sampleIndex, 20260411, { cohortMotion: "contact_heading" })` for sample indices 0-4. The exact harness behavior is covered by `tests/standard-units-comparison.test.mjs`.
