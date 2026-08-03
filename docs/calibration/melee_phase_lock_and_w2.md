# Melee phase-lock — analysis, W2 build, and the fragmentation proposal (2026-08-02)

Self-contained pick-up doc for the next round of the champion-vs-melee gap
work. Reads after `docs/calibration/HANDOFF_2026-08-02.md` and
`docs/calibration/w1_scrum_walk_champion_round.md` (W1 build + gates).
Everything below is measured on the STANDARD_UNITS champion subset
(63 fights; ingest and run-id mapping in `.scratch/standard_units/`).

**Tree state:** W1 and W2 are implemented, flag-gated, default OFF,
UNCOMMITTED (as is the whole champion ingest). JS suite **397/397**.

## 1. The outcome gap (champion vs melee, W1-on board)

Losing melee side lands ~15–25% fewer swings than the tape before dying, so
the winner keeps too much HP (winner-side hp_remaining outside 90–110% of
tape on 19 champion-melee fights: elephant ×7, paladin ×7, hussar ×2,
steppe ×2, halberdier ×1).

Per-fight loser offence, tape vs sim (W1 on): hussar_r3 143 vs 112 swings,
halberdier 51 vs 38, champion-vs-elephant_r5 1932 vs 1504 damage,
paladin (r3 tape win) 1470 vs 1246.

## 2. The measured chain (each step verified; scripts in `.scratch/standard_units/`)

1. **Synchronized kill clusters.** Sim loser deaths cluster on one tick
   (5–7 adjacent pairs ≤0.25 s apart per fight; tape 1–4). Each clustered
   death costs the loser 2–4 unspent swings ≈ the whole 15–25% shortfall.
2. **Phase lock.** Per-side swing-phase histograms (t mod reload, 8 bins):
   tape ~uniform; sim up to 46–53% in ONE bin.
3. **Degenerate timing.** Sim same-victim swing intervals: med = p90 =
   2.017 s (reload+1 tick; 3–7 distinct values). Tape: same median, but a
   continuous right tail (25–34 distinct values, max 3.0–4.75).
4. **Tape slips are excursion-linked but rare.** Joining intervals to
   10 Hz positions: tape intervals >reload+0.15 s are only 10–12 of ~150,
   100% with an out-of-reach excursion inside; most excursions cost nothing
   (slip/excursion ratio 0.5–0.65 when both occur). So same-victim
   interval variance is NOT the desync driver.
5. **The desync driver is re-engagement.** Tape kill→first-hit-on-next-
   victim: med 2.03–2.48, p90 3.2–9.0, max 30, CONTINUOUS (34–56 distinct
   values). Sim (W1): med 2.017 (exactly one reload), p90 5.1–7.7, body
   degenerate. The sim killer's next victim is always already adjacent
   (ring stays packed; paladin-free-late 0.9% flag-off, 18% with W1, vs
   tape 9.5–40%); the tape killer WALKS.
6. **Opening sync is the phase lock's origin.** Sim: all units move at
   0.12 s, first damage 0.533 s (tick 32, six champions landing
   simultaneously; impossible — min spawn separation 2.0 tiles). Tape:
   first move 1.2–2.0 s (min 1.2–1.4, med 1.4–1.8, p90 1.8–2.0, ~66–75
   units/fight, 6 fights, BOTH melee templates incl. pal-steppe v3),
   first damage 2.42–2.64 s staggered.
7. **Contact distances are right.** Sim hit distance med 0.60–0.61 ==
   tape med 0.60–0.62 (E11 radii exonerated); tape has a p90 0.73 tail
   (cavalry windups + 10 Hz lag), sim tight (p90 0.63).

## 3. W2 reaction window (BUILT this round; flag-gated, default OFF)

Mechanism: in an all-melee fight each unit stands (no acquisition, no
movement, no swing) until a deterministic per-unit slot:

```
reactionUntil = W2_REACTION_MIN_S (1.2)
              + slot/(N-1) · (W2_REACTION_MAX_S − MIN) (0.8)
```

slot = index in team array, N = team size. Even spacing across the
measured tape window; NO rng (melee stays deterministic). Endpoints are
the measured tape breakpoints, documented at the constant
(`apps/website/static/js/engine/constants.js`, `W2`; predicate +
update() hold branch in `battle_unit.js` `w2ReactionHold()`; `--w2
reactionWindow` plumbed through calib_runner/worker and
melee_engagement_probe; tests `tests/js/engine/w2_reaction_window.test.mjs`,
suite 397/397). Byte-identity proven: `--w2 off` == defaults on melee +
ranged samples; `--w2 reactionWindow` byte-identical on ranged/siege
(scope is all-melee fights only).

