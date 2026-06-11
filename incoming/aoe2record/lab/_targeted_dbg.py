import os, struct, sys
sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D
from collections import Counter
D_DIR = r"C:\dev\aoe2\aoe2record\lab"

doc = D.Doc(); es0 = {}
D.seed_from_snapshot(os.path.join(D_DIR, "val_first_snap.bin"), doc, es0)
army = {}
for k, e in es0.items():
    mt = e.get("__type__"); o = e.get(2)
    if mt in (9, 11, 12) and o in (2, 3) and e.get(1) != 448 and isinstance(e.get(12), (int, float)) and e.get(12) > 30:
        army[k] = (mt, o)
print("army mt by owner:")
print("  S1(P2):", dict(Counter(mt for mt, o in army.values() if o == 2)))
print("  S2(P3):", dict(Counter(mt for mt, o in army.values() if o == 3)))

for fn in ("val_first_snap.bin", "val_latest_snap.bin"):
    data = open(os.path.join(D_DIR, fn), "rb").read()
    f2 = sum(1 for k, (mt, o) in army.items() if o == 2 and data.find(bytes([8, 1, mt]) + struct.pack("<i", k)) >= 0)
    f3 = sum(1 for k, (mt, o) in army.items() if o == 3 and data.find(bytes([8, 1, mt]) + struct.pack("<i", k)) >= 0)
    print(f"{fn}: S1 markers {f2}/23   S2 markers {f3}/30")

data = open(os.path.join(D_DIR, "val_first_snap.bin"), "rb").read()
s2 = [(k, mt) for k, (mt, o) in army.items() if o == 3][:4]
for k, mt in s2:
    kb = struct.pack("<i", k)
    pos = [i for i in range(len(data) - 4) if data[i:i + 4] == kb]
    pre = [(data[p - 3], data[p - 2], data[p - 1]) for p in pos[:4]]
    print(f"  S2 key {k} (seed mt={mt}): {len(pos)} raw occurrences; preceding 3 bytes: {pre}")
