"""Decode the validation snapshots -> per-owner unit counts + HP, initial vs post-battle."""
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import build_ground_truth as G   # reuses decode_snapshot_entities, nm, collapse

HP = 12
REAL = (9, 11, 12)               # units (exclude buildings 14, missile 13, dopple 10)

results = {}
for label, f in (("INITIAL", r"C:\dev\aoe2\aoe2record\lab\val_first_snap.bin"),
                 ("POST-BATTLE", r"C:\dev\aoe2\aoe2record\lab\val_latest_snap.bin")):
    es = G.decode_snapshot_entities(f)
    by_owner = defaultdict(list)   # owner -> [(name, hp)]
    for k, e in es.items():
        if e.get("__type__") not in REAL:
            continue
        by_owner[e.get(2)].append((G.collapse(G.nm(e.get(1))), e.get(HP)))
    results[label] = by_owner
    print(f"\n===== {label}  ({f.split(chr(92))[-1]})  —  {len(es)} entities total =====")
    for owner in sorted(by_owner, key=lambda x: (x is None, x)):
        rows = by_owner[owner]
        cnt = Counter(n for n, _ in rows)
        print(f"  owner={owner}: {len(rows)} units  {dict(cnt.most_common(8))}")
        byname = defaultdict(list)
        for n, hp in rows:
            if isinstance(hp, (int, float)):
                byname[n].append(round(float(hp), 1))
        for n, hps in byname.items():
            print(f"      {n:24} n={len(hps):3} hp[min={min(hps)} max={max(hps)}] "
                  f"sample={sorted(hps)[:12]}")
