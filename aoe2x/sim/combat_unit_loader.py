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

from aoe2x.dbgen.ability_registry import iter_params


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


# ---------------------------------------------------------------------------
# TRUE COLLISION SIZE (E11)
#
# The .dat carries TWO size fields per unit and this pipeline only ever
# extracted the wrong one. ``outline_size_x`` is the SELECTION CIRCLE — the
# visual footprint. ``collision_size_x`` is the physics radius that decides how
# tightly units pack and where "in contact" is. They are NOT the same number
# for anything mounted:
#
#     unit                     collision_size_x    outline_size_x
#     champion / halberdier            0.20             0.20
#     arbalester / skirm / HC          0.20             0.20
#     paladin / hussar / camel         0.25             0.40
#     elite steppe lancer              0.25             0.40
#     heavy cavalry archer             0.25             0.40
#     elite battle elephant            0.25             0.50   <-- big LOOKING
#     heavy scorpion / siege onager    0.50             0.50
#
# (read from D:/SteamLibrary/.../empires2_x2_p1.dat via genieutils, 2026-07-30)
#
# The recorded tapes confirm this independently: the p10 of same-owner
# nearest-neighbour distance over all 155 recordings is 0.394 tiles for
# champions, 0.400 for halberdiers/fire lancers, 0.43-0.50 for every mounted
# unit INCLUDING the elephant, and exactly 1.000 for scorpions and onagers —
# i.e. 2 x collision_size_x in every class, never 2 x outline_size_x.
#
# ref_units stores outline_size_x but not collision_size_x (adding it would
# mean re-extracting the .dat and regenerating aoe2_reference.db). It DOES
# store unit_class, and that plus the outline reproduces the .dat's
# collision_size_x exactly for every unit in the calibration corpus, and for
# 920 of the 966 mobile units in the .dat overall (95.2%).
#
# The 46 exceptions are all units outside the corpus and outside normal
# matchup play: rams and hussite wagons (class 13/55 outline 0.8 -> true 0.45,
# we say 0.5), war chariots, ox carts, boats, animals and campaign heroes.
_MOUNTED_CLASSES = frozenset({
    12,   # Cavalry (knight line, camels, steppe lancers, battle elephants)
    18,   # Monk-on-horse variants
    19,   # (mounted misc)
    23,   # Conquistador
    35,   # Camel Rider (legacy class)
    36,   # Cavalry Archer
    47,   # (mounted misc)
})

# Physics radius caps, in tiles. Mounted units cap at a quarter tile however
# large their selection circle is; everything on foot or on wheels uses its
# own outline, capped at half a tile (the largest real siege collision).
_MOUNTED_COLLISION_CAP = 0.25
_DEFAULT_COLLISION_CAP = 0.5


def collision_size_tiles(unit_class, outline_size):
    """The unit's TRUE .dat collision radius in tiles (see the block above)."""
    outline = outline_size or 0.2
    cap = (_MOUNTED_COLLISION_CAP if unit_class in _MOUNTED_CLASSES
           else _DEFAULT_COLLISION_CAP)
    return min(outline, cap)


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
        # final_range is real for melee too: the Steppe Lancer line, Kamayuk
        # and Hulk carry 1.0 tile of melee reach (attack over the front rank).
        # Zeroing it for is_ranged=0 units erased that trait from every engine.
        # is_ranged must travel explicitly: consumers used to infer ranged-ness
        # from attack_range >= 1, which a 1.0-reach melee unit now defeats.
        "attack_range": row["final_range"] or 0,
        "is_ranged": row["is_ranged"],
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
        # Outline size — the SELECTION CIRCLE, i.e. how big the unit LOOKS.
        # Kept because simulation_real.py still derives its radius from it and
        # the renderer wants the visual footprint. Not the physics radius.
        "outline_size": row["outline_size_x"] or 0.2,
        # Collision size — the TRUE .dat physics radius in tiles, which is what
        # decides packing, contact distance and melee reach. See the
        # collision_size_tiles() block above for the .dat readout and the tape
        # measurements that confirm it.
        "collision_size": collision_size_tiles(
            _get(row, "unit_class"), row["outline_size_x"]),
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
