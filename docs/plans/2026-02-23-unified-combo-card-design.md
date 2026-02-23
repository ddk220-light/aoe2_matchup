# Unified Combo Card — Matchup Advisor

## Goal

Replace the separate top unit card + sidekick sub-card + gold combo card with a single unified "combo card" format. The combo card shows the top unit + partner in one card, and only displays opponent units that neither can beat, with visual cues indicating the severity of each gap.

## Current State

- **Top unit card** (`_buildTopCard`): shows unit, "Beats X of Y", beaten icons, loss icons, then nested sidekick sub-cards
- **Sidekick sub-card**: nested inside top card, shows "Covers X of Y weaknesses", covered icons, "Neither can beat" gap icons
- **Gold combo card** (`_buildGoldComboCard`): separate card above top cards, shows two gold units with "+", "Together cover X of Y", covered icons, "Can't beat" gap icons

These three are replaced by one unified combo card.

## Unified Combo Card Layout

```
┌─ Combo Card ──────────────────────────────────┐
│ [header: "Best Combo" / "Gold Combo" / name]  │
│                                                │
│ [emblem] [icon] Paladin  +  [icon] Halberdier  │
│ Together handle X of Y opponent gold units      │
│                                                │
│ [only if gap > 0:]                             │
│ Can't beat:                                    │
│ [solid red] [dashed blue] [dashed orange]      │
└────────────────────────────────────────────────┘
```

Three variants, same component:
- **Gold + Trash** (has sidekick): header "Best Combo", two units with "+"
- **Gold + Gold** (gold partner): header "Gold Combo", two units with "+"
- **Solo** (no partner): header is unit name, no "+", gap = all losses/draws

## Gap Icon Visual Categories

For each opponent unit in the gap, compute the **best result from either combo unit**:

### Complete Loss — solid red border
- **Condition:** Neither unit wins either sim (pop or eco)
- **Style:** `2px solid #e74c3c`, full opacity
- **Meaning:** Opponent dominates both units completely

### Pop-Only Win — dashed blue border
- **Condition:** Best result is winning 30v30 only (pop efficient, not eco)
- **Style:** `2px dashed #3498db`, opacity 0.8
- **Meaning:** Win equal-numbers fights but lose on resource efficiency

### Eco-Only Win — dashed orange border
- **Condition:** Best result is winning 3k resource battle only (eco efficient, not pop)
- **Style:** `2px dashed #f39c12`, opacity 0.8
- **Meaning:** Resource efficient but lose equal-numbers fights

### Cross-unit coverage rule
If Unit A has pop-only win and Unit B has eco-only win against the same opponent, the opponent is **not in the gap** — the combo effectively covers it.

## Data Flow

All changes are frontend-only. No backend modifications. The sim data already provides `wins`, `pop_wins`, `eco_wins`, and `losses` for every unit.

### New: `_computeComboGap(topItem, partner, side, oppGoldSlugs)`

1. For each opponent gold slug, check both units' sim results
2. If either has it in `wins` → covered
3. If one has `pop_wins` and the other has `eco_wins` → covered
4. If best result is `pop_wins` only → gap with category `"pop"`
5. If best result is `eco_wins` only → gap with category `"eco"`
6. If neither has any win → gap with category `"loss"`
7. Returns `{ covered: count, total: oppGoldSlugs.size, gap: [{slug, category}] }`

### New: `_buildComboCard(topItem, partner, partnerType, civName, oppGoldSlugs, side)`

Single renderer for all three variants:
- `partnerType`: `"trash"` | `"gold"` | `null` (solo)
- Header label derived from partnerType
- Unit pair row: one or two units
- Summary: "Together handle X of Y" or "Handles X of Y" for solo
- Gap row: only if gap exists, icons styled per category

### Removed: `_buildTopCard`, `_buildGoldComboCard`

Replaced by `_buildComboCard`.

### Modified: `_buildTopColumn`

1. For each top unit, find best sidekick (existing `_computeSidekicks` logic)
2. If sidekick has no gap → combo card with trash partner
3. If sidekick has gap → also try gold combo; pick whichever has smaller gap
4. If no sidekick and no gold partner → solo card
5. Render one combo card per top unit

## CSS Changes

### New gap icon classes
```css
.ma-gap-icon.gap-loss { border: 2px solid #e74c3c; opacity: 1; }
.ma-gap-icon.gap-pop  { border: 2px dashed #3498db; opacity: 0.8; }
.ma-gap-icon.gap-eco  { border: 2px dashed #f39c12; opacity: 0.8; }
```

### Reused styles
- `.ma-gold-combo-card` — container for all combo variants
- `.ma-gold-combo-pair` — unit pair row with "+"
- `.ma-gold-combo-header`, `.ma-gold-combo-summary`
- `.ma-beats-icons`, `.ma-beats-icon`

### Removed styles (dead code)
- `.ma-sidekick-section`, `.ma-sidekick-card`, `.ma-sidekick-name-row`
- `.ma-sidekick-label`, `.ma-sidekick-name`, `.ma-sidekick-summary`
- `.ma-sidekick-covers-row`, `.ma-sidekick-gap-row`, `.ma-label-gap`

### Light mode
Add light mode overrides for `.gap-loss`, `.gap-pop`, `.gap-eco`.

## Files Modified

- `webapp/static/js/matchup_advisor.js`
- `webapp/static/css/matchup_advisor.css`
