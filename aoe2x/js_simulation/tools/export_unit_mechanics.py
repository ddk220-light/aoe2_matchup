"""Export source-backed Imperial unit mechanics for the JS simulator.

    python export_unit_mechanics.py --unit-slug champion --civ Chinese \
        --master 567 --reference-db ... --dat ... --output ...
"""

from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import math
import sqlite3
from pathlib import Path
import sys
from typing import Any

from aoe2x.dbgen.v3_runtime_config import (
    RUNTIME_EFFECTS_BY_CIV_SLUG,
    RUNTIME_EFFECTS_BY_SLUG,
)


IMPERIAL_AGE = "Imperial"

# The reference database uses current UI civilization names; four legacy
# Genie records retain their original internal names in build 177723.
REFERENCE_TO_DAT_CIV = {
    "Britons": "British",
    "Byzantines": "Byzantine",
    "Franks": "French",
    "Mayans": "Mayan",
}


# Runtime ability columns are generated from dbgen/ability_registry.py into
# ref_units.  Keeping this list in the fixture exporter means the JS combat
# engine consumes the same fully-upgraded, civilization-specific values as the
# reference site and the older engines, without naming a matchup or reading a
# captured result.  JSON attack/form blocks are decoded below; scalar zeroes
# and nulls are omitted from the fixture so ordinary units retain a compact
# shape.
REFERENCE_EFFECT_COLUMNS = (
    "base_accuracy",
    "extra_projectiles",
    "extra_projectile_attacks_json",
    "first_attack_extra_projectiles",
    "charge_projectile_count",
    "charge_projectile_attacks_json",
    "charge_projectile_speed",
    "charge_attack_range",
    "charge_ignores_armor",
    "trample_percent",
    "trample_radius",
    "trample_flat_damage",
    "splash_on_hit_radius",
    "splash_on_hit_fraction",
    "bleed_dps",
    "bleed_duration",
    "attack_bonus_per_kill",
    "hp_transform_threshold",
    "hp_regen",
    "hp_regen_in_combat",
    "pass_through_percent",
    "pass_through_count",
    "extra_proj_scatter",
    "miss_damage_percent",
    "hp_per_kill",
    "hp_per_kill_max",
    "armor_strip_per_hit",
    "ignores_melee_armor",
    "ignores_pierce_armor",
    "charge_attack_melee",
    "charge_recharge_time",
    "damage_reflect_percent",
    "attack_bonus_nearby",
    "nearby_bonus_count",
    "hp_nearby_percent_per_unit",
    "hp_nearby_max_units",
    "charge_slow_percent",
    "charge_slow_duration",
    "attack_speed_ramp",
    "attack_speed_min",
    "execute_damage_per_step",
    "execute_hp_step",
    "ally_death_heal",
    "ally_death_heal_duration",
    "transform_hp",
    "transform_attack",
    "transform_melee_armor",
    "transform_pierce_armor",
    "transform_attack_speed",
    "transform_attack_delay",
    "transform_movement_speed",
    "transform_attacks_json",
    "transform_armors_json",
)


JSON_EFFECT_COLUMNS = frozenset({
    "extra_projectile_attacks_json",
    "charge_projectile_attacks_json",
    "transform_attacks_json",
    "transform_armors_json",
})


# Backwards-compatible aliases for existing importers.  The declarations live
# in dbgen now so fixture export and the production mechanics database cannot
# drift apart.
CURATED_RUNTIME_EFFECTS = RUNTIME_EFFECTS_BY_SLUG
CURATED_CIV_RUNTIME_EFFECTS = RUNTIME_EFFECTS_BY_CIV_SLUG


@lru_cache(maxsize=8)
def _sha256_cached(path_text: str) -> str:
    digest = hashlib.sha256()
    path = Path(path_text)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _sha256(path: Path) -> str:
    return _sha256_cached(str(Path(path).resolve()))


