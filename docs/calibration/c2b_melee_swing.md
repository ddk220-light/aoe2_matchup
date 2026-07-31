# Phase C2-B — the melee swing: when it may begin, when it lands

Two rules, both stated flatly by the tapes, both wired behind a new `C2B` flag
object, **both shipped OFF**. Neither carries a constant of any kind.

| | |
|---|---|
| **C-b stop-to-swing** | REFUTED AT ITS PRICE. Real, live and directionally right (hits landed while the chaser is walking 19.8% → 14.8%), and it costs **3 melee winners and 9 melee sides** to buy 5 of the defect's 20 points. Shipped off. |
| **C-c windup-commit** | HALF OF IT WAS ALREADY SHIPPED. Every `frame_delay > 0` melee unit has always landed its committed swing out of reach; the flag only extends that to `frame_delay`-0 units, and there it is **measurably inert** (resolution reach 0.985 → 0.981, i.e. away from the tape's 1.43). Board holds/nudges up, winners hold 194/216. Shipped off pending the kiter fix, which is the thing that makes it matter. |
| **Net** | Corpus **byte-identical to `0e2dbc5`** as shipped. `--c2b off` is bit-identical by construction, hash-verified 48/48. Tests 242 → 260. |
| **The one number that decides the round** | With BOTH rules on, `champion__vs__heavy_cav_archer` goes **8/9 → 1/9** — the same knife-edge C1 M5 measured for P2, tipped this time from the chaser's side. Corpus 194 → 184. |

---

## 0. What was actually found, before any rule

The brief asked for two rules. Reading the engine first turned one of them into
half a rule and a scope question.

**C-c's delay > 0 half is not missing — it has always been there.** The melee
`committedAttack` branch (`battle_unit.js`, the `else if (this.committedAttack)`
arm of `update()`) tests `target.state !== "dead"` at the landing and **nothing
else**. `performAttackOn()` does not test reach either. So a paladin (0.433 s),
heavy camel (0.333), elite steppe lancer (0.217), hussar (0.167) or elite
elephant (0.167) already commits at contact and lands on schedule however far
its victim has walked. Measured on the BASE engine, flag off, victim teleported
to 26x reach mid-windup: **the blow lands.** That is now pinned by a test with
the flag explicitly OFF, so a later round cannot delete the property by
accident.

This reframes C1 M3's `dHit ≈ 0.99 * reach`: it is **not** the landing rule's
fault. It is M2's finding arriving from the other side — the engine's kiter
opens **0.05 tiles** of radial separation over a whole reload against the
tape's **1.03**, so there is nothing for a committed swing to miss.

---

## 1. What C-b is, and where it sits

Pre-change swing gating, `apps/website/static/js/engine/battle_unit.js`
`update()`, the `else` (melee) arm of the `isRanged()` split:

```
1867  } else if (this.committedAttack) {      // windup ticking; NO reach test
1886  } else if (this.inRange()) {
1887      if (this.attackCooldown <= 0) {
1888          if (this.attackDelay > 0) { commit }
1895          else { performAttack() }         // <- delay-0: decided AND resolved
1899      } else { stand }                     //    in the same tick
1902  } else if (this.meleeMoveLocked()) { plant }
1917  } else { moveTowardTarget() }
```

A melee unit in reach never moves, so the 19.8% of engine hits that land while
the chaser is walking are **arrival swings**: the unit walks, crosses the reach
line, and swings out of the step on the very next tick.

**C-b inserts a halt.** If the unit was stepping on the tick its cooldown came
up, it stands this tick and the swing begins next tick, from a stop. Nothing is
charged beyond the tick — no `RANGED_STOP_OVERHEAD` transplant, no reload
change.

Two design points that are load-bearing:

* **The movement fact is a new melee-only field, `meleeWasMoving`**, not
  `wasMoving`. `wasMoving` is not maintained on every melee branch (the
  in-reach stand and the delay-0 swing both leave it stale), so a unit that
  walked in while reloading and then stood for a second would still read as
  moving — exactly the over-charge R5b removed from the ranged side. The new
  field is written by every melee arm of `update()`.
* **It records the unit's own locomotion DECISION, not its displacement.** A
  planted unit shoved by `resolveCollisions` has not decided to walk and is not
  gated. C1 M3 makes the same distinction when it separates a chaser step of
  0.046–0.24 tiles (walking) from body jitter.

**The rule's content is the RE-TEST, not the delay.** After the halt, `inRange()`
is asked again — so a victim that used the halt to leave has genuinely escaped
that swing and the chaser goes back to closing. One tick is 0.0167 s, which at
1.54 t/s is 0.026 tiles; the rule can only bite on a swing whose victim was
already within a body-hair of the reach lip. That is exactly the population the
tape says is being lost, and exactly why the rule is worth measuring rather than
assuming.

## 2. What C-c is, after §0

Reach is tested once, at swing START; the blow lands on a LIVING victim however
far it drifted. For `frame_delay > 0` that is the shipped engine and the flag
does not touch it. **The flag's entire content is the `frame_delay`-0 case** —
champion and halberdier, the two heaviest chasers in the corpus — where the
swing is decided and resolved in the same tick, leaving no interval to drift in.
C-c gives that swing the engine's smallest resolvable interval, **one tick**, and
no more: `{ timeLeft: 0, zeroDelay: true }`, resolved on the next `update()`.

The zero-delay arm resolves through `performAttack()` rather than
`performAttackOn()`, so a melee unit with `extra_projectiles` or a first-attack
bonus keeps every strike it has today; the only thing that changes for such a
unit is which tick the identical call happens on. Pinned by test.

### The `frame_delay`-0 investigation, and the decision

**Question.** The tape lands `frame_delay`-0 swings at 1.43x reach (champion:
median 0.91 tiles against a 0.62-tile reach, p90 1.52). What in the engine or
the data mechanistically supports a lag between a delay-0 swing's start and its
damage frame?

**Answer: nothing.**

* `attack_delay` **IS** the game's own damage frame. `aoe2x/extract/
  extract_units.py:471-472` reads `type_50.frame_delay` and divides by 60. It is
  `0` for champion and `0` for halberdier — verified end-to-end in
  `data/calibration/combat_dicts.json` (`Chinese|champion` `attack_delay: 0`,
  `Chinese|halberdier` `attack_delay: 0`), so it is a real dat value, not a
  `getattr` default lost in extraction.
* The only other swing-shaped timers in `battle_unit.js` are `attackAnimTimer`
  and `animHold`, both stamped by `triggerAttackAnim()` off the attack
  **sprite sheet** and read only by the renderer. They are draw state; nothing
  in the sim consults them.
* `MELEE_SWING_RECOVERY_S` (E15b rule 1) is a POST-swing movement lock and it is
  shipped `0` (refuted). It cannot supply a pre-landing interval, and it is a
  different quantity in any case.

**What would close the gap, and why it is not here.** Reproducing 1.43x needs
the damage frame to lag the swing start by ~0.2 s (a 1.54 t/s HCA covers 0.31
tiles in 0.2 s, and 0.62 + 0.31 = 0.93 against the tape's measured 0.91). The
nearest thing in the codebase is `RANGED_STOP_OVERHEAD = 0.15`, the measured
stop/turn cost for RANGED units — the same physical act, fitted on ranged tape.
Transplanting it to melee would be a fitted constant, so it is not here. **The
one tick this rule can honestly give is 0.0167 s, and it carries a champion's
resolution reach from 0.99x to at best ~1.03x, not 1.43x.** The gap is reported,
not closed. If a future round wants it, the evidence it needs is a melee-side
measurement of the stop/turn interval, not a re-use of the ranged number.

---

## 3. Emergence — the three C1 M3 routes, measured

`node tools/simjs/c1_chase_probe.mjs --tags-file <c1 corpus> --seeds 20 --c2b <spec>`
then `c1_chaser_cadence.py --section all`. 86 recordings, 29 melee-swing
families (the four `elite_fire_lancer`-as-chaser families excluded exactly as
the C1 report excludes them). `base` reproduces the published report to the
digit, which is the check that the rig is the same one.

```
quantity                                        TAPE      base       C-b       C-c      both
------------------------------------------------------------------------------------------------
hits landed while the chaser is walking, %     0.000   19.8413   14.8148   22.2222   17.1429
hits landed on a STOPPED victim, %            14.300   70.2381   74.6032   70.2381   74.6032
resolution reach  dHit / reach                 1.430    0.9854    0.9819    0.9814    0.9752
chaser step at the landed hit, tiles           0.000    0.0455    0.0306    0.0456    0.0318
chaser hit excess  E/T                         1.000    1.4391    1.3849    1.4326    1.4356
chaser swing-interval ratio  T/E               1.000    1.2230    1.2230    1.2466    1.2466
cycles that lose contact, %                   97.200   54.0541   48.7500   58.4906   48.7500
seconds in reach per cycle                     0.657    1.8105    1.8603    1.8105    1.8744
```

**Against the brief's predictions, honestly:**

| predicted | measured |
|---|---|
| hits-while-walking 19.8% → **0** | → **14.8%** (C-b). Directionally right, a quarter of the way. |
| resolution reach 0.99x → **toward 1.43x** | → **0.981x** (C-c alone), **0.975x** (both). It moved the WRONG WAY. |
| chaser interval ratio → **toward 1.22 → 1.0** | **1.223 → 1.247**. Wrong way. |
| contact-limited cycle | cycles that lose contact **54.1% → 48.8%**, seconds in reach **1.81 → 1.87**. Wrong way. |

Why hits-while-walking does not reach 0: the statistic is decided over a **10 Hz
sample window** with a 0.02-tile bar, and one tick of halt is 0.0167 s. A chaser
that walked for four ticks of the window and then halted for one still registers
as moving. Driving that cell to 0.0% needs the chaser stationary for the whole
0.1 s before the blow — i.e. a swing interval on the order of the tape's ~0.2 s
lag, which §2 has just refused to invent. **The 0.0% cell is not reachable by a
tick-granular halt, and this is the honest ceiling of C-b as specified.**

Why the contact metrics move the wrong way: they are kiter-side quantities. C1
M1/M2 said so ("the proximate cause sits on the KITER, not the chaser") and the
measurement agrees — with the kiter still opening 0.05 tiles per reload, slowing
or shifting the chaser's swing does not create contact loss, it just leaves the
chaser standing in reach for slightly longer. **Nothing here can be judged until
the sibling's kiter break lands.** That is a statement of what was measured, not
an excuse: on THIS engine, both rules are inert-to-harmful on the very metrics
they were specified against.

---

## 4. Marginal boards

### 4a. Melee gate — `melee_hp_report.py`, 83 fights x 2 sides x 20 seeds

```
                       base       C-b       C-c      both
all_melee n=166
  <= 10 HP-pts          126       117       126       118
  <=  5 HP-pts           98        96       102        94
  <=  1 HP-pt            73        70        75        68
  mean |err|, pts       6.42      6.90      6.25      6.79
  median |err|, pts     2.42      3.67      2.34      3.67
  melee winners        67/83     64/83     67/83     64/83
  basic-melee winners  33/35     33/35     33/35     33/35
```

**The board does NOT hold under C-b.** The brief's expectation — "in scrums
engaged units are already stationary, so melee-vs-melee should barely move" —
is false as stated, and the reason is measurable: C-b moves **83/83** melee
fights and cuts melee damage events by **1.0%** (457 620 → 452 860). Scrum
units are planted *while engaged*, but they walk constantly *between*
engagements — after a kill, after being shoved out of reach, closing on a new
lock — and every one of those arrivals now pays a tick. The steppe/elephant
half of the gate is knife-edge (`steppe_eleph` 68 → 59 within-10) and 1% of
damage decides it.

C-c holds the gate and nudges it (within-5 98 → 102, within-1 73 → 75, mean
6.42 → 6.25). That movement is small enough that it is **not** offered as a
reason to ship it.

### 4b. Full corpus — 216 fights x 20 seeds

```
category            base       C-b       C-c      both
ranged-v-ranged      6/6       6/6       6/6       6/6
ranged-v-melee     97/102    97/102    97/102    90/102
melee-v-melee      67/83     64/83     67/83     64/83
siege              24/25     24/25     24/25     24/25
------------------------------------------------------
TOTAL             194/216   191/216   194/216   184/216
mean per-seed agr  0.8981    0.8829    0.8979    0.8505
```

Canaries, all four families, all four configurations:

```
canary family                            base      C-b      C-c     both
champion__vs__arbalester                  6/6      6/6      6/6      6/6
hand_cannoneer__vs__heavy_camel           6/6      6/6      6/6      6/6
heavy_cav_archer__vs__elite_steppe        6/6      6/6      6/6      6/6
champion__vs__heavy_cav_archer            8/9      8/9      8/9      1/9   <---
```

### 4c. THE INTERACTION — the finding of the round

C-b alone costs 3 winners. C-c alone costs 0. **Together they cost 10**, and
every one of the seven extra losses is a single family: `champion__vs__
heavy_cav_archer` **8/9 → 1/9**.

That is the identical failure C1 M5 measured for P2, arriving from the other
side of the same knife edge. M5's numbers: the engine's champions already
deliver **98.2%** of the HCA army's max HP per run against the tape's **62.8%**,
so the family is held by a hair, and P2's 28% cut to HCA output tips it. C-b+C-c
tip it by cutting the CHAMPION instead — combined they take another slice out of
the chaser's output and the same nine recordings fall over.

Read the other way, this is a **confirmation of M5's enable criterion, and a
warning about it**: champion damage per run has to fall from 943 to ~603 (0.64x)
for P2 to be safe, but every point of that fall has to come from the kiter
leaving, not from the chaser swinging less — because the family flips the moment
the chaser's output moves at all while the kiter still stands there.

### 4d. Blast radius (base vs each rule, whole corpus x 20 seeds)

```
group                      files   C-c identical   C-b identical
melee-vs-melee              1660       920 (37/83 moved)     0 (83/83 moved)
mixed (melee vs ranged)     2040      1440 (30/102 moved)    0 (102/102 moved)
ranged-vs-ranged             120       120 (0/6)           120 (0/6)
siege-bearing                500       420 (4/25 moved)    180 (16/25 moved)
```

**Ranged-vs-ranged is byte-identical under both rules, 120/120.** The scope
declared at the top of the flag object holds exactly: every fight with **no
melee unit in it** is byte-identical, including all nine ranged-vs-siege and
siege-vs-siege fights (`arbalester__vs__heavy_scorpion`,
`heavy_scorpion__vs__siege_onager`, … ). The siege fights that DO move are the
six/sixteen with a melee side (`champion__vs__siege_onager`,
`heavy_scorpion__vs__paladin`, …) — that is the scope working, not leaking:
these rules govern the melee unit, and a champion walking at an onager is a
melee unit.

---

## 5. Off-switch

`C2B.stopToSwing = false, committedSwingLands = false` (the shipped default;
`calib_runner.mjs --c2b off`) is bit-identical to `0e2dbc5`
**by construction**: the only statement the off path executes that base did not
is a write to `meleeWasMoving`, a field nothing reads while the flags are off.

Verified anyway over a mixed 16-fight panel (6 melee-vs-melee, 4
ranged-vs-ranged, 6 mixed) x 3 seeds, sha1 of the whole record including the
damage stream: **48/48 identical**, panel hash
`42c6d33acd06e7e13f05b89ae02eda971cc0798e` on both engines.

---

## 6. Enable criteria

Neither rule is refuted as a MECHANISM. Both are refuted as improvements *to
this engine*, for the same reason: they are chaser-side rules and the defect is
kiter-side.

**C-c is enabled when** the kiter's contact break lands (the sibling's rule) and,
re-measured on the C1 rig over the 29 melee-swing families, `dHit / reach` moves
**up** from 0.985 rather than down — i.e. once the victim actually walks during a
windup, the committed swing is landing past reach. Its board must still hold
194/216 with `champion__vs__heavy_cav_archer` at 8/9. It is the cheaper of the
two and should be re-gated first.

**C-b is enabled when** BOTH of the following hold on a re-run:

| quantity | today (C-b on) | required |
|---|---|---|
| melee gate, within-10 of 166 | 117 | **>= 126** (no worse than base) |
| melee winners | 64/83 | **>= 67/83** |
| corpus winners | 191/216 | **>= 194/216** |
| `champion__vs__heavy_cav_archer` | 8/9 | **8/9**, with C-c also on |

and its own signature is actually produced: hits landed while the chaser is
walking materially below 14.8%, at a chaser step at the landed hit materially
below 0.031 tiles. If the 10 Hz measurement floor (§3) means that signature is
unreachable without a melee stop/turn interval, then C-b as specified cannot be
validated and the round's honest conclusion is that **the missing quantity is a
melee stop/turn duration, and it has to be measured off the tape before it can
be spent.**

---

## 7. Surprises

1. **Half of C-c was already shipped**, silently, since the `committedAttack`
   branch was written — and the C1 report's 0.99x-reach headline is therefore
   not evidence against the engine's landing rule at all, it is more evidence
   about the kiter. It is now pinned by a test that runs with the flag OFF.
2. **Melee-vs-melee is not "barely moved" by a chaser-side halt.** C-b moves
   83/83 melee fights and 1.0% of melee damage. Scrum units are planted while
   engaged and walking constantly between engagements, and the gate is decided
   in the second population.
3. **C-c pushes the resolution reach the WRONG WAY** (0.9854 → 0.9814). One tick
   of commit buys nothing when the victim does not move, and the halt leaves the
   chaser marginally deeper inside its own reach when the blow lands.
4. **The two rules are worse than the sum of their parts** (−3 and 0 alone,
   −10 together), and the entire non-additive loss is one family that C1 M5 had
   already identified as sitting on a knife edge.
5. **`champion__vs__heavy_cav_archer` is now known to be flippable from BOTH
   sides** — P2 tips it by cutting the HCA, C-b+C-c tip it by cutting the
   champion. Any future round that touches either side of that fight should
   expect to be gated by it.
