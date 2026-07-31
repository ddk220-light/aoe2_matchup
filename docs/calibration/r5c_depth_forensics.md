# R5c forensics — what puts tape ranged units inside their reach lip

Measurement only. No engine file was edited. Every number below is produced by
`tools/simjs/ranged_depth_forensics.py`, which computes each statistic once and
feeds it either a recording's three streams or an engine run's shot dump, so a
tape number and an engine number are the same statistic and never two
implementations that happen to be named alike. It reuses
`ranged_fire_forensics`'s loaders, shot pairing, aim inference and
`engine_reach`, so it inherits their validation.

```
node tools/simjs/ranged_shot_dump.mjs --tags <the six> --seeds 20 \
     --out-dir D:/AI/aoe2_golden/shots_r5c
PYTHONPATH=. python tools/simjs/ranged_depth_forensics.py \
     --sim-runs-dir D:/AI/aoe2_golden/shots_r5c --seeds 20 --section all
```

Engine side: current `improved-simulation` HEAD (71cd4a9, post-R5b, all four
R5b rules on by their engine defaults), `tapebox` arena, 20 seeds per fight,
28,155 launches. Tape side: the six ranged recordings, 1,482 launches with a
resolvable target, of which 1,147 are *certain* — the victim is named by the
damage stream, not inferred.

`T` = tape, `E` = engine. Sides are `<owner>:<unit>` from the manifest's own
`owner` field, never the tag's word order.

---

## 0. The premise was measured against the wrong quantity

R5b's D4 approach margin was chosen against "the tape fires from 0.9–1.4 tiles
inside its reach". That figure is `ranged_fire_forensics.accuracy()`'s
`launch_range_med`, which is `shot["dist"]` — the length of the reconstructed
**flight**, `|impact point − launch point|`. On a tape neither endpoint is a
unit centre.

### 0a. Both endpoints are inset along the shot line

Restricted to the 1,147 shots whose victim the damage pairing names outright,
with each offset decomposed onto the shot line:

| fight | side | n | launch radial | (p10) | (p90) | launch **PERP** | impact radial | impact **PERP** | total inset |
|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 112 | +0.612 | 0.607 | 0.626 | **−0.000** | −0.239 | **−0.000** | 0.851 |
| arb v HC | 3:HC | 34 | +0.620 | 0.617 | 0.634 | **−0.011** | −0.256 | **−0.001** | 0.876 |
| arb v HCA | 2:arb | 230 | +0.612 | 0.606 | 0.626 | **−0.000** | −0.306 | **−0.000** | 0.919 |
| arb v HCA | 3:HCA | 126 | +0.611 | 0.604 | 0.625 | **−0.000** | −0.260 | **−0.000** | 0.871 |
| arb v skirm | 2:arb | 88 | +0.612 | 0.598 | 0.626 | **+0.000** | −0.253 | **−0.000** | 0.865 |
| arb v skirm | 3:skirm | 78 | +0.612 | 0.606 | 0.626 | **+0.000** | −0.243 | **−0.000** | 0.855 |
| skirm v HC | 2:skirm | 60 | +0.611 | 0.607 | 0.612 | **+0.000** | −0.287 | **−0.000** | 0.898 |
| skirm v HC | 3:HC | 21 | +0.620 | 0.612 | 0.635 | **+0.000** | −0.264 | **−0.000** | 0.884 |
| skirm v HCA | 2:skirm | 108 | +0.612 | 0.611 | 0.626 | **+0.000** | −0.319 | **+0.000** | 0.931 |
| skirm v HCA | 3:HCA | 56 | +0.610 | 0.601 | 0.624 | **−0.013** | −0.266 | **−0.001** | 0.875 |
| HCA v HC | 2:HCA | 126 | +0.616 | 0.604 | 0.625 | **−0.000** | −0.271 | **−0.000** | 0.886 |
| HCA v HC | 3:HC | 108 | +0.620 | 0.610 | 0.634 | **−0.000** | −0.299 | **−0.000** | 0.919 |

The projectile is first seen **0.610–0.620 tiles down-range of the shooter's
centre** and last seen **0.24–0.32 tiles short of the victim's centre**. Three
things make this geometry rather than an artefact of stream bookkeeping:

1. **The perpendicular component is zero on all twelve sides**, at both ends,
   to three decimals. A constant coordinate-frame skew between the units
   stream and the missiles stream would be a fixed *world* vector, whose
   perpendicular component swings with the firing direction; these are insets
   along the shot, the same size whatever direction the shot is fired in.
2. **It is not a sampling lag.** A one-tick delay before the first missile row
   would put the offset at `speed × Δt` and so scale with projectile speed. The
   hand cannoneer's bullet is 7% faster than the arbalester's arrow (7.482 vs
   6.998 tiles/s, measured) while its launch inset is 1.3% larger.
3. **It is not a radius.** The heavy cavalry archer's physics radius is 0.25
   tiles against 0.20 for the three foot units; its inset (0.611–0.619) is
   indistinguishable from theirs.

The units stream itself is the trustworthy frame: the melee corpus already
validated `engine_reach` against it to within 0.02 tiles of observed contact
distance, and §2 below shows the tape's ranged stopping distribution has its
ceiling on exactly the same formula.

### 0b. Correcting for it removes most of the residual

`depth` = `reach − range`, positive = inside the lip; `reach` is the engine's
own `inRange()` reach for that ordered pair.

| fight | side | reach | n(T) | T flight p50 | T **range** p50 | inset | T depth **by flight** | T depth **true** | E depth true |
|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 8.57 | 112 | 6.80 | 7.73 | 0.89 | 1.77 | **0.84** | 0.57 |
| arb v HC | 3:HC | 7.57 | 34 | 6.57 | 7.46 | 0.90 | 1.00 | **0.11** | 0.41 |
| arb v HCA | 2:arb | 8.62 | 230 | 6.65 | 7.61 | 0.93 | 1.96 | **1.01** | 0.98 |
| arb v HCA | 3:HCA | 7.62 | 126 | 6.64 | 7.52 | 0.87 | 0.97 | **0.10** | 0.29 |
| arb v skirm | 2:arb | 8.57 | 88 | 6.90 | 7.76 | 0.87 | 1.67 | **0.81** | 0.41 |
| arb v skirm | 3:skirm | 8.57 | 78 | 7.52 | 8.39 | 0.86 | 1.05 | **0.18** | 0.41 |
| skirm v HC | 2:skirm | 8.57 | 60 | 6.91 | 7.82 | 0.91 | 1.65 | **0.74** | 0.70 |
| skirm v HC | 3:HC | 7.57 | 21 | 6.63 | 7.51 | 0.87 | 0.94 | **0.06** | 0.41 |
| skirm v HCA | 2:skirm | 8.62 | 108 | 6.89 | 7.85 | 0.94 | 1.73 | **0.77** | 0.61 |
| skirm v HCA | 3:HCA | 7.62 | 56 | 6.63 | 7.51 | 0.88 | 0.99 | **0.10** | 0.50 |
| HCA v HC | 2:HCA | 7.62 | 126 | 6.36 | 7.23 | 0.88 | 1.26 | **0.39** | 0.34 |
| HCA v HC | 3:HC | 7.62 | 108 | 6.13 | 7.06 | 0.93 | 1.48 | **0.55** | 0.40 |

The "0.9–1.4 tiles inside reach" (here 0.94–1.96, same statistic on the same
tapes) is **0.85–0.93 tiles of anchor inset**. Measured centre-to-centre, the
tape fires from 0.06–1.01 tiles inside the lip and the current engine fires
from 0.29–0.98. That is why the R5b agent's D4 prediction disagreed with its
own spec by about 2×: the spec was fitted to a number that is roughly twice
the quantity it was believed to be.

Everything below measures range **centre-to-centre off the 10 Hz position
stream**, on both sources.

---

## 1. What the residual actually is

Two questions have to be kept apart, because the tape answers them
differently. `1a` is positioning only — no shot bookkeeping enters it.

### 1a. Where units STAND: `reach − dist(nearest living enemy)`, every unit-frame

