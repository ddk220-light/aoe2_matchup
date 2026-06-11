# AoE2 Replay Visualizer - Developer Guide

This document describes the architecture and implementation of the AoE2 Replay Visualizer.

## Project Overview

A browser-based tool to visualize Age of Empires II: Definitive Edition replay files (`.aoe2record`). Users can upload replay files, watch unit movements on an isometric map, and control playback.

## Repo layout (since 2026-06-10)

- `visualizer/` — the deployed product (everything below in this guide). The root
  Dockerfile copies ONLY this directory.
- `lab/` — the ground-truth research toolkit, merged in from the formerly standalone
  `aoe2grpc` repo (github.com/ddk220-light/aoe2grpc is now a frozen archive). It captures
  live games over the game's gRPC API, decodes state, extracts per-unit truth labels, and
  scores/improves `visualizer/unit_classifier.py`. See `lab/README.md` and
  `lab/_improve/REPORT.md`.
  - Scorer pattern: `cd lab`, set `$env:UC_DIR` to a directory containing a candidate
    `unit_classifier.py` (+ `train_times.json`), then
    `python _improve\score_game.py <replay> <labels.json> <end_min>`.
  - Lab data files (GB-scale `.bin` captures, `*.aoe2record`, keys/certs) are gitignored
    via `lab/.gitignore` and must NEVER be committed.
- `docs/ANALYZER_SYNC.md` — standing guide for syncing replay features downstream into
  the aoe2-unit-analyzer website (which embeds a fork of this viewer under `/replay`).
  This repo is canonical; develop replay features here first.
- Deploy caution: prefer git-push deploys (Option 1 below). `railway up` uploads the
  local build context; `.dockerignore`/`.railwayignore` exclude `lab/` to keep that sane.

## Architecture

```
visualizer/
├── server.py          # Flask backend - handles file uploads, match browsing, replay downloads
├── players.csv        # List of tracked players (name, profileId)
├── public/
│   ├── index.html     # Main HTML structure with match browser modals
│   ├── style.css      # Styling (full-screen map layout, modal panels)
│   └── app.js         # Main application controller with match browsing
├── renderer.js        # Canvas rendering (isometric projection)
├── playback.js        # Game state and animation engine
├── generate_data.py   # CLI tool to export replay to JSON
├── fetch_matches.py   # Prototype script for API testing
└── replay_data.json   # Pre-generated replay data (optional)
```

## Components

### Backend (server.py)

Flask server that:
- Serves static files (HTML, CSS, JS)
- Handles file uploads at `/api/upload` (POST)
- Processes `.aoe2record` files using mgz library
- Fetches match history from AoE2 Companion API
- Downloads and processes replays from aoe.ms
- Returns JSON data for the frontend

**Key endpoints:**
```
GET /api/matches
- Fetches recent Land Nomad matches from all players in players.csv
- Deduplicates matches, returns latest 25
- Returns: JSON array of match objects

GET /api/matches/<player_name>
- Fetches last 10 matches for a specific player
- Returns: JSON array of match objects

POST /api/load-match
- Accepts: JSON with match_id and profile_id
- Downloads replay ZIP from aoe.ms, extracts .aoe2record, parses with mgz
- Returns: JSON with match data, players, actions, units

POST /api/upload
- Accepts: multipart/form-data with 'file' field
- Returns: JSON with match data, players, actions, units
```

**External APIs:**
- AoE2 Companion API: `https://data.aoe2companion.com/api` (requires User-Agent header)
- Replay downloads: `https://aoe.ms/replay/?gameId={matchId}&profileId={profileId}`

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
- Handles file upload UI and match browsing
- Manages playback controls (play/pause, speed, timeline)
- Sets up keyboard shortcuts
- Manages player visibility toggles
- Fetches and displays match history from tracked players

**Key methods:**
- `init()` - Loads default replay or shows upload prompt
- `uploadReplay(file)` - Sends file to server, reinitializes on success
- `setupUI()` - Binds event listeners (only once via `controlsInitialized` flag)
- `togglePlay()` - Play/pause control
- `startRenderLoop()` - 60fps render loop using requestAnimationFrame
- `fetchMatches()` - Fetches Land Nomad matches from all tracked players
- `renderMatchList(matches)` - Displays match list in modal panel
- `renderMatchDetail(match)` - Shows match details with teams, civs, ratings
- `loadMatch(matchId, profileId)` - Downloads and loads a replay from aoe.ms
- `setupPlayerLegend()` - Creates player list grouped by team with civilizations
- `updatePlayerTracker(time)` - Updates production rates display with color coding
- `calculateProductionRates(time)` - Calculates villager/military production per minute

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

**Team data from mgz:**
- `player.team` returns a list of `Player` objects (not strings)
- Must convert to strings with `[str(tm) for tm in player.team]` for JSON serialization
- Team list includes the player themselves along with their teammates

### CSS Layout

Full-screen layout with:
- Header bar (title, match info, browse matches button)
- Map container (flex: 1, fills available space)
- Info panel (overlaid on map, top-left):
  - Player legend with team grouping and civilization display
  - Player production tracker (villagers/min, military/min)
- Controls panel (fixed at bottom)
- Match list modal (overlay panel for browsing matches)
- Match detail modal (overlay panel for viewing match details before loading)

## Data Flow

### Direct Upload Flow
1. **Upload:** User selects `.aoe2record` file
2. **Process:** Flask saves to temp file, parses with mgz, extracts data
3. **Return:** JSON with match info, players, units, actions
4. **Initialize:** Frontend creates Renderer and Playback with data
5. **Render:** 60fps loop calls `playback.getState()` and `renderer.render(state)`
6. **Animate:** Playback advances time, interpolates unit positions

