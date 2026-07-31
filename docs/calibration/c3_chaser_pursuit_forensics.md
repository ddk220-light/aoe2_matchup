# Phase C3 — melee chaser pursuit, tape vs E1-on engine

Measurement only. No engine file is touched, no flag default changes. This
round measures **how the chaser pursues** an orbiting kiter — the one side of
the C1 cadence defect that was still unattributed after the kiter-side
mechanisms (flee bearing, rhythm, contact break, orbit) were built or refuted.

**The question.** With `E1.orbitKite` ON the kiter's geometry matches the tape
in kind (e1_orbit_kite.md), yet the melee chaser over-catches: champion
damage/run in `champion__vs__arbalester` 720 vs the ledger's ~603 target (tape
recordings measured here: **127.5**), camel damage/run in
`hand_cannoneer__vs__heavy_camel` 540 vs tape **272.8**. C1 said the tape
chaser is contact-limited (0.66 s in reach per cycle vs engine 1.81, 97.2 % of
cycles lose contact vs 54.1 %). C3 asks: is the difference the pursuit LAW,
the pursuit SPEED, the SWING HALT, or the EPISODE STRUCTURE — with numbers on
each.

## How this was measured

```
node <scratchpad>/dump_c3_tracks.mjs --repo D:/AI/aoe2_matchup \
     --out-dir <scratchpad>/c3_e1on --seeds 3 --e1 orbitKite \
     --families champion__vs__arbalester,champion__vs__heavy_cav_archer,\
halberdier__vs__heavy_cav_archer,hand_cannoneer__vs__heavy_camel,\
hand_cannoneer__vs__paladin,hand_cannoneer__vs__hussar
python <scratchpad>/c3_analysis.py     # -> data/calibration/analysis/c3_chaser_pursuit.json
```

- **Corpus**: the six chaser families named in the brief — 39 non-quarantined
  recordings (6+9+6+6+6+6), engine = the same 39 fights × 3 seeds = 117 runs,
  `improved-simulation` working tree, tapebox arena, tape spawns, **all flags
  shipped defaults except `E1.orbitKite = ON`**. Chaser = the melee side
  (champion / halberdier / heavy_camel / paladin / hussar).
- **One implementation, two sources**: tapes load through
  `rff.load_tape` (10 Hz positions, damage stream, engine-equivalent wipe cut);
  engine runs are 10 Hz samples of the identical sim `calib_runner` builds,
  plus two fields the tape cannot give: the chaser's **actual `u.target` id
  per frame** and the sim's own `fightCenter`. Reach is `rff.engine_reach`
  (inRange() itself). "Moved" is the campaign bar (0.02 tiles/sample).