| fight | side | reach | T p25 | T p50 | T p75 | **T p90** | T in% | E p25 | E p50 | E p75 | **E p90** | E in% | T−E p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 8.57 | 0.43 | 0.92 | 1.43 | 2.25 | 91 | 0.33 | 0.79 | 1.39 | 1.65 | 91 | +0.14 |
| arb v HC | 3:HC | 7.57 | 0.04 | 0.45 | 1.04 | 1.34 | 89 | 0.18 | 0.44 | 0.66 | 1.25 | 91 | 0.00 |
| arb v HCA | 2:arb | 8.62 | 0.83 | 1.12 | 1.86 | 2.53 | 97 | 0.65 | 1.10 | 1.40 | 1.52 | 99 | +0.02 |
| arb v HCA | 3:HCA | 7.62 | 0.05 | 0.18 | 0.91 | 1.91 | 93 | 0.01 | 0.21 | 0.51 | 0.55 | 82 | −0.03 |
| arb v skirm | 2:arb | 8.57 | 0.42 | 0.82 | 1.50 | 1.90 | 97 | 0.41 | 0.50 | 0.96 | 1.57 | 97 | +0.31 |
| arb v skirm | 3:skirm | 8.57 | 0.15 | 0.49 | 1.09 | 1.76 | 96 | 0.11 | 0.41 | 0.57 | 1.29 | 88 | +0.08 |
| skirm v HC | 2:skirm | 8.57 | 0.31 | 0.67 | 0.95 | 1.45 | 88 | 0.32 | 0.83 | 1.34 | 1.73 | 92 | −0.16 |
| skirm v HC | 3:HC | 7.57 | 0.03 | 0.12 | 0.59 | 0.88 | 82 | 0.21 | 0.57 | 0.61 | 1.28 | 90 | −0.45 |
| skirm v HCA | 2:skirm | 8.62 | 0.31 | 0.71 | 1.09 | 1.46 | 90 | 0.41 | 0.68 | 1.16 | 1.52 | 95 | +0.03 |
| skirm v HCA | 3:HCA | 7.62 | 0.10 | 0.32 | 0.80 | 0.99 | 92 | 0.24 | 0.50 | 0.55 | 0.91 | 95 | −0.18 |
| **HCA v HC** | **2:HCA** | 7.62 | 0.22 | 0.72 | **1.53** | **4.78** | 87 | 0.02 | 0.30 | 0.52 | **0.87** | 82 | **+0.42** |
| **HCA v HC** | **3:HC** | 7.62 | 0.41 | 0.95 | **3.17** | **4.85** | 95 | 0.35 | 0.42 | 0.62 | **0.96** | 96 | **+0.53** |

**The engine's typical stopping distance is right.** The median differs by
−0.45 to +0.53 tiles, mean absolute difference 0.20, and on five of twelve
sides by ≤0.08.

**What is missing is the deep tail, and it is one fight.** In five fights the
engine's p90 brackets the tape's (1.25–1.73 vs 0.88–2.53). In
`heavy_cav_archer__vs__hand_cannoneer` the tape's p90 is **4.78 / 4.85** and
the engine's is **0.87 / 0.96** — the engine never produces a unit standing
more than about a tile inside its reach, and the tape routinely has a quarter
of each army 1.5–5 tiles in.

### 1b. Where units SHOOT FROM: `reach − dist(the unit actually fired at)`

| fight | side | T n | T p10 | T p50 | T p90 | T sd | T settled p50 | E n | E p10 | E p50 | E p90 | E sd | E settled p50 | T−E p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 154 | 0.04 | 0.56 | 1.99 | 0.82 | 0.69 | 3134 | 0.03 | 0.57 | 1.57 | 0.66 | 0.68 | −0.01 |
| arb v HC | 3:HC | 43 | −1.96 | 0.06 | 0.82 | 0.91 | 0.04 | 920 | 0.01 | 0.41 | 0.86 | 0.48 | 0.41 | −0.34 |
| arb v HCA | 2:arb | 262 | 0.07 | 1.00 | 2.45 | 0.93 | 1.01 | 5280 | 0.38 | 0.98 | 1.52 | 0.53 | 1.01 | +0.02 |
| arb v HCA | 3:HCA | 155 | 0.00 | 0.09 | 0.55 | 0.46 | 0.09 | 3000 | 0.01 | 0.29 | 0.62 | 0.36 | 0.29 | −0.20 |
| arb v skirm | 2:arb | 96 | 0.06 | 0.75 | 1.92 | 0.83 | 0.81 | 1600 | 0.02 | 0.41 | 1.57 | 0.70 | 0.50 | +0.34 |
| arb v skirm | 3:skirm | 131 | −0.46 | 0.12 | 1.01 | 0.61 | 0.14 | 2560 | 0.02 | 0.41 | 1.36 | 0.60 | 0.41 | −0.28 |
| skirm v HC | 2:skirm | 101 | 0.15 | 0.66 | 1.50 | 0.63 | 0.57 | 2144 | 0.06 | 0.70 | 1.69 | 0.68 | 0.81 | −0.03 |
| skirm v HC | 3:HC | 26 | −1.35 | 0.05 | 0.36 | 1.09 | 0.05 | 522 | 0.01 | 0.41 | 1.48 | 0.56 | 0.41 | −0.35 |
| skirm v HCA | 2:skirm | 160 | 0.05 | 0.63 | 1.35 | 0.59 | 0.63 | 2740 | 0.16 | 0.61 | 1.55 | 0.62 | 0.62 | +0.02 |
| skirm v HCA | 3:HCA | 59 | −0.15 | 0.10 | 0.80 | 0.42 | 0.10 | 1240 | 0.02 | 0.50 | 0.91 | 0.46 | 0.50 | −0.40 |
| HCA v HC | 2:HCA | 171 | 0.02 | 0.32 | **2.83** | **1.29** | 0.32 | 3204 | 0.01 | 0.34 | 0.76 | 0.37 | 0.34 | −0.02 |
| HCA v HC | 3:HC | 124 | −0.57 | 0.48 | **4.52** | **2.04** | 0.55 | 1811 | 0.02 | 0.40 | 0.98 | 0.41 | 0.41 | +0.08 |

Same verdict from the shot side: the medians agree to within 0.40 on every
side, and the *spread* does not — tape sd 0.42–2.04 against engine 0.36–0.70,
with the whole excess concentrated in `HCA v HC`. Note also that the engine's
`settled p50` equals its `p50` on eleven of twelve sides, i.e. its launches
happen from a single pinned distance; the tape's does too, but around a much
wider distribution.

---

## 2. H4 — aim-at-body vs aim-at-edge: **REFUTED**

Four predicates differing only in which radii they count, plus the engine's:

```
C   = attack_range                              centre -> centre
SE  = attack_range + r_self                     own edge -> target centre
TE  = attack_range + r_target                   centre -> target edge
EE  = attack_range + r_self + r_target          edge -> edge
ENG = EE + MELEE_RANGE_BUFFER (5 px)            what BattleUnit.inRange() uses
```

Tape stopping distribution, certain-victim shots only:

| fight | side | C | SE | TE | EE | **ENG** | n | p50 | p90 | p99 | **max** | >C% | >SE% | >TE% | >EE% | **>ENG%** | E max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 8.00 | 8.20 | 8.20 | 8.40 | **8.57** | 112 | 7.73 | 8.43 | 8.55 | **8.55** | 41.1 | 25.9 | 25.9 | 13.4 | **0.0** | 8.57 |
| arb v HC | 3:HC | 7.00 | 7.20 | 7.20 | 7.40 | **7.57** | 34 | 7.46 | 7.56 | 8.31 | 8.38 | 79.4 | 79.4 | 79.4 | 67.6 | 8.8 | 7.57 |
| arb v HCA | 2:arb | 8.00 | 8.20 | 8.25 | 8.45 | **8.62** | 230 | 7.61 | 8.47 | 8.62 | **8.63** | 21.3 | 16.1 | 14.3 | 10.4 | **0.9** | 8.61 |
| arb v HCA | 3:HCA | 7.00 | 7.25 | 7.20 | 7.45 | **7.62** | 126 | 7.52 | 7.59 | 7.62 | **7.62** | 92.1 | 86.5 | 86.5 | 69.0 | **2.4** | 7.62 |
| arb v skirm | 2:arb | 8.00 | 8.20 | 8.20 | 8.40 | **8.57** | 88 | 7.76 | 8.47 | 8.52 | **8.52** | 34.1 | 25.0 | 25.0 | 18.2 | **0.0** | 8.56 |
| arb v skirm | 3:skirm | 8.00 | 8.20 | 8.20 | 8.40 | **8.57** | 78 | 8.39 | 8.50 | 8.67 | 8.73 | 73.1 | 64.1 | 64.1 | 41.0 | 3.8 | 8.57 |
| skirm v HC | 2:skirm | 8.00 | 8.20 | 8.20 | 8.40 | **8.57** | 60 | 7.82 | 8.27 | 8.54 | **8.56** | 35.0 | 18.3 | 18.3 | 5.0 | **0.0** | 8.57 |
| skirm v HC | 3:HC | 7.00 | 7.20 | 7.20 | 7.40 | **7.57** | 21 | 7.51 | 7.60 | 8.02 | 8.06 | 90.5 | 85.7 | 85.7 | 81.0 | 14.3 | 7.57 |
| skirm v HCA | 2:skirm | 8.00 | 8.20 | 8.25 | 8.45 | **8.62** | 108 | 7.85 | 8.55 | 8.63 | **8.63** | 34.3 | 27.8 | 24.1 | 13.0 | 3.7 | 8.61 |
| skirm v HCA | 3:HCA | 7.00 | 7.25 | 7.20 | 7.45 | **7.62** | 56 | 7.51 | 7.61 | 7.87 | 7.96 | 85.7 | 76.8 | 78.6 | 62.5 | 8.9 | 7.62 |
| HCA v HC | 2:HCA | 7.00 | 7.25 | 7.20 | 7.45 | **7.62** | 126 | 7.23 | 7.59 | 7.62 | **7.62** | 56.3 | 49.2 | 51.6 | 34.1 | **1.6** | 7.62 |
| HCA v HC | 3:HC | 7.00 | 7.20 | 7.25 | 7.45 | **7.62** | 108 | 7.06 | 7.58 | 8.19 | 8.60 | 52.8 | 40.7 | 40.7 | 33.3 | 3.7 | 7.62 |

**The tape's reach is the engine's reach.** On the nine arbalester / skirmisher
/ heavy-cavalry-archer sides, `>ENG%` is 0.0–8.9 and the observed maximum sits
on `ENG` to within 0.01–0.06 tiles — 7.62 against 7.62 exactly for both HCA
sides, 8.63 against 8.62 for the two arb/skirm-vs-HCA sides. The engine's own
maximum, which *is* `ENG` by construction, lands on the same number.

**H4 predicts the opposite of what is observed.** If the game approached on a
centre-to-centre predicate, no unit would ever be found firing from beyond `C`,
and the free burial would be a constant `r_self + r_target + buffer` = 0.57
tiles for foot pairs, 0.62 with a heavy cavalry archer. Instead 21.3–92.1% of
tape shots are fired from beyond `C`, 5.0–81.0% from beyond `EE`, and the
measured depth is not a constant — it runs 0.06 to 1.01 across sides, in a
pattern (§3) that tracks army geometry rather than radii.

The residual `>ENG%` (0.0–8.9 on nine sides; 8.8, 14.3 and 3.7 on the three
hand-cannoneer sides, n = 34, 21, 108) is not a second predicate: those shots
are 0.4–1.0 tiles beyond `ENG` with nothing in between, which is the signature
of a mis-paired damage event rather than a wider reach. They are too few to
move any median.

---

## 3. H1 — army depth: **SUPPORTS**, as a within-army gradient present in both

### 3a. Median launch depth by the shooter's rank (0 = frontmost) (n)

| fight | side | T r0 | T r1-2 | T r3-5 | T r6+ | E r0 | E r1-2 | E r3-5 | E r6+ |
|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 1.95 (10) | 1.11 (21) | 1.05 (29) | 0.36 (94) | 1.57 (194) | 1.57 (370) | 0.80 (571) | 0.44 (1996) |
| arb v HC | 3:HC | 0.53 (6) | 0.10 (10) | 0.02 (10) | 0.05 (17) | 0.57 (65) | 0.41 (214) | 0.42 (244) | 0.29 (393) |
| arb v HCA | 2:arb | 1.14 (25) | 1.08 (43) | 1.00 (56) | 0.79 (136) | 1.39 (600) | 1.08 (1000) | 1.09 (1200) | 0.57 (2440) |
| arb v HCA | 3:HCA | 0.10 (22) | 0.08 (40) | 0.10 (55) | 0.06 (38) | 0.51 (520) | 0.41 (940) | 0.17 (820) | 0.03 (720) |
| arb v skirm | 2:arb | 1.07 (13) | 0.81 (24) | 1.23 (25) | 0.37 (33) | 0.49 (240) | 0.57 (400) | 0.49 (440) | 0.41 (520) |
| arb v skirm | 3:skirm | 1.08 (6) | 0.22 (17) | 0.15 (20) | 0.10 (88) | 0.57 (140) | 0.54 (280) | 0.41 (420) | 0.34 (1720) |
| skirm v HC | 2:skirm | 1.36 (6) | 1.06 (12) | 0.85 (18) | 0.40 (65) | 1.57 (120) | 1.57 (240) | 1.11 (360) | 0.50 (1424) |
| skirm v HC | 3:HC | 0.05 (5) | 0.06 (9) | 0.04 (9) | −1.66 (2) | 0.41 (120) | 0.57 (140) | 0.41 (141) | 0.08 (121) |
| skirm v HCA | 2:skirm | 1.26 (9) | 1.06 (18) | 0.85 (27) | 0.38 (106) | 1.55 (160) | 1.43 (320) | 0.89 (480) | 0.44 (1780) |
| skirm v HCA | 3:HCA | 0.09 (15) | 0.18 (22) | 0.08 (19) | −0.19 (3) | 0.52 (280) | 0.50 (380) | 0.33 (400) | 0.34 (180) |
| **HCA v HC** | **2:HCA** | **2.06** (18) | 1.10 (31) | 0.45 (47) | 0.14 (75) | 0.62 (271) | 0.55 (519) | 0.43 (734) | 0.15 (1666) |
| **HCA v HC** | **3:HC** | **4.50** (11) | 3.50 (22) | 2.12 (27) | 0.09 (64) | 0.41 (162) | 0.37 (314) | 0.41 (360) | 0.40 (970) |

The gradient is real and it is monotone on eleven of twelve sides in each
source: the frontmost unit fires from deep inside the lip, the rear rank fires
from the lip itself. **But the engine already reproduces it.** The tape's
front-minus-rear gap is 0.03–4.21 tiles (median across sides ≈1.10) and the
engine's is 0.07–1.40 (median ≈0.42) — the same shape, roughly half the
amplitude, and the difference is dominated by one fight.

### 3b. Army depth along the threat axis vs front/rear launch depth

| fight | side | reach | T armydep | T front | T rear | T f−r | E armydep | E front | E rear | E f−r |
|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 8.57 | 2.77 | 1.95 | 0.03 | 1.92 | 2.56 | 1.57 | 0.16 | 1.40 |
| arb v HC | 3:HC | 7.57 | 2.02 | 0.53 | −2.00 | 2.53 | 1.81 | 0.57 | 0.29 | 0.28 |
| arb v HCA | 2:arb | 8.62 | 2.40 | 1.14 | 0.72 | 0.42 | 1.46 | 1.39 | 0.83 | 0.56 |
| arb v HCA | 3:HCA | 7.62 | 1.14 | 0.10 | 0.06 | 0.04 | 1.50 | 0.51 | 0.06 | 0.44 |
| arb v skirm | 2:arb | 8.57 | 2.39 | 1.07 | 0.12 | 0.95 | 1.30 | 0.49 | 0.40 | 0.09 |
| arb v skirm | 3:skirm | 8.57 | 1.75 | 1.08 | 0.07 | 1.01 | 1.82 | 0.57 | 0.17 | 0.40 |
| skirm v HC | 2:skirm | 8.57 | 2.27 | 1.36 | 0.16 | 1.20 | 2.10 | 1.57 | 0.19 | 1.38 |
| skirm v HC | 3:HC | 7.57 | 0.91 | 0.05 | 0.02 | 0.03 | 1.17 | 0.41 | 0.29 | 0.12 |
| skirm v HCA | 2:skirm | 8.62 | 1.83 | 1.26 | 0.07 | 1.18 | 1.95 | 1.55 | 0.24 | 1.31 |
| skirm v HCA | 3:HCA | 7.62 | 0.79 | 0.09 | 0.05 | 0.04 | 1.08 | 0.52 | 0.25 | 0.28 |
| **HCA v HC** | **2:HCA** | 7.62 | **4.26** | 2.06 | 0.15 | 1.91 | 1.97 | 0.62 | 0.06 | 0.56 |
| **HCA v HC** | **3:HC** | 7.62 | 2.54 | **4.50** | 0.29 | 4.21 | 1.73 | 0.41 | 0.34 | 0.07 |

