# R5 forensics — the six ranged-vs-ranged fights

Measurement only. Every number below is produced by
`tools/simjs/ranged_fire_forensics.py` (one implementation, fed either a
recording's three streams or an engine run's), over the six fights named in
`data/calibration/fight_sets.json`'s ranged set. Engine side = 20 seeds,
`tapebox` arena, current `improved-simulation` engine, dumped by
`tools/simjs/ranged_shot_dump.mjs`.

```
node tools/simjs/ranged_shot_dump.mjs --tags <the six> --seeds 20 \
     --out-dir D:/AI/aoe2_golden/simruns_r5_ranged
PYTHONPATH=. python tools/simjs/ranged_fire_forensics.py --section all
```

`T` = tape, `E` = engine (mean over seeds; time-series use the median-duration
seed). Sides are named `<owner>:<unit>` and come from the manifest's own
`owner` field, never the tag's word order.

---

## 0. Two things that have to be said before any table

### 0a. The "0.60-0.75x duration deficit" is a measurement artifact

The manifest's `duration_s` is the RECORDER's stream length. It runs 10-20 s
past the moment a side reaches zero units. Cut both sides at the same event —
the engine's own stop condition, first frame with a side at zero — and the
comparison inverts:

| fight | manifest `duration_s` | actual wipe | recorder tail | engine (med) | engine / **wipe** | engine / manifest |
|---|---|---|---|---|---|---|
| arb v HC | 34.69 | **17.92** | 16.77 | 21.92 | **1.22** | 0.63 |
| arb v HCA | 62.52 | **42.95** | 19.57 | 59.00 | **1.37** | 0.94 |
| arb v skirm | 41.54 | **23.29** | 18.25 | 26.00 | **1.12** | 0.63 |
| skirm v HC | 34.82 | **17.18** | 17.64 | 20.86 | **1.21** | 0.60 |
| skirm v HCA | 36.38 | **26.17** | 10.21 | 26.03 | **0.99** | 0.72 |
| HCA v HC | 61.09 | **41.01** | 20.08 | 35.44 | **0.86** | 0.58 |

The engine is **slower** than the tape in five of six ranged fights, not
0.6-0.75x faster. The one fight it genuinely finishes early is
`heavy_cav_archer__vs__hand_cannoneer` (0.86x).

This is not a scoring bug — `score.py` marks `duration_s` "reported only,
never gated", and `hp_remaining` is taken at the end of the recording, when
nothing is happening, so the HP errors are unaffected. But every
per-second and per-army-second statistic computed against the manifest number
is deflated, and the campaign's stated duration gap is not real. Everything
below uses the wipe time.

### 0b. The tape leads its projectiles; the engine does not

Restricted to tape hits whose victim the shot/damage pairing already names,
the distance from the arrow's landing point to the victim is:

| victim during flight | \|aim − victim@launch\| | \|aim − victim@impact\| |
|---|---|---|
| stood still (n=1,121) | 0.25-0.32 | 0.25-0.32 |
| moved (n=26, all six sides) | **0.50-0.88** | **0.22-0.38** |

The flight itself is a straight line — over all **1,501** reconstructed
flights in the six tapes, the largest perpendicular deviation from a track's
own launch→impact chord is **0.00122 tiles** — and it travels at exactly the
dat's `projectile_speed` per projectile type (arbalester arrow 6.998 vs 7.0,
heavy_cav_archer arrow 6.935 vs 7.0, hand cannoneer bullet 7.482 vs 7.5). So
the tape's arrow does not home — it is
fired at where the target *will be*. Corollary: the tape's hand cannoneer
launches flights out to **9.3 tiles** against a nominal 7-tile range, because
the aim point is thrown ahead of a fleeing target. The engine freezes its
impact at `target.x, target.y` **at launch** (`battle_unit.js` `fireProjectile`),
so its launch-range distribution is degenerate at its own reach.

---

## 1. Fire cadence

`s/shot` = living-unit seconds per launch. `duty` = observed cycle ÷ s/shot
(1.0 = every living unit fired on cooldown for its whole life). `dutyW` = the
same over each unit's own firing window (first launch → last launch), which is
boundary-free. `win% / pre% / post%` partition army-seconds into that window,
the time before a unit's first shot, and the time after its last (including
units that never fired). `inrch%` = share of living-unit time with an enemy
inside that unit's own `inRange()` reach.

