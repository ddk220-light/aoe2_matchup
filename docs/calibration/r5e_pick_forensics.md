# R5e forensics — is the tape's victim choice POSITIONAL, and is that the same thing as the ride-in?

Measurement only. No file under `apps/website/static/js/engine/` was changed or
imported. Every number below is produced by `tools/simjs/r5e_pick_forensics.py`,
which computes each statistic once and feeds it either a recording's three
streams or an engine run's shot dump, so a tape number and an engine number are
the same statistic and never two implementations that happen to be named alike.
It reuses `ranged_fire_forensics`'s `Fight` (10 Hz positions, wipe-time cut,
interpolated positions), its shot→damage pairing and its aim inference, and
`r5c_targeting_forensics`'s `reach_tiles`, `living_enemies` and `hp_at`, so it
inherits their validation.

```
node tools/simjs/ranged_shot_dump.mjs --tags <the six> --seeds 20 \
     --out-dir D:/AI/aoe2_golden/shots_r5e
PYTHONPATH=. python tools/simjs/r5e_pick_forensics.py \
     --sim-runs-dir D:/AI/aoe2_golden/shots_r5e --seeds 20 --section all
PYTHONPATH=. python tools/simjs/r5e_pick_forensics.py ... --pool-reach inrange
```

Engine side: `improved-simulation` HEAD **0adebf3** — R5b all four on, R5d **T1
+ T2 ON**, T3 off, R5d-1 P1/P2 off — `tapebox` arena, 20 seeds per fight,
27,067 launches. Tape side: the six ranged recordings, 1,379 launches with a
resolvable victim inside the shooter's own reach. `T` = tape, `E` = engine.
Sides are `<owner>:<unit>` from the manifest's own `owner` field.

## The three answers, one line each

- **Positional selection is REFUTED.** The tape's chosen victim sits at
  percentile **0.23** of its reachable pool on DISTANCE and **0.48 / 0.49 /
  0.46** on across-the-line offset / straight-ahead offset / aim swing — 0.5 is
  the random null. All three positional metrics carry no information at all,
  on all twelve sides, in both pool definitions.
- **Cause and effect: DEPTH DRIVES ASSIGNMENT, not the reverse — and neither
  drives the other much.** In `HCA v HC` the tape's rider-level correlation
  between mean assignment depth and maximum advance is **−0.12**, and the lag
  sweep is negative at every lag and gets *more* negative as the lag grows
  (−0.07 at 0 s → −0.38 at +8 s). What the ride-in IS correlated with is
  silence: the tape's archers close on **52–62%** of the unit-steps in which
  they have not fired for more than two reload cycles and on **2.0%** of the
  steps in which they are trading on cooldown.
- **No rule matches both.** `nearest of 3 across` reproduces the tape's excess
  distribution almost exactly (Δ near% +2.5, Δ ex p90 −0.08, Δ far% −0.5) at
  39.4% per-pick accuracy; `persist→nearest` is the accuracy leader (**55.9%**,
  above both plain nearest 53.4% and shipped-T1 53.0%) but leaves the
  distribution 25 points too concentrated on the nearest. The plannedDamage
  over-count is real and worth **roughly half the all-covered fallback on the
  three hand-cannoneer sides and nothing at all on the other nine**.

---

## 0. What is measured, and against what null

**The pool.** A shot's candidate set is the living enemies inside
`reach_tiles` = `canReach()` = `attack_range + both physics radii`, because
that is the predicate `selectShotTarget()` itself uses to decide which
alternatives exist. A shot whose own victim falls outside the pool cannot be
scored against it and is dropped; the drop rate is reported (`drop%`, 0.6–24.0
on tape, 7.0–40.3 on the engine) rather than absorbed, and **every table was
re-run with the pool widened to `inRange()`'s reach** (`--pool-reach inrange`),
which is the tape's own measured firing ceiling (R5c §2). That cuts the drop
rate to 0.0–20.0 and moves no conclusion: tape `dist.pct` 0.078–0.395 against
0.079–0.370, tape `perp.pct` 0.385–0.631 against 0.359–0.617. The canReach
tables are the ones printed below.

**The metrics.** For each candidate, relative to the shooter:

| | |
|---|---|
| `d` | centre-to-centre distance |
| `perp` | \|offset across the ARMY threat axis\| — 0 means "directly across the line from me" |
| `perpS` | the same against the shooter → enemy-centroid axis (the other reading of "straight ahead") |
| `ang` | \|angle\| to the shooter's facing, where facing is the direction of that shooter's PREVIOUS launch |

The engine has no facing angle — only a sprite-side boolean — so the
previous-launch direction is the only facing definition available identically
on both sources. It is a *swing* angle, and a repeat pick scores 0 by
construction, so the angular column is computed only over shots that CHANGED
victim.

**The null.** `pctile` is where the chosen victim sits in its pool on that
metric, 0 = the minimum, mid-rank on ties. **A shooter picking uniformly at
random scores 0.500 on every column by construction**, and a strict
nearest-first rule scores `dist.pct` = 0.000 / `near%` = 100. `min%_rand` is
the matching null for the `min%` columns — the mean of 1/k over the same shots,
which is not the same number in two fights with different pool sizes.

**Two additive, read-only probe fields** were added to
`ranged_shot_dump.mjs` (identity re-verified: PASS on every seed):

1. `aimx/aimy` — the UNDISPLACED aim point. `fireProjectile` throws the aim
   point by the dat dispersion if and only if the accuracy roll failed, so
   `ax ≠ aimx` is an exact, rng-free readout of a failed roll. `willHit` is a
   local and is otherwise unobservable; measured failure rates come out at
   **25.7 / 26.1 / 26.4%** on the three hand-cannoneer sides against their dat
   accuracy of 75, and **0.0%** on all nine accuracy-100 sides.
2. `covered` — `coveredDamageOn(victim)` at the launch instant, read before the
   original runs (which adds this shot to the claim ledger). `covered ≥
   target_hp` is the exact signature of T1's `best || primary` all-covered
   fallback.

---

## 1. M1 — angular / positional pick structure: **REFUTED**

