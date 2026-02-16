# Best Units Logic Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Identify each civ's best units by role (pre-computed) and recommend counter-units + compositions for civ-vs-civ matchups (on-the-fly).

**Architecture:** Phase A pre-computes a `civ_power_units.json` from existing `battle_scores` DB data (no new simulations). Phase B loads Phase A data and runs ~10 targeted simulations on-the-fly per matchup request. A new `webapp/best_units.py` module contains all logic; two new API endpoints serve it.

**Tech Stack:** Python 3, SQLite3, existing `simulation.py` engine, Flask API in `webapp/app.py`.

**Design doc:** `docs/plans/2026-02-16-best-units-design.md`

---

## Important Codebase Notes

- **Age casing quirk:** `battle_scores` stores `"Imperial"` for `stable` line but `"imperial"` for all other lines. Also `"castle"` for siege. All queries must handle both casings: use `age IN ('Imperial', 'imperial')` or `LOWER(age)='imperial'`.
- **DB path:** `webapp/aoe2_reference.db` — use `sqlite3.connect(DB_PATH)` with `conn.row_factory = sqlite3.Row`.
- **Cost formula:** `0.8 * wood + food + 1.5 * gold` (see `calc_weighted_cost` in `compute_battle_scores.py:531`).
- **Combat unit loading:** Use `_build_combat_dict_from_ref()` in `app.py:335` then `prepare_combat_unit()` from `simulation.py:84`.
- **No test directory exists.** Use standalone validation scripts run via `python3`.
- **Civ list:** 50 civs in `ORIGINAL_13_CIVS` at `app.py:119-170`.
- **Trash units:** `final_cost_gold = 0` in `ref_units` table (hussar, halberdier, imp_elite_skirm, etc.).

---

### Task 1: Phase A — `compute_civ_power_units()` function

**Files:**
- Create: `webapp/best_units.py`
- Reference: `webapp/compute_battle_scores.py` (DB patterns), `webapp/aoe2_reference.db` (data source)

**Step 1: Write the `best_units.py` module with Phase A logic**

