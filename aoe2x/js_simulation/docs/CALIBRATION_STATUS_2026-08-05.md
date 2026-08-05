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
| `championvspaladin_..._complete (1)` (~/Downloads) | 62 | asymmetric holdout, 16 ratios |

The champion-vs-paladin fixture now carries all 62 fights across 16 ratios
(sha256 `F3665CA0…C3026`): the original 9 ratios at 3 repeats plus 8v4, 9v4,
10v5, 11v4, 15v8, 15v10 and 21v10 at 5 repeats each. Largest fight is 31 units.

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

## The game stops reproducing itself above ~8 units

Every repeat of a ratio starts from byte-identical positions, so the spread
across repeats is the GAME's own nondeterminism. It is not constant — it
switches on with crowding:

| ratio | repeats | winner-HP spread | winning side |
|---|---|---|---|
| 1v1 … 3v2 | 3 | **0.0%** | fixed |
| 3v5 / 3v6 | 3 | 2.6-3.2% | fixed |
| 5v3 | 3 | 10.0% | fixed |
| 6v3 | 3 | 50.0% | fixed |
| 9v4 / 11v4 / 15v10 | 5 | 19-42% | fixed |
| 15v8 | 5 | 60.7% | fixed |
| 8v4 / 10v5 / 21v10 | 5 | **75-94%** | **FLIPS** |

Below six units the game is bit-deterministic and a single run is a valid
target. Above it, three ratios cannot even agree on who wins from identical
starts. **On those, comparing one sim run to one tape number is meaningless** —
the sim has to match a distribution, which needs sampled acquisition orders.

## Scorecard

Champion mirror ratio gates: 18 pass / 0 fail. Suite: 112 pass / 27 fail.

champion_vs_paladin, one deterministic sim run per ratio scored against the
per-ratio tape band: **36/48 checks inside, winner side 15/16.**

The two defects worth chasing, both outside any RNG excuse:

- **3v2 — off by exactly one champion swing.** The tape returns 178 HP and 29
  hits in all three repeats, zero variance; the sim returns 191 and 28. Five
  units, fully deterministic on both sides. The cleanest target in the set.
- **15v8 — the only wrong winner,** and the tape is 5/5 on it. Paladins win
  with 265-675 HP; the sim hands champions a 56 HP win. Champions kill all 8
  paladins in the sim against 4.2-6.5 in the game.

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

- **Screening / surround capacity** — the lead from the 62-fight set. The game
  holds ~1 champion in 3 out of contact in big fights, we hold ~1 in 5, and the
  three ratios where that gap is widest are exactly the three where champions
  over-hit. Next step is to measure the game's actual per-target surround
  limit rather than infer it from the aggregate share.
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
