"""<scenario>.aoe2record -> data/<scenario>/commands.json (sim input).

Replay-pure: starting entities + nearby resources from the header, commands
from the action stream. Generic schema (build / gather_point / queue / order /
resign) consumed by the engine.

Usage: extract_commands.py <scenario>   (default: camp300)

Note: the 4_lumber replay was overwritten by later recordings; its
data/4_lumber/commands.json is frozen (committed).
"""
import json
import math
import sys
from pathlib import Path

import mgz.model

SCEN = sys.argv[1] if len(sys.argv) > 1 else "camp300"
ROOT = Path(__file__).resolve().parents[1]
REPLAY = Path(r"D:\AI\aoe2_matchup\lab\captures") / f"{SCEN}.aoe2record"
OUT = ROOT / "data" / SCEN / "commands.json"

TYPE_BY_NAME = {"villager": "villager", "town center": "town_center",
                "scout cavalry": "scout"}
RES_RADIUS = 9.0    # gather resources within this radius of any focus point
# Unnamed-in-aocref gaia masters that are trees (verified vs gRPC capture:
# both seed a wood pool and got harvested in camp300).
TREE_MASTERS_UNNAMED = {2567, 2570}
# Per-species wood pools measured from the capture seed (default 100).
TREE_WOOD_BY_MASTER = {1063: 150.0}
BUSH_MASTERS = {1059}            # Fruit/Forage Bush [cap: pool 125 food]
BUSH_FOOD = 125.0
# Herdables (sheep/goose/turkey/...): mobile food, can be converted + herded.
HERDABLE_MASTERS = {594, 1243, 705, 833, 1142}  # sheep, goose, turkey, cow...
HERDABLE_FOOD = 100.0
# Huntables: deer (wild, flees, scout-pushed) + boar (aggros, fights back).
DEER_MASTERS = {1796}            # deer (this map)
BOAR_MASTERS = {48}              # wild boar
HUNTABLE_MASTERS = DEER_MASTERS | BOAR_MASTERS
DEER_FOOD = 140.0                # [cap] pool 140.0 per deer
DEER_HP = 40.0
BOAR_FOOD = 340.0               # [cap] pool 340.0 per boar
BOAR_HP = 75.0                  # [cap] Wild Boar HP
HUNT_ZONE = 32.0                 # base/action radius from the TC (excludes far herds)


def scenery_type(name, master):
    """Classify a gaia object for full-map DECOR (drawn, not simulated).
    Returns an engine-agnostic kind, or None to skip pure terrain clutter."""
    n = (name or "").lower()
    if "tree" in n or master in TREE_MASTERS_UNNAMED:
        return "tree"
    if master == 66 or "gold mine" in n:
        return "gold"
    if master == 102 or "stone mine" in n:
        return "stone"
    if master in HERDABLE_MASTERS or n in ("goose", "sheep") or n.startswith("cow"):
        return "herdable"
    if master == 48 or "boar" in n:
        return "boar"
    if master in (126, 812) or "wolf" in n or "jaguar" in n:
        return "predator"        # this map's hunters are jaguars, not wolves
    if "deer" in n:
        return "deer"
    if master == 285 or "relic" in n:
        return "relic"
    if "forage bush" in n or "fruit bush" in n:
        return "bush"
    return None                  # grass / plants / flowers / rocks / fish / unnamed


def build_elevation(match):
    """Per-tile elevation (0-9) as a flat row-major string, index = y*dim + x.
    This DOES come from the replay (the map header carries terrain+elevation)."""
    mp = match.map
    dim = mp.dimension
    grid = [["0"] * dim for _ in range(dim)]
    hi = 0
    for t in getattr(mp, "tiles", None) or []:
        pos = getattr(t, "position", None)
        if pos is None:
            continue
        h = int(getattr(t, "elevation", 0) or 0)
        h = max(0, min(9, h))
        hi = max(hi, h)
        if 0 <= pos.y < dim and 0 <= pos.x < dim:
            grid[pos.y][pos.x] = str(h)
    return {"dim": dim, "max": hi, "data": "".join("".join(r) for r in grid)}


def build_scenery(match, skip_ids):
    """Every renderable gaia object across the whole map, minus the ids that
    are already live sim entities (so they animate instead of sitting static)."""
    out = []
    for g in getattr(match, "gaia", None) or []:
        if g.instance_id in skip_ids:
            continue
        pos = getattr(g, "position", None)
        if pos is None:
            continue
        kind = scenery_type(getattr(g, "name", None), getattr(g, "object_id", None))
        if kind:
            out.append({"id": g.instance_id, "type": kind,
                        "x": round(pos.x, 2), "y": round(pos.y, 2)})
    return out


