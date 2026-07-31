# E2 — What law sets the tape kiter's orbit radius? (tape-only measurement)

**Question.** The JS engine's composed kite-escape stack (E1 orbit + C3 plant +
C4 run-commitment) leaves one ranged deficit: the engine orbit balloons
(+0.077 tiles/s outward, 1.1–1.6 tiles wider than tape) while the tape holds or
shrinks radius (−0.030 t/s, 4.0 → 2.7 over a fight). This report measures what
actually controls the tape kiter's standoff, so the engine waypoint law can be
grounded in dat values or a measured tape breakpoint — no fitted constants.

**Corpus.** The 78-fight E1 kite corpus (ranged non-siege vs melee) plus
heavy_cav_archer__vs__paladin r2–r5 = **82 tapes**, all parsed (0 errors).
Conventions (fight center C, θ sign, 10 Hz frames) are identical to
`docs/calibration/e1_kite_orbit_tapes.md`. Machine-readable per-tape metrics:
`data/calibration/analysis/e2_orbit_radius_law.json`.

Dat inputs (data/calibration/combat_dicts.json): arbalester range 8, speed
0.96, coll 0.2; hand_cannoneer 7 / 0.96 / 0.2; heavy_cav_archer 7 / 1.54 /
0.25. Melee collision sizes 0.2–0.25 → pairwise collision-contact (sum of
sizes) is 0.40–0.50 tiles.

## Q1 — The radius predictor: nothing tracks weapon range; the control variable is nearest-enemy distance with a ~4.4-tile breakpoint

At every kiter fire event (volley-collapsed missiles, firing unit located in
the frame): r(center), distance to nearest living enemy, distance to enemy
centroid, and — via attacker-matched damage events — distance to the actual
target.

| kiter | n | range | at-fire d(nearest) mean / slope / det-std | at-fire r(center) mean / slope / det-std | at-fire d(enemy centroid) | at-fire d(target) mean / p90 |
|---|---|---|---|---|---|---|
| arbalester | 23 | 8 | **2.12** / −0.065 / 1.21 | 4.08 / −0.053 / 1.42 | 3.39 / −0.105 / 1.33 | 2.13 / 3.84 |
| hand_cannoneer | 24 | 7 | **1.70** / −0.034 / 1.14 | 3.84 / −0.018 / 1.41 | 2.96 / −0.067 / 1.16 | 1.78 / 2.99 |
| heavy_cav_archer | 35 | 7 | **1.65** / −0.048 / 1.03 | 4.34 / −0.028 / 1.25 | 2.81 / −0.090 / 1.11 | 1.79 / 3.30 |

- **The tape kiter does NOT fire at max range.** Mean at-fire distance to the
  actual target is 1.8–2.1 tiles ≈ 25 % of max range (p90 3.0–3.8; only the
  max approaches dat range). "Keep nearest enemy at own range" is falsified.
- **d(nearest enemy) is the most stationary series** — lower detrended std
  than r(center) in 72/82 tapes (corpus mean 1.11 vs 1.35 tiles). Neither is
  truly flat within a fight; all three drift slowly inward.
- **Across 82 tapes:** corr(at-fire d_nearest, own range) = **0.70** (weak
  range tracking: +1 range ⇒ ~+0.45 tiles), corr with enemy speed = **0.00**.
  r(center) has NO range dependence (−0.08); its between-tape mean is
  **4.12 ± 0.31** — pinned at the spawn half-separation (~4.0) in every fight
  regardless of who is fighting. **Orbit radius is emergent from spawn
  geometry, not a controlled quantity.**

**The actual law appears in the approach/retreat breakpoint.** Binning every
moving kiter-unit frame (speed > 0.15 t/s, velocity over 0.3 s) by
nearest-enemy distance and measuring the velocity component toward that enemy:

| d(nearest) bin | arb P(toward) / v_rad | HC P(toward) / v_rad | HCA P(toward) / v_rad |
|---|---|---|---|
| 1–2 | 0.12 / −0.52 | 0.10 / −0.58 | 0.13 / −0.67 |
| 3–4 | 0.15 / −0.41 | 0.23 / −0.33 | 0.20 / −0.50 |
| 4–5 | 0.31 / −0.16 | 0.58 / +0.19 | 0.49 / −0.00 |
| 5–6 | 0.71 / +0.30 | 0.87 / +0.56 | 0.83 / +0.52 |
| 6–7 | 0.97 / +0.60 | 0.99 / +0.77 | 0.87 / +0.60 |
| 7–8 | 0.98 / +0.66 | 1.00 / +0.75 | 0.92 / +0.79 |

