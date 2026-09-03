# Calibration gap analysis — where the JS engine disagrees with recorded reality

**Date:** 2026-07-30 · **Corpus:** 105 recordings / 92 matchups, real AoE2 fights captured at ~60 Hz
**Scoreboard:** `data/calibration/runs/20260730T113556Z-post-revert.json`
**Method:** every claim below was produced by one analyst and then independently re-derived by a second
analyst instructed to refute it. Where they disagree, both positions are recorded.

---

## 0. Status

| level | result |
|---|---|
| gated metric rows | **3298 MATCH / 756 MISMATCH / 155 INCONCLUSIVE** — 78.4% match |
| fight level (worst gated metric decides) | PASS 6 / MISMATCH 97 / INCONCLUSIVE 2 |
| winner-side rows | 74% match (1447/1946) |
| loser-side rows | 82% match (1851/2263) |

The fight-level number is a harsh rollup — one bad metric out of ~40 condemns a fight. The metric-level
78.4% is the honest measure of how close the engine already is.

**Failure is bimodal, not a uniform fog:** 8 fights have zero gated mismatches and 31 miss ≤3, while 26
miss ≥10 and one misses 23. There is a clean core and a broken tail.

---

## 1. The headline correction: three of the five "gaps" are not engine physics

Two full investigations (18 analysts) converged on the same reframing. Ranked by what the evidence
actually supports:

| # | finding | class | confidence |
|---|---|---|---|
| 1 | **Swing cycle double-counts `attack_delay`** | genuine engine bug, clean fix | high |
| 2 | **"Crowd churn" is mostly recording protocol + contact loss** | not a physics gap | high |
| 3 | **`SWING_EPS = 0.15 s` splits slow-projectile swings** | defect in *our own rig* | high |
| 4 | **19 fights pick the wrong winner; duration is the driver** | engagement model | high |
| 5 | **Fire Lancer fires 3 charge projectiles at one target** | genuine engine bug, one site | high |
| 6 | **Arena geometry** | minor contributor; the obvious fix is *harmful* | high |

---

## 2. Genuine engine defects

### 2.1 The swing cycle adds `attack_delay` on top of the reload — 13 of 14 units

The engine's steady-state cycle is `attack_delay + reload_time + 1 tick`. Reality's is `reload_time`,
flat. Measured excess vs the combat dict's own `attack_delay`, per unit:

| unit | sim excess | dict `attack_delay` |
|---|---|---|
| heavy_cav_archer | 0.800 | 0.767 |
| arbalester | 0.333 | 0.333 |
| heavy_camel | 0.350 | 0.333 |
| imp_elite_skirm | 0.348 | 0.317 |
| hand_cannoneer | 0.342 | 0.250 |
| elite_steppe / paladin | 0.250 | 0.217 |
| elite_elephant / fire_lancer / hussar | 0.200 | 0.167 |
| champion / halberdier | 0.017 | 0.000 |

Residual is 1–2 ticks at dt = 1/60 in every case. **Six units show literally zero spread across all
13–20 of their fight-sides** — this is opponent-invariant, which is the signature of a per-unit
mechanical defect rather than an emergent one.

**Fix:** in `battle_unit.js`, melee path, set `attackCooldown = Math.max(0, reloadTime - attackDelay)`
after `performAttackOn`; route the ranged path through the same committed-windup pattern instead of
`attackCooldown = attackDelay`. `simulation_real.py` already does it this way.

**Measured counterfactual** (over gated `swing_interval_median` *and* `swing_interval_fastest`, 117
mismatches today):

- (A) subtract `attack_delay`: **117 → 110** — median improves, but `fastest` *regresses* 34 → 44
- (A + B1) A plus `+0.16 × reload` for ranged-attacker-vs-melee-target: **117 → 93**, best measured

Ship A and B1 together. The earlier analyst's B2 (a flat +1.62 s/swing melee tax) was measured and makes
things **worse**: 117 → 136, and `swing_interval_fastest` in the affected quadrant 3 → 44.

### 2.2 Fire Lancer charge volley is single-target

`battle_unit.js:596-618` fires all 3 charge projectiles at `this.target`. The tape's victim ceiling for
that unit is exactly 3, consistent with three projectiles hitting three *different* targets. Accounts for
27 metric rows. The `!this.hasUsedCharge` gate should be replaced with the `chargeTimer /
chargeRechargeTime` mechanism already used correctly elsewhere in the same file.

---

## 3. What is NOT an engine physics gap

### 3.1 "Crowd churn" is largely the recording operator

This is the single most important negative result, and it explains why the churn attempt failed.