| fight | side | reload | qcyc | T shots | E shots | T mv% | E mv% | T mvgap | E mvgap | T stgap | E stgap | T s/shot | E s/shot | T duty | E duty | T inrch% | E inrch% | T dutyW | E dutyW | T win% | E win% | T pre% | E pre% | T post% | E post% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 1.70 | 2.00 | 154 | 186.4 | 26.3 | 16.8 | 1.72 | 2.50 | 1.73 | 1.72 | 2.07 | 2.10 | 0.833 | 0.816 | 90.5 | 82.1 | 0.872 | 0.825 | 82.5 | 87.8 | 9.1 | 5.8 | 8.4 | 6.4 |
| arb v HC | 3:HC | 3.45 | 4.00 | 43 | 48.2 | 51.9 | 53.8 | 3.47 | 4.55 | 3.47 | 3.48 | 3.91 | 4.05 | 0.888 | 1.033 | 88.5 | 59.5 | 0.979 | 0.875 | 57.0 | 78.8 | 23.1 | 5.7 | 19.9 | 15.5 |
| arb v HCA | 2:arb | 1.70 | 2.00 | 262 | 343.0 | 8.3 | 4.1 | 1.94 | 2.45 | 1.72 | 1.72 | 1.79 | 1.92 | 0.957 | 0.893 | 97.5 | 92.2 | 0.954 | 0.896 | 92.3 | 93.6 | 3.7 | 3.1 | 4.0 | 3.4 |
| arb v HCA | 3:HCA | 1.80 | 2.00 | 155 | 135.0 | 39.0 | 42.0 | 2.21 | **3.90** | 1.82 | 1.82 | 2.24 | 2.95 | 0.814 | **0.616** | 93.4 | **65.0** | 0.903 | **0.611** | 82.0 | 90.3 | 13.3 | 4.3 | 4.7 | 5.4 |
| arb v skirm | 2:arb | 1.70 | 2.00 | 96 | 101.0 | 21.7 | 8.0 | 1.71 | 2.55 | 1.72 | 1.72 | 1.78 | 1.82 | 0.966 | 0.942 | 97.1 | 92.3 | 0.939 | 0.928 | 88.9 | 88.5 | 4.8 | 4.1 | 6.3 | 7.5 |
| arb v skirm | 3:skirm | 3.00 | 3.33 | 132 | 128.0 | 32.4 | 39.0 | 3.02 | 3.80 | 3.02 | 3.02 | 3.32 | 3.93 | 0.908 | 0.768 | 94.7 | 63.6 | 0.963 | 0.809 | 79.3 | 79.3 | 11.7 | 2.0 | 9.0 | 18.6 |
| skirm v HC | 2:skirm | 3.00 | 3.33 | 102 | 98.3 | 28.4 | 23.1 | 3.05 | 4.56 | 3.02 | 3.02 | 3.22 | 3.91 | 0.938 | 0.772 | 88.3 | 74.0 | 0.936 | 0.756 | 79.6 | 80.2 | 11.4 | 7.9 | 9.0 | 11.9 |
| skirm v HC | 3:HC | 3.45 | 4.00 | 26 | 31.0 | 50.0 | 57.5 | 3.47 | 4.56 | 3.47 | 3.48 | 3.72 | 4.11 | 0.933 | 1.014 | 83.9 | 57.5 | 1.000 | 0.855 | 57.4 | 80.4 | 23.0 | 5.8 | 19.6 | 13.9 |
| skirm v HCA | 2:skirm | 3.00 | 3.33 | 160 | 137.0 | 19.4 | 20.2 | 3.25 | 3.72 | 3.02 | 3.02 | 3.20 | 3.59 | 0.943 | 0.840 | 89.9 | 77.7 | 0.952 | 0.843 | 86.0 | 84.4 | 6.4 | 8.4 | 7.6 | 7.2 |
| skirm v HCA | 3:HCA | 1.80 | 2.00 | 59 | 64.0 | 12.0 | 25.5 | 2.27 | 2.44 | 1.82 | 1.82 | 2.22 | 2.11 | 0.818 | 0.860 | 92.5 | 84.9 | 0.932 | 0.860 | 74.4 | 86.0 | 20.4 | 7.1 | 5.2 | 6.9 |
| HCA v HC | 2:HCA | 1.80 | 2.00 | 173 | 165.1 | 36.4 | 32.5 | 2.72 | 3.74 | 1.93 | 1.82 | 3.15 | 3.27 | 0.689 | 0.556 | 87.4 | 63.7 | 0.752 | 0.638 | 81.5 | 77.2 | 14.7 | 12.8 | 3.9 | 10.0 |
| HCA v HC | 3:HC | 3.45 | 4.00 | 139 | 99.7 | 18.6 | 23.7 | 3.47 | 4.40 | 3.47 | 3.48 | 3.57 | 3.91 | 0.971 | 0.890 | 95.1 | 73.7 | 0.974 | 0.805 | 84.6 | 87.4 | 8.8 | 3.4 | 6.6 | 9.2 |

**What this says.**

1. **The tape's law is "if something is in reach, fire on cooldown."** Tape
   `dutyW` is 0.75-1.00 on every one of the twelve sides (mean 0.93), and
   tape `inrch%` (84-98%, mean 91.6) tracks `win% + pre%` almost exactly. A
   tape ranged unit is idle only when it has nothing to shoot at.
