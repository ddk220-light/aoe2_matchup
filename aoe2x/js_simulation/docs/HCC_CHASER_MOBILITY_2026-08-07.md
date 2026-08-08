# HCA vs Champion 12v21 — chaser mobility forensics (2026-08-07)

The standard-units corpus's one genuine measured-cause wrong winner
(`STANDARD_UNITS_SUMMARY_2026-08-07.md`: tape −36.5 over 14 repeats, sim +24.5,
champions winning 22/25 sampled orders) is root-caused here from the full-rate
`frames.bin` decode of all 14 recordings, and a scoped candidate rule is landed
behind `AOE2X_EXP_STEP=chaser` (default OFF). The rule fixes this matchup
dead-on and leaves every non-kited fight bit-identical, but it moves the
calibrated kited columns — whose constants were fitted on the defective
mobility — so landing it as default requires a recalibration round, not a
flag flip. Numbers below.

## Evidence source

`aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip` — the raw-`frames.bin` build of the
locked FINAL corpus. Identity to the authority was verified before use: the
decoded streams for the fights used here are byte-identical (SHA-256) to
`aoe2_golden_STANDARD_UNITS_FINAL.zip`, whose own hash was verified against
`calibration/source/source_of_truth.json` first. Decoder:
`tools/decode_tape_frames.py` (~59.9 Hz per-unit position + Action state/target).

Both sides of every comparison go through the same two metric scripts
(mirrored-measurement rule): full-rate speed histograms, swing starts
(Action.state 7 rising edge / windup+swing timers), Chebyshev contact, kiter
duty cycle, ball revolutions about map centre.

## What the tape shows (14 recordings, 12 HCA vs 21 Champion)

HCA win 13/14. The kiting layer itself is NOT the story — the sim's ball laps
the ring at the tape's own cadence:

| metric | tape (median over repeats) | sim (6 sampled orders) |
|---|---|---|
| HCA duty cycle | 0.26 (0.23–0.30) | 0.19–0.28 |
| ball revolutions per fight | ~1.0 | 0.5–2.5 |
| champion speed stopped/partial/full % | 27 / **0.7** / 72 | 47–57 / **7.5–15.4** / 34–41 |
| champion → nearest-HCA gap p50 | **1.42–2.06 tiles** | **0.67–0.81** |
| champion contact (≤0.5 cheb) % of frames | **3.1–6.2** | **23–31** |
| kiter exposure (champ ≤1.0) | 23–49% | 72–82% |
| contact-window mean length | **0.42–0.69 s** | **1.49–3.16 s** |
| champion swings per fight | 32–95, tracks duration | ~90–96 regardless |
| swings per contact-second | 1.7–2.6 | 0.36–0.65 |

Genie chaser movement is bimodal (the camel histogram again, now confirmed on
champions): stopped or full speed, 0.6–0.8% in between. The sim's constraint
solver (`constrainPair` → `distributeEqualMassRemoval`) manufactures a
partial-speed grinding population that keeps a chaser glued to the ball
surface: median gap 0.75 vs the tape's 1.6, six-times the contact, windows of
seconds instead of a touch. Tape contact is a brief catch → swing → release;
sim contact is standing pressure. At 12 shooters vs 21 chasers that pressure
decides the fight, so the winner inverts.

Why this matchup and not the neighbours: HCA vs Champion is the corpus's one
kite pairing with both a decisive speed gap (1.54 vs 1.06) and a low-damage
chaser, so the catch rate is the whole outcome. Against Paladin/Hussar/Camel/
Steppe the chaser is fast enough that standing pressure is *correct*-ish, and
against Halberdier the +32 cavalry bonus wins regardless.

The sim construction used for all of this (tape reference ids, tape spawns,
measured hcc kiteProfile, chaseCapture OFF, 25→6 sampled acquisition orders)
reproduces the committed sweep's inversion: 5/6 champion wins at baseline.

## Candidate rules, all measured (sum band error / wrong winners over the
## 192-recorded-ratio corpus scoreboard; baseline = 442.9 / 2)

| rule | corpus | hcc 12v21 (6 orders) | verdict |
|---|---|---|---|
| `AOE2X_EXP_STEP=bimodal` (blanket) | 924.8 / 5 | 6/6 HCA, mean −37.5 | melee ratios flip; kite block strands |
| `AOE2X_EXP_STEP=steer` (blanket) | 666.7 / 4 + 1 timeout | 6/6 HCA, −33.8 | kac collapses, kiter side escapes forever |
| `chaser` as stop-only | 911.3 / 6 | 6/6 HCA, −61.0 | fast chasers that SHOULD catch stop dead (esc/hcp die) |
| **`chaser` = steer-then-stop (landed)** | **592.6 / 3** | **6/6 HCA, −42.7 (tape −36.5)** | best; kac 5v10 flips, see below |
| `chaser` + enemy-only steer | 650.9 / 5 | 5/6 HCA | ally-block steering matters for crowded catches |

The landed `chaser` mode: in a kited world (`world.kiteState` present), the
chasing side's blocked steps first search a nearby clear full-speed heading
(the camel tape's route-around-at-full-speed), and a step that still cannot
run clean is cancelled to a stop (the bimodal histogram). The kiting side and
every non-kited scenario keep the baseline solver — verified bit-identical:
0 of 131 non-kited ratios moved, and the default-config corpus and test suite
are unchanged with the flag off.

## Why this cannot land as default yet

The kited columns were calibrated ON the grinding engine, and their
per-scenario constants compensate for it — explicitly so for contact capture
(`CONTACT_CAPTURE_2026-08-07.md` records kac/hcc OFF "until block-escape
pathing improves"; this flag IS the block-escape pathing improving) and for
the dwell/beat models fitted per column. Under `chaser` the seesaw moves:
esc columns improve (20v15 12.4→1.9, 10v5 10.3→0), kac regresses
(5v10 flips winner, 20v20 0→40 err), hcp/avp shuffle by single digits.

So the recorded order of operations from the camel work still stands, now one
step further along:

1. ~~fix chaser mobility~~ — this flag;
2. re-measure engulfment + contact rates per column under `chaser`;
3. re-derive the per-scenario `chaseCapture` settings (the kac/hcc OFFs exist
   only because of the grinding) and re-land min-range suppression, whose
   cost scales with exposure (45.7% → measured anew under `chaser`);
4. re-verify the kiting corpus + svc/svp, then pin `chaser` into
   `engine-config.js` and re-sweep the standard-units archive.

Until that round runs, the committed default stays grinding, and the
standard-units summary's HCA-vs-Champion row stays a known wrong winner with
its cause measured and its fix staged.

## Reproducing

Scratch tooling for this round (tape decode → mirrored metrics → corpus A/B)
is session-scratchpad only by design; the decode path and both metric
definitions are fully specified above and in `tools/decode_tape_frames.py`.
The corpus scoreboard is one deterministic playback per recorded ratio via
`src/matchup-playback.js`, signed winner-HP% against the tape runs' min–max
band, wrong winner = sim winner absent from every tape repeat.
