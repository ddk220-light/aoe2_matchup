# AoE2 Replay Visualizer - Sprite Implementation Plan

## Overview

Replace geometric shapes with proper AoE2 sprites for units and buildings while maintaining player color visibility.

---

## Implementation Phases

### Phase 1: Add Text Labels for Verification
**Goal:** Add text labels below each unit/building showing the detected type, so we can verify the classification is correct.

- [ ] Modify `renderer.js` to display type text below units
- [ ] Modify `renderer.js` to display type text below buildings
- [ ] Test with a replay to verify all types are correctly identified
- [ ] Git commit: "Add debug text labels to verify unit/building type detection"

**Learnings to capture:**
- Which unit types appear most frequently
- Any misclassified units
- Building types that need better detection

---

### Phase 2: Download and Catalog Sprites
**Goal:** Download all available sprites and create a mapping file linking sprite images to unit/building type names.

- [ ] Create `/visualizer/public/assets/sprites/` directory structure
- [ ] Download unit sprites from The Spriters Resource
- [ ] Download building sprites
- [ ] Create `sprite_catalog.md` with image previews and type mappings
- [ ] Create `sprites.json` metadata file
- [ ] Git commit: "Add sprite assets and catalog for verification"

**Directory structure:**
```
visualizer/public/assets/sprites/
├── units/
│   ├── villager.png
│   ├── infantry.png
│   ├── archer.png
│   ├── cavalry.png
│   ├── siege.png
│   ├── monk.png
│   ├── ship.png
│   ├── king.png
│   └── military.png
├── buildings/
│   ├── towncenter.png
│   ├── castle.png
│   ├── barracks.png
│   ├── archeryrange.png
│   ├── stable.png
│   ├── siegeworkshop.png
│   ├── monastery.png
│   ├── university.png
│   ├── market.png
│   ├── blacksmith.png
│   ├── mill.png
│   ├── lumbercamp.png
│   ├── miningcamp.png
│   ├── dock.png
│   └── house.png
└── sprites.json
```

**Learnings to capture:**
- Which sprites look best at small sizes
- Any missing unit/building types
- Sprite quality and visibility concerns

---

### Phase 3: Implement 3 Test Sprites
**Goal:** Replace 3 unit types with actual sprites to test the rendering system.

Test sprites:
1. `villager` - Most common unit
2. `cavalry` - Distinct shape, easy to verify
3. `towncenter` - Key building

- [ ] Implement sprite loading system in `renderer.js`
- [ ] Implement player color overlay (glow/border)
- [ ] Replace villager rendering with sprite
- [ ] Replace cavalry rendering with sprite
- [ ] Replace towncenter rendering with sprite
- [ ] Keep fallback to geometric shapes for other types
- [ ] Test locally with replay
- [ ] Git commit: "Implement sprite rendering for villager, cavalry, and towncenter"

**Learnings to capture:**
- Performance impact of sprite rendering
- Player color visibility with sprites
- Zoom level behavior
- Any rendering issues

---

### Phase 4: Replace All Sprites and Deploy
**Goal:** Replace all remaining unit and building types with sprites, then deploy to Railway.

- [ ] Replace all remaining unit sprites (infantry, archer, siege, monk, ship, king, military)
- [ ] Replace all remaining building sprites
- [ ] Test all zoom levels
- [ ] Test with multiple replays
- [ ] Remove debug text labels (or make them optional)
- [ ] Git commit: "Complete sprite implementation for all units and buildings"
- [ ] Push to Railway
- [ ] Verify deployment works

**Learnings to capture:**
- Final performance metrics
- User feedback on visibility
- Any edge cases or issues

---

## Current State

### Unit Types (from `renderer.js`)

| Type | Current Shape | Size | Frequency |
|------|---------------|------|-----------|
| `villager` | Circle | 5px | Very High |
| `infantry` | Shield/rounded rect | 6px | High |
| `archer` | Diamond with arrow | 6px | High |
| `cavalry` | Horizontal oval | 8px | Medium |
| `siege` | Square | 10px | Low |
| `monk` | Cross | 5px | Low |
| `ship` | Boat shape | 12px | Rare |
| `king` | Circle with crown | 6px | Rare |
| `military` (default) | Triangle | 6px | Medium |

### Building Types

| Type | Current Shape | Size |
|------|---------------|------|
| Small buildings (house, farm, etc.) | Isometric diamond | 12px |
| Large buildings (barracks, stable, etc.) | Isometric diamond + inner detail | 20px |
| Town Center | Diamond with roof & flag | 28px |
| Castle | Diamond with 4 corner towers | 32px |

### Large Buildings Set
```
monastery, university, siegeworkshop, stable, archeryrange,
barracks, market, blacksmith, mill, lumbercamp, miningcamp, dock, harbor
```

---

## Player Color System

To maintain player identification with sprites:

**Recommended: Colored Glow/Border**
```javascript
drawSpriteWithPlayerColor(sprite, x, y, playerColor, size) {
  // Draw colored glow behind sprite
  ctx.shadowColor = playerColor;
  ctx.shadowBlur = 6;
  ctx.drawImage(sprite, x - size/2, y - size/2, size, size);
  ctx.shadowBlur = 0;
}
```

**Alternative: Colored Base Circle**
```javascript
drawSpriteWithPlayerColor(sprite, x, y, playerColor, size) {
  // Draw colored circle base
  ctx.fillStyle = playerColor;
  ctx.beginPath();
  ctx.arc(x, y, size/2 + 3, 0, Math.PI * 2);
  ctx.fill();
  
  // Draw sprite on top
  ctx.drawImage(sprite, x - size/2, y - size/2, size, size);
}
```

---

## Sprite Sources

| Source | URL | Assets |
|--------|-----|--------|
| The Spriters Resource | [Link](https://www.spriters-resource.com/pc_computer/ageofempiresii/) | Unit icons, Building icons |
| Unit Icons | [Link](https://www.spriters-resource.com/pc_computer/ageofempiresii/asset/118253/) | 564x553px PNG |
| Building Icons | [Link](https://www.spriters-resource.com/pc_computer/ageofempiresii/asset/51446/) | 590x255px PNG |

---

## Learnings Log

### Phase 1 Learnings
_(To be filled after Phase 1 completion)_

### Phase 2 Learnings
_(To be filled after Phase 2 completion)_

### Phase 3 Learnings
_(To be filled after Phase 3 completion)_

### Phase 4 Learnings
_(To be filled after Phase 4 completion)_

---

## Progress Tracking

| Phase | Status | Commit | Date |
|-------|--------|--------|------|
| Phase 1: Text Labels | Complete | 9e12a12 | 2026-01-28 |
| Phase 2: Download Sprites | In Progress | - | - |
| Phase 3: Test 3 Sprites | Not Started | - | - |
| Phase 4: All Sprites + Deploy | Not Started | - | - |

## Learnings Log

### Phase 1 Learnings
- Unit type detection was flawed - was matching wrong training events to units
- Fixed by tracking training queue per player and matching unused events to new units
- Units now correctly show types like `archer`, `scoutcavalry`, `knight` instead of `villager`
- Some units still show as `unit` when no matching training event found
- Labels work well at zoom > 0.5, hidden when zoomed out to reduce clutter