Counting `interact` + `formFormation` + `unitAiState` commands in each tape's `commands.jsonl`:

- **All 28 both-melee fights: exactly 0.00 micro commands/second**
- All melee-vs-siege fights: 0.00
- **Every fight containing a mobile ranged unit: 2.44–4.49 commands/second**

Across 160 sides, `micro_cmds_per_s` is the **best single predictor of tape churn: ρ = +0.831**, ahead of
duration (+0.579), attack range (+0.433), movement speed (−0.420), and body size (outline_size ρ = −0.066
— essentially zero).

So the "churn quadrants" are precisely the micro'd recordings, and the "metronome quadrants" are precisely
the un-micro'd ones.

**And the melee unit is a metronome when in contact.** In melee-vs-mobile-ranged fights the tape's
`swing_interval_fastest` is **1.00× paper reload** (p10 1.00, median 1.00, p90 1.01 across 45 sides). The
overhead is not slower swinging — it is a heavy-tailed **contact-loss mixture**: gap/reload p25 1.01,
p50 1.40, p75 3.13, p90 7.65, **max 38.8×**. 42% of gaps sit inside 0.9–1.2× and 36% exceed 2×.

That is a unit repeatedly losing contact with a target being actively kited away from it — which is
exactly the group-orbit behaviour described below. It is an *engagement* problem, not a swing-rate one.

**Implication:** do not model churn as a per-swing tax. The reverted `CHURN_MAX` attempt failed because
it was fitting a distributional artifact of operator micro with a mechanism that cannot reproduce it.

### 3.2 The tape fights are sustained group orbits

Measured directly from the 10 Hz position streams — net rotation of each side's centroid about the
enemy centroid:

| recording | net rotation | directional coherence |
|---|---|---|
| `hand_cannoneer__vs__elite_elephant` (shooters) | **+1613°** — 4.5 full revolutions | 96% |
| same fight (elephants) | +1733° — 4.8 revolutions | 95% |
| `champion__vs__heavy_cav_archer` | +370° — 1 revolution | 80% |

Both sides rotate together; the melee side follows. Roughly one revolution per 34 s, sustained.

**The engine cannot do this.** `moveAwayFromTarget` (`battle_unit.js:1447`) computes
`(this.x - target.x, this.y - target.y)` — each unit flees radially from *its own* target, independently.
There is no tangential component and no group coordination anywhere in the engine.

This is the mechanism behind §3.1: an orbiting, micro'd formation stays cohesive and repeatedly breaks
melee contact, producing both the tight formations and the long-tailed swing gaps.

### 3.3 `SWING_EPS = 0.15 s` is a defect in our own extractor

Multi-victim damage delivered by *slow projectiles* arrives spread over more than 0.15 s, so our extractor
splits one swing into several — inflating measured churn for exactly three units.

Re-extracting at `SWING_EPS = 0.60` (applied to tape and sim alike, preserving the one-extractor rule):

| unit | churn at 0.15 | at 0.60 |
|---|---|---|
| siege_onager | 5.306 | **0.582** |
| heavy_scorpion | 2.929 | **0.794** |
| elite_fire_lancer | 1.856 | **0.148** |

The other 11 units are bit-identical. Corpus: **MISMATCH 756 → 726**, `swing_interval_median` 84 → 77,
`churn` 67 → 61. Fight verdicts unchanged.

Crucially, the elephant has **402 multi-victim swings and zero** with span > 0.15 s — its trample really
is instantaneous, so the fix does not disturb the trample results.

Also note: `siege_onager` and `elite_fire_lancer` show *sim-side* churn (0.15–1.54 s and 0.65–0.68 s).
"The engine has zero churn" is true only for melee units — projectile flight time creates real churn for
ranged ones.

### 3.4 Rig defects, not engine defects

`data/calibration/truth/hand_cannoneer__vs__elite_elephant_r2.json` records `swing_count 0` for **both**
sides despite the tape carrying 403 damage events with owners matching the manifest. It is the only such
card in 105 and it alone injects `hits_landed −310` and `damage_dealt −2440` mismatches. Fix before
measuring anything else, so the baseline is honest. Roughly 23 of the 81 trample rows are rig artifacts
of this class.

---

## 4. Arena geometry: real, but the obvious fix is actively harmful

The recordings use a 16×16 arena ~39% obstructed by trees; the sim uses an open 30×20 box.

**The density difference is real and large:** tape formations are **2.44× tighter linearly, 5.95× areally**
(515 side×timepoint rows across all 105 fights). **90.3% of tape nearest-neighbour distances are below the
engine's own collision floor** (`minDist = r₁ + r₂ + 1 px`) — real units pack tighter than the engine
physically permits.

