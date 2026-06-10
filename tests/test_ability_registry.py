"""Validation glue for analysis/ability_registry.py (Phase A, data-model-review §3.2/§3.5).

Five assertion layers, all against COMMITTED artifacts (no regeneration):

  (a) orphan keys      — config_combat.py keys vs the ref-DB roster
  (b) registry<->config — property-name parity with config_combat.py values
  (c) registry<->schema — declared columns exist in webapp/aoe2_reference.db
                          and combat-dict keys appear in combat_unit_loader.py
  (d) registry<->engines — PRESENCE-ONLY check: each param's identifier appears
                          in the source of every engine the registry claims
                          implements it (snake_case for Python; snake OR
                          camelCase for simulate.js). This proves the engines
                          mention the property, NOT that the semantics match —
                          semantic parity lives in tests/test_position_sim_abilities.py
                          and tests/test_frontend_projectile_miss.js.
  (e) defaults         — registry defaults match simulation.prepare_combat_unit
                          where both define one.

Phase A is declare+validate only; storage/loader generation is Phase B.
"""

import json
import re
import sqlite3
from pathlib import Path

import pytest

from analysis.ability_registry import (
    ABILITIES,
    ALL_ENGINES,
    FAMILIES,
    iter_params,
    param_names,
)
from analysis.config_combat import (
    CIV_COMBAT_PROPERTIES,
    COMBAT_PROPERTIES,
    UNIQUE_COMBAT_PROPERTIES,
)

ROOT = Path(__file__).resolve().parents[1]
REF_DB = ROOT / "webapp" / "aoe2_reference.db"
LOADER_SRC = (ROOT / "webapp" / "combat_unit_loader.py").read_text(encoding="utf-8")
ENGINE_SOURCES = {
    "abstract": (ROOT / "webapp" / "simulation.py").read_text(encoding="utf-8"),
    "position": (ROOT / "webapp" / "simulation_real.py").read_text(encoding="utf-8"),
    "js": (ROOT / "webapp" / "static" / "js" / "simulate.js").read_text(encoding="utf-8"),
}


@pytest.fixture(scope="module")
def roster():
    """All (civ_name, unit_slug) pairs in the committed reference DB."""
    conn = sqlite3.connect(f"file:{REF_DB.as_posix()}?mode=ro", uri=True)
    try:
        pairs = set(
            conn.execute("SELECT DISTINCT civ_name, unit_slug FROM ref_units")
        )
    finally:
        conn.close()
    assert pairs, "ref_units roster is empty — wrong DB?"
    return pairs


@pytest.fixture(scope="module")
def ref_columns():
    conn = sqlite3.connect(f"file:{REF_DB.as_posix()}?mode=ro", uri=True)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(ref_units)")}
    finally:
        conn.close()
    return cols


# ---------------------------------------------------------------------------
# (a) Orphan keys: config_combat keys must match the roster — with a
#     documented allowlist for keys that legitimately match nothing today.
#
# Matching semantics mirror analysis/combat_properties.get_combat_properties():
#   COMBAT_PROPERTIES        exact unit_slug match
#   UNIQUE_COMBAT_PROPERTIES exact OR unit_slug.startswith(key + "_")
#   CIV_COMBAT_PROPERTIES    exact (civ, slug) OR same civ + slug-prefix match
#
# Every allowlisted key below is a CANDIDATE FOR DELETION (or for a roster
# change): it is a silent no-op today. The prior audit counted ~21 orphans;
# ('Dravidians', 'elite_elephant') left the list on 2026-06-10 when the
# Imperial Battle Elephant row was restored (verified against the committed
# DB), leaving the 20 below. The test asserts set EQUALITY, so a NEW orphan
# fails the suite, and fixing/deleting an allowlisted key fails too until the
# entry here is removed — the list cannot go stale silently.
# ---------------------------------------------------------------------------

ALLOWED_ORPHANS_COMBAT = {
    "skirm": "Feudal-only line stage; ref DB materializes Castle+Imperial rows only",
    "spearman": "Feudal-only line stage; ref DB materializes Castle+Imperial rows only",
    "scout": "Feudal-only line stage; ref DB materializes Castle+Imperial rows only",
    "winged_hussar": "roster models the Imperial light-cav of all civs as 'hussar'; no winged_hussar slug exists",
    "organ_gun": "unique unit is civ-suffixed (organ_gun_portuguese); COMBAT_PROPERTIES is exact-match so this never fires",
    "elite_organ_gun": "civ-suffixed (elite_organ_gun_portuguese); exact-match never fires",
    "hussite_wagon": "civ-suffixed (hussite_wagon_bohemians); exact-match never fires",
    "elite_hussite_wagon": "no elite_hussite_wagon* slug (elite shares the base slug); exact-match never fires",
    "chakram_thrower": "civ-suffixed (chakram_thrower_gurjaras); exact-match never fires",
    "elite_chakram_thrower": "civ-suffixed (elite_chakram_thrower_gurjaras); exact-match never fires",
    "warrior_priest": "civ-suffixed (warrior_priest_armenians); exact-match never fires",
    "grenadier": "civ-suffixed (grenadier_jurchens); exact-match never fires",
    "war_chariot": "civ-suffixed (war_chariot_shu); exact-match never fires",
    "mounted_trebuchet": "civ-suffixed (mounted_trebuchet_khitans); exact-match never fires",
    "jian_swordsman": "civ-suffixed (jian_swordsman_wu); exact-match never fires",
}

