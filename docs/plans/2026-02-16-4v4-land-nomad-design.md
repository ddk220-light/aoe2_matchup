# 4v4 Land Nomad Team Analysis — Design

## Overview

A new "Team Analysis" tab where users pick 4 civs per team and see which team has the upper hand in cavalry (and later ranged/infantry). Uses pre-computed rank and median-delta data from the `battle_scores` table for instant lookups — no runtime simulations.

## Decisions

| Decision | Choice |
|----------|--------|
| Primary score | `stable_effectiveness` (70% general_combat + 30% anti_cav) |
| Per-civ logic | Show all individual stable units above median |
| Team comparison | Sum of score deltas from median |
| Age | Imperial only (v1) |
| Civ picker | Two separate side-by-side grids |
| Data model | Add columns to existing `battle_scores` table |
| Rank/delta scope | Computed for every `score_type`, not just composites |

## Database Schema Changes

### `battle_scores` table — add 2 columns

```sql
ALTER TABLE battle_scores ADD COLUMN rank INTEGER;
ALTER TABLE battle_scores ADD COLUMN median_delta REAL;
```

Computed in `compute_battle_scores.py` as a final pass after all scores are written:

For each unique `(line_slug, age, score_type)` group:
1. Collect all `score_value` entries
2. `median = numpy.median(values)`
3. `rank` = position when sorted by `score_value` descending (1 = highest)
4. `median_delta = score_value - median`

A unit is "above median" when `median_delta > 0`.

This applies to all 44+ score types across all line slugs (stable, militia, archer, etc.), giving maximum flexibility for future stage analysis.

## API Endpoint

### `GET /api/team-analysis`

**Query params:**
- `team1` — comma-separated civ slugs (4 required)
- `team2` — comma-separated civ slugs (4 required)
- `stage` — `cavalry` (future: `ranged`, `infantry`)
- `age` — `Imperial` (default)

**Stage-to-query mapping:**

| Stage | line_slug | score_type |
|-------|-----------|------------|
| cavalry | stable | stable_effectiveness |
| ranged (future) | archery | ranged_effectiveness |
| infantry (future) | infantry | militia_value |

**Response:**
```json
{
  "stage": "cavalry",
  "age": "Imperial",
  "score_type": "stable_effectiveness",
  "median": 58.2,
  "team1": {
    "civs": ["franks", "persians", "mongols", "huns"],
    "above_median_units": [
      {
        "civ": "franks",
        "unit_slug": "paladin",
        "score": 82.3,
        "rank": 3,
        "median_delta": 24.1
      }
    ],
    "total_delta": 41.3
  },
  "team2": {
    "civs": ["aztecs", "celts", "japanese", "byzantines"],
    "above_median_units": [],
    "total_delta": 0
  },
  "advantage": "team1",
  "advantage_margin": 31.3
}
```

**Query logic:** Single SELECT with WHERE filters — no computation at request time.

```sql
SELECT civ_name, unit_slug, score_value, rank, median_delta
FROM battle_scores
WHERE line_slug = :line_slug
  AND age = :age
  AND score_type = :score_type
  AND civ_name IN (:team_civs)
  AND median_delta > 0
ORDER BY score_value DESC
```

## Frontend UI

### New nav tab

"Team Analysis" added between "Matchup Advisor" and "Rankings" in `base.html`.

### Page: `team_analysis.html`

**Template:** extends `base.html`, follows existing patterns.

**Layout (top to bottom):**

#### 1. Team Picker

Two side-by-side panels, each containing:
- 4 civ slots at top (showing selected civ emblems)
- Scrollable civ emblem grid (50 civs)
- Click civ = fills next empty slot; click filled slot = removes it
- Team 1: red-tinted border (`--team1`); Team 2: blue-tinted (`--team2`)
- "Analyze Teams" button (enabled when 4+4 civs selected)

#### 2. Results: Stage Cards

Vertical stack of stage analysis cards. V1 has only cavalry:

**Cavalry Matchup card:**
- Header: stage name + advantage indicator (which team, margin)
- Two columns (Team 1 / Team 2)
- Each column lists above-median units sorted by score desc
- Each unit card: civ emblem, unit name, score, rank #, delta
- Footer: civs with no above-median cavalry listed

#### 3. Future extensibility

Stage cards stack vertically:
```
[ Cavalry Matchup ]    <- v1
[ Ranged Matchup  ]    <- future
[ Infantry Matchup]    <- future
[ Overall Summary ]    <- future
```

Each stage uses the same component structure with different `line_slug`/`score_type`.

## Files to Modify

| File | Change |
|------|--------|
| `webapp/compute_battle_scores.py` | Add rank + median_delta computation pass |
| `webapp/app.py` | Add `/team-analysis` route + `/api/team-analysis` endpoint |
| `webapp/templates/team_analysis.html` | New template (team picker + results) |
| `webapp/templates/base.html` | Add "Team Analysis" nav tab |
| `webapp/static/js/team_analysis.js` | New JS for team picker + API calls + results rendering |
| `webapp/static/css/team_analysis.css` | New CSS for team picker + stage cards |

## Out of Scope (v1)

- Ranged and infantry stages (future)
- Castle Age analysis
- Map-specific scoring
- Team synergy / composition diversity scoring
- Overall summary aggregating all stages