Army depth itself matches (tape 0.79–2.77 vs engine 1.08–2.56) in five fights.

### 3c. Army shape over the last third — closure vs spread

| fight | side | reach | T sep | T depth | T width | E sep | E depth | E width | sep T−E | depth T−E |
|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 8.57 | 8.14 | 1.68 | 4.31 | 8.11 | 2.09 | 4.67 | +0.03 | −0.41 |
| arb v HC | 3:HC | 7.57 | 8.15 | 0.43 | 2.19 | 8.09 | 0.72 | 1.48 | +0.06 | −0.29 |
| arb v HCA | 2:arb | 8.62 | 7.53 | 0.35 | 1.23 | 7.63 | 0.94 | 1.78 | −0.10 | −0.59 |
| arb v HCA | 3:HCA | 7.62 | 7.53 | 0.60 | 5.10 | 7.60 | 0.35 | 1.62 | −0.07 | +0.25 |
| arb v skirm | 2:arb | 8.57 | 8.27 | 0.76 | 0.78 | 8.43 | 0.78 | 0.66 | −0.16 | −0.02 |
| arb v skirm | 3:skirm | 8.57 | 8.27 | 1.28 | 7.91 | 8.30 | 1.77 | 7.65 | −0.03 | −0.49 |
| skirm v HC | 2:skirm | 8.57 | 7.91 | 2.91 | 6.57 | 7.73 | 1.45 | 5.51 | +0.18 | +1.46 |
| skirm v HC | 3:HC | 7.57 | 7.91 | 0.01 | 0.99 | 7.27 | 0.79 | 1.91 | +0.64 | −0.78 |
| skirm v HCA | 2:skirm | 8.62 | 8.12 | 1.68 | 3.37 | 7.71 | 1.95 | 5.81 | +0.41 | −0.27 |
| skirm v HCA | 3:HCA | 7.62 | 8.12 | 0.11 | 3.68 | 7.70 | 0.39 | 1.01 | +0.42 | −0.28 |
| **HCA v HC** | **2:HCA** | 7.62 | **5.26** | **6.25** | 5.87 | **7.57** | **1.62** | 6.25 | **−2.31** | **+4.63** |
| **HCA v HC** | **3:HC** | 7.62 | **5.19** | 0.83 | 2.46 | **7.60** | 0.87 | 3.36 | **−2.41** | −0.04 |

This is the sharpest single statement in the round. In five fights the engine's
late-fight army shape is the tape's, to within 0.64 tiles on separation and
1.46 on depth. In `HCA v HC` the tape's heavy cavalry archer army is a **6.25-tile-
deep** formation whose centroid sits 5.26 tiles from the enemy, and the engine's
is a **1.62-tile-deep flat line parked at 7.57**. The *width* is the same
(5.87 vs 6.25), so this is not envelopment — it is the army stringing out
**along the threat axis**, individual units driving into the hand-cannoneer
blob while the rest hang back.

---

## 4. H2 — target-motion chase-in: **REFUTED**

### 4a. Median launch depth by the target's motion over the preceding 1 s (n)

| fight | side | T still | T lateral | T fleeing | T closing | E still | E lateral | E fleeing | E closing |
|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 0.54 (111) | 0.59 (8) | – | 0.64 (35) | 0.57 (2449) | 0.70 (56) | – | 0.86 (629) |
| arb v HC | 3:HC | 0.05 (33) | 0.04 (3) | 0.12 (4) | 0.33 (3) | 0.41 (920) | – | – | – |
| arb v HCA | 2:arb | 1.00 (208) | 0.96 (6) | – | 0.96 (48) | 0.98 (4700) | 0.92 (80) | – | 0.88 (500) |
| arb v HCA | 3:HCA | 0.09 (154) | 0.17 (1) | – | – | 0.29 (3000) | – | – | – |
| arb v skirm | 2:arb | 0.68 (83) | 0.28 (1) | – | 1.43 (12) | 0.41 (1560) | – | – | 0.03 (40) |
| arb v skirm | 3:skirm | 0.14 (121) | −0.09 (1) | 1.10 (3) | −0.71 (6) | 0.41 (2420) | – | – | 0.27 (140) |
| skirm v HC | 2:skirm | 0.57 (81) | 0.75 (6) | – | 0.67 (14) | 0.70 (1742) | 0.26 (2) | – | 0.76 (400) |
| skirm v HC | 3:HC | 0.05 (18) | −0.44 (2) | 0.15 (2) | −1.93 (4) | 0.41 (513) | – | – | 0.00 (9) |
| skirm v HCA | 2:skirm | 0.63 (157) | – | – | 0.32 (3) | 0.62 (2360) | 0.23 (60) | – | 0.48 (320) |
| skirm v HCA | 3:HCA | 0.10 (50) | 0.64 (2) | 0.33 (6) | −0.50 (1) | 0.50 (1240) | – | – | – |
| HCA v HC | 2:HCA | 0.30 (164) | 1.18 (4) | – | 0.32 (3) | 0.34 (3167) | 0.42 (6) | – | 0.41 (31) |
| HCA v HC | 3:HC | 0.48 (91) | −0.69 (8) | – | 1.20 (25) | 0.41 (1670) | 0.00 (40) | – | 0.21 (101) |

### 4b. Pooled, all six fights and both sides

| src | target motion | n | depth p50 | depth p90 |
|---|---|---|---|---|
| tape | \|v\| ≤ 0.05 | **1271** | 0.42 | 1.87 |
| tape | 0.05–0.4 | 94 | 0.66 | 1.98 |
| tape | 0.4–0.9 | 65 | 0.45 | 1.11 |
| tape | > 0.9 | 52 | 1.21 | 3.51 |
| tape | radial < −0.3 (closing) | 113 | 0.73 | 3.00 |
| tape | −0.3 … 0.3 | 1359 | 0.42 | 1.88 |
| tape | radial > 0.3 (**fleeing**) | **10** | **0.14** | 1.17 |
| engine | \|v\| ≤ 0.05 | 25741 | 0.50 | 1.50 |
| engine | 0.05–0.4 | 1265 | 0.72 | 1.33 |
| engine | 0.4–0.9 | 1044 | 0.57 | 1.29 |
| engine | > 0.9 | 105 | 0.69 | 1.16 |
| engine | radial < −0.3 (closing) | 1522 | 0.60 | 1.29 |
| engine | −0.3 … 0.3 | 26633 | 0.50 | 1.50 |
| engine | radial > 0.3 (fleeing) | 0 | – | – |

Chase-in requires depth on a moving target to exceed depth on a stationary
one, and it requires the moving targets to exist. Neither holds:

- **86% of tape launches (1,271 / 1,482) are at a target that has not moved**
  in the preceding second, and their depth (0.42) is the corpus median. The
  residual cannot be produced by a population that is 14% of the shots.
- **Fleeing targets are ten shots in the whole corpus**, and they are the
  *shallowest* bucket (0.14), not the deepest. The overshoot story predicts the
  opposite sign.
- The one bucket that is deeper — targets closing at >0.3 tiles/s, 0.73 vs
  0.42 — is deeper in the engine too (0.60 vs 0.50), by the same margin. This
  is the trivial fact that a target walking toward you is closer when you shoot
  it, not a mechanism the engine is missing.

---

## 5. H3 — re-approach after a retarget: **REFUTED**

### 5a. Median launch depth by shot index since retarget (n)

