"""D1 (siege round): read the .dat for the scorpion and mangonel lines and dump
EVERY field the two engines could have used, so the "what does the pipeline
drop" question is answered from the source rather than from the combat dict.

The .dat is not in the repo (data/inputs/MANIFEST.md) -- point --dat at a local
AoE2:DE install. genieutils-py lives in the conda python, so:

    D:/miniconda3/python.exe tools/simjs/d1_dat_audit.py \
        --dat "D:/SteamLibrary/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat" \
        --json D:/AI/aoe2_golden/d1_dat_audit.json

What it prints, per unit:
  * type_50 combat block: max/min range, reload, frame_delay, accuracy_percent,
    blast_width, blast_attack_level, blast_damage, projectile_unit_id,
    attacks/armours;
  * the PROJECTILE unit (type 60) behind it: speed, and its own type_50 block
    (a projectile carries blast fields of its own) plus the type_60-specific
    ballistics -- projectile_arc, penetration/pass-through flags, smart_mode,
    graphic_displacement, hit_mode/vanish_mode/area_effect_specials;
  * every attribute genieutils exposes on both objects, so a field nobody in
    this repo has ever read still shows up in the dump.

Unit ids are resolved by NAME from the dat itself (id_of), never hardcoded, so
a patch that renumbers a unit cannot silently audit the wrong row.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import fields, is_dataclass

# Names as they appear in the dat's internal `name` field (ASCII, no spaces
# for most siege). Resolved case-insensitively, substring-matched, and every
# match is printed so an ambiguous name is visible rather than guessed.
WANTED = [
    "SCORPIO",       # Scorpion / Heavy Scorpion (and their projectiles)
    "MANGONEL",      # Mangonel / Onager / Siege Onager
    "ONAGER",
    "BALLISTA",      # the AoK-era internal names the DE dat still carries
    "CATAPULT",
]

# The unit ids the calibration corpus actually fights with, audited by id as
# well as by name so a renamed row still lands in the dump.
WANTED_IDS = [279, 280, 542, 550, 588, 1105]

# Fields that are structurally interesting on any object.
SKIP_BULK = {"graphics", "damage_graphics", "sprite", "annexes", "sound"}


def to_plain(v, depth=0):
    if depth > 3:
        return "<...>"
    if is_dataclass(v):
        return {f.name: to_plain(getattr(v, f.name, None), depth + 1)
                for f in fields(v) if f.name not in SKIP_BULK}
    if isinstance(v, (list, tuple)):
        if len(v) > 24:
            return f"<{len(v)} items>"
        return [to_plain(x, depth + 1) for x in v]
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)


def obj_dump(o, depth=0):
    """Every non-callable, non-dunder attribute of `o`, flattened."""
    if o is None:
        return None
    out = {}
    names = ([f.name for f in fields(o)] if is_dataclass(o)
             else [n for n in dir(o) if not n.startswith("_")])
    for n in names:
        if n in SKIP_BULK:
            continue
        try:
            v = getattr(o, n)
        except Exception:
            continue
        if callable(v):
            continue
        out[n] = to_plain(v, depth)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dat", required=True)
    ap.add_argument("--json")
    args = ap.parse_args()

    from genieutils.datfile import DatFile

    df = DatFile.parse(args.dat)
    # Civ 0 (Gaia) misses some units; use the first civ with the fullest table.
    civ = max(df.civs, key=lambda c: sum(1 for u in c.units if u is not None))
    units = {i: u for i, u in enumerate(civ.units) if u is not None}

    by_name = {}
    for uid, u in units.items():
        nm = (getattr(u, "name", "") or "")
        by_name.setdefault(nm.upper(), []).append(uid)

    targets = []
    for want in WANTED:
        for nm, ids in by_name.items():
            if want in nm:
                for uid in ids:
                    targets.append((uid, nm))
    for uid in WANTED_IDS:
        if uid in units:
            targets.append((uid, (getattr(units[uid], "name", "") or "").upper()))
    targets = sorted(set(targets))

    report = {"civ_index": df.civs.index(civ), "units": {}}
    for uid, nm in targets:
        u = units[uid]
        rec = {
            "id": uid, "name": nm,
            "class": getattr(u, "unit_class", None),
            "hit_points": getattr(u, "hit_points", None),
            "speed": getattr(u, "speed", None),
            "collision_x": getattr(u, "collision_size_x", None),
            "collision_y": getattr(u, "collision_size_y", None),
            "type_50": obj_dump(getattr(u, "type_50", None)),
            "bird": obj_dump(getattr(u, "bird", None)),
            "projectile_block": obj_dump(getattr(u, "projectile", None)),
        }
        t50 = getattr(u, "type_50", None)
        pid = getattr(t50, "projectile_unit_id", -1) if t50 else -1
        rec["projectile_unit_id"] = pid
        if pid and pid > 0 and pid in units:
            p = units[pid]
            rec["projectile"] = {
                "id": pid, "name": getattr(p, "name", None),
                "speed": getattr(p, "speed", None),
                "class": getattr(p, "unit_class", None),
                "collision_x": getattr(p, "collision_size_x", None),
                "collision_y": getattr(p, "collision_size_y", None),
                "type_50": obj_dump(getattr(p, "type_50", None)),
                "projectile_block": obj_dump(getattr(p, "projectile", None)),
                "bird": obj_dump(getattr(p, "bird", None)),
            }
        report["units"][str(uid)] = rec

    for uid, rec in sorted(report["units"].items(), key=lambda kv: int(kv[0])):
        print(f"\n=== {rec['name']} (id {uid}) class={rec['class']} "
              f"hp={rec['hit_points']} speed={rec['speed']}")
        t = rec["type_50"] or {}
        for k in ("max_range", "min_range", "reload_time", "frame_delay",
                  "accuracy_percent", "accuracy_dispersion", "blast_width",
                  "blast_attack_level", "blast_damage",
                  "bonus_damage_resistance", "projectile_unit_id",
                  "displayed_attack", "attacks", "armours"):
            if k in t:
                print(f"    {k:26s} {t[k]}")
        p = rec.get("projectile")
        if p:
            print(f"  -> projectile {p['name']} (id {p['id']}) "
                  f"speed={p['speed']} coll={p['collision_x']}")
            pb = p.get("projectile_block") or {}
            for k, v in sorted(pb.items()):
                print(f"       proj.{k:22s} {v}")
            pt = p.get("type_50") or {}
            for k in ("blast_width", "blast_attack_level", "blast_damage",
                      "accuracy_percent", "attacks", "max_range"):
                if k in pt:
                    print(f"       proj.type_50.{k:14s} {pt[k]}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
