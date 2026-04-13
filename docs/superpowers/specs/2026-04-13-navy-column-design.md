# Navy Column — Civilization Overview Page

**Date:** 2026-04-13
**Status:** Approved

## Summary

Add a 5th column ("Navy") to the civilization overview page, sitting alongside Infantry, Ranged, Cavalry, and Siege. The column shows 4 naval subcategories: galleon, fire, hulk, and demo. Each subcategory displays the highest-tier naval unit the civilization can build, with icon + name only (no strength tier for now — naval simulations are a future task).

Also adds Cannon Galleon line to the existing Siege column, including its civ-specific unique replacements (Dromon, Mapuche siege ship, Three Kingdoms siege ship).

---

## Naval Line Definitions

| Line slug | Display Name | Standard tiers (low → high) |
|-----------|-------------|------------------------------|
| `galleon` | Galleon Line | Galley → War Galley → Galleon |
| `fire` | Fire Ship Line | Fire Galley → Fire Ship → Fast Fire Ship |
| `hulk` | Hulk Line | Hulk → Elite Hulk *(exact unit IDs confirmed from dat)* |
| `demo` | Demo Ship Line | Demo Raft → Demo Ship → Heavy Demo Ship |

Each civ shows the highest tier it can reach per line. If a civ cannot build any unit in a line, the slot shows "—".

---

## Unique Naval Unit Mapping

Unique naval units are assigned to a line category based on their combat role. Civs with a unique in a line display that unit **instead of** the standard unit — the unique replaces the slot entirely, matching how unique land units work.

| Unique Unit | Civ(s) | Line |
|------------|--------|------|
| Longboat / Elite Longboat | Vikings | galleon |
| Caravel / Elite Caravel | Portuguese | galleon |
| Thirisadai / Elite Thirisadai | Dravidians | galleon |
| Xebec | Berbers | galleon |
| Turtle Ship / Elite Turtle Ship | Koreans | hulk |
| Other new-civ unique naval units | TBD | confirmed from dat during impl |

---

## Cannon Galleon → Siege Column

Cannon Galleon is a siege-class naval unit, not a pure naval unit. It is added to the **existing Siege column** as a 4th line, not the Navy column.

| Line slug | Display Name | Standard tiers |
|-----------|-------------|----------------|
| `cannon_galleon` | Cannon Galleon | Cannon Galleon → Elite Cannon Galleon |

**Civ-specific replacements** (unique units that replace Cannon Galleon for their civ):
- **Dromon** — certain civs (e.g., Byzantines)
- **Mapuche siege ship** — Mapuche
- **Three Kingdoms siege ship** — Shu / Wei / Wu

All replacement unit IDs confirmed from dat during implementation.

---

## Data Pipeline

Follows the existing land unit architecture exactly:

```
generate_reference.py
  → aoe2_reference.db  (ref_units table, unit_type='naval')
  → generate_main_db.py
  → aoe2_units.db  (unit_stats table)
  → best_units.py
  → civ_power_units.json  (navy key added)
```

### `generate_reference.py`

Add a new loop after the standard/unique unit loops:
- Iterates: all naval unit IDs × all 50 civs
- Calls `unit_analyzer.calculate_unit_stats_for_civ()` with naval unit ID and class
- Applies relevant tech chain (Shipwright, Dry Dock, Chemistry, etc.)
- Writes rows to `ref_units` with `unit_type='naval'`

### `generate_main_db.py`

No structural changes needed — naval rows in `ref_units` flow through naturally. Verify naval units are not filtered out by any existing type guard.

### `best_units.py`

New `generate_naval_column(civ_name, conn)` function:
- For each of the 4 naval lines, queries `ref_units` for units this civ can build in that line
- Selects the highest-tier available unit (e.g., Galleon beats War Galley beats Galley)
- If the civ has a unique naval unit mapped to this line, that unique unit **replaces** the standard unit in that slot (same as land unique units — never shown alongside)
- Returns null for the slot if civ has no unit in this line

Output structure in `civ_power_units.json`:
```json
"navy": {
  "galleon": [{ "unit_name": "Galleon", "unit_slug": "galleon", "strength": null }],
  "fire":    [{ "unit_name": "Fast Fire Ship", "unit_slug": "fast_fire_ship", "strength": null }],
  "hulk":    [{ "unit_name": "Elite Hulk", "unit_slug": "elite_hulk", "strength": null }],
  "demo":    [{ "unit_name": "Heavy Demo Ship", "unit_slug": "heavy_demo_ship", "strength": null }]
}
```

`strength: null` signals to the frontend that no tier colouring should be applied.

### `unit_lines.py` (or new `naval_unit_lines.py`)

Add naval line definitions following the same structure as existing `UNIT_LINES`:
```python
NAVAL_UNIT_LINES = {
    "galleon": {
        "name": "Galleon Line",
        "slugs": ["galley", "war_galley", "galleon"],  # low → high
        "unique_units": {
            "Vikings": ("longboat", "elite_longboat"),
            "Portuguese": ("caravel", "elite_caravel"),
            ...
        },
    },
    "fire": { ... },
    "hulk": { ... },
    "demo": { ... },
}
```

---

## Frontend

### `matchup.js`

- Add `"navy"` to `COLUMN_ORDER` (5th position)
- Add to `COLUMN_DEFS`: `navy: ["galleon", "fire", "hulk", "demo"]`
- Add to `COLUMN_LABELS`: `navy: "Navy"`
- Add to `LINE_NAMES`: `galleon: "Galleon Line"`, `fire: "Fire Ship Line"`, `hulk: "Hulk Line"`, `demo: "Demo Ship Line"`
- Add `"cannon_galleon"` to `COLUMN_DEFS.siege`
- Add `cannon_galleon: "Cannon Galleon"` to `LINE_NAMES`
- Badge rendering: when `unit.strength === null`, render with a neutral grey border (no strength label, no tier colour)

### `constants.js`

Add `NAME_TO_ICON` entries for all naval units:
- Standard: Galley, War Galley, Galleon, Fire Galley, Fire Ship, Fast Fire Ship, Hulk, Elite Hulk, Demo Raft, Demo Ship, Heavy Demo Ship, Cannon Galleon, Elite Cannon Galleon
- Unique: Longboat, Elite Longboat, Turtle Ship, Elite Turtle Ship, Caravel, Elite Caravel, Thirisadai, Elite Thirisadai, Xebec, Dromon, and any new-civ unique naval units

### `matchup.css`

Add one new rule for the neutral badge border (strength: null):
```css
.unit-badge.no-strength { border-left-color: var(--text-muted); }
```

---

## Icons

For each naval unit:
1. Get `icon_id` from dat via genieutils: `dat.civs[0].units[UNIT_ID].icon_id`
2. Fetch `https://aoe2techtree.net/img/Unit/{icon_id}.png`
3. If 404, fall back to Fandom wiki API
4. Save as `webapp/static/img/units/{Unit_Name}.png`

---

## Out of Scope

- Naval battle simulations and strength tier classification (future task)
- Transport Ship (non-combat, not shown)
- Galleass (Italian unique technology, not a trainable unit)
- Fire Ship line unique replacements (none currently in game)