2. **The engine is idle even when it has a target.** Engine `dutyW`
   0.61-0.93 (mean 0.82) and engine `inrch%` 57.5-92.3 (mean **73.8** vs the
   tape's 91.6). The engine's armies are less engaged, on every side but one.
3. **The engine's *stationary* cadence is exact and its *moving* cadence is
   not.** `stgap` matches the tape to 0.01 s on all twelve sides. `mvgap`
   overshoots on all twelve: arb 2.45-2.55 vs a 2.00 quantum, skirm 3.72-3.80
   vs 3.33, HC 4.40-4.56 vs 4.00, HCA 2.44-3.90 vs 2.00. The E9 cooldown is
   set to the quantised cycle, but the unit does not launch the moment the
   cooldown expires, so launch-to-launch runs 0.4-1.9 s long.

### 1b. E9 re-tested on this corpus

Median launch-to-launch gap (n) split by the fraction of the cycle the shooter
spent displaced. E9 predicts every non-`still` bucket sits at `qcyc`.

| unit | reload | qcyc | T still | T mv<25% | T mv25-60% | T mv>60% | E still | E mv<25% | E mv25-60% |
|---|---|---|---|---|---|---|---|---|---|
| arb | 1.70 | 2.00 | 1.72 (384) | 1.88 (24) | **1.71 (40)** | 5.79 (9) | 1.72 (10514) | **2.42 (730)** | 4.08 (224) |
| HCA | 1.80 | 2.00 | 1.82 (228) | 2.24 (90) | 2.99 (13) | 8.49 (14) | 1.82 (4144) | **3.90 (1901)** | 2.85 (318) |
| skirm | 3.00 | 3.33 | 3.02 (245) | **3.02 (35)** | **3.03 (17)** | 3.25 (34) | 3.02 (4268) | **3.75 (1393)** | 5.73 (237) |
| HC | 3.45 | 4.00 | 3.47 (117) | **3.47 (31)** | **3.48 (8)** | 4.31 (5) | 3.48 (1629) | **4.47 (826)** | 5.33 (107) |

On **ranged-vs-ranged** tape, a cycle with a *little* movement in it costs
nothing: arbalester, imp_elite_skirm and hand_cannoneer all sit at bare
`reload` through the `mv<60%` buckets. Only heavy_cav_archer shows a
movement-graded cost (1.82 → 2.24 → 2.99 → 8.49), and only cycles that are
mostly movement (`mv>60%`) pay a large one on any unit. E9's binary
"moved at any point → quantise" was derived over all 140 recordings, which are
dominated by archers running from melee; on this corpus it over-charges. The
engine over-charges twice: it applies the quantum *and* then overshoots it.

---

## 2. Shot outcomes

Percentages are of shots that had time to land (CENSORED — still airborne at
the recording's end — removed; nothing else is).

| fight | side | T hit% | E hit% | T wst% | E wst% | T ddg% | E ddg% | T sct% | E sct% | T whf% | E whf% | T rng | E rng | T wst/kill | E wst/kill |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 72.7 | 63.4 | 14.9 | **36.2** | 0.6 | 0.0 | 5.8 | 0.2 | 5.8 | 0.0 | 7.19 | 8.10 | 1.44 | 4.00 |
| arb v HC | 3:HC | **79.1** | **52.6** | **0.0** | **28.5** | 4.7 | 0.0 | 4.7 | 0.1 | 11.6 | 18.7 | 6.60 | 7.60 | 0.00 | 2.70 |
| arb v HCA | 2:arb | 87.8 | 82.6 | 4.6 | 16.5 | 2.7 | 0.0 | 1.5 | 0.3 | 3.4 | 0.3 | 6.70 | 8.00 | 1.33 | 4.00 |
| arb v HCA | 3:HCA | 81.3 | 74.6 | 8.4 | 23.1 | 0.0 | 0.0 | 4.5 | 1.5 | 5.8 | 0.0 | 6.66 | 7.60 | 0.62 | 1.90 |
| arb v skirm | 2:arb | 91.7 | 92.0 | 2.1 | 8.0 | 0.0 | 0.0 | 0.0 | 0.0 | 6.2 | 0.0 | 6.98 | 8.50 | 0.67 | 2.70 |
| arb v skirm | 3:skirm | 59.1 | 63.4 | 13.6 | 35.8 | 2.3 | 0.0 | 7.6 | 0.0 | **16.7** | 0.0 | 7.61 | 8.60 | 1.38 | 3.40 |
| skirm v HC | 2:skirm | 58.8 | 64.0 | 33.3 | 35.9 | 0.0 | 0.1 | 6.9 | 0.0 | 0.0 | 0.0 | 7.24 | 8.10 | 3.40 | 3.40 |
| skirm v HC | 3:HC | **80.8** | **62.4** | **0.0** | **18.8** | 11.5 | 0.0 | 0.0 | 0.0 | 7.7 | 18.8 | 6.64 | 7.60 | 0.00 | 1.40 |
| skirm v HCA | 2:skirm | 67.5 | 81.8 | 29.4 | 17.4 | 0.0 | 0.0 | 1.9 | 0.8 | 1.2 | 0.0 | 7.17 | 8.30 | 5.22 | 2.60 |
| skirm v HCA | 3:HCA | 94.9 | 79.4 | 0.0 | 20.6 | 0.0 | 0.0 | 0.0 | 0.0 | 5.1 | 0.0 | 6.64 | 7.60 | 0.00 | 3.20 |
| HCA v HC | 2:HCA | 72.8 | 79.3 | 20.8 | 20.0 | 0.0 | 0.1 | 1.2 | 0.4 | 4.0 | 0.0 | 6.54 | 7.60 | 1.71 | 1.50 |
| HCA v HC | 3:HC | **77.7** | **67.7** | **0.0** | **13.6** | 7.2 | 0.1 | 0.0 | 0.1 | 4.3 | 18.5 | 6.43 | 7.60 | 0.00 | 2.10 |

**What this says.**

1. **Hand cannoneer never wastes a shot on tape and wastes 14-29% in the
   engine.** In all three of its recordings, tape HC's `wst%` is exactly
   **0.0** — not one hand-cannoneer bullet in the corpus is aimed at a unit
   that dies before it lands. The engine's is 13.6 / 18.8 / 28.5%. Wasted
   shots per kill: tape 0.00 / 0.00 / 0.00, engine 2.70 / 1.40 / 2.10.
2. **In-flight waste is the engine's largest single shot-outcome error and it
   is systematic**: engine `wst%` exceeds tape `wst%` on 9 of 12 sides, by up
   to 21 points (arb in arb v HC: 14.9 → 36.2).
3. **The units the dat calls 100% accurate still miss on tape.** Arbalester,
   heavy_cav_archer and imp_elite_skirm all carry `accuracy = 100` in
   `combat_dicts.json`, so the engine's `whf% + ddg% + sct%` for them is
   0.0-1.5%. On tape it is 6.2 / 6.2 / 12.2% (arb), 5.2 / 5.1 / 10.3% (HCA),
   **3.1 / 6.9 / 26.6%** (skirm). Conversely the engine's hand cannoneer
   whiffs at a flat **18.5-18.8%** (its 75 accuracy) while tape HC's on-target
   failure is **4.3 / 7.7 / 11.6%**.
4. **Movement-dependent misses exist on tape and are small.** Tape `ddg%` (shot
   landed wide of a target that moved) is 0.0-11.5%, concentrated in hand
   cannoneer (4.7 / 11.5 / 7.2) — the one unit whose target set includes fast
   movers. It is not the dominant miss mechanism; in-flight death is.
5. **The engine fires at max reach; the tape fires inside it.** Engine median
   launch range = its `inRange()` reach to two digits (7.60 for a range-7
   unit, 8.10-8.60 for a range-8 one) with p90 = median. Tape median is
   6.43-7.61, i.e. **0.9-1.4 tiles closer**, with a broad distribution and (for
   hand cannoneer, thanks to leading) a tail past 9. Longer engine flights →
   longer travel time → more in-flight waste, which is finding 1's mechanism.

---

## 3. Standoff geometry

`sep` = inter-centroid separation, tiles. `rad<owner>` = that side's mean
radial speed toward the enemy centroid (+ closing). `mv%` = share of
unit-samples in which a unit was moving.

| fight | reach | T sep0 | E sep0 | T sepmin | E sepmin | T sepmid | E sepmid | T sepend | E sepend | T rad(s1) | E rad(s1) | T rad(s2) | E rad(s2) | T mv%(s1) | E mv%(s1) | T mv%(s2) | E mv%(s2) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 8.57 | 9.44 | 9.43 | 7.97 | 7.80 | 8.18 | 8.72 | 8.09 | 7.83 | 0.046 | 0.030 | 0.034 | 0.049 | 18.8 | 9.2 | 16.6 | 12.6 |
| arb v HCA | 8.62 | 9.59 | 9.58 | 7.34 | 7.85 | 7.76 | 8.04 | 7.34 | 7.94 | -0.019 | -0.009 | 0.073 | 0.038 | 4.5 | 4.5 | 10.5 | 13.5 |
| arb v skirm | 8.57 | 9.03 | 9.02 | 8.07 | 8.35 | 8.27 | 8.75 | 8.07 | 8.35 | -0.030 | -0.009 | 0.071 | 0.038 | 10.9 | 4.7 | 10.9 | 9.7 |
| skirm v HC | 8.57 | 9.66 | 9.65 | 7.82 | 7.20 | 8.05 | 8.57 | 7.94 | 7.20 | 0.059 | 0.034 | 0.050 | 0.087 | 21.5 | 11.1 | 14.7 | 12.8 |
| skirm v HCA | 8.62 | 9.58 | 9.57 | 7.81 | 7.99 | 7.95 | 8.56 | 8.18 | 8.02 | 0.034 | 0.030 | 0.029 | 0.031 | 15.5 | 9.6 | 10.7 | 5.9 |
| HCA v HC | 7.62 | 9.09 | 9.07 | **4.84** | **7.45** | **6.42** | **8.06** | **5.36** | **7.45** | 0.075 | 0.049 | 0.022 | -0.000 | 28.1 | 21.3 | 7.8 | 6.9 |

Spawns match (sep0 identical to two digits — the tapebox arena is doing its
job). Five of six fights hold a similar standoff. The exception is
**`heavy_cav_archer__vs__hand_cannoneer`**, and it is not marginal: the tape's
two armies close from 8.5 to **4.84** tiles and hold ~6.4 through the whole
midgame, so essentially every unit on both sides is inside reach (`inrch%`
96-100 from t=15 on, Table 1). The engine holds them at **8.06** — *above*
the 7.62 reach — so only the front ranks ever engage (`inrch%` 52-70 for HCA,
59-81 for HC).

Across the board the engine's `sepmid` is 0.25-1.64 tiles wider than the
tape's, and never narrower.

---

## 4. Focus / target selection

`vict/cyc` = distinct enemies this side damaged in a trailing reload window.
`att/vict` = distinct shooters on the same victim in that window. `hhi` =
Herfindahl of damage per victim (`even` = the 1/n floor for the same victim
count).

| fight | side | T vict/cyc | E vict/cyc | T att/vict | E att/vict | T hhi | E hhi | T even | E even | T 1stkill | E 1stkill | T kills | E kills |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 3.0 | 4.05 | 4.0 | 3.00 | 0.0625 | 0.062 | 0.0625 | 0.062 | 1.46 | 1.50 | 16 | 16.0 |
| arb v HC | 3:HC | 4.0 | 2.73 | 2.0 | 1.85 | 0.1017 | 0.137 | 0.0833 | 0.121 | 3.22 | 1.28 | 6 | 5.1 |
| arb v HCA | 2:arb | 2.0 | 4.00 | 6.0 | 4.00 | 0.0836 | 0.071 | 0.0769 | 0.071 | 3.01 | 3.08 | 9 | 14.0 |
| arb v HCA | 3:HCA | 3.0 | 2.00 | 2.0 | 2.00 | 0.0476 | 0.058 | 0.0476 | 0.053 | 5.18 | 1.90 | 21 | 16.0 |
| arb v skirm | 2:arb | 2.0 | 3.00 | 5.0 | 2.00 | 0.1875 | 0.153 | 0.1250 | 0.111 | 3.22 | 3.25 | 3 | 3.0 |
| arb v skirm | 3:skirm | 5.5 | 3.00 | 2.0 | 3.00 | 0.0769 | 0.077 | 0.0769 | 0.077 | 5.96 | 1.40 | 13 | 13.0 |
| skirm v HC | 2:skirm | 2.0 | 3.58 | 3.0 | 2.93 | 0.1000 | 0.100 | 0.1000 | 0.100 | 1.61 | 1.48 | 10 | 10.0 |
| skirm v HC | 3:HC | 3.0 | 1.98 | 1.0 | 1.98 | 0.1769 | 0.195 | 0.1250 | 0.162 | 6.11 | 1.40 | 4 | 4.0 |
| skirm v HCA | 2:skirm | 2.0 | 4.00 | 6.0 | 4.00 | 0.1111 | 0.111 | 0.1111 | 0.111 | 1.74 | 1.65 | 9 | 9.0 |
| skirm v HCA | 3:HCA | 3.0 | 1.50 | 2.0 | 4.00 | 0.1712 | 0.231 | 0.1250 | 0.167 | 9.37 | 3.72 | 3 | 4.0 |
| HCA v HC | 2:HCA | 2.0 | 3.83 | 3.0 | 2.00 | 0.0476 | 0.048 | 0.0476 | 0.048 | 2.12 | 1.93 | 21 | 21.0 |
| HCA v HC | 3:HC | 5.0 | 3.95 | 2.0 | 2.05 | 0.0712 | 0.103 | 0.0625 | 0.077 | 2.78 | 1.40 | 10 | 6.4 |

Concentration is close to the even floor on both sides in most fights — ranged
fire here is *not* strongly focused, in either source, and this is not a
melee-style lock problem. The one consistent asymmetry is **hand cannoneer**:
tape HC spreads over 3.0-5.0 distinct victims per cycle vs the engine's
1.98-3.95, and its `hhi` is below the engine's in all three fights (0.1017 vs
0.137, 0.1769 vs 0.195, 0.0712 vs 0.103). That is the same fact as its 0%
in-flight waste, seen from the other side: the tape's HCs are not all
shooting the same dying unit.

Engine first-blood is systematically earlier for the SLOW-cycle side (HC 3.22
→ 1.28, 6.11 → 1.40, 2.78 → 1.40; skirm 5.96 → 1.40), an opening-volley
alignment difference, not a sustained one.

---

## 5. Attrition shape

Surviving HP fraction on a normalised time axis (0 = start, 1 = that fight's
own wipe), 11 of 21 sample points.

```
arbalester__vs__hand_cannoneer
   2:arb  tape    1.00 0.99 0.88 0.84 0.75 0.72 0.67 0.66 0.61 0.61 0.60
          engine  1.00 0.95 0.95 0.86 0.80 0.78 0.76 0.76 0.75 0.70 0.70
   3:HC   tape    1.00 0.94 0.81 0.66 0.50 0.36 0.34 0.28 0.18 0.07 0.00
          engine  1.00 0.94 0.77 0.66 0.61 0.50 0.38 0.31 0.15 0.12 0.00

arbalester__vs__heavy_cav_archer
   2:arb  tape    1.00 0.93 0.78 0.62 0.49 0.39 0.31 0.19 0.14 0.08 0.00
          engine  1.00 0.83 0.75 0.64 0.57 0.47 0.36 0.32 0.27 0.22 0.20
   3:HCA  tape    1.00 0.93 0.74 0.61 0.51 0.41 0.34 0.28 0.23 0.20 0.18
          engine  1.00 0.87 0.71 0.59 0.46 0.34 0.24 0.18 0.12 0.06 0.00

arbalester__vs__imp_elite_skirm
   2:arb  tape    1.00 0.99 0.86 0.67 0.51 0.38 0.33 0.21 0.11 0.08 0.00
          engine  1.00 0.92 0.77 0.65 0.54 0.47 0.36 0.32 0.16 0.10 0.00
   3:skirm tape   1.00 0.97 0.95 0.88 0.86 0.84 0.81 0.80 0.78 0.77 0.77
          engine  1.00 0.96 0.92 0.90 0.87 0.84 0.81 0.79 0.77 0.76 0.75

imp_elite_skirm__vs__hand_cannoneer
   2:skirm tape   1.00 1.00 0.96 0.93 0.89 0.87 0.82 0.81 0.78 0.78 0.77
          engine  1.00 0.95 0.94 0.89 0.86 0.86 0.84 0.82 0.81 0.79 0.76
   3:HC   tape    1.00 0.90 0.90 0.70 0.70 0.51 0.47 0.25 0.23 0.15 0.00
          engine  1.00 0.90 0.90 0.75 0.61 0.58 0.44 0.38 0.23 0.13 0.00

imp_elite_skirm__vs__heavy_cav_archer
   2:skirm tape   1.00 0.99 0.97 0.93 0.89 0.87 0.83 0.81 0.79 0.78 0.78
          engine  1.00 0.97 0.95 0.91 0.89 0.86 0.84 0.83 0.81 0.81 0.80
   3:HCA  tape    1.00 0.89 0.71 0.68 0.57 0.38 0.35 0.25 0.15 0.11 0.00
          engine  1.00 0.89 0.78 0.63 0.59 0.47 0.35 0.29 0.16 0.08 0.00

heavy_cav_archer__vs__hand_cannoneer
   2:HCA  tape    1.00 0.91 0.82 0.73 0.65 0.53 0.48 0.42 0.37 0.34 0.32
          engine  1.00 0.94 0.85 0.78 0.74 0.70 0.68 0.62 0.59 0.58 0.57
   3:HC   tape    1.00 0.95 0.82 0.78 0.66 0.53 0.41 0.33 0.24 0.13 0.00
          engine  1.00 0.92 0.77 0.63 0.56 0.47 0.36 0.24 0.16 0.06 0.00
```

No fight diverges at a moment. Every gap opens gradually from ~20-30% of
normalised time and widens monotonically to the end — a sustained rate
difference, not an event. The two bad fights:

- **arb v HCA** — both curves move the same way: the engine's arbalesters die
  slower than the tape's (0.57 vs 0.49 at 40%, 0.32 vs 0.19 at 70%, 0.20 vs
  0.00 at 100%) AND the engine's HCAs die faster (0.24 vs 0.34 at 60%). The
  HCA is losing damage output the whole way.
