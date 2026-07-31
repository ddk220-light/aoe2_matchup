# E15 step 1 — where does a melee unit's walking come from?

Measurement-only report. **No engine changes are proposed or made here**; the
mechanism design is left to the main session. Everything below is produced by
`tools/simjs/melee_walk_forensics.py`, one implementation fed either a
recording or a sim run, so every tape number and engine number in the same row
is literally the same statistic.

```
PYTHONPATH=. python tools/simjs/melee_walk_forensics.py \
    --sim-runs-dir D:/AI/aoe2_golden/simruns_e15_base [--by-slug] [--fights ...]
```

Corpus: the 31 pure-melee recordings (62 sides) of
`data/calibration/manifest.json`. Engine stream: the E14 engine at
`31f7339`, tapebox arena, seed 1 (`calib_runner.mjs` + `dump_sim_units.mjs`).

---

## 0. READ THIS FIRST — the premise of E15 was a measurement bug

E14 handed E15 the headline "a tape melee unit is moving 44.7% of the fight
and moving *with a foe inside its own reach* 28.7% of it, against an engine
that manages 21.5% / 1.7% — the walk is the last measured gap."

**That comparison was computed with the wrong reach.** Every position-based
forensic through E14 used

```
reach = attack_range + collision_size_attacker + collision_size_defender   # tiles
```

The engine's own `inRange()` (`battle_unit.js:494`) is

```
reach = attack_range * TILE_SIZE + MELEE_RANGE_BUFFER(5px) + radiusA + radiusB
        with radius = max(MIN_PHYSICS_RADIUS_PX = 5px, collision_size * 30)
```

For two infantry that is 0.567 tiles, not 0.40. The old number sits **below**
`resolveCollisions`' hard floor (`radiusA + radiusB + 1px`), so "a living foe
is inside my reach" was *unsatisfiable* for every 0-range melee unit.
`melee_lock_forensics.walk_share` returns `None` in that case and its driver
skips the side — so **51 of the 62 melee sides were silently dropped** and
every "moving WITH a foe in reach" figure ever printed came from the 11
range-1 `elite_steppe` sides alone.

The formula is not taken on the engine's word either. Over all 31 recordings,
the attacker→victim distance at the instant of a landed hit has a **median
within 0.02 tiles of the formula for all 42 (attacker, defender) class pairs**
(e.g. champion→halberdier tape 0.494 / formula 0.567; heavy_camel→hussar
0.669 / 0.667; elite_steppe→paladin 1.221 / 1.667). The long upper tail on
tape (p99 up to 2.2 tiles) is attack-delay — a swing launched in contact still
lands after the victim has walked off — which is a damage-application rule,
not a reach.

`engine_reach()` now lives in `tools/simjs/melee_bout_forensics.py` and both
scripts use it. With it, the headline reverses:

| | tape | engine (E14) |
|---|---|---|
| moving, any time | **39.21%** | **40.90%** |
| moving WITH a foe in reach | 13.60% | 8.28% |

**The engine is not under-walking. It already walks marginally more than the
tape.** There is no missing walk to build. What is wrong is *where the walking
goes* and, downstream of that, how much of the fight is spent in contact.

---

## 1. Walk decomposition

### Method

A unit's intent is read backwards off the only ground truth both streams
share, the damage stream. Run-length-encode each attacker's victim sequence;
run *k* (victim `v_k`, first hit `f_k`, last hit `l_k`) owns the interval
`(l_{k-1}, l_k]`, split into

* **ACQUISITION** `(l_{k-1}, f_k)` — getting to `v_k`. Sub-classified by what
  ended the previous run: the previous victim **died** (`travel_postkill`) or
  was still **alive** (`travel_livebreak` — contact was lost with a foe that
  could still be fought). The interval before a unit's *first* hit is
  `travel_open`.
