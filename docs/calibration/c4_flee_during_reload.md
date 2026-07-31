# C4.fleeDuringReload — the hunted kiter's run-commitment

Mechanism round for the composed escape cycle's third leg (E1 orbit basis →
C3 chaser plant → **C4 kiter run-commitment**). One rule, one flag, no new
constant. **Ships OFF**; `--c4 fleeDuringReload` on tools/simjs/calib_runner.mjs
(and dump_kite_tracks.mjs) is the A/B entry point; the intended pairing is
`--e1 orbitKite --c3 postSwingPlant --c4 fleeDuringReload`.

## The measurement, and where the engine's reload window actually went

C1 Table 2b (docs/calibration/c1_chaser_cadence.md): the tape cycle for a
ranged kiter hunted by melee is FIRE → RUN the whole reload window → HALT
(stop-to-fire) → FIRE. The tape's foot shooters run **2.7–3.4 s
continuously** (hand_cannoneer moveMed 3.35 s, imp_elite_skirm 2.71 s ≈ one
full reload window) and stop **once per cycle for ~0.62 s** (stops/min 16–18
at reload 3.0–3.45) — the pre-shot halt and nothing else. The engine's same
units: 0.3–0.4 s displacement dribbles at ~2× the tape's stopped duty cycle.

A state-level probe run for this round (per-tick state of the kiter side,
shipped defaults) relocated the defect. The engine's hunted kiter is ALREADY
in the kite arm for most of its reload — update()'s
`attackCooldown > 0 && !target.isRanged()` arm moves it every mid-reload
tick. Mid-reload occupancy, hand_cannoneer__vs__heavy_camel seed 1: kiting
0.68, kiting-but-pinned (attempted step, no displacement — bodies/wall) 0.21,
**post-fire recovery freeze 0.11**; champion__vs__arbalester: kiting 0.69,
recovery 0.25. So the standing that is a DECISION rather than collision
physics is:

1. **E9's post-fire recovery freeze** (`fireRecovery`, 0.20–0.43 s per
   cycle) — measured on the RANGED corpus ("over kiting cycles",
   ranged-vs-ranged) where it is real and stays; the C1 ranged-vs-MELEE
   tapes show a hunted kiter running again the moment the missile leaves
   (its single 0.62 s halt ≈ hand_cannoneer attack_delay 0.43 + 0.15 stop
   overhead — pre-shot only, no post-shot component).
2. **The R5B reloading park** (the settle arm), reachable mid-reload when
   the unit's own target is not melee.

The hunted/un-hunted split is what reconciles the two tape measurements, and
it is exactly the flag's gate.

## The rule

With `C4.fleeDuringReload` on, a FOOT (non-mounted, non-siege — see the
refinement section) RANGED unit that is

- **(a) mid-reload** — `attackCooldown > 0`, it cannot fire this tick — and
- **(b) hunted** — at least one living MELEE enemy's `target === this`
  (engine target bookkeeping; no distance constant, no timer constant)

**keeps moving through the reload window** via the EXISTING kite arm — the
same `moveAwayFromTarget(dt, allUnits, kiteSteering(...))` call, so the
basis is E1's orbit waypoint when `E1.orbitKite` is on and today's radial
otherwise, with all steering/avoidance/smoothing/arena terms unchanged.
Concretely the two parks stop holding a hunted unit: the recovery freeze is
bypassed (the timer still ticks down; it still binds the un-hunted), and the
kite arm outranks the settle park.

Not touched, by construction:

- **Firing is never delayed.** The predicate requires `attackCooldown > 0`,
  so at reload expiry the tick belongs to canFireNow/stop-to-fire exactly as
  today; `wasMoving` is written by the same arms that always wrote it, so
  the halt cost at fire time is unchanged. A degenerate
  recovery-outlasts-reload state re-freezes (pinned by test): C4 can never
  manufacture a moving launch.
- **The committed windup** still freezes (animation in flight — the same
  refusal C2A recorded).
- **Scope**: `minAttackRange > 0` (Siege Onager, Heavy Scorpion) is excluded
  by the same clause kiteSteering/C2A use — the C1 corpus excluded siege by
  construction. Ranged-vs-ranged is unreachable (no melee hunter exists);
  melee units never read any of it (isRanged gate + they never enter the
  ranged branch).