**But it is generated during the fight, not by the map.** Same-side mean nearest-neighbour distance:

| fight progress | tape | sim | ratio |
|---|---|---|---|
| spawn | 1.039 | 1.324 | 1.27× |
| 10% | 0.646 | 1.366 | 2.12× |
| 50% | 0.592 | 1.595 | 2.70× |
| 90% | 0.601 | 2.265 | **3.77×** |

**The tape army compresses 1.73× over the fight; the sim army expands 1.71×.** At spawn the sim's
footprint is actually 3.8× *smaller*. So roughly half the headline gap is the simulator dispersing —
behaviour (pursuit thrash, radial kiting scatter), not geometry.

**The arena counterfactual was actually run, and it fails.** A real 480×480 walled arena (spawn *and*
post-step clamp, all 105 fights):

- density improves only 9–30%, an order of magnitude short of what is needed
- **88 of 105 fights got worse** on duration; median |log₂(sim/tape)| error 0.359 → 0.663
- fights pinned at the 600 s cap went 3 → 5
- `hand_cannoneer__vs__elite_elephant` **283 s → 575 s** against a 152 s tape

Walls do not force engagement — the kiters simply orbit inside the box.

**And the radius-shrink proposal cancels itself.** Trample reach is `attacker.radius + trample_radius +
victim.radius`, so shrinking radii by 0.43× cuts the swept area 66%. Measured across four modes
(base / walled-16 / small-radius / small-radius + packed spawn), the paired median error on
`trample_victims_max` is **3.000 in all four** — literally unchanged. The density gain and the reach loss
cancel exactly.

**Verdict: GEOMETRY IS A MINOR CONTRIBUTOR.** Do not change the arena.

---

## 5. The 19 winner flips — and a reason to revisit the reverted pursuit fix

In **19 of 105 fights the engine picks the opposite winner**. No tolerance rule can rescue those (winner
`hp_remaining` matches 0/19). They account for 56% of the winner/loser asymmetry, which is therefore *not*
purely a tolerance artifact.

The driver is **fight duration**, which the scorer currently does not gate: 74 of 105 fights are off by
>15%, correlating 0.636 with loser damage error. Duration ratio by class: melee-melee 0.72,
ranged-ranged 0.69, melee-ranged 1.14 — and duration predicts the error *within* each class too
(ρ = +0.53 to +0.88), so class is a proxy and duration is the cause.

**Important:** the reverted pursuit-fit run (`20260730T112941Z`) **fixes 14 of the 19 winner flips**,
including **all six** `siege_onager` flips, with no splash-model change at all. That is a materially
stronger result than the corpus rollup I reverted it on, and it means the revert decision should be
re-examined against winner-flip count rather than aggregate mismatch count.

---

## 6. Recommended order

Rig fixes first — they are free, carry zero engine risk, and make every subsequent measurement honest.

1. **Quarantine / re-ingest the zeroed truth card** (`hand_cannoneer__vs__elite_elephant_r2`).
2. **Raise `SWING_EPS` to ~0.60** in the extractor. Corpus 756 → 726 for free.
3. **Emit `duration_s` as a scored diagnostic**, plus `tol_z = |delta|/tolerance` and a degenerate-band
   flag, so future changes are judged on effect size rather than a binary.
4. **Fix the `attack_delay` double-count** (A + B1 together). Measured 117 → 93.
5. **Fix the Fire Lancer charge volley.** One site, 27 rows, highest confidence in the corpus.
6. **Re-examine the pursuit revert against winner flips** (14/19) rather than aggregate mismatches.
7. **Do not** ship a churn tax, and **do not** change the arena. Both were measured; both make it worse.

Every step lands alone with a before/after scoreboard. The churn and pursuit history is the reason:
bundled changes cannot be attributed, and two plausible mechanisms have already measured worse than
doing nothing.

---

## 7. What remains genuinely unexplained

- **Group orbiting.** The engine has no tangential kiting or group coordination. Whether to model it is a
  judgment call: it may be an artifact of the recording operator's micro rather than emergent AoE2
  behaviour, in which case calibrating to it would fit the harness instead of the game. **This needs a
  decision before any engagement-model work.**
- **Trample spatial overdispersion.** Tape variance-to-mean ratio 1.64 vs sim 0.95 at matched λ — real
  formations clump unevenly in a way uniform density cannot reproduce.
- **Effective accuracy mechanism is under-identified.** Self-rehit and full-damage neighbour graze are
  indistinguishable in this data and both are real AoE2 mechanics. The size-law correlation weakens from
  r = +0.908 to +0.498 when all 13 fights are used instead of a hand-picked 9.
