# B1 — melee engagement forensics: what the non-swinging bodies are doing

**Date:** 2026-07-31 · **Base:** `716a522` (improved-simulation) · **Scope:** measurement only, no engine change.

Follow-up to `v2_melee_rebaseline.md` §6c, which named the melee defect as
"asymmetric under-engagement of the outnumbered side" and quantified it as a
concurrent-attacker ratio of 0.75x (paladin in `paladin__vs__elite_steppe`) and
0.73x (paladin in `champion__vs__paladin`) against 0.91x / 1.02x for the
superior side. This report takes that metric apart, tick by tick, and asks the
engine what the missing bodies were doing instead.

Everything below is measured. No design conclusions are drawn.

---

## 0. Headline

| Question | Answer |
|---|---|
| Is the outnumbered side systematically under-engaged? | **No — not once survivorship is divided out.** Pooled over 21 old-corpus asymmetric fights the outnumbered side's *swinging share of living bodies* is **0.98x** the tape's; the superior side's is 1.01x. |
| Then what was the 0.75x / 0.73x? | **Two different things wearing one number.** Concurrency = (living bodies) x (share of them swinging). In `paladin__vs__elite_steppe` v2 the share is **1.17x** — the engine's paladins engage *more* than the tape's — and the entire 0.80x concurrency gap is **0.74x living bodies**. In `champion__vs__paladin` v2 it splits about evenly (0.89x live, 0.91x share). |
| Is there a real engagement defect at all? | **Yes, and it is localised.** Two families collapse: `halberdier__vs__paladin` (21v7) share **0.31x** and `halberdier__vs__elite_elephant` (21v6) share **0.46x**. Both are the most extreme count ratios in the corpus and both hold their living-body count exactly (0.99x, 0.92x), so this is pure under-engagement. |
| What is the mechanism? | **Lock freezing.** 95% of the outnumbered side's wasted ticks are `lock_out_of_reach`; 96% of those have E14's target lock actively forbidding the stuck bar from releasing; **0.0%** are crowd-out and **0.2%** had a bump available. |
| Why does the bump not save it? | **E14 rule 2's trigger is the collision resolver's own floor.** `dist <= radius + radius + 1` is the exact separation `resolveCollisions` enforces as a *minimum*, so a pair it has just pushed apart is never "in contact" on the next tick. Measured: bump eligible on **0.2%** of frozen ticks; 900 bump fires against 21 080 stuck-bar trips. |
| Slot starvation? | **Ruled out.** `crowdedOut` is 0.000 of wasted ticks; the slots-full release fires on 1.0% of the outnumbered side's stuck trips. |
| Lane journeys? | **Minor.** 5.9% of re-acquisitions divert, costing 0.28 tiles and 0.55 s; `lane_journey` is 2.1% of the outnumbered side's wasted ticks. |

**The one-line version:** the engine's melee lock, plus a release valve that
cannot physically fire, freezes a surrounded unit on an out-of-reach victim
while hittable enemies stand ~1 px outside its bump threshold. It costs 6-10%
of a normally-outnumbered unit's life and **40%** of a heavily-outnumbered
one's.

---

## 1. Run configuration

```bash
# 40 fights: 21 old-corpus asymmetric melee (live positions) + 19 v2
# (paladin__vs__elite_steppe_r7..r18, champion__vs__paladin_r7..r13)
node tools/simjs/calib_runner.mjs --tags <40> --seeds 20 --workers 8 \
     --out-dir D:/AI/aoe2_golden/simruns_b1_clean
node tools/simjs/melee_engagement_probe.mjs --tags <40> --seeds 20 \
     --pos-seeds 5 --out-dir D:/AI/aoe2_golden/simruns_b1_probe \
     --verify D:/AI/aoe2_golden/simruns_b1_clean
PYTHONPATH=. python tools/simjs/melee_engagement_report.py \
     --probe-dir D:/AI/aoe2_golden/simruns_b1_probe
```

**No engine file was modified.** `melee_engagement_probe.mjs` installs four
prototype wrappers (`update`, `findTarget`, `meleeTargetLock`,
`meleeBumpRetarget`) from `tools/simjs/`, each calling straight through to the
original and only reading state afterwards. `--verify` re-checks that claim
against a plain `calib_runner.mjs` run of the same 800 (fight, seed) pairs:

> **determinism: 800/800 (fight, seed) damage streams byte-identical to the
> un-instrumented run.**

**Fight selection.** Both sides melee, count ratio >= 1.4x, not quarantined —
21 old-corpus fights (`champion__vs__paladin` + `_r2..r6`,
`halberdier__vs__paladin`, `halberdier__vs__elite_elephant`,
`paladin__vs__hussar`, and 12 more; `champion__vs__hussar` is 21v21 and is
excluded by the ratio). The six quarantined `paladin__vs__elite_steppe`
originals are dropped by `loadManifest`/`filters.py` and never reach the probe.
Sections 1, 3 and 4 need positions and therefore run on the **old corpus only**
— v2's position channel is frozen at spawn (`v2_melee_rebaseline.md` §1b).
Sections 2 and 5 are engine internals and cover both. Section 6 is damage-only
and is the v2 cross-check.