- **Target assignment**: engine = the recorded `u.target`. Tape = the victim
  of that chaser's next landed hit (≤ 8 s ahead), else the nearest living
  kiter. Fight centre for the tape = midpoint of the two side centroids on
  frame 0 (the engine's own definition).
- 3-seed KPI check against the E1 round's 20-seed board: champion dmg/run 710
  (board: 720), camel 464 (board: 540) — same regime, samples 4–27× the
  tape's per family. `halberdier__vs__heavy_cav_archer` lands **720 = 720**
  and matches the tape on every C3 metric below — it is the built-in control.

**KPI anchor (chaser damage delivered to the kiter side per run):**

| family | tape | E1-on engine | E/T |
|---|---|---|---|
| champion__vs__arbalester | **127.5** | 710.0 | 5.6× |
| champion__vs__heavy_cav_archer | **603.0** | 960.0 | 1.6× |
| halberdier__vs__heavy_cav_archer | 720.0 | 720.0 | 1.0× |
| hand_cannoneer__vs__heavy_camel | **272.8** | 464.3 | 1.7× |
| hand_cannoneer__vs__paladin | 827.3 | 828.0 | 1.0× |
| hand_cannoneer__vs__hussar | 538.5 | 560.0 | 1.04× |

(hits per chaser-alive-second, T → E: champ/arb 0.022 → 0.111; champ/HCA
0.077 → 0.135; halb/HCA 0.055 → 0.104; camel 0.096 → 0.137; paladin
0.097 → 0.157; hussar 0.089 → 0.121.)

---

## Q1. Pursuit law — what the code says, what both sources do

**What the engine SHOULD do (code read):** `moveTowardTarget()`
(battle_unit.js:3355) is textbook **pure pursuit**: heading = normalised
vector to the target's **current position**, plus collision avoidance, passed
through a 0.3 per-tick velocity smoothing. There is no intercept or lead term
anywhere on the melee path (the only intercept in the file is projectile
aiming, `computeLeadPoint`, ranged-only).

**Measured** (chaser frames: moving ≥ 0.05 tiles/sample, living assigned
target): angle between realised velocity and (a) bearing to the target's
current position vs (b) bearing to the constant-speed intercept point; plus a
**time-lag fit** — which time-offset τ of the target's own track best explains
the chaser's heading (τ>0 = leading at a future position, τ<0 = trailing).

| family | med∠cur T→E | med∠int T→E | % frames closer to CUR than INT, T→E | leadFrac T→E | best-fit τ (s) T→E |
|---|---|---|---|---|---|
| champion__vs__arbalester | 19.3 → 26.3 | 33.4 → 28.8 | **77.1 → 49.0** | −0.16 → +0.54 | **−0.1 → +0.9** |
| champion__vs__heavy_cav_archer | 24.2 → 30.8 | 28.7 → 32.6 | **72.3 → 40.9** | −0.14 → +0.86 | **0.0 → +1.0** |
| halberdier__vs__heavy_cav_archer | 19.3 → 15.0 | 22.5 → 17.5 | 73.4 → 60.9 | −0.10 → +0.24 | −0.1 → +0.3 |
| hand_cannoneer__vs__heavy_camel | 26.2 → 40.1 | 31.8 → 30.9 | **67.4 → 32.8** | −0.14 → +1.71 | **+0.2 → +1.0** |
| hand_cannoneer__vs__paladin | 25.7 → 32.1 | 32.6 → 27.7 | **69.1 → 36.9** | −0.20 → +1.27 | **0.0 → +1.0** |
| hand_cannoneer__vs__hussar | 31.0 → 43.7 | 36.4 → 34.6 | **66.6 → 31.9** | −0.36 → +1.78 | **0.0 → +1.0** |

(leadFrac = signed angle from current-bearing toward the intercept bearing
covered by the realised velocity; 0 = pure pursuit, 1 = full intercept.
The τ fit uses only out-of-reach frames with the target displacing ≥ 0.15
tiles over ±0.2 s. The tape's τ curve is a shallow bowl with its minimum at
−0.1…+0.2 s; the engine's falls monotonically out to +0.9/+1.0 s, e.g.
camel: 73° at τ=−1 → 29° at τ=+1.)

**Verdict.**

- **The tape chaser is a pure pursuer, with a slight trail** — its heading is
  best explained by the target's position **now** (τ ≈ 0, leadFrac slightly
  negative in all six families), and it points closer to the current position
  than to the intercept in ~70 % of frames. There is no evidence of lead.
- **The engine chaser, as realised, cuts the orbit chord** — τ ≈ +1.0 s,
  leadFrac ≥ 1 in the three HC families (it heads at or past the full
  intercept point) — even though its code is pure pursuit. The resolution is
  **not a steering-law bug**: the E1 kiter executes its orbit as
  *stop-fire-hop* (0.6 s parks between bursts, §Q3/Q4), and a pure pursuer
  aimed at a **parked** target is indistinguishable from an interceptor. Each
  hop re-parks the kiter a short arc clockwise; the chaser's straight walk to
  the park point IS the chord. The tape kiter, by contrast, is *in motion*
  when the chaser approaches (its runs are 2.7–3.4 s long) so pure pursuit
  stays a curve **behind** it.
- Catch-rate this implies: the chord-cutter re-touches in 0.2–0.5 s (§Q5) and
  lands 1.3–5.1× the tape's hits per chaser-second (table above). But note
  the direction of the fix: the engine does NOT need a different chase law —
  it needs the situations in which pursuit ≠ intercept to exist at all (real
  gaps, moving target). **Do not add a lead/intercept term; do not "fix"
  pure pursuit.** The tape confirms pure pursuit is the right law.

## Q2. Speed ledger — the tape chaser runs at book speed; ours loses 24–39 % to jostle

