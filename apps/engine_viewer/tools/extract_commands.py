"""<scenario>.aoe2record -> data/<scenario>/commands.json (sim input).

Replay-pure: starting entities + nearby trees from the header, commands from
the action stream. Generic schema (build / gather_point / queue / resign)
consumed by the engine.

Usage: extract_commands.py <scenario>   (default: camp300)

Note: the 4_lumber replay was overwritten by later recordings; its
data/4_lumber/commands.json is frozen (committed). This tool now bakes
camp300 from lab/captures/camp300.aoe2record.
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
TREE_RADIUS = 9.0   # gather trees within this many tiles of the build/gather focus
# Unnamed-in-aocref gaia masters that are trees (verified vs gRPC capture:
# both seed a wood pool and got harvested in camp300).
TREE_MASTERS_UNNAMED = {2567, 2570}
# Per-species wood pools measured from the capture seed (default 100).
TREE_WOOD_BY_MASTER = {1063: 150.0}


def main():
    with open(REPLAY, "rb") as f:
        match = mgz.model.parse_match(f)
    p1 = match.players[0]

    # ---- starting entities (dedupe multi-part TC to the commanded one) ----
    raw = []
    for o in p1.objects or []:
        etype = TYPE_BY_NAME.get((o.name or "").lower())
        pos = getattr(o, "position", None)
        if etype and pos is not None:
            raw.append({"id": o.instance_id, "type": etype, "owner": 1,
                        "x": round(pos.x, 2), "y": round(pos.y, 2)})

    cmds = []
    build_site = None
    for a in match.actions:
        ty = str(a.type).replace("Action.", "")
        pl = a.payload or {}
        ts = round(a.timestamp.total_seconds(), 3)
        apos = getattr(a, "position", None)
        if ty == "BUILD":
            build_site = [round(apos.x, 2), round(apos.y, 2)] if apos else None
            cmds.append({"t": ts, "type": "build",
                         "unit_ids": pl["object_ids"],
                         "building": pl.get("building", "Lumber Camp"),
                         "x": build_site[0] if build_site else None,
                         "y": build_site[1] if build_site else None})
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

    # focus point for the forest = build site (fallback: gather-point coords)
    focus = build_site
    if focus is None:
        gp = next((c for c in cmds if c["type"] == "gather_point" and c["x"]), None)
        focus = [gp["x"], gp["y"]] if gp else [keep_tc["x"], keep_tc["y"]]

    trees = []
    for g in getattr(match, "gaia", None) or []:
        name = (getattr(g, "name", None) or "").lower()
        pos = getattr(g, "position", None)
        master = getattr(g, "object_id", None)
        if pos is None:
            continue
        is_tree = "tree" in name or master in TREE_MASTERS_UNNAMED
        if not is_tree:
            continue
        if math.hypot(pos.x - focus[0], pos.y - focus[1]) <= TREE_RADIUS:
            trees.append({"id": g.instance_id, "type": "tree", "owner": 0,
                          "x": round(pos.x, 2), "y": round(pos.y, 2),
                          "wood": TREE_WOOD_BY_MASTER.get(master, 100.0),
                          "hp": 20.0, "master": master,
                          "species": (g.name or "Straggler").replace("Tree (", "").rstrip(")")})
    entities += trees

    doc = {
        "scenario": SCEN,
        "map": {"dimension": match.map.dimension},
        "players": [{"id": 1, "name": p1.name, "civ": str(p1.civilization),
                     "start_wood": 200.0, "start_wood_source": "ui_observed",
                     "goal_wood_collected": 300.0}],
        "duration": round(match.duration.total_seconds(), 3),
        "entities": entities,
        "build_site": build_site,
        "props": [],
        "commands": cmds,
    }

    kinds = [c["type"] for c in cmds]
    assert "build" in kinds, kinds
    assert build_site is not None, "no BUILD position"
    assert sum(1 for c in cmds if c["type"] == "queue") >= 3, kinds
    assert len(trees) >= 4, f"only {len(trees)} trees near build site"
    assert sum(1 for e in entities if e["type"] == "villager") == 3

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1))
    print(f"OK {OUT}")
    print(f"  entities={len(entities)} trees={len(trees)} cmds={kinds}")
    print(f"  build_site={build_site}  villagers="
          f"{[e['id'] for e in entities if e['type']=='villager']}")
    print(f"  trees: {[(t['id'], t['x'], t['y']) for t in trees]}")


if __name__ == "__main__":
    main()