| fight | side | src | n | k | drop% | **dist.pct** | near% | **perp.pct** | perp.min% | **perpS.pct** | min%rand | ang.n | **ang.pct** | rho(d,perp) | ex p50 | ex p90 | far% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | T | 148 | 7.0 | 3.3 | **0.314** | 33.1 | **0.535** | 15.2 | 0.460 | 19.4 | 117 | 0.502 | −0.01 | 0.13 | 1.00 | 25.0 |
| arb v HC | 2:arb | E | 141.0 | 4.6 | 15.7 | 0.179 | 60.7 | 0.542 | 18.3 | 0.591 | 34.6 | 74 | 0.501 | −0.18 | 0.00 | 0.55 | 11.7 |
| arb v HC | 3:HC | T | 32 | 6.5 | 23.8 | **0.318** | 34.4 | **0.617** | 12.5 | 0.547 | 17.8 | 14 | 0.406 | 0.07 | 0.22 | 1.28 | 37.5 |
| arb v HC | 3:HC | E | 36.6 | 2.9 | 23.4 | 0.179 | 68.1 | 0.515 | 28.7 | 0.483 | 49.7 | 12 | 0.504 | −0.17 | 0.00 | 0.40 | 9.0 |
| arb v HCA | 2:arb | T | 253 | 7 | 3.4 | **0.202** | 54.8 | **0.486** | 14.7 | 0.378 | 16.2 | 166 | 0.455 | 0.28 | 0.00 | 0.85 | 18.6 |
| arb v HCA | 2:arb | E | 251 | 6 | 7.0 | 0.062 | 82.8 | 0.574 | 15.9 | 0.638 | 25.3 | 113 | 0.494 | −0.08 | 0.00 | 0.12 | 2.8 |
| arb v HCA | 3:HCA | T | 148 | 4.0 | 3.3 | **0.225** | 62.9 | **0.436** | 37.9 | 0.625 | 30.9 | 74 | 0.408 | 0.11 | 0.00 | 1.29 | 25.0 |
| arb v HCA | 3:HCA | E | 89 | 2 | 40.3 | 0.152 | 79.3 | 0.484 | 29.3 | 0.553 | 55.9 | 32 | 0.466 | −0.04 | 0.00 | 0.05 | 2.2 |
| arb v skirm | 2:arb | T | 92 | 15.0 | 4.2 | **0.106** | 71.7 | **0.359** | 12.0 | 0.337 | 9.6 | 48 | 0.565 | 0.33 | 0.00 | 0.55 | 12.0 |
| arb v skirm | 2:arb | E | 54 | 6.5 | 18.2 | 0.043 | 95.2 | 0.540 | 16.7 | 0.513 | 36.4 | 14 | 0.650 | 0.11 | 0.00 | 0.00 | 1.9 |
| arb v skirm | 3:skirm | T | 115 | 5 | 11.5 | **0.370** | 39.8 | **0.490** | 26.2 | 0.544 | 29.2 | 62 | 0.505 | 0.20 | 0.16 | 1.24 | 31.3 |
| arb v skirm | 3:skirm | E | 76 | 2.0 | 27.6 | 0.206 | 57.4 | 0.356 | 40.4 | 0.467 | 56.8 | 30 | 0.475 | 0.24 | 0.00 | 0.83 | 14.5 |
| skirm v HC | 2:skirm | T | 100 | 5.0 | 1.0 | **0.246** | 56.7 | **0.432** | 33.0 | 0.535 | 28.1 | 76 | 0.336 | 0.26 | 0.00 | 0.31 | 3.0 |
| skirm v HC | 2:skirm | E | 85.7 | 2.9 | 13.3 | 0.216 | 61.7 | 0.483 | 27.9 | 0.546 | 45.6 | 39 | 0.480 | 0.07 | 0.00 | 0.87 | 17.4 |
| skirm v HC | 3:HC | T | 19 | 7 | 24.0 | **0.128** | 61.1 | **0.415** | 16.7 | 0.452 | 19.5 | 8 | 0.360 | 0.07 | 0.00 | 0.54 | 15.8 |
| skirm v HC | 3:HC | E | 21.3 | 2.2 | 17.8 | 0.134 | 79.3 | 0.649 | 16.8 | 0.501 | 52.7 | 7 | 0.583 | −0.22 | 0.00 | 0.09 | 4.7 |
| skirm v HCA | 2:skirm | T | 159 | 5 | 0.6 | **0.267** | 49.3 | **0.406** | 27.9 | 0.454 | 32.6 | 95 | 0.526 | 0.39 | 0.00 | 0.38 | 5.0 |
| skirm v HCA | 2:skirm | E | 101 | 3 | 15.1 | 0.175 | 75.0 | 0.587 | 26.2 | 0.644 | 46.9 | 57 | 0.475 | −0.17 | 0.00 | 0.40 | 5.0 |
| skirm v HCA | 3:HCA | T | 45 | 8 | 2.2 | **0.079** | 71.1 | **0.520** | 2.2 | 0.386 | 13.7 | 8 | 0.493 | 0.13 | 0.00 | 0.50 | 11.1 |
| skirm v HCA | 3:HCA | E | 36 | 2.0 | 34.5 | 0.183 | 76.2 | 0.667 | 14.3 | 0.540 | 61.8 | 10 | 0.683 | −0.52 | 0.00 | 0.12 | 2.8 |
| **HCA v HC** | **2:HCA** | **T** | **164** | **8.0** | **0.6** | **0.337** | **38.9** | **0.558** | **14.6** | **0.523** | **21.0** | **128** | **0.501** | **0.07** | **0.11** | **1.54** | **31.1** |
| **HCA v HC** | **2:HCA** | **E** | **113.4** | **3.2** | **27.1** | **0.112** | **79.0** | **0.486** | **18.1** | **0.466** | **45.0** | **49** | **0.556** | **0.01** | **0.00** | **0.12** | **4.3** |
| HCA v HC | 3:HC | T | 104 | 9.0 | 11.9 | **0.215** | 44.7 | **0.472** | 16.5 | 0.600 | 15.8 | 62 | 0.427 | 0.22 | 0.02 | 1.43 | 25.0 |
| HCA v HC | 3:HC | E | 84.0 | 4.0 | 10.2 | 0.045 | 88.6 | 0.500 | 15.2 | 0.512 | 35.5 | 31 | 0.499 | −0.05 | 0.00 | 0.01 | 1.2 |

**The hypothesis predicted `perp.pct` near 0 and `dist.pct` mid-range. The
opposite is measured, and not marginally.** Averaged over the twelve tape
sides:

| metric | tape mean pctile | random null | tape `min%` | its random null |
|---|---|---|---|---|
| **distance** | **0.234** | 0.500 | **51.5** | 21.2 |
| across-the-line (`perp`) | **0.477** | 0.500 | 19.1 | 21.2 |
| straight-ahead (`perpS`) | **0.487** | 0.500 | – | – |
| aim swing (`ang`) | **0.457** | 0.500 | – | – |

Distance carries a **2.4× lift over chance** on `min%` (51.5 vs 21.2) and pulls
the percentile more than halfway to the minimum. The three positional metrics
carry **none**: `perp.pct` 0.477 and `perpS.pct` 0.487 against a null of 0.500,
and `perp.min%` 19.1 against its own null of 21.2 — *below* chance. It is not
one fight: `perp.pct` is above 0.5 on four of twelve tape sides and
`perp.min%` is below its own random null on eight of twelve.