- **Flag OFF is structural**: `c4FleeDuringReload()` returns false before
  reading anything, so every caller composes its pre-C4 expression.
  Verified three ways: default run byte-identical to `--c4 off`; the full
  234×20 control run reproduces the 0731 baseline board exactly (201/234,
  zero winner flips, max |HP-pts delta| 0.000); melee corpus (95 fights ×
  20 seeds) byte-identical to control in ALL FOUR gate configs.

Tests: `tests/js/engine/c4_flee_during_reload.test.mjs` (15 — defaults pin,
setC4 rejection, off no-op ×2, hunted-moves-through-recovery, whole-window
kiting, un-hunted unchanged, ranged-hunter/dead-hunter/siege/melee
exclusions + melee behavioral twin, fire-tick equality, freeze-rules-at-expiry
guard, settle-park outranked, rng purity).
`node --test tests/js/engine/`: **375/375 green** (360 + 15).
parity_check.mjs deliberately not consulted (stale golden panel, campaign-end
recapture queued).

## Iteration — 44-fight subset, 3 seeds, tapebox, tape spawns

Families: champion__vs__arbalester ×6, champion__vs__heavy_cav_archer ×9,
halberdier__vs__heavy_cav_archer ×6 (control),
hand_cannoneer__vs__{heavy_camel,paladin,hussar} ×6 each,
heavy_cav_archer__vs__paladin ×5 (new family, truth paladin 5/5). Configs:
(a) shipped defaults; (b) `--e1 orbitKite --c3 postSwingPlant --c4
fleeDuringReload`; (c) `--e1 orbitKite --c4 fleeDuringReload`; (d) `--c4
fleeDuringReload` alone. (a) reproduces the C3 round's anchors exactly
(champ dmg/run 145.0, camel 588.0, HC land 85.7 %) — harness validated.

### Winners (tape-matched) / mean HP-pts per family

| family (n) | (a) default | (b) E1+C3+C4 | (c) E1+C4 | (d) C4 |
|---|---|---|---|---|
| champion__vs__arbalester (6) | 6/6 / 1.9 | **6/6 / 25.2** | 0/6 / 50.3 | 6/6 / 8.9 |
| champion__vs__heavy_cav_archer (9) | 8/9 / 18.4 | 1/9 / 24.4 | 1/9 / 26.9 | 8/9 / 14.3 |
| halberdier__vs__heavy_cav_archer (6) | 6/6 / 4.4 | **6/6 / 12.9** | 6/6 / 7.8 | **0/6 / 17.2** |
| hand_cannoneer__vs__heavy_camel (6) | 6/6 / 18.2 | 6/6 / 12.2 | 6/6 / 13.4 | 6/6 / 9.5 |
| hand_cannoneer__vs__paladin (6) | 5/6 / 22.8 | 5/6 / 23.3 | 5/6 / 25.6 | 5/6 / 22.1 |
| hand_cannoneer__vs__hussar (6) | 4/6 / 22.6 | 4/6 / 23.7 | 4/6 / 24.4 | 4/6 / 24.1 |
| heavy_cav_archer__vs__paladin (5) | 5/5 / 4.3 | 5/5 / 3.6 | 5/5 / 5.2 | 5/5 / 12.4 |
| TOTAL | 40/44 | 33/44 | 27/44 | 34/44 |

The headline: **champion__vs__arbalester recovers under the full
composition** — E1+C3 alone had it 0/6 at dmg/run 720 (the champions wiping
the ball); adding C4 returns it to 6/6. The (c) column shows C4 without the
plant does NOT save it (0/6): the arb only banks the head start the plant
grants — C3 and C4 are the two halves of one measured exchange. And (d)
shows C4 alone breaks the halberdier control (0/6: the HCA now escapes a
chaser that never plants, interval 4.20 → 4.77 vs tape 3.32) — like C3, C4
is a *pairing* mechanism, safe only composed.

### KPIs (3-seed subset; 20-seed full-gate values in §Full gate)