## 4. W1+W2 results (54 champion-melee fights, `simruns_champ_0802_w1w2`)

Winners 50/54. Per-fight winner HP vs tape (selected):

| fight | tape | OFF | W1 | W1+W2 |
|---|---|---|---|---|
| paladin__vs__champion | champ 14 | champ 224 | pal 137 | **champ 28** ✓ |
| elite_steppe__vs__champion | champ 546 | 727 | 620 | **594** ✓ (in band) |
| halberdier__vs__champion | champ 740 | 714 ✓ | 822 | **794** ✓ |
| heavy_camel__vs__champion | champ 959 | 1085 | 1022 | **1008** ✓ |
| hussar__vs__champion | champ 588 | 735 | 686 | **168** ✗ overshot |
| champion__vs__paladin_r14-16 | champ 518/462/280 | 630 | 378 | **126** ✗ |
| champion__vs__elite_elephant_r5 | eleph 628 | 976 | 1056 | **1164** ✗ worse |
| paladin__vs__champion_r3/r4 | pal 343/37 | champ 224 | pal 137 | champ 28 (flip) |

### The two W2 anomalies (measured, not guessed)

- **Overshoot in asymmetric fights** (hussar, paladin-r14): the even
  0.8 s slot spacing turns arrival into a conveyor belt of serial duels.
  Hussar offence went 784 (OFF) → 1302 (W1W2) vs tape 1001; fight
  stretched to 49 s vs tape 39.9. Tape arrivals are BURSTY (0.6 s spread
  then a wall clash with texture), not a uniform stream.
- **Elephant unaffected/worse**: champion deaths STILL cluster 5-at-a-tick
  (10.3 s) — elephant trample + cadence re-lock dominate the opening
  stagger; champion offence 1396 vs tape 1932.
- First-swing median is still late (sim 10.5–11.2 vs tape 4.6–7.2): back
  ranks queue behind the front instead of engaging — NOT solved by W1
  drift or W2 stagger.

## 5. The remaining core defect: mid-fight ring re-densification

Both residual anomalies reduce to one thing: **the tape's scrum never
re-densifies after a kill; ours refills the ring instantly.** The sim
killer's next victim is adjacent ~100% of the time (swing at the next
expiry tick, constant 2.017 s); the tape killer typically walks
(continuous 2.03–9.0 s) because its next victim is NOT in reach — the
tape keeps 1–3 attackers per victim late (sim 2–5), and its dead victim's
ring slot stays empty while a reinforcement walks over. This is what
keeps the tape's phases decorrelated, its kills staggered, its losers
alive to spend their swings — and (for elephant) what lets more than 4–5
champions be chewing on elephants at once (tape engages 6–7 concurrently
vs sim 4–5).

## 6. Proposal — next measurement round (before ANY further building)

Produce the post-kill **ring-slot refill forensics**, tape vs sim
(W1+W2 on), on `paladin__vs__champion`, `hussar__vs__champion_r3`,
`champion__vs__elite_elephant_r5`, `champion__vs__paladin_r14`
(probe positions already exist: `D:/AI/aoe2_golden/simruns_champ_0802_probe_w1`
— regenerate with `--w1 scrumWalk --w2 reactionWindow`):

1. At each melee kill: the dead victim's adjacent cells — how long does
   each stay empty of ENEMY attackers, and who fills it (a walking
   reinforcement vs an already-adjacent body rotating in)?
2. Killers' next-victim distance at kill tick (tape vs sim): the
   distribution behind re-engage med 2.03–2.48 vs 2.017.
3. Arrival shape at the opening: per-unit first-contact times, tape vs
   W2 sim — quantify "bursty vs conveyor" (decides W2's slot
   distribution: keep even spacing, or re-derive from the tape's actual
   first-contact CDF).
4. Elephant: attackers-per-elephant over time (tape 6–7 vs sim 4–5) and
   WHERE the extra tape attackers stand (ring capacity vs approach
   queueing).

Then design the mechanism from whichever real behavior the refill
forensics indict — candidates, all physical, none fitted: attacker
overshoot/slide past contact on collision, reinforcements queuing behind
the front rank (a real blocking rule), or the 81058 bump-retarget valve
firing on ring saturation rather than only on hard stuck.