**Reach** is the engine's own `attackRange + radius + enemy.radius`
(`inRange()`), never an approximation. For two 0-range melee units it is
0.55-0.62 tiles.

---

## 2. Table 1 — concurrent-swinger timeline, and its decomposition

Distinct units of a side landing a hit inside a 2.5 s trailing window, sampled
every 0.25 s, by decile of **normalised** fight time (each stream normalised by
its own last damage event, not the truth card's inflated `duration_s`). Engine
= mean of 20 seeds. Deciles where the tape itself is below 0.5 swingers are
blanked — the armies are still closing and the ratio is all denominator.

### 1a. Outnumbered side, ratio engine/tape by decile

```
family                              n  d2    d3    d4    d5    d6    d7    d8    d9   d10   overall
champion__vs__elite_elephant        1 1.01  0.54  1.23  0.99  1.04  1.23  1.07  0.93  1.00   1.03  (4.80->4.92)
champion__vs__elite_steppe          1 3.54  1.63  1.22  1.00  0.94  0.83  0.89  1.13  1.69   1.22  (5.93->7.26)
champion__vs__halberdier            1 1.63  0.77  0.69  1.80  4.44  2.38  0.98  0.82  0.90   1.20  (5.69->6.80)
champion__vs__heavy_camel           1 2.17  1.13  1.86  1.71  1.58  1.13  1.00  0.75  1.01   1.34  (3.65->4.89)
champion__vs__paladin               6 2.51  0.84  1.04  0.93  0.89  0.91  0.98  1.02  1.35   1.05  (3.96->4.15)
elite_steppe__vs__elite_elephant    1 1.62  1.63  1.29  0.96  0.97  0.78  0.83  0.81  0.94   1.04  (5.69->5.91)
halberdier__vs__elite_elephant      1    -  2.00  0.64  0.45  0.25  0.25  0.33  0.70  0.16   0.42  (2.08->0.87)  <== COLLAPSE
halberdier__vs__elite_steppe        1    -  3.73  2.13  1.49  1.04  1.05  0.83  0.87  0.80   1.31  (3.82->5.02)
halberdier__vs__heavy_camel         1    -  1.00  0.52  0.70  0.89  0.97  0.71  0.76  1.02   0.84  (2.35->1.97)
halberdier__vs__hussar              1    -  1.00  1.19  1.29  1.71  1.34  1.40  1.14  0.56   1.32  (2.83->3.73)
halberdier__vs__paladin             1    -  1.00  0.47  0.22  0.25  0.21  0.11  0.26  0.50   0.31  (2.58->0.81)  <== COLLAPSE
heavy_camel__vs__elite_elephant     1 1.09  1.08  1.01  0.59  0.84  0.87  0.89  1.10  1.32   0.94  (5.91->5.58)
hussar__vs__elite_elephant          1 1.18  1.11  1.06  1.01  0.85  0.93  0.95  0.74  0.70   0.94  (5.55->5.21)
hussar__vs__elite_steppe            1 1.65  1.19  1.07  0.86  0.98  1.24  1.01  1.75  2.24   1.25  (6.21->7.74)
hussar__vs__heavy_camel             1 4.25  1.41  1.12  0.71  0.58  0.80  1.01  1.08  1.03   0.97  (5.92->5.73)
paladin__vs__hussar                 1 1.57  4.89  0.73  0.63  0.55  1.47  1.60  2.33  1.38   1.18  (3.69->4.36)
ALL                                21                                                         1.06  (4.31->4.56)
```

Superior side, same treatment: **0.95x** overall (6.00 -> 5.72).

**Where the sag is.** In the two collapse families it is **mid-fight and it
does not recover**: `halberdier__vs__paladin` runs 1.00 / 0.47 / 0.22 / 0.25 /
0.21 / 0.11 across d3-d8, i.e. the outnumbered paladins keep up for the first
third and then stop. By the brief's own decoder that is a lock/retarget
signature, not an acquisition or approach one. Everywhere else the d2-d3 cells
run 1.5-4x (the engine reaches contact *earlier* than the tape) and the
mid-fight cells sit near 1.0.

### 1b. Concurrency decomposed — living bodies x share of them swinging

Concurrency is a product, and the two factors want opposite fixes. Both come
out of the damage stream alone (deaths from `kill` events), so this also works
on v2.

```
family                             role conc_t conc_e  cRat live_t live_e  lRat  shr_t  shr_e  sRat
champion__vs__elite_elephant        out   4.80   4.92  1.03   7.49   7.54  1.01  0.653  0.665  1.02
champion__vs__elite_steppe          out   5.93   7.26  1.22   8.38   7.94  0.95  0.892  1.048  1.18
champion__vs__halberdier            out   5.69   6.80  1.20  14.78  14.78  1.00  0.390  0.463  1.19
champion__vs__heavy_camel           out   3.65   4.89  1.34   8.25   8.28  1.00  0.668  0.687  1.03
champion__vs__paladin               out   3.96   4.15  1.05   6.45   6.44  1.00  0.792  0.781  0.99
elite_steppe__vs__elite_elephant    out   5.69   5.91  1.04  11.87  10.68  0.90  0.494  0.574  1.16
halberdier__vs__elite_elephant      out   2.08   0.87  0.42   4.83   4.44  0.92  0.561  0.256  0.46
halberdier__vs__elite_steppe        out   3.82   5.02  1.31   6.59   5.94  0.90  0.825  1.116  1.35
halberdier__vs__heavy_camel         out   2.35   1.97  0.84   5.82   5.59  0.96  0.574  0.561  0.98
halberdier__vs__hussar              out   2.83   3.73  1.32  10.48   9.64  0.92  0.414  0.638  1.54
halberdier__vs__paladin             out   2.58   0.81  0.31   5.17   5.11  0.99  0.706  0.217  0.31
heavy_camel__vs__elite_elephant     out   5.91   5.58  0.94   9.54   9.44  0.99  0.822  0.673  0.82
hussar__vs__elite_elephant          out   5.55   5.21  0.94   8.00   8.00  1.00  0.693  0.651  0.94
hussar__vs__elite_steppe            out   6.21   7.74  1.25   7.87   8.64  1.10  0.916  0.915  1.00
hussar__vs__heavy_camel             out   5.92   5.73  0.97  10.26  10.93  1.07  0.587  0.525  0.89
paladin__vs__hussar                 out   3.69   4.36  1.18   5.98   6.71  1.12  0.743  0.690  0.93
ALL out                             out   4.31   4.56  1.06   7.81   7.73  0.99  0.700  0.684  0.98
ALL sup                             sup   6.00   5.72  0.95  16.14  15.21  0.94  0.490  0.496  1.01
```

**Verdict (table 1).** Over the old corpus the engine's living-body counts track
the tape almost exactly (0.99x outnumbered, 0.94x superior), so `share` is the
honest engagement metric and it is **0.98x / 1.01x** — no corpus-wide
under-engagement of the outnumbered side. The defect is **two families**, both
at the extreme end of the count ratio (3.0x and 3.5x), where the outnumbered
side keeps its bodies alive on schedule and swings a third to a half as often.

---

## 3. Table 2 — non-swinging anatomy (engine internals)

Every living melee unit-tick, after that unit's own `update()`, split three
ways. **ENGAGED** = `state` is `attacking`/`committed` (inside the swing loop,
windup or reload included). **WASTED** = at least one living enemy is inside
this unit's own reach and it is *not* engaged — a fight was available and it
declined. **OUT** = nothing at all is inside its reach.

```
                                               OUTNUMBERED      SUPERIOR
unit-ticks (alive)                                 6 966 020    12 553 280
  engaged (share of alive)                           0.561         0.374
  WASTED  (share of alive)                           0.075         0.068
  out of contact (share of alive)                    0.365         0.557
```

### 2a. What the WASTED ticks are

```
WASTED-tick breakdown (share of wasted)        OUTNUMBERED      SUPERIOR
  lock_out_of_reach                                  0.950         0.872
  lane_journey                                       0.021         0.103
  no_target                                          0.000         0.000
  no_target_blacklist                                0.000         0.000
  other (1-tick artifact, see below)                 0.029         0.025

sub-flags (share of wasted ticks)              OUTNUMBERED      SUPERIOR
  lock protected (E14 forbids blacklisting)          0.960         0.925
  bump WAS eligible (rule 2 should have fired)       0.002         0.004
  crowded out (every in-reach foe already full)      0.000         0.005
  PRIME SUSPECT (locked, not crowded, no bump)       0.958         0.917

episode durations, seconds (med / p90 / max)   OUTNUMBERED      SUPERIOR
  lock_out_of_reach                          0.09/1.38/35.60 0.06/1.38/9.18
  PRIME SUSPECT                              0.10/1.39/35.60 0.09/1.49/9.18
  episode count                                        12 960        18 120

geometry of the wasted tick, tiles             OUTNUMBERED      SUPERIOR
  locked victim is this far PAST reach (med)         0.370         0.456
  nearest hittable foe, gap past bump floor          0.056         0.076
```

`other` is a one-tick artifact of classifying *after* `update()`: a unit whose
own approach step carried it into reach is still `state=moving` on that tick
and swings on the next. Its episode median is **0.0167 s = exactly one tick**,
which is the check on that reading. Nothing else in the taxonomy is unexplained
— `no_target` and `no_target_blacklist` are both zero, so blacklisting plays no
part at all.

**The prime suspect is confirmed and it is essentially the whole bucket.**
95.8% of the outnumbered side's wasted ticks are: E14's lock held on a living
victim ~0.37 tiles beyond reach, at least one enemy hittable right now, no
crowding, and no bump available. Median episode 0.10 s, p90 1.39 s, **max
35.6 s** — a unit that stood in a scrum for over half a minute without
swinging.

### 2b. Why the bump never fires — the knife-edge

`meleeBumpRetarget` triggers on `dist <= this.radius + enemy.radius + 1`.
`Simulation.resolveCollisions` uses `minDist = a.radius + b.radius + 1` for
every cross-team pair and pushes them apart until the distance *reaches* it.
The bump's trigger and the resolver's floor are the same expression, and the
resolver runs after every update — so on the following tick the pair is at or
just above the floor and the `<=` test fails.

Measured, outnumbered side: the nearest hittable enemy sits a median **0.056
tiles (1.7 px) past the bump floor**; in the collapse families it is 0.034
tiles (**1.0 px**). Bump eligible on **0.2%** of frozen ticks. Over the whole
run the bump fired 900 times against 21 080 stuck-bar trips.

### 2c. What the OUT-OF-CONTACT ticks are

```
OUT-OF-CONTACT breakdown (share of out)        OUTNUMBERED      SUPERIOR
  approach_nearest                                   0.623         0.651
  approach_nonnearest                                0.369         0.345
  approach_lane                                      0.008         0.003
  approach_no_target                                 0.000         0.001
  STALLED (nearest foe not getting closer)           0.326         0.339
  distance to nearest foe, tiles (median)             1.20          1.21
```

Out-of-contact is the larger bucket but it is **not** where the tape/engine gap
lives: the corpus-wide `share` ratio is 0.98x, so whatever the engine does
during these ticks it reproduces the tape's overall swing rate. It is reported
because a third of it is *stalled* (walking without closing) at a median 1.20
tiles from the nearest enemy — units queued one body-length behind the contact
line, which is the population the lock freeze then acts on.

### 2d. Per family, outnumbered side — where the freeze concentrates

`prime/alive` is the fraction of a living unit's entire existence spent in the
prime-suspect state. `ovrRch` = median tiles the locked victim is past reach.
`bmpGap` = median tiles the nearest hittable enemy sits past the bump floor.

```
family                              eng   wast    out  lockOOR   prime  prime/  crowd  stall  epiMed  epiP90  ovrRch  bmpGap
                                                        /wast   /wast   alive
champion__vs__elite_elephant      0.580  0.102  0.318    0.862   0.952   0.097  0.000  0.287    0.05    1.45   0.470   0.045
champion__vs__elite_steppe        0.837  0.005  0.158    0.869   0.000   0.000  0.000  0.087       -       -   0.221   0.961
champion__vs__halberdier          0.376  0.060  0.564    0.758   0.853   0.051  0.000  0.324    0.14    1.71   0.291   0.046
champion__vs__heavy_camel         0.544  0.093  0.363    0.974   0.973   0.090  0.000  0.315    0.21    2.46   0.454   0.073
champion__vs__paladin             0.593  0.066  0.342    0.967   0.989   0.065  0.000  0.352    0.10    1.15   0.268   0.041
elite_steppe__vs__elite_elephant  0.499  0.025  0.476    0.923   0.945   0.024  0.000  0.313    0.40    2.77   0.067   0.038
halberdier__vs__elite_elephant    0.174  0.334  0.492    0.999   0.998   0.333  0.000  0.167    0.05    1.03   0.557   0.041  <==
halberdier__vs__elite_steppe      0.705  0.011  0.285    0.043   0.848   0.009  0.000  0.026    0.07    0.45   1.226   0.974
halberdier__vs__heavy_camel       0.287  0.187  0.526    0.998   0.994   0.186  0.000  0.281    0.09    1.50   0.435   0.043
halberdier__vs__hussar            0.282  0.144  0.573    0.996   0.994   0.143  0.000  0.304    0.03    1.55   0.561   0.054
halberdier__vs__paladin           0.128  0.400  0.472    0.999   0.996   0.398  0.000  0.226    0.56    1.17   0.468   0.034  <==
heavy_camel__vs__elite_elephant   0.524  0.072  0.404    0.968   0.967   0.070  0.000  0.364    0.05    1.20   0.185   0.048
hussar__vs__elite_elephant        0.572  0.068  0.361    0.964   0.962   0.065  0.000  0.376    0.05    3.03   0.818   0.037
hussar__vs__elite_steppe          0.919  0.011  0.070    0.910   0.000   0.000  0.000  0.076       -       -   0.364   0.729
hussar__vs__heavy_camel           0.498  0.019  0.482    0.741   0.733   0.014  0.000  0.373    0.10    0.73   1.105   0.041
paladin__vs__hussar               0.603  0.145  0.252    0.964   0.981   0.142  0.000  0.373    0.05    0.72   0.242   0.037
```

Two readings, both load-bearing for a fix spec:

1. **`prime/alive` tracks the collapse exactly.** The two families table 1b
   flags (share 0.31x, 0.46x) are the two with the highest `prime/alive`
   (0.398, 0.333) — 4-6x the corpus norm of 0.065-0.10. Nothing else
   distinguishes them: `crowd` is 0.000 everywhere, `stall` is *lower* there
   than average, and `lockOOR/wast` is ~1.00 there versus 0.86-0.97 elsewhere.
2. **`halberdier` as the superior side is the common factor**, and it is not
   just the count: at the *same* outnumbered unit and count, `elite_elephant`
   8-v-21 costs 0.097 `prime/alive` under champions and 0.065 under hussars,
   while `elite_elephant` 6-v-21 under halberdiers costs 0.333;
   `heavy_camel` 11-v-21 costs 0.090 under champions, 8-v-21 costs 0.186 under
   halberdiers. The halberdier is the only unit in the corpus with a 3.0 s
   reload (everything else is 1.90-2.00 s) and it is 0-range infantry
   (radius 6 px) against 7.5 px mounted bodies. **This report does not isolate
   which of those properties drives it** — that would need a per-property A/B,
   which is an engine change and out of scope here.

The two families with `prime/alive` = 0.000 (`champion__vs__elite_steppe`,
`hussar__vs__elite_steppe`) are the range-1.0 Steppe Lancer sides: a 1.23-tile
reach means the lock is almost never out of reach while something else is in
it, and their `bmpGap` of ~0.96-0.97 tiles confirms the geometry. They are the
natural control, and they are also the two highest engaged shares in the table
(0.837, 0.919).

---

## 4. Table 3 — tape counterpart: effective retarget latency

Same inference on both streams, no engine internals used: a unit's **lock** at
time *t* is the victim of its most recent landed hit; an **opportunity** begins
on the first 10 Hz frame where that lock is alive but out of reach while some
other living enemy is in reach; the **latency** is the time to that unit's next
landed hit on anybody. Units that never hit again are censored, not zeroed.
Engine = seeds 1..5.

```
family / OUTNUMBERED side                n_t  med_t  p90_t    n_e  med_e  p90_e  ratio
champion__vs__elite_elephant              25   1.51   3.17     45   1.98   2.00   1.31
champion__vs__halberdier                  38   2.59   8.42     40   1.70   2.22   0.66
elite_steppe__vs__elite_elephant           8   1.21   7.15     25   1.98   2.00   1.63
halberdier__vs__elite_elephant             2   1.22   1.82      5   2.00   2.00   1.64
heavy_camel__vs__elite_elephant           46   2.01   6.97     75   1.95   2.02   0.97
hussar__vs__elite_elephant                38   1.42   2.00     70   1.93   2.02   1.36
paladin__vs__hussar                       26   1.94  10.41      5   1.90   1.90   0.98
ALL OUTNUMBERED                          393   1.66   4.73    265   1.93   2.02   1.17
    episodes / censored                  420     27            270      5
ALL SUPERIOR                             466   1.95   8.01    145   0.95   3.84   0.49
    episodes / censored                  508     42            155     10
```

**Verdict (table 3).** Medians are close (engine 1.17x for the outnumbered
side) but the *shapes* differ sharply. The engine's distribution is pinned at
one reload — p90 2.02 s against the tape's 4.73 s — while the tape has a long
tail it never reaches. Read together with table 2, that is consistent: when the
engine's unit does escape the state it escapes on schedule; the damage is done
by how *often* it enters it, not by how long an individual escape takes. The
median episode is 0.10 s, which is why the median latency looks healthy.

**Caveat, stated plainly:** the two collapse families are the thinnest rows
here (`halberdier__vs__elite_elephant` n_t = 2, `halberdier__vs__paladin`
absent from the outnumbered table entirely) because the inference needs a unit
to have landed a hit first, and in those fights the outnumbered side barely
does. **Table 3 does not independently corroborate the collapse.** The engine
side of it is also 5 seeds against 1 recording; treat the per-family rows as
indicative and the pooled row as the result.

### Attackers per victim on the outnumbered side's own bodies

`geom` = living enemies inside *their* reach of that body, at 10 Hz.
`dmg` = distinct attackers landing a hit inside a trailing reload.

```
family                                  geom_t  geom_e  gmax_t  gmax_e  dmg_t  dmg_e  dmax_t  dmax_e
champion__vs__elite_elephant              0.51    1.17       5       4   2.45   2.38       6       4
champion__vs__elite_steppe                0.44    0.78       3       4   2.10   2.23       5       4
champion__vs__halberdier                  0.40    0.56       4       3   1.66   1.68       3       3
champion__vs__heavy_camel                 0.94    1.18       6       5   2.50   2.02       6       5
champion__vs__paladin                     1.06    1.12       5       4   2.63   1.81       6       4
elite_steppe__vs__elite_elephant          2.18    4.01      13      13   3.54   4.31      11      13
halberdier__vs__elite_elephant            0.68    1.18       5       5   2.33   2.40       4       5
halberdier__vs__elite_steppe              0.50    0.60       4       4   1.81   1.81       3       3
halberdier__vs__heavy_camel               0.83    1.17       4       5   2.20   2.33       5       4
halberdier__vs__hussar                    0.50    0.74       5       6   1.64   1.64       3       3
halberdier__vs__paladin                   0.76    1.32       4       5   2.14   2.60       5       5
heavy_camel__vs__elite_elephant           0.86    0.87       5       4   2.19   1.82       5       3
hussar__vs__elite_elephant                0.62    0.95       4       4   2.54   2.23       4       4
hussar__vs__elite_steppe                  0.68    0.64       4       4   2.13   1.90       8       4
hussar__vs__heavy_camel                   0.33    0.68       4       4   2.48   1.37       5       3
paladin__vs__hussar                       0.85    1.28       4       4   2.16   2.09       5       4
```

**Over-crowding of the outnumbered side's victims does not starve its
attackers.** The engine surrounds those bodies *more* than the tape does
(pooled geometric mean 1.23 vs 0.89), and the damage-window count is slightly
*lower* (2.21 vs 2.48) — the engine has more enemies standing in reach of each
outnumbered body while fewer of them are actually landing hits on it. That is
the same lock freeze seen from the victim's side, and it is the opposite of
crowd-out.

---

## 5. Table 4 — contact-slot audit

```
                                               OUTNUMBERED      SUPERIOR
stuck bar reached 0.8 s on a melee unit              21 080        40 320
  ... E14 lock HELD (bar re-armed, no release)       20 860        38 180
  ... slots-full RELEASE fired                          220         2 140
bump-retarget fired                                     900         1 480
release as a share of stuck trips                     0.010         0.053
```

Engine attackers-in-reach histogram on the outnumbered side's bodies (the exact
target-aware count `meleeTargetLock` caps at 4):

