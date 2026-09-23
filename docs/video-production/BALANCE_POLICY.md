# Approved army-size formula

Updated September 22, 2026: resource weights are food 1.0, wood 0.9 and gold 1.1;
all discounts count in full. Population remains one per physical unit
(`geometric_full_discount_weighted_resources_v3`). Default for newly planned AoE2 Lab matchups and new
video episodes. Existing manifests, recordings and published videos retain the
explicit policy under which they were created.

## Formula

Start with fully upgraded Imperial **purchase cost per physical unit**. Divide
batch purchases to obtain the cost of one physical unit;
Blackwood Archers are two physical units per purchase, Karambits are one.

Owner instruction, September 22, 2026: assume the maximum applicable civilization
cost discount for new comparisons, including conditional discounts. Record the
condition and its verified maximum with the purchase-cost evidence before freezing
counts. This selects the actual purchase price before resource weighting.
It does not authorize changing old captures.

For all units, including civilization-exclusive, regional and team-granted units:

```
comparisonCost = finalFood + 0.9 * finalWood + 1.1 * finalGold
weightedCostOf27 = 27 * comparisonCost
```

Use the actual final per-resource costs after all applicable discounts. Discount
effectiveness is 100% for food, wood and gold for every unit. Shared/exclusive
classification remains recorded provenance and no longer changes the price.
The old half-strength food/wood discount adjustment does not apply to v3.

Let `score = comparisonCost`. Cap the lower-score side at
27 physical units. Give the higher-score side:

```
max(1, round_half_up(27 * sqrt(lowerScore / higherScore)))
```

Equivalently, with our side at 27:
`opponents = 27 * sqrt(ourCost / theirCost)`.
If this would exceed 27, cap the opponent instead and reduce our count. Ties give
27 each. Every physical unit has comparison population 1. Reduced population
for Blackwood Archers, Karambit Warriors, Georgian cavalry, or future units does
not change counts. The benchmark excludes the advantage of lower housing use
at the population cap. Supporting villagers and additive population values
(60, 120, etc.) are not used.

The owner removed the earlier 5,000-resource ceiling on September 15, 2026.
New standard episodes use only the formula and 27-unit cap. Historical plans
retain their explicit budgets. Golden placement, full HP and authored buffer
rules are independent.

## Hussar buffer for new captures

Approved September 22, 2026: new geometric mixed melee/ranged plans use
`fielded_weighted_cost_v1`. Calculate the main armies first. Let T be the ranged
side's actual rounded unit count multiplied by its discounted, weighted unit cost:

```
T = rangedCount * (finalFood + 0.9 * finalWood + 1.1 * finalGold)
Hussars = round_half_up(clamp(5 + (T - 1000) / 1800, 5, 10))
```

Use the actually fielded ranged army, never an assumed 27-unit army or both armies
combined. Hussars are additional support and excluded from T and the main army's
27-unit allowance. Only mixed matchups receive the buffer. Jarl is ranged for
scenario selection, like other thrown-weapon units. Its registry identity and
release costs still require verification before capture.

Examples: T=1093.5 gives 5 Hussars; T=2700 gives 6; T=5500 gives 8; T>=10000
gives 10. All rounds use nearest integer, halves up. Save the ranged owner,
fielded count, weighted unit price, T and final buffer count in the hashed plan.

Scenario generation keeps the first N existing P4 records. For ten, preserve the
nine original records and clone one at the empty adjacent tile (7.5, 5.5), inside
the existing P4 patrol area. Verify it is unoccupied. Never use (10.5, 10.5), which
contains a Golden tree. Keep the shared Golden files, camera, diplomacy, AI and
gate triggers unchanged. Existing saved plans retain their original screen;
explicit `golden`, `none`, and manual counts remain available for reproduction.
Non-nine-unit screens remain recording-only until simulator placement support is
implemented; do not compare against the simulator's fixed nine-unit screen.

| 27 featured units versus Spanish Paladin | Comparison cost | Population | Paladins |
|---|---:|---:|---:|
| Inca Elite Champi Warrior | 62.5 | 1 | 18 |
| Mapuche/Muisca/Tupi Elite Champi Warrior | 77.5 | 1 | 20 |
| Tupi Elite Blackwood Archer | 40.5 | 1 | 14 |

Spanish Paladin comparison cost in these examples is 60 food + 1.1 * 75 gold = 142.5.

This is an agreed comparison benchmark, not an in-game price, a claim of equal
spending, or a prediction of economic/strategic play. Describe new videos as
using geometric cost balance with one population per unit, not as equal resources.

## Historical recordings

`geometric_shared_discount_unit_count_v2` used one population per physical unit,
equal resource weights, and half-strength food/wood discounts for shared units.
Its corresponding Champi/Blackwood example counts were 19, 20 and 15 Paladins.
Keep those saved prices, counts and presentation rules intact. The v3 default
does not authorize replanning, recapturing or overwriting any existing result.

The earlier `geometric_shared_discount_v1` used actual catalog population:
`score = comparisonCost * population`. Its Blackwood example was 27 versus 10
Paladins. The completed Champi, Paladin and Cavalier captures retain that policy
and their original counts, frame data, results, and presentation copy. Do not
replan or rerun those episodes as part of this change. Saved-policy labels must
continue to distinguish v1 from v2. A changed narration is not a changed battle.

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
Then review whether the exact unit is shared or exclusive for provenance. The catalog retains
population source evidence for inspection, but v2 and v3 counts never use that number.
The catalog is not universal coverage.

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
11. It does not evaluate future population-changing technologies; those do not
affect this benchmark. The plan records that value as `catalogPopulation` for
provenance and explicitly sets comparison `population` to 1. Never assume an
unknown unit is exclusive or bypass missing identity/cost evidence.

Review the catalog diff and all generated counts before a new capture campaign.
Neither catalog regeneration nor changing the default authorizes new captures.
