"""Goal harness: exact unit-type accuracy from the .aoe2record vs gRPC ground truth,
IGNORING units produced in the last 5 minutes. Reports per-player + combined, overall
(villager+military) and military-only, with the confusion + the worst error rows.
"""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer"]
from collections import Counter, defaultdict
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

REPLAY = "C:/dev/_tmp_replay/fresh_newpatch.aoe2record"
labels = json.load(open("labels.json"))
GAME_END_MIN = 42.6
CUT = (GAME_END_MIN - 5) * 60000     # ignore units spawned in the last 5 min


def run():
    mt = mgz.model.parse_match(open(REPLAY, "rb"))
    tm, _ = uc.build_type_map(mt)
    return tm


def scope(owner, mil_only):
    out = []
    for k, u in labels.items():
        if u.get("owner") != owner:
            continue
        if (u.get("created_ms") or 0) >= CUT:
            continue
        t = E.canon_truth(u["type"])
        cls = E.coarse(t)
        if cls not in ("villager", "military"):
            continue
        if mil_only and cls != "military":
            continue
        out.append((int(k), t))
    return out


def main():
    tm = run()
    print(f"=== GOAL: exact type accuracy, units spawned < {(GAME_END_MIN-5):.1f} min ===")
    for label, mil_only in (("OVERALL (vil+mil)", False), ("MILITARY only", True)):
        print(f"\n-- {label} --")
        gtot = gok = 0
        for owner, name in ((1, "munq"), (2, "ddk220")):
            units = [(k, t) for k, t in scope(owner, mil_only) if k in tm]
            if not units:
                continue
            ok = sum(E.canon_pred(tm[k]) == t for k, t in units)
            gtot += len(units); gok += ok
            print(f"   {name:8}: {100*ok/len(units):5.1f}%  ({ok}/{len(units)})")
        print(f"   {'COMBINED':8}: {100*gok/max(gtot,1):5.1f}%  ({gok}/{gtot})   GOAL 99%")

    # military confusion + worst errors (combined, in-scope)
    print("\n-- military confusion (in-scope) --")
    conf = Counter()
    errs = []
    for owner in (1, 2):
        for k, t in scope(owner, True):
            if k not in tm:
                continue
            p = E.canon_pred(tm[k])
            conf[(t, p)] += 1
            if p != t:
                errs.append((owner, k, t, p, (labels[str(k)].get("created_ms") or 0) / 60000))
    bt = defaultdict(lambda: [0, 0])
    for (t, p), c in conf.items():
        bt[t][1] += c
        if t == p:
            bt[t][0] += c
    for t in sorted(bt, key=lambda x: -bt[x][1]):
        e = {p: c for (tt, p), c in conf.items() if tt == t and tt != p}
        print(f"   {t:13} {bt[t][0]}/{bt[t][1]}   {e}")
    print(f"\n   total military errors in-scope: {len(errs)}")
    for owner, k, t, p, mn in sorted(errs, key=lambda x: -x[4])[:15]:
        print(f"     P{owner} id={k} TRUE={t:12} GOT={p:12} spawn={mn:.1f}m")


if __name__ == "__main__":
    main()
