# Sidekick Units — Matchup Advisor

## Goal

For each top 2 unit per civ, identify the best complementary "sidekick" unit from the opposite resource pool (trash for gold top units, gold for trash top units) that covers the top unit's weaknesses.

## Definitions

- **Gold unit**: `cost_gold > 0`
- **Trash unit**: `cost_gold == 0`
- **Top unit losses**: opponent units in the top unit's `losses` list (opponent wins both sims)
- **Top unit draws**: opponent units in the top unit's `pop_wins` ∪ `eco_wins` (top unit wins one sim only)

## Sidekick Scoring Formula

Sidekick candidates: units on the same side with opposite cost type (gold↔trash, strict).

For each candidate, score against the top unit's weaknesses:

```
score = sum(3  for opp in topLosses  if opp in sidekick.wins)
      + sum(2  for opp in topLosses  if opp in sidekick.draws)
      + sum(2  for opp in topDraws   if opp in sidekick.wins)
      + sum(1  for opp in topDraws   if opp in sidekick.draws)
```

Where `sidekick.draws` = `sidekick.pop_wins ∪ sidekick.eco_wins`.

**Ranking:** Sort by `(score DESC, percentile DESC)`. Take top 2.

## Output Per Sidekick

- `covered`: opponent slugs from (topLosses ∪ topDraws) that the sidekick wins or draws against
- `gap`: (topLosses ∪ topDraws) − covered — units neither top unit nor sidekick can handle

## Data Flow

No backend changes. All data already in frontend simData:
- `simData[side][slug].wins`, `.pop_wins`, `.eco_wins`, `.losses` — available for ALL units (gold and trash)
- `unitsBySlug` — already built in `renderTopUnits()`, contains `stats.cost_gold` and `percentile`

## Display

Inline sub-cards nested below each top unit card:

```
┌─ Top Unit Card ──────────────────┐
│ 🏰 Paladin    Beats 7 of 9 gold │
│ [beaten icons]                   │
│ Loses to: [loss icons]           │
├──────────────────────────────────┤
│ Best Sidekick: Halberdier        │
│ Covers: [icons]  Gap: [icons]   │
├──────────────────────────────────┤
│ Alt Sidekick: Skirmisher         │
│ Covers: [icons]  Gap: [icons]   │
└──────────────────────────────────┘
```

Each sidekick sub-card shows:
- Unit icon + name (no civ emblem — same civ as parent)
- "Covers X of Y weaknesses" summary
- Icons of covered opponent units (sidekick wins or draws against)
- "Neither can beat:" row with gap icons (if any remain)

## Files Modified

- `webapp/static/js/matchup_advisor.js` — add `_computeSidekicks()`, modify `_buildTopCard()` to render sub-cards
- `webapp/static/css/matchup_advisor.css` — add `.ma-sidekick-card`, `.ma-sidekick-summary`, `.ma-sidekick-gap-row` styles
