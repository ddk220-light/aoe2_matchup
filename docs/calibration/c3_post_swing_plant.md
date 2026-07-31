# C3.postSwingPlant — the measured 0.7 s melee plant after a landed swing on a ranged victim

Mechanism round for the C3 forensics' candidate 1
(docs/calibration/c3_chaser_pursuit_forensics.md, measurements in
data/calibration/analysis/c3_chaser_pursuit.json). One rule, one flag, one
measured constant. **Ships OFF**; `--c3 postSwingPlant` on
tools/simjs/calib_runner.mjs (and dump_kite_tracks.mjs) is the A/B entry
point, `--e1 orbitKite --c3 postSwingPlant` the intended pairing.

## The rule

When a MELEE unit LANDS a swing on a RANGED victim, it may not MOVE for
`POST_SWING_PLANT_S = 0.7` seconds. Movement only:

- **Not the next swing.** update()'s in-reach attack branch is tested before
  the plant branch, so a victim still in reach at reload expiry is hit at
  bare reloadTime — the halberdier-control invariant (reload 3.0 swallows
  halt + re-close; such fights must not change cadence, and don't — see §4).
- **Not the windup or the damage.** The stamp happens at hit RESOLUTION in
  `performAttackOn` (after the damage path is committed), covering every
  melee landing path identically: delay-0 `performAttack`, committed-windup
  completion, killing blows.
- **Not melee victims.** C2B refuted a melee-vs-melee plant (the tape scrum's
  moving-share is a monotone ramp, not a step), so the stamp is gated on the
  victim's own `is_ranged` flag — the same scoping pattern as
  MELEE_TARGET_LOCK / the pursuit rules. Melee-vs-melee is bit-identical with
  the flag ON: proven by byte-comparing 6 champion-vs-melee fights × 3 seeds
  with `--c3 postSwingPlant` vs without — **18/18 seed files identical**.
- **Not ranged attackers.** They never reach `performAttackOn`, and the
  shared `meleeMoveLocked()` predicate excludes them besides.

Implementation reuses the C2B/E15b machinery exactly as the forensics asked:
the stamp writes the E15b `moveLockUntil` field (Math.max, so it can only
extend a lock) and is read by the existing `meleeMoveLocked()` predicate — a
planted unit still turns, re-targets, reloads, and is shoved by
resolveCollisions. Flag OFF is a no-op by construction: the stamp is behind
`if (C3.postSwingPlant ...)` and the predicate short-circuits with the flag
off while `MELEE_SWING_RECOVERY_S` is 0.

**The constant.** 0.7 s is the centre of the tape's measured halt band:
median post-landing halt 0.64–0.74 s across all six chaser families / five
chaser classes, zero halts under 0.2 s anywhere (forensics §Q3 — champion
0.74, halberdier 0.72, heavy_camel 0.71, paladin 0.64, hussar 0.71). A
sensitivity run at the top of the band (0.74) is board-indistinguishable
(camel dmg/run 455.0 vs 444.3, every winner cell identical), so the centre
stays. Never tuned against the scoreboard.

Tests: `tests/js/engine/c3_post_swing_plant.test.mjs` (12 tests — defaults
pin, off-identity, exact-duration lock, escape-then-pursuit, reload-cadence
invariance in reach, melee-victim exemption, ranged-attacker exemption,
killing-blow stamp, Math.max extension, rng purity).
`node --test tests/js/engine/`: **360/360 green** (348 + 12).
parity_check.mjs deliberately not consulted (stale golden panel this round).

## Iteration — 39-fight subset, 3 seeds, tapebox, tape spawns

The forensics' own six families (6+9+6+6+6+6 recordings). Configs:
(a) shipped defaults; (b) `--e1 orbitKite --c3 postSwingPlant`;
(c) `--c3 postSwingPlant` alone; plus the (d) `--e1 orbitKite` reference,
which reproduces the E1 board's regime (champ/arb 720, camel 464.3 — the
forensics' own 3-seed anchor numbers, confirming the harness).

### Winners (fight-level, median outcome, vs tape) and mean HP-pts error

| family (n) | (a) win / HP-pts | (d) E1 win / HP-pts | (b) E1+C3 win / HP-pts | (c) C3 win / HP-pts |
|---|---|---|---|---|
| champion__vs__arbalester (6) | 6/6 / 1.9 | 0/6 / 53.2 | 0/6 / 44.4 | **6/6** / 6.4 |
| champion__vs__heavy_cav_archer (9) | 8/9 / 18.4 | 1/9 / 32.6 | 1/9 / 36.7 | 1/9 / 35.1 |
| halberdier__vs__heavy_cav_archer (6) | 6/6 / 4.4 | 6/6 / 13.1 | **6/6** / 11.7 | 6/6 / 3.3 |
| hand_cannoneer__vs__heavy_camel (6) | 6/6 / 18.8 | 6/6 / 11.4 | 6/6 / 10.2 | 6/6 / 22.4 |
| hand_cannoneer__vs__paladin (6) | 5/6 / 23.2 | 5/6 / 25.1 | 5/6 / 24.2 | 5/6 / 23.5 |
| hand_cannoneer__vs__hussar (6) | 4/6 / 23.4 | 4/6 / 24.4 | 4/6 / 22.3 | 4/6 / 24.8 |

### KPIs (chaser damage/run; targets from the forensics table)

| KPI | (a) | (d) E1 | (b) E1+C3 | (c) C3 | tape / target |
|---|---|---|---|---|---|
| champion dmg/run, champ__vs__arb | 145.0 | 720.0 | **720.0** | 220.0 | 127.5 (ledger ~603) |
| camel dmg/run, HC__vs__heavy_camel | 588.0 | 464.3 | **444.3** | 648.7 | 272.8 (~390 first-order) |
| HC land rate, same family | 85.7 % | 83.0 % | **84.4 %** | 86.2 % | hold ~85 % |

### Chaser swing interval (median s, the mechanism's own axis)

| family | (a) | (d) E1 | (b) E1+C3 | tape (§Q5) |
|---|---|---|---|---|
| champion__vs__arbalester | 2.02 | 2.13 | **2.75** | 2.46 |
| champion__vs__heavy_cav_archer | 2.02 | 2.02 | 2.02 | 2.77 |
| halberdier__vs__heavy_cav_archer (control) | 4.20 | 3.23 | **3.13** | 3.32 |
| hand_cannoneer__vs__heavy_camel | 2.02 | 2.05 | **2.20** | 2.51 |
| hand_cannoneer__vs__paladin | 1.92 | 1.95 | **2.37** | 3.21 |
| hand_cannoneer__vs__hussar | 1.92 | 1.92 | 1.95 | 2.88 |

## What moved, what didn't, and why — honestly

**The mechanism does what was measured, where a contact break exists.**
Champ-vs-arb cadence 2.13 → 2.75 (tape 2.46), paladin 1.95 → 2.37, camel
2.05 → 2.20 — the plant is live in-fight and the released chaser resumes an
honest full-speed pursuit (unit-tested). The halberdier control holds on
every axis: winners 6/6, dmg/run 720.0 in all four configs, interval
3.13–3.23 against reload 3.0 (the plant swallowed exactly as the
`max(reload, halt + re-close)` law requires).

**The KPI targets did not arrive, and the residual has the forensics' own
name: candidate 2.** Three distinct blockers, all visible in this round's
numbers:

1. **champion__vs__arbalester (b): dmg/run stays 720.0** — that number is
   the arbalester side's entire HP pool (18 × 40); the champions still wipe
   the ball every seed despite swinging 29 % slower. With Δspeed only
   0.10 t/s the plant should cost 5–7 s per re-close — but in-engine there
   is no re-close: the E1 kiter is itself PARKED (stop-fire-hop, §Q1/Q4)
   during the plant window, so the head start the tape victim takes
   (it is mid-run when the blow lands, §Q3 latency 0.00 on a *moving*
   victim) still does not exist. The englobement then decides the fight.
2. **champion__vs__heavy_cav_archer: interval pinned at 2.02 in every
   config** — the continuous-contact mode (§Q4: the victim never leaves
   reach), where the plant by design changes nothing (in-reach swings are
   reload-limited). This family needs the kiter to actually leave, not the
   chaser to stand longer.
3. **Fast-chaser families: catches are wall events** (§Q4: 37–46 % within
   1.5 tiles). The plant cannot un-pin a kiter whose arc grinds the wall —
   camel improves 464 → 444, hussar barely (1.92 → 1.95: its catches were
   never cadence-limited).

**Geometry (dump_kite_tracks --e1 [--c3], subset, per-family medians):**

| family | r-slope E1 → E1+C3 | wall-death E1 → E1+C3 | revs E1 → E1+C3 |
|---|---|---|---|
| champion__vs__arbalester | +0.068 → +0.070 | 0.28 → 0.56 | 0.54 → 0.72 |
| champion__vs__heavy_cav_archer | +0.028 → **−0.045** | 0.00 → 0.00 | 0.53 → 0.65 |
| halberdier__vs__heavy_cav_archer | −0.010 → +0.015 | 0.00 → 0.00 | 0.27 → 0.29 |
| hand_cannoneer__vs__heavy_camel | +0.038 → +0.047 | 0.56 → 0.62 | 0.92 → 0.79 |
| hand_cannoneer__vs__paladin | +0.146 → +0.127 | 0.48 → 0.52 | 0.57 → 0.57 |
| hand_cannoneer__vs__hussar | +0.142 → +0.094 | 0.71 → 0.71 | 0.39 → 0.55 |

The radius ballooning RELENTS where the plant relieves chaser pressure
(champ/HCA crosses to the tape's negative sign; hussar/paladin slopes fall
by a third) but the subset median stays positive (+0.041 → +0.047, tape
−0.030) and cornering does NOT fall — near-wall share actually rises in the
families whose fights now last longer while the ball still ends on the wall.
Exactly the forensics' prediction: *"candidate 1 will not remove it: a camel
that must re-close 0.7 tiles will still eventually corner a kiter whose arc
grinds the wall."* The E1 orbit-radius/wall refinement (candidate 2) is the
gating residual, and secondarily the kiter's stop-fire-hop parking (its
move-run rhythm swallows the head start the plant grants).

