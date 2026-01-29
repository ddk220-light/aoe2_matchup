# AoE2 Replay Visualizer - Sprite Implementation Plan

## Overview

This document outlines the plan for implementing proper sprites to replace the current geometric shapes (circles, triangles, diamonds) used for units and buildings in the replay visualizer.

## Current State

### Unit Types (from `renderer.js`)
Currently rendered as geometric shapes with player-colored backgrounds:

| Type | Current Shape | Size |
|------|---------------|------|
| `villager` | Circle | 5px |
| `infantry` | Shield/rounded rect | 6px |
| `archer` | Diamond with arrow | 6px |
| `cavalry` | Horizontal oval | 8px |
| `siege` | Square | 10px |
| `monk` | Cross | 5px |
| `ship` | Boat shape | 12px |
| `king` | Circle with crown | 6px |
| `military` (default) | Triangle | 6px |

### Building Types (from `renderer.js`)
| Type | Current Shape | Size |
|------|---------------|------|
| Small buildings | Isometric diamond | 12px |
| Large buildings | Isometric diamond with inner detail | 20px |
| Town Center | Diamond with roof & flag | 28px |
| Castle | Diamond with 4 corner towers | 32px |

### Large Buildings Set
```javascript
monastery, university, siegeworkshop, stable, archeryrange,
barracks, market, blacksmith, mill, lumbercamp, miningcamp, dock, harbor
```

## Sprite Resources

### Available Sources

1. **The Spriters Resource** - https://www.spriters-resource.com/pc_computer/ageofempiresii/
   - Unit Icons: 564x553px PNG sprite sheet
   - Building Icons: 590x255px PNG sprite sheet
   - Technology Icons: Available
   - Format: PNG with transparency

2. **AoE2 Game Files** (for extraction)
   - Location: `AoE2DE/resources/_common/drs/graphics/`
   - Format: `.smx` files (can be exported to PNG via SLX Studio)
   - Higher resolution available with Enhanced Graphics Pack

3. **AoE Fandom Wiki**
   - Individual unit/building sprites with neutral backgrounds
   - Useful for specific units not in sprite sheets

4. **AoEZone Community**
   - Full pack of AoE2 icons (units, buildings, techs, animals, heroes)
   - Available via Hermetica Discord

### Recommended Approach

Use **icon-style sprites** rather than full animation sprites because:
- Smaller file sizes (single image per unit type)
- Consistent visual style (top-down/isometric view)
- Easier to overlay with player colors
- Better visibility at various zoom levels

## Implementation Architecture

### 1. Sprite Atlas System

Create a sprite atlas (single image with all sprites) for efficient loading:

```
visualizer/public/assets/
├── sprites/
│   ├── units.png          # All unit icons in a grid
│   ├── buildings.png      # All building icons in a grid
│   └── sprites.json       # Sprite atlas metadata
```

**sprites.json format:**
```json
{
  "units": {
    "villager": { "x": 0, "y": 0, "width": 32, "height": 32 },
    "infantry": { "x": 32, "y": 0, "width": 32, "height": 32 },
    "archer": { "x": 64, "y": 0, "width": 32, "height": 32 },
    ...
  },
  "buildings": {
    "towncenter": { "x": 0, "y": 0, "width": 48, "height": 48 },
    "barracks": { "x": 48, "y": 0, "width": 32, "height": 32 },
    ...
  }
}
```

### 2. Player Color Overlay System

To maintain player color identification while using sprites:

**Option A: Colored Border/Glow (Recommended)**
```javascript
drawSpriteWithPlayerColor(sprite, x, y, playerColor) {
  // Draw colored glow/shadow behind sprite
  ctx.shadowColor = playerColor;
  ctx.shadowBlur = 8;
  ctx.shadowOffsetX = 0;
  ctx.shadowOffsetY = 0;
  
  // Draw the sprite
  ctx.drawImage(sprite, x, y);
  
  // Reset shadow
  ctx.shadowBlur = 0;
}
```

**Option B: Colored Base Circle**
```javascript
drawSpriteWithPlayerColor(sprite, x, y, playerColor, size) {
  // Draw colored circle base
  ctx.fillStyle = playerColor;
  ctx.beginPath();
  ctx.arc(x, y, size/2 + 2, 0, Math.PI * 2);
  ctx.fill();
  
  // Draw sprite on top
  ctx.drawImage(sprite, x - size/2, y - size/2, size, size);
}
```

**Option C: Color Tinting (Advanced)**
```javascript
drawTintedSprite(sprite, x, y, playerColor) {
  // Draw to temp canvas
  tempCtx.drawImage(sprite, 0, 0);
  
  // Apply color multiply blend
  tempCtx.globalCompositeOperation = 'multiply';
  tempCtx.fillStyle = playerColor;
  tempCtx.fillRect(0, 0, sprite.width, sprite.height);
  
  // Draw tinted result
  ctx.drawImage(tempCanvas, x, y);
}
```

### 3. Renderer Changes

Modify `renderer.js` to use sprites:

```javascript
class Renderer {
  constructor(canvas, mapSize = 220) {
    // ... existing code ...
    
    // Sprite system
    this.spritesLoaded = false;
    this.spriteAtlas = null;
    this.spriteData = null;
    
    // Load sprites
    this.loadSprites();
  }
  
  async loadSprites() {
    // Load sprite atlas image
    this.spriteAtlas = new Image();
    this.spriteAtlas.src = '/assets/sprites/units.png';
    
    // Load sprite metadata
    const response = await fetch('/assets/sprites/sprites.json');
    this.spriteData = await response.json();
    
    this.spriteAtlas.onload = () => {
      this.spritesLoaded = true;
    };
  }
  
  drawUnit(x, y, player, type, opacity = 1) {
    if (!this.spritesLoaded) {
      // Fallback to geometric shapes
      this.drawUnitFallback(x, y, player, type, opacity);
      return;
    }
    
    const pos = this.gameToCanvas(x, y);
    const color = this.playerColors[player] || "#ffffff";
    const spriteInfo = this.spriteData.units[type] || this.spriteData.units.military;
    const size = (this.sizes[type] || this.sizes.military) * this.zoom * 2;
    
    this.ctx.globalAlpha = opacity;
    
    // Draw player color indicator (glow or border)
    this.drawPlayerColorIndicator(pos.x, pos.y, color, size);
    
    // Draw sprite from atlas
    this.ctx.drawImage(
      this.spriteAtlas,
      spriteInfo.x, spriteInfo.y,           // Source position
      spriteInfo.width, spriteInfo.height,  // Source size
      pos.x - size/2, pos.y - size/2,       // Destination position
      size, size                            // Destination size
    );
    
    this.ctx.globalAlpha = 1;
  }
}
```

## Sprite Requirements

### Unit Sprites Needed

| Category | Units | Sprite Suggestion |
|----------|-------|-------------------|
| Villager | Male/Female villager | Single villager icon |
| Infantry | Militia, MAA, Long Swords, Champions, Spears, Pikes, Halbs | Swordsman icon |
| Archer | Archers, Crossbows, Arbs, Skirms, Cav Archers | Archer icon |
| Cavalry | Scouts, Knights, Cavaliers, Paladins, Hussars, Camels | Knight icon |
| Siege | Rams, Mangonels, Scorpions, Trebs, BBCs | Trebuchet icon |
| Monk | Monks, Missionaries | Monk icon |
| Ship | All naval units | Galley icon |
| King | Kings | King icon |

### Building Sprites Needed

| Category | Buildings | Sprite Suggestion |
|----------|-----------|-------------------|
| Town Center | TC | Town Center icon (large) |
| Castle | Castle | Castle icon (large) |
| Military | Barracks, Archery Range, Stable, Siege Workshop | Individual icons |
| Economy | Mill, Lumber Camp, Mining Camp, Market | Individual icons |
| Defense | Towers, Walls, Gates | Tower/wall icons |
| Other | Monastery, University, Blacksmith, Dock | Individual icons |

## Implementation Steps

### Phase 1: Setup (2-3 hours)
1. Create `/visualizer/public/assets/sprites/` directory
2. Download sprite sheets from The Spriters Resource
3. Create `sprites.json` metadata file with coordinates
4. Add sprite loading to `renderer.js`

### Phase 2: Unit Sprites (3-4 hours)
1. Implement `loadSprites()` method
2. Implement `drawSpriteWithPlayerColor()` method
3. Modify `drawUnit()` to use sprites
4. Test with all unit types
5. Implement fallback to geometric shapes if sprites fail to load

### Phase 3: Building Sprites (2-3 hours)
1. Add building sprites to atlas
2. Modify `drawBuilding()` to use sprites
3. Handle different building sizes
4. Test with all building types

### Phase 4: Polish (2-3 hours)
1. Optimize sprite rendering for performance
2. Add zoom-level-based sprite sizing
3. Implement sprite caching
4. Test at various zoom levels and with many units

## File Changes Summary

| File | Changes |
|------|---------|
| `visualizer/public/assets/sprites/units.png` | NEW - Unit sprite atlas |
| `visualizer/public/assets/sprites/buildings.png` | NEW - Building sprite atlas |
| `visualizer/public/assets/sprites/sprites.json` | NEW - Sprite metadata |
| `visualizer/renderer.js` | MODIFY - Add sprite loading and rendering |
| `visualizer/public/renderer.js` | MODIFY - Same as above (served copy) |

## Considerations

### Performance
- Use sprite atlases to minimize HTTP requests
- Pre-load sprites before starting playback
- Consider canvas caching for complex sprites

### Scalability
- Sprites should look good at 0.5x to 4x zoom
- Consider multiple resolution sprites for different zoom levels

### Fallback
- Keep geometric shape rendering as fallback
- Show loading indicator while sprites load

### Player Color Visibility
- Colored glow/border must be clearly visible
- Consider using contrasting outline for dark player colors

## Sources

- [The Spriters Resource - AoE2](https://www.spriters-resource.com/pc_computer/ageofempiresii/)
- [Unit Icons Sprite Sheet](https://www.spriters-resource.com/pc_computer/ageofempiresii/asset/118253/)
- [Building Icons Sprite Sheet](https://www.spriters-resource.com/pc_computer/ageofempiresii/asset/51446/)
- [Steam Community - Sprite Extraction](https://steamcommunity.com/app/813780/discussions/4/2951536988383052150/)
- [AoE2 Visual Modding Guide](https://alan.com.ar/posts/aoevisualmods/)
