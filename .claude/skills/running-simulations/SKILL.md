---
name: running-simulations
description: Use when needing to look up unit stats from the database, run backend battle simulations, or interpret simulation results in the AoE2 Unit Analyzer project
---

# Running Simulations

Quick reference for querying unit stats, running backend simulations, and interpreting results. Simulations are **deterministic** — run each scenario once.

## 1. Look Up Unit Stats

Query `ref_units` in `webapp/aoe2_reference.db` (the DB the app serves — NOT
the legacy `aoe2_units.db`). Run from the repo root:

```python
import sqlite3, sys
sys.path.insert(0, "webapp")
from simulation import prepare_combat_unit, simulate_battle
from combat_unit_loader import build_combat_dict_from_ref

db = sqlite3.connect("webapp/aoe2_reference.db")
db.row_factory = sqlite3.Row

def get_unit(civ_name, slug, age="Imperial"):
    row = db.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ_name, slug, age)).fetchone()
    return prepare_combat_unit(build_combat_dict_from_ref(row))
```

**Civ names** are title-case: `"Franks"`, `"Chinese"`, `"Byzantines"`.
**Slugs**: standard units = `"knight"`, `"halberdier"`; unique units have civ suffix = `"huskarl_goths"`, `"cataphract_byzantines"`.
**Age filter**: non-elite uniques use the same slug in Castle and Imperial — pass `age="Castle"` for the Castle-age version (the helper defaults to Imperial).

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
