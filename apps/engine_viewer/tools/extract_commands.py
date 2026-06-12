"""rec.aoe2record -> data/4_lumber/commands.json (sim input, replay-pure).

Everything the engine needs comes from the replay file alone: starting
entities from the header (player objects + gaia), commands from the action
stream. The gRPC capture is used only by extract_truth.py.

Run: apps/video/.venv python (has the pinned mgz fork).
"""
import json
import math
from pathlib import Path

import mgz.model

REPLAY = Path(
    r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894"
    r"\savegame\rec.aoe2record"
)
OUT = Path(__file__).resolve().parents[1] / "data" / "4_lumber" / "commands.json"

TYPE_BY_NAME = {
    "villager": "villager",
    "town center": "town_center",
    "scout cavalry": "scout",
}


def main():
    with open(REPLAY, "rb") as f:
        match = mgz.model.parse_match(f)

    p1 = match.players[0]
    entities = []
    for obj in p1.objects or []:
        name = (obj.name or "").lower()
        etype = TYPE_BY_NAME.get(name)
        pos = getattr(obj, "position", None)
        if etype and pos is not None:
            entities.append({
                "id": obj.instance_id, "type": etype, "owner": 1,
                "x": round(pos.x, 2), "y": round(pos.y, 2),
            })

    cmds = []
    for a in match.actions:
        ty = str(a.type).replace("Action.", "")
        pl = a.payload or {}
        ts = round(a.timestamp.total_seconds(), 3)
        if ty == "ORDER" and pl.get("target_id"):
            cmds.append({"t": ts, "type": "order",
                         "unit_ids": pl["object_ids"],
                         "target_id": pl["target_id"]})
        elif ty == "GATHER_POINT" and pl.get("target_id"):
            cmds.append({"t": ts, "type": "gather_point",
                         "building_id": pl["object_ids"][0],
                         "target_id": pl["target_id"]})
        elif ty == "DE_QUEUE" and pl.get("unit_id") == 83:
            cmds.append({"t": ts, "type": "queue",
                         "building_id": pl["object_ids"][0],
                         "unit": "villager", "train_time": 25.0})
        elif ty == "RESIGN":
            cmds.append({"t": ts, "type": "resign", "player": 1})

    # DE headers list the TC as several same-named annex parts; keep the one
    # the command stream actually references (queue/rally building_id).
    cmd_building_ids = {c.get("building_id") for c in cmds if c.get("building_id")}
    tcs = [e for e in entities if e["type"] == "town_center"]
    keep_tc = next((e for e in tcs if e["id"] in cmd_building_ids), tcs[0])
    entities = [e for e in entities
                if e["type"] != "town_center" or e is keep_tc]

    target_ids = {c.get("target_id") for c in cmds if c.get("target_id")}
    tc = keep_tc
    props = []
    for g in getattr(match, "gaia", None) or []:
        name = (getattr(g, "name", None) or "").lower()
        pos = getattr(g, "position", None)
        iid = getattr(g, "instance_id", None)
        if pos is None:
            continue
        if iid in target_ids:
            entities.append({
                "id": iid, "type": "tree", "owner": 0,
                "x": round(pos.x, 2), "y": round(pos.y, 2),
                "wood": 100.0, "hp": 20.0,
            })
        elif "tree" in name and math.hypot(pos.x - tc["x"], pos.y - tc["y"]) < 18:
            props.append({"x": round(pos.x, 2), "y": round(pos.y, 2),
                          "kind": "tree"})

    doc = {
        "scenario": "4_lumber",
        "map": {"dimension": match.map.dimension},
        "players": [{"id": 1, "name": p1.name, "civ": str(p1.civilization),
                     "start_wood": 150.0, "start_wood_source": "ui_observed"}],
        "duration": round(match.duration.total_seconds(), 3),
        "entities": entities,
        "props": props,
        "commands": cmds,
    }

    # ---- self-check: the known shape of the 4_lumber record ----
    kinds = [c["type"] for c in cmds]
    assert kinds == ["order", "gather_point", "queue", "resign"], kinds
    assert sorted(cmds[0]["unit_ids"]) == [3652, 3654, 3656], cmds[0]
    assert cmds[0]["target_id"] == 3662, cmds[0]
    assert cmds[1]["building_id"] == 3641 and cmds[1]["target_id"] == 3662
    assert abs(cmds[2]["t"] - 10.269) < 0.01, cmds[2]
    assert any(e["id"] == 3662 for e in entities), "ordered tree not in gaia"
    assert sum(1 for e in entities if e["type"] == "villager") == 3
    assert sum(1 for e in entities if e["type"] == "town_center") == 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1))
    print(f"OK {OUT}")
    print(f"  entities={len(entities)} props={len(props)} cmds={kinds}")
    for e in entities:
        print(f"  {e}")


if __name__ == "__main__":
    main()