### Constraints (user, standing)

- NO fitted stochastic constants; mechanisms from real physics/dat or
  measured tape breakpoints documented at the constant.
- Do not "improve the physics" cosmetically or add factors to force-fit
  the scoreboard. The W2 slot endpoints (1.2/2.0 s) are the model of a
  measured breakpoint; anything further needs its own measurement first.
- W1/W2 stay default-OFF until a full-corpus gate; every new flag gets
  the same byte-identity proofs (`--wX off` == defaults; scoped-out
  families byte-identical with ON).

### Decision points for the main session

- Keep W2's even slots, reshape them from the arrival CDF (measurement
  6.3), or park W2 if the fragmentation mechanism makes it redundant.
- Whether paladin__vs__champion_r3/r4 (tape paladin upsets, now champion
  again under W1+W2) is recoverable without breaking the base fight's
  new-found exactness (28 vs 14).

## 7. Elephant trample and body geometry correction (2026-08-02 continuation)

The authoritative STANDARD_UNITS Champion→Elite Battle Elephant tapes (`r3`–`r9`)
were remeasured before changing the engine. The old implementation was physically
wrong in two ways:

1. It floored fractional trample damage, producing `3` from a 14-damage primary
   hit. The tape records `3.5` exactly, so trample now retains
   `damage * trample_percent` as a float.
2. It enlarged the blast disc by the Elephant's own collision radius. Tape
   candidate-exposure geometry rejects that: secondary victims are sharply
   bounded around the Elephant, with no hits above ~0.70 tiles, while the old
   formula reached 0.85. The corrected reach is
   `trample_radius + victim.radius + 2px`, where 2px is the movement resolver's
   existing contact tolerance. The Elephant's 0.25-tile dat collision radius
   still governs packing, and its 0.50 outline remains renderer-only.

The tape also showed why correcting blast geometry alone did not fix winner HP:
the engine's W1 scrum walk was counter-steered by same-team social repulsion before
allies overlapped. While W1 is active, already-engaged allies now ignore only that
outer social band; the actual overlap force and collision resolver are unchanged.
This refinement remains behind W1, so shipped defaults are unaffected by it.

Measured trample texture on representative `r5`, tape vs corrected W1+W2:

| metric | tape | corrected sim |
|---|---:|---:|
| Elephant swing groups | 93 | 91 |
| multi-hit rate | 50.5% | 48.4% |
| victims per multi-hit swing | 2.51 | 2.77 |
| maximum victims | 4 | 4 |
| secondary damage | 3.5 | 3.5 |

Outcome over authoritative `r3`–`r9`: Elephant wins 7/7 in both; tape median
winner HP **776**, corrected W1+W2 **728** (**93.8%**); tape median Champion hits
**150**, sim **154**. Individual tapes still span 628–1224 HP despite identical
recorded starts, so the deterministic sim is judged against the family median.
Fight duration remains short (`r5`: 39.6 s sim vs 53.4 s tape), leaving the
mid-fight fragmentation work in §5 open.

W1 alone remains wrong (1108 Elephant HP, 143% of the tape median). W2 is not an
optional score adjustment here: the tape's measured 1.2–2.0 s opening reaction
window is required to prevent Elephant cadence from re-locking the scrum. Both
flags remain default-OFF pending the full-corpus campaign gate.

Validation: `node --test tests/js/engine/` 397/397; authoritative 28-fight
Champion melee W1+W2 board 26/28 winners and 16/28 within ±20% winner HP. The
mandatory parity panel remains red at its pre-existing `champ-v-jaguar` tick-0
spawn offset, before any corrected combat tick executes.

## 8. Commands

```
# champion melee subset, W1+W2
node tools/simjs/calib_runner.mjs --tags-file .scratch/standard_units/champion_melee_tags.txt \
  --seeds 20 --w1 scrumWalk --w2 reactionWindow --out-dir D:/AI/aoe2_golden/simruns_champ_0802_w1w2
python -m aoe2x.calibration.score --melee-only --sim-runs-dir <dir> --label <l>
# probe positions for the refill forensics
node tools/simjs/melee_engagement_probe.mjs --tags <T> --seeds 1 --pos-seeds 1 \
  --w1 scrumWalk --w2 reactionWindow --out-dir <probe> --verify <clean>
# suites
node --test tests/js/engine/          # 397/397
python -m pytest tests/test_calibration_filters.py   # 14 passed (gate pinned 123)
```
