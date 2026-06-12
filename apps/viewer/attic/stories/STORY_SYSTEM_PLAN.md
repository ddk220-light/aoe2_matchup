# Story Teller System - Implementation Plan

## Overview

A caption system that narrates interesting moments during replay playback. Captions appear at the bottom of the screen as events happen, providing playful commentary on player actions, achievements, and comparisons.

## Display Behavior

- **Position**: Bottom center of the map area, above the controls panel
- **Max visible**: Up to 3 captions at a time (stack vertically, newest at bottom)
- **Duration**: Each caption fades out after 5 seconds (real time, not game time)
- **Animation**: Fade in on appear, fade out on expire
- **Styling**: Semi-transparent dark background, white text, centered

## Story Trigger System

Stories are defined in `stories.json` and evaluated continuously during playback. Each story has:
- **Conditions**: When to trigger (time-based, event-based, comparative)
- **Template**: The caption text with placeholders for dynamic values
- **Priority**: Higher priority stories can bump lower ones if queue is full
- **Cooldown**: Minimum time between similar stories (prevent spam)

## Architecture

```
visualizer/
├── stories/
│   ├── stories.json        # Story definitions (editable)
│   ├── STORY_SYSTEM_PLAN.md # This document
│   └── README.md           # How to add new stories
├── public/
│   ├── storyteller.js      # Story engine (evaluates conditions, manages queue)
│   └── app.js              # Integrates storyteller with playback
```

## Story Definition Format (stories.json)

```json
{
  "stories": [
    {
      "id": "first_loom",
      "name": "First Loom",
      "category": "early_game",
      "trigger": {
        "type": "first_player",
        "event": "research",
        "target": "loom"
      },
      "templates": [
        "{player} gets Loom first at {time} - safety first!",
        "{player} protecting those villagers early with Loom at {time}!"
      ],
      "priority": 2,
      "cooldown": 0,
      "enabled": true
    }
  ]
}
```

## Trigger Types

### 1. `first_player` - First player to do something
```json
{
  "type": "first_player",
  "event": "research|build|train",
  "target": "loom|towncenter|knight|etc"
}
```

### 2. `last_player` - Last player to do something
```json
{
  "type": "last_player",
  "event": "research|build|train",
  "target": "loom|feudalage|etc",
  "deadline": 900  // Optional: only trigger if after X seconds
}
```

### 3. `player_event` - When any player does something
```json
{
  "type": "player_event",
  "event": "research|build|attack",
  "target": "imperialage|castle|etc"
}
```

### 4. `comparison` - Compare values between players/teams
```json
{
  "type": "comparison",
  "metric": "military_count|villager_count|tech_count",
  "condition": "difference_exceeds|ratio_exceeds",
  "threshold": 10,
  "check_interval": 60  // Check every N game seconds
}
```

### 5. `milestone` - Player reaches a threshold
```json
{
  "type": "milestone",
  "metric": "villager_count|military_count|building_count",
  "threshold": 100,
  "comparison": "gte"
}
```

### 6. `absence` - Player hasn't done something by a time
```json
{
  "type": "absence",
  "event": "research",
  "target": "wheelbarrow",
  "deadline": 1500,  // 25 minutes
  "check_at": 1500   // When to check
}
```

### 7. `attack_event` - Combat-related events
```json
{
  "type": "attack_event",
  "condition": "first_attack|raid_detected",
  "min_units": 5
}
```

## Template Variables

- `{player}` - Player name (colored)
- `{player2}` - Second player (for comparisons)
- `{team}` - Team number
- `{time}` - Game time formatted (MM:SS)
- `{value}` - Numeric value (count, difference, etc.)
- `{target}` - Tech/unit/building name
- `{civ}` - Player's civilization

## Initial Stories (10 total)

### Early Game (0-10 min)

1. **First Loom** - First player to research Loom
2. **Last Loom** - Last player to research Loom (playful ribbing)
3. **First TC Placed** - First player to place Town Center (Land Nomad specific)
4. **Last TC Placed** - Last player to place TC (slowpoke alert)
5. **Speed Feudal** - First player to reach Feudal Age

### Mid Game (10-25 min)

6. **Fast Castle** - First player to reach Castle Age
7. **First Blood** - First attack command between players
8. **Army Difference** - When one team has 20+ more military units
9. **Knight Rush Detected** - Player trains 5+ knights before 20 min
10. **Archer Mass** - Player trains 20+ archers

### Late Game / General

11. **Imperial Race** - First to Imperial Age
12. **Forgotten Wheelbarrow** - Player hasn't researched Wheelbarrow by 25 min
13. **Castle Drop** - Player builds castle (especially if near enemy)

## Story Evaluation Flow

```
On each time update:
1. Get current game time
2. For each story definition:
   a. Check if story is enabled
   b. Check if story already triggered (for one-time stories)
   c. Check if cooldown has passed
   d. Evaluate trigger conditions against current game state
   e. If triggered, add to caption queue with formatted text
3. Display queue (max 3, remove expired)
```

## Game State Required

The storyteller needs access to:
- `researchData` - All research events per player (already exists)
- `productionData` - Unit training events (already exists)  
- `buildingData` - Building placements with timestamps (needs extraction)
- `attackData` - Attack commands (ORDER actions with targets)
- Current game time
- Player/team info

## Implementation Steps

1. Create `stories.json` with initial story definitions
2. Create `storyteller.js` class:
   - Load stories from JSON
   - Track triggered stories (one-time events)
   - Evaluate conditions on time update
   - Manage caption queue (add, expire, limit to 3)
3. Add caption UI to `index.html` (bottom overlay)
4. Add caption styles to `style.css` (fade animations)
5. Integrate in `app.js`:
   - Initialize storyteller with game data
   - Call `storyteller.update(currentTime)` in time update
   - Render active captions

## Adding New Stories

To add a new story:
1. Open `stories/stories.json`
2. Add a new story object to the `stories` array
3. Define the trigger conditions
4. Write playful template(s)
5. Set priority and cooldown
6. Refresh the page - no code changes needed!

See `stories/README.md` for detailed examples.