```
  0 attackers  704 140  0.606      4 attackers   14 140  0.012   <- the cap
  1 attackers  237 580  0.204      5 attackers    4 840  0.004
  2 attackers  153 900  0.132      6 attackers    1 260  0.001
  3 attackers   45 800  0.039      8-12 attackers 1 140  0.001
```

```
pooled, outnumbered side                    tape    engine
geometric mean attackers/body               0.89      1.23
geometric p90                               2.00      3.00
geometric MAX simultaneous                    13        13
damage-window mean                          2.48      2.21
damage-window p90                           4.00      4.00
damage-window MAX                             11        13
```

**Verdict (table 4).** E14's slots-full release is **effectively dead**: it
fires on 1.0% of the outnumbered side's stuck-bar trips (220 of 21 080) and
5.3% of the superior side's. In 98.9% of samples the victim has fewer than 4
attackers in reach, so the cap has nothing to release.

On whether 4 is the right number for *these* fights: the tape's observed max
simultaneous attackers on an outnumbered body is **13** for the range-1.0
Steppe Lancer and **5-6** for every 0-range melee family
(`champion__vs__heavy_camel` 6, `champion__vs__elite_elephant` 5,
`champion__vs__paladin` 5, `halberdier__vs__hussar` 5). So **4 binds earlier
than the tape's asymmetric-fight maximum** — the constant was derived from
balanced fights and those show a lower ceiling. But since `crowdedOut` is
0.000, raising it would change nothing measurable; the cap is not what is
holding the units still.

