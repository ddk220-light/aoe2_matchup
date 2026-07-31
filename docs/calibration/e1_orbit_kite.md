# E1 — orbitKite: the clockwise-arc retreat basis (implementation round)

**What this round built.** The mechanism specified off the paired E1
measurement (docs/calibration/e1_kite_orbit_tapes.md /
e1_kite_orbit_engine.md): with `E1.orbitKite` on, a group-kiting ranged
unit's retreat BEARING stops being "away from the threat" and becomes the
chord toward the point advanced CLOCKWISE along its own circle about the
fight centre C — `waypoint = C + rotate(d, s/r)`, `d = pos − C`, `s` the
existing per-tick kite step (`moveSpeed × dt`; no new magnitude constant).
C is computed once per battle in `scenario.js createSimulation` (midpoint of
the two sides' spawn centroids — the tape boards' own reference point) and
stored as `sim.fightCenter`. Clockwise = the atan2-increasing rotation in
engine world coordinates, which equals the tape boards' documented
convention (positive Δθ in tile coords = clockwise on screen;
`TapeBox.worldToTile` has no axis flip) — pinned by a test.

Only the basis changes. The override sits in
`BattleUnit.moveAwayFromTarget`, gated on `kiteSteering()`'s own non-null
result (so siege, melee and non-out-ranging sides are byte-identical), does
not touch a live C2A contact break, and leaves the orbit/cohesion steering
terms, avoidance, velocity smoothing, arena constraint and every kite-state
trigger untouched — the compositions the C2 rounds adversarially refuted
changing. Degenerate guard: r < 0.5 tiles falls back to the radial basis.

**Code:** `E1`/`setE1` + `E1_ORBIT_TANRAD`/`E1_ORBIT_MIN_RADIUS_TILES` in
engine `constants.js`; mechanism in `battle_unit.js`; `sim.fightCenter` in
`sim.js`/`scenario.js`; `--e1` spec through `calib_runner.mjs` /
`calib_worker.mjs` / `dump_kite_tracks.mjs` (which also grew `--tags`);
tests in `tests/js/engine/e1_orbit_kite.test.mjs` (16 tests; suite 348/348).

**Shipped variant: pure tangent. Shipped default: OFF (both flags).**

---

## 1. Dev-subset iteration (5 matchups × 3 seeds, tapebox, tape spawns)

Subset: champion__vs__heavy_cav_archer, hand_cannoneer__vs__paladin,
hand_cannoneer__vs__hussar, hand_cannoneer__vs__heavy_camel,
arbalester__vs__elite_steppe. Geometry metrics are the two E1 boards'
definitions verbatim (validated first: the analyzer reproduces the
published engine board's rows at shipped defaults to the printed digits —
e.g. arb_vs_steppe +0.09 rev / 0.66 / +0.235 / corner 1.00 / t→wall 4.8 s).

### Geometry, subset aggregates (mean | median)

| metric | target | flag off | pure tangent | blend 1.77:1 |
|---|---|---|---|---|
| Δθ (rev, clockwise +) | median ≥ +0.5 | +0.15 \| +0.09 | **+0.62 \| +0.57** | +0.53 \| +0.38 |
| sign consistency | ≥ 0.85 | 0.70 | **0.98** | 0.97 |
| r-slope (t/s) | in [−0.10, +0.05] | +0.142 \| +0.154 | **+0.075 \| +0.041** | +0.120 \| +0.159 |
| corner (final 25%) | ≤ 0.5 | 0.85 \| 1.00 | 0.63 \| 0.93 | 0.88 \| 1.00 |
| wall deaths (pooled) | — | 0.91 | **0.33** | 0.48 |
| clockwise fights | — | 5/5 (drift) | 5/5 locked | 5/5 |

**Variant decision.** The brief's one knob (blend tangent with the existing
away basis at the tape's measured 1.77:1) was built, wired (`orbitBlend`)
and measured — and it is worse on every geometry axis: the away basis it
re-adds duplicates the radial push the avoidance sum already supplies, so
the radius balloons (median r-slope +0.159 vs +0.041) and the sweep drops
below the target (+0.38 vs +0.57). Pure tangent did not under-rotate and
did not balloon/collapse the radius on the subset, so per the brief's own
breakpoint the blend does not ship. Targets hit by pure tangent: sweep ✓,
sign ✓, r-slope ✓ (median; mean +0.075 slightly out on the two slow-HC
fights), corner ✗ (0.63 vs ≤0.5 — improved from 0.85 but the two
hand-cannoneer fights still end wall-adjacent; their TAPE corner is 1.00
and 0.47, so the target is conservative for this subset).

### HP-error, subset (33 fights incl. repeats, 3 seeds, winners / mean pts)

