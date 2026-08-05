import sys, tempfile
from pathlib import Path
sys.path.insert(0, r"D:\AI\aoe2_matchup\aoe2x\grpc")
sys.path.insert(0, r"D:\AI\aoe2_matchup\apps\engine_viewer\tools")
import decode_state_v2 as D
from extract_truth import segment
F_MASTER, F_OWNER, F_X, F_Y, F_CARRY, F_HP = 1, 2, 3, 4, 6, 12
seg = segment(Path(r"D:\AI\aoe2_matchup\lab\captures\sheep.frames.bin"))
tmp = Path(tempfile.gettempdir()) / "sheep_dbg2.bin"
tmp.write_bytes(seg["snap"])
doc, es = D.Doc(), {}
_, wid = D.seed_from_snapshot(str(tmp), doc, es)
GEESE = [3703, 3702, 3705, 3704]
marks = list(range(0, 193, 8))
mi = 0
print("t       g3703  g3702  g3705  g3704   (kill: 35.7 / 94.7 / 139.5 / 179.3)")
for t, patch, events in seg["frames"]:
    if patch:
        D.apply_patch(doc, patch, es, wid)
    ts = t / 1000 if t else 0
    if mi < len(marks) and ts >= marks[mi]:
        mi += 1
        vals = []
        for g in GEESE:
            e = es.get(g)
            p = e.get(F_CARRY) if e else None
            vals.append(f"{p:5.1f}" if isinstance(p, float) else "  -  ")
        print(f"{ts:5.1f}   " + "  ".join(vals))