---

## 6. Table 5 — lane-rule involvement

```
                                               OUTNUMBERED      SUPERIOR
target acquisitions                                  19 800        28 880
  of which RE-acquisitions                           15 560        20 080
  of which LANE-DIVERTED to a farther enemy               920         1 000
divert share of re-acquisitions                       0.059         0.050
extra distance to the diverted pick (tiles, med)       0.28          0.21
journey after a DIVERT, s (median)                     0.55          0.56
journey after a PLAIN pick, s (median)                 0.07          0.55
lane_journey share of WASTED ticks                    0.021         0.103
approach_lane share of OUT ticks                      0.008         0.003
```

**Verdict (table 5).** The lane rule diverts **5.9%** of the outnumbered side's
re-acquisitions, by a median 0.28 tiles, costing a 0.55 s walk against 0.07 s
for a plain pick. Those journeys account for **2.1%** of its wasted ticks and
0.8% of its out-of-contact ticks. It is a real cost and it is small, and it is
*larger* on the superior side (10.3% of wasted ticks) which is not the side
with the defect. This measurement neither indicts nor exonerates the rule on
its own merits — `v2_melee_rebaseline.md` §6b already showed switching it off
makes the corpus worse — it only establishes that lane journeys are **not** the
mechanism behind the outnumbered side's under-engagement.

