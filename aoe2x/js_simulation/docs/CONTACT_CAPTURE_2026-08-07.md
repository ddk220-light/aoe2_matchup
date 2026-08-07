# Contact capture: the skirm-vs-camel fix, read off the tape's own action state

The last wrong-winner matchup in the held-out standard-units set — Elite
Skirmisher (21) vs Heavy Camel Rider (8), tape: camels win at **+39.8%** — is
fixed by a rule read directly from the tapes' full-rate action decode, after
every geometry-side attempt failed (`CHASER_ENGAGEMENT_2026-08-06.md`).

## The measurement that broke it open

The svcam `frames.bin` carries each unit's live `Action.target_id` at ~60 Hz —
ground truth this investigation had never consulted for the chasers. Two prior
beliefs fell immediately:

1. **The camel side is not AI-micromanaged.** The whole fight contains 8
   aiOrders for the camels: the slice(4) wave at 0.8–1.3 s (recipients
   1609–1612, all-but-the-4-lowest ids, matching the kac model exactly) plus 4
   sparse re-orders.
2. **Camel pursuit is not lock-until-death.** 142 target switches; **64 with
   the old target still alive**; switch cadence p50 3.0 s; the new target is
   the camel's nearest skirmisher **77%** of the time; distance to the current
   target p50 1.74 — they fight what is around them, not a stale designation.

What triggers an alive-switch is unambiguous:

| at the switch | svcam camels (n=64) |
|---|---|
| distance to NEW target | p25 0.49 / p50 0.54 / p75 0.59 |
| distance to OLD target | p25 0.88 / p50 1.12 |
| speed in prior 0.25 s | p50 96% of dat speed, 11% stopped |
| under attack | 1/64 |
| hp dropped in prior 1.5 s | 13/64 |
| new target in direction of motion | cos p50 +0.82, cos>0 in 92% |

0.49–0.59 is exactly the collision-contact band (camel 0.25 + skirm 0.20 =
Chebyshev 0.45, spanning Euclidean 0.45–0.64 by approach angle). **A walking
chaser that comes into body contact with an enemy in its path switches its
pursuit to that enemy.**

The same signature holds corpus-wide: esc champions (46 alive-switches, p50
0.50), avp paladins (38, p50 0.58), esp paladins (43, p50 0.54), avst steppe
(6, p50 0.51), hcc champions (17, p25 0.51). kac shows only 9 — 7 of them
under attack at p50 1.68, i.e. the sparse aiOrders — because kac's champions
(1.056) essentially never catch the arbalester block, so contact never happens.
The rule is universal; its *frequency* is emergent catchability.

This also retro-explains two standing mysteries: the victim-rank agreement
(tape r1 = 71% — the chaser fights the body it touched, which is its nearest)
and why chasers never wade into the block (**the first body a chaser touches
captures it, so it fights the formation's surface**).

## The rule as implemented

In the kited-world chase branch (`world.updateEngagements`): a chaser that is
not attacking, not engaged, and whose pursuit target is **beyond its reach**
(the recorded old target sits p50 1.12 away) switches pursuit to the nearest
enemy in body contact (`chebyshevGap ≤ 0.02`) **in the direction of its
pursuit** (dot > 0 — the tape's cos>0 in 81–92%). The beyond-reach condition
makes capture an event: once captured, the new target is in contact, and the
rule goes quiet — without it a chaser pressed between two bodies ping-pongs
every tick (3944 captures/fight against the tape's 64) and its dwell never
completes. With it: **47 captures/fight against the tape's 64.**

The old 64%-no-swing adjacency measurement that built the sticky discipline
used a 1-tile radius; capture needs actual box contact, a strictly smaller
trigger, so both hold.

**Scope:** engine-universal rule, enabled per scenario (`chaseCapture` in the
truth fixture, carried like `kiteProfile`). Measured capture rates, sim against
tape: svcam 47/64, esc 40/46, esp 25/43, avp 20/38, **kac 43/9**, hcc 22/17.

ON for svcam, esc, esp, avp — the sim fires the rule at or below the tape's
rate. OFF for kac, the one gross over-generator (4.8x), pending the
block-escape pathing work. hcc is a **weaker** case for OFF than kac: its rate
looks close, but only about half of its 17 tape switches sit in the contact
band (p25 0.51, p75 6.27 — the rest are aiOrders), so it is held off until that
subset is counted properly, not because the rate is wrong. Elephant /
fire-lancer chase archives have not had their action decode measured yet: OFF
until measured.

## Result

svcam, 25 sampled acquisition orders (tape +39.8, camels win):

| | HEAD | contact capture |
|---|---:|---:|
| camels win | 10/25 | **22/25** |
| mean signed | −9.4 | **+26.7** |
| kiters take (tape 8.36 hp/s) | 6.09 | **8.91** |
| chasers take (tape 7.67 hp/s) | 10.45 | 9.42 |
| duration (tape 87.9 s) | 100.4 | **87.6** |
| victim rank r1 (tape 71%) | 31% | **75%** |
| captures/fight (tape 64) | — | 47 |

The winner is fixed and the camel side's physics is exact. The remaining
margin gap (+26.7 vs +39.8) is the skirmisher side still over-delivering
(9.42 vs 7.67) — the min-range suppression that measurement supports but that
cannot land until exposure (45.7% vs the tape's 22.9%) comes down further.

Circuit (27 matchups × 25 orders, summed mean band error / wrong winners):
only the three flagged columns move —
`eliteskirm_vs_champion_kiting` 3.96 → **3.34**,
`eliteskirm_vs_paladin_kiting` 0.40 → **0.22**,
`arbalester_vs_paladin_kiting` 3.06 → 3.54;
every other matchup is bit-identical, kac stays at 1.90 and hcc at 0.00.
Tests unchanged at 131/157 (all 26 failures pre-exist).

## What remains

1. The margin undershoot is the suppression story: at tape exposure (22.9%)
   the measured min-range shooter suppression would take skirm output from
   9.42 to ~7.6. Exposure is down from 60.3% (HEAD) to 45.7% but not there.
2. kac keeps capture off because our block still jams into chasers the tape
   says it should outrun; fixing block escape (the `STEP=steer` line of work)
   would let the flag come off. hcc needs its contact-band switch subset
   counted before its flag can be decided either way.
3. ~~Re-run the standard-units sweep~~ — done, in
   `STANDARD_UNITS_SUMMARY_2026-08-07.md`. Isolated against this commit's
   parent by re-running the whole sweep there, contact capture moves exactly
   one of the 101 matchups (svcam, -9.4 -> +26.7) and leaves the other 100
   bit-identical; corpus winner agreement 96/101 -> 97/101, mean |delta|
   14.95 -> 14.59.
4. `arbalester_vs_paladin_kiting` is the one column the rule costs (3.06 ->
   3.54, four of five ratios slightly worse). Its capture rate is the weakest
   match of the flagged set (20 against 38), so it is the first to revisit — but
   it stays ON because the tape signature is there, and switching it off on the
   strength of the score would be fitting to the outcome.

## Reproducing

```
AOE2X_EXP_ENGAGEMENT=pursuit AOE2X_EXP_ORDERS=1 node run_matchup_circuit.mjs 25
```

Scratchpad: `camel_target_truth.py` (the ground-truth switch measurement),
`read_ai_orders.py` output for the camel side, the per-archive switch scans,
`capture_count.mjs`, `capture_speed.mjs`, `svcam_probe.mjs`,
`sim_victim_rank.mjs`; circuits `base_circuit.json` / `final_circuit.json`.
