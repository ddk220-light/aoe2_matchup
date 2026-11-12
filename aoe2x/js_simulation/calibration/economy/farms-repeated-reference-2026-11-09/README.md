# Repeated farming-reference audit

The engine is unchanged. This audit adds an independent published experiment with 36 sets of eight farms. It does not replace the earlier six-case comparison.

Source: [Vixark: Folwark Farming Analysis](https://vixark.com/age-of-empires-ii/folwark). The source table contains 286 usable observations; two cells are blank and are excluded rather than imputed.

The image shows a 3×3 drop site surrounded by eight 3×3 farms. The calculation uses the author’s stated 175 food gathered per farm, without instant collection. This tests ordinary farmer movement in that geometry; it does not validate the Poles bonus.

| Farm group | Published mean seconds | Simulated mean seconds | Published food/min | Simulated food/min | Difference |
|---|---:|---:|---:|---:|---:|
| Adjacent (A) | 507.580 | 503.376 | 20.686 | 20.859 | 0.835% |
| Corner (B) | 542.566 | 527.292 | 19.352 | 19.913 | 2.897% |

Each model group includes 144 depletion times across the first 36 seeds. The rate estimator matches the source: food divided by mean lifetime. Reference observations from one setup may be correlated; treating all farms as independent would understate uncertainty.

## Previous benchmark retained

| Upgrades | Farm | Difference |
|---|---|---:|
| none | near | -3.533% |
| none | outer | -2.070% |
| wheelbarrow | near | 1.774% |
| wheelbarrow | outer | 0.574% |
| full | near | -0.114% |
| full | outer | -0.730% |

These are the existing 32-seed results, with their original mean-of-individual-rates estimator. No seed selection, changed parameters, or reference replacement was used.

## Limits

- Publication date, executable build, game speed, exact worker start positions, initial pool and task timestamps are not provided.
- The text explicitly describes collecting 175 food per farm. How instant Folwark collection was disabled or avoided is not explained; this is a conditional generic-farmer comparison, not a validated Poles scenario.
- Layout dimensions follow the source image; source A/B orientation is arbitrary under rotation in this model. Exact contact/pathing geometry is not supplied.
- The model starts empty-handed farmers at farm centers with empty pools and no reseeding. No initial wait or movement correction is fitted.
- The earlier 2023 benchmark remains outside 1% for three of six cases. Neither source supplies a reproducible current-DE scenario or movement capture.

Passing a group mean is narrower than validating every position, upgrade level, or civilization. Current-DE recordings with known starts and drop-off events are still needed for a universal sub-1% claim.