| fight | side | T 1st | T 2nd | T 3rd | T 4th+ | E 1st | E 2nd | E 3rd | E 4th+ |
|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 0.59 (147) | 0.30 (7) | – | – | 0.57 (2284) | 0.64 (644) | 0.57 (129) | 0.48 (77) |
| arb v HC | 3:HC | 0.07 (40) | 0.05 (3) | – | – | 0.40 (761) | 0.41 (141) | 0.41 (18) | – |
| arb v HCA | 2:arb | 0.99 (193) | 1.04 (62) | 1.00 (6) | 1.01 (1) | 0.75 (1960) | 0.99 (1200) | 1.00 (800) | 1.02 (1320) |
| arb v HCA | 3:HCA | 0.08 (99) | 0.09 (41) | 0.09 (9) | 0.10 (6) | 0.28 (1920) | 0.41 (820) | 0.22 (240) | 0.51 (20) |
| arb v skirm | 2:arb | 0.75 (65) | 0.87 (24) | 0.17 (5) | 0.61 (2) | 0.50 (660) | 0.57 (420) | 0.41 (240) | 0.41 (280) |
| arb v skirm | 3:skirm | 0.10 (102) | 0.17 (23) | 0.14 (4) | 0.18 (2) | 0.41 (2280) | 0.32 (260) | 0.02 (20) | – |
| skirm v HC | 2:skirm | 0.66 (99) | 0.43 (2) | – | – | 0.66 (1849) | 1.19 (295) | – | – |
| skirm v HC | 3:HC | 0.05 (23) | 0.05 (3) | – | – | 0.41 (416) | 0.41 (103) | 0.20 (2) | 0.29 (1) |
| skirm v HCA | 2:skirm | 0.65 (134) | 0.61 (26) | – | – | 0.58 (2000) | 0.59 (560) | 0.75 (120) | 1.16 (60) |
| skirm v HCA | 3:HCA | 0.09 (19) | 0.08 (14) | 0.09 (10) | 0.10 (16) | 0.34 (600) | 0.51 (440) | 0.42 (160) | 0.51 (40) |
| HCA v HC | 2:HCA | 0.34 (158) | 0.17 (13) | – | – | 0.31 (2196) | 0.40 (755) | 0.50 (236) | 0.18 (17) |
| HCA v HC | 3:HC | 0.48 (99) | 1.15 (17) | 0.16 (5) | 0.08 (3) | 0.41 (1211) | 0.41 (415) | 0.40 (127) | 0.34 (58) |

### 5b. Pooled depth vs the shooter's own launch gap

| src | bucket | n | depth p50 | moving% |
|---|---|---|---|---|
| tape | first launch of the unit | 207 | 0.37 | 0 |
| tape | gap ≤ 2.5 s | 710 | 0.55 | 0 |
| tape | gap 2.5–5 s | 523 | 0.37 | 0 |
| tape | gap > 5 s | 42 | **0.10** | 0 |
| engine | first launch of the unit | 4140 | 0.55 | 0 |
| engine | gap ≤ 2.5 s | 13563 | 0.52 | 0 |
| engine | gap 2.5–5 s | 9743 | 0.41 | 0 |
| engine | gap > 5 s | 709 | **0.04** | 0 |

The prediction is a deep first shot that relaxes on later shots at the same
target. The tape's first-shot-after-retarget depth is within 0.30 of its second
on eleven of twelve sides, and it is *lower* on five of them. Pooled, the tape's
first-ever launch (0.37) is shallower than its steady-state (0.55), and depth
**falls** monotonically as the launch gap grows — 0.55 → 0.37 → 0.10 — where
momentum overshoot predicts a rise. The engine shows the identical shape
(0.52 → 0.41 → 0.04). A long gap means the unit lost its target and walked
*outward* or waited, not that it overran a new one.