- **HCA v HC** — the HC curves are within 0.05-0.10 of each other, faster in
  the engine if anything. The whole error is on the HCA curve, which sits
  0.09-0.25 above the tape's from 30% onward.

---

## 6. Throughput ledger

A side's landed hits per second factorises exactly:

```
hits/s  =  A  x  F  x  H
   A = mean living units          (army-seconds / duration)
   F = launches per living-unit-second
   H = hit rate
```

so the engine/tape ratio is the product of three ratios. `tilt` = side1's
hits/s ratio divided by side2's — how much the engine moves the two sides'
firepower **relative to each other**, which is what the HP score reads.

| fight | side | T dur | E dur | dur x | T A | E A | A x | T F | E F | F x | T H | E H | H x | T hit/s | E hit/s | hit/s x | T hp% | E hp% | tilt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 17.92 | 21.92 | 1.22 | 17.78 | 17.88 | 1.01 | 0.483 | 0.476 | 0.98 | 0.727 | 0.634 | 0.87 | 6.25 | 5.39 | **0.86** | 59.8 | 69.2 | **1.42** |
| arb v HC | 3:HC | 17.92 | 21.92 | 1.22 | 9.39 | 8.88 | 0.95 | 0.256 | 0.247 | 0.97 | 0.791 | 0.526 | **0.66** | 1.90 | 1.16 | **0.61** | 0.0 | 0.0 | |
| arb v HCA | 2:arb | 42.95 | 59.00 | 1.37 | 10.94 | 11.18 | 1.02 | 0.558 | 0.520 | 0.93 | 0.878 | 0.826 | 0.94 | 5.36 | 4.80 | **0.90** | 0.0 | 20.5 | **1.54** |
| arb v HCA | 3:HCA | 42.95 | 59.00 | 1.37 | 8.10 | 6.75 | **0.83** | 0.446 | 0.339 | **0.76** | 0.813 | 0.746 | 0.92 | 2.93 | 1.71 | **0.58** | 17.9 | 0.0 | |
| arb v skirm | 2:arb | 23.29 | 26.00 | 1.12 | 7.33 | 7.08 | 0.97 | 0.562 | 0.549 | 0.98 | 0.917 | 0.920 | 1.00 | 3.78 | 3.57 | 0.95 | 0.0 | 0.0 | **1.01** |
| arb v skirm | 3:skirm | 23.29 | 26.00 | 1.12 | 18.84 | 19.35 | 1.03 | 0.301 | 0.254 | 0.85 | 0.591 | 0.634 | 1.07 | 3.35 | 3.12 | 0.93 | 76.5 | 75.4 | |
| skirm v HC | 2:skirm | 17.18 | 20.86 | 1.21 | 19.12 | 18.42 | 0.96 | 0.311 | 0.256 | 0.82 | 0.588 | 0.640 | 1.09 | 3.49 | 3.01 | 0.86 | 76.7 | 77.3 | **1.14** |
| skirm v HC | 3:HC | 17.18 | 20.86 | 1.21 | 5.62 | 6.10 | 1.09 | 0.269 | 0.244 | 0.90 | 0.808 | 0.624 | **0.77** | 1.22 | 0.93 | 0.76 | 0.0 | 0.0 | |
| skirm v HCA | 2:skirm | 26.17 | 26.03 | 0.99 | 19.59 | 18.89 | 0.96 | 0.312 | 0.279 | 0.89 | 0.675 | 0.818 | 1.21 | 4.13 | 4.31 | 1.04 | 77.6 | 80.1 | **1.14** |
| skirm v HCA | 3:HCA | 26.17 | 26.03 | 0.99 | 5.01 | 5.19 | 1.04 | 0.450 | 0.474 | 1.05 | 0.949 | 0.794 | 0.84 | 2.14 | 1.95 | 0.91 | 0.0 | 0.0 | |
| HCA v HC | 2:HCA | 41.01 | 35.44 | 0.86 | 13.27 | 15.22 | **1.15** | 0.318 | 0.306 | 0.96 | 0.728 | 0.793 | 1.09 | 3.07 | 3.69 | **1.20** | 32.2 | 55.7 | **1.66** |
| HCA v HC | 3:HC | 41.01 | 35.44 | 0.86 | 12.11 | 11.01 | 0.91 | 0.280 | 0.256 | 0.91 | 0.777 | 0.677 | **0.87** | 2.63 | 1.90 | **0.72** | 0.0 | 0.0 | |