| variant | winners | mean pts | note |
|---|---|---|---|
| off | 29/33 | 18.6 | |
| pure tangent | 22/33 | 22.2 | champ_vs_HCA family 8/9 → 1/9; HC_vs_camel 15–21 → 5–12 pts |
| blend | 22/33 | 24.1 | same flips, worse pts everywhere except champ family |

The champion__vs__heavy_cav_archer flip is the documented knife edge
(P2/R5f-A2/C2a all hit it): any mechanism that changes the kiter's motion
while the tape's melee-chaser cadence loss (1.29×, E12/C1) is unmodeled
flips this family. The orbiting kiter holds radius — tape-correct — and the
full-cadence engine chaser, which no longer has to run the radius down,
catches it.

---

## 2. Full gate (216 fights × 20 seeds, shipped defaults ± `--e1 orbitKite`)

Scoreboards: `data/calibration/runs/20260731T145539Z-e1-orbitkite-on.json`
and `…145543Z-e1-control-off.json`.

**Control first: flag-off is behavior-identical, proven at the byte level.**
The control run's 4,320 seed files are `diff -rq`-identical to the
night-final run directory, and its scoreboard reproduces the night-final
summary exactly (194/216, agr 0.8981, 191 MISMATCH / 23 PASS / 2
INCONCLUSIVE).

| board | winners | r-v-r | r-v-m | melee | siege |
|---|---|---|---|---|---|
| night-final baseline (= control) | 194/216 | 6/6, 2.33 pts | 97/102, 9.90 pts | 67/83, 6.43 pts | 24/25, 9.62 pts |
| **E1 orbitKite ON** | **181/216** | 6/6, 2.33 pts | **84/102, 16.13 pts** | 67/83, 6.43 pts | 24/25, 9.62 pts |

Melee, siege and ranged-vs-ranged are BIT-IDENTICAL with the flag on — the
kiteSteering gate holds; every change lives in ranged-vs-melee.

**Winner flips.** Lost 14 / gained 1 (net −13):
lost = champion__vs__arbalester ×6 (CANARY — fails) and
champion__vs__heavy_cav_archer_r2…r9 ×8; gained =
champion__vs__heavy_cav_archer (base recording — the family's tape winner
flips once within the family, so the deterministic engine can only match
one side of it).

**Canaries:** champion__vs__arbalester ✗ (agr 1.0 → 0.0, 0.35 → 51.7 pts);
halberdier__vs__heavy_cav_archer ✓ (family 6/6 holds, pts 3.7 → 13.9);
arbalester__vs__elite_steppe ✓ (6/6 holds, 10.1 → 13.7);
hand_cannoneer__vs__heavy_camel ✓ (6/6 holds and IMPROVES, 16.4 → 12.7).

### Every fight worse by ≥ 2 pts with E1 on (59 — no silent regressions)

All ranged-vs-melee; `W` = winner kept, `→n` = winner lost. Repeats share
one engine fight (identical spawns ⇒ identical sim), so families move as
blocks; per-family lines below give the shared delta.

| family (fights) | pts off → on (Δ) | winner |
|---|---|---|
| champion__vs__arbalester (6) | 0.35–3.82 → 50.3–55.8 (+48.5…+52.0) | Y→n ×6 |
| champion__vs__hand_cannoneer (1) | 7.68 → 25.45 (+17.8) | Y |
| champion__vs__heavy_cav_archer_r2–r9 (8) | 2.8–29.4 → 18.2–44.8 (+15.4) | Y→n ×8 |
| arbalester__vs__elite_fire_lancer (1) | 13.99 → 26.73 (+12.7) | Y |
| halberdier__vs__heavy_cav_archer (5 of 6) | 1.8–5.7 → 12.0–16.0 (+10.2) | Y |
| hand_cannoneer__vs__elite_elephant (2) | 11.7–15.7 → 19.6–23.6 (+7.9) | Y |
| elite_fire_lancer__vs__hand_cannoneer (1) | 4.97 → 11.22 (+6.3) | Y |
| arbalester__vs__heavy_camel (1) | 10.48 → 16.67 (+6.2) | Y |
| halberdier__vs__arbalester (1) | 1.35 → 6.73 (+5.4) | Y |
| champion__vs__heavy_cav_archer base (1) | 5.31 → 10.07 (+4.8) | n→Y |
| hand_cannoneer__vs__elite_steppe (1) | 22.13 → 26.12 (+4.0) | Y |
| heavy_cav_archer__vs__heavy_camel (6) | 0.4–5.6 → 4.2–9.3 (+3.8) | Y |
| elite_steppe__vs__arbalester (1) | 29.67 → 33.24 (+3.6) | n |
| arbalester__vs__elite_steppe (6) | 8.6–13.4 → 12.1–17.0 (+3.6) | Y |
| heavy_cav_archer__vs__paladin (1) | 4.82 → 8.37 (+3.6) | Y |
| heavy_cav_archer__vs__elite_steppe (6) | 1.4–11.4 → 4.9–14.9 (+3.5) | Y |
| heavy_cav_archer__vs__elite_elephant (1) | 2.21 → 5.12 (+2.9) | Y |
| arbalester__vs__paladin (3) | 8.9–14.4 → 11.6–17.1 (+2.7) | Y |
| arbalester__vs__hussar (1) | 12.71 → 15.16 (+2.5) | Y |
| hand_cannoneer__vs__paladin (6) | 19.4–33.4 → 21.7–35.7 (+2.3) | Y ×5, n ×1 (already lost) |

