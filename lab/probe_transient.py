import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cade_api_pb2 as pb, decode_state_v2 as D
import statistics as st
CAP = "captures/capture_20260603-224746.bin"
SCH = D.SCHEMA
TARGET = {112, 1902, 1717, 332}
created = {}
removed = {}
fh = open(CAP, "rb")
nframe = 0
while True:
    h = fh.read(4)
    if len(h) < 4:
        break
    ln = struct.unpack("<I", h)[0]
    buf = fh.read(ln)
    if len(buf) < ln:
        break
    sq = pb.FrameSequence()
    sq.ParseFromString(buf)
    for fr in sq.frame:
        t = fr.time
        p = fr.patch
        L = len(p)
        if not p or L > 500000:
            continue
        nframe += 1
        j = 0
        while j < L - 8:
            b = p[j]
            if b == 8 and p[j + 1] == 1 and p[j + 2] == 9 and p[j + 7] == 2:
                key = struct.unpack_from("<i", p, j + 3)[0]
                if 0 < key < 1_000_000 and key not in created:
                    r = D.Reader(p)
                    r.p = j + 7
                    f = {}
                    for _ in range(6):
                        if r.p >= L or p[r.p] != 2:
                            break
                        r.p += 1
                        fld = r.u8()
                        try:
                            v = D.read_value(r, *SCH.get(9, {}).get(fld, ("value", False, None)))
                        except Exception:
                            break
                        f[fld] = v
                        if all(k in f for k in (1, 2, 3, 4)):
                            break
                    m = f.get(1)
                    if m in TARGET:
                        created[key] = (t, m, f.get(2), f.get(3), f.get(4))
                j += 7
                continue
            if b in (9, 12) and p[j + 1] == 1:
                key = struct.unpack_from("<i", p, j + 2)[0]
                if 0 < key < 1_000_000 and key not in removed:
                    removed[key] = t
                j += 6
                continue
            j += 1
fh.close()
for M in (112, 1902, 1717):
    lifes = sorted((removed[k] - created[k][0]) / 1000 for k in created if created[k][1] == M and k in removed)
    n = sum(1 for k in created if created[k][1] == M)
    if lifes:
        print(f"master {M}: n={n} removed={len(lifes)} lifetime(s) p10={lifes[len(lifes)//10]:.2f} "
              f"median={st.median(lifes):.2f} p90={lifes[len(lifes)*9//10]:.2f} max={max(lifes):.1f}")
    else:
        print(f"master {M}: n={n} removed=0 (never removed in capture)")
print("sample master-112 (t, owner, x, y):")
for v in [v for v in created.values() if v[1] == 112][:6]:
    print(f"   t={v[0]/60000:.2f}m owner={v[2]} x={v[3]} y={v[4]}")
print("frames scanned:", nframe)
