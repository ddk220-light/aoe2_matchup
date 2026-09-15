# Approved army-size formula

Approved September 15, 2026. Default for newly planned AoE2 Lab matchups and new
video episodes. Existing manifests, recordings and published videos retain the
explicit policy under which they were created.

## Formula

Start with fully upgraded Imperial **purchase cost per physical unit**. Food,
wood and gold have weight 1. Divide batch purchases before calculating discounts;
Blackwood Archers are two physical units per purchase, Karambits are one.

For units shared across civilizations (including regional and team-granted units):

```
comparisonFood = finalFood + 0.5 * max(0, baseFood - finalFood)
comparisonWood = finalWood + 0.5 * max(0, baseWood - finalWood)
comparisonGold = finalGold
comparisonCost = comparisonFood + comparisonWood + comparisonGold
```

For civilization-exclusive units, use the actual final resource total. This
halves only positive food/wood discounts; food/wood prices themselves keep full
weight. Gold discounts and resource-cost increases remain fully effective.
Classification follows unit availability, not its production building. Exclusive
final upgrades such as Savar, Houfnice and Imperial Camel remain exclusive.

Let `score = comparisonCost * militaryPopulation`. Cap the lower-score side at
27 physical units. Give the higher-score side:

```
max(1, round_half_up(27 * sqrt(lowerScore / higherScore)))
```

Equivalently, with our side at 27:
`opponents = 27 * sqrt((ourCost / theirCost) * (ourPopulation / theirPopulation))`.
If this would exceed 27, cap the opponent instead and reduce our count. Ties give
27 each. Military population is the actual per-unit population, not supporting
villagers. The earlier additive population values (60, 120, etc.) are not used.

For standard episodes retain the 5,000 actual-resource ceiling per main army.
Reject a request that exceeds the ceiling rather than silently changing the
formula. Golden placement, full HP and authored buffer rules are independent.

| 27 featured units versus Spanish Paladin | Comparison cost | Population | Paladins |
|---|---:|---:|---:|
| Inca Elite Champi Warrior | 67.5 | 1 | 19 |
| Mapuche/Muisca/Tupi Elite Champi Warrior | 75 | 1 | 20 |
| Tupi Elite Blackwood Archer | 40 | 0.5 | 10 |

This is an agreed comparison benchmark, not an in-game price, a claim of equal
spending, or a prediction of economic/strategic play. Describe new videos as
balancing resource cost and population efficiency, not as equal resources.

## Code and provenance

- [Calculation](../../aoe2x/js_simulation/src/recording-balance.js)
- [Purchase costs](../../data/recording-costs.json)
- [Reviewed population and availability](../../data/recording-balance.json)
- [Independent capture validation](../../aoe2x/lab/costs.py)
- [Saved-plan presentation labels](../../aoe2x/lab/balance.py)
- [New episode scaffold](../../apps/video/scaffold_video_episode.py)
- [Completed comparison campaign](CHAMPI_GEOMETRIC.md)

New CLI, Python and Node plans default to `geometric_shared_discount`. Explicit
`equal_resources`, `equal_count` and `explicit` modes remain available for
historical reproduction or a specifically requested experiment. Do not copy a
historical episode-specific `prepare_*` script to create a new episode; use the
scaffold, which selects the approved formula and updates description wording.

Both purchase and comparison catalog hashes are saved in the plan and affect
its plan hash. Missing identities fail closed. Never backfill a captured plan
with a new catalog hash; archive indexes retain original evidence for replay.

## Registering a new identity

First audit effective purchase costs using [Setup and data](SETUP_AND_DATA.md).
Then review whether the exact unit is shared or exclusive, and check its final
military population including any relevant civilization/technology effects.
The current catalog contains 79 reviewed identities; it is not universal coverage.

Existing reviewed classifications are preserved by the generator. A new master
requires a JSON file keyed by master ID, with `sharedAcrossCivilizations` (boolean)
and `classificationEvidence` (nonempty explanation). Example shape:

```json
{"12345": {"sharedAcrossCivilizations": true, "classificationEvidence": "Reviewed availability in civilizations A and B"}}
```

Run in an environment with the existing `genieutils` parser:

```powershell
$env:PYTHONPATH='data/local/cost-audit-deps;apps/video;.'
apps/video/.venv/Scripts/python.exe scripts/build_recording_balance_catalog.py --dat <installed-dat-path> --identity 'Civilization|registered_slug' --classifications <reviewed-json-path>
```

The generator reads base population from DAT storage 4 and cross-checks storage
11. It does not evaluate future population-changing technologies: if a new
identity has those, extend and test the extractor before capturing it. Never
assume an unknown unit is exclusive or assign population 1 as a fallback.

Review the catalog diff and all generated counts before a new capture campaign.
Neither catalog regeneration nor changing the default authorizes new captures.
