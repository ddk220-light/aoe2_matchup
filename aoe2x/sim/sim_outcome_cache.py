"""Role: batch-runner — per-fingerprint outcome cache for sim deduplication.

Two civs that produce a unit with identical final stats, costs, and special
abilities will produce identical sim outcomes for the same opponent and
seed.  Caching keyed by (my_fingerprint, opp_fingerprint, my_count,
opp_count, scale, seed) lets us skip repeat sims across civs.

Lives per-process; not pickled across pool workers.

Contract
--------
``unit_fingerprint`` consumes PREPARED combat dicts: the output of
``combat_unit_loader.build_combat_dict_from_ref`` run through either
``simulation_real.prepare_combat_unit`` (the batch-runner path:
run_matchup_battles / rebuild_matchup_baseline / patch_resim / verify_flips)
or ``simulation.prepare_combat_unit`` (the abstract engine).  The two shapes
differ — sim_real keeps ``attacks_json`` strings and flat ``dismount_*`` /
``transform_*`` keys, the abstract engine parses them into ``attacks`` dicts
and nested ``dismount`` / ``transform`` blocks — so every read below handles
both.  tests/test_sim_outcome_cache.py pins this contract against real units.

History: before 2026-06-11 this function read keys that exist in NEITHER
shape (``speed`` / ``reload_time`` / ``max_range`` / ``min_range`` /
``projectile_count`` / ``special_properties``), so movement speed, attack
speed, range, and every special ability were invisible to dedup and
genuinely-different units collapsed into one group (e.g. all 33 generic
champions, including Celts +15% speed, Japanese attack speed, Dravidians
Wootz Steel, Slavs trample).  The ability keys are now driven by
analysis/ability_registry.py — the canonical list of ability params.
"""

import json

try:
    from analysis.ability_registry import iter_params
except ImportError:  # pragma: no cover - launch dir on sys.path, repo root not
    import sys
    from pathlib import Path

    _ROOT = str(Path(__file__).resolve().parents[2])
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from analysis.ability_registry import iter_params


# Core final stats present (same key) in both prepared shapes: (key, ndigits).
_CORE_STATS = (
    ("hp", 1),
    ("attack", 1),
    ("melee_armor", 1),
    ("pierce_armor", 1),
    ("attack_range", 1),
    ("attack_speed", 4),      # attacks/sec (1/reload) — 1.5s vs 2.0s reload differs here
    ("attack_delay", 3),
    ("movement_speed", 3),
    ("accuracy", 1),
    ("base_accuracy", 1),
)

# Alternate-form stat blocks (Konnik dismount-on-death, Jian Swordsman HP
# transform).  In the sim_real shape these are flat ``<prefix>_<field>`` keys
# (+ ``<prefix>_attacks_json`` / ``<prefix>_armors_json``); in the abstract
# shape they are a nested dict under ``<prefix>`` with the bare field names.
_FORM_PREFIXES = ("dismount", "transform")
_FORM_BLOCK_FIELDS = (
    "hp", "attack", "melee_armor", "pierce_armor",
    "attack_speed", "attack_delay", "movement_speed",
)


def _ability_params():
    """(name, default) for every registry param the fingerprint must cover.

    Form-block stat params (dismount_* / transform_*) are excluded — they are
    fingerprinted as canonical blocks by _form_block() so both prepared
    shapes (flat keys vs nested dicts) hash identically.
    """
    out = []
    for _ability, p in iter_params():
        if not p.in_combat_dict:
            continue
        if p.name.startswith(("dismount_", "transform_")):
            continue
        out.append((p.name, p.default))
    return tuple(out)


_ABILITY_PARAMS = _ability_params()


def _table(value):
    """Canonical sorted tuple for an attack/armor table (dict or JSON string)."""
    if not value:
        return ()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return ()
    if not isinstance(value, dict):
        return ()
    return tuple(sorted((str(k), round(float(v), 4)) for k, v in value.items()))


