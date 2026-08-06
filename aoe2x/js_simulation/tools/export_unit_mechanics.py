"""Export source-backed Imperial unit mechanics for the JS simulator.

    python export_unit_mechanics.py --unit-slug champion --civ Chinese \
        --master 567 --reference-db ... --dat ... --output ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any


IMPERIAL_AGE = "Imperial"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_reference_row(reference_db: Path, unit_slug: str, civ: str) -> dict[str, Any]:
    reference_db = reference_db.resolve()
    uri = f"{reference_db.as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                id,
                civ_name,
                age,
                final_hp,
                final_speed,
                final_range,
                final_reload_time,
                final_attack_delay,
                final_accuracy,
                final_los,
                final_attacks_json,
                final_armors_json
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
    if chain is None:
        raise ValueError(f"reference DB has no stat chain for the {civ} {unit_slug}")
    row["exact_speed"] = float(chain["speed"])
    if abs(row["exact_speed"] - float(row["final_speed"])) > 0.05:
        raise ValueError(
            "stat-chain speed disagrees with ref_units.final_speed beyond rounding: "
            f"{row['exact_speed']} vs {row['final_speed']}"
        )
    return row


def _parse_classes(raw: str) -> dict[str, int | float]:
    return {
        str(class_id): amount
        for class_id, amount in sorted(
            json.loads(raw).items(), key=lambda item: int(item[0])
        )
    }


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


def _raw_unit(dat_path: Path, civ: str, master: int):
    from genieutils.datfile import DatFile

    data = DatFile.parse(dat_path)
    matches = [civilization for civilization in data.civs if civilization.name == civ]
    if len(matches) != 1:
        raise ValueError(
            f"Genie .dat must contain exactly one {civ} civilization; "
            f"found {len(matches)}"
        )
    unit = matches[0].units[master]
    if unit is None or unit.id != master:
        raise ValueError(f"Genie .dat does not contain {civ} master {master}")
    return data, unit


def _animation_seconds(data, graphic_id: int, label: str) -> dict[str, Any]:
    """Duration of a Genie animation = frame_count x frame_duration."""
    if graphic_id is None or graphic_id < 0:
        raise ValueError(f"{label} graphic is absent")
    graphic = data.graphics[graphic_id]
    frames = int(graphic.frame_count)
    duration = float(graphic.frame_duration)
    if frames <= 0 or not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"{label} graphic {graphic_id} has no usable frame timing")
    return {
        "graphic": graphic_id,
        "frames": frames,
        "frame_duration_seconds": duration,
        "seconds": frames * duration,
    }


def export_unit_mechanics(
    reference_db: Path, dat_path: Path, unit_slug: str, civ: str, master: int
) -> dict:
    """Return the clean-room Imperial mechanics fixture for one unit x civ."""
    reference_db = Path(reference_db)
    dat_path = Path(dat_path)
    reference = _read_reference_row(reference_db, unit_slug, civ)
    data, unit = _raw_unit(dat_path, civ, master)
    attack_classes = _parse_classes(reference["final_attacks_json"])
    armor_classes = _parse_classes(reference["final_armors_json"])

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

    # Genie hit timing. The hit lands on animation frame `frame_delay`, so
    #   attack_delay = animation_seconds * frame_delay / frame_count
    # `frame_delay == 0` is an UNSET sentinel, not "instant damage": the engine
    # then falls back to the animation midpoint. The split is on frame_delay,
    # NOT on melee-vs-ranged -- the Paladin is melee with frame_delay 13.
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
    if frame_delay == 0:
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
        "reload_seconds": "ref_units.final_reload_time",
        "attack_delay_seconds": attack_delay_source,
        "attack_animation.graphic": "unit.type_50.attack_graphic",
        "attack_animation.frames": "graphics[attack_graphic].frame_count",
        "attack_animation.frame_duration_seconds": (
            "graphics[attack_graphic].frame_duration"
        ),
        "attack_animation.seconds": "frames * frame_duration",
        "idle_animation": "graphics[unit.standing_graphic[0]]",
        "walk_animation": "graphics[unit.dead_fish.walking_graphic]",
        "line_of_sight_tiles": "ref_units.final_los",
        "attack_classes": "ref_units.final_attacks_json",
        "armor_classes": "ref_units.final_armors_json",
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
    charge_type = int(getattr(unit.creatable, "charge_type", 0) or 0)
    if charge_type:
        proj_id = int(unit.creatable.charge_projectile_unit)
        proj = data.civs[0].units[proj_id] if proj_id >= 0 else None
        if proj is None:
            raise ValueError(f"charge_type {charge_type} without projectile unit")
        special_graphic = int(unit.creatable.special_graphic)
        charge_animation = _animation_seconds(data, special_graphic, "charge")
        if frame_delay <= 0:
            raise ValueError("charge windup needs a nonzero frame_delay")
        proj_attacks = {
            str(a.class_): a.amount
            for a in proj.type_50.attacks
            if a.amount > 0
        }
        charge = {
            "max_charge": float(unit.creatable.max_charge),
            "recharge_rate": float(unit.creatable.recharge_rate),
            "charge_type": charge_type,
            "charge_event": int(unit.creatable.charge_event),
            "projectile_unit": proj_id,
            "projectile_count": int(unit.creatable.max_total_projectiles),
            "projectile_speed_tiles_per_second": float(proj.speed),
            "projectile_attacks": proj_attacks,
            "charge_animation": charge_animation,
            "windup_seconds": (
                charge_animation["seconds"] * frame_delay
                / charge_animation["frames"]
            ),
        }
        fields.update({
            "charge.max_charge": "unit.creatable.max_charge",
            "charge.recharge_rate": "unit.creatable.recharge_rate",
            "charge.charge_type": "unit.creatable.charge_type",
            "charge.charge_event": "unit.creatable.charge_event",
            "charge.projectile_unit": "unit.creatable.charge_projectile_unit",
            "charge.projectile_count": "unit.creatable.max_total_projectiles",
            "charge.projectile_speed_tiles_per_second": (
                f"dat.civs[0].units[{proj_id}].speed"
            ),
            "charge.projectile_attacks": (
                f"positive dat.civs[0].units[{proj_id}].type_50.attacks; the"
                " engine applies class matching with armor values IGNORED"
                " (all four victim types measure exactly the class-3 amount)"
            ),
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
        pass_through = bool(getattr(proj.projectile, "vanish_mode", 0)) \
            if proj.projectile is not None else False
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
            "min_range_tiles": float(unit.type_50.min_range),
            "accuracy_percent": float(reference["final_accuracy"]),
            "pass_through": pass_through,
            "projectile_half_width_tiles": round(float(proj.collision_size_x), 6),
            "smart_mode": smart_mode,
            # Miss scatter half-radius (dat accuracy_dispersion); only
            # consulted when accuracy_percent < 100.
            "accuracy_dispersion_tiles": float(unit.type_50.accuracy_dispersion),
            # Extra visual projectiles (mangonel line): total - 1 secondaries
            # with EMPTY attack lists — each lands scattered over the
            # spawning area and deals only the floor 1 damage.
            "secondary_projectile_count": max(
                0, int(unit.creatable.total_projectiles) - 1),
            "projectile_spawning_area": [
                float(unit.creatable.projectile_spawning_area[0]),
                float(unit.creatable.projectile_spawning_area[1]),
            ],
        }
        fields.update({
            "ranged.projectile_unit": "unit.type_50.projectile_unit_id",
            "ranged.projectile_speed_tiles_per_second": (
                f"dat.civs[0].units[{projectile_id}].speed"
            ),
            "ranged.min_range_tiles": "unit.type_50.min_range",
            "ranged.accuracy_percent": (
                "ref_units.final_accuracy (not simulated: 98.7% of tape shots"
                " resolve deterministically; see measurement note)"
            ),
            "ranged.pass_through": (
                f"dat.civs[0].units[{projectile_id}].projectile.vanish_mode"
            ),
            "ranged.projectile_half_width_tiles": (
                f"dat.civs[0].units[{projectile_id}].collision_size_x"
            ),
            "ranged.smart_mode": (
                f"dat.civs[0].units[{projectile_id}].projectile.smart_mode"
                " | 1 when dat tech 93 (Ballistics) sets attribute 19 on"
                f" projectile {projectile_id} (Imperial fully-teched model)"
            ),
            "ranged.accuracy_dispersion_tiles": "unit.type_50.accuracy_dispersion",
            "ranged.secondary_projectile_count": "unit.creatable.total_projectiles - 1",
            "ranged.projectile_spawning_area": "unit.creatable.projectile_spawning_area[0:2]",
        })

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
        "ranged": ranged,
        "hp": int(reference["final_hp"]),
        "speed_tiles_per_second": float(reference["exact_speed"]),
        "attack_range_tiles": float(reference["final_range"]),
        "reload_seconds": float(reference["final_reload_time"]),
        "attack_delay_seconds": attack_delay_seconds,
        "attack_animation": attack_animation,
        "idle_animation": idle_animation,
        "walk_animation": walk_animation,
        "line_of_sight_tiles": float(reference["final_los"]),
        "attack_classes": attack_classes,
        "armor_classes": armor_classes,
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
            "dat_selector": f"dat.civs[name='{civ}'].units[{master}]",
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