ALLOWED_ORPHANS_UNIQUE = {
    "elite_xianbei_raider": (
        "elite shares the non-elite slug (xianbei_raider_wei at Castle AND "
        "Imperial), so the elite_ key can never prefix-match; its values are "
        "identical to the live 'xianbei_raider' entry"
    ),
}

ALLOWED_ORPHANS_CIV = {
    ("Sicilians", "heavy_camel"): "Sicilians have no camel line in the roster (tech tree)",
    ("Sicilians", "hand_cannoneer"): "Sicilians have no hand cannoneer in the roster (tech tree)",
    ("Poles", "winged_hussar"): "Poles imperial light-cav is modeled as 'hussar' (which carries the live Lechitic Legacy entry)",
    ("Romans", "legionary"): "Romans imperial militia line is modeled under the generic 'champion' slug (which carries the live Comitatenses entry)",
}


def test_orphan_keys_combat_properties(roster):
    slugs = {slug for _, slug in roster}
    orphans = {k for k in COMBAT_PROPERTIES if k not in slugs}
    unexpected = orphans - set(ALLOWED_ORPHANS_COMBAT)
    stale = set(ALLOWED_ORPHANS_COMBAT) - orphans
    assert not unexpected, (
        f"NEW orphan COMBAT_PROPERTIES keys (match no ref_units slug): "
        f"{sorted(unexpected)} — fix the key or allowlist it with a reason."
    )
    assert not stale, (
        f"Stale allowlist entries (now match the roster): {sorted(stale)} — "
        f"remove them from ALLOWED_ORPHANS_COMBAT."
    )


def test_orphan_keys_unique_combat_properties(roster):
    slugs = {slug for _, slug in roster}
    orphans = {
        k
        for k in UNIQUE_COMBAT_PROPERTIES
        if k not in slugs and not any(s.startswith(k + "_") for s in slugs)
    }
    unexpected = orphans - set(ALLOWED_ORPHANS_UNIQUE)
    stale = set(ALLOWED_ORPHANS_UNIQUE) - orphans
    assert not unexpected, (
        f"NEW orphan UNIQUE_COMBAT_PROPERTIES keys: {sorted(unexpected)}"
    )
    assert not stale, f"Stale ALLOWED_ORPHANS_UNIQUE entries: {sorted(stale)}"


def test_orphan_keys_civ_combat_properties(roster):
    orphans = set()
    for (civ, key) in CIV_COMBAT_PROPERTIES:
        if (civ, key) in roster:
            continue
        if any(c == civ and s.startswith(key + "_") for (c, s) in roster):
            continue
        orphans.add((civ, key))
    unexpected = orphans - set(ALLOWED_ORPHANS_CIV)
    stale = set(ALLOWED_ORPHANS_CIV) - orphans
    assert not unexpected, (
        f"NEW orphan CIV_COMBAT_PROPERTIES keys: {sorted(unexpected)}"
    )
    assert not stale, f"Stale ALLOWED_ORPHANS_CIV entries: {sorted(stale)}"


def test_dravidians_elite_elephant_is_not_an_orphan(roster):
    """Regression pin for the 2026-06-10 fix: the Imperial Battle Elephant row
    is back, so the Wootz Steel entry is live again."""
    assert ("Dravidians", "elite_elephant") in roster


# ---------------------------------------------------------------------------
# (b) registry <-> config_combat parity
# ---------------------------------------------------------------------------

def _config_property_names():
    names = set()
    for props in COMBAT_PROPERTIES.values():
        names |= set(props)
    for props in UNIQUE_COMBAT_PROPERTIES.values():
        names |= set(props)
    for props in CIV_COMBAT_PROPERTIES.values():
        names |= set(props)
    return names


def test_every_config_property_is_declared_in_registry():
    missing = _config_property_names() - param_names()
    assert not missing, (
        f"config_combat.py uses property names the registry does not declare: "
        f"{sorted(missing)} — add them to analysis/ability_registry.py."
    )