Dict speeds (`data/calibration/combat_dicts.json`, tiles/s) and realised speed
over pursuit frames (moving, out of reach of the assigned target):

| family | chaser dict | kiter dict | realised med T→E | ratio-to-dict T→E | closing component T→E (t/s) | kiter realised T→E |
|---|---|---|---|---|---|---|
| champion__vs__arbalester | 1.06 | 0.96 | 1.054 → 1.015 | **0.994 → 0.958** | 0.97 → 0.87 | 0.96 → 0.90 |
| champion__vs__heavy_cav_archer | 1.06 | 1.54 | 1.054 → 0.962 | **0.994 → 0.908** | 0.92 → 0.77 | 1.46 → 1.35 |
| halberdier__vs__heavy_cav_archer | 1.10 | 1.54 | 1.098 → 1.091 | 0.999 → 0.992 | 1.01 → 1.03 | 1.53 → 1.50 |
| hand_cannoneer__vs__heavy_camel | 1.60 | 0.96 | 1.592 → 1.069 | **0.995 → 0.668** | 1.33 → 0.73 | 0.96 → 0.90 |
| hand_cannoneer__vs__paladin | 1.49 | 0.96 | 1.482 → 1.135 | **0.995 → 0.761** | 1.25 → 0.87 | 0.96 → 0.90 |
| hand_cannoneer__vs__hussar | 1.65 | 0.96 | 1.647 → 1.000 | **0.998 → 0.606** | 1.23 → 0.66 | 0.96 → 0.90 |

- **The tape chaser realises 99.4–99.9 % of its dat speed in every family** —
  including the 1.6 t/s camel and 1.65 t/s hussar. Full speed, no pathing
  tax, while its cycle is still 1.23–1.69× reload. The cadence loss is
  therefore *not* bought with speed.
- **The engine chaser realises 61–96 %**, worst exactly where it over-catches
  most (hussar 0.606). Where does it go? **Turning, not walking.** Binned by
  heading-change rate (deg/s between consecutive samples):

| bin (deg/s) | tape speed (× dict) | engine speed (× dict) | share of pursuit frames T → E |
|---|---|---|---|
| < 100 (straight) | 1.00 | **1.00** | 67–79 % → 27–47 % |
| 100–300 | 0.98–0.99 | 0.73–0.94 | 10–13 % → 22–27 % |
| 300–700 | 0.94–0.95 | 0.65–0.82 | 7–11 % → 14–24 % |
| > 700 | 0.79–0.88 | 0.53–0.75 | 5–9 % → 5–24 % |

  In its straight-line bin the engine walks at exactly dict speed — there is
  no raw speed bug. But it spends 53–73 % of its pursuit frames in the
  turning bins (tape: 21–33 %) because it rides at contact distance where the
  bearing to an adjacent body swings fast, and avoidance + the 0.3 smoothing
  bleed speed on every swing. **The tape shows no meaningful turn-rate cost**
  (0.94–0.95 × dict at 300–700 deg/s) — do not add one; the engine's deficit
  is an emergent symptom of contact-riding and disappears if real gaps exist.

## Q3. Swing-halt anatomy — the tape's ~0.7 s plant is the whole escape

Around every landed chaser hit with a full reload window (both parties alive
through it): chaser stopped-duration from the hit, victim departure latency,
and the separation change split by chaser state.

| family | chaser halt med (p90) T | E | halts < 0.2 s T→E | victim latency T→E | gap opened DURING halt T→E | gap change after halt (rest of reload) T→E |
|---|---|---|---|---|---|---|
| champion__vs__arbalester | 0.74 (1.96) | 0.10 (0.8) | 0 % → 65 % | 0.00 → 0.00 | +0.52 → 0.00 | −0.21 → +0.08 |
| champion__vs__heavy_cav_archer | 0.74 (2.00) | 0.90 (2.0) | 0 % → 23 % | 0.11 → 0.30 | +0.43 → 0.00 | −0.16 → +0.03 |
| halberdier__vs__heavy_cav_archer | 0.72 (2.11) | 0.40 (1.5) | 0 % → 0 % | 0.51 → 0.10 | +0.53 → −0.00 | −0.09 → +0.00 |
| hand_cannoneer__vs__heavy_camel | 0.71 (0.78) | 0.00 (0.3) | 0 % → 84 % | 0.00 → 0.00 | +0.57 → 0.00 | −0.00 → +0.10 |
| hand_cannoneer__vs__paladin | 0.64 (0.74) | 0.00 (0.5) | 0 % → 68 % | 0.00 → 0.00 | +0.54 → 0.00 | −0.22 → +0.06 |
| hand_cannoneer__vs__hussar | 0.71 (1.13) | 0.00 (1.4) | 0 % → 75 % | 0.00 → 0.00 | +0.57 → 0.00 | −0.07 → +0.02 |