`moving%` is 0 in every bucket in both sources: essentially no launch in this
corpus happens while the shooter is displaced (R5b's D1 stop-to-fire on the
engine side; the tape's own behaviour on the other).

---

## 6. H5 — `heavy_cav_archer__vs__hand_cannoneer`, the one residual

### 6a. Closure timeline, 30 buckets

`T` = tape; `E` = the median-duration engine seed. `dmin`/`dmed` = distance to
the nearest living enemy, minimum and median over the side's units. `rch%` =
share of the side with an enemy inside its own reach. `rad` = centroid radial
speed, + = closing. `sh/us` = launches per living-unit-second. `dep` = median
launch depth in the bucket.

| src | t | sep | HCA n | HCA dmin | HCA dmed | HCA rch% | HCA rad | HCA sh/us | HCA dep | HC n | HC dmin | HC dmed | HC rch% | HC rad | HC sh/us | HC dep |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T | 0.7 | 9.03 | 19 | 5.00 | 7.28 | 53 | 0.10 | 0.347 | 1.29 | 21 | 5.00 | 7.28 | 71 | 0.00 | 0.000 | – |
| T | 2.1 | 8.44 | 19 | 5.00 | 7.07 | 79 | 0.10 | 0.000 | – | 21 | 5.00 | 7.01 | 95 | 0.32 | 0.592 | 0.03 |
| T | 3.4 | 8.18 | 18 | 5.57 | 7.25 | 67 | 0.02 | 0.041 | 0.12 | 20 | 5.57 | 7.23 | 80 | 0.31 | 0.146 | 0.15 |
| T | 4.8 | 8.18 | 18 | 5.57 | 7.12 | 72 | −0.04 | 0.488 | 0.46 | 20 | 5.57 | 7.00 | 95 | 0.14 | 0.146 | 0.32 |
| T | 6.2 | 8.06 | 18 | 5.57 | 6.88 | 89 | 0.05 | 0.325 | 1.27 | 19 | 5.57 | 6.97 | 95 | 0.15 | 0.308 | 0.47 |
| T | 7.5 | 8.04 | 17 | 5.51 | 7.05 | 71 | 0.20 | 0.301 | 0.72 | 18 | 5.51 | 7.00 | 94 | −0.29 | 0.081 | 0.04 |
| T | 8.9 | 7.91 | 17 | 5.51 | 7.05 | 88 | 0.11 | 0.129 | 0.02 | 18 | 5.51 | 7.00 | 100 | 0.06 | 0.366 | 0.09 |
| T | 10.3 | 7.96 | 16 | 5.99 | 7.20 | 81 | −0.23 | 0.366 | 0.67 | 18 | 5.99 | 7.04 | 83 | 0.11 | 0.203 | 0.16 |
| T | 11.6 | 7.76 | 16 | 6.42 | 7.27 | 69 | 0.30 | 0.320 | 0.45 | 17 | 6.42 | 7.07 | 100 | 0.00 | 0.172 | 0.21 |
| T | 13.0 | 7.72 | 16 | 6.07 | 7.21 | 75 | 0.02 | 0.137 | 0.16 | 17 | 6.07 | 7.07 | 100 | 0.00 | 0.301 | −0.43 |
| T | 14.4 | 7.42 | 15 | 4.45 | 6.96 | 93 | 0.18 | 0.244 | 0.22 | 17 | 4.45 | 6.79 | 100 | 0.00 | 0.172 | 0.47 |
| T | 15.7 | 7.00 | 15 | **2.78** | 6.87 | 93 | 0.33 | 0.195 | 0.17 | 15 | 2.78 | **5.23** | 100 | 0.00 | 0.537 | 0.08 |
| T | 17.1 | 6.76 | 15 | 2.20 | 6.77 | 87 | 0.03 | 0.098 | 0.10 | 14 | 2.20 | 4.54 | 100 | 0.08 | 0.209 | 0.40 |
| T | 18.5 | 6.56 | 15 | 2.01 | 6.24 | 100 | 0.07 | 0.683 | 0.75 | 14 | 2.01 | 4.40 | 100 | 0.00 | 0.105 | **2.00** |
| T | 19.8 | 6.50 | 13 | 2.01 | 6.48 | 92 | 0.30 | 0.281 | 0.13 | 13 | 2.01 | 4.65 | 100 | 0.00 | 0.169 | **4.15** |
| T | 21.2 | 6.37 | 13 | 2.01 | 6.48 | 100 | 0.05 | 0.281 | 0.03 | 13 | 2.01 | 4.65 | 100 | 0.00 | 0.169 | **4.30** |
| T | 22.6 | 6.39 | 12 | 2.30 | 6.32 | 100 | 0.17 | 0.366 | 0.28 | 12 | 2.30 | 4.98 | 100 | 0.00 | 0.549 | 1.63 |
| T | 23.9 | 6.33 | 11 | 2.86 | 6.54 | 100 | −0.15 | 0.200 | 0.07 | 11 | 2.86 | 5.55 | 100 | 0.04 | 0.200 | 3.50 |
| T | 25.3 | 5.75 | 11 | 2.81 | 6.44 | 91 | 0.43 | 0.399 | 0.12 | 10 | 2.81 | 5.01 | 100 | 0.00 | 0.073 | 2.12 |
| T | 26.7 | 5.36 | 11 | 2.62 | 6.44 | 100 | 0.23 | 0.133 | 0.11 | 10 | 2.62 | 4.85 | 100 | 0.00 | 0.439 | 1.88 |
| T | 28.0 | 5.21 | 10 | 2.06 | 6.50 | 100 | −0.14 | 0.658 | 0.11 | 9 | 2.06 | 3.78 | 100 | 0.00 | 0.244 | 3.82 |
| T | 29.4 | 4.93 | 10 | 1.45 | 6.42 | 100 | 0.11 | 0.293 | 0.17 | 7 | 1.45 | 2.77 | 100 | 0.41 | 0.314 | 3.43 |
| T | 30.8 | 4.86 | 10 | 1.45 | 6.33 | 100 | 0.00 | 0.585 | 0.08 | 7 | 1.45 | 2.77 | 100 | 0.00 | 0.418 | **5.08** |
| T | 32.1 | 4.84 | 10 | 1.45 | 6.33 | 100 | 0.02 | 0.073 | 0.04 | 6 | 1.45 | 2.69 | 100 | 0.00 | 0.122 | 3.12 |
| T | 33.5 | 4.96 | 10 | 1.80 | 6.57 | 100 | 0.00 | 0.658 | 1.22 | 5 | 1.80 | 2.77 | 100 | −0.22 | 0.293 | 4.74 |
| T | 34.9 | 5.30 | 9 | 1.80 | 6.82 | 100 | 0.00 | 0.732 | 0.80 | 4 | 1.80 | 2.87 | 100 | 0.00 | 0.183 | 5.00 |
| T | 36.2 | 5.48 | 9 | 2.62 | 7.07 | 89 | −0.06 | 0.406 | 3.29 | 3 | 2.62 | 3.12 | 100 | −0.25 | 0.488 | 3.96 |
| T | 37.6 | 5.45 | 9 | 2.62 | 7.07 | 100 | 0.04 | 0.244 | 0.13 | 3 | 2.62 | 3.12 | 100 | 0.00 | 0.244 | 5.00 |
| T | 39.0 | 5.48 | 9 | 2.62 | 7.21 | 100 | 0.00 | 0.732 | 0.40 | 2 | 2.62 | 3.40 | 100 | −0.08 | 0.000 | – |
| T | 40.3 | 5.36 | 9 | 2.62 | 7.21 | 100 | 0.10 | 0.325 | 2.22 | 1 | 2.62 | 2.62 | 100 | 0.22 | 0.732 | 3.43 |
| E | 0.5 | 8.70 | 19 | 5.00 | 7.28 | 79 | 0.51 | 0.000 | – | 21 | 5.00 | 7.28 | 90 | 0.24 | 0.969 | 0.55 |
| E | 1.4 | 8.62 | 18 | 6.00 | 7.40 | 83 | −0.19 | 0.952 | 0.55 | 21 | 6.00 | 7.63 | 43 | 0.20 | 0.051 | 0.01 |
| E | 2.3 | 8.07 | 18 | 6.32 | 7.40 | 83 | 0.36 | 0.416 | 0.62 | 20 | 6.32 | 7.25 | 90 | 0.21 | 0.054 | 0.01 |
| E | 3.3 | 7.90 | 18 | 6.32 | 7.34 | 89 | 0.01 | 0.476 | 0.02 | 20 | 6.32 | 7.20 | 100 | 0.10 | 0.000 | – |
| E | 4.2 | 7.68 | 18 | 6.55 | 7.38 | 78 | 0.51 | 0.238 | 0.62 | 19 | 6.55 | 7.20 | 100 | 0.02 | 0.845 | 0.41 |
| E | 5.1 | 7.66 | 18 | 6.55 | 7.35 | 83 | **0.00** | 0.654 | 0.06 | 19 | 6.55 | 7.20 | 100 | 0.01 | 0.056 | 0.35 |
| E | 6.1 | 7.52 | 17 | 6.55 | 7.20 | 94 | 0.07 | 0.189 | 0.62 | 19 | 6.55 | 7.20 | 100 | 0.00 | 0.113 | 0.51 |
| E | 7.0 | 7.51 | 17 | 6.55 | 7.11 | 94 | **0.00** | 0.630 | 0.15 | 18 | 6.55 | 7.20 | 100 | −0.00 | 0.654 | 0.43 |
| E | 7.9 | 7.50 | 17 | 6.55 | 7.25 | 88 | 0.03 | 0.126 | 0.67 | 16 | 6.55 | 7.18 | 100 | −0.06 | 0.335 | 0.40 |
| E | 8.9 | 7.49 | 17 | 6.55 | 7.25 | 88 | **−0.00** | 0.756 | 0.30 | 16 | 6.55 | 7.17 | 100 | 0.03 | 0.000 | – |
| E | 9.8 | 7.49 | 17 | 6.55 | 7.27 | 94 | 0.01 | 0.126 | 0.83 | 15 | 6.55 | 7.19 | 100 | −0.03 | 0.071 | 0.98 |
| E | 10.7 | 7.55 | 17 | 6.55 | 7.27 | 88 | −0.01 | 0.441 | 0.50 | 13 | 6.55 | 7.14 | 100 | 0.00 | 0.659 | 0.34 |
| E | 11.7 | 7.43 | 17 | 6.55 | 7.06 | 100 | 0.11 | 0.315 | 0.87 | 12 | 6.55 | 7.15 | 100 | 0.01 | 0.357 | 0.40 |
| E | 12.6 | 7.50 | 15 | 6.55 | 7.10 | 100 | **0.00** | 0.857 | 0.41 | 12 | 6.55 | 7.15 | 100 | 0.00 | 0.000 | – |
| E | 13.5 | 7.62 | 14 | 6.76 | 7.18 | 93 | 0.01 | 0.000 | – | 9 | 6.76 | 7.20 | 100 | −0.12 | 0.000 | – |
| E | 14.5 | 7.74 | 14 | 6.76 | 7.52 | 71 | 0.01 | 0.153 | 0.41 | 8 | 6.76 | 7.24 | 100 | 0.00 | 0.803 | 0.30 |
| E | 15.4 | 7.65 | 14 | 6.76 | 7.44 | 93 | 0.06 | 0.306 | 0.23 | 8 | 6.76 | 7.15 | 100 | 0.00 | 0.268 | 0.41 |
| E | 16.3 | 7.63 | 14 | 6.76 | 7.36 | 93 | 0.04 | 0.688 | 0.21 | 8 | 6.76 | 7.15 | 100 | 0.00 | 0.000 | – |
| E | 17.3 | 7.77 | 14 | 6.76 | 7.57 | 71 | **−0.00** | 0.076 | 0.86 | 7 | 6.76 | 7.20 | 100 | −0.24 | 0.000 | – |
| E | 18.2 | 7.73 | 14 | 6.76 | 7.43 | 79 | 0.08 | 0.459 | 0.16 | 7 | 6.76 | 7.20 | 100 | 0.00 | 0.765 | 0.28 |
| E | 19.1 | 7.59 | 13 | 7.09 | 7.34 | 100 | −0.10 | 0.494 | 0.19 | 6 | 7.09 | 7.30 | 100 | 0.12 | 0.178 | 0.40 |
| E | 20.1 | 7.57 | 13 | 7.09 | 7.34 | 92 | −0.01 | 0.329 | 0.04 | 5 | 7.09 | 7.27 | 100 | 0.00 | 0.000 | – |
| E | 21.0 | 7.73 | 13 | 7.21 | 7.56 | 69 | **−0.00** | 0.329 | 0.26 | 4 | 7.21 | 7.31 | 100 | 0.00 | 0.535 | 0.30 |
| E | 21.9 | 7.73 | 13 | 7.21 | 7.56 | 69 | **−0.00** | 0.329 | 0.15 | 4 | 7.21 | 7.31 | 100 | 0.00 | 0.535 | 0.19 |
| E | 22.9 | 7.66 | 13 | 7.11 | 7.61 | 62 | 0.30 | 0.082 | 0.41 | 3 | 7.11 | 7.21 | 100 | 0.00 | 0.000 | – |
| E | 23.8 | 7.49 | 13 | 7.11 | 7.37 | 85 | 0.34 | 0.577 | 0.25 | 3 | 7.11 | 7.21 | 100 | 0.00 | 0.000 | – |
| E | 24.7 | 7.34 | 13 | 7.10 | 7.21 | 92 | 0.06 | 0.082 | 0.41 | 3 | 7.10 | 7.21 | 100 | 0.00 | 0.714 | 0.30 |
| E | 25.7 | 7.45 | 13 | 7.10 | 7.58 | 62 | 0.16 | 0.165 | 0.09 | 2 | 7.10 | 7.15 | 100 | 0.00 | 0.000 | – |
| E | 26.6 | 7.17 | 12 | 7.09 | 7.44 | 83 | 0.17 | 0.535 | 0.14 | 1 | 7.09 | 7.44 | 100 | 0.00 | 0.000 | – |
| E | 27.5 | 7.17 | 12 | 7.09 | 7.44 | 75 | **−0.00** | 0.357 | 0.51 | 1 | 7.09 | 7.09 | 100 | 0.00 | 0.000 | – |

### 6b. Who crosses into reach first

| src | side | reach | t first unit in reach | t 90% of side in reach | t first launch | wipe |
|---|---|---|---|---|---|---|
| T | 2:HCA | 7.62 | 0.20 | 6.36 | 1.21 | 41.01 |
| T | 3:HC | 7.62 | 0.20 | 1.94 | 1.55 | 41.01 |
| E | 2:HCA | 7.62 | 0.02 | 5.72 | 0.95 | 28.02 |
| E | 3:HC | 7.62 | 0.02 | 0.52 | 0.43 | 28.02 |

Neither side "crosses in first" in any meaningful sense — the tapebox spawn
already puts one unit of each side 5.00 tiles from the other, inside both
reaches, at t = 0.2, in both sources. The immobile side (hand cannoneer, speed
0) is fully engaged first in both (1.94 s tape, 0.52 s engine), simply because
it never has to walk.

**The engagement shape that produces the tape's result.** It is neither a
drive-by nor a stand-and-trade at 5.3. It is a **40-second one-sided grind-in
by the heavy cavalry archers against a hand-cannoneer army that never moves**:

1. The hand cannoneers stand. `HC rad` is 0.00 in 21 of the tape's 30 buckets
   and its cumulative closure over the fight is +0.89 tiles (§7 below), all of
   it in the first 6 s. It has 94–100% of its units in reach from t = 2 onward
   and fires at 0.07–0.73 launches per unit-second throughout. It is a static
   gun line.
2. The heavy cavalry archers walk in, slowly, all fight. `HCA rad` is positive
   in 20 of 30 buckets, typically 0.02–0.43 tiles/s, and never stops:
   separation goes 9.03 → 8.04 (t = 7.5) → 7.00 (t = 15.7) → 6.37 (t = 21.2) →
   5.36 (t = 26.7) → 4.84 (t = 32.1). Cumulative +3.06 tiles.
3. The army strings out rather than advancing as a line. `HCA dmin` collapses
   from 5.57 to 2.78 at t = 15.7 and to **1.45** by t = 29.4, while `HCA dmed`
   never leaves 6.24–7.28 — the median heavy cavalry archer stays about a tile
   inside its own lip for the entire fight while a handful of them ride into
   the gun line. That is the 6.25-tile army depth of §3c.
4. The consequence lands on the hand cannoneer, not on the archer. `HC dmed`
   falls 7.28 → 5.23 (t = 15.7) → 4.40 (t = 18.5) → **2.77** (t = 29.4), and
   `HC dep` — the depth the hand cannoneers are firing from — steps up from
   ~0.1–0.5 for the first 17 s to **2.0, 4.15, 4.30, 3.50, 3.82, 5.08, 4.74,
   5.00** for the rest. The hand cannoneers are not deep because they advanced;
   they are deep because the archers arrived.

The engine reproduces step 1 and the first 5 s of step 2, then stops.
`HCA rad` is 0.00 or −0.00 to two decimals in eight buckets after t = 5 and
never exceeds 0.34; `HCA dmin` plateaus at 6.55 from t = 4.2 to t = 18.2 and
then *increases* to 7.09–7.21; separation ends at 7.17, above the 7.62 reach
minus a body diameter. `HC dep` stays 0.19–0.98 all fight. The tape's fight
runs 41.01 s, the engine's 28.02 s.

---

## 7. Closure budget — a one-shot margin vs a sustained walk-in

`net` = cumulative centroid displacement toward the enemy over the whole fight
(tiles, + = closed in). `close/hold/back%` = share of 0.1 s steps with radial
speed above +0.05 / within ±0.05 / below −0.05 tiles/s. `d1/d2/d3` = median
standoff depth (§1a) in the first / middle / last third.

| fight | side | T net | T close% | T hold% | T back% | T d1 | T d2 | T d3 | E net | E close% | E hold% | E back% | E d1 | E d2 | E d3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 0.80 | 38 | 55 | 7 | 1.05 | 1.17 | 0.50 | 0.56 | 37 | 60 | 3 | 0.54 | 1.17 | 0.63 |
| arb v HC | 3:HC | 0.61 | 46 | 46 | 8 | 0.74 | 0.74 | 0.04 | 0.81 | 54 | 39 | 7 | 0.44 | 0.60 | 0.36 |
| arb v HCA | 2:arb | −0.82 | 9 | 86 | 5 | 1.55 | 0.91 | 0.99 | −1.22 | 8 | 88 | 4 | 0.96 | 1.18 | 1.21 |
| arb v HCA | 3:HCA | 3.13 | 24 | 74 | 2 | 0.91 | 0.11 | 0.03 | 3.43 | 32 | 65 | 3 | 0.17 | 0.20 | 0.28 |
| arb v skirm | 2:arb | −0.67 | 11 | 84 | 5 | 1.23 | 0.81 | 0.42 | −1.01 | 26 | 69 | 6 | 0.59 | 0.41 | 0.41 |
| arb v skirm | 3:skirm | 1.65 | 37 | 61 | 1 | 1.38 | 0.48 | 0.13 | 2.02 | 36 | 63 | 1 | 0.53 | 0.40 | 0.16 |
| skirm v HC | 2:skirm | 0.97 | 27 | 67 | 6 | 0.74 | 0.57 | 0.67 | 0.84 | 29 | 69 | 2 | 0.50 | 0.84 | 1.13 |
| skirm v HC | 3:HC | 0.85 | 31 | 65 | 4 | 0.47 | 0.08 | 0.09 | 1.13 | 37 | 58 | 4 | 0.40 | 0.57 | 0.89 |
| skirm v HCA | 2:skirm | 0.87 | 12 | 82 | 6 | 1.00 | 0.68 | 0.37 | 0.83 | 20 | 78 | 2 | 0.62 | 0.66 | 0.74 |
| skirm v HCA | 3:HCA | 0.76 | 19 | 73 | 7 | 0.52 | 0.30 | 0.10 | 0.94 | 24 | 73 | 3 | 0.51 | 0.36 | 0.53 |
| **HCA v HC** | **2:HCA** | **3.06** | **50** | 41 | 8 | 0.50 | 0.99 | 0.88 | **2.16** | **41** | 56 | 3 | 0.34 | 0.37 | 0.18 |
| **HCA v HC** | **3:HC** | 0.89 | 22 | 75 | 3 | 0.57 | **2.46** | **4.50** | −0.10 | 22 | 74 | 5 | 0.42 | 0.44 | 0.41 |

The engine's gross closure budget is already the tape's: `net` matches within
0.40 tiles on ten of twelve sides (the two misses are the `HCA v HC` pair,
0.90 and 0.99) and `close%` within 9 points on eleven of twelve (the miss is
`arb v skirm / 2:arb`, 11 vs 26, on a side whose net motion is *backward* in
both sources). The single quantity that does not match anywhere in this table is
`HCA v HC / 3:HC / d3` — **4.50 tape against 0.41 engine**, an 11× gap in the
median standoff of the losing side over the last third of the fight, produced
by an extra 0.9 tiles of enemy closure (3.06 vs 2.16) landing on a formation
that is 4.63 tiles deeper.

---

## 8. Target choice (context, not a hypothesis)

`excess` = how much further than the nearest living enemy the shot's actual
target was, at launch. `nearest%` = share of launches aimed at the nearest
enemy. `depth(near)` = `reach − dist(nearest enemy)` at the launch instant.

| fight | side | T n | T excess p50 | T excess p90 | T nearest% | T depth(near) p50 | E n | E excess p50 | E excess p90 | E nearest% | E depth(near) p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 154 | 0.21 | 1.03 | 31 | 1.08 | 3134 | 0.00 | 0.52 | 57 | 0.91 |
| arb v HC | 3:HC | 43 | 0.81 | 2.03 | 26 | 0.74 | 920 | 0.00 | 0.95 | 60 | 0.55 |
| arb v HCA | 2:arb | 262 | 0.00 | 1.04 | 52 | 1.16 | 5280 | 0.00 | 0.48 | 58 | 1.11 |
| arb v HCA | 3:HCA | 155 | 0.00 | 1.32 | 61 | 0.18 | 3000 | 0.00 | 0.05 | 84 | 0.32 |
| arb v skirm | 2:arb | 96 | 0.00 | 0.78 | 68 | 0.91 | 1600 | 0.00 | 0.23 | 70 | 0.50 |
| arb v skirm | 3:skirm | 131 | 0.38 | 1.41 | 40 | 0.61 | 2560 | 0.00 | 0.26 | 70 | 0.42 |
| skirm v HC | 2:skirm | 101 | 0.00 | 0.41 | 56 | 0.72 | 2144 | 0.00 | 0.48 | 72 | 0.95 |
| skirm v HC | 3:HC | 26 | 0.04 | 2.00 | 38 | 0.17 | 522 | 0.00 | 0.87 | 55 | 0.57 |
| skirm v HCA | 2:skirm | 160 | 0.00 | 0.40 | 51 | 0.75 | 2740 | 0.00 | 0.38 | 66 | 0.71 |
| skirm v HCA | 3:HCA | 59 | 0.00 | 0.81 | 54 | 0.39 | 1240 | 0.00 | 0.05 | 89 | 0.51 |
| HCA v HC | 2:HCA | 171 | 0.18 | 2.19 | 36 | 0.86 | 3204 | 0.00 | 0.23 | 77 | 0.40 |
| HCA v HC | 3:HC | 124 | 0.19 | 2.00 | 35 | 1.16 | 1811 | 0.00 | 0.33 | 56 | 0.42 |

The tape aims at the nearest enemy on 26–68% of launches (median ≈45), the
engine on 55–89% (median ≈68), and the tape's `excess p90` reaches 2.0–2.2
tiles where the engine's stays at 0.2–1.0. This matters for interpreting §1b:
part of the reason the tape's *launch* depth is shallower than its *standoff*
depth is that its units regularly shoot past a nearer enemy at one near their
reach limit. It is a separate finding from the depth question and is recorded
here so the two are not confused.

---

## 9. Verdicts

| # | mechanism | verdict | evidence | measured magnitude |
|---|---|---|---|---|
| **0** | **The premise itself** — "0.9–1.4 tiles inside reach" | **artefact** | §0a: the tape's recorded flight is inset 0.610–0.620 tiles at the launch end and 0.24–0.32 at the impact end, both purely radial (perp = 0.000 on all 12 sides), neither speed- nor radius-scaled | **0.85–0.93 tiles** of the claimed 0.94–1.96. True depth: tape 0.06–1.01, engine 0.29–0.98 |
| **1** | **Army depth** — rear ranks need reach, front is pushed in | **supports, but already modelled** | §3a: depth falls monotonically with rank on 11/12 sides in *both* sources | tape front−rear 0.03–4.21 (median ≈1.19); engine 0.07–1.40 (median ≈0.42). Army depth: tape 0.79–2.77 vs engine 1.08–2.56 in five fights; **4.26 vs 1.97** in `HCA v HC` |
| **2** | **Target-motion chase-in** | **refutes** | §4b: 86% of tape launches are at a target that has not moved in 1 s; fleeing targets are **10 shots in the corpus** and are the *shallowest* bucket | fleeing depth 0.14 vs still 0.42; the "closing" lift (+0.31) is matched by the engine (+0.10) |
| **3** | **Re-approach / decision latency** | **refutes** | §5a-b: first-shot-after-retarget within 0.30 of the second on 10/12 sides; pooled depth **falls** with launch gap (0.55 → 0.37 → 0.10) where overshoot predicts a rise; engine shows the identical shape | first-launch depth 0.37 vs steady-state 0.55 — the wrong sign |
| **4** | **Aim-at-body vs aim-at-edge** | **refutes** | §2: 21.3–92.1% of tape shots are fired from beyond `C`; the tape's observed maximum sits on `ENG` to within 0.01–0.06 tiles (7.62 vs 7.62 exactly on both HCA sides) | the predicate would give a constant 0.57–0.62-tile burial; the observed depth is 0.06–1.01 and varies with army geometry |
| **5** | **`HCA v HC` closure** | **the whole residual** | §6, §7, §3c | tape sep 5.26 / HCA army depth **6.25** / HC last-third standoff **4.50**; engine sep 7.57 / depth **1.62** / standoff **0.41** |

**What the data selects.** After §0's correction, five of the six ranged fights
have no depth residual worth a mechanism: the engine's median standoff is
within 0.20 tiles of the tape's (mean absolute over 12 sides), its p90 brackets
the tape's, and its late-fight army shape matches on separation to ≤0.64 tiles.
Of the four candidate mechanisms, three are refuted outright (H2, H3, H4) and
the fourth (H1) is a real gradient that the engine already reproduces at about
half amplitude.

The remaining residual is **one fight, one tail, one side**. In
`heavy_cav_archer__vs__hand_cannoneer` the tape's heavy cavalry archers close
for the entire 41 s (positive radial speed in 20 of 30 buckets, cumulative
+3.06 tiles, `close%` 50) and do so as a **strung-out 6.25-tile-deep column**
rather than a line, driving individual units to 1.45 tiles of the enemy while
the median archer stays a tile inside its own lip. The engine's archers close
+2.16 tiles in the first 5 s and then stop dead — `rad` = ±0.00 in eight
post-t=5 buckets, `dmin` pinned at 6.55 for 14 s and then *receding* — leaving
a 1.62-tile-deep line parked at separation 7.57. The measured consequence is
the hand cannoneer's standoff over the last third of the fight: **4.50 tiles
inside reach on tape, 0.41 in the engine**.

Two engine facts are consistent with the shape of that gap and are recorded as
observations only. `rangedShouldApproach()` latches `rangedClosed = true` the
first time a unit reaches `reach − 2·radius` and clears it only when the target
leaves reach entirely, so a unit that has once closed never approaches again
while its target survives at any distance inside reach. And the engine's
army-depth statistic (1.62–1.97 in this fight against the tape's 2.54–4.26)
says its formation stays a line, so no individual unit ever gets far enough
ahead to pull the rest in. Which of those two — the hysteresis latch or the
formation's rigidity — carries the residual is not separable from this
measurement; it would need an A/B.

---

## 10. Methodology notes and validation

- **Sides** come from `manifest.json`'s `owner` field, never tag word order.
- **Target identity.** Engine: the shot probe's recorded `true_target`, ground
  truth. Tape: the victim named by the damage pairing when the shot landed
  (1,147 of 1,482 launches — "certain"), else `ranged_fire_forensics`'s
  inferred aim target, which that module validates at 97.3% against tape hits
  and 99.3% against the engine's recorded truth. §0a, §0b and §2 use the
  certain subset only; `--certain-only` restricts every table to it.
- **Range is always centre-to-centre off the 10 Hz position stream**, on both
  sources, interpolated between samples. It is never `shot["dist"]` — see §0.
- **`reach`** is `ranged_fire_forensics.engine_reach`, i.e.
  `(attack_range·30 + MELEE_RANGE_BUFFER + r_self + r_target) / 30`, the same
  formula `BattleUnit.inRange()` applies, validated against the melee corpus to
  within 0.02 tiles of observed contact distance and independently confirmed
  here by the tape's own ranged ceiling (§2).
- **Settled** = the shooter has not moved (0.02-tile bar) in the 0.6 s before
  the launch, the same step bar `melee_walk_forensics` and
  `ranged_fire_forensics` use.
- **Engine pooling.** Shot-level distributions pool all 20 seeds. Timelines use
  the median-duration seed. `closure` averages the per-seed budget.
- **Occupancy tables** sample every 5th frame (0.5 s) — the statistic is a
  standoff distribution, not an event count, and the sweep is O(units ×
  enemies) per frame.
- **The engine dump is behaviour-neutral.** `ranged_shot_dump.mjs` wraps
  `BattleUnit.prototype.fireProjectile` read-only in `tools/`; it draws no rng,
  mutates no engine state and is not in `stateHash()`. Its `--verify-identity`
  mode A/Bs the same seed with the wrapper removed.
- **No engine file was modified for this round.** The only new file is
  `tools/simjs/ranged_depth_forensics.py`.