### Match Browser Flow
1. **Browse:** User clicks "Browse Matches" button
2. **Fetch:** Frontend calls `/api/matches` to get Land Nomad matches from tracked players
3. **Display:** Match list modal shows recent matches with map, date, players
4. **Select:** User clicks a match to see details (teams, civs, ratings, winner)
5. **Load:** User clicks "Load Replay" button
6. **Download:** Server fetches ZIP from aoe.ms, extracts .aoe2record, parses with mgz
7. **Initialize:** Same as direct upload flow from step 4

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

## Configuration

### players.csv

CSV file containing tracked players for match browsing:
```csv
name,profileId
ddk220,612690
Arkantos12,1314165
...
```

The server loads this file to fetch matches from all tracked players. Matches are:
- Fetched in batches from AoE2 Companion API
- Deduplicated by matchId
- Filtered to only include "Land Nomad" maps
- Sorted by date (newest first)
- Limited to 25 matches

## Dependencies

**Python:**
- Flask, flask-cors - Web server
- mgz - AoE2 replay parser
- aocref - Object name lookups
- requests - HTTP client for API calls

**Frontend:**
- Vanilla JavaScript (no frameworks)
- HTML5 Canvas for rendering

## Sprite System

The visualizer uses PNG sprites for units and buildings instead of geometric shapes.

**Sprite locations:**
- `visualizer/public/assets/sprites/units/` - Unit sprites (villager, knight, archer, etc.)
- `visualizer/public/assets/sprites/buildings/` - Building sprites (towncenter, castle, etc.)
- `visualizer/public/assets/sprites/sprites.json` - Metadata mapping unit/building types to sprite files

**Sprite rendering features:**
- Units rendered with circular player-color backgrounds
- Buildings rendered with isometric diamond player-color backgrounds and transformed sprites
- Building opacity: 100% for first 30s, fades to 50% at 30s, then to 25% by 5 minutes
- Idle villagers (30s+ no action): 50% opacity, fading to 25% by 5 minutes, rendered below active units
- Attack arrows: Drawn from attacker to target in player color, visible for 5 seconds after attack command
- Ranged units (archer, siege): Stay at distance when attacking instead of moving to target

**Player info panel features:**
- Player legend groups players by team (Team 1, Team 2, etc.)
- Civilization shown in brackets next to player name
- Player production tracker shows real-time villagers/min and military/min rates
- Production rates color-coded: green (#1), light green (top 3), red (last), light red (bottom 3)

**Adding new sprites:**
1. Add PNG file to appropriate directory (48x48 recommended, transparent background)
2. Update `sprites.json` with the mapping
3. Renderer will automatically load and use the sprite if exact name match exists

## Railway Deployment

The app is deployed to Railway at: https://aoe2-replay-visualizer.up.railway.app

### Project Structure for Railway

Railway requires a `Dockerfile` at the **root level** of the repository. The current setup:

```
/Dockerfile              # Root Dockerfile that copies from visualizer/
/visualizer/
  /Dockerfile            # Original Dockerfile (not used by Railway)
  /requirements.txt
  /server.py
  /public/
  ...
```

The root `Dockerfile` copies files from the `visualizer/` subdirectory:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY visualizer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY visualizer/ .
EXPOSE 8000
CMD ["/bin/sh", "-c", "gunicorn server:app --bind 0.0.0.0:${PORT:-8000}"]
```

### Deployment Commands

**Link to Railway project (first time):**
```bash
railway link --project aoe2-replay-visualizer --service aoe2-replay-visualizer --environment production
```

**Deploy new changes:**
```bash
# Option 1: Push to main branch (auto-deploys if connected to GitHub)
git push origin main

# Option 2: Manual deploy with railway CLI (uploads local files)
railway up --detach

# Option 3: Force redeploy of existing code
railway redeploy --yes
```

**Monitor deployment:**
```bash
# Check build logs
railway logs --build

# Check runtime logs
railway logs --tail 50

# Check status
railway status
```

### Common Railway Issues

1. **"Railpack could not determine how to build the app"**: Railway's auto-detection failed. Ensure `Dockerfile` exists at the repository root (not in a subdirectory).

2. **"No changes to watched files"**: The `railway redeploy` command reuses cached code. Use `railway up` to upload fresh code.

3. **Build uses old code**: Railway caches builds. Either:
   - Make a change to force a new build
   - Use `railway up` instead of `railway redeploy`
   - Clear build cache in Railway dashboard

4. **Dockerfile not detected**: Railway may use Railpack instead of Dockerfile. Ensure:
   - `Dockerfile` is at repository root
   - File is named exactly `Dockerfile` (case-sensitive)
   - No `railway.json` with conflicting `watchPatterns`

5. **Service not linked**: Run `railway link` with project, service, and environment flags.

## Common Issues

1. **Port 5000 blocked:** macOS AirPlay uses port 5000. Use port 8000 instead.

2. **File upload fails:** Ensure Flask server is running, not simple HTTP server.

3. **Play button unresponsive:** Check browser console for errors. May be duplicate event listeners.

4. **Map squished:** Ensure `setupCanvas()` calculates proper fit scale.

5. **AoE2 Companion API 403 error:** Ensure User-Agent header is set in requests.

6. **Replay download fails:** Some replays may not be available on aoe.ms. Try a different match.

7. **Railway build cache:** If dependencies aren't updating, clear the build cache in Railway dashboard.

## Related Files

- `aoe2recordinsight.md` - Details on parsing `.aoe2record` files with mgz
- `README.md` - User-facing documentation
- `analyzers/` - Additional Python scripts for data extraction
