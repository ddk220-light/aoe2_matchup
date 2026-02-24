# Unique Combo Deduplication

## Problem

In `_buildTopColumn`, the top 2 units each independently compute their best partner (trash sidekick or gold combo). When two cards end up with the same unit pair in swapped roles (e.g., Card 1: A top + B partner, Card 2: B top + A partner), the UI shows duplicate combos.

## Solution

Post-filter cards in `_buildTopColumn` using a seen-set of normalized unit pairs. The first card with a given pair wins (since `topUnits` is pre-sorted by score). Duplicate cards are dropped entirely.

## Scope

- **File:** `webapp/static/js/matchup_advisor.js`
- **Function:** `_buildTopColumn`
- **Change:** ~6 lines added between card construction (line 858) and zero-gap filtering (line 862)

## Logic

```javascript
const seenPairs = new Set();
cards = cards.filter(card => {
    if (!card.partner) return true;
    const key = [card.item.slug, card.partner.slug].sort().join("|");
    if (seenPairs.has(key)) return false;
    seenPairs.add(key);
    return true;
});
```

## Behavior

- Solo cards (no partner) are never filtered
- Applies to both gold+trash and gold+gold pairings
- First card always wins (higher-scored top unit keeps the combo)
- Dropped cards are removed entirely, not replaced with a fallback

## Edge Cases

- Only 1 top unit: no pair to check, no-op
- Partner is null (solo): passes through
- No duplicates exist: filter is a no-op
