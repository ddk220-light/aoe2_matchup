# Clean-room sim — calibration status, 2026-08-05

Branch `codex/cleanroom-champion-sim`. Continues
`CLEANROOM_CHAMPION_HANDOFF_2026-08-05.md`.

## Headline

The engine now runs **three** unit sets, and every sourced constant transferred
with no retuning. The one remaining outlier (champion_vs_paladin 6v3) has been
isolated to the initial acquisition order, which is engine RNG a deterministic
simulator cannot reproduce. Combat math, movement, collision and retargeting
are each independently exonerated.

## Data sets in use

| archive | fights | role |
|---|---|---|
| `championvschampion` (calibration/source) | 15 | original calibration set |
| `paladinvspaladin` (~/Downloads) | 15 | second unit, holdout |
| `championvspaladin_..._complete (2)` (~/Downloads) | 92 | asymmetric holdout, 26 ratios |

The champion-vs-paladin fixture carries all 92 fights across 26 ratios
(sha256 `90F8588D…1DCAC`), spanning 0.50:1 to 5.00:1 and 2 to 40 units. The ten
ratios added by this archive deliberately probe far from break-even (15v4 at
3.75:1, 20v5 at 4.00:1, 10v2 at 5.00:1) and large near-even fights (10v10,
15v15, 20v20, 20v18, 20v15, 15v20, 10v20).

No camel recordings exist. The recorded pairs are champion, paladin, elephant,
firelancer and steppe (Steppe Lancer).

## Constants — all sourced, confirmed on two units

| | Champion (Chinese 567) | Paladin (Spanish 569) |
|---|---|---|
| half-extent | 0.20 | 0.25 |
| `min_collision_size_multiplier` | 0.80 | 0.50 |
| `frame_delay` | 0 | 13 |
| speed: fixture → tape | 1.056 → 1.056 | 1.485 → 1.48503 |
| attack delay: rule → tape floor | 0.750 → 0.750 | 0.672 → 0.672 |
| reload: dat → tape floor | 2.000 → 2.020 | 1.900 → 1.918 |

Reload and cadence differ from the dat by exactly one render frame (~17 ms) on
BOTH units — sampling lag, not a rate error.

**Attack delay rule.** The hit lands on animation frame `frame_delay`, i.e.
`anim_seconds * frame_delay / frame_count`. `frame_delay == 0` is an UNSET
sentinel where the engine uses the animation midpoint. The split is on
frame_delay, NOT melee-vs-ranged (the Paladin is melee with frame_delay 13).
**`ref_units.final_attack_delay` is wrong** — it stores `frame_delay/60`
(0.217 s for the Paladin), which the tape rules out by 3x. This affects the
production engines too, not just the clean-room one.

**Speeds** must come from `ref_stat_chain` (last step); `ref_units.final_speed`
is rounded to 2 decimals at `aoe2x/dbgen/generate_reference.py:1027`.

**Acquisition lag** is an ENGINE property, not a unit stat: pooled over both
units (n=162) it is Uniform[0.952, 1.708] s, with the two units agreeing on the
endpoints to within 4 ms. Within a fight the per-unit delays are the ORDER
STATISTICS of that range, modelled as `min + i/(n+1) * (max - min)`; checked
against 53 real acquisitions, mean absolute error 0.058 s.

**Collision.** Genie obstruction is an axis-aligned BOX, so separation is
Chebyshev. Enemy pairs never close below the sum of half-extents (0.400 / 0.500
respectively), undershooting by exactly one frame of travel. Allies are NOT a
hard constraint: they rest inside the full box in 6-7% of samples and a moving
unit can push through a stationary friendly. NOTE a 2018 richg42 dev blog says
units use circular obstructions — the tapes contradict that for AoE2:DE melee
units. Do not "correct" this back from the blog.

## The game stops reproducing itself NEAR BREAK-EVEN, not at scale

Every repeat of a ratio starts from byte-identical positions, so the spread
across repeats is the GAME's own nondeterminism. An earlier version of this
document blamed fight SIZE. The 92-fight archive refutes that outright:

| ratio | units | C:P | winner-HP spread | side |
|---|---|---|---|---|
| 8v4 | 12 | 2.00 | **94.2%** | **FLIPS** |
| 10v5 | 15 | 2.00 | 75.4% | **FLIPS** |
| 21v10 | 31 | 2.10 | 92.7% | **FLIPS** |
| 20v15 | 35 | 1.33 | 12.0% | fixed |
| 15v15 | 30 | 1.00 | 8.6% | fixed |
| 20v18 | 38 | 1.11 | 10.7% | fixed |
| 20v20 | **40** | 1.00 | **14.1%** | fixed |

