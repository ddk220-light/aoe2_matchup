"""Round 2: refined predicates with n-size and distinct-time conditions."""
import sys, types, json
from collections import Counter, defaultdict
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab",
                r"C:\dev\aoe2\aoe2record\lab\_improve\behavior-fingerprint"]
import mgz.model
import unit_classifier as uc

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", r"C:\dev\aoe2\aoe2record\lab\labels.json"),
    "train": (r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
              r"C:\dev\aoe2\aoe2record\lab\labels_g2.json"),
}

agg = defaultdict(lambda: Counter())

for game, (REPLAY, LABELS) in GAMES.items():
    labels = json.load(open(LABELS))
    truth_name = {int(k): u.get("type") for k, u in labels.items()}
    mt = mgz.model.parse_match(open(REPLAY, "rb"))
    ctx = uc.build_context(mt)

    relic_ids = {g.instance_id for g in (mt.gaia or [])
                 if "relic" in ((getattr(g, "name", "") or "").lower())}

    st = defaultdict(lambda: defaultdict(int))
    times = defaultdict(lambda: defaultdict(set))
    for a in mt.actions:
        if not a.player:
            continue
        at = uc._at(a)
        payload = a.payload or {}
        ids = [ctx.canon(o) for o in payload.get("object_ids", [])]
        n = len(ids)
        t = a.timestamp.total_seconds()
        tgt = payload.get("target_id")
        ctgt = ctx.canon(tgt) if isinstance(tgt, int) and tgt > 0 else None
        for cid in ids:
            if cid in ctx.building_ids or cid in ctx.gaia_all:
                continue
            s = st[cid]
            if at == "ORDER":
                if ctgt in relic_ids:
                    s[f"relic_n{min(n,3)}"] += 1
                if ctgt in ctx.resource_ids:
                    s["gather"] += 1
                    times[cid]["gather_t"].add(round(t))
                    if n == 1:
                        s["gather_n1"] += 1
                    if n <= 2:
                        s["gather_n2"] += 1
                if ctgt is not None and ctx.owner.get(ctgt) == a.player.name and ctgt in ctx.building_ids:
                    s["own_bld"] += 1
                    if n <= 2:
                        s["own_bld_n2"] += 1
            if at in uc.MIL_CMDS:
                s["hardmil"] += 1
            if at in ("BUILD", "REPAIR", "WALL"):
                s["build"] += 1

    for cid, s in st.items():
        tn = truth_name.get(cid) or "?"
        coarse = ("villager-ish" if any(k in tn.lower() for k in
                  ("villager", "lumberjack", "miner", "hunter", "shepherd", "builder", "forager", "fisher", "farmer", "repairer", "gatherer"))
                  else tn)
        if s.get("relic_n1") or s.get("relic_n2"):
            agg["relic order n<=2"][tn] += 1
        if s.get("relic_n3"):
            agg["relic order n>=3"][tn] += 1
        nh = not s.get("hardmil")
        if s.get("gather_n1") and nh:
            agg["gather n==1, no hardmil"][coarse] += 1
        if s.get("gather_n2") and nh:
            agg["gather n<=2, no hardmil"][coarse] += 1
        if len(times[cid]["gather_t"]) >= 2 and nh:
            agg["gathers >=2 distinct times, no hardmil"][coarse] += 1
        if len(times[cid]["gather_t"]) >= 3 and nh:
            agg["gathers >=3 distinct times, no hardmil"][coarse] += 1
        if s.get("own_bld_n2") and nh and not s.get("gather"):
            agg["own-bld n<=2, no hardmil, no gather"][coarse] += 1

print("=== refined fingerprints -> truth ===")
for fp, c in agg.items():
    tot = sum(c.values())
    vil = c.get("villager-ish", 0)
    print(f"\n{fp}  (n={tot}, villager-ish={vil})")
    for tn, k in c.most_common(14):
        print(f"    {tn:22} {k}")