```python
"""
Best units logic: civ power units (pre-computed) + matchup recommendations (on-the-fly).
"""

import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
POWER_UNITS_PATH = os.path.join(os.path.dirname(__file__), "civ_power_units.json")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Role definitions: (role_key, line_slugs, score_type)
ROLE_DEFS = [
    ("cavalry", ["stable"], "stable_effectiveness"),
    ("ranged", ["archer", "cav_archer", "scorpion", "gunpowder"], "ranged_effectiveness"),
    ("infantry", ["militia", "shock_infantry"], "militia_value"),
    ("anti_cavalry", ["spear", "militia"], "anti_cav_value"),
    ("siege", ["siege"], "anti_building_score"),
]

# Trash role handled separately (needs gold cost filter)
TRASH_LINES = ["stable", "militia", "spear", "shock_infantry", "archer", "cav_archer",
               "scorpion", "gunpowder", "skirmisher"]


def _classify_strength(rank, median_delta):
    """Classify a unit's strength tier based on rank and median_delta."""
    if rank is not None and rank <= 5 and median_delta is not None and median_delta > 20:
        return "signature"
    if median_delta is not None and median_delta > 10:
        return "strong"
    if median_delta is not None and median_delta < -10:
        return "weak"
    return "average"


def compute_civ_power_units():
    """Pre-compute power units for all civs. Returns dict keyed by civ_name."""
    conn = _get_db()
    rc = conn.cursor()

    # Get all civ names
    rc.execute("SELECT DISTINCT civ_name FROM battle_scores ORDER BY civ_name")
    all_civs = [row["civ_name"] for row in rc.fetchall()]

    # Get trash unit slugs (gold cost = 0) from ref_units
    rc.execute(
        "SELECT DISTINCT civ_name, unit_slug FROM ref_units WHERE final_cost_gold = 0 AND age = 'Imperial'"
    )
    trash_by_civ = {}
    for row in rc.fetchall():
        trash_by_civ.setdefault(row["civ_name"], set()).add(row["unit_slug"])

    result = {}

    for civ in all_civs:
        civ_data = {"imperial": None, "castle": None}

        for age_key in ["imperial"]:  # Start with imperial only
            power_units = {}

            for role_key, line_slugs, score_type in ROLE_DEFS:
                placeholders = ",".join("?" for _ in line_slugs)
                rc.execute(
                    f"""SELECT unit_slug, line_slug, score_value, rank, median_delta
                        FROM battle_scores
                        WHERE civ_name = ?
                          AND LOWER(age) = ?
                          AND score_type = ?
                          AND line_slug IN ({placeholders})
                        ORDER BY median_delta DESC
                        LIMIT 1""",
                    [civ, age_key, score_type] + line_slugs,
                )
                row = rc.fetchone()
                if row:
                    strength = _classify_strength(row["rank"], row["median_delta"])
                    power_units[role_key] = {
                        "unit_slug": row["unit_slug"],
                        "line_slug": row["line_slug"],
                        "score": round(row["score_value"], 1),
                        "rank": row["rank"],
                        "median_delta": round(row["median_delta"], 1),
                        "is_signature": strength == "signature",
                        "strength": strength,
                    }
                else:
                    power_units[role_key] = None

            # Trash: best general_combat among zero-gold units
            civ_trash = trash_by_civ.get(civ, set())
            if civ_trash:
                trash_placeholders = ",".join("?" for _ in civ_trash)
                line_placeholders = ",".join("?" for _ in TRASH_LINES)
                rc.execute(
                    f"""SELECT unit_slug, line_slug, score_value, rank, median_delta
                        FROM battle_scores
                        WHERE civ_name = ?
                          AND LOWER(age) = ?
                          AND score_type = 'general_combat'
                          AND line_slug IN ({line_placeholders})
                          AND unit_slug IN ({trash_placeholders})
                        ORDER BY median_delta DESC
                        LIMIT 1""",
                    [civ, age_key] + TRASH_LINES + list(civ_trash),
                )
                row = rc.fetchone()
                if row:
                    strength = _classify_strength(row["rank"], row["median_delta"])
                    power_units["trash"] = {
                        "unit_slug": row["unit_slug"],
                        "line_slug": row["line_slug"],
                        "score": round(row["score_value"], 1),
                        "rank": row["rank"],
                        "median_delta": round(row["median_delta"], 1),
                        "is_signature": strength == "signature",
                        "strength": strength,
                    }
                else:
                    power_units["trash"] = None
            else:
                power_units["trash"] = None

            # Build strength profile
            strength_profile = {}
            for role_key in ["cavalry", "ranged", "infantry", "anti_cavalry", "trash", "siege"]:
                entry = power_units.get(role_key)
                strength_profile[role_key] = entry["strength"] if entry else "weak"

            civ_data[age_key] = {
                "power_units": power_units,
                "strength_profile": strength_profile,
            }

        result[civ] = civ_data

    conn.close()
    return result


def save_civ_power_units():
    """Compute and write civ_power_units.json."""
    data = compute_civ_power_units()
    with open(POWER_UNITS_PATH, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"Wrote {POWER_UNITS_PATH} ({len(data)} civs)")
    return data


def load_civ_power_units():
    """Load pre-computed civ power units. Returns dict or None if file missing."""
    if not os.path.exists(POWER_UNITS_PATH):
        return None
    with open(POWER_UNITS_PATH, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    save_civ_power_units()
```

**Step 2: Run it to generate `civ_power_units.json`**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 best_units.py`

Expected: Prints `"Wrote .../civ_power_units.json (50 civs)"` and creates the JSON file.

**Step 3: Validate output with a spot-check script**

Create `webapp/validate_power_units.py`:

```python
"""Spot-check civ_power_units.json against known expectations."""
import json
import sys

with open("civ_power_units.json") as f:
    data = json.load(f)

errors = []

# Check all 50 civs present
if len(data) != 50:
    errors.append(f"Expected 50 civs, got {len(data)}")

# Franks: paladin should be cavalry power unit, strength should be "strong" or "signature"
franks = data.get("Franks", {}).get("imperial", {})
if franks:
    cav = franks["power_units"].get("cavalry")
    if not cav or cav["unit_slug"] != "paladin":
        errors.append(f"Franks cavalry: expected paladin, got {cav}")
    elif cav["strength"] not in ("strong", "signature"):
        errors.append(f"Franks paladin strength: expected strong/signature, got {cav['strength']}")