def _read_reference_row(reference_db: Path, unit_slug: str, civ: str) -> dict[str, Any]:
    reference_db = reference_db.resolve()
    uri = f"{reference_db.as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        effect_columns = ",\n                ".join(REFERENCE_EFFECT_COLUMNS)
        rows = connection.execute(
            f"""
            SELECT
                id,
                civ_name,
                age,
                final_hp,
                final_speed,
                final_range,
                min_range,
                final_reload_time,
                final_attack_delay,
                final_accuracy,
                final_los,
                final_attacks_json,
                final_armors_json,
                pop_space,
                {effect_columns}
            FROM ref_units
            WHERE unit_slug = ? AND civ_name = ? AND age = ?
            """,
            (unit_slug, civ, IMPERIAL_AGE),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError(
                f"reference DB must contain exactly one {civ} Imperial {unit_slug} "
                f"row; found {len(rows)}"
            )
        row = dict(rows[0])
        # ref_units.final_speed is rounded to 2 decimals by the DB generator, which
        # turns the Squires-modified 0.96 x 1.1 into 1.06 and makes every unit run
        # 0.38% fast. ref_stat_chain keeps the unrounded value, and the authorized
        # tapes measure exactly 1.056 tiles/s, so take the chain's last step.
        chain = connection.execute(
            """
            SELECT speed
            FROM ref_stat_chain
            WHERE ref_unit_id = ?
            ORDER BY step_order DESC
            LIMIT 1
            """,
            (row["id"],),
        ).fetchone()
        row["applied_tech_ids"] = tuple(
            int(tech["tech_id"])
            for tech in connection.execute(
                "SELECT tech_id FROM ref_techs_applied WHERE ref_unit_id = ?",
                (row["id"],),
            ).fetchall()
        )
    if chain is None:
        raise ValueError(f"reference DB has no stat chain for the {civ} {unit_slug}")
    row["exact_speed"] = float(chain["speed"])
    if abs(row["exact_speed"] - float(row["final_speed"])) > 0.05:
        raise ValueError(
            "stat-chain speed disagrees with ref_units.final_speed beyond rounding: "
            f"{row['exact_speed']} vs {row['final_speed']}"
        )
    return row


def _runtime_effects(reference: dict[str, Any], unit_slug: str) -> dict[str, Any] | None:
    effects: dict[str, Any] = {}
    for name in REFERENCE_EFFECT_COLUMNS:
        value = reference.get(name)
        if value is None or value == 0 or value == 0.0 or value == "":
            continue
        output_name = name.removesuffix("_json")
        if name in JSON_EFFECT_COLUMNS:
            parsed = _parse_classes(value)
            if parsed:
                effects[output_name] = parsed
        else:
            effects[output_name] = value
    effects.update(RUNTIME_EFFECTS_BY_SLUG.get(unit_slug, {}))
    effects.update(RUNTIME_EFFECTS_BY_CIV_SLUG.get(
        (reference["civ_name"], unit_slug), {}
    ))
    return effects or None


def _parse_classes(raw: str) -> dict[str, int | float]:
    return {
        str(class_id): amount
        for class_id, amount in sorted(
            json.loads(raw).items(), key=lambda item: int(item[0])
        )
    }


def _decode_armor_attack_value(value: float) -> tuple[int, int]:
    """Decode Genie's class * 256 + signed-byte amount representation."""
    encoded = int(value)
    if encoded >= 0:
        class_id = encoded // 256
        amount = encoded % 256
        if amount > 127:
            amount -= 256
        return class_id, amount
    encoded = abs(encoded)
    return encoded // 256, -(encoded % 256)


def _damage_reduction_by_attacker_category(
    data, unit_master: int, applied_tech_ids: tuple[int, ...]
) -> dict[str, int] | None:
    """Export sourced conditional incoming-damage reductions.

    Royal Heirs (tech 574) adds three points of armor class 39 to each
    affected target. Build 177723 uses negative class-39 attack entries as the
    mounted-attacker marker. The game-facing effect is therefore represented
    explicitly as flat incoming damage reduction from mounted attackers,
    rather than pretending it is ordinary melee or pierce armor.
    """
    royal_heirs_tech_id = 574
    if royal_heirs_tech_id not in applied_tech_ids:
        return None
    tech = data.techs[royal_heirs_tech_id]
    effect = data.effects[int(tech.effect_id)]
    if effect.name != "Royal Heirs":
        raise ValueError(
            f"tech {royal_heirs_tech_id} must resolve to Royal Heirs, got {effect.name!r}"
        )
    reductions = []
    for command in effect.effect_commands:
        if (
            int(command.type) != 4
            or int(command.a) != unit_master
            or int(command.c) != 8
        ):
            continue
        class_id, amount = _decode_armor_attack_value(command.d)
        if class_id == 39 and amount > 0:
            reductions.append(amount)
    if reductions != [3]:
        raise ValueError(
            f"Royal Heirs must give master {unit_master} one +3 class-39 effect; "
            f"found {reductions}"
        )
    return {"mounted": 3}


def _damage_against_self(
    attack_classes: dict[str, int | float],
    armor_classes: dict[str, int | float],
) -> int | float:
    """Apply the AoE class rule to the unit's own attack and armor maps.

    Melee units carry their base attack in class 4, ranged units in class 3
    (archers have no class-4 attack at all); both are ordinary armor classes
    under the one shared rule, followed by any matching bonus classes.
    """
    def numeric(classes, class_id, label):
        value = classes[class_id]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"{label} class {class_id} must be numeric")
        return value

    if not any(
        class_id in attack_classes and numeric(attack_classes, class_id, "attack") > 0
        for class_id in ("4", "3")
    ):
        raise ValueError("attack must carry a positive class 4 or class 3 value")
    damage = 0
    for class_id in ("4", "3"):
        if class_id not in attack_classes or class_id not in armor_classes:
            continue
        damage += max(0, numeric(attack_classes, class_id, "attack")
                      - numeric(armor_classes, class_id, "armor"))
    for class_id, attack in attack_classes.items():
        if class_id in {"3", "4"} or attack <= 0 or class_id not in armor_classes:
            continue
        damage += max(0, attack - armor_classes[class_id])
    return max(1, damage)


@lru_cache(maxsize=2)
def _parsed_dat(dat_path_text: str):
    from genieutils.datfile import DatFile

    return DatFile.parse(Path(dat_path_text))


def _raw_unit(dat_path: Path, civ: str, master: int):
    dat_path = Path(dat_path).resolve()

    data = _parsed_dat(str(dat_path))
    dat_civ = REFERENCE_TO_DAT_CIV.get(civ, civ)
    matches = [
        civilization for civilization in data.civs
        if civilization.name == dat_civ
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Genie .dat must contain exactly one {dat_civ} civilization "
            f"for reference civ {civ}; "
            f"found {len(matches)}"
        )
    unit = matches[0].units[master]
    if unit is None or unit.id != master:
        raise ValueError(f"Genie .dat does not contain {civ} master {master}")
    return data, unit


@lru_cache(maxsize=1)
def _unit_analyzer():
    """Load the shared fully-teched stat evaluator once for concrete forms."""
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from aoe2x.dbgen.unit_analyzer import UnitAnalyzer

    return UnitAnalyzer()


def _concrete_form_stats(civ: str, master: int):
    """Fully upgrade a real DAT form rather than its public mode-switch shell."""
    stats = _unit_analyzer().calculate_form_stats(civ, master, 4)
    if stats is None:
        raise ValueError(f"cannot derive fully-teched {civ} form master {master}")
    return stats


def _civilization_reload_multiplier(data, civ: str, unit) -> float:
    """Return direct civilization tech-tree multipliers for reload attribute 10.

    The reference DB's final_reload_time does not apply civilization tech-tree
    effects such as the Spanish 15% faster gunpowder reload. Genie effect type
    5 multiplies an attribute; a == -1/b == class targets a unit class, while
    a == unit.id targets one master. Deriving this from the selected civ's raw
    tech-tree effect keeps the exporter generic and source-backed.
    """
    dat_civ = REFERENCE_TO_DAT_CIV.get(civ, civ)
    civilization = next(current for current in data.civs if current.name == dat_civ)
    effect = data.effects[int(civilization.tech_tree_id)]
    multiplier = 1.0
    for command in effect.effect_commands:
        if int(command.type) != 5 or int(command.c) != 10:
            continue
        targets_unit = int(command.a) == int(unit.id)
        targets_class = int(command.a) == -1 and int(command.b) == int(unit.class_)
        if targets_unit or targets_class:
            multiplier *= float(command.d)
    return round(multiplier, 6)