---

## 7. Table 6 — v2 outcome cross-check

The two families the fix has to move, on the current engine, 20 seeds, from
each v2 recording's own first-frame spawns. Damage streams only (v2 positions
are dead), same concurrency metric as §2.

```
family                     side          army role conc_t conc_e  cRat live_t live_e  shr_t  shr_e  sRat
champion__vs__paladin      champion        21  sup   7.76   8.78  1.13  13.94  16.70  0.677  0.532  0.79
champion__vs__paladin      paladin          9  out   4.91   3.92  0.80   6.33   5.62  0.914  0.834  0.91
paladin__vs__elite_steppe  elite_steppe    21  sup  10.48  10.02  0.96  12.56  10.99  0.958  0.971  1.01
paladin__vs__elite_steppe  paladin         15  out   6.14   4.90  0.80   9.73   7.23  0.734  0.861  1.17
```

The 0.75x/0.73x signature reproduces on the current engine as **0.80x on both
outnumbered sides**, against 0.96x/1.13x for the superior sides. But the
decomposition splits the two families apart:

* **`paladin__vs__elite_steppe`** — the engine's living paladins swing **1.17x**
  as often as the tape's. There is **no engagement deficit on this side at
  all.** The whole 0.80x is survivorship: mean living paladins 7.23 vs 9.73
  (**0.74x**). The paladins are dying, and dying is what suppresses the swing
  count — not the other way round. This contradicts the reading in
  `v2_melee_rebaseline.md` §6c that "the missing paladin swings ARE the outcome
  error"; measured with survivorship divided out, the missing swings are a
  *consequence* of the outcome error, not its cause.
