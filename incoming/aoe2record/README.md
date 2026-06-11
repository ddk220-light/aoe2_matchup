# AoE2 Replay Analyzer & Visualizer

The canonical home of the AoE2:DE replay engine: Python tools to analyze Age of Empires II: Definitive Edition replay files (`.aoe2record`), a browser-based visualizer to watch the game unfold, and the ground-truth research lab that iterates on the unit classifier.

## Features

- **Extract game statistics** to CSV files (units, buildings, technologies, actions)
- **Track unit journeys** with full action history for each unit
- **Detect unit deaths** based on inactivity threshold
- **Browser-based visualizer** with isometric diamond map view
- **Playback controls** with variable speed and timeline scrubbing
- **Unit-type classifier** (`visualizer/unit_classifier.py`) that infers each unit's true type from the command stream alone — measured and improved against gRPC ground-truth labels in `lab/`

## Project Structure

```
aoe2record/
├── visualizer/          # THE PRODUCT — deployed to Railway (Dockerfile copies only this)
│   ├── server.py             # Flask backend (upload, player search, aoe.ms downloads, clips)
│   ├── unit_classifier.py    # Production classifier (improved 2026-06-10: military
│   │                         #   accuracy g0 80.9→84.7%, train 78.9→90.8%, holdout held)
│   ├── public/               # Viewer UI (app.js, renderer.js, playback.js, sprites)
│   └── generate_data.py      # Export replay to JSON for visualizer
├── lab/                 # THE LAB — ground-truth research toolkit (formerly the standalone
│   │                    #   aoe2grpc repo; that GitHub repo is now frozen as an archive).
│   │                    #   gRPC capture → state decode → per-unit truth labels →
│   │                    #   classifier scoring & improvement. See lab/README.md.
│   └── _improve/             # Scoring harness + improvement workspaces + REPORT.md
├── analyzers/           # Python analysis scripts (stats, journeys, deaths)
├── docs/                # Documentation (incl. ANALYZER_SYNC.md — how the matchup
│                        #   website pulls replay features from this repo)
├── replays/             # Place replay files here
└── download_replays.py  # Download replays from aoe2.net
```

## The iteration loop

Replay features and classifier improvements happen **here first**, then flow outward:

1. `lab/` improves the classifier against gRPC ground-truth labels
   (score with `cd lab; $env:UC_DIR='<candidate dir>'; python _improve\score_game.py <replay> <labels> <end_min>`)
2. A verified winner is copied to `visualizer/unit_classifier.py`
3. `git push origin main` deploys the visualizer to Railway
4. The matchup website (aoe2-unit-analyzer) pulls features downstream by following
   `docs/ANALYZER_SYNC.md`

Large lab data (GB-scale `.bin` gRPC captures, replays, keys) is gitignored and
never committed; `.dockerignore`/`.railwayignore` keep `lab/` out of deploys.

## Installation

### Prerequisites

- Python 3.8+
- pip

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/aoe2record.git
   cd aoe2record
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install mgz aocref
   ```

## Usage

### Extract Statistics to CSV

```bash
python analyzers/extract_stats.py your_replay.aoe2record
```

This creates a folder with 10 CSV files:
- `match_info.csv` - General match information
- `players.csv` - Player details
- `units.csv` - All units trained
- `buildings.csv` - All buildings constructed
- `technologies.csv` - All technologies researched
- `actions_summary.csv` - Actions per minute per player
- `unit_summary.csv` - Summary stats per unit
- `all_actions.csv` - Every action with full details
- `actions_readable.csv` - Human-readable action log with named units
- `player_totals.csv` - Aggregate stats per player

### Extract Unit Journeys

```bash
python analyzers/extract_journeys.py your_replay.aoe2record
```

Creates a CSV with one row per unit showing their complete action history.

### Use the Visualizer

1. Generate the JSON data:
   ```bash
   cd visualizer
   python generate_data.py
   ```

2. Start a local server:
   ```bash
   python -m http.server 8000
   ```

3. Open http://localhost:8000 in your browser

### Visualizer Controls

- **Space**: Play/Pause
- **Arrow keys**: Step forward/backward
- **1/2/4/8**: Set playback speed
- **Mouse wheel**: Zoom in/out
- **Click + drag**: Pan the map
- **Player checkboxes**: Toggle player visibility

## Map Orientation

The visualizer uses AoE2's isometric diamond view:
- **(0, 0)** is at the **left** corner
- **(max, 0)** is at the **top** corner  
- **(0, max)** is at the **bottom** corner
- **(max, max)** is at the **right** corner

## Dependencies

- [mgz](https://github.com/happyleavesaoc/aoc-mgz) - AoE2 recorded game parser
- [aocref](https://github.com/happyleavesaoc/aoc-mgz) - AoE2 reference data (unit names, etc.)

## License

MIT License