def main():
    with open(REPLAY, "rb") as f:
        match = mgz.model.parse_match(f)
    p1 = match.players[0]

    # ---- starting entities (dedupe multi-part TC to the commanded one) ----
    raw = []
    owned_herd_ids = set()
    for o in p1.objects or []:
        etype = TYPE_BY_NAME.get((o.name or "").lower())
        pos = getattr(o, "position", None)
        master = getattr(o, "object_id", None)
        if etype and pos is not None:
            raw.append({"id": o.instance_id, "type": etype, "owner": 1,
                        "x": round(pos.x, 2), "y": round(pos.y, 2)})
        elif master in HERDABLE_MASTERS and pos is not None:
            # a herdable already owned at game start (no conversion needed)
            owned_herd_ids.add(o.instance_id)
            raw.append({"id": o.instance_id, "type": "herdable", "owner": 1,
                        "x": round(pos.x, 2), "y": round(pos.y, 2),
                        "food": HERDABLE_FOOD, "master": master,
                        "species": (o.name or "Sheep")})

    cmds = []
    build_sites = []
    tc_ids = {e["id"] for e in raw if e["type"] == "town_center"}
    for a in match.actions:
        ty = str(a.type).replace("Action.", "")
        pl = a.payload or {}
        ts = round(a.timestamp.total_seconds(), 3)
        apos = getattr(a, "position", None)
        if ty == "BUILD":
            site = [round(apos.x, 2), round(apos.y, 2)] if apos else None
            if site:
                build_sites.append(site)
            cmds.append({"t": ts, "type": "build",
                         "unit_ids": pl["object_ids"],
                         "building": pl.get("building", "?"),
                         "x": site[0] if site else None,
                         "y": site[1] if site else None})
        elif ty == "GATHER_POINT" and pl.get("target_id"):
            cmds.append({"t": ts, "type": "gather_point",
                         "building_id": pl["object_ids"][0],
                         "target_id": pl["target_id"],
                         "x": round(apos.x, 2) if apos else None,
                         "y": round(apos.y, 2) if apos else None})
        elif ty == "ORDER" and pl.get("target_id"):
            cmds.append({"t": ts, "type": "order",
                         "unit_ids": pl["object_ids"],
                         "target_id": pl["target_id"]})
        elif ty == "MOVE" and apos is not None:
            cmds.append({"t": ts, "type": "move",
                         "unit_ids": pl["object_ids"],
                         "x": round(apos.x, 2), "y": round(apos.y, 2)})
        elif ty == "SPECIAL" and pl.get("target_id") in tc_ids:
            # garrison units into the TC (boosts its arrow fire — deer2/boars)
            cmds.append({"t": ts, "type": "garrison", "building_id": pl["target_id"],
                         "n": len(pl.get("object_ids") or [])})
        elif ty == "UNGARRISON":
            cmds.append({"t": ts, "type": "ungarrison", "building_id": None})
        elif ty == "RESEARCH":
            cmds.append({"t": ts, "type": "research",
                         "tech": pl.get("technology_id", pl.get("technology"))})
        elif ty == "DE_QUEUE" and pl.get("unit_id") == 83:
            cmds.append({"t": ts, "type": "queue",
                         "building_id": pl["object_ids"][0],
                         "unit": "villager", "train_time": 25.0})
        elif ty == "RESIGN":
            cmds.append({"t": ts, "type": "resign", "player": 1})

    cmd_bids = {c.get("building_id") for c in cmds if c.get("building_id")}
    tcs = [e for e in raw if e["type"] == "town_center"]
    keep_tc = next((e for e in tcs if e["id"] in cmd_bids), tcs[0] if tcs else None)
    entities = [e for e in raw if e["type"] != "town_center" or e is keep_tc]
    raw_herd_ids = {e["id"] for e in entities if e["type"] == "herdable"}
    # garrison/ungarrison target the one commanded TC
    for c in cmds:
        if c["type"] in ("garrison", "ungarrison"):
            c["building_id"] = keep_tc["id"]

    tcx, tcy = keep_tc["x"], keep_tc["y"]
    # focus points for resource harvesting = build sites + gather points +
    # every MOVE target (herding/push routes pass through the resource cluster),
    # but ONLY within the base action zone — the deer scout explores the whole
    # map late-game; without this clamp every far forest/herd would be pulled in
    # (huge sim bounds, wrong deer simmed). Localized scenarios are unaffected.
    focuses = list(build_sites)
    for c in cmds:
        if c.get("x") is not None and c["type"] in ("gather_point", "move"):
            focuses.append([c["x"], c["y"]])
    focuses = [f for f in focuses if math.hypot(f[0] - tcx, f[1] - tcy) <= HUNT_ZONE]
    if not focuses:
        focuses = [[tcx, tcy]]

    def near_focus(x, y):
        return any(math.hypot(x - fx, y - fy) <= RES_RADIUS for fx, fy in focuses)

    # herdables that the player commands (MOVE/ORDER target) are theirs; the
    # engine still performs the conversion visually via scout proximity.
    moved_ids = {i for c in cmds if c["type"] == "move" for i in c["unit_ids"]}

    trees, bushes, herds, hunt = [], [], [], []
    for g in getattr(match, "gaia", None) or []:
        name = (getattr(g, "name", None) or "").lower()
        pos = getattr(g, "position", None)
        master = getattr(g, "object_id", None)
        if pos is None:
            continue
        if master in HUNTABLE_MASTERS or "deer" in name or "boar" in name:
            # huntables in the base zone are simmed; far herds (the scout merely
            # explores past them) stay render decor. Boars AGGRO + fight back;
            # deer FLEE and are pushed. Both reuse the carcass once slain.
            if math.hypot(pos.x - tcx, pos.y - tcy) <= HUNT_ZONE:
                xy = {"x": round(pos.x, 2), "y": round(pos.y, 2)}
                if master in BOAR_MASTERS or "boar" in name:
                    hunt.append({"id": g.instance_id, "type": "herdable", "species": "boar",
                                 "aggro": True, "owner": 0, **xy,
                                 "food": BOAR_FOOD, "hp": BOAR_HP, "master": master,
                                 "home": [xy["x"], xy["y"]]})
                else:
                    hunt.append({"id": g.instance_id, "type": "herdable", "species": "deer",
                                 "wild": True, "owner": 0, **xy,
                                 "food": DEER_FOOD, "hp": DEER_HP, "master": master,
                                 "home": [xy["x"], xy["y"]]})
            continue
        if master in HERDABLE_MASTERS:
            # skip herdables already added from player objects (owned at start)
            if g.instance_id in raw_herd_ids:
                continue
            # include herdables that are commanded OR near a focus cluster
            if g.instance_id in moved_ids or near_focus(pos.x, pos.y):
                herds.append({"id": g.instance_id, "type": "herdable", "owner": 0,
                              "x": round(pos.x, 2), "y": round(pos.y, 2),
                              "food": HERDABLE_FOOD, "master": master,
                              "species": (getattr(g, "name", None) or "Sheep")})
            continue
        if not near_focus(pos.x, pos.y):
            continue
        if "tree" in name or master in TREE_MASTERS_UNNAMED:
            trees.append({"id": g.instance_id, "type": "tree", "owner": 0,
                          "x": round(pos.x, 2), "y": round(pos.y, 2),
                          "wood": TREE_WOOD_BY_MASTER.get(master, 100.0),
                          "hp": 20.0, "master": master,
                          "species": (g.name or "Straggler").replace("Tree (", "").rstrip(")")})
        elif master in BUSH_MASTERS:
            bushes.append({"id": g.instance_id, "type": "bush", "owner": 0,
                           "x": round(pos.x, 2), "y": round(pos.y, 2),
                           "food": BUSH_FOOD, "master": master})
    # A HUNT scenario (deer/boar) doesn't FORAGE: the capture shows the villagers
    # only ate carcasses, never a bush. Drop bushes as gatherables so idle
    # villagers wait for the next kill instead of berry-farming. Trees STAY —
    # they're obstacles the scout paths around, and that detour is what makes its
    # path match the real scout (they still aren't gathered: wood != carcass food).
    if hunt:
        bushes = []
    entities += trees + bushes + herds + hunt

    # Trained-villager ids the LATER commands reference (ORDER/MOVE a villager
    # that isn't a starting unit/scout/TC). DE assigns spawned units sequential
    # instance_ids, so sorting gives spawn order — the engine assigns these to
    # its trained villagers so those commands (boar bait/swarm) hit real units.
    start_ids = {e["id"] for e in entities if e["type"] in ("villager", "scout")}
    referenced = set()
    for c in cmds:
        for i in c.get("unit_ids", []) or []:
            referenced.add(i)
    trained_ids = sorted(i for i in referenced if i not in start_ids and i not in tc_ids)

    doc = {
        "scenario": SCEN,
        "map": {"dimension": match.map.dimension},
        "trained_ids": trained_ids,
        "players": [{"id": 1, "name": p1.name, "civ": str(p1.civilization),
                     "start_wood": 200.0, "start_food": 200.0,
                     "start_source": "standard_dark_age"}],
        "duration": round(match.duration.total_seconds(), 3),
        "entities": entities,
        "build_sites": build_sites,
        "scenery": build_scenery(match, {e["id"] for e in entities}),
        "elevation": build_elevation(match),
        "props": [],
        "commands": cmds,
    }

    kinds = [c["type"] for c in cmds]
    assert sum(1 for e in entities if e["type"] == "villager") == 3
    assert trees or bushes or herds or hunt, "no resource source near the action"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1))
    print(f"OK {OUT}")
    print(f"  entities={len(entities)} trees={len(trees)} bushes={len(bushes)} "
          f"herds={len(herds)} hunt={len(hunt)} cmds={kinds}")
    print(f"  hunt: {[(d['id'], d['species'], d['x'], d['y']) for d in hunt]}")
    print(f"  build_sites={build_sites}")
    print(f"  builds: {[(c['t'], c['building'], c['x'], c['y']) for c in cmds if c['type']=='build']}")
    print(f"  herds: {[(h['id'], h['x'], h['y']) for h in herds]}")
    print(f"  moves: {[(c['t'], c['unit_ids'], c['x'], c['y']) for c in cmds if c['type']=='move']}")
    from collections import Counter
    sc = Counter(s["type"] for s in doc["scenery"])
    print(f"  scenery={len(doc['scenery'])} {dict(sc)}")
    el = doc["elevation"]
    print(f"  elevation: dim={el['dim']} max={el['max']} chars={len(el['data'])}")


if __name__ == "__main__":
    main()