* **`champion__vs__paladin`** — splits roughly evenly: living 0.89x, share
  0.91x. Note the superior side here is the one with the worse share ratio
  (champion 0.79x) while carrying 1.20x the living bodies (16.70 vs 13.94,
  itself the +24.6 pt HP error). Both sides under-engage per living body; the
  champions more.

### 7b. Same matchup, two corpora — did the engine move, or did the tape?

`champion__vs__paladin` (21v9) is the only asymmetric melee matchup recorded in
both corpora. The engine fights each from that recording's own first-frame
spawns, so this isolates the recorder change.

```
                                             OLD corpus      V2 corpus
recordings                                            6              7
spawn: centroid separation (tiles)                 9.58           4.15
spawn: nearest cross-army pair (tiles)             5.00           2.00
TAPE paladin concurrency                           3.96           4.91
ENGINE paladin concurrency                         4.15           3.92
  ratio engine/tape                                1.05           0.80
TAPE mean living paladins                          6.45           6.33
ENGINE mean living paladins                        6.44           5.62
TAPE swinging share of living                     0.792          0.914
ENGINE swinging share of living                   0.781          0.834
  ratio engine/tape                                0.99           0.91
TAPE wipe / ENGINE wipe (s)                   39.0/42.8      34.6/29.4
engine paladin: engaged share                     0.593          0.642
engine paladin: WASTED share                      0.066          0.058
engine paladin: out-of-contact share              0.342          0.300
engine paladin: prime-suspect / wasted            0.989          0.986
engine paladin: stalled / out                     0.352          0.412
```