Zero-crossing of mean radial velocity (0.5-tile bins,
`crossover_fine` in the JSON): **arbalester 4.77, hand_cannoneer 4.09,
heavy_cav_archer 4.45 tiles** (per-enemy spread 3.1–5.4 across 19 pairs with
data). Beyond the crossover the kiter drives **toward** the enemy at 0.5–0.8
t/s (most of its move speed); inside ~3.5 it retreats hard. The crossover is
NOT threat-scaled — slow elephants (0.99 t/s) get the *widest* standoff
(5.4 / 4.7 for foot kiters) and fast hussars the narrowest — and it sits far
inside weapon range. The class ordering matches range (8 → 4.8 vs 7 → 4.1–4.5,
≈ 0.6 × range, or range − 3), but neither dat expression is clean; treat
**d\* ≈ 4.4 tiles (per-class 4.8 / 4.1 / 4.5)** as a measured tape breakpoint.

## Q2 — What makes tape r shrink 4.0 → 2.7: the kiter cuts inside

Decomposition of the kiter-centroid radius change (movement of the common
alive set vs composition jumps at deaths, summed over the fight):

| kiter | total mvmt part (tiles) | death-jump part | enemy-centroid→C slope (t/s) | mean per-unit radial vel (t/s) |
|---|---|---|---|---|
| arbalester | **−2.29** | +0.45 | +0.030 | −0.056 |
| hand_cannoneer | **−0.79** | +0.35 | +0.009 | −0.016 |
| heavy_cav_archer | **−1.57** | +0.37 | +0.008 | −0.026 |

- The shrink is **active inward movement** of the kiter units.
- Deaths shift the centroid **outward** (+0.35..0.45 total): the units that die
  are the ones caught *inside* — the composition effect fights the shrink,
  it doesn't cause it.
- The fight center does not drift toward the kiter: the enemy centroid drifts
  slightly *away* from C (+0.008..+0.030 t/s).

This is exactly what the Q1 law predicts: as the melee blob thins, more
kiter units see d(nearest) > d\* more often and advance, ratcheting the ring
inward.

## Q3 — The outward-force question: tape kiters brush through at collision contact

"Blocked" frame = the enemy centroid lies in the corridor between the kiter
centroid and C (projection 0.05–0.95, perpendicular < 1.5 tiles) — the worst
case for staying tight. Response measured over the following 3 s:

| kiter | blocked frames | blocked Δr(3s) | free Δr(3s) | blocked pushthrough (minpair < coll+0.125) | blocked within-1-tile | all-frames minpair p5 | frames minpair < coll+0.125 |
|---|---|---|---|---|---|---|---|
| arbalester | 18 % | **+0.54** | −0.23 | **0.74** | 0.91 | 0.44 | 18 % |
| hand_cannoneer | 29 % | **+0.78** | −0.27 | **0.78** | 0.96 | 0.42 | 24 % |
| heavy_cav_archer | 29 % | **+0.21** | −0.14 | **0.91** | 0.98 | 0.40 | 47 % |

- **Yes, tape kiters move into overlap-band range.** The 5th percentile of the
  per-frame min kiter↔enemy body distance is 0.40–0.44 tiles — right at the
  sum of collision sizes. For HCA, 47 % of ALL frames have some kiter within
  collision contact +0.125 of an enemy body; 60–80 % of frames within 1 tile.
- **Blocked arcs cause a temporary widen, not a balloon:** +0.2..+0.8 tiles
  over 3 s, and in 74–91 % of those same windows the kiter ALSO passes within
  collision-contact clearance of an enemy body (it climbs over the blob edge,
  brushing through the gap). Un-blocked windows re-tighten (−0.14..−0.27).
- The oscillation is bounded and mean-reverting; the engine's failure mode —
  converting each block into a permanent radius gain — does not exist in the
  tapes. Engine avoidance clearance (untouched by E1) forcing wider detours
  than collision-contact is consistent with being the ballooning mechanism.

## Q4 — champ_vs_HCA (9 tapes) + hca_vs_paladin (5 tapes) catch anatomy

Ground truth: **HCA beats champions 8/9** (HCA survivors 0, 9, 7, 9, 3, 10, 8,
9, 11 of 12) but champions always land substantial damage: **379–960 dmg
(median ~526), 30–84 hits, 1–12 HCA killed (median 3)**. Paladins beat HCA
5/5, killing all 21 HCA every round (1680 dmg) with 9–12 of 15 surviving.

