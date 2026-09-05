"""Reference lookup and validated V3 mechanics repository."""
import json
from aoe2x.dbgen.v3_mechanics import MECHANICS_SCHEMA_VERSION, validate_runtime_profile, mechanics_hash as calculate_mechanics_hash

def _find_ref_unit(rc, civ_name, unit_slug, age):
    rc.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ_name, unit_slug, age),
    )
    row = rc.fetchone()
    if row is None:
        rc.execute(
            "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=?",
            (civ_name, unit_slug),
        )
        row = rc.fetchone()
    return row


def _load_v3_mechanics(rc, ref_unit_id, requested_mode=None):
    modes = rc.execute(
        """
        SELECT mode, is_default, schema_version, mechanics_json,
               mechanics_hash, source_build
        FROM ref_unit_mechanics
        WHERE ref_unit_id=?
        ORDER BY is_default DESC, mode
        """,
        (ref_unit_id,),
    ).fetchall()
    if not modes:
        raise LookupError(f"V3 mechanics missing for ref_unit_id={ref_unit_id}")
    selected = next(
        (
            row for row in modes
            if row["mode"] == requested_mode
        ),
        None,
    ) if requested_mode else next((row for row in modes if row["is_default"]), None)
    if selected is None:
        available = ", ".join(row["mode"] for row in modes)
        raise ValueError(f"unknown mechanics mode {requested_mode!r}; available: {available}")
    if selected["schema_version"] != MECHANICS_SCHEMA_VERSION:
        raise RuntimeError(
            f"mechanics schema {selected['schema_version']} is incompatible with "
            f"server schema {MECHANICS_SCHEMA_VERSION}"
        )
    try:
        mechanics = json.loads(selected["mechanics_json"])
        validate_runtime_profile(mechanics)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"invalid mechanics payload for ref_unit_id={ref_unit_id}"
        ) from exc
    actual_hash = calculate_mechanics_hash(mechanics)
    if actual_hash != selected["mechanics_hash"]:
        raise RuntimeError(f"mechanics hash mismatch for ref_unit_id={ref_unit_id}")
    return {
        "mechanics": mechanics,
        "mechanics_hash": actual_hash,
        "mechanics_schema_version": selected["schema_version"],
        "mechanics_source_build": selected["source_build"],
        "mechanics_mode": selected["mode"],
        "mechanics_modes": [row["mode"] for row in modes],
    }


def _load_v3_auxiliary_mechanics(rc, actor_slug, mode="default"):
    row = rc.execute(
        """
        SELECT schema_version, mechanics_json, mechanics_hash, source_build
        FROM ref_auxiliary_mechanics
        WHERE actor_slug=? AND mode=?
        """,
        (actor_slug, mode),
    ).fetchone()
    if row is None:
        raise LookupError(f"V3 auxiliary mechanics missing for {actor_slug}:{mode}")
    if row["schema_version"] != MECHANICS_SCHEMA_VERSION:
        raise RuntimeError(
            f"auxiliary mechanics schema {row['schema_version']} is incompatible"
        )
    try:
        mechanics = json.loads(row["mechanics_json"])
        validate_runtime_profile(mechanics)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"invalid auxiliary mechanics payload for {actor_slug}:{mode}"
        ) from exc
    actual_hash = calculate_mechanics_hash(mechanics)
    if actual_hash != row["mechanics_hash"]:
        raise RuntimeError(f"auxiliary mechanics hash mismatch for {actor_slug}:{mode}")
    return {
        "mechanics": mechanics,
        "mechanics_hash": actual_hash,
        "mechanics_source_build": row["source_build"],
    }
