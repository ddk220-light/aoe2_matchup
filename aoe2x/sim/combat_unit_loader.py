"""Role: serving — shared combat-unit dict builder for ref_units rows.

All callers (app.py, best_units.py, run_matchup_battles.py,
compute_battle_scores.py) import this single canonical mapping.

Phase B (data-model-review §3.2): the ability-key portion of the dict is
GENERATED from analysis/ability_registry.py — every registry param with
``in_combat_dict=True`` is emitted, reading ``param.column`` and falling back
to ``param.default``. Only the core stats (hp/attack/armor/costs/jsons/
accuracy/outline) remain hand-written. Adding an ability never touches this
file again.
"""

try:
    from analysis.ability_registry import iter_params
except ImportError:  # pragma: no cover - launch dir on sys.path, repo root not
    # Production (gunicorn) starts from webapp/, where the repo root is not
    # importable; analysis/ lives at the repo root (until it moves to
    # aoe2x.dbgen in migration Stage 4).
    import sys
    from pathlib import Path

    _ROOT = str(Path(__file__).resolve().parents[2])
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from analysis.ability_registry import iter_params


def _get(row, key, default=None):
    """Read a sqlite3.Row column, returning `default` if the column is missing.

    sqlite3.Row raises IndexError on unknown keys, but some DBs (e.g. an older
    aoe2_reference.db built before a column was added) may not have every
    column the simulator now expects. This lets newer code work against older
    DB blobs without crashing.
    """
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


# Casts the pre-registry hand-written mapping applied on top of the
# null-coalesce. int-typed params are int()-cast uniformly — a no-op for
# INTEGER columns (verified: every int param's column stores only integers)
# and semantic only for attack_bonus_per_kill, whose column is historically
# REAL. charge_attack_range is the one float()-cast param (REAL column whose
# zero rows must coalesce to 0.0, not int 0, for output-identity with the
# pre-registry loader).
_FLOAT_CAST_PARAMS = frozenset({"charge_attack_range"})


def _ability_fields():
    """[(dict key, ref column, python type, default)] from the registry."""
    return tuple(
        (p.name, p.column, p.type, p.default)
        for _a, p in iter_params()
        if p.in_combat_dict
    )


_ABILITY_FIELDS = _ability_fields()


def build_combat_dict_from_ref(row):
    """Build a combat-unit dict from a ref_units row.

    Compatible with prepare_combat_unit() from simulation.py. Core stats are
    hand-written below; every special-ability key is generated from the
    ability registry (see module docstring).
    """
    reload_time = row["final_reload_time"] or 2.0
    attack_speed = 1.0 / reload_time if reload_time > 0 else 0.5

    unit = {
        "slug": row["unit_slug"],
        "unit_name": row["unit_name"],
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
        # Base accuracy (pre-Thumb Ring) is the per-arrow rate for SECONDARY
        # projectiles — Thumb Ring boosts only the primary arrow. Used by
        # simulation.py to roll extra-projectile hits at the unit's natural
        # accuracy (e.g. 85% for Chu Ko Nu) rather than a flat 50% heuristic.
        "base_accuracy": row["base_accuracy"] or 100,
        # Outline size — used by the position-aware sim (simulation_real.py)
        # to compute unit radius for collision/range calculations.  Not used
        # by the abstract tick-based sim in simulation.py.
        "outline_size": row["outline_size_x"] or 0.2,
    }

    for name, column, type_, default in _ABILITY_FIELDS:
        if column is None:
            # Not stored in ref_units (unit_category, paired_unit_slug):
            # the loader emits the registry default.
            unit[name] = default
        elif default is None:
            # Raw NULL passthrough: JSON blobs + dismount/transform stat blocks.
            unit[name] = _get(row, column)
        else:
            value = _get(row, column) or default
            if type_ is int:
                value = int(value)
            elif name in _FLOAT_CAST_PARAMS:
                value = float(value)
            unit[name] = value

    return unit
