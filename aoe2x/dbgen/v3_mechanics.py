"""Versioned runtime contract for production V3 unit mechanics."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

from .v3_runtime_config import BEHAVIOR_CLASS_BY_CIV_SLUG


MECHANICS_SCHEMA_VERSION = 1
BEHAVIOR_CLASSES = frozenset({"melee", "mobile_ranged", "siege_ranged"})
_NON_RUNTIME_KEYS = frozenset({"provenance", "mode_validation"})


class MechanicsValidationError(ValueError):
    """Raised when a generated V3 mechanics payload is not runtime-safe."""


def _runtime_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _runtime_copy(child)
            for key, child in value.items()
            if key not in _NON_RUNTIME_KEYS
        }
    if isinstance(value, list):
        return [_runtime_copy(child) for child in value]
    return value


def canonical_json(value: Mapping[str, Any]) -> str:
    """Canonical JSON used for SQLite storage, ETags and replay identity."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def mechanics_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def behavior_class_for(
    civilization: str,
    unit_slug: str,
    unit_class: int | None,
    is_ranged: bool,
) -> str:
    override = BEHAVIOR_CLASS_BY_CIV_SLUG.get((civilization, unit_slug))
    if override:
        return override
    if not is_ranged:
        return "melee"
    return "siege_ranged" if unit_class == 13 else "mobile_ranged"


def build_runtime_profile(
    exported: Mapping[str, Any],
    row: Mapping[str, Any],
    *,
    mode: str,
) -> dict[str, Any]:
    """Decorate exporter output with web identity and remove audit-only data."""
    profile = _runtime_copy(dict(exported))
    profile.update(
        {
            "mechanics_schema_version": MECHANICS_SCHEMA_VERSION,
            "unit_slug": row["unit_slug"],
            "unit_name": row["unit_name"],
            "mode": mode,
            "behavior_class": behavior_class_for(
                row["civ_name"],
                row["unit_slug"],
                row["unit_class"],
                bool(row["is_ranged"]),
            ),
            **(
                {"behavior_family": "onager"}
                if row["unit_slug"] == "siege_onager"
                else {}
            ),
            "cost": {
                "food": float(row["final_cost_food"] or 0),
                "wood": float(row["final_cost_wood"] or 0),
                "gold": float(row["final_cost_gold"] or 0),
            },
        }
    )
    validate_runtime_profile(profile)
    return profile


def _finite_number(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MechanicsValidationError(f"{label} must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise MechanicsValidationError(f"{label} must be finite")
    if minimum is not None and value < minimum:
        raise MechanicsValidationError(f"{label} must be >= {minimum}")
    return value


def _class_map(value: Any, label: str) -> None:
    if not isinstance(value, dict) or not value:
        raise MechanicsValidationError(f"{label} must be a nonempty object")
    for key, amount in value.items():
        try:
            int(key)
        except (TypeError, ValueError) as exc:
            raise MechanicsValidationError(f"{label} key {key!r} is not an armor class") from exc
        _finite_number(amount, f"{label}.{key}")


def validate_runtime_profile(profile: Mapping[str, Any]) -> None:
    """Validate the common invariants required by the V3 combat engine."""
    if profile.get("mechanics_schema_version") != MECHANICS_SCHEMA_VERSION:
        raise MechanicsValidationError("unsupported mechanics_schema_version")
    for key in ("unit_slug", "unit_name", "civilization", "age", "mode"):
        if not isinstance(profile.get(key), str) or not profile[key]:
            raise MechanicsValidationError(f"{key} must be a nonempty string")
    if profile.get("behavior_class") not in BEHAVIOR_CLASSES:
        raise MechanicsValidationError("behavior_class is invalid")
    if not isinstance(profile.get("unit_master"), int) or profile["unit_master"] < 0:
        raise MechanicsValidationError("unit_master must be a nonnegative integer")

    for key, minimum in (
        ("hp", 1),
        ("speed_tiles_per_second", 0),
        ("attack_range_tiles", 0),
        ("reload_seconds", 0),
        ("attack_delay_seconds", 0),
        ("line_of_sight_tiles", 0),
        ("population_space", 0),
    ):
        _finite_number(profile.get(key), key, minimum=minimum)

    _class_map(profile.get("attack_classes"), "attack_classes")
    _class_map(profile.get("armor_classes"), "armor_classes")

    cost = profile.get("cost")
    if not isinstance(cost, dict):
        raise MechanicsValidationError("cost must be an object")
    for resource in ("food", "wood", "gold"):
        _finite_number(cost.get(resource), f"cost.{resource}", minimum=0)

    animation = profile.get("attack_animation")
    if not isinstance(animation, dict):
        raise MechanicsValidationError("attack_animation must be an object")
    _finite_number(animation.get("seconds"), "attack_animation.seconds", minimum=0)
    if animation["seconds"] <= 0:
        raise MechanicsValidationError("attack_animation.seconds must be positive")
    if profile["attack_delay_seconds"] > animation["seconds"]:
        raise MechanicsValidationError("attack delay exceeds attack animation")

    for group in ("collision_size_tiles", "outline_size_tiles"):
        value = profile.get(group)
        if not isinstance(value, dict):
            raise MechanicsValidationError(f"{group} must be an object")
        _finite_number(value.get("x"), f"{group}.x", minimum=0)
        _finite_number(value.get("y"), f"{group}.y", minimum=0)

    ranged = profile.get("ranged")
    if ranged is not None:
        if not isinstance(ranged, dict):
            raise MechanicsValidationError("ranged must be null or an object")
        for key in (
            "projectile_speed_tiles_per_second",
            "min_range_tiles",
            "accuracy_percent",
            "projectile_half_width_tiles",
        ):
            _finite_number(ranged.get(key), f"ranged.{key}", minimum=0)
        if ranged["accuracy_percent"] > 100:
            raise MechanicsValidationError("ranged accuracy exceeds 100 percent")
        if ranged["min_range_tiles"] > profile["attack_range_tiles"]:
            raise MechanicsValidationError("minimum range exceeds attack range")

    for forbidden in _NON_RUNTIME_KEYS:
        if forbidden in profile:
            raise MechanicsValidationError(f"runtime profile contains {forbidden}")

    # Recursively reject local capture paths and outcome-fitting fields.
    encoded = canonical_json(profile).lower()
    forbidden_fragments = (
        "frames.bin",
        "live_frames_bin",
        "winner_override",
        "expected_winner",
        "survivor_hp",
        "hp_correction",
    )
    found = [fragment for fragment in forbidden_fragments if fragment in encoded]
    if found:
        raise MechanicsValidationError(f"runtime profile contains forbidden evidence: {found}")