- **Contact is continuous, not episodic:** 1–4 melee-damage episodes spanning
  the whole fight; damage share by fight quarter ≈ [0.10, 0.30, 0.35, 0.25] —
  champions are landing hits from the first quarter on.
- **Catches happen mid-field, not at walls:** melee hits land at mean r
  3.1–4.1 tiles from C, mean distance to the usable-area edge 2.3–2.9 tiles;
  only ~15–30 % (max 50 %) of hits within 2 tiles of the wall.
- **The tape HCA ball balloons early, then cuts hard inside:** HCA centroid
  radius trace (0/25/50/75/100 % of fight) ≈ 3.8 → **5.5** → ~4.5 → **~2** →
  varies. In hca_vs_paladin r4/r5 the mid-fight radius collapses to **0.9** —
  the ball rides straight through the center across paladin-held ground.
- **Mechanism the engine's wide orbit removes:** champions (1.06 t/s) can
  never run down a 1.54 t/s HCA ball on an expanding orbit. In the tapes the
  catch windows are created by the HCA *itself* returning inside d\* ≈ 4.5 —
  every inward cut drags the ball across the champion blob at collision-contact
  clearance (Q3), which is where all the melee damage lands. A widening engine
  orbit deletes every one of those windows, which is precisely the gated
  deficit.

## Q5 — Ranked zero-constant waypoint-law candidates

1. **Nearest-enemy setpoint band (advance-to-threat).** Orbit waypoint =
   tangential step (E1 unchanged) + radial bias: **inward/toward nearest enemy
   when d(nearest) > d\*, tangential-or-outward when below**, with
   d\* = the measured tape breakpoint **4.4 tiles global (per-class 4.8 / 4.1 /
   4.5; ≈ 0.6 × own dat range)**. No gains to fit — the radial component is
   the unit's normal move speed, as measured (+0.5..0.8 t/s beyond d\*).
   *Predicts:* d(nearest) stationary (the observed most-stationary series),
   r-slope ≤ 0 (shrink emerges as the enemy thins, Q2), continuous champion
   contact in champ_vs_HCA (Q4). *Risk:* foot families currently at tape
   geometry with C4 — the law is inactive unless d(nearest) exceeds d\*, which
   is exactly (and only) the engine's balloon regime, so it should not disturb
   them.
2. **Cap waypoint radius at spawn radius** (r of the kiter centroid at the
   first both-sides frame). Purely from the fight's own geometry — tape
   between-tape at-fire r(center) is 4.12 ± 0.31, i.e. the tape never exceeds
   spawn radius on average. *Predicts:* eliminates the +0.077 t/s balloon
   outright; does NOT reproduce the inward cut to r ≈ 2 on its own, so
   champ_vs_HCA catch share improves but may stay short of tape. *Risk:*
   minimal; combines cleanly with #1 as a guard.
3. **Radius ratchet — r ≤ r at last fire.** Zero constants, but at-fire
   r(center) has a within-fight std of 1.35 tiles: the ratchet locks onto
   noise lows, over-tightens, and forbids the real, measured 3-s blocked
   widen (+0.2..+0.8, Q3). Rank below the cap.
4. **Keep nearest enemy at own max range (pure dat).** **Rejected by
   measurement:** the tape fires at ~25 % of max range, tolerates enemies at
   collision contact (minpair p5 ≈ coll sum), and its standoff is ~4.4 tiles
   for both 7- and 8-range kiters. This law predicts an equilibrium radius of
   range + enemy blob radius ≈ 8–9 tiles — it *reproduces the balloon*.

**Companion finding for implementation:** whatever the waypoint law, the
engine must also allow orbit passes at collision-contact clearance (Q3);
avoidance that enforces >0.5-tile clearance around enemy bodies will convert
blocked arcs into permanent widening regardless of the waypoint.

---
Scratch scripts: `e2_orbit_radius_law.py`, `e2_v2_target_breakpoint.py`,
`e2_v3_crossover.py` (session scratchpad). Data:
`data/calibration/analysis/e2_orbit_radius_law.json` (per-tape q1/q2/q3,
per-tape `breakpoint` bins, `crossover_fine` per pair, q4 anatomy for the 14
champ/paladin tapes, `aggregates_by_kiter`, `verdicts`).
