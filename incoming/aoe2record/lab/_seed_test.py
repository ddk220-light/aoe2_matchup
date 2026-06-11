import os, sys
sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D
DD = r"C:\dev\aoe2\aoe2record\lab"
F_HP = 12

doc = D.Doc(); es0 = {}
D.seed_from_snapshot(os.path.join(DD, "val_first_snap.bin"), doc, es0)
army = {2: set(), 3: set()}
for k, e in es0.items():
    if (e.get("__type__") in (9, 11, 12) and e.get(2) in (2, 3) and e.get(1) != 448
            and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
        army[e.get(2)].add(k)


def tot(es):
    out = {}
    for o in (2, 3):
        hs = [es[k].get(F_HP) for k in army[o] if k in es and isinstance(es[k].get(F_HP), (int, float)) and es[k].get(F_HP) > 0]
        out[o] = (len(hs), round(sum(hs), 0))
    return out


for fn in ("val_first_snap.bin", "val_latest_snap.bin", "grpc_auto_fight_1.seed_snap.bin"):
    path = os.path.join(DD, fn)
    if not os.path.exists(path):
        print(fn, "MISSING"); continue
    d = D.Doc(); es = {}
    try:
        D.seed_from_snapshot(path, d, es)
        print(f"{fn:36} size={os.path.getsize(path)//1024}KB  S1={tot(es)[2]}  S2={tot(es)[3]}  (entities={len(es)})")
    except Exception as e:
        print(fn, "ERR", type(e).__name__, e)
