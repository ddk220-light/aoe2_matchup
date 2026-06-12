"""Validate candidate behavioral fingerprints: for each predicate, show the truth-type
distribution of matching units across both labeled games (precision check)."""
import sys, types, json
from collections import Counter, defaultdict
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab",
                r"C:\dev\aoe2\aoe2record\lab\_improve\behavior-fingerprint"]
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", r"C:\dev\aoe2\aoe2record\lab\labels.json"),
    "train": (r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
              r"C:\dev\aoe2\aoe2record\lab\labels_g2.json"),
}

agg = defaultdict(lambda: Counter())          # fingerprint -> truth type counter
special_orders = Counter()
transform_ids = Counter()

for game, (REPLAY, LABELS) in GAMES.items():
    labels = json.load(open(LABELS))
    truth_name = {int(k): u.get("type") for k, u in labels.items()}
    mt = mgz.model.parse_match(open(REPLAY, "rb"))
    ctx = uc.build_context(mt)   # owner/buildings/gaia/canon

    relic_ids = set()
    for g in (mt.gaia or []):
        if "relic" in ((getattr(g, "name", "") or "").lower()):
            relic_ids.add(g.instance_id)

    # per-unit stats
    st = defaultdict(lambda: defaultdict(int))
    targeted_by_enemy = Counter()
    for a in mt.actions:
        if not a.player:
            continue
        at = uc._at(a)
        payload = a.payload or {}
        ids = [ctx.canon(o) for o in payload.get("object_ids", [])]
        n = len(ids)
        tgt = payload.get("target_id")
        ctgt = ctx.canon(tgt) if isinstance(tgt, int) and tgt > 0 else None
        if at == "SPECIAL":
            oname = str(payload.get("order"))
            special_orders[f"{game}:{payload.get('order_id')}/{oname}"] += 1
        if at == "DE_TRANSFORM":
            for o in ids:
                transform_ids[(game, o)] += 1
        for cid in ids:
            if cid in ctx.building_ids or cid in ctx.gaia_all:
                continue
            s = st[cid]
            s["ncmd"] += 1
            if at == "MOVE":
                s["moves"] += 1
            elif at == "ORDER":
                s["orders"] += 1
                if ctgt in relic_ids:
                    s["relic"] += 1
                if ctgt in ctx.resource_ids:
                    s["gather"] += 1
                    if n <= 2:
                        s["solo_gather"] += 1
                if ctgt is not None and ctx.owner.get(ctgt) == a.player.name and ctgt in ctx.building_ids:
                    s["own_bld"] += 1
            elif at == "SPECIAL":
                onm = str(payload.get("order") or "")
                if "Trebuchet" in onm:
                    s["pack_treb"] += 1
                if onm == "Garrison":
                    s["garrison"] += 1
                    if n <= 2:
                        s["solo_garrison"] += 1
                    # target building owner's? monastery?
                    if ctgt is not None and truth_name.get(ctgt) == "Monastery":
                        s["garr_monastery"] += 1
            elif at == "FOLLOW":
                s["follow"] += 1
            elif at in ("BUILD", "REPAIR", "WALL"):
                s["build"] += 1
                if n <= 2:
                    s["solo_build"] += 1
            elif at == "PATROL":
                s["patrol"] += 1
            elif at == "STANCE":
                s["stance"] += 1
        # enemy targeting
        if at == "ORDER" and ctgt is not None:
            town = ctx.owner.get(ctgt)
            if town and town != a.player.name:
                targeted_by_enemy[ctgt] += 1

    for cid, s in st.items():
        tn = truth_name.get(cid)
        if not tn or tn.lower() == "flare" or tn.startswith("id"):
            tn = tn or "?"
        if s.get("relic"):
            agg["ORDER->relic"][tn] += 1
        if s.get("pack_treb"):
            agg["SPECIAL pack/unpack treb"][tn] += 1
        if s.get("garrison"):
            agg["SPECIAL garrison (any n)"][tn] += 1
        if s.get("solo_garrison"):
            agg["SPECIAL garrison (n<=2)"][tn] += 1
        if s.get("garr_monastery"):
            agg["garrison->monastery"][tn] += 1
        if s.get("solo_gather"):
            agg["gather n<=2"][tn] += 1
        if s.get("gather"):
            agg["gather any-n"][tn] += 1
        if s.get("follow"):
            agg["FOLLOW subject"][tn] += 1
        # moves-only: never ordered/built/gathered, only MOVEs (and maybe stop)
        if s.get("moves", 0) >= 2 and not s.get("orders") and not s.get("build") and not s.get("patrol"):
            agg[f"moves-only >=2"][tn] += 1
        if s.get("moves", 0) >= 3 and not s.get("orders") and not s.get("build") and not s.get("patrol"):
            agg[f"moves-only >=3"][tn] += 1
        if targeted_by_enemy.get(cid) and not s.get("gather") and not s.get("build") and not s.get("orders"):
            agg["enemy-targeted, no own orders"][tn] += 1
        if s.get("own_bld") and s.get("gather"):
            agg["own-bld-order + gather"][tn] += 1

print("=== fingerprint -> truth distribution (both games) ===")
for fp, c in agg.items():
    tot = sum(c.values())
    print(f"\n{fp}  (n={tot})")
    for tn, k in c.most_common(12):
        print(f"    {tn:22} {k}")

print("\n=== SPECIAL order ids ===")
for k, v in special_orders.most_common(20):
    print(f"  {k}: {v}")

print("\n=== DE_TRANSFORM ids (top) ===")
for (game, o), v in transform_ids.most_common(10):
    print(f"  {game} id={o}: {v}")