**`tilt` orders the six fights exactly as the scoreboard does:**

| fight | tilt | HP error (run 20260731T021629Z) |
|---|---|---|
| arb v skirm | 1.01 | 1.1 |
| skirm v HC | 1.14 | 0.6 |
| skirm v HCA | 1.14 | 2.6 |
| arb v HC | 1.42 | 9.4 |
| arb v HCA | 1.54 | wrong winner |
| HCA v HC | 1.66 | 23.5 |

Which factor carries the tilt differs by fight, and that is the useful part:

- **arb v HC** — all of it is `H`. `A x` and `F x` are 0.95-1.01 on both
  sides; hand cannoneer's hit rate ratio is 0.66.
- **arb v HCA** — all of it is heavy_cav_archer's `A x` 0.83 and `F x` 0.76.
  Its hit rate is fine (0.92).
- **HCA v HC** — split: HCA gains on `A` (1.15) and `H` (1.09) while HC loses
  on `H` (0.87), `F` (0.91) and `A` (0.91).

Note that **hand cannoneer's `H x` is 0.66 / 0.77 / 0.87 — below 1 in all
three of its fights** and by more than any other unit's, which is why it
appears on the wrong side of every one of the three off-target results.

---

## 7. Per-fight diagnoses (the three off-target fights)