Better by ≥ 2 pts: hand_cannoneer__vs__heavy_camel ×6 (−3.7, the P1
canary family) and heavy_cav_archer__vs__hussar (−4.5).

---

## 3. Geometry re-board: full 78-fight kite corpus, flag ON (3 seeds)

| metric | tape | engine off | **E1 orbitKite ON** |
|---|---|---|---|
| Δθ (rev about C) | +1.33 mean / +1.13 median | +0.103 | **+0.538 / +0.539** |
| clockwise fights | 78/78 | 65/78 (drift) | **78/78, sign-locked** |
| sign consistency | 0.941 | 0.679 | **0.973** |
| ≥ half revolution | 75/78 | 0/78 | 50/78 |
| r-slope (t/s) | −0.030 | +0.146 | **+0.077 mean / +0.055 median** |
| radius s/m/e (tiles) | 4.0 / 3.5 / 2.7 | 3.9 / 8.7 / 9.1 | 4.0 / 5.3 / 5.7 |
| tan/rad | 1.77 | 1.25 (wall-slide) | 3.50 |
| corner (final 25%) | 0.24 | 0.90 | **0.603** |
| kiter wall-death fraction | rare | 0.86 | **0.276** |

Per kiter (E1 on): arbalester +0.56 rev / corner 0.70 / wall-death 0.26;
hand_cannoneer +0.62 / 0.95 / 0.54; heavy_cav_archer +0.46 / 0.26 / 0.10.

Read: the mechanism does exactly what the tapes show, directionally, on
every metric — direction-locked clockwise rotation appears (0/78 → 50/78
half-revolutions), radius growth drops 2× and the wall-grind death mode
largely disappears. Residuals vs tape: total sweep is still ~half the
tape's (fights end sooner because the orbiting kiter gets caught — cadence,
below), and tan/rad overshoots (3.50 vs 1.77) because the tape kiter's
radial 36% share comes from in/out oscillation the pure tangent basis does
not produce (the blend's outward-only radial is the wrong reconstruction of
it — measured, §1).

---

## 4. KPI extras (measurement only, for the later P1/P2 re-gate)

20 seeds, methodology validated against the C1 ledger (control camel
dmg/run 591 = the ledger's "was 591" exactly; HC land rate 85–86%).

| KPI | ledger target | control (off) | E1 ON |
|---|---|---|---|
| champion dmg/run, champion__vs__arbalester | ~603 (was 943 on the C1-era engine) | 145 | **720** |
| camel dmg/run, hand_cannoneer__vs__heavy_camel | ~273 (was 591) | 591 | **540** |
| HC land rate, same fight | hold ~86% | 85.3% | 84.1% |

Note the champion figure: the current shipped engine sits at 145 on this
metric (its arbs fly radially to the wall and shoot the champions down
almost untouched — the C1 ledger's 943 was measured on the Phase-C-era
engine). E1-on lands 720, +19% over the tape ledger's ~603 — i.e. the
orbit restores approximately the CONTACT the tape shows, and what converts
that contact into a flipped fight is the chaser swinging at full cadence
through it. Both held flags move toward their enable criteria under E1;
neither reaches it.

---

## 5. Verdict

The tape behavior is reproduced in kind; the scoreboard cannot pay for it
until the chaser side loses cadence the way the tape's does. `orbitKite`
ships built, tested and OFF — same holding pattern, same unlock, as
P1/P2/boltCorridor. When the melee-chaser-vs-kiter cadence mechanism lands,
flip `--e1 orbitKite` in the same gate and re-run this round's boards
(both scoreboard JSONs and the geometry dump command lines are above).

Test suite: 348/348 (`node --test tests/js/engine/`), including the 16 new
E1 tests. `parity_check.mjs` remains deliberately red (stale golden panel,
champ-v-jaguar tick-0 spawn offset — pre-existing, campaign-end recapture).
