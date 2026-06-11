"""Calibrate per-type train times from truth spawn gaps (mode of consecutive
same-type same-owner inter-spawn intervals == train time when one building
produces continuously)."""
import sys, json
from collections import Counter, defaultdict

E_DIR = "C:/dev/aoe2/aoe2record/lab"
sys.path.insert(0, E_DIR)

LABELS = {"g0": r"C:\dev\aoe2\aoe2record\lab\labels.json",
          "train": r"C:\dev\aoe2\aoe2record\lab\labels_g2.json"}

for key, lp in LABELS.items():
    labels = json.load(open(lp))
    print(f"=== {key} ===")
    spawns = defaultdict(list)   # (owner, raw type) -> [t]
    for k, u in labels.items():
        nm = (u.get("type") or "").lower()
        if not nm or nm == "flare" or nm.startswith("id"):
            continue
        spawns[(u.get("owner"), nm)].append((u.get("created_ms") or 0) / 1000)
    for (o, nm), ts in sorted(spawns.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        if len(ts) < 4:
            continue
        ts.sort()
        gaps = [round((b - a) * 20) / 20 for a, b in zip(ts, ts[1:]) if 0.1 < b - a < 120]
        if not gaps:
            continue
        # cluster gaps to 0.25s and show top modes
        cl = Counter(round(g * 4) / 4 for g in gaps)
        top = cl.most_common(6)
        print(f"  owner={o} {nm:18} n={len(ts):3}  modes={top}")
