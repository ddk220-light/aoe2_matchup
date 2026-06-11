"""Phase 1: locate the desync onset frame by tracking army-HP sanity + resyncs."""
import struct, sys
sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D
import cade_api_pb2 as pb

PFX = r"C:\dev\aoe2\aoe2record\lab\run1"
doc = D.Doc(); es = {}; _, world_id = D.seed_from_snapshot(PFX + ".seed_snap.bin", doc, es)
army = {2: set(), 3: set()}
for k, e in es.items():
    if (e.get("__type__") in (9, 11, 12) and e.get(2) in (2, 3) and e.get(1) != 448
            and isinstance(e.get(12), (int, float)) and e.get(12) > 30):
        army[e.get(2)].add(k)
print("army S1(P2)=%d S2(P3)=%d" % (len(army[2]), len(army[3])))


def stats():
    s = {}
    for o in (2, 3):
        hs = [es[k].get(12) for k in army[o] if k in es and isinstance(es[k].get(12), (int, float))]
        alive = [h for h in hs if h > 0]
        bad = [h for h in hs if h < -1 or h > 1000]
        s[o] = (len(alive), int(sum(alive)), len(bad))
    return s


f = open(PFX + ".frames.bin", "rb"); fi = 0; frames = []
while True:
    hdr = f.read(4)
    if len(hdr) < 4:
        break
    ln = struct.unpack("<I", hdr)[0]; buf = f.read(ln)
    if len(buf) < ln:
        break
    sq = pb.FrameSequence(); sq.ParseFromString(buf)
    for fr in sq.frame:
        p = fr.patch
        if not p or len(p) > 400_000:
            continue
        rs = D.apply_patch(doc, p, es, world_id)
        fi += 1
        frames.append((fi, fr.time, rs, stats(), len(p), p))
f.close()

print("frame   gt    resync   S1(alive/hp/bad)     S2(alive/hp/bad)   plen")
onset = None
for (fi, t, rs, st, pl, p) in frames:
    flag = rs > 3 or st[2][2] > 0 or st[3][2] > 0
    if flag and onset is None:
        onset = fi
    if flag or fi % 100 == 0 or (onset and onset - 2 <= fi <= onset + 4):
        print(f"{fi:5} {t/1000:6.1f} {rs:6}   {str(st[2]):18} {str(st[3]):18} {pl}")
print("\nONSET frame:", onset, "of", len(frames))
if onset:
    open(PFX + ".onset_patch.bin", "wb").write(frames[onset - 1][5])
    open(PFX + ".pre_patch.bin", "wb").write(frames[onset - 2][5])
    print(f"saved onset patch ({len(frames[onset-1][5])} B) + pre patch")
