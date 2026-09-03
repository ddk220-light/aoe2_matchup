# Skirm vs camel: what is actually wrong, and the order to fix it

Elite Skirmisher (21) vs Heavy Camel Rider (8) is the last wrong-winner matchup
in the held-out standard-units set: the tape has the camels winning with 39.8%
of their HP pool, the sim has the skirmishers winning most runs.

This supersedes the "next step" recorded in `KITER_FLOW_2026-08-06.md`. Every
number below is measured today, tape and sim through the **same metric at the
same cadence** — which is what changed the conclusion.

## The defect: our units grind, the game's do not

Heavy camel speed, sampled per frame at ~60 Hz over the whole fight:

| speed (tiles/s) | tape | sim |
|---|---:|---:|
| 0.00–0.05 — stopped | 46.1% | 50.6% |
| 0.05–1.50 — **partial** | **0.6%** | **25.2%** |
| 1.50–1.70 — full (dat 1.595) | 52.9% | 24.2% |
| n | 44 719 | 121 311 |

The tape is strictly bimodal: a Genie unit is stopped or it is at full speed.
It never grinds along a body. Ours spends a quarter of the fight at partial
speed and only half as long as the tape at full speed. Directly: our camels
stall on **33.6%** of the ticks they have somewhere to be, and **48.7% of those
stalls happen inside the skirmisher block**. Their action mix is idle 62% /
attacking 28% / reload 10%.

The cause is in the movement pipeline. `resolveMovementProposals` removes the
inward component of a blocked step (`constrainPair` → `distributeEqualMassRemoval`),
so a blocked unit slides along the obstacle at whatever speed survives. Stopped
units are correctly never shoved — only inward motion is removed — so the error
is entirely on the mover's side.

## What it costs: the block engulfs the chaser

A slow chaser inside a formation that reforms through itself gets flowed around
and closed over. Same metric, tape vs sim, over the whole fight:

| | tape | sim |
|---|---:|---:|
| chaser gap to nearest shooter, p50 | **1.51** | **0.58** |
| chaser → block centroid, p50 | 2.39 | 1.52 |
| chaser-frames with any shooter inside 1.0 | 28.3% | 75.9% |
| shooters covered per chaser, mean | **0.69** | **3.36** |
| shooter-frames with a chaser inside min_range 1.0 | **22.9%** | **57.3%** |
| block radial spread p50 / p90 | 0.69 / 1.25 | 0.93 / 1.75 |

The tape's camels hover **outside** the block — median 1.51 tiles from the
nearest skirmisher, 2.39 from its centroid against a block whose own p90 radius
is 1.25. Ours sit **inside** it, each one covering 4.9× as many shooters.

This is not chasers passing through bodies. Enemy obstruction is real on the
tape: 99.76% of camel↔skirmisher pairs hold ≥ 0.45 Chebyshev (0.25 + 0.20), min
0.173, p0.1 0.385. The game's camel keeps full speed *around* the block; ours
wedges into it.

## The consequence in damage

| | tape | sim (5 orders) |
|---|---:|---:|
| duration | 87.9 s | 84–101 s |
| kiters take | 8.36 hp/s | 4.72–7.77 (mean ~5.7, **−32%**) |
| chasers take | 7.67 hp/s | 9.05–13.32 (mean ~11.5, **+50%**) |

Our skirmishers deliver half again as much damage as the tape's, because ~3.4
of them are firing point-blank at each camel from inside their own minimum
range. The camels' shortfall is downstream of that: in the one sampled run
where our camels survive (23.6% left) their output is 7.77 hp/s against the
tape's 8.36 — right. They under-deliver in the other runs because they die.

## Why min-range suppression overshot

The suppression rule itself is measured and correct — minimum range holds the
*shooter*, not just the one target it aimed at (439 named shooters, 233 arrows,
225 of them hits; firers' nearest camel p50 2.2 tiles vs holders' 1.0; the
min_range-0.0 arbalester column as a null control). What was wrong was landing
it on top of this geometry.