Three things stop this being an artefact of the geometry:

1. **The two metrics are nearly independent inside a pool.** `rho(d,perp)`, the
   mean within-pool Spearman, is **−0.01 to +0.39 on tape (mean 0.18)**, so the
   distance column is not smuggling the perp column or vice versa.
2. **It survives the pool definition.** With the pool widened to `inRange()`
   the drop rate falls to 0.0–20.0% and the numbers move by ≤0.04.
3. **The engine reproduces the tape on `perp` and diverges on `d`.** Engine
   `perp.pct` runs 0.356–0.667 against the tape's 0.359–0.617 — the same
   nothing. Engine `dist.pct` is 0.043–0.216 against the tape's 0.079–0.370,
   i.e. **too near-first, exactly as R5d measured**. The entire tape-engine gap
   in target choice lives in one column, and it is the distance column.

The last three columns say the same thing from the outcome side: the tape fires
past a nearer body (`excess > 0.5`) on **3.0–37.5%** of its shots with an
excess p90 of **0.31–1.54 tiles**; the engine on **1.2–17.4%** with p90
**0.00–0.87**. In `HCA v HC` the gap is 31.1% vs 4.3% and p90 1.54 vs 0.12.

---

## 2. M2 — conditional pick chains

Pooled over the twelve sides, n-weighted. `prev victim` is the state, at this
launch, of the victim of that shooter's previous launch.

| src | prev victim | n | share% | same% | near% | far% | dist.pct | perp.pct |
|---|---|---|---|---|---|---|---|---|
| T | first shot | 202 | 14.6 | – | 56.6 | 26.7 | 0.222 | 0.483 |
| T | dead / gone | 175 | 12.7 | – | 44.1 | 11.4 | 0.195 | 0.466 |
| T | alive, left reach | 430 | 31.2 | – | 56.3 | 13.7 | 0.244 | 0.458 |
| T | **alive, covered** | **95** | **6.9** | **31.6** | **28.9** | **43.2** | **0.390** | 0.537 |
| T | alive, open | 477 | 34.6 | **52.0** | **49.0** | 21.4 | 0.252 | 0.474 |
| E | first shot | 206 | 19.0 | – | 66.2 | 14.8 | 0.166 | 0.495 |
| E | dead / gone | 144 | 13.2 | – | 87.4 | 2.8 | 0.074 | 0.546 |
| E | alive, left reach | 218 | 20.0 | – | 75.4 | 3.2 | 0.172 | 0.524 |
| E | alive, covered | 141 | 12.9 | 17.4 | 18.1 | 17.0 | 0.380 | 0.505 |
| E | alive, open | 380 | 34.9 | **76.4** | **96.5** | 0.9 | 0.018 | 0.549 |

`HCA v HC`, the fight that matters, per side:

| src | side | prev victim | n | share% | same% | near% | dist.pct | ex p50 | far% |
|---|---|---|---|---|---|---|---|---|---|
| T | 2:HCA | first | 19 | 11.6 | – | 58.8 | 0.201 | 0.00 | 21.1 |
| T | 2:HCA | dead / gone | 28 | 17.1 | – | 51.9 | 0.201 | 0.00 | 28.6 |
| T | 2:HCA | **left reach** | **76** | **46.3** | – | **27.4** | **0.409** | **0.18** | **30.3** |
| T | 2:HCA | covered | 8 | 4.9 | 12.5 | 12.5 | 0.657 | 0.84 | 75.0 |
| T | 2:HCA | open | 33 | 20.1 | 36.4 | 50.0 | 0.278 | 0.00 | 30.3 |
| E | 2:HCA | first | 18.5 | 16.3 | – | 78.1 | 0.096 | 0.00 | 10.8 |
| E | 2:HCA | dead / gone | 20.6 | 18.1 | – | 96.4 | 0.025 | 0.00 | 0.5 |
| E | 2:HCA | left reach | 26.1 | 23.0 | – | 78.8 | 0.135 | 0.00 | 1.7 |
| E | 2:HCA | covered | 14.3 | 12.6 | 25.3 | 8.5 | 0.504 | 0.11 | 14.2 |
| E | 2:HCA | open | 34.0 | 30.0 | **82.1** | **94.7** | 0.014 | 0.00 | 1.0 |

**Verdict (M2). The aggregate does NOT decompose into "nearest at
re-acquisition, positional in between" — it decomposes into two different
things, and neither of them is positional.**

1. **Re-acquisition is the NEAREST-est regime in the tape, not the least.**
   First shot 56.6% nearest, previous victim dead 44.1%, left reach 56.3% —
   against 49.0% in the steady `open` regime. The predicted ordering is the
   other way round.
2. **The far picks concentrate almost entirely in one small regime: the
   previous victim is alive, in reach, and already lethally covered.** 43.2%
   of those shots are `far` against 11.4–26.7% everywhere else, and their
   `dist.pct` is 0.390 against 0.195–0.252. **But it is 6.9% of tape shots.**
   A mechanism that only operates there cannot move the corpus.
3. **`perp.pct` is 0.458–0.549 in every single regime, on both sources** (tape
   0.458–0.537, engine 0.495–0.549), i.e. never distinguishable from the 0.500
   null. The positional metric does not become informative in any conditional
   slice.
4. **The one large, clean tape-vs-engine gap is persistence in the open
   regime**: with the previous victim alive, in reach and uncovered, the tape
   re-picks it 52.0% of the time and picks the nearest 49.0%; the engine
   re-picks 76.4% and picks the nearest **96.5%**. Same regime, same share of
   shots (34.6 vs 34.9), completely different behaviour. T1's non-stickiness is
   not what is missing — the tape is *stickier* than T1 predicts on the covered
   branch (31.6% vs 17.4%) and *less* near-first than the engine everywhere.
5. In `HCA v HC` specifically, 46.3% of the tape's archer shots are taken with
   the previous victim alive but out of reach, and that is the bucket with the
   lowest near% (27.4) and the highest `dist.pct` (0.409). The engine's
   equivalent bucket is 23.0% of shots at 78.8% nearest. This is the shot-side
   shadow of §4: the tape's archers are constantly losing their victim's range
   because they are wandering, and the engine's are not.

---

## 3. M3 — assignment vs advance in `HCA v HC`: **DEPTH DRIVES ASSIGNMENT**

`assign` = the victim's depth percentile in its own army along the threat axis
(0 = frontmost, 1 = deepest). `adv` = how far the shooter is ahead of its own
army's centroid along the same axis. `pen` = how far inside its own reach lip
its nearest enemy is. `L+x` = the Spearman correlation between `assign` at a
shot and the shooter's `adv` **x seconds later**.