| KPI | (a) | (b) E1+C3+C4 | (c) E1+C4 | (d) C4 | tape / target |
|---|---|---|---|---|---|
| champion dmg/run, champ__vs__arb | 145.0 | **490.0** | 720.0 | 255.0 | band 127–603 (ledger ~603) |
| camel dmg/run, HC__vs__camel | 588.0 | **520.7** | 539.0 | 484.0 | ~273 (~390 first-order) |
| HC land rate, same family | 85.7 % | 83.6 % | 86.8 % | 87.0 % | hold ~85 % |
| camel swing interval | 2.02 | **2.52** | 2.04 | 2.02 | 2.51 |
| paladin interval, HC__vs__paladin | 1.92 | 2.30 | 1.93 | 1.92 | 3.21 |
| halberdier interval (control) | 4.20 | 3.02 | 3.02 | 4.77 | 3.32 |
| champion interval, champ__vs__HCA | 2.02 | 2.07 | 2.02 | 2.02 | 2.77 |

The camel's swing interval lands ON the tape (2.52 vs 2.51) under the full
composition. champ_vs_arb's champion dmg/run collapses 720 → 490 — inside
the tape band, first time any config has done it with the orbit on.

### Geometry (dump_kite_tracks, 3 seeds, per-family; move bar 0.02 tiles/0.1 s)

| family | cfg | runMed | runP90 | r-slope | corner | wall-death |
|---|---|---|---|---|---|---|
| champion__vs__arbalester | E1+C3 | 1.10 | 1.10 | +0.075 | 1.00 | 0.56 |
| | **E1+C3+C4** | 1.10 | **1.40** | +0.079 | **0.61** | **0.14** |
| hand_cannoneer__vs__heavy_camel | E1+C3 | 2.90 | 3.00 | +0.050 | 0.99 | 0.64 |
| | **E1+C3+C4** | 2.90 | 3.00 | +0.049 | 0.91 | 0.65 |
| hand_cannoneer__vs__hussar | E1+C3 | 2.20 | 3.00 | +0.097 | 1.00 | 0.71 |
| | **E1+C3+C4** | **2.80** | **3.20** | +0.125 | 1.00 | 0.62 |
| hand_cannoneer__vs__paladin | E1+C3 | 2.80 | 3.00 | +0.135 | 1.00 | 0.56 |
| | **E1+C3+C4** | 2.70 | 3.00 | +0.127 | 1.00 | 0.60 |
| heavy_cav_archer__vs__paladin | E1+C3 | 0.70 | 0.70 | +0.069 | 1.00 | 0.62 |
| | **E1+C3+C4** | 0.70 | 1.10 | **−0.013** | **0.16** | **0.38** |
| champion__vs__heavy_cav_archer | E1+C3 | 0.70 | 0.70 | −0.039 | 0.00 | 0.00 |
| | **E1+C3+C4** | 0.80 | 1.10 | −0.067 | 0.00 | 0.00 |

The foot shooters' continuous runs sit in the tape's 2.7–3.4 s band under
the composition (they were already near it under E1+C3 — the orbit, not the
run-commitment, bought most of the run length; C4's marginal value is the
arb's p90 1.10 → 1.40 = the tape's own 1.38 moveMed, and the escape
conversion below). Where C4 visibly converts runs into survival:
champ_vs_arb wall-death 0.56 → 0.14 and cornering 1.00 → 0.61;
HCA_vs_paladin r-slope crosses to the tape's negative sign (+0.069 → −0.013)
with cornering 1.00 → 0.16.

## Full gate — 234 fights × 20 seeds

Baseline: `data/calibration/runs/20260731T154530Z-post-0731-ingest-baseline.json`
(201/234). This round's boards, same directory:
`…162254Z-c4-full-control.json`, `…162258Z-c4-full-e1c3c4.json`,
`…162302Z-c4-full-e1c3c4-p1.json`, `…162307Z-c4-full-e1c3c4-p2.json`,
`…162311Z-c4-full-e1c3c4-p1p2.json` (P1/P2 = `--r5d1
reducedDamageHits` / `trailingWindowLead`).