def test_every_curated_param_appears_in_config_or_has_quirks():
    """Every param of a 'curated:*'-sourced ability must be set somewhere in
    config_combat.py, or carry quirks text explaining why not (e.g. defined in
    another config module, or kept for symmetry)."""
    config_names = _config_property_names()
    offenders = []
    for ability, param in iter_params():
        if "curated:" not in ability.source:
            continue
        if param.name in config_names:
            continue
        if param.quirks or ability.quirks:
            continue
        offenders.append((ability.name, param.name))
    assert not offenders, (
        f"Curated params absent from config_combat.py without explanatory "
        f"quirks: {offenders}"
    )


# ---------------------------------------------------------------------------
# (c) registry <-> schema / loader
# ---------------------------------------------------------------------------

def test_every_declared_column_exists_in_ref_db(ref_columns):
    missing = [
        (a.name, p.name, p.column)
        for a, p in iter_params()
        if p.column is not None and p.column not in ref_columns
    ]
    assert not missing, (
        f"Registry declares ref_units columns that do not exist in the "
        f"committed webapp/aoe2_reference.db: {missing}"
    )


def test_every_combat_dict_param_appears_in_loader_source():
    """String-presence check against combat_unit_loader.build_combat_dict_from_ref."""
    missing = [
        (a.name, p.name)
        for a, p in iter_params()
        if p.in_combat_dict and f'"{p.name}"' not in LOADER_SRC
    ]
    assert not missing, (
        f"Params claimed to be in the combat dict but absent from "
        f"combat_unit_loader.py: {missing}"
    )


def test_params_not_in_combat_dict_are_really_absent_from_loader():
    """The inverse guard: if Phase B adds them to the loader, flip the flag."""
    present = [
        (a.name, p.name)
        for a, p in iter_params()
        if not p.in_combat_dict and f'"{p.name}"' in LOADER_SRC
    ]
    assert not present, (
        f"Params flagged in_combat_dict=False but found in the loader: {present}"
    )


# ---------------------------------------------------------------------------
# (d) registry <-> engines (presence-only)
# ---------------------------------------------------------------------------

def _camel(snake):
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _identifiers(param_name, engine):
    """Candidate identifiers for a param in an engine's source.

    Python engines consume snake_case; the `_json` suffix may be stripped
    after parsing (e.g. prepare_combat_unit emits `extra_projectile_attacks`).
    simulate.js reads snake_case off the stats dict and uses camelCase
    internally — accept either.
    """
    names = {param_name}
    if param_name.endswith("_json"):
        names.add(param_name[: -len("_json")])
    if engine == "js":
        names |= {_camel(n) for n in set(names)}
    return names


def test_engine_claims_are_valid_engine_names():
    for ability, param in iter_params():
        engines = ability.param_engines(param)
        assert set(engines) <= set(ALL_ENGINES), (ability.name, param.name, engines)


def test_registry_engine_parity_presence():
    """For each ability/param and each engine the registry lists, the param's
    identifier must appear in that engine's source. Presence-only — see module
    docstring."""
    failures = []
    for ability, param in iter_params():
        for engine in ability.param_engines(param):
            src = ENGINE_SOURCES[engine]
            idents = _identifiers(param.name, engine)
            if not any(
                re.search(rf"\b{re.escape(ident)}\b", src) for ident in idents
            ):
                failures.append((ability.name, param.name, engine))
    assert not failures, (
        f"Registry claims these engines implement these params, but the "
        f"identifier does not appear in the engine source: {failures}"
    )


KNOWN_ENGINE_GAPS = {
    # ability -> engines that deliberately do NOT implement it. These are the
    # registry's documented gaps (quirks fields); this test pins them so a
    # future port must update the registry (and this list) — and so nobody
    # "fixes" the registry by silently widening an engines tuple without code.
    # (dismount_on_death left this list 2026-06-10: ported to position + js
    # in the bundled sim_version window. Reverting that port now fails the
    # presence test above, since the registry claims all three engines.)
    "hp_regen_in_combat": {"abstract", "js"},  # Khitan Ordo: position-only
    "resources_per_kill": {"abstract", "js"},  # Mapuche eco: position-only
    "ranged_charge_mods": {"abstract"},        # Fire Lancer range/armor-ignore
    "projectile_speed": {"abstract"},          # no flight model in abstract
    "paired_forms": {"abstract", "position", "js"},  # serving-layer only
    "unit_category": {"abstract", "position", "js"},  # scoring metadata only
}


def test_known_engine_gaps_match_registry():
    for name, gaps in KNOWN_ENGINE_GAPS.items():
        ability = ABILITIES[name]
        declared = set(ability.engines)
        assert declared == set(ALL_ENGINES) - gaps, (
            f"{name}: registry engines {sorted(declared)} disagree with the "
            f"documented gap list {sorted(gaps)}"
        )


