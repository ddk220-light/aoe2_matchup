---
name: running-simulations
description: Use when needing to look up unit stats from the database, run backend battle simulations, or interpret simulation results in the AoE2 Unit Analyzer project
---

# Running Simulations

Quick reference for querying unit stats, running backend simulations, and interpreting results. Simulations are **deterministic** — run each scenario once.

## 1. Look Up Unit Stats

```python
import sqlite3, sys
sys.path.insert(0, "/Users/deepak/AI/aoe2unitanalyzer")
from webapp.simulation import prepare_combat_unit, simulate_battle

db = sqlite3.connect("/Users/deepak/AI/aoe2unitanalyzer/webapp/aoe2_units.db")
db.row_factory = sqlite3.Row

def get_unit(civ_name, slug):
    row = db.execute("""
        SELECT us.* FROM unit_stats us
        JOIN units u ON us.unit_id = u.id
        JOIN civilizations c ON us.civ_id = c.id
        WHERE c.name = ? AND u.slug = ? AND us.has_unit = 1
    """, (civ_name, slug)).fetchone()
    return prepare_combat_unit(dict(row))
```

**Civ names** are title-case: `"Franks"`, `"Chinese"`, `"Byzantines"`.
**Slugs**: standard units = `"knight"`, `"halberdier"`; unique units have civ suffix = `"huskarl_goths"`, `"cataphract_byzantines"`.
**Age filter**: if same slug exists in Castle+Imperial (non-elite uniques), add `AND us.age = 'Imperial'`.

## 2. Run a Simulation

```python
unit1 = get_unit("Franks", "paladin")
unit2 = get_unit("Chinese", "champion")

# Equal count (e.g., 30v30)
winner, rem1, rem2, hp1, hp2 = simulate_battle(unit1, unit2, 0, fixed_count=30, return_hp=True)

# Equal resources (e.g., 3000 each)
winner, rem1, rem2, hp1, hp2 = simulate_battle(unit1, unit2, 3000, return_hp=True)
```

**Parameters**: `resources` (int, 0 if using fixed_count), `fixed_count` (int, units per side), `return_hp=True` (adds hp_pct floats 0.0-1.0), `return_ticks=True` (adds tick count).

## 3. Interpret Results

- `winner`: 1 = unit1 wins, 2 = unit2 wins, 0 = draw
- `rem1/rem2`: surviving unit count per side
- `hp1/hp2`: fraction of total HP remaining (0.0-1.0)
- **Always run both** equal count AND equal resources for a complete picture.
- **Equal count** tests raw combat strength. **Equal resources** tests cost-efficiency (more realistic).
- A unit winning 30v30 but losing at equal resources means it's strong but overpriced.

## 4. When to Delegate

**Run inline** (paste the snippet above) for quick 1-2 matchup checks.
**Use simulation-tester subagent** for: multi-matchup investigations, tick-by-tick analysis, or debugging simulation mechanics. Specify both units AND civilizations when delegating.
