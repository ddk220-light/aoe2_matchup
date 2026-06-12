import os, struct, sys
sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D
D_DIR = r"C:\dev\aoe2\aoe2record\lab"

doc = D.Doc(); es0 = {}
D.seed_from_snapshot(os.path.join(D_DIR, "val_first_snap.bin"), doc, es0)
# pick one JW (owner 3) and one TG (owner 2) army key
jw = next(k for k, e in es0.items() if e.get(2) == 3 and e.get(1) == 726)
tg = next(k for k, e in es0.items() if e.get(2) == 2 and e.get(1) == 2587)
print(f"JW key={jw} seed fields: master={es0[jw].get(1)} owner={es0[jw].get(2)} hp={es0[jw].get(12)}")
print(f"TG key={tg} seed fields: master={es0[tg].get(1)} owner={es0[tg].get(2)} hp={es0[tg].get(12)}")

data = open(os.path.join(D_DIR, "val_first_snap.bin"), "rb").read()


def decode_from(pos, mt, lim=24):
    r = D.Reader(data); r.p = pos + 7
    SCH = D.SCHEMA.get(mt, {}); out = {}; ops = []
    for _ in range(lim):
        op_pos = r.p
        try:
            op = r.u8()
            if op == 2:
                f = r.u8(); fi = SCH.get(f) or ("value", False, None); b = r.p
                v = D.read_value(r, *fi); out[f] = v; ops.append(f"a{f}={v}(w{r.p-b})")
            elif op == 1:
                ops.append("pop"); break
            elif op == 8:
                ops.append("OP8"); break
            elif op in (3, 5): r.u8(); ops.append(f"op{op}")
            elif op == 4: r.u8(); r.u8(); ops.append("op4")
            elif op in (7, 9, 12): r.u8(); r.i32(); ops.append(f"op{op}")
            elif op in (6, 10):
                f = r.u8(); r.i32(); fi = SCH.get(f) or ("value", False, None); D.read_value(r, *fi); ops.append(f"k{op}f{f}")
            elif op == 11: r.u8(); r.u8(); r.i32(); ops.append("op11")
            elif op == 13: r.u8(); r.i32(); r.i32(); ops.append("op13")
            elif op == 14: r.u8(); r.i32(); ops.append("op14")
            else: ops.append(f"BAD{op}"); break
        except Exception as e:
            ops.append(f"ERR:{type(e).__name__}"); break
    return out, ops


for label, key in (("TG", tg), ("JW", jw)):
    marker = bytes([8, 1, 12]) + struct.pack("<i", key)
    positions = []
    s = 0
    while True:
        p = data.find(marker, s)
        if p < 0: break
        positions.append(p); s = p + 1
    print(f"\n{label} key {key}: {len(positions)} marker occurrences")
    for p in positions[:6]:
        out, ops = decode_from(p, 12)
        print(f"  @{p}: master={out.get(1)} owner={out.get(2)} hp={out.get(12)}  ops={ops[:10]}")