**Also observed:** (c) C3-alone is scoreboard-safe on this subset (no winner
cell regresses; champ/arb stays 6/6 with the champion collapsing 145 → 220
under a kiter that now escapes radially), except camel dmg/run WORSENS
588 → 649 — without the orbit the radially-fleeing HC ball reaches the wall
sooner and the planted camel catches it there anyway. The plant is a
*pairing* mechanism: it spends its value only when the kiter has somewhere
to go.

**Note for the enable round:** siege victims carry `is_ranged = 1` in the
combat dicts, so a champion landing on a scorpion/onager will plant with the
flag on — re-check D2's champion-vs-siege families on the full-corpus gate,
as the forensics' candidate-1 scope note asked.

## Files

- `apps/website/static/js/engine/constants.js` — `C3` flag object + `setC3`
  + `POST_SWING_PLANT_S` (rationale block cites the forensics).
- `apps/website/static/js/engine/battle_unit.js` — stamp in
  `performAttackOn` (victim-ranged gated), shared `meleeMoveLocked()`
  predicate now also armed by `C3.postSwingPlant`.
- `tools/simjs/calib_runner.mjs` — `applyC3Spec` + `--c3`, forwarded through
  `calib_worker.mjs` workerData; `tools/simjs/dump_kite_tracks.mjs` — `--c3`.
- `tests/js/engine/c3_post_swing_plant.test.mjs`.
- Boards/geometry produced in the session scratchpad (`c3_board.py`,
  `c3_kite_geom.py`, run dirs `runs_{a,b,c,d,b74}`, `kite_e1{,c3}`) —
  throwaway, reproducible from the commands above.