def _animation_seconds(data, graphic_id: int, label: str) -> dict[str, Any]:
    """Return DAT animation timing, including composite parent graphics.

    Some valid Genie graphics are one-frame containers with a zero duration;
    their animated hull/weapon layers live in ``graphic.deltas``.  In that
    case the longest usable direct child is the visual cycle.  This keeps the
    value DAT-derived while avoiding a synthetic per-unit fallback.
    """
    if graphic_id is None or graphic_id < 0:
        raise ValueError(f"{label} graphic is absent")
    graphic = data.graphics[graphic_id]
    frames = int(graphic.frame_count)
    duration = float(graphic.frame_duration)
    timing_graphic_id = graphic_id
    if frames <= 0 or not math.isfinite(duration) or duration <= 0:
        candidates = []
        for delta in graphic.deltas:
            child_id = int(delta.graphic_id)
            if child_id < 0 or child_id >= len(data.graphics):
                continue
            child = data.graphics[child_id]
            child_frames = int(child.frame_count)
            child_duration = float(child.frame_duration)
            if child_frames > 0 and math.isfinite(child_duration) and child_duration > 0:
                candidates.append(
                    (child_frames * child_duration, child_id, child_frames, child_duration)
                )
        if not candidates:
            raise ValueError(f"{label} graphic {graphic_id} has no usable frame timing")
        _, timing_graphic_id, frames, duration = max(candidates)
    return {
        "graphic": graphic_id,
        **(
            {"timing_graphic": timing_graphic_id}
            if timing_graphic_id != graphic_id else {}
        ),
        "frames": frames,
        "frame_duration_seconds": duration,
        "seconds": frames * duration,
    }


