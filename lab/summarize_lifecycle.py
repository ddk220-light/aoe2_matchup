"""Clean GROUND-TRUTH summary from units_lifecycle.json.

Per player: how many units of each type (villager task-variants collapsed),
buildings, plus created/died/damage stats. Cross-checks military counts vs the
.aoe2record production. This is the simple ground-truth dataset we wanted.
"""
import json
import os
import sys
import types
from collections import Counter, defaultdict

import aocref

# ---- name map (master_id -> name, dataset 100) ----
_p = os.path.join(os.path.dirname(aocref.__file__), "data", "datasets", "100.json")
_raw = json.load(open(_p, encoding="utf-8"))
_objs = _raw.get("objects", _raw)
NAME = {}
for k, v in (_objs.items() if isinstance(_objs, dict) else []):
    try:
        NAME[int(k)] = v if isinstance(v, str) else (v.get("name") if isinstance(v, dict) else str(v))
    except Exception:
        pass

VILLAGER_KW = ("villager", "hunter", "lumberjack", "miner", "builder", "forager",
               "farmer", "fisher", "shepherd", "repairer", "gatherer", "berry")
ANIMAL_KW = ("cow", "llama", "sheep", "turkey", "goat", "pig", "deer", "boar",
             "wolf", "zebra", "ostrich", "rhino", "wild", "goose", "elephant",
             "jaguar", "crocodile", "hawk", "macaw", "fish", "marlin", "dolphin")
OWNER = {0: "Gaia", 1: "P1 munq (Bohemians)", 2: "P2 ddk220 (Incas)"}


def category(mt, name):
    n = (name or "").lower()
    if mt == 14:
        return "building"
    if name is None or name.startswith("id"):
        return "unknown"
    if "flare" in n:
        return "flare"
    if any(k in n for k in ANIMAL_KW):
        return "animal"
    if any(k in n for k in VILLAGER_KW):
        return "villager"
    return "military"


def aoe2record_production():
    for m in ("flask", "flask_cors", "requests"):
        sys.modules.setdefault(m, types.ModuleType(m))
    sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x"]
    import mgz.model
    mt = mgz.model.parse_match(open("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", "rb"))
    prod = defaultdict(Counter)
    for a in mt.actions:
        if str(a.type).endswith("DE_QUEUE") and a.player and a.payload:
            prod[a.player.name][a.payload.get("unit", "?")] += a.payload.get("amount", 1) or 1
    return prod


def main():
    units = json.load(open("units_lifecycle.json"))
    # bucket per player
    per = defaultdict(lambda: {"villager": Counter(), "military": Counter(),
                               "building": Counter(), "animal": Counter(),
                               "unknown": Counter(), "flare": Counter()})
    stats = defaultdict(lambda: Counter())
    for k, u in units.items():
        own = u.get("owner")
        if own not in (1, 2):
            continue
        mt = u.get("model_type")
        name = NAME.get(u.get("master_id"), f"id{u.get('master_id')}")
        cat = category(mt, name)
        label = "Villager" if cat == "villager" else name
        per[own][cat][label] += 1
        stats[own]["total_entities"] += 1
        if cat in ("villager", "military"):
            stats[own]["units"] += 1
            if u.get("died_ms") is not None:
                stats[own]["units_died"] += 1
            hx, hn = u.get("hp_max"), u.get("hp_min")
            if hx and hn is not None and hn < hx:
                stats[own]["units_damaged"] += 1

    prod = aoe2record_production()
    pname = {1: "munq", 2: "ddk220"}

    for own in (1, 2):
        b = per[own]
        print(f"\n================  {OWNER[own]}  ================")
        nvil = sum(b["villager"].values())
        print(f"VILLAGERS: {nvil}")
        print(f"MILITARY ({sum(b['military'].values())}):")
        for nm, c in b["military"].most_common():
            print(f"    {nm:22} {c}")
        print(f"BUILDINGS ({sum(b['building'].values())}):")
        for nm, c in b["building"].most_common(12):
            print(f"    {nm:22} {c}")
        if b["unknown"]:
            print(f"UNKNOWN ids ({sum(b['unknown'].values())}): {dict(b['unknown'].most_common(8))}")
        if b["animal"]:
            print(f"animals (eco): {sum(b['animal'].values())}")
        s = stats[own]
        print(f"lifecycle: units={s['units']}  died={s['units_died']}  took_damage={s['units_damaged']}")
        # cross-check vs .aoe2record production
        print("CROSS-CHECK vs .aoe2record production (gRPC alive-or-dead cumulative | record queued):")
        rec = prod.get(pname[own], Counter())
        gt_mil = b["military"]
        keys = set(rec) | set(gt_mil)
        for u in sorted(keys):
            print(f"    {u:18} gRPC={gt_mil.get(u,0):4}  record={rec.get(u,0):4}")
        print(f"    {'Villager':18} gRPC={nvil:4}  record={rec.get('Villager',0):4}")


if __name__ == "__main__":
    main()
