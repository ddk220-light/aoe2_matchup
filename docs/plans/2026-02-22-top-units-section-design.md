# Top Units Section — Matchup Advisor

## Goal

Add a summary section between the hero card/age toggle and the per-unit breakdown that highlights each civ's top 2 units based on how many opponent gold units they beat.

## Definition

- **Gold unit**: any unit with `cost_gold > 0` in stats
- **Wins**: from `simData[side][slug].wins` (beats opponent in both 30v30 and 3k-resource)
- **Gold wins count**: number of opponent gold units in a unit's wins list
- **Ranking**: sort by `(gold_wins_count DESC, percentile DESC)`

## Data Flow

No backend changes. All data is already available in the frontend:
1. `dataL`/`dataR` from `/api/civ-power-units` — contains `stats.cost_gold` per unit
2. `simData` from `/api/matchup-sims` — contains `wins` and `losses` per unit

After `simData` loads, compute top units and render the section.

## Algorithm

For each side (left/right):
1. Collect all opponent unit slugs where `stats.cost_gold > 0`
2. For each unit on this side (from simData keys), count how many opponent gold slugs are in its `wins` list
3. Sort by `(gold_wins_count DESC, percentile DESC)`
4. Take top 2
5. For each top unit, find opponent gold slugs in its `losses` list

## UI

Section appears above `.ma-sections` (the 4-column breakdown), below controls.

Layout: side-by-side, left civ's top units on left, right civ's on right.

Each top-unit card shows:
- Unit icon + name + civ emblem (reuse existing `ma-unit-name-row` pattern)
- "Beats X of Y gold units" text
- Row of icons for beaten gold units
- If losses to gold units exist: "Loses to:" row with those icons

## Files Modified

- `webapp/static/js/matchup_advisor.js` — add `renderTopUnits()` function, call from `renderSimOverlays()`
- `webapp/static/css/matchup_advisor.css` — add `.ma-top-units` styles
- `webapp/templates/matchup_advisor.html` — add placeholder `<div id="top-units">` between controls and results

## Storage

Need to store `dataL`/`dataR` in module-level state so `renderSimOverlays()` can access power unit stats for gold-cost filtering.
