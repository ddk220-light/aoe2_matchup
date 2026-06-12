# Claude's Notes on AoE2 Replay Analysis

This document captures lessons learned while building tools to analyze Age of Empires II: Definitive Edition replay files.

## Parsing Library

### mgz (aoc-mgz)
- **Library**: `mgz` (https://github.com/happyleavesaoc/aoc-mgz)
- **Install**: `pip install mgz`
- **Version matters**: Newer AoE2 DE replays require mgz 1.8.46+. Earlier versions may fail with "could not read enough bytes" errors.

### Basic Usage
```python
import mgz
import mgz.model

with open("replay.aoe2record", "rb") as f:
    match = mgz.model.parse_match(f)
```

## Key Data Structures

### Match Object
- `match.duration` - Total game duration (timedelta)
- `match.map.name` - Map name (e.g., "Land Nomad")
- `match.map.size` - Map size (e.g., "Large")
- `match.players` - List of Player objects
- `match.actions` - List of all actions in the game

### Player Object
- `player.name` - Player name
- `player.civilization` - Civilization name
- `player.civilization_id` - Numeric civilization ID
- `player.color_id` - Player color (0-7)
- `player.winner` - Boolean, whether player won
- `player.objects` - Starting units/buildings (list of objects with `instance_id`, `name`)

### Action Object
- `action.timestamp` - When the action occurred (timedelta)
- `action.type` - Action type enum (e.g., `Action.MOVE`, `Action.BUILD`)
- `action.player` - Player who issued the action
- `action.position` - Position object with `.x` and `.y` (may be None)
- `action.payload` - Dictionary with action-specific data

## Coordinate System

### Game Coordinates
- AoE2 uses a coordinate system where (0,0) is one corner of the map
- For a "Large" map, coordinates range from 0 to ~220
- X and Y increase in perpendicular directions

### Isometric Visualization
The game displays the map as a diamond (isometric view). To convert game coordinates to screen coordinates:

```javascript
// Diamond orientation: (0,0) at left, X goes to top, Y goes to bottom
const isoX = (gameX + gameY) * (tileWidth / 2);
const isoY = (gameY - gameX) * (tileHeight / 2);
```

This places:
- **(0, 0)** at the **left** corner of the diamond
- **(maxX, 0)** at the **top** corner
- **(0, maxY)** at the **bottom** corner
- **(maxX, maxY)** at the **right** corner

## Unit Identification

### Instance IDs
- Each unit has a unique `instance_id` that persists throughout the game
- Starting units have their IDs in `player.objects`
- New units get IDs when they're first commanded

### Unit Ownership
Units belong to the **first player who commands them**, not necessarily who issued a specific action. Build a lookup map:

```python
unit_owner_map = {}

# Starting units belong to their player
for player in match.players:
    if player.objects:
        for obj in player.objects:
            unit_owner_map[obj.instance_id] = player.name

# Other units belong to first player to command them
for action in match.actions:
    if action.player and action.payload:
        for obj_id in action.payload.get("object_ids", []):
            if obj_id not in unit_owner_map:
                unit_owner_map[obj_id] = action.player.name
```

### Identifying Villagers
Villagers are identified by checking if they ever issue a `BUILD` action:

```python
villager_ids = set()
for action in match.actions:
    if str(action.type) == "Action.BUILD":
        for obj_id in action.payload.get("object_ids", []):
            villager_ids.add(obj_id)
```

### Identifying Unit Types
For non-villager units, match them with training events based on timing:

```python
training_events = []
for action in match.actions:
    if str(action.type) == "Action.DE_QUEUE":
        training_events.append({
            "time": action.timestamp.total_seconds(),
            "player": action.player.name,
            "unit_type": action.payload.get("unit", "unit"),
        })

# When a new unit appears, find the most recent training event
# from the same player that occurred before the unit was first seen
```

## Common Action Types

| Action Type | Description | Key Payload Fields |
|-------------|-------------|-------------------|
| `MOVE` | Unit movement | `object_ids` |
| `BUILD` | Construct building | `object_ids`, `building_id`, position |
| `ORDER` | Attack/interact | `object_ids`, `target_id`, position |
| `DE_QUEUE` | Train unit | `object_ids` (building), `unit`, `unit_id`, `amount` |
| `RESEARCH` | Research tech | `object_ids` (building), `technology` |
| `STANCE` | Change stance | `object_ids`, `stance` (0-3) |
| `FORMATION` | Change formation | `object_ids`, `formation` |
| `PATROL` | Set patrol | `object_ids`, position |
| `GARRISON` | Enter building | `object_ids` |
| `UNGARRISON` | Exit building | `object_ids` |
| `DELETE` | Delete unit | `object_ids` |
| `GAME` | Game commands | `command` (e.g., "Farm Autoqueue") |

## Death Detection

The replay doesn't explicitly record unit deaths. Estimate deaths by:

1. Track the last time each unit was commanded
2. If a military unit hasn't been commanded for 5+ minutes before the game ends, assume it died
3. Estimated death time = last_command_time + 5 minutes

```python
DEATH_THRESHOLD = 5 * 60  # 5 minutes in seconds

for unit_id, actions in unit_actions.items():
    last_action_time = actions[-1]["timestamp_seconds"]
    time_since_last = match_duration - last_action_time
    
    if time_since_last > DEATH_THRESHOLD:
        likely_died = True
        estimated_death_time = last_action_time + DEATH_THRESHOLD
```

## Reference Data

### Object Names (aocref)
```python
import aocref
import os
import json

aocref_path = os.path.dirname(aocref.__file__)
dataset_file = os.path.join(aocref_path, "data", "datasets", "100.json")

with open(dataset_file, "r") as f:
    data = json.load(f)
    object_names = data.get("objects", {})  # {id: name}
```

### Player Colors
Standard AoE2 player colors:
| color_id | Color |
|----------|-------|
| 0 | Blue (#0042FF) |
| 1 | Red (#FF0000) |
| 2 | Green (#00FF00) |
| 3 | Yellow (#FFFF00) |
| 4 | Cyan (#00FFFF) |
| 5 | Purple (#FF00FF) |
| 6 | Grey (#808080) |
| 7 | Orange (#FFA500) |

## Unit Stats

Unit stats can be fetched from the aoe2techtree repository:
```
https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/master/data/data.json
```

Key stats: HP, Attack, MeleeArmor, PierceArmor, Speed, Range, TrainTime, Cost

## Common Pitfalls

1. **Position can be None**: Always check `if action.position` before accessing `.x` and `.y`

2. **Payload can be None**: Always use `action.payload or {}` 

3. **Action type is an enum**: Convert with `str(action.type).replace("Action.", "")`

4. **Unit IDs in actions may not exist yet**: Units created mid-game won't be in `player.objects`

5. **Multiple units in one action**: `object_ids` is a list - many actions affect multiple units

6. **Coordinate system varies**: Game coords vs screen coords vs isometric - keep track of which you're using

## File Processing Notes

### File Handle Requirements
- mgz requires a proper file handle opened in binary mode (`"rb"`)
- When processing uploaded files (e.g., from Flask), save to a temp file first:

```python
import tempfile
import os

with tempfile.NamedTemporaryFile(suffix=".aoe2record", delete=False) as tmp:
    uploaded_file.save(tmp.name)
    tmp_path = tmp.name

try:
    with open(tmp_path, "rb") as f:
        match = mgz.model.parse_match(f)
finally:
    os.unlink(tmp_path)
```

### Map Size Detection
- Map sizes are typically: Tiny (120), Small (144), Medium (168), Normal (200), Large (220), Giant (240), Ludicrous (480)
- The `match.map.size` attribute contains the size name, not the numeric value
- For visualization, Large maps (220x220) are the most common

## JSON Export Structure

When exporting replay data for visualization, use this structure:

```python
data = {
    "match": {
        "map_name": str,
        "map_size": int,  # e.g., 220
        "duration_seconds": float,
        "duration_formatted": str,  # "HH:MM:SS"
    },
    "players": [
        {
            "name": str,
            "color_id": int,
            "color_hex": str,
            "color_name": str,
            "civilization": str,
        }
    ],
    "starting_units": [
        {
            "id": str,  # unique name like "villager_PlayerName_1"
            "instance_id": int,
            "player": str,
            "type": str,  # "villager" or "military"
            "x": float or None,
            "y": float or None,
        }
    ],
    "actions": [
        {
            "id": int,
            "time": float,  # seconds
            "player": str,
            "type": str,  # action type
            "subjects": [str],  # unit names
            "target": str,  # building/unit/tech name
            "x": float or None,
            "y": float or None,
            "amount": int or None,
        }
    ],
    "unit_deaths": {
        "unit_name": float,  # death time in seconds
    }
}
```