**Halving the starting separation raises the tape's paladin engagement by 15%
(share 0.792 -> 0.914) and the engine's by 7% (0.781 -> 0.834).** The engine
moves in the right direction and only half as far, which is what turns a 0.99x
match on the old spawns into a 0.91x miss on the v2 ones. The engine's internal
mix barely changes (prime-suspect share of wasted 0.989 -> 0.986), so this is
the same mechanism operating at a different density, not a new one.

---

## 8. What the mechanism is

Ranked by the evidence:

1. **Lock freezing — the mechanism.** 95.8% of the outnumbered side's wasted
   ticks are E14's lock held on a victim a median 0.37 tiles beyond reach while
   something hittable stands adjacent, with the stuck bar forbidden from
   releasing and no bump available. Median episode 0.10 s, p90 1.39 s, max
   35.6 s. It costs 6.5-10% of a normally-outnumbered unit's life and **39.8%**
   of a `halberdier__vs__paladin` paladin's.
2. **The release valve is structurally dead — the reason the freeze persists.**
   `meleeBumpRetarget`'s trigger `dist <= r+r+1` is byte-for-byte the floor
   `resolveCollisions` enforces as a minimum on the same pair, so the enemy the
   unit is pressed against is a median 1.0-1.7 px too far away to count as
   "bumped". Eligible on 0.2% of frozen ticks.
