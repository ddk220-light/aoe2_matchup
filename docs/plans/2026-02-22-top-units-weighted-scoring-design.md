# Top Units Weighted Scoring — Matchup Advisor

## Goal

Replace simple gold-win-count ranking with a weighted scoring system that values beating strong opponent units more than beating weak ones.

## Scoring Formula

**Points:** Win = 3, Draw (pop_win or eco_win) = 1

**Opponent strength:** For each opponent gold unit, count how many of my gold units it fully beats (wins list).

**Unit score:**
```
score = sum(3 * oppStrength[slug] for slug in wins if slug is gold)
      + sum(1 * oppStrength[slug] for slug in pop_wins if slug is gold)
      + sum(1 * oppStrength[slug] for slug in eco_wins if slug is gold)
```

**Ranking:** Sort by `(score DESC, percentile DESC)`. Take top 2.

## Data Flow

No backend changes. All data already in frontend simData:
- `simData[side][slug].wins` — full wins (both v30+3k)
- `simData[side][slug].pop_wins` — v30 only wins (draw overall)
- `simData[side][slug].eco_wins` — 3k only wins (draw overall)

Opponent strength computed from the opposite side's simData.

## Display

No display changes. Cards still show "Beats X of Y gold units" with icons. Only the ranking order changes.

## Files Modified

- `webapp/static/js/matchup_advisor.js` — modify `_computeTopUnits()` to accept opponent side's simData and compute weighted scores