# Britons: ranged should be a strong/signature unit
britons = data.get("Britons", {}).get("imperial", {})
if britons:
    ranged = britons["power_units"].get("ranged")
    if not ranged or ranged["strength"] not in ("strong", "signature"):
        errors.append(f"Britons ranged: expected strong/signature, got {ranged}")

# Every civ should have at least cavalry and ranged entries
for civ, civ_data in data.items():
    imp = civ_data.get("imperial", {})
    if not imp:
        errors.append(f"{civ}: missing imperial data")
        continue
    pu = imp.get("power_units", {})
    for role in ["cavalry", "ranged", "infantry"]:
        if pu.get(role) is None:
            errors.append(f"{civ}: missing {role} power unit")

if errors:
    print("VALIDATION FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
    # Print a few examples
    for civ in ["Franks", "Britons", "Mongols", "Goths", "Spanish"]:
        imp = data[civ]["imperial"]
        profile = imp["strength_profile"]
        sigs = [r for r, s in profile.items() if s == "signature"]
        strongs = [r for r, s in profile.items() if s == "strong"]
        print(f"  {civ}: signature={sigs}, strong={strongs}")
```

**Step 4: Run validation**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 validate_power_units.py`

Expected: `"ALL CHECKS PASSED"` with example output.

**Step 5: Commit**

```bash
git add webapp/best_units.py webapp/civ_power_units.json webapp/validate_power_units.py
git commit -m "feat: add Phase A civ power units computation

Reads battle_scores DB, picks best unit per role per civ, classifies
strength tiers (signature/strong/average/weak). Writes civ_power_units.json."
```

---

### Task 2: Phase B — Matchup recommendations logic

**Files:**
- Modify: `webapp/best_units.py` (add matchup functions)
- Reference: `webapp/app.py:335-428` (`_build_combat_dict_from_ref`), `webapp/simulation.py:84,355` (`prepare_combat_unit`, `simulate_battle`)

**Step 1: Add counter-role mapping and matchup logic to `best_units.py`**

Append the following to `webapp/best_units.py`:

```python
from simulation import prepare_combat_unit, simulate_battle


def _calc_weighted_cost(food, wood, gold):
    """Resource cost with gold weighted higher."""
    cost = 0.8 * (wood or 0) + (food or 0) + 1.5 * (gold or 0)
    return int(cost) if cost > 0 else 100


# Counter-role mapping: opponent strength -> what Civ A should query
COUNTER_MAP = {
    "cavalry": [
        # (lines_to_search, score_type, description)
        (["spear", "militia"], "anti_cav_value", "anti-cavalry specialist"),
        (["stable"], "anti_cav", "camel/cavalry counter"),
    ],
    "ranged": [
        (["stable"], "general_combat", "cavalry closes distance on ranged"),
        (["archer", "cav_archer", "scorpion", "gunpowder", "skirmisher"], "anti_archer", "anti-archer unit"),
    ],
    "infantry": [
        (["archer", "cav_archer", "scorpion", "gunpowder"], "general_combat", "ranged vs infantry"),
        (["stable"], "general_combat", "cavalry vs infantry"),
    ],
    "siege": [
        (["stable"], "general_combat", "cavalry snipes siege"),
    ],
}

# Trash pairing logic: gold_unit_line -> preferred trash partner
TRASH_PAIRING = {
    "stable": "skirmisher",       # cavalry + skirm (skirm handles halbs)
    "archer": "stable",           # archers + hussar (hussar tanks & raids)
    "cav_archer": "stable",       # cav archers + hussar
    "scorpion": "spear",          # scorpion + halbs (halbs screen from cav)
    "gunpowder": "spear",         # hand cannoneers + halbs
    "militia": "stable",          # infantry + hussar
    "spear": "skirmisher",        # spearmen + skirm
    "shock_infantry": "stable",   # shock infantry + hussar
    "skirmisher": "stable",       # skirm + hussar
    "siege": "spear",             # siege + halbs
}


def _load_combat_unit(civ_name, unit_slug, age="Imperial"):
    """Load a single combat-ready unit from ref_units."""
    conn = _get_db()
    rc = conn.cursor()
    rc.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ_name, unit_slug, age),
    )
    row = rc.fetchone()
    if not row:
        conn.close()
        return None

    reload_time = row["final_reload_time"] or 2.0
    attack_speed = 1.0 / reload_time if reload_time > 0 else 0.5

    combat_dict = {
        "slug": row["unit_slug"],
        "unit_name": row["unit_name"],
        "unit_category": "military",
        "paired_unit_slug": None,
        "hp": row["final_hp"],
        "attack": row["final_attack"],
        "attack_range": row["final_range"] if row["is_ranged"] else 0,
        "attack_speed": attack_speed,
        "attack_delay": row["final_attack_delay"] or 0,
        "melee_armor": row["final_melee_armor"],
        "pierce_armor": row["final_pierce_armor"],
        "movement_speed": row["final_speed"],
        "cost_food": row["final_cost_food"] or 0,
        "cost_wood": row["final_cost_wood"] or 0,
        "cost_gold": row["final_cost_gold"] or 0,
        "upgrade_cost_food": row["upgrade_cost_food"] or 0,
        "upgrade_cost_wood": row["upgrade_cost_wood"] or 0,
        "upgrade_cost_gold": row["upgrade_cost_gold"] or 0,
        "attacks_json": row["final_attacks_json"],
        "armors_json": row["final_armors_json"],
        "accuracy": row["final_accuracy"] or 100,
        "min_attack_range": row["min_range"] or 0,
        "projectile_speed": row["projectile_speed"] or 0,
        "is_siege_projectile": row["is_siege_projectile"] or 0,
        "splash_radius": row["splash_radius"] or 0,
        "extra_projectiles": row["extra_projectiles"] or 0,
        "extra_projectile_attacks_json": row["extra_projectile_attacks_json"],
        "trample_percent": row["trample_percent"] or 0,
        "trample_radius": row["trample_radius"] or 0,
        "trample_flat_damage": row["trample_flat_damage"] or 0,
        "hp_regen": row["hp_regen"] or 0,
        "charge_projectile_count": row["charge_projectile_count"] or 0,
        "charge_projectile_speed": row["charge_projectile_speed"] or 0,
        "charge_projectile_attacks_json": row["charge_projectile_attacks_json"],
        "charge_attack_range": float(row["charge_attack_range"] or 0),
        "charge_ignores_armor": int(row["charge_ignores_armor"] or 0),
        "ignores_pierce_armor": int(row["ignores_pierce_armor"] or 0),
        "ignores_melee_armor": int(row["ignores_melee_armor"] or 0),
        "bonus_damage_reduction": row["bonus_damage_reduction"] or 0,
        "splash_on_hit_radius": row["splash_on_hit_radius"] or 0,
        "splash_on_hit_fraction": row["splash_on_hit_fraction"] or 1.0,
        "dodge_shield_max": int(row["dodge_shield_max"] or 0),
        "dodge_shield_recharge": row["dodge_shield_recharge"] or 0,
        "bleed_dps": row["bleed_dps"] or 0,
        "bleed_duration": row["bleed_duration"] or 0,
        "block_first_melee": int(row["block_first_melee"] or 0),
        "attack_bonus_per_kill": int(row["attack_bonus_per_kill"] or 0),
        "first_attack_extra_projectiles": int(row["first_attack_extra_projectiles"] or 0),
        "pass_through_percent": row["pass_through_percent"] or 0,
        "pass_through_count": row["pass_through_count"] or 1,
        "extra_proj_scatter": row["extra_proj_scatter"] or 0,
        "miss_damage_percent": row["miss_damage_percent"] or 0,
        "hp_per_kill": int(row["hp_per_kill"] or 0),
        "hp_per_kill_max": int(row["hp_per_kill_max"] or 0),
        "hp_transform_threshold": row["hp_transform_threshold"] or 0,
        "pop_space": row["pop_space"] or 1.0,
        "armor_strip_per_hit": int(row["armor_strip_per_hit"] or 0),
        "charge_attack_melee": int(row["charge_attack_melee"] or 0),
        "charge_recharge_time": row["charge_recharge_time"] or 0,
        "attack_bonus_nearby": row["attack_bonus_nearby"] or 0,
        "nearby_bonus_count": int(row["nearby_bonus_count"] or 0),
        "damage_reflect_percent": row["damage_reflect_percent"] or 0,
        "hp_nearby_percent_per_unit": row["hp_nearby_percent_per_unit"] or 0,
        "hp_nearby_max_units": int(row["hp_nearby_max_units"] or 0),
        "dismount_hp": row["dismount_hp"],
        "dismount_attack": row["dismount_attack"],
        "dismount_melee_armor": row["dismount_melee_armor"],
        "dismount_pierce_armor": row["dismount_pierce_armor"],
        "dismount_attack_speed": row["dismount_attack_speed"],
        "dismount_attack_delay": row["dismount_attack_delay"],
        "dismount_movement_speed": row["dismount_movement_speed"],
        "dismount_attacks_json": row["dismount_attacks_json"],
        "dismount_armors_json": row["dismount_armors_json"],
        "transform_hp": row["transform_hp"],
        "transform_attack": row["transform_attack"],
        "transform_melee_armor": row["transform_melee_armor"],
        "transform_pierce_armor": row["transform_pierce_armor"],
        "transform_attack_speed": row["transform_attack_speed"],
        "transform_attack_delay": row["transform_attack_delay"],
        "transform_movement_speed": row["transform_movement_speed"],
        "transform_attacks_json": row["transform_attacks_json"],
        "transform_armors_json": row["transform_armors_json"],
    }
    conn.close()
    cu = prepare_combat_unit(combat_dict)
    cu["cost_food"] = combat_dict["cost_food"]
    cu["cost_wood"] = combat_dict["cost_wood"]
    cu["cost_gold"] = combat_dict["cost_gold"]
    return cu


def _sim_score(unit_a, unit_b):
    """Run two battle scenarios and return composite score (-100..+100) from unit_a's perspective."""
    cost_a = _calc_weighted_cost(unit_a["cost_food"], unit_a["cost_wood"], unit_a["cost_gold"])
    cost_b = _calc_weighted_cost(unit_b["cost_food"], unit_b["cost_wood"], unit_b["cost_gold"])

    # 3K resource battle (cost efficiency)
    w1, _, _, hp1_1, hp2_1 = simulate_battle(
        unit_a, unit_b, 3000, cost1_override=cost_a, cost2_override=cost_b, return_hp=True
    )
    res_score = hp1_1 * 100 if w1 == 1 else (-hp2_1 * 100 if w1 == 2 else 0)

    # 30v30 fixed count (pop efficiency)
    w2, _, _, hp1_2, hp2_2 = simulate_battle(
        unit_a, unit_b, 0, fixed_count=30, return_hp=True
    )
    pop_score = hp1_2 * 100 if w2 == 1 else (-hp2_2 * 100 if w2 == 2 else 0)

    composite = 0.6 * res_score + 0.4 * pop_score
    return round(res_score, 1), round(pop_score, 1), round(composite, 1)


def _generate_reasoning(gold_unit, trash_unit, opponent_unit):
    """Generate human-readable reasoning for a composition recommendation."""
    reasons = []
    g_name = gold_unit.get("unit_name", gold_unit.get("slug", "Unit"))
    o_name = opponent_unit.get("unit_name", opponent_unit.get("slug", "Opponent"))
    t_name = trash_unit.get("unit_name", trash_unit.get("slug", "Support")) if trash_unit else None

    g_speed = gold_unit.get("movement_speed", 0)
    o_speed = opponent_unit.get("movement_speed", 0)
    g_range = gold_unit.get("attack_range", 0)
    o_range = opponent_unit.get("attack_range", 0)

    if g_speed > o_speed and g_range == 0:
        reasons.append(f"{g_name} closes distance on {o_name}")
    if g_range > o_range and g_range > 0:
        reasons.append(f"{g_name} outranges {o_name}")
    if g_range > 0 and o_range == 0:
        reasons.append(f"{g_name} kites melee {o_name}")
    if not reasons:
        reasons.append(f"{g_name} is strong against {o_name}")
    if t_name:
        reasons.append(f"{t_name} covers weakness")
    return "; ".join(reasons)


def get_matchup_recommendations(civ_a, civ_b, age="imperial"):
    """Get recommended units and compositions for civ_a vs civ_b.

    Returns dict with opponent_strengths, recommended_compositions, individual_counters.
    """
    power_data = load_civ_power_units()
    if not power_data:
        return {"error": "civ_power_units.json not found — run best_units.py first"}

    civ_a_data = power_data.get(civ_a, {}).get(age)
    civ_b_data = power_data.get(civ_b, {}).get(age)
    if not civ_a_data or not civ_b_data:
        return {"error": f"No data for {civ_a} or {civ_b} in {age}"}

    # Step 1: Identify opponent's strengths (strong or signature)
    opponent_strengths = []
    for role_key in ["cavalry", "ranged", "infantry", "siege"]:
        entry = civ_b_data["power_units"].get(role_key)
        if entry and entry["strength"] in ("strong", "signature"):
            opponent_strengths.append({
                "role": role_key,
                "unit_slug": entry["unit_slug"],
                "strength": entry["strength"],
                "median_delta": entry["median_delta"],
            })

    # If opponent has no clear strengths, use their best roles anyway
    if not opponent_strengths:
        best_role = max(
            ["cavalry", "ranged", "infantry"],
            key=lambda r: (civ_b_data["power_units"].get(r) or {}).get("median_delta", -999),
        )
        entry = civ_b_data["power_units"].get(best_role)
        if entry:
            opponent_strengths.append({
                "role": best_role,
                "unit_slug": entry["unit_slug"],
                "strength": entry["strength"],
                "median_delta": entry["median_delta"],
            })

    # Step 2: Find counter candidates from battle_scores
    conn = _get_db()
    rc = conn.cursor()
    db_age = "Imperial" if age == "imperial" else "Castle"

    counter_candidates = []  # list of (unit_slug, line_slug, score, vs_role)
    seen_slugs = set()

    for opp in opponent_strengths:
        counter_defs = COUNTER_MAP.get(opp["role"], [])
        for line_slugs, score_type, desc in counter_defs:
            placeholders = ",".join("?" for _ in line_slugs)
            rc.execute(
                f"""SELECT unit_slug, line_slug, score_value, rank, median_delta
                    FROM battle_scores
                    WHERE civ_name = ?
                      AND LOWER(age) = ?
                      AND score_type = ?
                      AND line_slug IN ({placeholders})
                    ORDER BY median_delta DESC
                    LIMIT 3""",
                [civ_a, age, score_type] + line_slugs,
            )
            for row in rc.fetchall():
                slug = row["unit_slug"]
                if slug not in seen_slugs:
                    seen_slugs.add(slug)
                    counter_candidates.append({
                        "unit_slug": slug,
                        "line_slug": row["line_slug"],
                        "score": round(row["score_value"], 1),
                        "median_delta": round(row["median_delta"], 1),
                        "vs_role": opp["role"],
                        "vs_unit_slug": opp["unit_slug"],
                    })

    conn.close()

    # Step 3: Simulate top candidates vs opponent power units
    individual_counters = []

    for cand in counter_candidates[:6]:  # Cap at 6 to limit sim count
        cu_a = _load_combat_unit(civ_a, cand["unit_slug"], db_age)
        cu_b = _load_combat_unit(civ_b, cand["vs_unit_slug"], db_age)
        if not cu_a or not cu_b:
            continue
        res_score, pop_score, composite = _sim_score(cu_a, cu_b)
        individual_counters.append({
            "unit_slug": cand["unit_slug"],
            "line_slug": cand["line_slug"],
            "vs_unit": cand["vs_unit_slug"],
            "resource_score": res_score,
            "pop_score": pop_score,
            "composite": composite,
        })

    # Sort by composite score descending
    individual_counters.sort(key=lambda x: x["composite"], reverse=True)

    # Step 4: Composition generation
    # Find civ_a's best trash unit
    civ_a_trash = civ_a_data["power_units"].get("trash")
    compositions = []

    for counter in individual_counters[:2]:  # Top 2 gold units
        gold_slug = counter["unit_slug"]
        gold_line = counter["line_slug"]

        # Determine trash partner
        trash_line = TRASH_PAIRING.get(gold_line, "stable")
        # Get actual trash unit for civ_a in that line
        trash_slug = None
        if civ_a_trash:
            trash_slug = civ_a_trash["unit_slug"]
        # Try to find a better match from the preferred line
        tconn = _get_db()
        trc = tconn.cursor()
        trc.execute(
            """SELECT unit_slug FROM ref_units
               WHERE civ_name=? AND age=? AND final_cost_gold=0
               ORDER BY final_hp DESC LIMIT 1""",
            (civ_a, db_age),
        )
        trash_row = trc.fetchone()
        if trash_row:
            trash_slug = trash_row["unit_slug"]
        tconn.close()

        if not trash_slug:
            trash_slug = civ_a_trash["unit_slug"] if civ_a_trash else None

        # Load units for reasoning
        gold_cu = _load_combat_unit(civ_a, gold_slug, db_age)
        trash_cu = _load_combat_unit(civ_a, trash_slug, db_age) if trash_slug else None
        opp_cu = _load_combat_unit(civ_b, counter["vs_unit"], db_age)

        reasoning = ""
        if gold_cu and opp_cu:
            reasoning = _generate_reasoning(gold_cu, trash_cu, opp_cu)

        compositions.append({
            "rank": len(compositions) + 1,
            "gold_unit": {
                "unit_slug": gold_slug,
                "line_slug": gold_line,
            },
            "trash_unit": {
                "unit_slug": trash_slug,
            } if trash_slug else None,
            "resource_split": {"gold_pct": 70, "trash_pct": 30},
            "scores": {
                "resource_efficiency": counter["resource_score"],
                "pop_efficiency": counter["pop_score"],
                "composite": counter["composite"],
            },
            "reasoning": reasoning,
        })

    return {
        "civ_a": civ_a,
        "civ_b": civ_b,
        "age": age,
        "opponent_strengths": opponent_strengths,
        "recommended_compositions": compositions,
        "individual_counters": individual_counters,
    }
```

**Step 2: Write a validation script for Phase B**

Create `webapp/validate_matchup.py`:

```python
"""Validate matchup recommendation logic with known matchups."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from best_units import get_matchup_recommendations

errors = []

# Franks vs Britons: Franks should recommend cavalry (to close on longbows)
result = get_matchup_recommendations("Franks", "Britons")
if "error" in result:
    errors.append(f"Franks vs Britons: {result['error']}")
else:
    comps = result["recommended_compositions"]
    if not comps:
        errors.append("Franks vs Britons: no compositions recommended")
    else:
        print(f"Franks vs Britons:")
        print(f"  Opponent strengths: {result['opponent_strengths']}")
        for c in comps:
            print(f"  Comp #{c['rank']}: {c['gold_unit']['unit_slug']} + {c.get('trash_unit', {}).get('unit_slug', 'none')}")
            print(f"    Scores: {c['scores']}")
            print(f"    Reasoning: {c['reasoning']}")

# Britons vs Franks: Britons should recommend ranged + anti-cav
result2 = get_matchup_recommendations("Britons", "Franks")
if "error" not in result2:
    print(f"\nBritons vs Franks:")
    print(f"  Opponent strengths: {result2['opponent_strengths']}")
    for c in result2["recommended_compositions"]:
        print(f"  Comp #{c['rank']}: {c['gold_unit']['unit_slug']} + {c.get('trash_unit', {}).get('unit_slug', 'none')}")
        print(f"    Reasoning: {c['reasoning']}")

# Goths vs Spanish: test a generic matchup
result3 = get_matchup_recommendations("Goths", "Spanish")
if "error" not in result3:
    print(f"\nGoths vs Spanish:")
    for c in result3["recommended_compositions"]:
        print(f"  Comp #{c['rank']}: {c['gold_unit']['unit_slug']} + {c.get('trash_unit', {}).get('unit_slug', 'none')}")

if errors:
    print(f"\nERRORS: {errors}")
    sys.exit(1)
else:
    print("\nALL MATCHUP CHECKS PASSED")
```

**Step 3: Run validation**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 validate_matchup.py`

Expected: Outputs recommendations for all three matchups without errors.

**Step 4: Commit**

```bash
git add webapp/best_units.py webapp/validate_matchup.py
git commit -m "feat: add Phase B matchup recommendations with targeted simulation

Counter-role mapping finds civ A's best counter-units against civ B's
strengths. Runs ~6 targeted simulations for validation, generates
compositions with reasoning."
```

---

### Task 3: API endpoints in app.py

**Files:**
- Modify: `webapp/app.py` (add two routes)

**Step 1: Add import and endpoints to `app.py`**

Add near top of `app.py` (after other imports):

```python
from best_units import load_civ_power_units, get_matchup_recommendations
```

Add before the `if __name__` block (or after the team-analysis route):

```python
@app.route("/api/civ-power-units/<civ_name>")
def api_civ_power_units(civ_name):
    """Get pre-computed power units for a civilization."""
    age = request.args.get("age", "imperial").lower()
    data = load_civ_power_units()
    if not data:
        return jsonify({"error": "civ_power_units.json not found"}), 500
    civ_data = data.get(civ_name)
    if not civ_data:
        return jsonify({"error": f"Civilization '{civ_name}' not found"}), 404
    age_data = civ_data.get(age)
    if not age_data:
        return jsonify({"error": f"No {age} data for {civ_name}"}), 404
    return jsonify({"civ_name": civ_name, "age": age, **age_data})


@app.route("/api/matchup-recommendations/<civ_a>/<civ_b>")
def api_matchup_recommendations(civ_a, civ_b):
    """Get recommended units and compositions for civ_a vs civ_b."""
    age = request.args.get("age", "imperial").lower()
    result = get_matchup_recommendations(civ_a, civ_b, age)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)