def export_unit_mechanics(
    reference_db: Path,
    dat_path: Path,
    unit_slug: str,
    civ: str,
    master: int,
    *,
    concrete_form: bool = False,
    extra_projectile_count: int | None = None,
    volley_release_interval_seconds: float | None = None,
    volley_release_size: int | None = None,
    volley_double_release_percent: float | None = None,
    volley_release_source: str | None = None,
    weapon_mode: str | None = None,
) -> dict:
    """Return the Imperial mechanics fixture for one unit x civilization.

    ``concrete_form`` is for real DAT units hidden behind a public transform or
    weapon-mode shell.  It runs that concrete master through the same standard,
    civilization, team, and unique-technology chain as an ordinary unit.  No
    observed matchup result participates in the calculation.
    """
    reference_db = Path(reference_db)
    dat_path = Path(dat_path)
    reference = _read_reference_row(reference_db, unit_slug, civ)
    data, unit = _raw_unit(dat_path, civ, master)
    form_stats = _concrete_form_stats(civ, master) if concrete_form else None
    attack_classes = (
        {str(class_id): amount for class_id, amount in sorted(form_stats.attacks.items())}
        if form_stats else _parse_classes(reference["final_attacks_json"])
    )
    armor_classes = (
        {str(class_id): amount for class_id, amount in sorted(form_stats.armors.items())}
        if form_stats else _parse_classes(reference["final_armors_json"])
    )
    damage_reduction = _damage_reduction_by_attacker_category(
        data, master, reference["applied_tech_ids"]
    )
    reload_multiplier = (
        1.0 if form_stats else _civilization_reload_multiplier(data, civ, unit)
    )
    reload_seconds = round(
        float(form_stats.reload_time) if form_stats
        else float(reference["final_reload_time"]) * reload_multiplier,
        6,
    )

    attack_animation = _animation_seconds(
        data, int(unit.type_50.attack_graphic), "attack")
    # Idle/walk animations are informational (nothing in the engine reads
    # them); siege sprites can be static frames with no usable timing.
    try:
        idle_animation = _animation_seconds(
            data, int(unit.standing_graphic[0]), "idle")
    except ValueError:
        idle_animation = None
    try:
        walk_animation = _animation_seconds(
            data, int(unit.dead_fish.walking_graphic), "walk")
    except ValueError:
        walk_animation = None
    try:
        death_animation = _animation_seconds(
            data, int(unit.dying_graphic), "death")
    except ValueError:
        death_animation = None

    # Genie hit timing. The hit lands on animation frame `frame_delay`, so
    #   attack_delay = animation_seconds * frame_delay / frame_count
    # `frame_delay == 0` is normally an UNSET sentinel, so ordinary attacks
    # fall back to the animation midpoint. Mangonel-family blast projectiles
    # are the measured exception: the primary shell appears on the very next
    # recorder frame after action-state 7 begins (0.016-0.018 s), so their
    # zero frame is a literal immediate release rather than the sentinel.
    #
    # Both branches are confirmed against the authorized tapes, which is why
    # this is a sourced rule and not a fitted one:
    #   Champion (frame_delay 0,  1.500 s anim) -> 0.750 s, tape floor 0.750
    #   Paladin  (frame_delay 13, 1.550 s anim) -> 0.672 s, tape floor 0.672
    # In both tapes the measured spread is one render frame wide (~17 ms) and
    # sits ABOVE the computed value, exactly as sampling lag predicts.
    #
    # ref_units.final_attack_delay must NOT be used: it stores frame_delay/60
    # (0.217 s for the Paladin), which the tape rules out by a factor of three.
    frame_delay = int(unit.type_50.frame_delay)
    immediate_blast_projectile = (
        frame_delay == 0
        and int(unit.type_50.blast_attack_level) == 1
        and float(unit.type_50.blast_width) > 0
    )
    if immediate_blast_projectile:
        attack_delay_seconds = 0.0
        attack_delay_source = (
            "zero-frame-delay blast projectile: immediate shell release"
        )
    elif frame_delay == 0:
        attack_delay_seconds = attack_animation["seconds"] / 2
        attack_delay_source = (
            "frame_delay unset (0): hit at the attack-animation midpoint"
        )
    else:
        attack_delay_seconds = (
            attack_animation["seconds"] * frame_delay / attack_animation["frames"]
        )
        attack_delay_source = (
            "hit on animation frame frame_delay:"
            " attack animation seconds * frame_delay / frames"
        )

    fields = {
        "unit_master": "unit.id",
        "blast.width_tiles": "unit.type_50.blast_width",
        "blast.damage_fraction": "unit.type_50.blast_damage",
        "blast.attack_level": "unit.type_50.blast_attack_level",
        "blast.defense_level": "unit.blast_defense_level",
        "blast.friendly_fire_damage": "unit.type_50.friendly_fire_damage",
        "civilization": "ref_units.civ_name",
        "age": "ref_units.age",
        "hp": "ref_units.final_hp",
        "speed_tiles_per_second": (
            "ref_stat_chain.speed (final step; ref_units.final_speed is rounded)"
        ),
        "attack_range_tiles": "ref_units.final_range",
        "reload_seconds": (
            "ref_units.final_reload_time * matching civilization tech-tree "
            "effect type 5 on reload attribute 10"
        ),
        "attack_delay_seconds": attack_delay_source,
        "attack_animation.graphic": "unit.type_50.attack_graphic",
        "attack_animation.frames": "graphics[attack_graphic].frame_count",
        "attack_animation.frame_duration_seconds": (
            "graphics[attack_graphic].frame_duration, or longest usable direct "
            "delta graphic for a zero-duration composite"
        ),
        "attack_animation.seconds": (
            "frames * frame_duration from the graphic or its longest usable "
            "direct delta"
        ),
        "idle_animation": "graphics[unit.standing_graphic[0]]",
        "walk_animation": "graphics[unit.dead_fish.walking_graphic]",
        "death_animation": "graphics[unit.dying_graphic]",
        "line_of_sight_tiles": "ref_units.final_los",
        "attack_classes": "ref_units.final_attacks_json",
        "armor_classes": "ref_units.final_armors_json",
        "population_space": "ref_units.pop_space",
        "collision_size_tiles.x": "unit.collision_size_x",
        "collision_size_tiles.y": "unit.collision_size_y",
        "collision_size_tiles.z": "unit.collision_size_z",
        "clearance_size_tiles.x": "unit.clearance_size[0]",
        "clearance_size_tiles.y": "unit.clearance_size[1]",
        "outline_size_tiles.x": "unit.outline_size_x",
        "outline_size_tiles.y": "unit.outline_size_y",
        "outline_size_tiles.z": "unit.outline_size_z",
        "obstruction.type": "unit.obstruction_type",
        "obstruction.class": "unit.obstruction_class",
        "movement_blocks.terrain_restriction": "unit.terrain_restriction",
        "movement_blocks.fly_mode": "unit.fly_mode",
        "movement_blocks.hill_mode": "unit.hill_mode",
        "min_collision_size_multiplier": "unit.dead_fish.min_collision_size_multiplier",
        "attack_graphic": "unit.type_50.attack_graphic",
        "frame_delay": "unit.type_50.frame_delay",
        "derived.damage_vs_self": (
            "AoE class rule(ref_units.final_attacks_json,"
            " ref_units.final_armors_json)"
        ),
    }
    if form_stats:
        concrete_source = (
            "aoe2x.dbgen.unit_analyzer.calculate_form_stats"
            f"(civilization='{civ}', unit_id={master}, max_age=4)"
        )
        fields.update({
            "hp": concrete_source + ".hp",
            "speed_tiles_per_second": concrete_source + ".speed",
            "attack_range_tiles": concrete_source + ".range",
            "reload_seconds": concrete_source + ".reload_time",
            "line_of_sight_tiles": concrete_source + ".los",
            "attack_classes": concrete_source + ".attacks",
            "armor_classes": concrete_source + ".armors",
        })
    if damage_reduction is not None:
        fields["damage_reduction_by_attacker_category.mounted"] = (
            "ref_techs_applied.tech_id 574 + dat tech 574/effect 'Royal Heirs': "
            "type 4 adds +3 armor class 39 to this unit; negative attacker "
            "class 39 is the build-177723 mounted marker"
        )

    # Charge ability (Fire Lancer family). Raw dat values, exported whenever
    # charge_type is nonzero. Semantics measured from the four authorized
    # firelancer archives (108 fights, 265 volleys, 684 charge damage events):
    #   - charge_type 6 fires `max_total_projectiles` charge projectiles as the
    #     unit's FIRST attack cycle (units spawn with full charge; every volley
    #     in the tapes is the firer's opening attack; zero refires -- at
    #     recharge_rate 1/30 s no tape fight lasts long enough to test one).
    #   - The charge cycle uses `special_graphic` (charge_event 5 selects it):
    #     2.000 s animation; the volley spawns on frame `frame_delay` (10/30 ->
    #     0.6667 s, tape floor 0.668 across 265 volleys, one render frame wide).
    #     The unit stands for the whole animation: first post-volley movement
    #     at +1.408 s p50 (= anim end 1.333 s + the 0.05-tile detection lag).
    #   - Fired from standstill at the acquisition target, distance 1.5-5.2
    #     tiles (LOS-bounded), no closing beforehand.
    #   - Each projectile flies at the projectile unit's speed and deals the
    #     standard class-matched attack total with the victim's armor VALUES
    #     ignored (treated as 0): champions (PA 5), paladins (PA 7), steppe
    #     lancers (PA 6) and elephants (PA 9) all take exactly 3.0 per hit --
    #     684/684 events, which is the projectile's class-3 pierce amount
    #     alone (no victim here carries its class-17 bonus class).
    #   - 88% of hits land on the volley's target and 2.58 of 3 projectiles
    #     land on average (victim-size independent; the in-game scatter is not
    #     resolvable at the recorder's 10 Hz missile sampling). The JS engine
    #     models all three projectiles on the target and documents the
    #     ~1 damage/volley overshoot as an accepted residual.
    charge = None
    melee_charge = None
    charge_type = int(getattr(unit.creatable, "charge_type", 0) or 0)
    # ref_units is the canonical, fully-upgraded mechanics contract.  In
    # particular, an explicit zero may disable a raw DAT charge representation
    # when the same weapon is represented by ordinary primary/extra projectiles
    # (Wu Fire Archer).  Falling back with ``reference_count or dat_count``
    # resurrected that disabled raw charge and made it replace the real attack.
    # Older reference databases without the column are rejected by the SELECT
    # above, so zero is always meaningful here and must be preserved.
    projectile_count = int(reference.get("charge_projectile_count") or 0)
    # A few units retain a charge_type flag while declaring no charge
    # projectiles at all.  Treat that combination as an inactive DAT feature,
    # matching the database extractor's generic max/total-projectile rule.
    if charge_type in (6, 7) and projectile_count > 0:
        proj_id = int(unit.creatable.charge_projectile_unit)
        proj = data.civs[0].units[proj_id] if proj_id >= 0 else None
        if proj is None:
            raise ValueError(f"charge_type {charge_type} without projectile unit")
        special_graphic = int(unit.creatable.special_graphic)
        charge_animation = (
            _animation_seconds(data, special_graphic, "charge")
            if special_graphic >= 0 else attack_animation
        )
        reference_charge_attacks = reference.get("charge_projectile_attacks_json")
        proj_attacks = (
            _parse_classes(reference_charge_attacks)
            if reference_charge_attacks else {
                str(a.class_): a.amount
                for a in proj.type_50.attacks
                if a.amount > 0
            }
        )
        reference_speed = float(reference.get("charge_projectile_speed") or 0)
        recharge_seconds = float(reference.get("charge_recharge_time") or 0)
        charge = {
            "max_charge": float(unit.creatable.max_charge),
            "recharge_rate": float(unit.creatable.recharge_rate),
            "recharge_seconds": recharge_seconds,
            "charge_type": charge_type,
            "charge_event": int(unit.creatable.charge_event),
            "projectile_unit": proj_id,
            "projectile_count": projectile_count,
            "projectile_speed_tiles_per_second": reference_speed or float(proj.speed),
            "projectile_attacks": proj_attacks,
            "attack_range_tiles": float(
                reference.get("charge_attack_range") or reference["final_range"]),
            "ignores_armor": bool(reference.get("charge_ignores_armor") or 0),
            "adds_to_normal_attack": recharge_seconds > 0
                and float(reference["final_range"]) > 0,
            "charge_animation": charge_animation,
            "windup_seconds": (
                charge_animation["seconds"] * frame_delay
                / charge_animation["frames"]
                if frame_delay > 0 else attack_delay_seconds
            ),
        }
        fields.update({
            "charge.max_charge": "unit.creatable.max_charge",
            "charge.recharge_rate": "unit.creatable.recharge_rate",
            "charge.charge_type": "unit.creatable.charge_type",
            "charge.charge_event": "unit.creatable.charge_event",
            "charge.projectile_unit": "unit.creatable.charge_projectile_unit",
            "charge.projectile_count": (
                "ref_units.charge_projectile_count (explicit zero disables "
                "the raw dat charge representation)"
            ),
            "charge.projectile_speed_tiles_per_second": (
                f"dat.civs[0].units[{proj_id}].speed"
            ),
            "charge.projectile_attacks": (
                "ref_units.charge_projectile_attacks_json; fallback to "
                f"positive dat.civs[0].units[{proj_id}].type_50.attacks"
            ),
            "charge.attack_range_tiles": "ref_units.charge_attack_range",
            "charge.ignores_armor": "ref_units.charge_ignores_armor",
            "charge.adds_to_normal_attack": (
                "ranged charge volley with a positive sourced recharge time"
            ),
            "charge.recharge_seconds": "ref_units.charge_recharge_time",
            "charge.charge_animation": (
                "graphics[unit.creatable.special_graphic]"
            ),
            "charge.windup_seconds": (
                "charge animation seconds * frame_delay / frames"
            ),
        })

    # Ranged attack projectile. Exported whenever the unit fires a projectile
    # (type_50.projectile_unit_id >= 0 with a positive range). Semantics
    # measured on the arbalester-vs-eliteskirm archive (25 fights, 6312 shots):
    #   - the attack cycle is the MELEE cycle (same reach rule over outline
    #     boxes at range + 0.1 -- max observed fire distance 8.56 = 8 + 0.1 +
    #     both 0.2 outlines -- same stop rule, same windup frame), except the
    #     damage is delivered by a projectile flying at the projectile unit's
    #     dat speed to the target's position at fire time;
    #   - on arrival the shot hits iff the target is alive and still within
    #     its own collision box of the aim point: 5141/6312 shots hit, 1068
    #     find a corpse (dead mid-flight), 23 find the target walked away
    #     (displacement 0.23-1.03 at arrival; hits show p90 displacement 0.0),
    #     and only 80 (1.27%) miss a live stationary target -- the accuracy
    #     roll residue, accepted as a documented deterministic-engine
    #     overshoot;
    #   - min_range is exported for completeness (the skirmisher's 1.0 is
    #     never exercised in a recorded fight; scorpion tapes will measure
    #     its semantics before the engine enforces it).
    # Pass-through bolts (scorpion family): the dat marks the projectile with
    # vanish_mode 1 (continue after impact). Measured on the two authorized
    # scorpion archives (50 fights, 5407 pass hits): the bolt damages EVERY
    # enemy whose collision box crosses its 0.1-half-width line (the
    # projectile unit's own dat collision size), the firer's action target
    # takes full class-rule damage (577/577 full hits are the target, zero
    # exceptions), every other victim -- before or beyond the target -- takes
    # exactly HALF its own post-armor damage (fractional HP like trample),
    # each victim once per bolt, and the bolt expires ~3.0 tiles past its aim
    # point (overshoot p95 plateaus at 2.97-3.00 across target distances).
    ranged = None
    projectile_id = int(unit.type_50.projectile_unit_id)
    if projectile_id >= 0 and float(reference["final_range"]) > 0:
        proj = data.civs[0].units[projectile_id]
        projectile_arc = (
            float(proj.projectile.projectile_arc)
            if proj.projectile is not None else 0.0
        )
        # Vanish mode is overloaded in the DAT.  Flat bolts use it to keep
        # travelling through bodies; arcing grenades/trebuchet stones use it
        # to disappear at their ground impact and must not become line-piercing.
        tech_pass_through_fraction = float(
            reference.get("pass_through_percent") or 0
        )
        pass_through = (
            bool(getattr(proj.projectile, "vanish_mode", 0))
            and projectile_arc <= 0
        ) if proj.projectile is not None else False
        # Some pass-through attacks are granted by a researched civilization
        # technology rather than encoded on the projectile's DAT vanish mode
        # (for example Mapuche Malon). The reference DB is the fully-upgraded
        # source of truth for those effects, so activate the same generic line
        # intersection mechanic whenever it supplies a positive fraction.
        pass_through = pass_through or tech_pass_through_fraction > 0
        # Projectile smart mode (dat attribute 19, a bitfield: 1 = ballistics
        # lead on moving targets, 2 = full damage on unintended targets). The
        # raw projectile record carries the pre-Ballistics value; the
        # Ballistics tech (dat tech 93) SETS attribute 19 to 1 on an explicit
        # list of projectile units. This project's data model is
        # fully-upgraded Imperial, so Ballistics counts as researched whenever
        # the projectile is in that list. NOTE: revisit with civ tech-tree
        # gating before exporting an archer fixture for a civ that lacks
        # Ballistics.
        smart_mode = int(getattr(proj.projectile, "smart_mode", 0)) \
            if proj.projectile is not None else 0
        projectile_hit_mode = int(getattr(proj.projectile, "hit_mode", 0)) \
            if proj.projectile is not None else 0
        secondary_projectile_id = int(
            unit.creatable.secondary_projectile_unit)
        secondary_projectile = (
            data.civs[0].units[secondary_projectile_id]
            if secondary_projectile_id >= 0 else None
        )
        secondary_projectile_hit_mode = int(getattr(
            getattr(secondary_projectile, "projectile", None), "hit_mode",
            projectile_hit_mode,
        ))
        ballistics = data.effects[int(data.techs[93].effect_id)]
        ballistics_ids = {
            int(command.a)
            for command in ballistics.effect_commands
            if command.type == 0 and int(command.c) == 19
        }
        if projectile_id in ballistics_ids:
            smart_mode |= 1
        ranged = {
            "projectile_unit": projectile_id,
            "projectile_speed_tiles_per_second": float(proj.speed),
            "projectile_arc": projectile_arc,
            "min_range_tiles": float(reference["min_range"]),
            "accuracy_percent": float(
                form_stats.accuracy if form_stats
                else reference["final_accuracy"]
            ),
            "base_accuracy_percent": float(
                unit.type_50.accuracy_percent if form_stats
                else reference["base_accuracy"]
            ),
            "pass_through": pass_through,
            "pass_through_damage_fraction": (
                (tech_pass_through_fraction or 0.5)
                if pass_through else 0.0
            ),
            "pass_through_count": (
                int(reference.get("pass_through_count") or 0)
                if pass_through else 0
            ),
            "projectile_half_width_tiles": round(float(proj.collision_size_x), 6),
            "smart_mode": smart_mode,
            "projectile_hit_mode": projectile_hit_mode,
            "secondary_projectile_hit_mode": secondary_projectile_hit_mode,
            # Miss scatter half-radius (dat accuracy_dispersion); only
            # consulted when accuracy_percent < 100.
            "accuracy_dispersion_tiles": float(unit.type_50.accuracy_dispersion),
            # Extra visual projectiles (mangonel line): total - 1 secondaries
            # with EMPTY attack lists — each lands scattered over the
            # spawning area and deals only the floor 1 damage.
            "secondary_projectile_count": (
                max(0, int(unit.creatable.total_projectiles) - 1)
                if int(unit.type_50.blast_attack_level) == 1
                and float(unit.type_50.blast_width) > 0
                else 0
            ),
            "secondary_projectile_unit": int(
                unit.creatable.secondary_projectile_unit),
            "secondary_projectile_half_width_tiles": (
                round(float(data.civs[0].units[
                    int(unit.creatable.secondary_projectile_unit)
                ].collision_size_x), 6)
                if int(unit.creatable.secondary_projectile_unit) >= 0 else 0.0
            ),
            "projectile_spawning_area": [
                float(unit.creatable.projectile_spawning_area[0]),
                float(unit.creatable.projectile_spawning_area[1]),
            ],
            "extra_projectile_count": int(
                extra_projectile_count
                if extra_projectile_count is not None
                else reference.get("extra_projectiles") or 0
            ),
            "extra_projectile_attacks": (
                _parse_classes(reference["extra_projectile_attacks_json"])
                if reference.get("extra_projectile_attacks_json") else None
            ),
            "first_attack_extra_projectiles": int(
                reference.get("first_attack_extra_projectiles") or 0),
            "impact_splash_radius_tiles": float(
                reference.get("splash_on_hit_radius") or 0),
            "impact_splash_damage_fraction": float(
                reference.get("splash_on_hit_fraction") or 1),
            "impact_splash_friendly_fire_fraction": float(
                unit.type_50.friendly_fire_damage),
            **({
                "volley_release_interval_seconds": float(
                    volley_release_interval_seconds),
                "volley_release_size": int(volley_release_size or 1),
                **({"volley_double_release_percent": float(
                    volley_double_release_percent)}
                   if volley_double_release_percent is not None else {}),
                "reload_after_final_projectile": True,
            } if volley_release_interval_seconds is not None else {}),
            **({"weapon_mode": weapon_mode} if weapon_mode else {}),
        }
        fields.update({
            "ranged.projectile_unit": "unit.type_50.projectile_unit_id",
            "ranged.projectile_speed_tiles_per_second": (
                f"dat.civs[0].units[{projectile_id}].speed"
            ),
            "ranged.projectile_arc": (
                f"dat.civs[0].units[{projectile_id}].projectile.projectile_arc"
            ),
            "ranged.min_range_tiles": "ref_units.min_range",
            "ranged.accuracy_percent": (
                "ref_units.final_accuracy (not simulated: 98.7% of tape shots"
                " resolve deterministically; see measurement note)"
            ),
            "ranged.base_accuracy_percent": "ref_units.base_accuracy",
            "ranged.pass_through": (
                f"dat.civs[0].units[{projectile_id}].projectile.vanish_mode"
                " OR positive ref_units.pass_through_percent from researched"
                " civilization technology"
            ),
            "ranged.pass_through_damage_fraction": (
                "ref_units.pass_through_percent; dat pass-through defaults to 0.5"
            ),
            "ranged.pass_through_count": "ref_units.pass_through_count",
            "ranged.projectile_half_width_tiles": (
                f"dat.civs[0].units[{projectile_id}].collision_size_x"
            ),
            "ranged.smart_mode": (
                f"dat.civs[0].units[{projectile_id}].projectile.smart_mode"
                " | 1 when dat tech 93 (Ballistics) sets attribute 19 on"
                f" projectile {projectile_id} (Imperial fully-teched model)"
            ),
            "ranged.projectile_hit_mode": (
                f"dat.civs[0].units[{projectile_id}].projectile.hit_mode"
            ),
            "ranged.secondary_projectile_hit_mode": (
                "dat.civs[0].units[unit.creatable.secondary_projectile_unit]"
                ".projectile.hit_mode"
            ),
            "ranged.accuracy_dispersion_tiles": "unit.type_50.accuracy_dispersion",
            "ranged.secondary_projectile_count": "unit.creatable.total_projectiles - 1",
            "ranged.secondary_projectile_unit": "unit.creatable.secondary_projectile_unit",
            "ranged.secondary_projectile_half_width_tiles": (
                "dat.civs[0].units[unit.creatable.secondary_projectile_unit]"
                ".collision_size_x"
            ),
            "ranged.projectile_spawning_area": "unit.creatable.projectile_spawning_area[0:2]",
            "ranged.extra_projectile_count": "ref_units.extra_projectiles",
            "ranged.extra_projectile_attacks": (
                "ref_units.extra_projectile_attacks_json"
            ),
            "ranged.first_attack_extra_projectiles": (
                "ref_units.first_attack_extra_projectiles"
            ),
            "ranged.impact_splash_radius_tiles": "ref_units.splash_on_hit_radius",
            "ranged.impact_splash_damage_fraction": (
                "ref_units.splash_on_hit_fraction"
            ),
            "ranged.impact_splash_friendly_fire_fraction": (
                "unit.type_50.friendly_fire_damage"
            ),
        })
    elif charge_type == 3:
        # Urumi-style area charge. This is a direct melee strike (the DAT has
        # no projectile unit and range 0), but its charged hit reaches nearby
        # bodies through the unit's level-2 blast circle. The charge payload is
        # added to the ordinary hit before the blast fraction is calculated;
        # non-charged swings do not emit the blast.
        special_graphic = int(unit.creatable.special_graphic)
        charge_animation = (
            _animation_seconds(data, special_graphic, "melee charge")
            if special_graphic >= 0 else attack_animation
        )
        attack_bonus = float(reference.get("charge_attack_melee") or 0)
        recharge_seconds = float(reference.get("charge_recharge_time") or 0)
        blast_radius = float(unit.type_50.blast_width)
        blast_fraction = float(unit.type_50.blast_damage)
        if attack_bonus <= 0 or recharge_seconds <= 0:
            raise ValueError("charge_type 3 needs a positive attack and recharge")
        if (int(unit.type_50.blast_attack_level) != 2
                or blast_radius <= 0
                or not 0 < blast_fraction < 1):
            raise ValueError("charge_type 3 needs a fractional level-2 blast")
        melee_charge = {
            "max_charge": float(unit.creatable.max_charge),
            "recharge_rate": float(unit.creatable.recharge_rate),
            "recharge_seconds": recharge_seconds,
            "charge_type": charge_type,
            "charge_event": int(unit.creatable.charge_event),
            "attack_bonus": attack_bonus,
            # Charge type 3 is an area-reach strike: the charged sword can
            # select any unit whose collision body intersects this radius.
            # The ordinary weapon keeps ref_units.final_range (zero).
            "attack_range_tiles": blast_radius,
            "splash_radius_tiles": blast_radius,
            "splash_damage_fraction": blast_fraction,
            "charge_animation": charge_animation,
            "windup_seconds": attack_delay_seconds,
        }
        fields.update({
            "melee_charge.max_charge": "unit.creatable.max_charge",
            "melee_charge.recharge_rate": "unit.creatable.recharge_rate",
            "melee_charge.recharge_seconds": "ref_units.charge_recharge_time",
            "melee_charge.charge_type": "unit.creatable.charge_type",
            "melee_charge.charge_event": "unit.creatable.charge_event",
            "melee_charge.attack_bonus": "ref_units.charge_attack_melee",
            "melee_charge.attack_range_tiles": (
                "unit.type_50.blast_width (charge-type-3 area reach only)"
            ),
            "melee_charge.splash_radius_tiles": "unit.type_50.blast_width",
            "melee_charge.splash_damage_fraction": "unit.type_50.blast_damage",
            "melee_charge.charge_animation": (
                "graphics[unit.creatable.special_graphic]"
            ),
            "melee_charge.windup_seconds": (
                "ordinary DAT attack-delay release frame"
            ),
        })
        if extra_projectile_count is not None:
            fields["ranged.extra_projectile_count"] = (
                "concrete DAT mode projectile count plus its sourced "
                "civilization technology bonus"
            )
        if volley_release_interval_seconds is not None:
            fields.update({
                "ranged.volley_release_interval_seconds": (
                    volley_release_source
                    or "full-rate live projectile births grouped by source actor; "
                       "mechanics validation only"
                ),
                "ranged.reload_after_final_projectile": (
                    "full-rate same-actor volley start gap equals final release "
                    "+ DAT reload"
                ),
                "ranged.volley_release_size": (
                    volley_release_source
                    or "full-rate projectile births grouped by source actor"
                ),
                **({
                    "ranged.volley_double_release_percent": (
                        volley_release_source
                        or "full-rate projectile births grouped by source actor"
                    )
                } if volley_double_release_percent is not None else {}),
            })
        if weapon_mode:
            fields["ranged.weapon_mode"] = "concrete scenario/DAT weapon form"
        if form_stats:
            fields.update({
                "ranged.accuracy_percent": (
                    "concrete fully-teched form accuracy"
                ),
                "ranged.base_accuracy_percent": (
                    "concrete unit.type_50.accuracy_percent"
                ),
            })

    runtime_effects = _runtime_effects(reference, unit_slug)
    if form_stats:
        runtime_effects = dict(runtime_effects or {})
        runtime_effects["base_accuracy"] = float(unit.type_50.accuracy_percent)
        runtime_effects["extra_projectiles"] = int(
            extra_projectile_count
            if extra_projectile_count is not None
            else reference.get("extra_projectiles") or 0
        )
        raw_trample = (
            int(unit.type_50.blast_attack_level) == 2
            and float(unit.type_50.blast_width) > 0
            and 0 < float(unit.type_50.blast_damage) < 1
        )
        if not raw_trample:
            runtime_effects.pop("trample_percent", None)
            runtime_effects.pop("trample_radius", None)
            runtime_effects.pop("trample_flat_damage", None)
        if not ranged or not ranged["pass_through"]:
            runtime_effects.pop("pass_through_percent", None)
            runtime_effects.pop("pass_through_count", None)
        if not runtime_effects:
            runtime_effects = None

    # Melee blast ("trample"). Raw dat values, exported for every unit; the
    # engine gates on attack_level == 2 and 0 < damage_fraction < 1 (the
    # Champion's blast_damage is a -5.0 "no trample" sentinel with width 0).
    # Semantics measured from the authorized elephant tapes (54 fights, 1694
    # bystander samples, 0 misclassifications): the blast is a circle of radius
    # width_tiles centred on the ATTACKER, it reaches every ENEMY unit whose
    # collision box intersects the circle (allies are never hit despite the
    # level-2/friendly-fire dat flags), the main target is excluded, and each
    # victim takes damage_fraction x the post-armor damage against THAT victim.
    blast = {
        "width_tiles": float(unit.type_50.blast_width),
        "damage_fraction": float(unit.type_50.blast_damage),
        "attack_level": int(unit.type_50.blast_attack_level),
        "defense_level": int(unit.blast_defense_level),
        "friendly_fire_damage": float(unit.type_50.friendly_fire_damage),
    }

    return {
        "unit_master": unit.id,
        "civilization": reference["civ_name"],
        "age": reference["age"],
        "blast": blast,
        "charge": charge,
        "melee_charge": melee_charge,
        "ranged": ranged,
        "effects": runtime_effects,
        "hp": int(form_stats.hp if form_stats else reference["final_hp"]),
        "speed_tiles_per_second": float(
            form_stats.speed if form_stats else reference["exact_speed"]),
        "attack_range_tiles": float(
            form_stats.range if form_stats else reference["final_range"]),
        "reload_seconds": reload_seconds,
        "attack_delay_seconds": attack_delay_seconds,
        "attack_animation": attack_animation,
        "idle_animation": idle_animation,
        "walk_animation": walk_animation,
        "death_animation": death_animation,
        "line_of_sight_tiles": float(
            form_stats.los if form_stats else reference["final_los"]),
        "attack_classes": attack_classes,
        "armor_classes": armor_classes,
        "population_space": float(reference["pop_space"]),
        "damage_reduction_by_attacker_category": damage_reduction,
        "collision_size_tiles": {
            "x": round(float(unit.collision_size_x), 6),
            "y": round(float(unit.collision_size_y), 6),
            "z": round(float(unit.collision_size_z), 6),
        },
        "clearance_size_tiles": {
            "x": round(float(unit.clearance_size[0]), 6),
            "y": round(float(unit.clearance_size[1]), 6),
        },
        "outline_size_tiles": {
            "x": round(float(unit.outline_size_x), 6),
            "y": round(float(unit.outline_size_y), 6),
            "z": round(float(unit.outline_size_z), 6),
        },
        "obstruction": {
            "type": int(unit.obstruction_type),
            "class": int(unit.obstruction_class),
        },
        "movement_blocks": {
            "terrain_restriction": int(unit.terrain_restriction),
            "fly_mode": int(unit.fly_mode),
            "hill_mode": int(unit.hill_mode),
        },
        "min_collision_size_multiplier": float(
            unit.dead_fish.min_collision_size_multiplier),
        "attack_graphic": int(unit.type_50.attack_graphic),
        "frame_delay": int(unit.type_50.frame_delay),
        "derived": {"damage_vs_self": _damage_against_self(attack_classes, armor_classes)},
        "provenance": {
            "reference_db_sha256": _sha256(reference_db),
            "dat_sha256": _sha256(dat_path),
            "reference_selector": (
                f"ref_units WHERE unit_slug='{unit_slug}' AND civ_name='{civ}' "
                "AND age='Imperial'"
            ),
            "dat_selector": (
                f"dat.civs[name='{REFERENCE_TO_DAT_CIV.get(civ, civ)}'].units[{master}]"
            ),
            "reload_base_seconds": float(
                form_stats.reload_time if form_stats
                else reference["final_reload_time"]),
            "reload_multiplier": reload_multiplier,
            "fields": fields,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-db", type=Path, required=True)
    parser.add_argument("--dat", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--unit-slug", default="champion")
    parser.add_argument("--civ", default="Chinese")
    parser.add_argument("--master", type=int, default=567)
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    try:
        fixture = export_unit_mechanics(
            args.reference_db, args.dat, args.unit_slug, args.civ, args.master
        )
    except Exception as exc:
        parser.error(f"failed to parse Genie .dat or read reference DB: {exc}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
