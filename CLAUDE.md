# AoE2 Replay Visualizer - Developer Guide

This document describes the architecture and implementation of the AoE2 Replay Visualizer.

## Project Overview

A browser-based tool to visualize Age of Empires II: Definitive Edition replay files (`.aoe2record`). Users can upload replay files, watch unit movements on an isometric map, and control playback.

## Architecture

```
visualizer/
├── server.py          # Flask backend - handles file uploads and processing
├── index.html         # Main HTML structure
├── style.css          # Styling (full-screen map layout)
├── app.js             # Main application controller
├── renderer.js        # Canvas rendering (isometric projection)
├── playback.js        # Game state and animation engine
├── generate_data.py   # CLI tool to export replay to JSON
└── replay_data.json   # Pre-generated replay data (optional)
```

## Components

### Backend (server.py)

Flask server that:
- Serves static files (HTML, CSS, JS)
- Handles file uploads at `/api/upload` (POST)
- Processes `.aoe2record` files using mgz library
- Returns JSON data for the frontend

**Key endpoint:**
```
POST /api/upload
- Accepts: multipart/form-data with 'file' field
- Returns: JSON with match data, players, actions, units
```

**Running the server:**
```bash
cd visualizer
source ../venv/bin/activate
python3 server.py
# Opens at http://localhost:8000
```

### Frontend Components

#### app.js - Application Controller

Main orchestrator that:
- Initializes Renderer and Playback instances
- Handles file upload UI
- Manages playback controls (play/pause, speed, timeline)
- Sets up keyboard shortcuts
- Manages player visibility toggles

**Key methods:**
- `init()` - Loads default replay or shows upload prompt
- `uploadReplay(file)` - Sends file to server, reinitializes on success
- `setupUI()` - Binds event listeners (only once via `controlsInitialized` flag)
- `togglePlay()` - Play/pause control
- `startRenderLoop()` - 60fps render loop using requestAnimationFrame

#### renderer.js - Canvas Rendering

Handles all drawing operations with isometric projection.

**Coordinate System:**
```javascript
// Game coords (0,0) to (mapSize, mapSize) -> Isometric canvas coords
gameToCanvas(gameX, gameY) {
    const isoX = (gameX + gameY) * (tileWidth / 2) * zoom;
    const isoY = (gameY - gameX) * (tileHeight / 2) * zoom;
    return { x: panX + isoX, y: panY + isoY };
}
```

**Diamond orientation:**
- (0, 0) = Left corner
- (maxX, 0) = Top corner
- (0, maxY) = Bottom corner
- (maxX, maxY) = Right corner

**Key features:**
- Auto-scales to fit container while maintaining aspect ratio
- Mouse wheel zoom (centered on cursor)
- Click-and-drag panning
- Different shapes for unit types (circles=villagers, triangles=military)
- Isometric diamonds for buildings

#### playback.js - Game State Engine

Manages game state over time with smooth interpolation.

**Key concepts:**
- Pre-processes all actions into movement timelines per unit
- Interpolates unit positions between commands for smooth movement
- Tracks unit spawns, deaths, and deletions
- Handles building construction timeline

**State structure:**
```javascript
{
    units: Map<name, {x, y, player, type, alive, dying}>,
    buildings: Map<key, {x, y, player, type}>,
    currentTime: float
}
```

**Death detection:**
- Military units idle for 5+ minutes before game end are marked as dead
- Death time = last_command_time + 5 minutes
- Dying units (within 30s of death) rendered at 50% opacity

### CSS Layout

Full-screen layout with:
- Header bar (title, match info, upload button)
- Map container (flex: 1, fills available space)
- Info panel (overlaid on map, top-left)
- Controls panel (fixed at bottom)

## Data Flow

1. **Upload:** User selects `.aoe2record` file
2. **Process:** Flask saves to temp file, parses with mgz, extracts data
3. **Return:** JSON with match info, players, units, actions
4. **Initialize:** Frontend creates Renderer and Playback with data
5. **Render:** 60fps loop calls `playback.getState()` and `renderer.render(state)`
6. **Animate:** Playback advances time, interpolates unit positions

## Key Implementation Details

### Event Listener Management

To prevent duplicate listeners when uploading new replays:
```javascript
if (!this.controlsInitialized) {
    this.controlsInitialized = true;
    this.btnPlay.addEventListener("click", () => this.togglePlay());
    // ... other listeners
}
```

### Unit Position Interpolation

Units move smoothly between command positions:
```javascript
getUnitPosition(unit) {
    // Find prev and next movement commands around currentTime
    // Interpolate: pos = prev + (next - prev) * t
    const t = (currentTime - prevTime) / (nextTime - prevTime);
    return {
        x: prevX + (nextX - prevX) * t,
        y: prevY + (nextY - prevY) * t
    };
}
```

### Canvas Auto-Scaling

Map fits container while maintaining diamond aspect ratio:
```javascript
setupCanvas() {
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    
    const scaleX = canvas.width / mapPixelWidth;
    const scaleY = canvas.height / mapPixelHeight;
    const fitScale = Math.min(scaleX, scaleY) * 0.9;
    
    if (zoom === 1) zoom = fitScale;
}
```

## Dependencies

**Python:**
- Flask, flask-cors - Web server
- mgz - AoE2 replay parser
- aocref - Object name lookups

**Frontend:**
- Vanilla JavaScript (no frameworks)
- HTML5 Canvas for rendering

## Common Issues

1. **Port 5000 blocked:** macOS AirPlay uses port 5000. Use port 8000 instead.

2. **File upload fails:** Ensure Flask server is running, not simple HTTP server.

3. **Play button unresponsive:** Check browser console for errors. May be duplicate event listeners.

4. **Map squished:** Ensure `setupCanvas()` calculates proper fit scale.

## Related Files

- `aoe2recordinsight.md` - Details on parsing `.aoe2record` files with mgz
- `README.md` - User-facing documentation
- `analyzers/` - Additional Python scripts for data extraction