40 units at 1.00:1 is six times more reproducible than 12 units at 2.00:1. The
driver is proximity to break-even (2.00:1), where the first concentrated
engagement compounds and decides the fight. Away from it the game is nearly
deterministic at any size — 15v4, 20v5 and 10v2 spread only 2.0-4.9%.

**Near 2:1, comparing one sim run to one tape number is meaningless.** The sim
has to match a distribution; see the sampler below.

## Scorecard

Champion mirror ratio gates: 18 pass / 0 fail. Suite: 112 pass / 27 fail.

champion_vs_paladin, one deterministic sim run per ratio scored against the
per-ratio tape band: **36/48 checks inside, winner side 15/16.**

**3v2 is the one defect outside any RNG excuse — off by exactly one champion
swing.** The tape returns 178 HP and 29 hits in all three repeats, zero
variance; the sim returns 191 and 28. Five units, fully deterministic on both
sides. The cleanest target in the set.

**15v8 is NOT a systematic defect** — corrected below under sampling. Scored as
a single run it looks like the only wrong winner, but sampling acquisition
orders shows champions win it in just 3% of orders and the sim's median margin
sits inside the tape band. Ranking acquisition by reference id simply drew an
atypical order. The same correction applies to the earlier 21v10 reading.

Decomposing damage by side (champion HP lost = how hard paladins hit, and
vice versa) isolates the direction — deltas are HP outside the band, 0 = inside:

| ratio | champions over-hit by | paladins under-hit by |
|---|---|---|
| 6v3 | 0 | **-84** |
| 9v4 | 0 | **-42** |
| 15v8 | **+265** | **-56** |
| 15v10 | **+191** | 0 |
| 8v4 / 10v5 / 11v4 / 21v10 | 0 | 0 |

No ratio errs the other way: champions never under-hit and paladins never
over-hit. The bias is one-directional.

Contact share explains the two 15-champion fights. Counting, per frame with
both sides alive, the fraction of LIVE champions inside swing reach:

| ratio | tape | sim |
|---|---|---|
| 9v4 | 63.5% | 71.4% |
| 15v8 | 70.7% | **82.9%** |
| 15v10 | 63.7% | **80.5%** |
| 10v5 | 79.2% | 77.8% |
| 21v10 | 60.9% | 56.9% |

The game keeps roughly one champion in three out of contact in a big fight;
our engine keeps only one in five. Exactly the three ratios where the sim lets
a larger share engage (9v4, 15v8, 15v10) are the three where champions
over-hit, and the ratios whose shares match score inside band. That is
correlation across six ratios with one sim run each, not proof — but it names a
concrete mechanism (surround capacity / screening) and a concrete test.

6v3 is NOT this mechanism: its sim contact share is *lower* than the tape
(78.0% vs 85.2%), and it was already isolated to acquisition order below.

Last death is early in the small ratios by 0.05-0.31 s — a uniform residual not
yet chased. In the big fights the sim instead runs long (15v8 45.8 s against a
25.0-34.4 s band; 15v10 34.7 s against 20.7-24.5 s).

## Break-even sits at 2.00:1, and that is where the game stops agreeing with itself