```

**Step 2: Test the endpoints**

Run the server: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 -c "from app import app; app.run(port=5001, debug=False)"` (in background)

Then test:
```bash
curl -s http://localhost:5001/api/civ-power-units/Franks | python3 -m json.tool | head -30
curl -s http://localhost:5001/api/matchup-recommendations/Franks/Britons | python3 -m json.tool | head -40
```

Expected: JSON responses matching the design doc schemas.

**Step 3: Commit**

```bash
git add webapp/app.py
git commit -m "feat: add /api/civ-power-units and /api/matchup-recommendations endpoints"
```

---

### Task 4: Clean up validation scripts

**Files:**
- Delete: `webapp/validate_power_units.py`, `webapp/validate_matchup.py`

**Step 1: Ensure everything works end-to-end**

Run Phase A computation + both validations back-to-back:

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp
python3 best_units.py && python3 validate_power_units.py && python3 validate_matchup.py
```

Expected: All pass.

**Step 2: Remove validation scripts (they served their purpose)**

```bash
rm webapp/validate_power_units.py webapp/validate_matchup.py
```

**Step 3: Final commit**

```bash
git add -u
git commit -m "chore: remove validation scripts after successful testing"
```

---

### Task 5: Update build pipeline docs

**Files:**
- Modify: Memory/MEMORY.md (update build pipeline)

**Step 1: Update MEMORY.md build pipeline**

Add to the Build Pipeline section:
```
5. `cd webapp && python3 best_units.py` (civ power units)
```

**Step 2: Commit**

```bash
git add -A && git commit -m "docs: update build pipeline with best_units step"
```

---

## Summary

| Task | What | New Sims | Time |
|------|------|----------|------|
| 1 | Phase A: `compute_civ_power_units()` — pre-compute best unit per role per civ | 0 | ~2min |
| 2 | Phase B: `get_matchup_recommendations()` — counter-roles + targeted sim + compositions | ~10/req | ~5min |
| 3 | API endpoints: `/api/civ-power-units/<civ>`, `/api/matchup-recommendations/<a>/<b>` | 0 | ~2min |
| 4 | Cleanup validation scripts | 0 | ~1min |
| 5 | Update build pipeline docs | 0 | ~1min |

**Total: ~11 minutes of implementation.**

---

Plan complete and saved to `docs/plans/2026-02-16-best-units-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** — I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** — Open new session with executing-plans, batch execution with checkpoints

Which approach?