def _json_param(unit, name):
    """Table for a ``*_json`` registry param: parsed key wins over raw JSON."""
    parsed = unit.get(name[:-5])  # 'extra_projectile_attacks_json' -> parsed dict
    if isinstance(parsed, dict):
        return _table(parsed)
    return _table(unit.get(name))


def _form_block(unit, prefix):
    """Canonical tuple for a dismount/transform block; () when absent.

    Mirrors simulation._parse_dismount/_parse_transform gating: no block
    unless ``<prefix>_hp`` (or nested ``hp``) is non-empty, so the ~99% of
    units without forms keep compact fingerprints.
    """
    nested = unit.get(prefix)
    if isinstance(nested, dict):
        get = nested.get
        attacks = _table(nested.get("attacks"))
        armors = _table(nested.get("armors"))
    else:
        get = lambda f: unit.get("%s_%s" % (prefix, f))  # noqa: E731
        attacks = _table(unit.get("%s_attacks_json" % prefix))
        armors = _table(unit.get("%s_armors_json" % prefix))
    if not get("hp"):
        return ()
    scalars = tuple(
        (f, round(float(v), 4))
        for f in _FORM_BLOCK_FIELDS
        for v in (get(f),)
        if v not in (None, "")
    )
    return scalars + (("attacks", attacks), ("armors", armors))


def unit_fingerprint(unit):
    """Canonical hashable fingerprint for a PREPARED combat unit dict.

    Includes every input that affects sim behavior: final core stats, costs,
    visual radius (outline_size), bonus damage tables, every ability-registry
    param (only when it differs from the registry default, so ability-less
    units keep compact fingerprints), and the dismount/transform form blocks.
    Values are rounded for float stability.
    """
    abilities = []
    for name, default in _ABILITY_PARAMS:
        if name.endswith("_json"):
            t = _json_param(unit, name)
            if t:
                abilities.append((name, t))
            continue
        value = unit.get(name, default)
        if value is None:
            value = default
        if isinstance(value, (int, float)):
            value = round(float(value), 4)
            neutral = (
                round(float(default), 4)
                if isinstance(default, (int, float))
                else default
            )
            if value != neutral:
                abilities.append((name, value))
        elif value != default:
            abilities.append((name, str(value)))
    for prefix in _FORM_PREFIXES:
        block = _form_block(unit, prefix)
        if block:
            abilities.append((prefix, block))

    attacks = unit.get("attacks")
    attacks_t = _table(attacks if isinstance(attacks, dict) else unit.get("attacks_json"))
    armors = unit.get("armors")
    armors_t = _table(armors if isinstance(armors, dict) else unit.get("armors_json"))

    return (
        tuple(round(float(unit.get(k) or 0), nd) for k, nd in _CORE_STATS)
        + (
            int(unit.get("cost_food") or 0),
            int(unit.get("cost_wood") or 0),
            int(unit.get("cost_gold") or 0),
            round(float(unit.get("outline_size") or 0.2), 3),
            attacks_t,
            armors_t,
            tuple(sorted(abilities)),
        )
    )


class OutcomeCache:
    __slots__ = ("_data", "hits", "misses")

    def __init__(self):
        self._data = {}
        self.hits = 0
        self.misses = 0

    def get(self, fp1, fp2, count1, count2, scale, seed):
        key = (fp1, fp2, count1, count2, scale, seed)
        out = self._data.get(key)
        if out is None:
            self.misses += 1
        else:
            self.hits += 1
        return out

    def put(self, fp1, fp2, count1, count2, scale, seed, outcome):
        self._data[(fp1, fp2, count1, count2, scale, seed)] = outcome

    def stats(self):
        total = self.hits + self.misses
        rate = (self.hits / total) if total else 0.0
        return {"hits": self.hits, "misses": self.misses, "hit_rate": rate}