| side | src | shots | riders | rho(a,adv) | rho(a,pen) | rider rho(a,adv) | rider rho(a,pen) | L−6 | L−4 | L−2 | L−1 | L+0 | L+1 | L+2 | L+4 | L+6 | L+8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **2:HCA** | **T** | **160** | **17** | **−0.064** | **0.133** | **−0.123** | **−0.042** | −0.044 | −0.022 | −0.008 | −0.027 | **−0.068** | −0.116 | −0.154 | −0.173 | −0.270 | **−0.384** |
| 2:HCA | E | 108.3 | 15.3 | 0.520 | 0.093 | 0.840 | 0.794 | 0.466 | 0.513 | 0.553 | 0.582 | 0.520 | 0.537 | 0.553 | 0.609 | 0.616 | 0.611 |
| 3:HC | T | 104 | 14 | −0.059 | 0.018 | −0.222 | −0.648 | −0.204 | −0.151 | −0.156 | −0.127 | −0.089 | −0.060 | −0.023 | −0.003 | 0.008 | 0.019 |
| 3:HC | E | 83.9 | 14.2 | 0.668 | −0.002 | 0.767 | −0.353 | 0.720 | 0.844 | 0.810 | 0.815 | 0.668 | 0.671 | 0.728 | 0.781 | 0.785 | 0.760 |

**Verdict (M3). The positional-assignment hypothesis predicted a positive
correlation peaking at a POSITIVE lag — pick a deep target, then ride in to it.
The tape shows no positive correlation at any lag, and the sign of the trend is
the opposite of the prediction.**

- On the load-bearing side (2:HCA, the archers that actually move) the
  same-shot correlation is **−0.064** and the per-rider correlation between
  mean assignment depth and maximum advance is **−0.123**. A rider that is
  given deep targets is, if anything, *less* advanced.
- The lag sweep is monotone downward: −0.044 at −6 s, −0.068 at 0, −0.384 at
  +8 s. Assignment depth does not lead advance; it trails it and then decays.
  Read with §4, the sequence is: the rider gets deep, and *then* the units
  around it are by definition the deep ones.