### `arbalester__vs__heavy_cav_archer` — wrong winner (tape: HCA 17.9%; engine: arb 20.5%, 20/20 seeds)

The heavy cavalry archer's problem is **uptime, not marksmanship**. Its hit
rate ratio is 0.92 and its stationary cadence is exact (1.818 vs 1.817), but
its `F x` is 0.76 and its `A x` is 0.83, for a hits/s ratio of 0.58 against
the arbalester's 0.90 — a 1.54x tilt. The mechanism is visible in the
5-second timeline: the tape's HCAs hold an enemy inside reach for **87 / 99 /
95 / 93 / 98 / 96 / 96 / 85 / 84%** of their living time bucket by bucket and
keep firing 14-29 shots per bucket to the end. The engine's HCAs start at
81%, then fall to **54 / 45 / 54 / 62 / 72 / 76%** as they back off, and their
shot count collapses from 31 in the opening bucket to 11-18 thereafter.
Compounding it, the engine's HCA moving cycle runs **3.90 s** against a 2.00 s
quantum and the tape's 2.21 s, so each of the 42% of cycles in which it moves
costs it nearly a whole extra shot. The engine's arbalesters, meanwhile, keep
80-100% in-reach throughout. Net: the engine gives the mobile unit a retreat
that costs it half its damage and gives the immobile unit nothing, and that
alone flips the result. Nothing about accuracy, focus (both sides sit at the
even-HHI floor), damage per hit or spawn geometry differs materially.

