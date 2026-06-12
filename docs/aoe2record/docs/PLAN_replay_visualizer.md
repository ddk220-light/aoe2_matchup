# AoE2 Replay Visualizer - Implementation Plan

## Overview
Create a browser-based visualization tool that replays AoE2 game actions on an interactive map with playback controls.

## Data Summary
- **Map**: Land Nomad (Large) - 220x220 tile coordinate system
- **Duration**: 36 minutes 11 seconds
- **Players**: 8
- **Total Actions**: 9,036 actions to visualize
- **Units/Buildings**: ~1,734 entities to track

## Architecture

### Files to Create
```
/Users/deepak/Documents/AI/aoe2record/visualizer/
├── index.html          # Main HTML page
├── style.css           # Styling for the visualizer
├── app.js              # Main application logic
├── renderer.js         # Canvas rendering functions
├── playback.js         # Playback control logic
├── data-loader.js      # Load and parse game data
└── generate_data.py    # Python script to export replay data as JSON
```

### Step 1: Data Export (Python)
Create `generate_data.py` to export replay data as JSON for the browser:

**Output: `replay_data.json`**
```json
{
  "match": {
    "map_name": "Land Nomad",
    "map_size": 220,
    "duration_seconds": 2171.9,
    "duration_formatted": "36:11"
  },
  "players": [
    {"name": "ddk220", "color_id": 3, "color_hex": "#00FF00"},
    ...
  ],
  "actions": [
    {
      "id": 1,
      "time": 0.416,
      "player": "newisyou",
      "type": "GAME",
      "subject": "",
      "target": "",
      "x": null,
      "y": null,
      "details": "Farm Autoqueue"
    },
    {
      "id": 13,
      "time": 1.56,
      "player": "TiShi",
      "type": "MOVE",
      "subject": "villager_TiShi_1, villager_TiShi_2, villager_TiShi_3",
      "target": "",
      "x": 5.0,
      "y": 66.4,
      "details": ""
    },
    ...
  ],
  "starting_units": [
    {"id": "villager_ddk220_1", "player": "ddk220", "type": "villager", "x": 180, "y": 30},
    ...
  ]
}
```

### Step 2: HTML Structure (`index.html`)
```
┌─────────────────────────────────────────────────────────────┐
│  AoE2 Replay Visualizer - Land Nomad                        │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  │                    MAP CANVAS                         │  │
│  │                   (zoomable)                          │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  [|<] [<] [Play/Pause] [>] [>|]   00:00 / 36:11   [1x][2x]  │
│  ════════════════════●══════════════════════════════════    │
│                   Timeline Scrubber                          │
├─────────────────────────────────────────────────────────────┤
│  Player Legend:                                              │
│  ● ddk220  ● mutanT  ● Maximus  ● TiShi  ...               │
├─────────────────────────────────────────────────────────────┤
│  Action Log (scrollable):                                   │
│  [0:01] TiShi: MOVE villager_TiShi_1 to (5.0, 66.4)        │
│  [0:02] ddk220: MOVE villager_ddk220_3 to (186.0, 32.5)    │
└─────────────────────────────────────────────────────────────┘
```

### Step 3: Canvas Rendering (`renderer.js`)

**Map Canvas Features:**
- Base canvas size: 880x880 pixels (4 pixels per game tile)
- Zoom levels: 0.5x, 1x, 2x, 4x
- Pan with mouse drag
- Coordinate grid overlay (optional toggle)

**Sprite Placeholders (simple shapes):**
| Entity Type | Shape | Size |
|-------------|-------|------|
| Villager | Circle | 6px |
| Military Unit | Triangle | 8px |
| Scout | Diamond | 8px |
| Building (small) | Square | 12px |
| Building (large) | Square | 20px |
| Town Center | Square | 24px |

**Color Mapping (AoE2 standard):**
| color_id | Color Name | Hex |
|----------|------------|-----|
| 0 | Blue | #0000FF |
| 1 | Red | #FF0000 |
| 2 | Green | #00FF00 |
| 3 | Yellow | #FFFF00 |
| 4 | Cyan | #00FFFF |
| 5 | Purple | #FF00FF |
| 6 | Grey | #808080 |
| 7 | Orange | #FFA500 |

### Step 4: Playback System (`playback.js`)

**State Management:**
```javascript
state = {
  currentTime: 0,          // Current playback time in seconds
  isPlaying: false,
  playbackSpeed: 1,        // 1x, 2x, 4x, 8x
  entities: Map(),         // unit_name -> {x, y, type, player, alive}
  buildings: Map(),        // building_name -> {x, y, type, player}
  actionIndex: 0,          // Current position in actions array
}
```

**Playback Logic:**
1. On play: Start animation loop (requestAnimationFrame)
2. Each frame:
   - Advance currentTime by (deltaTime * playbackSpeed)
   - Process all actions where action.time <= currentTime
   - Update entity positions for MOVE actions
   - Add buildings for BUILD actions
   - Show attack indicators for ORDER actions
   - Mark units as dead based on journey data
3. Render current state to canvas

**Action Processing:**
| Action Type | Visual Effect |
|-------------|---------------|
| MOVE | Animate unit from current pos to new pos |
| BUILD | Place building sprite at position |
| ORDER | Draw line from unit to target position |
| STANCE | Change unit indicator (optional) |
| DE_QUEUE | Flash building (training) |
| RESEARCH | Flash building (researching) |
| GARRISON | Hide unit |
| UNGARRISON | Show unit at building |
| DELETE | Remove unit |

### Step 5: Zoom & Pan (`renderer.js`)

**Zoom Implementation:**
- Mouse wheel: zoom in/out centered on cursor
- Zoom buttons: zoom in/out centered on viewport
- Maintain zoom level: 0.5x to 4x

**Pan Implementation:**
- Click and drag to pan
- Keep map bounds (don't pan beyond edges)
- Mini-map in corner showing viewport position (optional)

### Step 6: UI Controls (`app.js`)

**Playback Controls:**
- Play/Pause button (spacebar shortcut)
- Step forward/backward (arrow keys)
- Jump to start/end
- Speed control: 1x, 2x, 4x, 8x
- Timeline scrubber (click to seek)

**Display Options:**
- Toggle player visibility (checkboxes)
- Toggle action log
- Toggle coordinate grid
- Toggle unit trails (show movement history)

## Implementation Order

1. **generate_data.py** - Export replay data to JSON
2. **index.html + style.css** - Basic page structure and styling
3. **data-loader.js** - Load JSON data
4. **renderer.js** - Basic map rendering with static sprites
5. **playback.js** - Playback controls and action processing
6. **app.js** - Wire everything together
7. **Polish** - Add zoom/pan, action log, player toggles

## Technical Notes

- Use vanilla JavaScript (no frameworks) for simplicity
- Canvas 2D API for rendering
- JSON data file loaded via fetch()
- Local file serving required (use `python -m http.server`)

## Testing

Run with:
```bash
cd /Users/deepak/Documents/AI/aoe2record/visualizer
python -m http.server 8000
# Open http://localhost:8000 in browser
```

## Estimated Complexity

| Component | Lines of Code (approx) |
|-----------|------------------------|
| generate_data.py | 150 |
| index.html | 80 |
| style.css | 120 |
| data-loader.js | 50 |
| renderer.js | 200 |
| playback.js | 180 |
| app.js | 150 |
| **Total** | **~930** |