Margin (winner HP as a share of the winner's own starting pool) collapses
monotonically as the champion:paladin ratio climbs toward 2.00 and rises again
past it. All three ratios whose winning side FLIPS between repeats sit at
2.00-2.10, and the two non-flipping 2.00 ratios are razor thin (2v1 paladins by
13.3%, 6v3 champions by 3.3-6.7%). Near the knife edge whoever lands the first
concentrated engagement compounds it, exactly the Lanchester picture.

That gives a one-number statement of the residual bias: **the game's break-even
is 2.00:1, ours is nearer 1.85:1.** Below 1.5:1 the sim is exact on five ratios
(1v1, 1v2, 2v3, 3v5, 3v6, plus 2v1 at 2.00). From 1.5:1 up it favours champions
on every ratio but 3v2.

## What varies between repeats: the opening target assignment

Starts are byte-identical, so the whole delta is WHO acquires first and WHOM
they pick. In 8v4 the paladins' opening concentration alone predicts the flip:

| repeats | paladins double up on | result |
|---|---|---|
| r1, r2, r5 | 2 champions | paladins win by 19.0-26.2% |
| r3, r4 | 1 champion | paladins by 1.5%, then champions by 15.0% |

Concentration is not the whole story: 10v5 r3 and r4 have identical paladin
opening maps and still diverge, because the CHAMPION assignment differs (r3
piles 6 of 10 onto one paladin, r4 spreads 4/2/1/3). Both sides' opening maps
matter.

## Sampling acquisition orders

`tools/sample_acquisition_orders.mjs --ratio 8v4 --samples 200` permutes the
acquisition rank, which permutes who moves first, hence who is nearest when the
next unit acquires, hence the opening targets. Seeded and reproducible; sample 0
is always the identity order, i.e. today's deterministic answer.

Three sampled orders on one 8v4 start bracket the tape's five repeats, and one
lands on `8v4_r3` exactly (paladins by 1.5%, 11 HP):

| | opening | result |
|---|---|---|
| sim run 1 | paladins double up once | paladins by 18.8% |
| sim run 2 | paladins double up twice | paladins by 1.5%, 11 HP |
| sim run 3 | as run 2, champions on 3 paladins | champions by 17.5% |
| tape | five repeats | -26.2, -19.3, -19.0, -1.5, +15.0 |

Scored as distributions (60 orders, 40 for the big ratios), the DISPERSION is
broadly right and the CENTRE is what is biased:

| ratio | sim median | tape range | median in band | orders in band |
|---|---|---|---|---|
| 3v2 | -53.1 | -49.4 | no, paladin-side | 18% |
| 5v3 | -37.4 | -44.6 … -40.2 | no, champion-side | 15% |
| 6v3 | +13.3 | +3.3 … +6.7 | no, champion-side | 5% |
| 8v4 | +7.5 | -26.3 … +15.0 | **yes** | 78% |
| 9v4 | +33.3 | +15.6 … +26.7 | no, champion-side | 18% |
| 10v5 | +6.0 | -25.3 … +8.0 | **yes** | 52% |
| 11v4 | +52.7 | +41.8 … +54.5 | **yes** | 72% |
| 15v8 | -24.7 | -46.9 … -18.4 | **yes** | 73% |
| 15v10 | -47.6 | -66.1 … -53.3 | no, champion-side | 18% |
| 21v10 | -21.2 | -36.8 … +13.3 | **yes** | 93% |

Five of ten medians land inside the tape band. The residual champion bias is
real and one-directional in 5v3, 6v3, 9v4 and 15v10; 3v2 is the lone opposite
case and is the one-swing bug.

## ROOT CAUSE: our units never voluntarily change target

Chased on the lopsided ratios, where one side clearly wins and there is no RNG
to hide behind, so any delta must be mechanical.

On those ratios the losing side is wiped in both tape and sim, so the whole
delta is how much damage the losers landed before dying, and that factors as
`time alive x damage per second alive`. Our losing champions do NOT live too
long — they live 5-40% LESS. They deal 28-46% more damage per second alive.

The time budget over each champion's own lifetime says where that comes from:

| ratio | attacking (tape → sim) | moving (tape → sim) |
|---|---|---|
| 10v10 | 48.8% → 74.3% | 39.8% → **14.5%** |
| 20v18 | 43.7% → 58.7% | 46.3% → **22.6%** |
| 20v15 | 44.3% → 59.5% | 46.1% → **19.4%** |
| 15v10 | 47.1% → 70.2% | 43.5% → **20.6%** |
| 20v20 | 45.6% → 56.6% | 45.9% → **23.8%** |

**The game's units spend 40-46% of a fight walking. Ours spend 14-24%.** The
deficit is -22 to -27 points on every large ratio and it converts almost
one-for-one into attacking time. Paladins show the same gap (tape 35-54%
moving, sim 28-34%), measured over the fight window — measuring it over a
survivor's full trace instead is an artifact, since the recording keeps running
after the fight and the idle tail swamps everything.

Why they walk: **the game switches targets while the old target is still
alive.** Splitting every switch by whether the abandoned target was still
alive:

| ratio | tape voluntary | sim voluntary |
|---|---|---|
| 10v10 | 43.5% | **0.0%** |
| 20v18 | 37.3% | 4.8% |
| 20v15 | 30.9% | 2.1% |
| 15v10 | 43.5% | 8.9% |
| 20v20 | 30.9% | 2.5% |

31-44% of the game's target switches are voluntary; ours are 0-9% and only on
the small ratios. The cause is explicit in `selectPursuitTarget`
(`src/combat/targeting.js`): once `pursuitTargetId` is set it is returned
unconditionally while the target lives, so our units re-evaluate only on a
kill. They lock on, plant, and grind.

**What the switch rule is NOT.** Tested on 217 voluntary switches: not nearest
(60% move to a FARTHER target, median +0.25 tiles), not focus-fire (median
target-HP change 0), not crowd relief (31% pick a less crowded target, 32% more
crowded), not retaliation (14% pick a unit attacking them against a 12% control
for the target they just left). No measurable preference on any axis.

**It is NOT a rate.** An earlier version of this section modelled it as one
voluntary retarget per ~16 s of engaged time. That was an artifact of a
large-fight-heavy sample. Measured across all 122 recorded fights the rate
scales with DENSITY — per-fight correlation with unit count **+0.83**:

| units | fights | switches | per unit-sec | 1 per |
|---|---|---|---|---|
| 2-4 | 21 | **0** | 0.0000 | never |
| 5-9 | 36 | 62 | 0.0204 | 49.0 s |
| 10-15 | 23 | 152 | 0.0306 | 32.7 s |
| 16-25 | 19 | 386 | 0.0560 | 17.9 s |
| 26-40 | 23 | 885 | 0.0631 | 15.9 s |

Small fights never voluntarily retarget at all, so no timer is involved.
Re-evaluation is CONTINUOUS: hold-time before a switch is a smooth unimodal
distribution peaking at 1.25-1.50 s with no periodicity (a Rayleigh sweep over
0.2-4.0 s finds only the trivial monotonic artifact), which is what a
continuously-evaluated condition on a churning melee produces.

Two more facts constrain the rule. Switches happen at **96.8% of maximum move
speed** — the same as the baseline moving frame, so units are NOT stuck when
they switch. And 54% of switches abandon a target the unit never once reached
(median hold 1.43 s, median closest approach 0.56 tiles against a 0.1 contact
threshold), while the other 46% happen a median of **0.02 s** after a swing
lands. All of this replicates in the champion and paladin MIRROR archives.

**The choice rule is still unknown.** Tested on 1485 switches across 122
fights, every candidate fails:

| candidate rule | result |
|---|---|
| nearest by straight line | 40% |
| nearest by PATH (grid A* around bodies) | 45% |
| old target unreachable | 6% |
| path-detour threshold | old 1.19 vs new 1.19 — identical |
| nearest with a free slot (any K) | flat 33% |
| focus the wounded | median target-HP change 0 |
| retaliation (new target attacking me) | 14% vs a 12% control |
| copy a nearby ally's target | 0.98x chance |
| fixed timer | no periodicity; zero switches in small fights |

**A second, independent blocker.** Even granting continuous re-evaluation, our
engine cannot reproduce the walking: `moveUnits` refuses to move any unit whose
action is `attacking`, and `selectEngagementTarget` retains `engagedTargetId`
while that target is alive and in reach. An engaged unit is therefore pinned
regardless of its pursuit target, where the tape shows units walking away
0.02 s after a swing. Experiment: removing only the pursuit lock (re-evaluate
nearest every tick, no new constants) halved the 10v10 attacking-share error
(+25.5 → +11.6 pt) but left the big fights near 22% moving against the tape's
46%, and outcome deltas were a wash — four ratios better, four worse. Reverted;
engagement pinning has to be addressed too.

## Error by ratio band — the sim is worst exactly where the game is

Winner HP remaining as a share of that side's own starting pool, sim median
(sampled orders) against tape median, over all 26 ratios:

| band | ratios | mean abs error | worst |
|---|---|---|---|
| paladin-dominant ≤1.00:1 | 10 | **1.3 pts** | 15v20, 4.8 |
| contested 1.11-1.50:1 | 4 | 6.9 pts | 15v10, 10.4 |
| knife edge 1.67-2.25:1 | 8 | **7.1 pts** | 9v4, 13.3 |
| champion-dominant ≥2.75:1 | 4 | 3.8 pts | 15v4, 6.7 |

Error tracks contestedness, not size. Six ratios are exact to the decimal and
all are decided by raw stats before geometry can matter; 10v2 (5.00:1, 12
units) is exact too. The error concentrates in the band where the game's own
repeats disagree most.

The ten ratios added by this archive average 3.7 pts against 4.8 for the
sixteen analysed before — better, because they were chosen away from the knife
edge, which is the prediction that motivated recording them. But the effect is
not uniform: 10v2 lands exact and 20v5 within 3.0, while 15v4 is off by 6.7 and
20v18 by 9.1. Being far from break-even helps; it does not by itself make a
ratio accurate.

**21v10: 11 of 40 orders never resolve inside the engine's 3600-tick (60 s)
guard.** The game settles every recorded 21v10 in 30.7-45.2 s. Runaway fights on
particular opening assignments are a defect in their own right; the tool counts
and excludes them rather than raising the cap.

## The 6v3 outlier — isolated, twice

1. `tools/pure_combat_math.py` — feeding the tape's own swing times and targets
   into nothing but our damage and windup rules reproduces the tape exactly:
   all 9 death times within 0.02 s, survivor on 14 HP. **Combat math is right.**
2. `tools/replay_tape_acquisition.mjs` — feeding each unit the tape's measured
   acquisition time and changing nothing else:

   | | winner | HP | survivors | hits |
   |---|---|---|---|---|
   | baseline | P2 | 112 | 3 | 64 |
   | tape acquisition | P2 | **14** | **1** | **71** |
   | TAPE | P2 | **14** | **1** | **71** |

   Same survivor unit, same HP. **Movement, collision and retargeting are right.**

The whole 98 HP miss is the acquisition ORDER. Ranking by reference ID makes the
lowest-ID unit always move first, changing who is nearest when later units
acquire, and so who fights whom. The tape's order is RNG (r1 starts 1633, r2
1631, r3 1633).