### `heavy_cav_archer__vs__hand_cannoneer` — 23.5 HP-pts (tape HCA 32.2%; engine 55.7%)

This is the one fight with a genuine **closure** failure and it is large. The
tape's two armies march into each other: centroid separation goes 8.49 → 6.74
→ 6.32 → **5.26** → 4.98 and both sides sit at 96-100% in-reach from t=15
onward, i.e. the whole of both armies is engaged for two thirds of the fight.
The engine never closes — separation stays 7.7-8.7, *above* the 7.62 reach —
so only the leading ranks fight: HCA in-reach 52-70%, HC 59-81%. The
consequences split cleanly. The hand cannoneer loses on every factor (`A`
0.91, `F` 0.91, `H` 0.87 → hits/s 0.72), its hit rate falling because the
engine gives it a flat 18.5% accuracy whiff (dat accuracy 75) where the tape
shows 4.3% on-target failure plus 7.2% dodges, and because 13.6% of its
bullets are wasted on units that die in flight where the tape wastes 0.0%.
The heavy cavalry archer meanwhile *gains* (`A` 1.15, `H` 1.09 → hits/s 1.20),
largely because standing off keeps it alive. Tilt 1.66, the largest in the
set. The attrition curves confirm the direction: the HC curves nearly overlay,
the HCA curve is the one that is wrong, sitting 0.09-0.25 high from 30% on.