* **SUSTAINED** `[f_k, l_k]` — landing hits on `v_k`. Split by whether the
  lock is inside reach (`micro_follow`) or outside it (`pursue_*`, split by
  whether the victim itself moved that frame).

Samples after a unit's last hit are censored (it died or the fight ended) and
excluded — that is the ~21% / ~12% the classified totals fall short of 100%.

Thresholds, all stated once and used everywhere: positions are the streams'
native 10 Hz; a unit counts as **walking** when it moves > **0.02 tiles**
between consecutive frames (the slowest melee unit here covers 0.10 tiles per
frame, so this is a fifth of a real step — above position quantisation, far
below a walk); "victim moved" uses the same 0.02.

### All melee, 62 sides

`occ` = % of all alive samples in this state · `walk` = % of all alive samples
this state contributes to walking · `rate` = % of the state's own samples
spent moving.

| state | t occ | e occ | t walk | e walk | t rate | e rate |
|---|---|---|---|---|---|---|
| pursue_victim_moved | 1.97% | 0.20% | 0.83% | 0.17% | 41.9% | 85.1% |
| pursue_victim_still | 6.23% | 0.21% | 0.54% | 0.14% | 8.7% | 65.4% |
| micro_follow (in reach of lock) | 18.20% | **35.75%** | 0.14% | 0.32% | 0.8% | 0.9% |
| travel_postkill | 13.77% | 14.36% | 5.09% | 3.38% | 37.0% | 23.6% |
| travel_livebreak | 5.51% | 2.17% | **2.44%** | **0.02%** | 44.2% | 1.0% |
| travel_open | 33.21% | 35.46% | 20.28% | 29.91% | 61.1% | 84.4% |
| TOTAL (classified) | 78.90% | 88.14% | 29.31% | 33.94% | | |
| alive samples (10 Hz) | 328 279 | 263 147 | | | | |

**Caveat that matters for design.** `pursue_victim_still` is *not* a real
pursuit state. The gap past reach in those samples is p25 0.033 / **p50
0.080** / p75 0.132 / p90 0.344 tiles — the unit is sitting a hair outside the
reach line while still landing hits on that victim. Reclassifying it as
contact gives **tape ≈ 24.4% in-contact against the engine's ≈ 36.0%**. Only
`pursue_victim_moved` (p50 **0.581**, p90 **1.602** tiles past reach) is
genuine pursuit.

**The three real gaps, in order of size:**

1. **Contact time.** Engine 36.0% vs tape 24.4%. The engine's melee, once
   joined, is a frozen mutual lattice.
2. **Live-break travel.** Tape contributes 2.44% of all samples as *walking
   after losing a still-living foe*; the engine contributes **0.02%** — a
   122× gap. Its `travel_livebreak` occupancy is not zero (2.17%) but its
   *rate* is 1.0% vs the tape's 44.2%: in the engine a "live break" is an
   instantaneous switch to an adjacent body, not a walk.
3. **Genuine pursuit.** Tape 1.97% occupancy vs engine 0.20%.

### Per unit class

`tape / engine`. Infantry = champion, halberdier · cavalry = paladin,
heavy_camel, hussar · steppe = elite_steppe (range 1) · elephant =
elite_elephant.