**Control**: winners and HP-pts identical to the baseline board (0 flips,
max pts delta 0.000). **Melee**: 95 fights × 20 seeds byte-identical to
control in all four configs.

| config | TOTAL | melee | mixed | siege | ranged | fire-lancer | agr |
|---|---|---|---|---|---|---|---|
| baseline / control | 201/234 | 68/95 / 7.2 | 81/86 / 10.9 | 22/23 / 9.4 | 8/8 / 1.8 | 22/22 / 5.2 | 0.859 |
| E1+C3+C4 | 194/234 | 68/95 / 7.2 | 74/86 / 14.1 | 22/23 / 10.9 | 8/8 / 1.8 | 22/22 / 5.7 | 0.829 |
| E1+C3+C4+P1 | **195/234** | 68/95 / 7.2 | 74/86 / 14.8 | **23/23** / 10.3 | 8/8 / 1.9 | 22/22 / 5.8 | 0.831 |
| E1+C3+C4+P2 | 188/234 | 68/95 / 7.2 | 68/86 / 15.0 | 22/23 / 9.3 | 8/8 / 1.5 | 22/22 / 5.7 | 0.803 |
| E1+C3+C4+P1+P2 | 188/234 | 68/95 / 7.2 | 68/86 / 16.1 | 22/23 / 8.8 | 8/8 / 1.7 | 22/22 / 5.9 | 0.805 |

(Category split here separates fire-lancer and siege from "mixed"; the
briefing's 68/95 melee, 8/8 ranged, fire-lancer 20/20-shaped totals map onto
the same 201.)

**Canaries** (champ_vs_arb / halb_vs_HCA / arb_vs_steppe / HC_vs_camel):
**4/4 in E1+C3+C4 and +P1** — including champion__vs__arbalester 6/6, the
family E1 alone loses 0/6. +P2 and +P1+P2 break champ_vs_arb 0/6 (P2's 28 %
cut in arb output re-tips the wiped-ball regime); P2 stays blocked.

**Family winner changes vs baseline** (all configs):

| family | base | E1C3C4 | +P1 | +P2 | +P1P2 |
|---|---|---|---|---|---|
| champion__vs__arbalester | 6/6 | 6/6 | 6/6 | 0/6 | 0/6 |
| champion__vs__heavy_cav_archer | 8/9 | 1/9 | 1/9 | 1/9 | 1/9 |
| hand_cannoneer__vs__heavy_scorpion | 0/1 | 0/1 | **1/1** | 0/1 | 0/1 |

**KPIs at 20 seeds**:

| KPI | control | E1C3C4 | +P1 | +P2 | +P1P2 | target |
|---|---|---|---|---|---|---|
| champ dmg/run, champ_vs_arb | 145 | **490** | 490 | 720 | 720 | 127–603 |
| camel dmg/run, HC_vs_camel | 590 | **494** | 587 | 393 | 551 | ~273 |
| HC land rate, HC_vs_camel | 85.3 % | 82.4 % | 86.1 % | 89.4 % | 90.9 % | ~85–86 % |
| champ dmg/run, champ_vs_HCA | 943 | 960 | 960 | 960 | 960 | ~603 |

**Every fight ≥ 2 pts worse than baseline** (per-family, shared repeat
deltas; full per-fight lists reproducible from the boards):

