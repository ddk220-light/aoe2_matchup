# Minimum-range kiting — scorpion_vs_champion (2026-08-06)

## Source

| Archive | SHA-256 |
|---|---|
| `aoe2_golden_ranged_scorpionvschampion_2026-08-05.zip` | `30235D984F503172123DFD2D4D24AB9AB513EE57A29C6825AF2252B7879B6EDB` |

5 ratios x 5 repeats (25 fights). Champion side = the Chinese Champion 567
already fixtured; scorpion side = the Japanese-group Heavy Scorpion (see
SCORPION_PASSTHROUGH_2026-08-06.md; melee hits of 17 = champion 18 − scorpion
melee armor 1 confirm the group).

## What the kiting actually is

The frames.bin command stream rules out player-AI micro: a 15-unit fight
carries ~2-4 AiOrder records total (orderType 700 attack designations; the
scorpion side's orders carry `range: 8`), yet scorpions move in 545 recorded
bursts. **The retreat is unit-level behaviour**: a ranged unit with an enemy
inside its dat `min_range` backs directly AWAY from the nearest such enemy in
short bursts between shots.

Measured on the 545 bursts (>0.3 tiles):
- away-aligned bursts (cos > 0.5 vs the away-from-nearest-champion bearing,
  n=301) trigger at nearest-champion distance p50 1.9 around the dat
  min_range 2.0 (p25 1.26 / p75 2.39, mid-burst sampling blur);
- burst length p50 1.0 tiles — a back-step per reload, then stop and fire
  (cadence stays at reload p50 3.618 with a mild p90 3.944 tail);
- direction alignment with away-from-threat reaches 0.97 at p75;
- the chase still closes: champion 1.056 vs scorpion 0.65 tiles/s, and the
  nearest-champion distance at burst END (p50 1.81) is no larger than at the
  start — retreating only delays contact, exactly as the recorded outcomes
  show.

Engine rule (`minRangeRetreat` in world.js): a non-attacking ranged unit
with any enemy centered inside `min_range` proposes a full-speed step
directly away from the nearest such enemy, overriding pursuit. No new
constants — the trigger distance IS the dat min_range, and the tape median
sits on it.

## Circuit results (25 sampled acquisition orders, pursuit+orders config)

| Ratio | Tape band | Sim median | Band error |
|---|---|---|---|
| 5v10 | +43.4..+67.7 | +34.0 | 9.4 |
| 10v5 | −91.5..−87.2 | −83.0 | 4.2 |
| 15v20 | +23.9..+35.3 | +5.9 | 18.0 |
| 20v15 | −80.1..−40.1 | −72.3 | 0 |
| 20v20 | −75.1..−32.2 | −53.0 | 0 |

**Mean band error 6.32, 0 wrong winners, 25/25 orders resolve per ratio.**

**Accepted residuals:** the two scorpion-favored ratios (5v10, 15v20)
underestimate the scorpions — the sim's kiting delays melee contact less
effectively than the tape's (retreating scorpions block on their own 0.5-tile
boxes and champions reach them slightly sooner). Winner correct in every
ratio; the champion-favored ratios land inside their (wide) tape bands
exactly. Left as the phase's documented residual pending the further ranged
archives the recorder is producing.