The rule's cost is proportional to exposure, and our exposure is 57.3% of
shooter-frames against the tape's 22.9%. So it removed ~2.5× too much fire:
camels won 25/25 at +75.8 against the tape's +39.8, and
`eliteskirm_vs_champion_kiting` went 2.54 → 13.50. At correct geometry the same
rule should cut skirmisher output by ~23%, i.e. 11.5 → ~8.9 hp/s against the
tape's 7.67 — the right order of magnitude, with the rest of the gap closing as
the chasers stop being surrounded.

## Correction: the slot geometry is not the problem

`KITER_FLOW_2026-08-06.md` recorded the next step as "calibrate the formation
slot geometry to the tape's settled block (2.01 × 2.23 tiles for 21 units,
nearest-neighbour p50 0.371)". That comparison was mismatched — the tape figure
came from settled full-roster frames, the sim figure from the whole fight.
Measured the same way on both sides:

| | tape | sim |
|---|---:|---:|
| ally NN Chebyshev p50 | 0.296 | 0.238 |
| share inside 0.40 | 82.1% | 71.2% |
| share inside 0.20 | 31.0% | 44.0% |
| block bbox w × h, p50 | 1.63 × 1.71 | 2.43 × 1.98 |

Our block is in the right ballpark: slightly clumpier locally (44% vs 31% inside
0.20) and looser overall (a wider bbox with a longer radial tail — stragglers).
Worth a later pass, but it is a second-order effect and it is not what decides
this fight. **Do not spend a round on slot spacing.**

## Fix order

1. **Chaser mobility.** A blocked unit must take a full-speed step around the
   obstruction or none at all. Target, measured the same way: the 0.05–1.50
   partial-speed band drops from 25.2% toward the tape's 0.6%, and the stall
   rate on want-to-move ticks drops well below 33.6%.
2. **Re-measure engulfment.** With (1) in, chaser → centroid p50 should rise
   from 1.52 toward 2.39 and coverage fall from 3.36 toward 0.69. If it does
   not, the remaining cause is the formation walking its slots over an enemy
   body, and the rule to test on tape is whether a slot occupied by an enemy is
   simply not entered.
3. **Then land min-range shooter suppression** (`kiteAttackBeat` carries the
   full measurement in a comment) and re-check against the 22.9% exposure
   figure, not against the outcome.
4. **Re-verify the whole kiting corpus plus svc/svp.** The esc/kac seesaw is
   real and any of these changes will move both.

## Risk

The same defect is in the *converged* columns, so fixing it will move them. On
`eliteskirm_vs_champion_kiting` 20v20 the sim has chasers inside 1.0 of a
shooter on 55.4% of chaser-frames against the tape's 11.6%, coverage 1.82
against 0.29, chaser gap p50 0.84 against 2.63, and a 25.8% stall rate. That
column currently scores 3.96 with the wrong microscopic behaviour — expect it,
and kac, to move when the geometry is corrected, in either direction.

## Verdict on commit e4730558

**Keep it.** Its three rules are each independently tape-measured, the corpus is
net better with 0 wrong winners (`arbalester_vs_champion_kiting` 3.88 → 1.90),
and the camel fight's small backslide (13/23 → 10/25) is a symptom of the
mobility defect above, not of the commit: a block that can reform through itself
engulfs a chaser that cannot get out of the way, and before the commit the same
block simply gridlocked instead. The honest arguments for reverting are
`eliteskirm_vs_champion_kiting` 2.54 → 3.96 and that backslide; both are smaller
than what step 1 is expected to move.

## Reproducing

Scratchpad tools, tape side: `pack_vs_suppress.py`, `block_shape.py`,
`damage_curve.py`. Sim side, same metrics and cadence:
`sim_pack_suppress.mjs`, `sim_block_shape.mjs`, `sim_damage_curve.mjs`,
`sim_centroid.mjs`, `sim_camel_jam.mjs`, `sim_speed_hist.mjs`,
`sim_esc_shape.mjs`. All sim runs need
`AOE2X_EXP_ENGAGEMENT=pursuit AOE2X_EXP_ORDERS=1`.
