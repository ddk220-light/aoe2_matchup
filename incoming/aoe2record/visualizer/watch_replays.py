"""Arm the system to auto-analyze NEW recorded games.

Watches the AoE2:DE savegame folders for new .aoe2record files and, when a finished
replay appears, runs the unit-type classifier on it (production path -- .aoe2record
ONLY, no gRPC) and writes a per-game analysis: each player's civ, result, and military
army composition (exact unit-type counts), plus the full {instance_id: type} map.

Usage:
  python watch_replays.py            # poll forever (default), analyze each new replay
  python watch_replays.py --once     # analyze every not-yet-seen replay, then exit
  python watch_replays.py --all       # (re)analyze ALL replays, ignoring the seen-cache

Output: one JSON per replay in  C:/dev/aoe2/aoe2record/lab/analysis/<replay-stem>.json
A small state file tracks which replays were already processed.
"""
import json
import os
import sys
import time
import types
from collections import Counter

# headless: the classifier pulls in server-side deps transitively; stub them
for _m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(_m, types.ModuleType(_m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", os.path.dirname(os.path.abspath(__file__))]

import mgz.model
import unit_classifier as uc

# --- config ------------------------------------------------------------------
USER_GAMES = r"C:\Users\ddk22\Games\Age of Empires 2 DE"
WATCH_DIRS = []
for _profile in (os.listdir(USER_GAMES) if os.path.isdir(USER_GAMES) else []):
    for _sub in ("savegame", os.path.join("savegame", "multi")):
        d = os.path.join(USER_GAMES, _profile, _sub)
        if os.path.isdir(d):
            WATCH_DIRS.append(d)

OUT_DIR = r"C:\dev\aoe2\aoe2record\lab\analysis"
SEEN_FILE = os.path.join(OUT_DIR, "_seen.json")
POLL_SEC = 20
STABLE_SEC = 15          # file mtime must be this old => game finished writing


def _load_seen():
    try:
        return set(json.load(open(SEEN_FILE)))
    except Exception:
        return set()


def _save_seen(seen):
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(sorted(seen), open(SEEN_FILE, "w"))


def find_replays():
    out = []
    for d in WATCH_DIRS:
        for fn in os.listdir(d):
            if fn.lower().endswith(".aoe2record"):
                out.append(os.path.join(d, fn))
    return out


def analyze(path):
    """Run the classifier on one .aoe2record; return the analysis dict."""
    mt = mgz.model.parse_match(open(path, "rb"))
    type_map, _remap = uc.build_type_map(mt)

    # owner (player name) per canonical instance id, from the classifier context
    ctx = uc._run(mt)
    by_player = {}
    for p in mt.players:
        comp = Counter()
        for cid, g in ctx.guesses.items():
            if g.player != p.name:
                continue
            if cid in ctx.building_ids or cid in ctx.gaia_all:
                continue
            t = type_map.get(cid)
            if t and t not in ("villager", "unit"):
                comp[t] += 1
        n_vil = sum(1 for cid, g in ctx.guesses.items()
                    if g.player == p.name and type_map.get(cid) == "villager")
        by_player[p.name] = {
            "civ": getattr(p, "civilization", None),
            "winner": bool(getattr(p, "winner", False)),
            "team": getattr(p, "team_id", None),
            "villagers": n_vil,
            "military_total": sum(comp.values()),
            "army_composition": dict(comp.most_common()),
        }

    return {
        "replay": os.path.basename(path),
        "map": getattr(getattr(mt, "map", None), "name", None),
        "duration": str(getattr(mt, "duration", None)),
        "game_version": str(getattr(mt, "game_version", None)),
        "players": by_player,
        "unit_types": {str(k): v for k, v in type_map.items()},
    }


def process(path, seen):
    key = os.path.basename(path)
    try:
        res = analyze(path)
    except Exception as e:
        print(f"  ! failed to analyze {key}: {e}")
        seen.add(key)             # don't retry a corrupt/partial file forever
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, os.path.splitext(key)[0] + ".json")
    json.dump(res, open(out, "w"), indent=2)
    seen.add(key)
    print(f"  + {key}  [{res['map']} {res['duration']}]")
    for name, pl in res["players"].items():
        comp = ", ".join(f"{t}:{c}" for t, c in list(pl["army_composition"].items())[:6])
        print(f"      {name:16} {str(pl['civ']):12} "
              f"{'WIN' if pl['winner'] else '   '} vil={pl['villagers']:3} mil={pl['military_total']:3}  {comp}")
    print(f"      -> {out}")


def main():
    args = set(sys.argv[1:])
    if not WATCH_DIRS:
        print(f"No savegame folders found under {USER_GAMES}")
        return
    print("Watching:")
    for d in WATCH_DIRS:
        print(f"   {d}")
    seen = set() if "--all" in args else _load_seen()

    def sweep():
        now = time.time()
        new = 0
        for path in find_replays():
            if os.path.basename(path) in seen:
                continue
            try:
                if now - os.path.getmtime(path) < STABLE_SEC:
                    continue          # still being written (game in progress)
            except OSError:
                continue
            process(path, seen)
            new += 1
        if new:
            _save_seen(seen)
        return new

    if "--once" in args or "--all" in args:
        n = sweep()
        print(f"done: {n} new replay(s) analyzed.")
        return

    print(f"polling every {POLL_SEC}s (Ctrl-C to stop)...")
    while True:
        try:
            sweep()
            time.sleep(POLL_SEC)
        except KeyboardInterrupt:
            print("\nstopped.")
            break


if __name__ == "__main__":
    main()
