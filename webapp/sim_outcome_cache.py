"""Role: batch-runner — per-fingerprint outcome cache for sim deduplication.

Two civs that produce a unit with identical final stats, costs, and special
properties will produce identical sim outcomes for the same opponent and
seed.  Caching keyed by (my_fingerprint, opp_fingerprint, my_count,
opp_count, scale, seed) lets us skip repeat sims across civs.

Lives per-process; not pickled across pool workers.
"""

# Alternate-form stat blocks (Konnik dismount-on-death, Jian Swordsman HP
# transform).  Appended to the fingerprint ONLY when present, so the ~99%
# of units without forms keep their exact historical fingerprints (and
# therefore their dedup-group hashes in existing baselines).
_FORM_FIELDS = (
    "hp_transform_threshold",
    "dismount_hp", "dismount_attack", "dismount_melee_armor",
    "dismount_pierce_armor", "dismount_attack_speed", "dismount_attack_delay",
    "dismount_movement_speed", "dismount_attacks_json", "dismount_armors_json",
    "transform_hp", "transform_attack", "transform_melee_armor",
    "transform_pierce_armor", "transform_attack_speed", "transform_attack_delay",
    "transform_movement_speed", "transform_attacks_json", "transform_armors_json",
)


def unit_fingerprint(unit):
    """Canonical hashable fingerprint for an instantiated combat unit dict.

    Includes every input that affects sim behavior: final stats, cost,
    visual radius (outline_size), bonus damage table, special properties.
    """
    attacks = unit.get("attacks") or {}
    if isinstance(attacks, dict):
        attacks_t = tuple(sorted((str(k), float(v)) for k, v in attacks.items()))
    else:
        attacks_t = tuple()
    armors = unit.get("armors") or {}
    if isinstance(armors, dict):
        armors_t = tuple(sorted((str(k), float(v)) for k, v in armors.items()))
    else:
        armors_t = tuple()
    special = unit.get("special_properties") or {}
    if isinstance(special, dict):
        special_t = tuple(sorted((str(k), float(v) if isinstance(v, (int, float)) else str(v))
                                 for k, v in special.items()))
    else:
        special_t = tuple()

    fp = (
        round(float(unit.get("hp") or 0), 1),
        round(float(unit.get("attack") or 0), 1),
        round(float(unit.get("melee_armor") or 0), 1),
        round(float(unit.get("pierce_armor") or 0), 1),
        round(float(unit.get("speed") or 0), 3),
        round(float(unit.get("max_range") or 0), 1),
        round(float(unit.get("min_range") or 0), 1),
        round(float(unit.get("reload_time") or 0), 3),
        int(unit.get("projectile_count") or 0),
        round(float(unit.get("projectile_speed") or 0), 2),
        int(unit.get("cost_food") or 0),
        int(unit.get("cost_wood") or 0),
        int(unit.get("cost_gold") or 0),
        round(float(unit.get("outline_size") or 0.2), 3),
        attacks_t, armors_t, special_t,
    )

    # Form blocks: appended ONLY when at least one field is non-empty/non-zero
    # so form-less units keep their exact pre-existing fingerprints.
    form_t = tuple(
        (name, round(float(val), 4) if isinstance(val, (int, float)) else str(val))
        for name in _FORM_FIELDS
        for val in (unit.get(name),)
        if val not in (None, 0, 0.0, "")
    )
    if form_t:
        return fp + (form_t,)
    return fp


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