**Walk contribution** (% of that class's alive samples spent walking in this state):

| state | champion | halberdier | paladin | heavy_camel | hussar | elite_steppe | elite_elephant |
|---|---|---|---|---|---|---|---|
| pursue_victim_moved | 0.41/0.34 | 0.24/0.40 | 0.44/0.06 | 0.64/0.26 | 0.86/0.01 | 2.02/**0.00** | 0.81/0.25 |
| pursue_victim_still | 0.59/0.06 | 0.20/0.05 | 0.38/0.23 | 0.25/0.50 | 0.51/0.03 | 0.84/0.01 | 0.81/0.23 |
| micro_follow | 0.25/0.32 | 0.02/0.31 | 0.09/0.37 | 0.10/0.76 | 0.04/0.27 | 0.24/0.15 | 0.01/0.27 |
| travel_postkill | 6.82/2.85 | 1.81/2.21 | 5.36/7.28 | 7.28/4.08 | 4.79/**0.49** | 3.01/1.34 | 7.34/3.43 |
| travel_livebreak | 2.24/**0.00** | 0.56/**0.00** | 4.09/**0.00** | 1.06/0.01 | 6.01/**0.00** | 1.12/**0.00** | 2.33/0.21 |
| travel_open | 26.16/39.00 | 15.81/28.00 | 20.37/28.62 | 18.60/31.05 | 32.87/47.19 | 12.31/14.44 | 16.91/24.53 |
| **moving, any time** | 53.15/49.99 | 58.64/69.58 | 33.07/37.27 | 34.30/48.79 | 49.35/54.24 | 19.59/15.96 | 30.02/34.88 |

**State occupancy** (% of that class's alive samples):

| state | champion | halberdier | paladin | heavy_camel | hussar | elite_steppe | elite_elephant |
|---|---|---|---|---|---|---|---|
| pursue_victim_moved | 1.20/0.37 | 0.92/0.42 | 1.56/0.06 | 2.46/0.30 | 2.58/0.01 | 3.27/0.00 | 2.02/0.42 |
| pursue_victim_still | 5.75/0.07 | 1.51/0.06 | 9.92/0.32 | 6.35/0.66 | 10.94/0.06 | 4.25/0.01 | 5.31/0.54 |
| micro_follow | 13.21/**28.56** | 3.17/**10.02** | 20.90/**41.21** | 13.96/**32.13** | 17.31/**32.70** | 35.87/**57.89** | 9.18/**21.03** |
| travel_postkill | 13.44/9.64 | 5.39/10.72 | 14.60/20.87 | 16.04/14.00 | 9.01/2.70 | 16.61/21.45 | 20.18/12.11 |
| travel_livebreak | 3.87/0.00 | 1.49/0.00 | 6.66/0.07 | 2.53/0.09 | 8.94/0.14 | 3.32/0.00 | 16.37/22.63 |
| travel_open | 37.20/47.36 | 24.40/30.40 | 39.58/33.21 | 37.23/36.18 | 43.02/54.13 | 26.02/17.44 | 23.44/32.20 |

The in-contact excess is **universal across classes** — the engine's
`micro_follow` occupancy is 1.6×–3.2× the tape's for every single one of the
seven. `travel_livebreak` is ~0.00 in the engine for five of seven.
`elite_steppe` is the extreme case: the tape gives it 3.27% genuine pursuit,
the engine **0.00%** — a range-1 unit in this engine never has to chase
anything.

---

## 2. Micro-following — **refuted**

Does an in-reach attacker drift with its target during the reload cycle?

| | tape | engine |
|---|---|---|
| engaged-unit step p50 (tiles / 0.1 s) | 0.0 | 0.0 |
| engaged-unit step p90 | 0.0 | 0.0 |
| engaged-unit step p99 | 0.0 | 0.018 |
| micro_follow moving-rate | **0.76%** | 0.91% |
| victim moving while I am in reach | 9.79% | 4.12% |
| cos(my step, victim step), both moving | 0.212 | 0.518 |
| n paired steps | 142 | 341 |

**A tape melee unit in reach of its victim does not move.** Its displacement
is exactly zero at the 90th percentile, it is moving in 0.76% of those
samples, and on the 142 occasions where both bodies moved the direction
correlation is 0.212 — i.e. essentially uncorrelated, not tracking. The
engine's 0.91% / cos 0.518 is, if anything, *more* follow-like.

Continuous target tracking between swings (brief candidate **(a)**) is not a
thing the recordings do. Building it would move the engine away from the tape.

---

## 3. Scrum flow

| | tape | engine |
|---|---|---|
| centroid speed, mean (tiles/s) | 0.2351 | 0.1933 |
| individual speed, mean (tiles/s) | **0.401** | **0.2564** |
| centroid / individual | 0.586 | 0.754 |
| rotation about own centroid, signed mean (rad/s) | −0.0028 | +0.0040 |
| rotation, **mean absolute** (rad/s) | **0.0877** | 0.0615 |

The tape's front does **not** translate more than the engine's (centroid
speeds are within 20%) and neither wheels coherently (signed rotation is zero
to three decimals in both). What the tape has is **57% more individual motion
at the same collective motion** — its centroid/individual ratio is 0.586
against the engine's 0.754. The tape scrum *churns internally*; the engine's
moves as a slab. Absolute rotation confirms it: 0.0877 vs 0.0615 rad/s of
unsigned angular shuffling.

So "the engine's front line freezes while the tape's translates" is **not**
the finding. Both fronts translate about the same. The engine's individuals
are what is frozen relative to each other.

---

## 4. Shove / push — **refuted as the origin of contact loss**

Contact breaks: an in-reach sustained pair that is out of reach the next frame.

| | tape | engine |
|---|---|---|
| breaks per in-reach sample | **0.95%** | 0.19% |
| … opened by the VICTIM moving | 90.32% | 91.11% |
| … opened at the ATTACKER end | 9.68% | 8.89% |

Who is behind a unit that steps *backwards* while engaged (negative radial
displacement) — the push-attribution test:

| | tape | engine |
|---|---|---|
| an ALLY body behind it | 23.93% | 50.59% |
| an ENEMY body behind it | 41.10% | 36.47% |
| nobody behind (self-initiated) | 34.97% | 12.94% |
| n backward steps while engaged | 163 | 85 |

**The engine already reproduces the break *attribution* almost exactly**
(90.3% vs 91.1% victim-opened). It just has **5× too few break events**. And
the tape's backward steps are *less* ally-driven than the engine's (23.9% vs
50.6%) with a third of them having no body behind them at all.

Unit pushing (brief candidate **(c)**) is therefore not what opens contact in
the recordings. The mechanism to find is whatever makes a tape **victim walk
away from the attacker holding it** — and that is a targeting question, not a
collision-physics question.

Two further hypotheses tested and refuted while chasing this:

* **Contact-slot queueing.** Units sitting out of reach of a living lock have
  a ring of only **1.55 allies** already in reach of that victim (median 1;
  only 18.6% have ≥3, 10.8% have ≥4). They are not waiting behind a full ring.
* **Bump-retarget over-firing.** Instrumented over all 31 fights:
  `meleeBumpRetarget` is *called* 1 582 456 times and actually switches a
  target **158 times** — 0.020 per swing. E14 rule 2 is not collapsing the
  target graph.

---

## 5. Post-kill travel and lock birth

| | tape | engine |
|---|---|---|
| distance to next victim at the kill, median (tiles past reach) | 0.349 | 0.146 |
| … p90 | **1.912** | 0.555 |
| seconds to the next landed hit, median | 2.026 | 2.017 |
| path walked / straight line, median | **1.278** | 1.036 |

Per class (`tape / engine`):

| metric | champion | halberdier | paladin | heavy_camel | hussar | elite_steppe | elite_elephant |
|---|---|---|---|---|---|---|---|
| dist to next victim, med | 0.896/0.273 | 1.033/0.166 | 0.361/0.163 | 0.537/0.209 | 0.725/0.301 | 0.0/0.0 | 0.376/0.466 |
| dist to next victim, p90 | 2.046/0.669 | 1.547/0.560 | 2.276/0.555 | 2.169/0.666 | 1.494/0.454 | 0.667/0.0 | 1.152/0.766 |
| seconds to next hit, med | 3.192/2.017 | 3.022/3.017 | 1.926/1.917 | 2.180/2.017 | 2.114/1.917 | 2.018/2.017 | 2.026/2.017 |
| path/straight, med | 1.415/1.016 | 1.268/1.095 | 1.185/1.038 | 1.276/1.049 | 1.464/1.036 | 1.893/1.596 | 1.228/1.049 |

**The tape's freed unit walks an arc; the engine's walks a straight line.**
Path/straight-line 1.278 vs 1.036 pooled, and 1.42/1.46 for champion/hussar
against ~1.02–1.04 in the engine. It threads or rounds the scrum; the engine
goes straight because its next victim is already touching it.

### Which enemy does a freed unit take? (2062 mid-fight lock births)

| | tape | engine |
|---|---|---|
| rank 1 (the nearest body) | **25.27%** | 48.65% |
| rank 2 | 31.13% | 40.55% |
| rank 3 | 13.48% | 6.30% |
| rank > 3 | **30.12%** | 4.50% |
| **excess tiles over the nearest, median** | **0.337** | 0.004 |
| **excess tiles over the nearest, p90** | **1.836** | 0.594 |
| allies already on the CHOSEN foe (mean) | 1.393 | 1.118 |
| allies already on the SKIPPED closer ones | 1.190 | 1.383 |

Per class, excess-over-nearest `tape / engine`:

| | champion | halberdier | paladin | heavy_camel | hussar | elite_steppe | elite_elephant |
|---|---|---|---|---|---|---|---|
| median | 0.584/0.298 | 0.506/0.293 | 0.337/0.000 | 0.556/0.164 | 0.590/0.190 | 0.234/0.000 | 0.160/0.000 |
| p90 | 2.051/0.682 | 1.733/0.607 | 2.072/0.731 | 2.061/0.600 | 1.946/0.474 | 1.442/0.446 | 1.266/0.428 |

**This is the largest clean behavioural difference in the corpus.** The
engine's `findTarget` takes the strictly nearest living enemy, so inside a
scrum the new victim is always whichever body the collision floor parked
against it — always already in reach, never requiring a walk (excess 0.004
tiles). The game walks a third of a tile past the closest enemy half the time
and nearly two tiles past it a tenth of the time.

Three explanations for it were measured. **All three are refuted:**

* *It avoids saturated victims* — no. The victim it takes already has **more**
  attackers on it (1.393) than the closer ones it walks past (1.190).
* *It keeps its facing and takes what is ahead* — no. Mean cos between the
  unit's heading and the direction to the chosen victim is **0.536** against
  **0.677** for the candidate pool (i.e. biased *away* from straight ahead),
  and in any case the unit is stationary at 99% of lock births (only 13 of
  2062 had a measurable 0.3 s heading).
* *Uniform choice within a search radius* — no single radius fits. Observed
  excess is median 0.337 / p90 1.836 / mean 0.660; uniform-within-nearest+1.5
  tiles matches the mean (0.676) but overshoots the median (0.685) and
  undershoots the tail (1.331). The observed shape is a **concentrated core
  with a heavy tail**, not a uniform draw.

The one hypothesis that **is** supported is *reachability*. Testing, at each
of the 2062 lock births, whether the straight approach lane from the unit to a
candidate is obstructed by an allied body (ally centre between the two along
the segment, perpendicular offset < `ally.radius + self.radius`, walk stopping
at contact):

| | blocked |
|---|---|
| the victim actually chosen | **25.0%** (515 / 2062) |
| the closer victims walked past | **31.8%** (1591 / 4996) |

Correctly signed, over a large sample — but **weak** (a 21% relative
reduction, not a hard exclusion). See §7 for what happened when it was
implemented as a hard rule.

---

## 5b. The two families the design must serve

`tape / engine`, pooled over each family's 6 recordings, both sides.

### paladin__vs__elite_steppe (6 recordings) — the family E14 lost, 5/6 → 1/6

| | tape | engine |
|---|---|---|
| moving, any time | 25.68% | 23.03% |
| moving WITH a foe in reach | 12.56% | 4.02% |
| **micro_follow occupancy** | 28.75% | **52.92%** |
| pursue_victim_moved occupancy | 2.39% | **0.01%** |
| pursue_victim_still occupancy | 7.47% | 0.00% |
| travel_postkill occupancy | 16.57% | 22.98% |
| **travel_livebreak occupancy** | 3.99% | **0.00%** |
| travel_open occupancy | 29.30% | 20.61% |
| pursuit gap median / p90 (tiles past reach) | 0.674 / **2.020** | 0.006 / 0.006 |
| breaks per in-reach sample | 0.72% | **0.04%** |
| engaged step p90 | 0.0 | 0.0 |
| cos(my step, victim step) | 0.253 | 0.637 |
| backward-step attribution ally/enemy/none | 37/29/34% | 100/0/0% |
| alive samples | 77 361 | 62 970 |

This family is the extreme of the whole corpus. The engine parks **52.92%** of
its unit-life in reach of its lock — more than double the tape's 28.75% — and
has *literally zero* live-break travel and a pursuit gap of 0.006 tiles at
both median and p90 (i.e. its lancers are never more than 6 thousandths of a
tile out of position). The tape's lancers pursue over gaps of up to 2.02
tiles. Mobility (1.68 t/s) plus 1-tile reach is exactly the combination that
makes walking-vs-planted decisive here, and the engine gives them nothing to
walk to.

### champion__vs__paladin (6 recordings) — margins currently fixed, must not regress

| | tape | engine |
|---|---|---|
| moving, any time | 43.57% | 45.32% |
| moving WITH a foe in reach | 13.68% | 9.90% |
| **micro_follow occupancy** | 18.22% | **33.00%** |
| pursue_victim_moved occupancy | 1.49% | 0.24% |
| pursue_victim_still occupancy | 6.80% | 0.39% |
| travel_postkill occupancy | 14.66% | 12.73% |
| **travel_livebreak occupancy** | 3.82% | **0.00%** |
| travel_open occupancy | 39.11% | **48.22%** |
| travel_open moving-rate | 65.16% | 82.80% |
| pursuit gap median / p90 | 0.390 / 0.899 | 0.095 / 0.166 |
| breaks per in-reach sample | 0.84% | 0.26% |
| backward-step attribution ally/enemy/none | 15/35/50% | 33/67/0% |
| alive samples | 53 431 | 49 788 |

Total walking already over-shoots here (45.32% vs 43.57%) and it is *all* in
the opening: the engine spends 48.22% of unit-life pre-first-hit at an 82.80%
moving rate against the tape's 39.11% at 65.16%. Anything that adds movement
to this family's approach will hurt it — which is precisely how the unscoped
lane rule in §7 took its margins from 21.9% to 6.7%.

---

## 6. When does a tape unit move rather than swing? — the strongest rule-like
regularity found

Moving-share as a function of position within the reload cycle, binned by
tenths of `1/attack_speed` since that unit's last landed hit (samples before a
unit's first hit, or more than one full reload after its last, are excluded —
neither is inside a cycle):

| phase of reload cycle | tape | engine |
|---|---|---|
| 0.0 – 0.1 | **0.90%** | 6.41% |
| 0.1 – 0.2 | 3.22% | 5.15% |
| 0.2 – 0.3 | 4.85% | 4.36% |
| 0.3 – 0.4 | 7.57% | 4.25% |
| 0.4 – 0.5 | 11.69% | 3.91% |
| 0.5 – 0.6 | 13.92% | 4.00% |
| 0.6 – 0.7 | 14.16% | 3.79% |
| 0.7 – 0.8 | 14.36% | 3.60% |
| 0.8 – 0.9 | 14.26% | 3.88% |
| 0.9 – 1.0 | **14.40%** | 6.19% |

**Testable statements, with the numbers that support them:**

* **T1.** *A tape melee unit is immobilised by its own swing and is released
  progressively as the reload runs down.* Moving-share climbs monotonically
  from 0.90% in the first tenth of the cycle to 14.40% in the last — a **16×
  ramp**, monotone across all ten bins.
* **T2.** *The release is not instantaneous; it saturates around 45–50% of the
  cycle.* Bins 0.5–1.0 are flat at 13.9–14.4%, so whatever holds the unit is
  spent by mid-cycle and the residual mobility is constant thereafter.
* **T3.** *The engine has no swing-phase structure at all.* Its profile is
  flat at 3.6–4.4% through bins 0.2–0.9 with symmetric bumps at both ends
  (6.41% / 6.19%) — the signature of a unit that either walks the whole cycle
  or none of it, uncorrelated with its own swing.
* **T4.** *Whatever the mechanism, it is not "keep stepping unless a swing is
  firing".* If it were, the tape's late-cycle bins would approach the
  unit's overall moving-share (39.2%); they cap at 14.4%. A unit that has
  swung recently is ~2.7× less mobile than the same unit averaged over its
  whole life.

The engine's counterpart to T1 is that a melee unit in reach never moves at
all, and out of reach always moves — a step function on distance rather than a
ramp on swing phase.

### Where the engine plants a unit — exact code paths

`apps/website/static/js/engine/battle_unit.js` (at `31f7339`):

| line | path | effect |
|---|---|---|
| **1034** | `} else if (this.inRange()) {` — melee branch | the only melee gate. Everything below it sets `state` and **never calls `moveTowardTarget`**. |
| 1035–1046 | `attackCooldown <= 0` → `committedAttack` (`state = "committed"`, `wasMoving = false`) or `performAttack()` (`state = "attacking"`) | planted for the windup / the swing |
| 1047–1049 | `else { this.state = "attacking"; }` | **planted for the entire remaining reload** — this is the branch T1/T3 indict: an in-reach melee unit with a cooldown running does nothing at all |
| 1050–1054 | `else { state = "moving"; this.moveTowardTarget(dt, allUnits); }` | the *only* melee movement call — reached solely when `inRange()` is false |
| 1015–1033 | `committedAttack` tick-down (`wasMoving = false` on completion) | planted for `attackDelay` |
| 936 / 1034 | `inRange()` at `battle_unit.js:494` | the step function: reach is binary, there is no partial or phase-dependent mobility anywhere |

For contrast, the **ranged** branch already has phase structure —
`fireRecovery` (line 911) immobilises for `postFireRecovery` and then
releases, which is E9's stand-and-shoot law. Melee has no analogue.

---

## 7. Side-result: a hard reachability rule was built and measured, then reverted

Before the scope change to step-1-only, the §5 lane-blocking result was
implemented as `MELEE_LANE_ACQUIRE` (prefer the nearest enemy whose approach
lane is clear; fall back to the nearest overall) and scored at 20 seeds. The
engine change has been **fully reverted** — the branch contains no engine
edits — but the numbers are evidence the design should have.

| variant | melee-62 ≤10 | ≤5 | ≤1 | mean \|err\| | median | winners all | basic | dur ratio |
|---|---|---|---|---|---|---|---|---|
| E14 baseline (`31f7339`) | **47** | 31 | 26 | 6.79 | 4.98 | 24/31 | 14/15 | 0.688 |
| lane rule, all acquisitions | 42 | 27 | 25 | 8.56 | 6.31 | 24/31 | 14/15 | 0.703 |
| lane rule, re-acquisition only | 43 | 33 | 26 | 6.73 | 4.05 | 24/31 | 14/15 | 0.678 |
| lane rule, re-acq. + narrow corridor (`perp < o.radius`) | **47** | **35** | **30** | **6.17** | **1.46** | **27/31** | 14/15 | 0.715 |

Emergence stats for the first (unscoped) variant, seed 1: breaks/swing
0.0212 → 0.0321 (tape 0.0815); post-kill slow 0.0423 → 0.0847 (tape 0.3427);
pursuit occupancy 0.41% → 1.00%; lock-birth excess median 0.004 → 0.025,
p90 0.594 → 0.730; post-kill distance p90 0.555 → 0.728. Every one moved
toward the tape, none of them close to it.

Notes for the design:

* The rule **must not be applied at the fight's opening**. The 25.0%/31.8%
  measurement is computed over mid-fight lock births only; the opening is
  excluded from the sample. Applied at t = 0 the armies are separated blocks
  with no scrum to thread, every front-rank unit's lane reads "blocked" by the
  ally beside it, and the line cross-assigns across the field — that variant
  cost 5 gate sides and took champion__vs__paladin margins from 21.9% to 6.7%.
* The corridor width matters more than the rule does. Widening it from the
  ally's own body (`perp < o.radius`) to a full clearance corridor
  (`perp < o.radius + self.radius`) turns a weak preference into a hard
  exclusion and loses everything the rule gains. **The narrow variant is a
  distinct geometric claim, not a tuned scalar, but nothing in the corpus
  currently distinguishes the two** — that is an open question, not a settled
  one, and it is why the change was not kept.
* Duration ratio is worth watching: the engine's fights already end at 0.69 of
  tape duration, and only the last variant moved it up (0.715).

---

## 8. What the design has to explain, ranked

1. **Contact time.** Engine ≈36.0% of alive samples in reach of its lock vs
   tape ≈24.4%. Everything else in this report is downstream of this.
2. **The swing-phase ramp (§6).** The tape's 0.90% → 14.40% monotone release
   across the reload cycle is the single most structured signal in the corpus
   and the engine has literally no counterpart to it. It is a *per-unit,
   per-swing, distance-independent* law — the melee analogue of E9's
   stand-and-shoot cycle — and it is the only measured thing that would raise
   mobility without touching targeting.
3. **Lock birth is not nearest-body (§5).** Excess over nearest median 0.337 /
   p90 1.836 vs the engine's 0.004 / 0.594; path/straight 1.278 vs 1.036.
   Reachability explains part of it (25.0% vs 31.8% blocked) but weakly, and
   saturation, facing and uniform-radius are all refuted.
4. **Live-break travel (§1).** Tape 2.44% of samples, engine 0.02%. This is
   the same phenomenon as (3) seen from the victim's side: tape victims walk
   off because they are locked on something that is not the unit hitting them.

**Do not build:** micro-following (§2 — the tape's engaged units have zero
displacement at p90), unit pushing as a break source (§4 — the engine already
matches the 90/10 attribution and only lacks event count), contact-slot
queueing, facing-based re-acquisition, or anything keyed to the front line
freezing (§3 — both fronts translate at similar speed).

---

## 9. Reproduction

```bash
node tools/simjs/calib_runner.mjs   --seeds 1 --out-dir D:/AI/aoe2_golden/simruns_e15_base
node tools/simjs/dump_sim_units.mjs --seeds 1 --out-dir D:/AI/aoe2_golden/simruns_e15_base

PYTHONPATH=. python tools/simjs/melee_walk_forensics.py \
    --sim-runs-dir D:/AI/aoe2_golden/simruns_e15_base            # §1-§6, pooled
PYTHONPATH=. python tools/simjs/melee_walk_forensics.py \
    --sim-runs-dir D:/AI/aoe2_golden/simruns_e15_base --by-slug  # per class
PYTHONPATH=. python tools/simjs/melee_walk_forensics.py \
    --sim-runs-dir D:/AI/aoe2_golden/simruns_e15_base \
    --fights paladin__vs__elite_steppe,paladin__vs__elite_steppe_r2,...
```

`melee_lock_forensics.py --positions` and `melee_break_rates.py` are unchanged
apart from the reach fix and remain the campaign's headline scoreboards.