Ruled out along the way, each with measurements: attack rate (1% = one frame, on
both units), damage per hit (identical distributions including the partial 11s),
champion engagement count (45 swings in both), engagement capacity (+0.2-0.4
attackers, conditioned properly), and the initial target rule (nearest-enemy is
correct wherever geometry decides it).

## Open

- **Implement voluntary retargeting** — the fix for the root cause above, and
  the only change that plausibly closes the whole >4 pt band at once. Design:
  re-evaluate a live pursuit target at ~0.062/s per engaged unit and reselect
  among reachable enemies. Two decisions needed first. (1) The choice is
  unbiased on every axis measured, so it needs an RNG draw, which makes the
  engine stochastic — it should share the seeded sampling already used by
  `tools/sample_acquisition_orders.mjs` rather than introduce a second source.
  (2) It changes every calibration number and requires re-capturing the golden
  baseline. NOT started; needs sign-off.
- **Screening / surround capacity** — earlier lead from the 62-fight set: the
  game holds ~1 champion in 3 out of contact in big fights, we hold ~1 in 5.
  Now believed to be a SYMPTOM of the missing voluntary retargeting rather than
  an independent mechanism — units that never leave a target never vacate a
  slot. Re-test after the retargeting fix before chasing it separately.
- **3v2, off by one champion swing.** Deterministic on both sides, five units.
  Should be debuggable to a single tick.