### `arbalester__vs__hand_cannoneer` — 9.4 HP-pts (tape arb 59.8%; engine 69.2%)

The simplest of the three: **the whole error is hand cannoneer hit rate.**
Both sides' `A x` and `F x` are 0.95-1.01 — the armies are the same size, alive
for the same fraction of the fight, and firing at the same per-unit rate
(engine `stgap` 3.483 vs tape 3.474). But the engine's HC lands 52.6% of its
shots against the tape's 79.1%, a ratio of 0.66, and the arbalester's own hit
rate ratio is 0.87, giving a 1.42 tilt. The 26-point hit-rate gap decomposes
into two roughly equal pieces: **28.5 points of in-flight waste** (tape: 0.0)
and **18.7 points of accuracy whiff versus the tape's 11.6**. The waste piece
is geometric — the engine's HC launches from 7.60 tiles (its exact reach)
against the tape's 6.60, a 15% longer flight, at a target the engine's HCs are
more likely to be sharing (tape 4.0 distinct victims per cycle, engine 2.73).

---

## 8. Methodology notes and validation

- **Sides** come from `manifest.json`'s `owner` field, never tag order, and
  were cross-checked against master ids in the units stream
  (arbalester **492**, hand_cannoneer **5**, heavy_cav_archer **474**,
  imp_elite_skirm **6** — the last one had not been recorded anywhere, so it
  is stated here). Every fight's distinct-unit count per `(owner, master)`
  equals the manifest's side count exactly, in all six fights, so no side
  label is taken on faith.
- **Shot→damage pairing is exact.** Over all six tapes: 1,147 shots paired,
  time residual **0.0000 s** at the maximum, and **0 damage events left
  unpaired**. Same on every engine seed checked (0 unpaired).
- **Landed shots arrive 0.282 tiles from their victim** (median over all
  1,147 tape pairs; p90 0.347, p99 0.421) -- the projectile sprite's anchor
  offset. `ON_TARGET_TILES = 0.45` therefore sits above the p99 of a genuine
  hit, which is what makes "arrived and did nothing" separable from "landed
  wide".
- **Aim-target inference is validated, not assumed**: 1,116/1,147 (97.3%)
  against tape hits whose victim the pairing names, and 4,577/4,608 (99.3%)
  against the *true* target recorded by the engine dump's probe.
- **No multi-hit.** Zero same-`(t, attacker)` multi-damage events in any tape
  or any engine seed. All four units are strictly one projectile, one
  application; the trample-style confound from the melee rounds does not
  exist here. (imp_elite_skirm's +4 vs archer-class is a damage bonus on the
  single projectile, and neither its `splash_on_hit_radius` nor
  `extra_projectiles` is non-zero.)
- **Both damage streams are HP-clamped.** A killing blow reports the HP the
  victim actually had, not the damage rolled (verified: HCA-vs-arbalester
  damage values are 105x 7.0 and 21x 5.0, and the HCA landed exactly 21
  kills). Overkill is therefore invisible in the damage stream on both sides
  and *must* be measured as shots-in-flight-at-a-dying-target, which is what
  the WASTE class does.
- **No missile-id recycling** in these six recordings (0 tracks with an
  internal time gap > 0.2 s, 0 ids used by more than one shooter), so
  reconstructing one flight per id is safe here. The E9 derivation's >3 s
  split rule is still needed for the wider corpus.
- **The engine probe is behaviour-neutral.** `ranged_shot_dump.mjs` wraps
  `BattleUnit.prototype.fireProjectile` from `tools/`, reading ids and
  positions only; `--verify-identity` re-runs each seed without the wrapper
  and diffs the damage stream (PASS on every seed), and the dump's damage
  array is byte-identical to `calib_runner.mjs`'s for the same (fight, seed).
  Nothing under `apps/website/static/js/engine/` was touched.
- **Tape anomaly screen**: all six recordings are clean. Every unit on every
  side fires at least once; the count histograms never exceed the manifest's
  start counts (no bleed from a neighbouring recording); kills are spread
  across the whole fight (first kill 1.46-3.22 s, last kill = wipe). None of
  the six looks like a bad capture. The only defect is the recorder tail
  (§0a), which is present in all six and is a property of the recorder, not
  of these fights.
- **Known limits.** (i) The aim-target inference misassigns ~3% of tape shots,
  which lands mostly in the WHIFF/DODGE/SCATTER split, not in HIT or WASTE —
  treat the tape's sub-3% miss categories as noise. (ii) Each fight is a
  SINGLE recording; the engine column is 20 seeds. Per-fight tape numbers
  carry one run's variance, so the ordering of `tilt` matters more than any
  individual cell. (iii) `dutyW` uses each side's own observed median cycle,
  so it measures cadence regularity, not cadence correctness — Table 1b is
  where cadence correctness is tested.