E1+C3+C4 (51 fights): champion__vs__arbalester ×6 (+20.5…+24.0, winners
HELD 6/6 — the fights are much closer than the tape's near-shutout),
siege_onager__vs__elite_steppe +11.0, siege_onager__vs__paladin +10.7,
champion__vs__hand_cannoneer +10.7, halberdier__vs__heavy_cav_archer ×5
+10.0, halberdier__vs__siege_onager +8.9, arbalester__vs__elite_fire_lancer
+7.6, champion__vs__heavy_cav_archer ×8 +7.1 (the 8 lost winners — ALL of
the config's net cost), elite_fire_lancer__vs__hand_cannoneer +5.8,
siege_onager__vs__heavy_camel +5.5, elite_steppe__vs__arbalester +4.1,
arbalester__vs__elite_steppe ×6 +4.1, hand_cannoneer__vs__elite_steppe
+3.6, heavy_cav_archer__vs__elite_steppe ×6 +3.6,
heavy_cav_archer__vs__elite_elephant +3.1, imp_elite_skirm__vs__elite_elephant
+2.8, heavy_cav_archer__vs__heavy_camel ×6 +2.8, heavy_cav_archer__vs__paladin
+2.4, halberdier__vs__heavy_scorpion +2.2, champion__vs__siege_onager +2.2.
+P1 is the same list ±1 (51). +P2/+P1P2 (49) swap the champ_vs_arb rows to
+38.0…+41.5 with the 6 winners lost. NOTE the siege-attacker rows
(siege_onager_vs_* +5.5…+11.0, *_vs_siege_onager/heavy_scorpion +2.1…+8.9,
winners all held): siege victims carry `is_ranged = 1` in the combat dicts,
so C3's plant fires on melee units swinging at siege — the scope note C3's
own doc flagged for the enable round. C4 excludes siege kiters and is not
the source.

## Refinement round — two evidence-based scope corrections, re-gated

Coordinator-directed, same session. Both are CLASS facts from the dat's own
armor-class table (`BattleUnit.hasArmorClass`), not invented thresholds:

1. **C4 → FOOT ranged victims only.** C1 M2's class split is explicit: the
   run-commitment is a foot-shooter fact; the mounted heavy_cav_archer's
   duty cycle is already engine-correct (0.688 vs tape 0.659) and its tape
   stopMed 1.26 s = its own windup + recovery — the tape's mounted archer
   pays its recovery even while hunted. A hunted unit carrying Cavalry (8)
   or Cavalry Archer (28) is no longer armed. This repairs the (d) breakage
   (halb_vs_HCA control 0/6 → **6/6**, champ_vs_HCA back to **8/9**,
   subset (d) total 34/44 → **40/44** = the (a) default) and removes the
   HCA-as-kiter pts regressions (+2.4…+3.9 rows gone; HCA_vs_paladin
   reverts to E1+C3 geometry — the r-slope sign flip unscoped C4 bought
   there was mounted run-commitment, i.e. a compensating error, and goes).
2. **C3 plant → siege victims excluded.** The plant was measured on chasers
   pursuing ranged kiters; siege carries `is_ranged = 1` in the dicts, so
   chasers planted against onagers/scorpions — the traced source of the
   siege-attacker pts regressions. The victim test now excludes armor class
   20 (Siege Weapons) — deliberately NOT `minAttackRange > 0`, whose 1.0 on
   the Imperial Elite Skirmisher would wrongly exclude a foot kiter.
   Re-measure when the new onager tape lands. Effect on the gate: every
   siege row leaves the ≥2-pt list, siege pts 10.9 → 9.4 (= baseline), and
   +P1 holds siege **23/23**.

Foot-family results are UNCHANGED by both scopes (subset (b): champ_vs_arb
6/6 @ dmg/run 490, camel interval 2.52, all KPIs identical; geometry
identical for arb/HC families). Tests: +2 (mounted-hunted behaves as today;
siege victim never stamps) — suite **377/377**.

### Re-gate (234 × 20 seeds; boards `…163451Z-c4r-full-e1c3c4.json`, `…163455Z-c4r-full-e1c3c4-p1.json`)

| config | TOTAL | melee | mixed | siege | ranged | fire-lancer |
|---|---|---|---|---|---|---|
| baseline / control | 201/234 | 68/95 / 7.2 | 81/86 / 10.9 | 22/23 / 9.4 | 8/8 / 1.8 | 22/22 / 5.2 |
| E1+C3+C4 (scoped) | 194/234 | 68/95 / 7.2 | 74/86 / 15.4 | 22/23 / **9.4** | 8/8 / 1.8 | 22/22 / 6.0 |
| E1+C3+C4+P1 (scoped) | **195/234** | 68/95 / 7.2 | 74/86 / 16.2 | **23/23** / 8.8 | 8/8 / 1.9 | 22/22 / 6.1 |

Melee byte-identical (95 × 20 × both configs). Canaries **4/4** in both.
KPIs unchanged from the first gate (champ_vs_arb dmg/run 490, camel 494,
HC land 82.4 / 86.1 %). Winner changes vs baseline: champ_vs_HCA 8/9 → 1/9
(both configs), HC_vs_heavy_scorpion 0/1 → 1/1 (+P1 only). ≥2-pt list
shrinks 51 → 46 rows, now purely ranged-vs-melee/fire-lancer (headline
rows: champ_vs_arb ×6 +20.5…+24.0 winners held; champ_vs_HCA ×9
+8.8…+19.5 with the 8 lost winners; halb_vs_HCA ×5 +8.9;
arb_vs_steppe ×6 +4.1; HCA_vs_steppe ×6 +3.9; HCA_vs_camel ×6 +3.6).

**The champ_vs_HCA attribution is now proven, not inferred**: scoped C4
does not touch mounted kiters at all, and the family still sits 1/9 under
E1+C3+C4 — identical to the E1+C3 regime. The −7 is E1's orbit arming the
mounted ball while the chaser-contact residual (champion dmg/run 960 vs the
~603 enable bar) is unmodeled. It was never C4's cost.

### Gate decision

Success bar was ≥ 201 with canaries 4/4 and melee identical. Best config is
**195/234 — below the bar**, so **no defaults were flipped**: E1.orbitKite,
C3.postSwingPlant, C4.fleeDuringReload and R5D1.reducedDamageHits all stay
OFF, P2 stays OFF/blocked. The remaining −6 is one family (champ_vs_HCA −7,
+HC_vs_scorpion +1); the unlock is the champion-vs-mounted-archer contact
mechanism (E1's own knife edge), after which this exact gate re-runs.

## Verdict

The composed cycle now produces the tape escape where the tape shows one:
foot-shooter continuous runs in the 2.7–3.4 s band, the arb ball off the
wall (wall-death 0.56 → 0.14), champion dmg/run 720 → 490 (inside the
127–603 band), camel cadence on the tape's 2.51, and — for the first time
with the orbit on — **all four canaries held**. What the composition still
pays is one family, and it is the one C1 named: champion__vs__heavy_cav_archer
(8/9 → 1/9, the whole −7), the continuous-contact regime where the kiter
never leaves the champion's reach (engine inR 2.02 s/cycle, tape 0.66) and
champion dmg/run sits at 960 vs the ~603 enable bar — no amount of
run-commitment moves a kiter that is never out of contact. That residual is
a chaser-contact problem (and P2's own enable criterion), not a kiter-rhythm
one.

Scoreboard arithmetic: best config (E1+C3+C4+P1) is 195/234 vs the
baseline's 201 — net −6, all in champ_vs_HCA (−7) less HC_vs_heavy_scorpion
(+1). **All flags ship OFF**, same holding pattern as E1/C3: flip the trio
(and re-gate P1 with it) when the champ_vs_HCA contact mechanism lands.

## Files

- `apps/website/static/js/engine/constants.js` — `C4` flag object + `setC4`
  (rationale block cites C1 Table 2b and the state-level probe).
- `apps/website/static/js/engine/battle_unit.js` — `c4FleeDuringReload()`
  predicate (foot-only via armor classes 8/28); recovery-freeze bypass +
  kite-arm join in update()'s ranged branch; `hasArmorClass()` helper; C3
  stamp in `performAttackOn` now excludes armor-class-20 (siege) victims.
- `tools/simjs/calib_runner.mjs` — `applyC4Spec` + `--c4`, forwarded through
  `calib_worker.mjs` workerData; `tools/simjs/dump_kite_tracks.mjs` — `--c4`.
- `tests/js/engine/c4_flee_during_reload.test.mjs` (16 tests incl. the
  mounted-hunted pin); `tests/js/engine/c3_post_swing_plant.test.mjs`
  (+ siege-victim pin, 13).
- Boards: `data/calibration/runs/20260731T16*-c4-full-*.json` (first gate),
  `…-c4r-full-*.json` (scoped re-gate), + the labeled `c4-subset-*` /
  `c4r-subset-*` 3-seed boards. Geometry/KPI scratch scripts were
  session-scratchpad throwaways, reproducible from the commands in this doc.