Decomposition of the per-reload radial gain (C1's +1.03 tiles), split by
whether the CHASER was stopped or moving over each sample:

| family | gain while chaser STOPPED, T→E | gain while chaser MOVING, T→E | victim path tortuosity T→E |
|---|---|---|---|
| champion__vs__arbalester | **+0.57 → +0.04** | −0.22 → +0.05 | 1.03 → 1.05 |
| champion__vs__heavy_cav_archer | **+0.50 → +0.01** | −0.26 → +0.03 | 1.02 → 1.05 |
| halberdier__vs__heavy_cav_archer | **+0.78 → −0.01** | −0.50 → +0.03 | 1.03 → 1.12 |
| hand_cannoneer__vs__heavy_camel | **+0.65 → +0.08** | −0.28 → −0.02 | 1.03 → 1.04 |
| hand_cannoneer__vs__paladin | **+0.61 → +0.03** | −0.31 → 0.00 | 1.06 → 1.04 |
| hand_cannoneer__vs__hussar | **+0.64 → +0.03** | −0.19 → 0.00 | 1.04 → 1.04 |

**The split C1 asked for, answered:**

1. **Chaser halt duration: ~100 % of the escape.** On tape the entire net
   gain (+0.50…+0.78 tiles) accrues while the chaser stands; once the chaser
   moves again it *claws back* 0.1–0.5 tiles. The tape's +1.03 tiles/reload
   is, to first order, `halt × kiter speed` (0.7 s × 0.96–1.5 t/s = 0.7–1.1
   tiles) minus the chase-back.
2. **Kiter departure latency: ~0 %.** The 0.96 t/s kiters have 0.00 s median
   latency in BOTH sources (they are already walking when the blow lands —
   the tape hit lands on a mid-move victim, C1 M3). Nothing left to model.
3. **Path curvature: ~0 %.** Tortuosity 1.02–1.06 both sides — the escape run
   is straight in both engines.

**The number the campaign was missing** (c2b_melee_swing.md §6 closed with
"the missing quantity is a melee stop/turn duration, and it has to be
measured off the tape"): the tape chaser's post-swing plant is **0.64–0.74 s
median, in all six families, five different chaser classes, with ZERO halts
under 0.2 s** (n = 29–301 windows per family). It reads as a fixed
swing-commit + recovery interval of **≈ 0.7 s**, not as a speed- or
class-dependent quantity. The E1-on engine's HC-family chasers halt **0.0 s**
(65–84 % of windows under 0.2 s): they swing and keep walking, so the kiter
never gets its head start. (The champion-vs-HCA engine cell reads 0.9 s only
because its victim *stays in reach* and the chaser stands in `attacking`
through the reload — a reload-plant, not a swing-plant.)

## Q4. Contact-episode structure — engine contact is continuous or wall-pinned

In-reach episodes (any living kiter within the chaser's reach) and the gaps
between them, per chaser; plus where the landed hits happen relative to the
orbit.

| family | episode med (p90) T | E | gap med (p90) T | E | in-reach share T→E |
|---|---|---|---|---|---|
| champion__vs__arbalester | 0.40 (1.04) | 1.30 (5.3) | 3.18 (9.6) | 0.40 (7.9) | 0.02 → 0.31 |
| champion__vs__heavy_cav_archer | 0.63 (1.48) | 1.20 (4.1) | 1.75 (8.3) | 0.50 (3.5) | 0.07 → 0.36 |
| halberdier__vs__heavy_cav_archer | 0.61 (1.57) | 0.75 (2.8) | 1.35 (4.9) | 0.40 (1.8) | 0.06 → 0.18 |
| hand_cannoneer__vs__heavy_camel | 0.42 (1.02) | 0.70 (4.0) | 2.18 (10.7) | 0.40 (4.7) | 0.05 → 0.34 |
| hand_cannoneer__vs__paladin | 0.33 (1.04) | 0.70 (2.9) | 3.32 (15.6) | 0.30 (4.1) | 0.05 → 0.24 |
| hand_cannoneer__vs__hussar | 0.32 (1.07) | 0.80 (4.7) | 3.30 (17.6) | 0.20 (1.6) | 0.04 → 0.23 |

Where the catches land (victim at the moment of a landed chaser hit,
relative to the fight centre and the box):

| family | r@hit vs orbit-r, T | E | hits ≤1.5 tiles of a wall T→E | orbit reversal at hit T→E |
|---|---|---|---|---|
| champion__vs__arbalester | 3.4 vs 4.2 | 4.7 vs 4.2 | 16 % → 11 % | 0 % → 0 % |
| champion__vs__heavy_cav_archer | 3.8 vs 4.3 | 4.0 vs 4.1 | 12 % → 0 % | 1 % → 0 % |
| halberdier__vs__heavy_cav_archer | 4.0 vs 4.5 | 3.5 vs 3.8 | 15 % → 0 % | 0 % → 0 % |
| hand_cannoneer__vs__heavy_camel | 2.6 vs 4.2 | 4.7 vs 5.2 | 7 % → **41 %** | 3 % → 0 % |
| hand_cannoneer__vs__paladin | 2.9 vs 4.3 | 4.9 vs 4.7 | 8 % → **37 %** | 3 % → 0 % |
| hand_cannoneer__vs__hussar | 2.8 vs 3.9 | 6.2 vs 5.5 | 3 % → **46 %** | 3 % → 0 % |

- **Structure**: tape = brief touches (0.3–0.6 s) separated by long gaps
  (1.4–3.3 s median, p90 5–18 s). Engine = long rides (0.7–1.3 s, p90 up to
  5.3 s) separated by micro-gaps (0.2–0.5 s) — the reach predicate flickers
  at the boundary while the chaser stays glued to the orbiting ball. The
  in-reach duty is 4–8× the tape's.
- **Location**: engine catches are NOT at orbit reversals (0 % everywhere;
  reversals barely exist for either source — the E1 orbit is sign-locked).
  In the three fast-chaser families they are **wall events**: 37–46 % land
  within 1.5 tiles of the tapebox wall (tape: 3–8 %), at radius at/above the
  orbit median, and the engine's orbit itself sits wider than the tape's
  (5.2–5.5 vs 3.9–4.2 tiles). The kiter ball drifts outward (E1 board:
  r-slope +0.077 t/s vs tape −0.030) until the arc runs along the wall and
  the corner pins it. The champion families instead show the
  continuous-contact mode (0–11 % near-wall, catches at mid-field radius) —
  there the kiter simply never leaves reach.
- On tape the catches happen **inside** the orbit (victim radius 2.6–4.0 vs
  ring at 3.9–4.5): the kiter is caught when it is displaced inward — cutting
  across the ring or repositioning — not while riding the ring. The engine
  never produces this because its kiter is caught before it can be displaced
  anywhere.

## Q5. Re-close mechanics — and the 1.29 falls out of `max(reload, halt + re-close)`

Per contact break (chaser loses reach to every living kiter): time to
re-contact, the peak gap reached, and the realised closing speed from the
peak back to contact.

| family | re-close med (p90) T | E | peak gap (tiles) T→E | closing speed from peak T→E (t/s) | raw Δspeed |
|---|---|---|---|---|---|
| champion__vs__arbalester | 2.89 (6.5) | 0.40 (7.4) | 0.68 → 0.10 | 0.49 → 0.29 | +0.10 |
| champion__vs__heavy_cav_archer | 1.69 (6.9) | 0.50 (2.0) | 0.60 → 0.12 | 0.51 → 0.43 | −0.48 |
| halberdier__vs__heavy_cav_archer | 1.31 (4.6) | 0.40 (1.8) | 0.56 → 0.16 | 0.61 → 0.61 | −0.44 |
| hand_cannoneer__vs__heavy_camel | 2.07 (7.1) | 0.40 (3.2) | 0.73 → 0.08 | 0.60 → 0.37 | +0.64 |
| hand_cannoneer__vs__paladin | 2.77 (7.7) | 0.30 (2.2) | 0.83 → 0.08 | 0.55 → 0.40 | +0.53 |
| hand_cannoneer__vs__hussar | 2.46 (7.9) | 0.20 (1.5) | 0.83 → 0.06 | 0.63 → 0.38 | +0.69 |

- The tape re-close is **slower than the raw speed delta predicts only
  slightly** for the fast chasers (camel: 0.60 vs 0.64 t/s ⇒ 0.93×; hussar
  0.91×; paladin 1.04×): once the kiter has its ~0.7-tile head start, the
  chase-back is an honest full-speed pursuit of a full-speed runner. For
  chasers with no speed edge (champion vs arb, Δ=0.10) the tape still closes
  at 0.49 t/s — the closing speed there is supplied by the *kiter stopping to
  fire*, not by the delta. So a correct model needs no pathing-loss constant
  on the chaser: **halt + full-speed re-close reproduces the tape's numbers**.
- **The cadence arithmetic.** Model the cycle as
  `interval ≈ max(reload, halt + re-close)` and insert only measured medians:

| family | tape: halt+reclose → pred (measured iv) | engine: halt+reclose → pred (measured iv) | pred T/E (measured T/E) |
|---|---|---|---|
| champion__vs__arbalester | 0.74+2.89 = 3.63 → 3.63 (2.46*) | 0.1+0.4 < rl → 2.00 (2.10) | 1.82 (1.17) |
| champion__vs__heavy_cav_archer | 0.74+1.69 = 2.43 → 2.43 (2.77) | 0.9+0.5 < rl → 2.00 (2.02) | 1.22 (1.38) |
| halberdier__vs__heavy_cav_archer | 0.72+1.31 = 2.03 < rl 3.0 → 3.00 (3.32) | → 3.00 (3.23) | 1.00 (1.03) |
| hand_cannoneer__vs__heavy_camel | 0.71+2.07 = 2.78 → 2.78 (2.51) | → 2.00 (2.03) | 1.39 (1.24) |
| hand_cannoneer__vs__paladin | 0.64+2.77 = 3.41 → 3.41 (3.21) | → 1.90 (1.93) | 1.79 (1.66) |
| hand_cannoneer__vs__hussar | 0.71+2.46 = 3.17 → 3.17 (2.88) | → 1.90 (1.92) | 1.67 (1.50) |

  (*champion vs arb overshoots because the tape champion frequently
  retargets a nearer arbalester rather than re-chasing the same one — the
  measured interval is to ANY victim.) Five of six families land within
  0.1–0.3 s of the measured interval, and the halberdier control falls out
  automatically: its 3.0 s reload swallows `halt + re-close = 2.0 s`, which
  is exactly why the engine already matches the tape there. **E12's 1.29 is
  not a mystery constant — it is `max(rl, 0.7 + re-close)/rl`, and re-close
  is itself `(halt × kiter speed)/closing speed`.** The engine's cycles sit
  at 1.01–1.08 × reload because with a 0-second halt there is nothing to
  re-close.

---

## Mechanism candidates, ranked by evidence

**1. Post-swing plant ≈ 0.7 s on the melee chaser (the missing quantity, now
measured).** The strongest and simplest: a fixed swing-commit/recovery
interval after a landed melee swing during which the chaser does not move.
- *Evidence*: tape halt median 0.64–0.74 s across five chaser classes, 0 % of
  windows below 0.2 s (§Q3); 100 % of the kiter's escape accrues during it
  (§Q3 split); with it, `max(reload, halt + re-close)` reproduces the
  measured cycle in 5/6 families including the halberdier control (§Q5);
  c2b_melee_swing.md §6 explicitly declared this measurement the enable
  blocker for the already-built C2B machinery
  (`stopToSwing`/`committedSwingLands`, `MELEE_SWING_RECOVERY_S = 0` today).
- *What to change*: spend the measured value — a ~0.7 s post-landing plant
  (C2B rules + `MELEE_SWING_RECOVERY_S ≈ 0.7`, or the dat's attack-anim
  duration if extractable per class) so the victim's escape happens while the
  swing resolves, and the re-test on wake finds it out of reach.
- *Predicted effect*: HC-vs-camel cycle 2.03 → ~2.8 s (tape 2.51) ⇒ cadence
  ×0.72, camel dmg/run 540 → ~390 first-order; second-order (HCs live longer,
  camels die sooner, fewer chaser-seconds) and the §Q4 wall share carry it
  toward the 273 target. Champion-vs-arb: with Δspeed 0.10 t/s a 0.5–0.7-tile
  head start costs 5–7 s per re-close ⇒ 720/710 collapses toward the tape's
  127–300 band (crosses the ~603 P2 ledger from above). Champion-vs-HCA:
  960 → ~790 by cadence (pred 2.43/2.02), further down as HCA survival
  compounds — the direction P2's enable criterion (0.0772 hits/cs) needs.
- *Must NOT break*: melee-vs-melee uses the same movement code. The plant
  self-scopes partially (a melee victim stays in reach, so hit-to-hit remains
  reload-limited), but C2B's own board showed C-b ON costing the melee gate
  (117 vs required ≥126) — the leak is walk-on-after-kill and scrum re-close
  delays. So gate the plant on the victim being RANGED (same scoping as the
  pursuit-bar/lock rules), or re-run the §6 C2B enable board and require
  melee-gate ≥126, corpus ≥194/216, and `halberdier__vs__heavy_cav_archer`
  unchanged (its reload already swallows the plant; any regression there
  means the implementation leaked into non-swing time). Also re-check D2
  (champion-vs-siege walks through the same branch).

**2. E1 orbit-radius / wall interaction (kiter-side residual, second order).**
- *Evidence*: 37–46 % of E1-on engine catches in the three fast-chaser
  families are within 1.5 tiles of a wall (tape 3–8 %), at an orbit that sits
  1.1–1.6 tiles wider than the tape's (§Q4); E1's own board shows r-slope
  +0.077 vs tape −0.030. This is not chaser behaviour and candidate 1 will
  not remove it: a camel that must re-close 0.7 tiles will still eventually
  corner a kiter whose arc grinds the wall.
- *What to change*: E1 refinement only — hold/contract the orbit radius (the
  tape's r-slope is slightly negative) or make the arc wall-aware so the ring
  never intersects the box; no new constant beyond the tape's measured
  radius profile.
- *Predicted effect*: removes most of the wall-pinned ~40 % of camel/hussar
  catches ⇒ combined with candidate 1 takes camel toward ~273; negligible on
  champion families (0–11 % near-wall) and on the champion-vs-arb KPI.
- *Must NOT break*: the E1 geometry board (Δθ sign-lock 78/78, corner share,
  wall-death 0.276) and `hand_cannoneer__vs__paladin` / `hussar` winners
  (already 1.0× on damage/run).

**3. Not candidates — measured out.**
- *Chase-law change (lead/trail/intercept)*: the engine's code is already the
  tape's law (pure pursuit); the apparent +1 s lead is emergent from chasing
  a parked, hopping target (§Q1) and collapses once candidates 1–2 give the
  kiter real motion between touches. Adding a trail/lag term would be fitting
  a symptom.
- *Chaser speed or turn-rate cost*: the tape chaser runs at 99.4–99.9 % of
  dat speed and pays no turn cost worth modelling (§Q2); the engine is
  already SLOWER than the tape while pursuing — any speed nerf moves the
  wrong direction, and the 0.61–0.76 realised ratio is contact-jostle that
  disappears when gaps exist.
- *Kiter departure latency / flee curvature*: both are already tape-exact
  (0.0 s, tortuosity ~1.03) with E1 on (§Q3). The kiter's move-run rhythm is
  also now near-tape (runs 2.9 vs 3.35 s, stop-frac 0.18 vs 0.19 for the HC;
  the hussar family's short 1.1 s runs are the chaser interrupting, not the
  kiter dawdling).

**Files**: measurements in `data/calibration/analysis/c3_chaser_pursuit.json`
(per family × source, every number in this doc); scratchpad tools
`dump_c3_tracks.mjs` + `c3_analysis.py` (session scratchpad, throwaway).