3. **Slot starvation — ruled out.** `crowdedOut` 0.000; slots-full release
   fires on 1.0% of stuck trips; 98.9% of victims have fewer than 4 attackers
   in reach. `MELEE_CONTACT_SLOTS = 4` does sit below these fights' observed
   tape maximum (5-6 for 0-range melee, 13 for the 1.0-range lancer), but it
   never binds.
4. **Lane journeys — minor.** 5.9% of re-acquisitions, 2.1% of wasted ticks,
   0.55 s each. Not the mechanism.
5. **Crowd-out of the outnumbered side's victims — ruled out, and inverted.**
   The engine puts *more* enemies in reach of each outnumbered body than the
   tape (1.23 vs 0.89) while landing *fewer* hits on it (2.21 vs 2.48).
6. **Survivorship — a separate, co-resident error.** In
   `paladin__vs__elite_steppe` v2 the entire concurrency gap is 0.74x living
   bodies with a 1.17x swinging share. A fix aimed only at engagement will not
   move that family, and a concurrency-only KPI cannot tell the two apart.

---

## 9. Fix targets

Concurrency ratios to restore. **Use `share` (swinging fraction of living
bodies), not raw concurrency** — raw concurrency is contaminated by the outcome
it is supposed to predict.

| Target | current | goal | note |
|---|---|---|---|
| old corpus, outnumbered, pooled `share` | **0.98x** | hold at 1.00x | already correct — a fix must not break this |
| old corpus, superior, pooled `share` | **1.01x** | hold | same |
| `halberdier__vs__paladin` outnumbered `share` | **0.31x** | 1.00x (0.217 -> 0.706) | the largest single miss on the board |
| `halberdier__vs__elite_elephant` outnumbered `share` | **0.46x** | 1.00x (0.256 -> 0.561) | second largest |
| `halberdier__vs__heavy_camel` / `__hussar` | 0.98x / 1.54x | hold | same superior unit, no miss — the fix must not be a halberdier special case |
| v2 `champion__vs__paladin` paladin `share` | **0.91x** | 1.00x (0.834 -> 0.914) | gates the +24.6 pt HP error |
| v2 `champion__vs__paladin` champion `share` | **0.79x** | 1.00x (0.532 -> 0.677) | the superior side is the worse miss here |
| v2 `paladin__vs__elite_steppe` paladin `share` | **1.17x** | do not raise | already above tape; this family's error is survivorship (live 0.74x) |

Internal budgets the fix has to move (outnumbered side, pooled):

| Probe metric | current | direction |
|---|---|---|
| `prime/alive` in the two collapse families | 0.398 / 0.333 | -> corpus norm 0.065-0.10 |
| `prime/alive` corpus-wide | 0.065-0.10 | must not rise |
| bump eligible on frozen ticks | 0.002 | the valve has to become reachable |
| slots-full release / stuck trips | 0.010 | currently inert |
| prime episode p90 | 1.39 s | -> under one reload (~1.9 s is already the bar; the p90 is not the problem, the entry rate is) |

---

## 10. What this run cannot tell you

* **Which halberdier property drives the collapse.** The 3.0 s reload, the
  0-range 6 px infantry body and the 21-v-6/7 count all covary. Separating them
  needs an engine A/B, which is out of scope for a measurement pass.
* **Whether fixing the freeze fixes the outcome.** Every number here is
  correlational. `paladin__vs__elite_steppe` v2 in particular has *no*
  engagement deficit to fix.
* **Anything positional about v2.** Position channel frozen at spawn; §§2, 5, 7
  are the only v2 measurements here and they are damage-stream or
  engine-internal.
* **Whether the old corpus's asymmetric families are themselves well captured.**
  Fourteen of the 21 are n = 1. The two collapse families are n = 1 each; their
  engine side is 20 seeds, their tape side is one recording.
* **The superior side's v2 `champion__vs__paladin` 0.79x share.** It is the
  worst single share ratio in §7 and this report does not explain it — the
  old-corpus counterpart is 0.97x.

---

## Artifacts

| what | where |
|---|---|
| instrumented probe (new) | `tools/simjs/melee_engagement_probe.mjs` |
| report generator (new) | `tools/simjs/melee_engagement_report.py` |
| clean control runs (800 files) | `D:/AI/aoe2_golden/simruns_b1_clean` |
| probe runs + 10 Hz positions (800 + 200 files) | `D:/AI/aoe2_golden/simruns_b1_probe` |
| machine-readable summary | `D:/AI/aoe2_golden/b1_report.json` |
| full console output | `D:/AI/aoe2_golden/b1_report.txt` |
