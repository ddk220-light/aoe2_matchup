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
| `championvspaladin_..._complete` (~/Downloads) | 27 | asymmetric holdout, 9 ratios |

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

## Scorecard

Champion mirror ratio gates: 18 pass / 0 fail. Suite: 112 pass / 27 fail.

champion_vs_paladin, 22/36 checks inside the tape band, winner side 9/9:

| ratio | winner HP tape → sim | verdict |
|---|---|---|
| 1v1 / 1v2 / 2v1 / 2v3 | exact | inside |
| 3v5 / 3v6 | inside band | inside |
| 3v2 | 178 → 191 | mildly off |
| 5v3 | 217-241 → 215 | 2 HP outside |
| 6v3 | 14-28 → 112 | the outlier |

Last death is early in all nine, by 0.05-0.31 s outside 6v3 — a uniform
residual not yet chased.

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

- **Acquisition order.** Does it have structure, or is it uniform per unit? More
  recordings of this matchup are being made to answer exactly this. If it is
  random, no deterministic ordering is correct and a single fight on this
  formation is not a meaningful target — the draw alone moves the result ~100
  HP. Score against the band, or sample several orders per scenario.
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
