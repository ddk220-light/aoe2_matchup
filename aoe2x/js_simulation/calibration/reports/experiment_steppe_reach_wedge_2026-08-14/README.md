# Reach-melee wedge transit experiment

## Decision

Keep the experiment for visual review. It fixes the HCA-versus-Elite-Steppe
winner failure without changing attack range, speed, reload, damage, HCA
kiting, or ordinary Champion collision.

The engine now permits one exclusive allied transit pair when all of these
physics-derived conditions hold:

- the pursuing melee unit has at least one tile of sourced attack range;
- it is within one attack-range tile of its legal engagement envelope;
- the allied unit is physically ahead of it toward the target;
- the move is closing on that ally and on the target;
- sourced relative closure over one reload is no greater than the unit's
  attack range; and
- neither unit already belongs to another transit pair.

This allows a two-deep reach wedge. Three-neighbor admissions and four-unit
compact cliques still take the existing preventive lateral route.

## Authorized tape sources

| Archive | SHA-256 |
|---|---|
| `aoe2_golden_kiting_hcavarchervssteppe_2026-08-06.zip` | `74D83F2EBE0D7EE89AD76C50D68147D4D0B085FA0223B1CECB59FF83198C9373` |
| `aoe2_golden_kiting_arbalestervssteppe_2026-08-06.zip` | `3F4D8F0B69AE82A874E28FD1A9B801C9B0DFB4F46A17B4692F4457ADB2CB9C34` |
| `aoe2_golden_kiting_eliteskirmvssteppe_2026-08-06.zip` | `9500E4703ACB48273C83D71CE4313820BA92391EE80CAF2882F92AF12B46414B` |
| `aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip` | `EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5` |

All archives were verified before the final run. Each row used all five exact
golden starting states.

## HCA versus Elite Steppe

| Ratio | Tape | Baseline sim | Wedge sim | Baseline abs delta | Wedge abs delta | Winner correct |
|---|---:|---:|---:|---:|---:|:---:|
| 10v5 | -86.25 | -62.50 | -61.25 | 23.75 | 25.00 | Yes |
| 15v20 | 59.20 | 31.00 | 49.25 | 28.20 | 9.95 | Yes |
| 20v15 | -26.50 | -55.62 | -29.38 | 29.13 | 2.88 | Yes |
| 20v20 | 29.60 | -41.87 | 33.75 | 71.47 | 4.15 | Yes |
| 5v10 | 80.20 | 69.50 | 84.00 | 10.70 | 3.80 | Yes |

- Mean absolute delta: **32.65 -> 9.16**.
- Wrong-winner runs: **5 -> 0**.
- Rows above 25 points: **3 -> 0** (`10v5` is exactly 25.00).
- Unresolved runs: **0**.

On exact 20v20 repeat 1, Steppe attack starts changed from 99 to 176 and
damaging hits from 93 to 160. The tape has about 169 attack entries and exactly
160 damaging hits. The simulation changed from an HCA win at -41.875 to a
Steppe win at +33.75; tape is +25.75 for that repeat.

## Regression screen

| Matchup family | Rows | Mean abs delta | Max abs delta | Wrong winners | Unresolved |
|---|---:|---:|---:|---:|---:|
| Arbalester vs Elite Steppe | 5 | 8.36 | 16.20 | 0 | 0 |
| Elite Skirmisher vs Elite Steppe | 5 | 2.03 | 3.68 | 0 | 0 |
| HCA vs Champion | 5 | 9.21 | 19.02 | 0 | 0 |
| HCA vs Elite Steppe | 5 | 9.16 | 25.00 | 0 | 0 |

Across the final 20-row / 100-run screen: mean absolute delta **7.19**,
maximum **25.00**, no wrong winners, no unresolved runs, and no rows above 25.

## Rejected intermediate

Relaxing contact-graph steering without pair transit increased Steppe attacks
slightly but left ordinary allied collision blocking the rear line. It moved
20v20 farther from the five-repeat tape target. Enabling reach transit without
the sourced closure-per-reload gate fixed HCA-Steppe but over-strengthened
Steppe against Arbalesters. Both intermediate variants were rejected.
