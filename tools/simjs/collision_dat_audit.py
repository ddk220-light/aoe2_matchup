"""Extract collision-related fields for the standard calibration units.

This is a read-only audit of the currently installed AoE2:DE Genie ``.dat``.
Unit IDs are resolved from ``aoe2x.dbgen.config_units.IMPERIAL_UNITS`` so the
audit fails visibly when project configuration changes instead of silently
reading a stale hard-coded row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


STANDARD_SLUGS = (
    "champion",
    "halberdier",
    "elite_fire_lancer",
    "hussar",
    "paladin",
    "heavy_camel",
    "elite_elephant",
    "elite_steppe",
    "arbalester",
    "imp_elite_skirm",
    "heavy_cav_archer",
    "siege_onager",
    "heavy_scorpion",
    "hand_cannoneer",
)

# These slugs have no generic final upgrade chain. Resolve the exact standard
# unit represented by the slug through a civ-specific chain in project config.
FINAL_ROSTER_CIV_OVERRIDE = {
    "heavy_camel": "Persians",
    "elite_elephant": "Burmese",
}


def _number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 9) if math.isfinite(value) else None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return round(converted, 9) if math.isfinite(converted) else None


def _pair(value: Any) -> list[float | int | None] | None:
    if value is None:
        return None
    try:
        values = list(value)
    except TypeError:
        return None
    return [_number(item) for item in values[:2]]


def resolve_standard_unit_ids() -> dict[str, int]:
    from aoe2x.dbgen.config_units import IMPERIAL_UNITS

    resolved: dict[str, int] = {}
    for slug in STANDARD_SLUGS:
        spec = IMPERIAL_UNITS[slug]
        preferred_civ = FINAL_ROSTER_CIV_OVERRIDE.get(slug)
        if preferred_civ:
            chain = spec["civ_upgrades"][preferred_civ]
            resolved[slug] = int(chain[-1][1])
        elif spec.get("upgrades"):
            resolved[slug] = int(spec["upgrades"][-1][1])
        else:
            resolved[slug] = int(spec["base_id"])
    return resolved


def extract_unit_fields(unit_id: int, unit: Any) -> dict[str, Any]:
    dead_fish = getattr(unit, "dead_fish", None)
    collision_x = _number(getattr(unit, "collision_size_x", None))
    multiplier = _number(getattr(dead_fish, "min_collision_size_multiplier", None))
    nominal_diameter = 2 * collision_x if isinstance(collision_x, (int, float)) else None
    multiplied_diameter = (
        nominal_diameter * multiplier
        if isinstance(nominal_diameter, (int, float)) and isinstance(multiplier, (int, float))
        else None
    )
    return {
        "unit_id": int(unit_id),
        "internal_name": getattr(unit, "name", None),
        "unit_class": _number(getattr(unit, "unit_class", getattr(unit, "class_", None))),
        "speed_tiles_per_second": _number(getattr(unit, "speed", None)),
        "collision_size_tiles": {
            "x": collision_x,
            "y": _number(getattr(unit, "collision_size_y", None)),
            "z": _number(getattr(unit, "collision_size_z", None)),
        },
        "clearance_size_tiles": _pair(getattr(unit, "clearance_size", None)),
        "outline_size_tiles": {
            "x": _number(getattr(unit, "outline_size_x", None)),
            "y": _number(getattr(unit, "outline_size_y", None)),
            "z": _number(getattr(unit, "outline_size_z", None)),
        },
        "obstruction": {
            "type": _number(getattr(unit, "obstruction_type", None)),
            "class": _number(getattr(unit, "obstruction_class", None)),
        },
        "min_collision_size_multiplier": multiplier,
        "movement_block": {
            "old_size_class": _number(getattr(dead_fish, "old_size_class", None)),
            "old_move_algorithm": _number(getattr(dead_fish, "old_move_algorithm", None)),
            "tracking_unit": _number(getattr(dead_fish, "tracking_unit", None)),
            "tracking_unit_mode": _number(getattr(dead_fish, "tracking_unit_mode", None)),
            "tracking_unit_density": _number(getattr(dead_fish, "tracking_unit_density", None)),
            "turn_radius": _number(getattr(dead_fish, "turn_radius", None)),
        },
        "nominal_collision_diameter_tiles": _number(nominal_diameter),
        "multiplied_collision_diameter_tiles": _number(multiplied_diameter),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def build_report(dat_path: Path, extracted_at: str | None = None) -> dict[str, Any]:
    from genieutils.datfile import DatFile

    dat_path = Path(dat_path).resolve()
    if not dat_path.is_file():
        raise FileNotFoundError(dat_path)

    data = DatFile.parse(dat_path)
    civ = max(data.civs, key=lambda candidate: sum(unit is not None for unit in candidate.units))
    unit_ids = resolve_standard_unit_ids()
    units: dict[str, dict[str, Any]] = {}
    for slug, unit_id in unit_ids.items():
        if unit_id >= len(civ.units) or civ.units[unit_id] is None:
            raise RuntimeError(f"{slug}: unit id {unit_id} is absent from the selected .dat civ")
        record = extract_unit_fields(unit_id, civ.units[unit_id])
        radius = record["collision_size_tiles"]["x"]
        if not isinstance(radius, (int, float)) or radius <= 0:
            raise RuntimeError(f"{slug}: invalid collision radius {radius!r}")
        units[slug] = record

    stat = dat_path.stat()
    try:
        parser_version = version("genieutils-py")
    except PackageNotFoundError:
        parser_version = "unknown"
    return {
        "schema": 1,
        "extracted_at_utc": extracted_at or datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": str(dat_path),
            "size_bytes": stat.st_size,
            "modified_at_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "sha256": _sha256(dat_path),
            "genieutils_py_version": parser_version,
            "selected_civ_index": data.civs.index(civ),
            "selected_civ_name": getattr(civ, "name", None),
        },
        "computed_field_note": (
            "multiplied_collision_diameter_tiles is arithmetic only: "
            "2 * collision_size_x * min_collision_size_multiplier. "
            "The audit does not assume when the engine applies the multiplier."
        ),
        "units": units,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dat", required=True, type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--extracted-at", help="Override timestamp for deterministic regeneration")
    args = parser.parse_args()

    report = build_report(args.dat, args.extracted_at)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