# ---------------------------------------------------------------------------
# (e) defaults match prepare_combat_unit
# ---------------------------------------------------------------------------

# Columns prepare_combat_unit indexes with row[...] (no .get fallback).
_PREPARE_REQUIRED_KEYS = [
    "attacks_json", "armors_json", "cost_food", "cost_wood", "cost_gold",
    "hp", "attack", "attack_range", "attack_speed", "attack_delay",
    "melee_armor", "pierce_armor", "movement_speed",
    "min_attack_range", "is_siege_projectile", "splash_radius",
    "projectile_speed", "ignores_pierce_armor", "ignores_melee_armor",
    "trample_percent", "trample_radius", "trample_flat_damage",
    "bonus_damage_reduction", "extra_projectiles",
    "extra_projectile_attacks_json", "splash_on_hit_radius",
    "dodge_shield_max", "dodge_shield_recharge", "bleed_dps",
    "bleed_duration", "block_first_melee", "attack_bonus_per_kill",
    "first_attack_extra_projectiles", "hp_regen", "pass_through_percent",
    "hp_transform_threshold", "pop_space",
]


def test_registry_defaults_match_prepare_combat_unit():
    """Feed prepare_combat_unit an all-NULL row and compare what it emits with
    the registry defaults, wherever the two define the same key.

    Skipped by construction: form-block params (prepare folds them into
    `transform`/`dismount` sub-dicts), and the eco trio (the abstract engine's
    prepare does not emit food/wood/gold_per_kill at all — they are
    position-engine inputs)."""
    from simulation import prepare_combat_unit  # webapp/ is on sys.path (conftest)

    row = {k: None for k in _PREPARE_REQUIRED_KEYS}
    prepared = prepare_combat_unit(row)

    mismatches = []
    for ability, param in iter_params():
        candidates = [param.name]
        if param.name.endswith("_json"):
            candidates.append(param.name[: -len("_json")])
        key = next((c for c in candidates if c in prepared), None)
        if key is None:
            continue
        got = prepared[key]
        want = param.default
        if got != want:
            mismatches.append(
                f"{ability.name}.{param.name}: registry default {want!r} but "
                f"prepare_combat_unit emits {got!r}"
            )
    assert not mismatches, "Defaults out of sync:\n" + "\n".join(mismatches)


# ---------------------------------------------------------------------------
# Registry structural sanity
# ---------------------------------------------------------------------------

def test_registry_structure():
    seen = {}
    for name, ability in ABILITIES.items():
        assert ability.name == name, f"dict key {name!r} != ability.name {ability.name!r}"
        assert ability.family in FAMILIES, (name, ability.family)
        assert ability.params, f"{name} declares no params"
        for param in ability.params:
            assert param.name not in seen, (
                f"param {param.name!r} declared by both {seen.get(param.name)!r} "
                f"and {name!r}"
            )
            seen[param.name] = name


def test_registry_covers_all_writer_columns(ref_columns):
    """Every special-ability column generate_reference.py writes must be owned
    by exactly one registry param. The non-ability columns of ref_units are
    listed explicitly so a NEW column cannot be added without a registry entry
    (or a conscious addition to this base list)."""
    base_columns = {
        # identity / classification
        "id", "civ_name", "unit_name", "unit_slug", "unit_type", "age",
        "unit_class", "unit_class_name", "is_ranged",
        # base/final scalar stats + costs + jsons
        "base_hp", "base_attack", "base_melee_armor", "base_pierce_armor",
        "base_speed", "base_range", "base_reload_time", "base_attack_delay",
        "base_accuracy", "base_los", "base_cost_food", "base_cost_wood",
        "base_cost_gold", "base_attacks_json", "base_armors_json",
        "final_hp", "final_attack", "final_melee_armor", "final_pierce_armor",
        "final_speed", "final_range", "final_reload_time", "final_attack_delay",
        "final_accuracy", "final_los", "final_cost_food", "final_cost_wood",
        "final_cost_gold", "final_attacks_json", "final_armors_json",
        "base_train_time", "final_train_time",
        "upgrade_cost_food", "upgrade_cost_wood", "upgrade_cost_gold",
        # projectile/geometry base data (not abilities)
        "total_projectiles", "outline_size_x", "applied_bonuses_summary",
    }
    registry_cols = {
        p.column for _, p in iter_params() if p.column is not None
    }
    unowned = ref_columns - base_columns - registry_cols
    assert not unowned, (
        f"ref_units columns owned by neither the base-stat list nor the "
        f"ability registry: {sorted(unowned)} — declare them in "
        f"analysis/ability_registry.py."
    )
    # and the registry must not invent columns (already covered by (c), but
    # cheap to assert the intersection is clean):
    assert registry_cols <= ref_columns
