# Naval Rankings Design

**Date:** 2026-04-13
**Status:** Approved

## Goal

Add a "Naval Effectiveness" 5th tab to the unit rankings page, alongside Infantry, Ranged, Stable, and Anti-Building. Show naval unit stats (HP, DPS, armor, speed, range, cost, upgrade cost, special) with no scoring column yet. Extend the existing Anti-Building tab with a new `cannon_galleon` sub-line (Canon Galleon and its civ-specific unique replacements).

## Architecture

Data already exists. All naval units are in `ref_units` in `aoe2_reference.db` from the navy column feature. No new pipeline runs or new API endpoints are needed. The existing `/api/ref/unit-line/<slug>` handler queries `ref_units` and handles missing battle scores gracefully — naval units will simply return no score columns.

---

## Unit Grouping

### Naval Effectiveness tab — 3 sub-lines

| Sub-line slug | Display name | Standard units | Unique replacements |
|---|---|---|---|
| `galleon` | Galleon Line | Galley, War Galley, Galleon | Longboat / Elite Longboat (Vikings), Caravel / Elite Caravel (Portuguese), Thirisadai (Dravidians), Lou Chuan (Wu) |
| `fire` | Fire Ship Line | Fire Galley, Fire Ship, Fast Fire Ship | — |
| `hulk` | Hulk Line | Hulk, War Hulk | Turtle Ship / Elite Turtle Ship (Koreans) |

**Unique unit routing rules:**
- All unique naval units go in the ranged/galleon sub-line, **except** Turtle Ship / Elite Turtle Ship → melee/hulk sub-line (combat role exception)
- Lou Chuan (Wu) appears in **both** `galleon` (anti-ship attack mode) and `cannon_galleon` (siege attack mode)
- Demo Ship line is excluded (too random for meaningful comparison)
- Xebec is excluded (removed from the game's civ assignments)

### Anti-Building tab — new 4th sub-line

| Sub-line slug | Display name | Standard units | Unique replacements |
|---|---|---|---|
| `cannon_galleon` | Cannon Galleon | Cannon Galleon, Elite Cannon Galleon | Dromon (Byzantines), Lou Chuan (Wu / Shu / Wei), Catapult Galleon (Mapuche / Shu / Wei) |

---

## Stats Columns

**Naval Effectiveness tab columns:** Civ, Unit, Line, HP, DPS, Melee Armor, Pierce Armor, Speed, Range, Cost, Upg Cost, Special

- DPS computed server-side as `attack / reload_time`
- No score column — battle scores for naval units do not exist yet
- "Special" shows ability text from `special_abilities` field in `ref_units`

**Cannon Galleon sub-line in Anti-Building tab:**
- Uses existing siege column layout (Civ, Unit, Line, anti_building_score, TTK, DPS, HP, ...)
- Score columns (`anti_building_score`, TTK) will be blank/absent until naval battle scoring is added

---

## Backend Changes

### `webapp/unit_lines.py`

1. Add `naval` to the aggregate lines mapping:
   ```python
   "naval": ["galleon", "fire", "hulk"]
   ```
2. Add `cannon_galleon` to the siege aggregate sub-lines (if not already present):
   ```python
   "siege": ["ram", "trebuchet", "bombard_cannon", "cannon_galleon"]
   ```
3. Add Lou Chuan to the `galleon` line's `unique_units` mapping for Wu (it is already present in `cannon_galleon` unique_units):
   ```python
   "galleon": {
       ...
       "Wu": ("lou_chuan", ...),
   }
   ```

### `webapp/app.py`

Minimal changes. Ensure the `/api/ref/unit-line/<slug>` handler recognises `naval` as a valid aggregate slug and `galleon`, `fire`, `hulk` as valid sub-line slugs. The existing score-attachment logic already handles missing scores gracefully (no rows in `battle_scores` → score fields absent from response).

---

## Frontend Changes

### `webapp/static/js/rankings.js`

1. Add `NAVAL_SLUGS` constant:
   ```js
   const NAVAL_SLUGS = ["galleon", "fire", "hulk", "naval"];
   ```
2. Add `cannon_galleon` to `SIEGE_SLUGS`:
   ```js
   const SIEGE_SLUGS = ["siege", "cannon_galleon"];
   ```
3. Add `naval` tab button in the tab group (5th position, after Anti-Building).
4. Add column definition for the naval tab:
   - Columns: Civ, Unit, Line, HP, DPS, Melee Armor, Pierce Armor, Speed, Range, Cost, Upg Cost, Special
   - No score column
5. Add `cannon_galleon` as a sub-line checkbox in the Anti-Building tab filter row.

### `webapp/templates/index.html`

Add the 5th "Naval Effectiveness" tab button. No other structural changes — the tab system is data-driven.

---

## Out of Scope

- Naval battle simulations and strength scoring (future task)
- Demo Ship line (excluded by design)
- Xebec (excluded — no confirmed civ assignment)
- CSS changes beyond what the existing rankings stylesheet already supports
