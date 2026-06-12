# Story System - Adding New Stories

This document explains how to add new stories to the replay narrator.

## Quick Start

Edit `stories.json` and add a new object to the `stories` array. No code changes needed!

## Story Structure

```json
{
  "id": "unique_id",
  "name": "Human Readable Name",
  "description": "What this story detects",
  "category": "early_game|mid_game|late_game",
  "trigger": { ... },
  "templates": ["Template 1", "Template 2"],
  "priority": 1-5,
  "cooldown_seconds": 0,
  "enabled": true
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (snake_case) |
| `name` | Yes | Display name for debugging |
| `description` | No | What the story detects |
| `category` | No | For organization: early_game, mid_game, late_game |
| `trigger` | Yes | Conditions that fire this story |
| `templates` | Yes | Array of caption texts (one chosen randomly) |
| `priority` | No | 1-5, higher = more important (default: 2) |
| `cooldown_seconds` | No | Min seconds between triggers (default: 0 = one-time) |
| `enabled` | No | Set to false to disable (default: true) |

## Template Variables

Use these placeholders in your templates:

| Variable | Description | Example |
|----------|-------------|---------|
| `{player}` | Player name (with color) | "ddk220" |
| `{player2}` | Second player (attacks, comparisons) | "Harry" |
| `{team}` | Team number | "1" |
| `{time}` | Game time (MM:SS) | "12:34" |
| `{value}` | Numeric value | "25" |
| `{target}` | Tech/unit/building name | "Knight" |
| `{civ}` | Player's civilization | "Britons" |

## Trigger Types

### 1. First Player to Do Something

```json
"trigger": {
  "type": "first_player",
  "event": "research",
  "target": "loom"
}
```

Events: `research`, `build`, `train`

### 2. Last Player to Do Something

```json
"trigger": {
  "type": "last_player",
  "event": "research",
  "target": "loom"
}
```

### 3. Any Player Does Something

```json
"trigger": {
  "type": "player_event",
  "event": "build",
  "target": "castle"
}
```

Fires for each player who does the action.

### 4. Player Hasn't Done Something (Absence)

```json
"trigger": {
  "type": "absence",
  "event": "research",
  "target": "wheelbarrow",
  "deadline": 1500,
  "check_at": 1500
}
```

Fires at `check_at` time if player hasn't done the action by `deadline`.

### 5. Milestone (Threshold Reached)

```json
"trigger": {
  "type": "milestone",
  "event": "train_cumulative",
  "target": ["knight"],
  "threshold": 5,
  "before_time": 1200
}
```

Optional `before_time` to only count if threshold reached before that time.

### 6. Comparison Between Teams

```json
"trigger": {
  "type": "comparison",
  "metric": "military_count",
  "condition": "team_difference_exceeds",
  "threshold": 20,
  "check_interval": 60
}
```

Metrics: `military_count`, `villager_count`, `tech_count`
Conditions: `team_difference_exceeds`, `ratio_exceeds`

### 7. Attack Events

```json
"trigger": {
  "type": "attack_event",
  "condition": "first_attack",
  "min_units": 3
}
```

Conditions: `first_attack`, `raid_detected`

## Examples

### Early Aggression Detection

```json
{
  "id": "early_aggression",
  "name": "Early Aggression",
  "trigger": {
    "type": "attack_event",
    "condition": "first_attack",
    "min_units": 5,
    "before_time": 600
  },
  "templates": [
    "EARLY RUSH! {player} attacks {player2} at just {time}!",
    "{player} choosing violence early! Hitting {player2} at {time}"
  ],
  "priority": 4,
  "enabled": true
}
```

### Boom Detected

```json
{
  "id": "boom_detected",
  "name": "Boom Detected",
  "trigger": {
    "type": "milestone",
    "metric": "tc_count",
    "threshold": 4
  },
  "templates": [
    "{player} is BOOMING! {value} TCs up!",
    "Full boom mode from {player} - {value} Town Centers!"
  ],
  "priority": 3,
  "enabled": true
}
```

### No Military Warning

```json
{
  "id": "no_military",
  "name": "No Military Warning",
  "trigger": {
    "type": "absence",
    "event": "train",
    "target": ["military"],
    "deadline": 900,
    "check_at": 900
  },
  "templates": [
    "{player} has no military at {time}! Living on a prayer...",
    "Where's the army, {player}? 15 minutes and counting!"
  ],
  "priority": 2,
  "enabled": true
}
```

## Tips for Good Stories

1. **Be specific**: Target exact techs/units rather than broad categories
2. **Be playful**: Use humor, AoE2 memes, caster-style language
3. **Vary templates**: Add 2-3 variations to keep it fresh
4. **Set cooldowns**: For repeating stories, use `cooldown_seconds` to prevent spam
5. **Test thresholds**: Make sure milestones trigger at meaningful moments
6. **Consider timing**: Early game stories should have low time thresholds

## Common Tech/Unit/Building Names

### Technologies
- `loom`, `wheelbarrow`, `handcart`
- `feudalage`, `castleage`, `imperialage`
- `doublebitaxe`, `bowsaw`, `horsecollar`
- `fletching`, `bodkinarrow`, `bracer`
- `forging`, `ironcasting`, `blastfurnace`
- `bloodlines`, `husbandry`
- `ballistics`, `chemistry`

### Units
- `villager`
- `militia`, `manatarms`, `longswordsman`, `champion`
- `archer`, `crossbowman`, `arbalester`
- `skirmisher`, `eliteskirmisher`
- `scout`, `lightcavalry`, `hussar`
- `knight`, `cavalier`, `paladin`
- `mangonel`, `onager`, `siegeonager`
- `scorpion`, `heavyscorpion`
- `batteringram`, `cappedram`, `siegeram`
- `trebuchet`

### Buildings
- `towncenter`, `house`, `mill`, `lumbercamp`, `miningcamp`
- `barracks`, `archeryrange`, `stable`, `siegeworkshop`
- `blacksmith`, `market`, `university`, `monastery`
- `castle`, `tower`, `watchtower`, `guardtower`, `keep`
- `palisadewall`, `stonewall`