- **The engine has the coupling the tape lacks** (+0.52 same-shot, +0.84
  rider-level, flat across every lag), which is the nearest-first signature —
  with T1, where a unit stands and which enemy it picks are the same variable.
  Two caveats on reading the engine column: its formation is nearly flat (army
  depth 1.62–1.97 against the tape's 2.54–4.26, R5c §3c), so its `assign` is
  spread over a small absolute range; and the hand-cannoneer rows of this table
  are not informative about cause at all, because a speed-0 side's `adv` barely
  varies. The load-bearing statement is the tape's 2:HCA row.

---

## 4. M4 — ride-in anatomy

### 4a. The five deepest units of each side (engine = seed 1)

`pen_max` = the deepest its nearest enemy ever got inside its reach lip.
`fire10` / `exp10` = launches in the 10 s before that instant against what its
own reload would produce. `spd` = its mean speed over the 3 s run-up against
its dat `walk`. `aim(near/vic/cen)` = median angle, degrees, between its
velocity and the direction to its nearest enemy / the victim it was assigned /
the enemy centroid, over the moving frames of that window.

| side | src | unit | t_peak | **pen_max** | dmin | shots | **fire10** | exp10 | gap_pre | k@peak | spd | walk | aim(near) | aim(vic) | aim(cen) | assign@peak | recede | died_at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2:HCA | T | 1631 | 29.0 | **6.17** | 1.45 | 12 | **1** | 5.6 | 8.00 | 9 | 1.48 | 1.54 | 57 | – | 64 | 0.83 | −1.17 | – |
| 2:HCA | T | 1634 | 29.0 | **6.05** | 1.57 | 13 | **3** | 5.6 | 0.86 | 9 | 0.77 | 1.54 | 16 | 4 | 11 | 0.83 | −1.27 | – |
| 2:HCA | T | 1633 | 29.7 | **5.81** | 1.80 | 6 | **1** | 5.6 | 1.86 | 7 | 0.26 | 1.54 | 29 | – | 19 | 0.83 | −0.45 | 4.1 |
| 2:HCA | T | 1646 | 17.3 | **5.61** | 2.01 | 4 | **0** | 5.6 | 10.66 | 14 | 1.45 | 1.54 | 27 | 37 | 40 | 0.38 | 0.00 | 4.6 |
| 2:HCA | T | 1630 | 17.3 | **5.41** | 2.21 | 5 | **1** | 5.6 | 0.36 | 14 | 0.85 | 1.54 | 35 | 52 | 37 | 1.00 | −0.09 | 6.1 |
| 2:HCA | E | 1-12 | 0.0 | 2.62 | 5.00 | 1 | 0 | 5.6 | – | 14 | – | 1.54 | – | – | – | 0.30 | 0.00 | 1.4 |
| 2:HCA | E | 1-11 | 0.0 | 1.62 | 6.00 | 6 | 0 | 5.6 | – | 8 | – | 1.54 | – | – | – | 0.05 | −0.27 | 15.4 |
| 2:HCA | E | 1-0 | 0.0 | 1.53 | 6.08 | 4 | 0 | 5.6 | – | 6 | – | 1.54 | – | – | – | 0.05 | −0.92 | 8.3 |
| 2:HCA | E | 1-14 | 0.0 | 1.53 | 6.08 | 6 | 0 | 5.6 | – | 7 | – | 1.54 | – | – | – | 0.00 | −0.43 | 15.8 |
| 2:HCA | E | 1-1 | 16.3 | 1.49 | 6.12 | 12 | 5 | 5.6 | 0.22 | 8 | 0.00 | 1.54 | – | – | – | 0.12 | −1.35 | – |
| 3:HC | T | 1717 | 29.0 | 6.17 | 1.45 | 9 | 3 | 2.9 | 1.41 | 9 | 0.00 | 0.96 | – | – | – | 0.30 | 0.00 | 4.2 |
| 3:HC | T | 1713 | 29.0 | 5.82 | 1.80 | 10 | 3 | 2.9 | 2.40 | 8 | 0.00 | 0.96 | – | – | – | 0.11 | 0.00 | 6.9 |
| 3:HC | T | 1716 | 17.3 | 5.55 | 2.06 | 5 | 2 | 2.9 | 3.99 | 14 | 0.28 | 0.96 | 19 | 19 | 24 | 0.21 | 0.00 | 1.8 |
| 3:HC | T | 1705 | 29.0 | 5.00 | 2.62 | 11 | 3 | 2.9 | 1.41 | 6 | 0.00 | 0.96 | – | – | – | 0.30 | 0.00 | 11.9 |
| 3:HC | T | 1712 | 29.0 | 4.85 | 2.77 | 10 | 3 | 2.9 | 2.37 | 9 | 0.00 | 0.96 | – | – | – | 0.22 | 0.00 | 4.7 |
| 3:HC | E | 2-2 | 0.0 | 2.62 | 5.00 | 1 | 0 | 2.9 | – | 10 | – | 0.96 | – | – | – | 0.00 | −1.00 | 2.0 |
| 3:HC | E | 2-1 | 0.0 | 1.62 | 6.00 | 4 | 0 | 2.9 | – | 5 | – | 0.96 | – | – | – | 0.00 | −0.96 | 13.5 |
| 3:HC | E | 2-8 | 0.0 | 1.53 | 6.08 | 4 | 0 | 2.9 | – | 5 | – | 0.96 | – | – | – | 0.00 | −0.95 | 13.9 |
| 3:HC | E | 2-12 | 0.0 | 1.53 | 6.08 | 3 | 0 | 2.9 | – | 5 | – | 0.96 | – | – | – | 0.00 | −0.90 | 9.6 |
| 3:HC | E | 2-0 | 16.3 | 1.49 | 6.12 | 3 | 1 | 2.9 | 0.62 | 8 | 0.53 | 0.96 | 17 | 22 | 4 | 0.08 | 0.00 | 2.1 |

Two facts before any interpretation:

- **The engine has no ride-in to anatomise.** Four of its five deepest archers
  peak at **t = 0.0** with `pen_max` 1.53–2.62 and `dmin` 5.00–6.08 — that is
  the tapebox spawn geometry, not a movement. The one that peaks later (1-1,
  t = 16.3) reaches `pen` 1.49, and its speed over the run-up is **0.00**. The
  engine's deepest unit never moves in; the tape's five reach `pen` 5.41–6.17
  and `dmin` 1.45–2.21.
- **The deep tape riders are UNDER-firing, not over-firing.** `fire10` is
  **0, 1, 1, 1, 3** against an `exp10` of **5.6**. Four of the five had not
  fired for 0.9–10.7 s at their deepest, with 7–14 enemies in reach. They are
  not units executing an approach to shoot better; they are units that have
  gone quiet.
- **`assign@peak` is 0.83 for each of the three deepest** (0.38 and 1.00 for
  the other two). That is exactly what "depth drives assignment" predicts and
  *not* what "assignment drives depth" predicts: once a rider is inside the gun
  line, the units around it ARE the deep ones. Combined with §3's lag sweep,
  the deep assignment is a consequence of the position, not its cause.

### 4b. When the closing actually happens

Closing speed along the threat axis, over every 0.1 s unit-step, bucketed by
how long since that unit last fired (in units of its own reload) crossed with
whether the victim of its last shot is dead.

| side | src | bucket | n | rad p50 | **close%** | back% |
|---|---|---|---|---|---|---|
| 2:HCA | T | never fired / victim alive | 742 | 0.000 | 35.8 | 18.6 |
| 2:HCA | T | **≤1 cycle / victim alive** | **1863** | 0.000 | **2.0** | 1.5 |
| 2:HCA | T | ≤1 cycle / victim dead | 871 | 0.000 | 11.1 | 2.0 |
| 2:HCA | T | 1–2 cycles / victim alive | 225 | 0.000 | 26.7 | 20.0 |
| 2:HCA | T | 1–2 cycles / victim dead | 664 | 0.000 | 14.3 | 10.8 |
| 2:HCA | T | **>2 cycles / victim alive** | **37** | **0.845** | **62.2** | 0.0 |
| 2:HCA | T | **>2 cycles / victim dead** | **763** | **0.200** | **52.2** | 17.6 |
| 2:HCA | E | never fired / victim alive | 1002.6 | 0.000 | 33.3 | 14.8 |
| 2:HCA | E | ≤1 cycle / victim alive | 1594.4 | 0.000 | 3.5 | 2.2 |
| 2:HCA | E | ≤1 cycle / victim dead | 343.0 | 0.000 | 8.0 | 2.8 |
| 2:HCA | E | 1–2 cycles / victim alive | 76.6 | 0.000 | 1.5 | 1.5 |
| 2:HCA | E | 1–2 cycles / victim dead | 640.5 | 0.000 | 15.1 | 3.6 |
| 2:HCA | E | **>2 cycles / victim alive** | **3.0** | 0.000 | 1.8 | 0.0 |
| 2:HCA | E | **>2 cycles / victim dead** | **907.6** | **0.000** | **20.9** | 10.3 |
| 3:HC | T | never fired / victim alive | 797 | 0.000 | 29.6 | 3.9 |
| 3:HC | T | ≤1 cycle / victim alive | 2300 | 0.000 | 0.7 | 0.0 |
| 3:HC | T | ≤1 cycle / victim dead | 838 | 0.000 | 6.6 | 0.0 |
| 3:HC | T | 1–2 cycles / victim alive | 238 | 0.000 | 2.5 | 0.0 |
| 3:HC | T | 1–2 cycles / victim dead | 370 | 0.000 | 5.9 | 0.0 |
| 3:HC | T | >2 cycles / victim alive | 6 | 0.000 | 0.0 | 0.0 |
| 3:HC | T | >2 cycles / victim dead | 165 | 0.000 | 0.6 | 0.0 |
| 3:HC | E | never fired / victim alive | 495.2 | 0.000 | 42.3 | 7.5 |
| 3:HC | E | ≤1 cycle / victim alive | 2113.4 | 0.000 | 2.4 | 0.7 |
| 3:HC | E | ≤1 cycle / victim dead | 451.2 | 0.000 | 12.8 | 3.1 |
| 3:HC | E | 1–2 cycles / victim dead | 96.5 | 0.009 | 30.6 | 20.3 |
| 3:HC | E | >2 cycles / victim dead | 119.1 | 0.019 | 40.5 | 18.9 |
| 3:HC | E | >2 cycles / victim alive | 7.5 | −0.025 | 31.5 | 39.1 |

**Verdict (M4). The ride-in is a SILENCE behaviour, not a targeting behaviour,
and the engine's version of it is throttled rather than absent.**

- The tape's archers close on **2.0%** of the unit-steps in which they are
  trading on cooldown at a live victim (n = 1,863 — the modal state of the
  fight) and on **52.2–62.2%** of the steps in which they have been silent for
  more than two reload cycles (n = 800). That is a **26×** difference in the
  same fight and the same units.
- **The engine has the same silent time and does not use it.** Its
  `>2 cycles / victim dead` bucket is 907.6 unit-steps against the tape's 763
  — the same amount of idle — but it closes on **20.9%** of them against the
  tape's **52.2%**, and its median radial speed there is **0.000** against the
  tape's **0.200**. Both sources also agree almost exactly on the opening walk
  (`never fired`: close% 35.8 tape vs 33.3 engine), so this is not a movement
  or pathing difference in general — it is specific to what a ranged unit does
  after it stops shooting.
- **The one bucket the engine essentially does not have is the tape's fastest
  closer.** `>2 cycles / victim ALIVE` is 37 unit-steps on tape, closing 62.2%
  of the time at a median 0.845 tiles/s (55% of walk speed); the engine has
  **3.0** unit-steps there. In the engine a unit whose target is alive and in
  reach fires; on tape a unit can be quiet for >3.6 s with a live target and
  walk in while it is.
- `recede` is −0.09 to −1.27 for the tape's deep riders: they mostly do not
  come back out. Two of the five survive the fight; three die 4.1–6.1 s after
  their deepest point.

---

## 5. M5 — null models

Every rule is expressed as a probability over the shot's candidates, so a
deterministic and a stochastic rule are scored on the same two things: `acc%`
= the mass it puts on the victim the shot actually went to, and the excess
distribution its own picks would produce. Persistence rules are teacher-forced
on the shooter's real previous victim. `acc far%` restricts the accuracy to the
shots the tape itself fired past a nearer body (excess > 0.5).

### 5a. Pooled over the twelve tape sides (mean), sorted by accuracy

| rule | acc% | acc far% | Δ near% | Δ ex p90 | Δ far% |
|---|---|---|---|---|---|
| **persist→nearest** | **55.9** | 19.1 | +24.8 | −0.42 | −10.7 |
| nearest | 53.4 | 0.0 | +46.6 | −0.91 | −20.0 |
| nearest-uncovered (T1, as shipped) | 53.0 | 3.4 | +34.3 | −0.79 | −16.2 |
| min-ang | 41.0 | 22.4 | −10.4 | +0.21 | +5.8 |
| **nearest of 3 across** | 39.4 | 4.9 | **+2.5** | **−0.08** | **−0.5** |
| persist→perp | 37.0 | 24.3 | −18.8 | +0.36 | +14.0 |
| persist(open)→perp | 36.4 | **24.7** | −20.6 | +0.39 | +15.6 |
| rand: 2 nearest | 36.3 | 3.0 | −1.6 | −0.42 | −10.1 |
| rand: 1/rank | 31.2 | 8.9 | −9.9 | +0.16 | +5.5 |
| nearest of 2 across | 30.3 | 8.3 | −12.3 | +0.10 | +6.4 |
| rand: 3 nearest | 29.9 | 8.8 | −16.5 | −0.21 | −2.9 |
| rand: 1/dist | 21.9 | 13.2 | −30.8 | +0.50 | +20.6 |
| min-perp | 21.8 | 9.2 | −28.1 | +0.45 | +22.0 |
| rand: uniform in reach | 21.1 | **13.7** | −32.2 | +0.61 | +22.6 |
| rand: uniform uncovered | 20.9 | 14.4 | −34.0 | +0.62 | +23.9 |

Δ columns are rule minus OBSERVED, so 0 is a perfect match.

### 5b. `HCA v HC` 2:HCA — the fight that carries the residual

| src | rule | n | acc% | acc far% | near% | ex p50 | ex p90 | ex mean | far% |
|---|---|---|---|---|---|---|---|---|---|
| T | **OBSERVED** | 164 | 100.0 | 100.0 | **41.5** | **0.11** | **1.54** | **0.62** | **31.1** |
| T | nearest | 164 | **41.5** | 0.0 | 100.0 | 0.00 | 0.00 | 0.00 | 0.0 |
| T | persist→nearest | 164 | 38.4 | 3.9 | 78.7 | 0.00 | 0.62 | 0.22 | 11.0 |
| T | nearest-uncovered (T1) | 164 | 33.5 | 0.0 | 84.1 | 0.00 | 0.19 | 0.06 | 4.9 |
| T | min-ang | 164 | 30.5 | 13.7 | 26.8 | 0.35 | **1.62** | **0.63** | 39.6 |
| T | **nearest of 3 across** | 164 | 29.9 | 7.8 | **51.8** | 0.00 | 0.94 | 0.26 | 23.2 |
| T | rand: 2 nearest | 164 | 29.3 | 0.0 | 52.1 | 0.00 | 0.51 | 0.15 | 10.1 |
| T | rand: 1/rank | 164 | 27.2 | 7.1 | 43.0 | **0.11** | 1.21 | 0.41 | 28.6 |
| T | rand: 3 nearest | 164 | 26.3 | 7.8 | 37.5 | 0.10 | 0.88 | 0.27 | 19.9 |
| T | nearest of 2 across | 164 | 25.6 | 5.9 | 45.1 | 0.12 | 1.09 | 0.32 | 26.8 |
| T | persist→perp | 164 | 22.6 | 9.8 | 25.6 | 0.35 | 1.41 | 0.57 | 42.1 |
| T | persist(open)→perp | 164 | 22.0 | 7.8 | 26.2 | 0.36 | 1.41 | 0.57 | 42.7 |
| T | rand: 1/dist | 164 | 21.2 | 10.6 | 23.7 | 0.44 | 1.49 | 0.63 | 44.7 |
| T | rand: uniform in reach | 164 | 21.0 | 12.9 | 21.0 | 0.47 | 1.64 | 0.72 | 48.3 |
| T | rand: uniform uncovered | 164 | 19.5 | 12.6 | 19.2 | 0.50 | 1.64 | 0.73 | 49.8 |
| T | min-perp | 164 | 18.3 | 7.8 | 29.9 | 0.28 | 1.30 | 0.47 | 41.5 |
| E | **OBSERVED** | 108 | 100.0 | 100.0 | 79.6 | 0.00 | 0.21 | 0.06 | 3.7 |
| E | nearest-uncovered (T1) | 108 | **100.0** | 100.0 | 79.6 | 0.00 | 0.24 | 0.06 | 3.7 |
| E | nearest | 108 | 78.7 | 0.0 | 100.0 | 0.00 | 0.00 | 0.00 | 0.0 |
| E | persist→nearest | 108 | 72.2 | 0.0 | 91.7 | 0.00 | 0.00 | 0.02 | 0.9 |

**Verdict (M5). No rule tested matches both, and the two things a rule can be
good at are pulled apart cleanly.**

1. **The distributional winner is `nearest of 3 across`** — take the three
   enemies most directly across the line from you and shoot the nearest of
   them. Pooled it lands Δ near% **+2.5**, Δ ex p90 **−0.08**, Δ far% **−0.5**:
   the tape's excess distribution, reproduced essentially exactly and without a
   fitted constant. Its per-pick accuracy is **39.4%**, well below plain
   nearest's 53.4%. On `HCA v HC` 2:HCA it gives near% 51.8 against the
   observed 41.5 and far% 23.2 against 31.1 — the closest of any rule with a
   defensible accuracy, but still short at the tail.
2. **The accuracy winner is `persist→nearest`** — keep the previous victim
   while it is in reach, otherwise take the nearest. 55.9% pooled, ahead of
   both plain nearest (53.4) and **the shipped T1 (53.0)**, and best on 7 of the
   12 sides. It is also distributionally closer than either (Δ near% +24.8
   against nearest's +46.6 and T1's +34.3). **T1 as shipped is not even the best
   member of the nearest family**, which is consistent with R5d's scoreboard
   moving the wrong way.
3. **Nothing explains the far tail.** On the shots the tape fired past a nearer
   body, plain nearest scores 0.0% by construction, T1 3.4%, and the best rule
   in the table (`persist(open)→perp`) scores **24.7% against a uniform-random
   baseline of 13.7%**. A 1.8× lift over chance on a tail that is 3–37% of
   shots is not a mechanism, it is a hint.
4. **The engine side is a clean control.** T1 recovers the engine's own picks
   at **100.0%** accuracy, which is what it should do — it *is* the rule — and
   confirms the reconstruction (pool, coverage, tie-breaks) is faithful.

---

## 6. M6 — plannedDamage sensitivity (mechanical check)

The engine books `plannedDamage` = the full post-armor damage on **every**
projectile, including one whose accuracy roll has already failed and which
(with `R5D1.reducedDamageHits` off) will apply nothing. The same arithmetic is
re-run with a failed-roll projectile worth full / half / zero.

`probe fb%` is the engine's exact all-covered fallback rate off
`coveredDamageOn` at launch; `probe fb% half/zero` subtracts only the exactly
identified failed-roll contribution from it, so the baseline is the engine's own
number and the stale-hp bias of the rebuild cancels. `fb% *`, `div% *` and
`vcov% *` are the full rebuild (a lower bound in absolute terms — hp is read
from the 10 Hz stream and is stale-high — but internally consistent).

| fight | side | shots | **fail%** | probe fb% | probe fb% half | **probe fb% zero** | fb% full | fb% half | fb% zero | div% full | div% half | **div% zero** | vcov% full | vcov% zero |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arb v HC | 2:arb | 167.2 | 0.0 | 12.59 | 12.59 | 12.59 | 9.12 | 9.12 | 9.12 | 34.75 | 34.75 | 34.75 | 10.06 | 10.06 |
| **arb v HC** | **3:HC** | **48** | **26.4** | **21.62** | **21.08** | **17.42** | **10.62** | **9.92** | **5.62** | **23.62** | **22.79** | **13.97** | **10.75** | **5.89** |
| arb v HCA | 2:arb | 270 | 0.0 | 1.90 | 1.90 | 1.90 | 1.60 | 1.60 | 1.60 | 15.90 | 15.90 | 15.90 | 2.00 | 2.00 |
| arb v HCA | 3:HCA | 149 | 0.0 | 15.40 | 15.40 | 15.40 | 7.90 | 7.90 | 7.90 | 13.50 | 13.50 | 13.50 | 7.90 | 7.90 |
| arb v skirm | 2:arb | 66 | 0.0 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.60 | 5.60 | 5.60 | 0.00 | 0.00 |
| arb v skirm | 3:skirm | 105 | 0.0 | 25.70 | 25.70 | 25.70 | 22.40 | 22.40 | 22.40 | 27.60 | 27.60 | 27.60 | 22.40 | 22.40 |
| skirm v HC | 2:skirm | 98.8 | 0.0 | 17.48 | 17.48 | 17.48 | 14.58 | 14.58 | 14.58 | 30.06 | 30.06 | 30.06 | 14.69 | 14.69 |
| **skirm v HC** | **3:HC** | **25.9** | **26.1** | **19.91** | **15.43** | **13.86** | **7.05** | **3.02** | **3.02** | **14.36** | **10.51** | **9.81** | **7.05** | **3.02** |
| skirm v HCA | 2:skirm | 119 | 0.0 | 8.40 | 8.40 | 8.40 | 2.00 | 2.00 | 2.00 | 19.80 | 19.80 | 19.80 | 2.00 | 2.00 |
| skirm v HCA | 3:HCA | 55 | 0.0 | 9.10 | 9.10 | 9.10 | 11.10 | 11.10 | 11.10 | 13.90 | 13.90 | 13.90 | 11.10 | 11.10 |
| HCA v HC | 2:HCA | 155.5 | 0.0 | 14.06 | 14.06 | 14.06 | 8.40 | 8.40 | 8.40 | 16.46 | 16.46 | 16.46 | 8.58 | 8.58 |
| **HCA v HC** | **3:HC** | **94** | **25.7** | **8.51** | **7.67** | **5.63** | **2.37** | **1.43** | **0.48** | **10.18** | **8.41** | **5.34** | **2.49** | **0.60** |

**Verdict (M6). The over-count is real, exactly localised, and worth about half
the fallback on the sides that have it — but it touches only three of twelve
sides and the fallback is not where T1's problem is.**

- **The failed-roll population is identified exactly**, not assumed: 26.4 /
  26.1 / 25.7% on the three hand-cannoneer sides against their dat accuracy of
  75, and **0.0%** on all nine accuracy-100 sides. On those nine sides every
  column is byte-identical across the three weightings — **the fix cannot move
  them at all**.
- On the three hand-cannoneer sides, discounting a failed roll entirely:
  - the engine's exact all-covered fallback falls **21.6 → 17.4**, **19.9 →
    13.9** and **8.5 → 5.6** — a **19–34% relative reduction**;
  - the rebuild's fallback, which is internally consistent across weightings,
    falls **10.6 → 5.6**, **7.0 → 3.0** and **2.4 → 0.5**, i.e. it roughly
    **halves** (and falls 5× on `HCA v HC`);
  - **T1's diversion rate falls 23.6 → 14.0, 14.4 → 9.8 and 10.2 → 5.3** — a
    **32–48% relative reduction**. Between a fifth and a half of every redirect
    the hand cannoneer currently makes is a redirect away from a target that
    only *looks* covered.
  - Half-weight (the tape's actual mechanic, R5c Q0) recovers roughly a third
    of the way: 21.6 → 21.1, 19.9 → 15.4, 8.5 → 7.7.
- **Order of magnitude for the main session:** corpus-wide the engine's exact
  fallback rate is **12.9%** of ranged shots (mean over the twelve sides);
  discounting failed rolls entirely takes it to **11.8%**. The whole effect is
  1.1 points of fallback across the corpus, concentrated in three sides. It is a
  correctness fix, not a lever on the ranged residual.

---

## 7. Verdicts

| # | question | verdict | evidence | magnitude |
|---|---|---|---|---|
| **M1** | picks are positional ("shoot across from me") | **REFUTED** | §1: tape `perp.pct` 0.477, `perpS.pct` 0.487, `ang.pct` 0.457 against a random null of 0.500; `perp.min%` 19.1 against its own null of 21.2 | distance pctile 0.234 / near% 51.5 vs null 21.2 — the only metric that carries information |
| **M2** | the rank-2–3.5 aggregate splits into nearest-at-re-acquisition + positional drift | **REFUTED, and it splits the other way** | §2: re-acquisition is the *most* near-first tape regime (44–57%) vs steady state 49%; `perp.pct` 0.458–0.537 in **every** regime | the far picks concentrate in "previous victim covered" (far% 43.2) — 6.9% of shots |
| **M3** | deep riders ride in BECAUSE they were assigned deep targets | **REFUTED — depth drives assignment** | §3: tape rider-level rho(mean assign, max adv) **−0.123**; lag sweep −0.068 at 0 s falling to −0.384 at +8 s; engine has the coupling (+0.84) the tape lacks | §4a: the three deepest riders' `assign@peak` is 0.83 each, i.e. deep targets are what is *around* them once they arrive |
| **M4** | what the ride-in actually is | **a SILENCE behaviour** | §4b: tape closes on **2.0%** of on-cooldown-with-a-live-victim steps and **52–62%** of >2-cycle-silent steps; engine has the same silent time (907.6 vs 763 steps) and closes on **20.9%** of it | tape deepest five: `pen` 5.41–6.17, `fire10` 0–3 against `exp10` 5.6; engine deepest five peak at t = 0 (spawn), `pen` 1.49–2.62 |
| **M5** | a rule that matches pick distribution AND produces elongation | **NONE** | §5: `nearest of 3 across` matches the distribution (Δ near% +2.5, Δ p90 −0.08, Δ far% −0.5) at 39.4% accuracy; `persist→nearest` leads accuracy (55.9%) with the distribution 24.8 points too near-first | best `acc far%` of any rule is 24.7% against a random 13.7% |
| **M6** | the failed-roll plannedDamage over-count matters | **real, localised, small** | §6: fail% 25.7–26.4 on the three HC sides, **0.0 on the other nine**; discounting it cuts the exact fallback 19–34% relative and T1 diversion 32–48% relative | corpus fallback 12.9% → 11.8% |

**What the data selects.** The round's central hypothesis — that selection and
elongation are one positional phenomenon — is refuted from both ends. The pick
carries no positional signal at any level of conditioning, in either pool
definition, on any of twelve sides (§1, §2). And the elongation is not
downstream of the pick: the tape's riders that go deep are not the riders with
deep assignments (§3), they are the riders that have **stopped firing** (§4).

The two open threads this leaves are separate, and neither is a targeting rule:

- **The pick.** The tape's excess distribution is reproduced almost exactly by
  a rule that mixes an across-the-line filter with nearest (`nearest of 3
  across`), and its per-shot identity is best predicted by a rule with
  *stickiness* (`persist→nearest`, 55.9%, which beats shipped T1's 53.0%). The
  two are not the same rule and the gap between them is the E15c signature:
  the tape's dispersion is real, but which unit receives a given shot is not
  determined by anything measured here.
- **The elongation.** The measured discriminator is silence, not selection:
  a tape archer that has not fired for more than two reload cycles closes
  52–62% of the time; the engine, with the same amount of idle time, closes
  20.9% of the time and at a median radial speed of exactly 0.000. The tape's
  fastest-closing bucket (>2 cycles silent with a **live** target, 0.845
  tiles/s) has 37 unit-steps on tape and 3.0 in the engine — the engine
  essentially cannot be in that state, because a unit with a live target in
  reach fires.

---

## 8. Methodology and limits

- **Probe neutrality.** `ranged_shot_dump.mjs` gained two read-only fields
  (`aimx/aimy` via a duplicate `aimPointFor()` call, `covered` via
  `coveredDamageOn()`), both taken before the original runs. Neither draws rng
  nor mutates state. `--verify-identity` re-runs each seed with the wrapper
  removed and diffs the damage stream: **PASS on every seed**. No file under
  `apps/website/static/js/engine/` was modified.
- **The choice set is a modelling decision and was tested both ways.**
  `canReach` (the engine's own alternative test) is the default; `--pool-reach
  inrange` widens it by the 5 px `MELEE_RANGE_BUFFER`, which is the tape's own
  measured firing ceiling (R5c §2). Drop rates fall from 0.6–24.0% to 0.0–20.0%
  on tape and no §1 conclusion moves by more than 0.04 in percentile.
- **Facing is a proxy.** The engine carries no facing angle, only a sprite-side
  boolean, so `ang` is measured against the direction of the shooter's previous
  launch and is reported only over shots that changed victim (otherwise a
  repeat pick scores 0 by construction). It is a swing angle, not a turret
  bearing. Its verdict (0.457 against a null of 0.500) agrees with the two
  offset metrics that need no proxy, which is why it is not carrying the §1
  conclusion alone.
- **`perp` needs a threat axis, and the axis is army-level.** Computed
  per-frame from the two centroids. The per-shooter alternative (`perpS`,
  shooter → enemy centroid) is reported alongside because the two can disagree;
  they do not (0.487 vs 0.477).
- **M3's hand-cannoneer rows are not informative about cause.** A speed-0 side
  has essentially constant `adv`, so its correlation with anything is
  meaningless. Only the 2:HCA rows bear on the question. The engine's positive
  correlations are also softened by its near-flat formation (army depth
  1.62–1.97 vs the tape's 2.54–4.26), which compresses the range `assign`
  varies over.
- **M4 is five units per side.** It is an anatomy, not a distribution; the
  population statement is M4b, which uses every unit-step of the fight
  (n = 4,400–5,200 per side per source).
- **M5 is teacher-forced.** Persistence rules see the shooter's real previous
  victim, not their own previous prediction. Free-running would measure error
  accumulation as much as the rule, and teacher forcing is what makes `acc%`
  and the excess distribution two readings of one object. A free-running
  evaluation of the winning candidates is the obvious follow-up if one is
  implemented.
- **M6's rebuild is a lower bound in absolute terms.** hp is read from the
  10 Hz frame at or before the launch and is therefore stale-HIGH, which makes
  coverage harder to trigger: the rebuild's fallback rate averages 8.1% against
  the probe's exact 12.9%. That is why the headline deltas are quoted from the
  probe-anchored columns, which subtract only the exactly-identified failed-roll
  contribution from the engine's own number.
- **Sample sizes.** 1,379 tape launches with a resolvable victim inside reach,
  19–253 per side. The `HCA v HC` archer side, which carries the residual, is
  **164 shots from 17–19 riders**; its lag correlations rest on 100–160 pairs.
  The M2 `covered` regime is 95 tape shots corpus-wide and 8 on the archer
  side — the 75% far rate quoted there is 6 shots and is reported for shape,
  not magnitude.
- **Engine pooling.** Shot-level distributions pool all 20 seeds; M4's unit
  table and M5's engine control use seed 1; M4b and M3's lags average the
  per-seed statistic.