- **Distributional scoring.** Acquisition order has no structure (checked on the
  interim set: rank spreads match random expectation), so no deterministic
  ordering is correct. Above ~8 units the game's own spread reaches 75-94% and
  the winning side flips, so the sim must be sampled over several acquisition
  orders and compared as a distribution. The band gates are the right shape;
  single runs against them are a smoke test, not a gate.
- **The uniform ~0.2 s early bias** on last-death across all nine ratios.
- **27 failing tests.** Mostly the same stale-model class already found in the
  validator: they assert circular geometry and instant damage, both refuted.
  Triage before treating them as defects.
- **The matchup playback path does not run the strict validator** the champion
  path does. Deliberate, to ship the viewer; worth wiring up.

## Tools added

`export_unit_mechanics.py` (any unit/civ/master), `decode_tape_frames.py`
(any archive), `measure_tape_mechanics.py`, `measure_blocked_movement.py`,
`compare_target_assignment.py`, `pure_combat_math.py`, `run_unit_tapes.mjs`,
`run_matchup_tapes.mjs`, `replay_tape_acquisition.mjs`,
`dump_matchup_trace.mjs`.

Viewer: matchup dropdown (champion mirror + champion_vs_paladin, 9 ratios) and
a **Top-down 2D** projection toggle — the isometric view halves the y axis, so
overlap and obstruction cannot be read honestly from it.
