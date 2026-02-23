# Double Gold Combo — Matchup Advisor

## Goal

When no top unit + sidekick (gold+trash) combo can fully cover all opponent gold units, identify the best pair of two gold units that together handle the most opponents. Show this as the primary recommendation above the top unit cards.

## Trigger Condition

The double-gold combo appears for a side **only when ALL top unit + best sidekick combos on that side still have gaps**:
- Every top unit's best sidekick (`sidekicks[0]`) has `gap.length > 0`, OR
- The top unit has no sidekicks at all

If any top unit + its best sidekick achieves full coverage (gap === 0), the double-gold combo is NOT shown.

## Computation

1. Start with the **#1 top unit** (highest-scoring from `_computeTopUnits()`)
2. Identify its **weaknesses**: losses + draws filtered to opponent gold slugs (same as sidekick logic)
3. Score each other **gold unit** on the same side as a combo partner using the same 3/2/2/1 formula:

```
score = sum(3  for opp in topLosses  if opp in partner.wins)
      + sum(2  for opp in topLosses  if opp in partner.draws)
      + sum(2  for opp in topDraws   if opp in partner.wins)
      + sum(1  for opp in topDraws   if opp in partner.draws)
```

Where `partner.draws` = `partner.pop_wins ∪ partner.eco_wins`.

4. **Filter**: partner must be gold (`cost_gold > 0`), exclude the top unit itself
5. **Sort**: `(score DESC, percentile DESC)`, take top 1

## Output

```
{
  topUnit:          <the #1 top unit item>,
  partner:          { slug, entry, score, percentile, covered, gap, totalWeaknesses },
  allGapsFilled:    boolean (gap.length === 0)
}
```

- `covered`: opponent slugs from (topLosses ∪ topDraws) that the partner wins or draws against
- `gap`: weaknesses not covered by either the top unit or the partner

## Display

- **Position**: Above all top unit cards, at the top of the side's column
- **Card style**: Distinctive accent border/background to differentiate from regular top unit cards
- **Content**:
  - Header label: "Best Gold Combo"
  - Both unit icons + names (side by side, with civ emblem once)
  - "Together cover X of Y opponent gold units"
  - Icons of covered opponents
  - If gap > 0: "Can't beat:" row with gap icons

## When NOT to Show

- No top units exist (no gold wins at all)
- Any top unit + its best sidekick has gap === 0 (clean gold+trash answer exists)
- No gold combo partner scores > 0

## Files Modified

- `webapp/static/js/matchup_advisor.js` — add `_computeGoldCombo()`, modify `_buildTopColumn()` to check gaps and prepend combo card
- `webapp/static/css/matchup_advisor.css` — add `.ma-gold-combo-card` styles with distinctive accent
