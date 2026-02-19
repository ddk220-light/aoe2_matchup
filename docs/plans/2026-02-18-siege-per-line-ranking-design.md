# Siege Per-Line Ranking Design

**Date:** 2026-02-18
**Status:** Approved

## Problem

Siege units (rams, trebuchets, bombard cannons) are currently aggregated into a single "siege" role with one pooled ranking. A civ with bad rams but great bombard cannons gets a mediocre overall siege rank. The user wants each siege line ranked independently against other civs' versions of the same line.

## Solution: Per-Line Storage (Approach A)

Store siege scores with actual line slugs (`ram`, `trebuchet`, `bombard_cannon`) instead of the generic `"siege"`. Rankings automatically become per-line since `compute_rankings()` groups by `(line_slug, age, score_type)`.

## Changes

### 1. `compute_battle_scores.py` — `compute_siege_antibuilding_scores()`

Change the return format key from `siege|{age}` to `{line_slug}|{age}`:

```python
# Before: result[f"siege|{age}"] = scores
# After:  result[f"{line_slug}|{age}"] = scores_for_this_line
```

Each line's scores are stored separately so rankings compare rams vs rams, trebs vs trebs, etc.

### 2. `compute_battle_scores.py` — `write_role_scores_to_db` call

Change the line_slugs parameter from `["siege"]` to `SIEGE_LINE_SLUGS` (`["ram", "trebuchet", "bombard_cannon"]`) so it deletes/writes per-line.

### 3. `best_units.py` — `ROLE_DEFS`

```python
# Before: ("siege", ["siege"], "anti_building_score")
# After:  ("siege", ["ram", "trebuchet", "bombard_cannon"], "anti_building_score")
```

The role still aggregates all 3 lines for display, but each unit's rank and median_delta come from its own line's pool.

### 4. No frontend changes needed

Units already display as individual badges with their ranks within the Siege column. The only difference is that ranks now reflect per-line comparison rather than pooled comparison.

## What stays the same

- Scoring methodology (time-to-kill Spanish Castle, anti_building_score normalization)
- Strength profile and strategic summary logic
- Narrative keys for siege role
- Frontend display layout and styling
