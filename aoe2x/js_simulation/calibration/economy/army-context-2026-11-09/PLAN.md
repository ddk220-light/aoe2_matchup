# Army context analysis plan

1. Use the supplied DAT extract, corrected production database, existing Imperial-priced upgrade database and consolidated matchup runs. Preserve all originals.
2. Replay available economic effects for all 56 civs, with integer carry rounding. Run source-derived food/wood/gold/stone scenarios; reuse identical physical parameter sets. Add generic yield, instant-collection and auto-deposit policies for farming.
3. Record every known economic mechanic with a modeled, conditional, event-only or unresolved status. Never substitute generic farming for unavailable farms or guess compiled-engine hook formulas.
4. Build one SQLite review database containing source inventories, rates and individual runs, unit replacement labor, production routes, research costs/time/buildings and every selected battle.
5. For every saved run with winner HP fraction below 0.25, compare dead-unit replacement labor and production queue time; report shared-upgrade cost/time separately from exclusive upgrades and infrastructure.
6. Flag attrition reversals and concurrent queue advantages as candidates, with ±5% resource-rate sensitivity. Keep HP-equivalent damage replacement as a separate diagnostic, because wounded survivors are not dead units.
7. Validate coverage, identity joins, accounting, special policies and missing-data exclusions; export all candidates and civ rates, then write the findings and limitations.

Baseline: post-Imperial with every available upgrade, own bonuses only, no allied team bonuses, no relics/trade/market purchases, no externally supplied resources, no covered church aura. Resource allocation can be optimized separately for each unit. Buildings are already built for replacement labor; their costs remain separate. All battle outcomes are retained. A candidate is not a newly simulated battle victory. No army-cost normalization is used for upgrade comparison.
