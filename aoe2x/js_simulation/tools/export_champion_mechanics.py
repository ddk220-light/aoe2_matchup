"""Export source-backed Chinese Imperial Champion mechanics for the JS simulator."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any


CHAMPION_MASTER = 567
CHINESE_CIV = "Chinese"
IMPERIAL_AGE = "Imperial"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_reference_row(reference_db: Path) -> dict[str, Any]:
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
                final_los,
                final_attacks_json,
                final_armors_json
            FROM ref_units
            WHERE unit_slug = ? AND civ_name = ? AND age = ?
            """,
            ("champion", CHINESE_CIV, IMPERIAL_AGE),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError(
                "reference DB must contain exactly one Chinese Imperial champion row; "
                f"found {len(rows)}"
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
        raise ValueError("reference DB has no stat chain for the Chinese Champion")
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
    """Apply the AoE class rule to the unit's own attack and armor maps."""
    for label, classes in (
        ("attack", attack_classes),
        ("armor", armor_classes),
    ):
        if "4" not in classes:
            raise ValueError(f"missing required {label} class 4")
        value = classes["4"]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"{label} class 4 must be numeric")
    if attack_classes["4"] <= 0:
        raise ValueError("attack class 4 must be positive")
    damage = max(0, attack_classes["4"] - armor_classes["4"])
    for class_id, attack in attack_classes.items():
        if class_id in {"3", "4"} or attack <= 0 or class_id not in armor_classes:
            continue
        damage += max(0, attack - armor_classes[class_id])
    return max(1, damage)


def _raw_chinese_champion(dat_path: Path):
    from genieutils.datfile import DatFile

    data = DatFile.parse(dat_path)
    chinese = [civilization for civilization in data.civs if civilization.name == CHINESE_CIV]
    if len(chinese) != 1:
        raise ValueError(
            "Genie .dat must contain exactly one Chinese civilization; "
            f"found {len(chinese)}"
        )
    unit = chinese[0].units[CHAMPION_MASTER]
    if unit is None or unit.id != CHAMPION_MASTER:
        raise ValueError("Genie .dat does not contain Chinese Champion master 567")
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


def export_champion_mechanics(reference_db: Path, dat_path: Path) -> dict:
    """Return the clean-room Chinese Imperial Champion mechanics fixture."""
    reference_db = Path(reference_db)
    dat_path = Path(dat_path)
    reference = _read_reference_row(reference_db)
    data, unit = _raw_chinese_champion(dat_path)
    attack_classes = _parse_classes(reference["final_attacks_json"])
    armor_classes = _parse_classes(reference["final_armors_json"])

    attack_animation = _animation_seconds(
        data, int(unit.type_50.attack_graphic), "attack")
    idle_animation = _animation_seconds(
        data, int(unit.standing_graphic[0]), "idle")
    walk_animation = _animation_seconds(
        data, int(unit.dead_fish.walking_graphic), "walk")

    # Genie melee hit timing. Documented rule (AoE2 wiki "Attack delay", sourced to
    # Icewind's frame-delay research, and philistine's frame-by-frame study):
    #   ranged: attack_delay = animation_duration * frame_delay / frames_per_angle
    #   melee : attack_delay = animation_duration / 2
    # A melee unit's frame_delay of 0 means "no projectile frame", NOT "instant
    # damage" -- the hit lands at the halfway point of the attack animation.
    # ref_units.final_attack_delay carries the raw 0 and must not be used directly.
    frame_delay = int(unit.type_50.frame_delay)
    is_melee = float(reference["final_range"]) <= 0 and frame_delay == 0
    if is_melee:
        attack_delay_seconds = attack_animation["seconds"] / 2
        attack_delay_source = (
            "melee rule: attack animation seconds / 2"
            " (Genie frame_delay=0 means no projectile frame)"
        )
    else:
        frames_per_angle = attack_animation["frames"]
        attack_delay_seconds = (
            attack_animation["seconds"] * frame_delay / frames_per_angle
        )
        attack_delay_source = (
            "ranged rule: attack animation seconds * frame_delay / frames"
        )

    fields = {
        "unit_master": "unit.id",
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
        "attack_graphic": "unit.type_50.attack_graphic",
        "frame_delay": "unit.type_50.frame_delay",
        "derived.damage_vs_self": (
            "AoE class rule(ref_units.final_attacks_json,"
            " ref_units.final_armors_json)"
        ),
    }

    return {
        "unit_master": unit.id,
        "civilization": reference["civ_name"],
        "age": reference["age"],
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
        "attack_graphic": int(unit.type_50.attack_graphic),
        "frame_delay": int(unit.type_50.frame_delay),
        "derived": {"damage_vs_self": _damage_against_self(attack_classes, armor_classes)},
        "provenance": {
            "reference_db_sha256": _sha256(reference_db),
            "dat_sha256": _sha256(dat_path),
            "reference_selector": (
                "ref_units WHERE unit_slug='champion' AND civ_name='Chinese' "
                "AND age='Imperial'"
            ),
            "dat_selector": "dat.civs[name='Chinese'].units[567]",
            "fields": fields,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-db", type=Path, required=True)
    parser.add_argument("--dat", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    try:
        fixture = export_champion_mechanics(args.reference_db, args.dat)
    except Exception as exc:
        parser.error(f"failed to parse Genie .dat or read reference DB: {exc}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
