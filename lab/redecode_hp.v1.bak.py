"""redecode_hp.py — offline re-decode of a saved run into a clean per-second per-side
HP+count timeline, using the REAL apply_patch decoder + entity_store (alive = present in
entity_store with hp>0). Army entities are chosen by key from the clean seed."""
import json, struct, sys
sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D
import cade_api_pb2 as pb

PFX = sys.argv[1] if len(sys.argv) > 1 else r"C:\dev\aoe2\aoe2record\lab\run1"
F_MASTER, F_OWNER, F_HP = 1, 2, 12

doc = D.Doc(); es = {}
_, world_id = D.seed_from_snapshot(PFX + ".seed_snap.bin", doc, es)
army = {2: set(), 3: set()}
for k, e in es.items():
    if (e.get("__type__") in (9, 11, 12) and e.get(F_OWNER) in (2, 3) and e.get(F_MASTER) != 448
            and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
        army[e.get(F_OWNER)].add(k)
print(f"army side1(P2)={len(army[2])}  side2(P3)={len(army[3])}")


def totals():
    out = {}
    for o in (2, 3):
        cnt = 0; hp = 0.0
        for k in army[o]:
            e = es.get(k)
            v = e.get(F_HP) if e else None
            if isinstance(v, (int, float)) and v > 0:
                cnt += 1; hp += v
        out[o] = (cnt, round(hp, 1))
    return out


rows = []; last_sec = -1; end_s = None; total_resync = 0
with open(PFX + ".frames.bin", "rb") as f:
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
            if p and len(p) > 400_000:
                # mid-stream full snapshot = the server's RESYNC after we fell behind.
                # Re-seed from it (entity keys persist, so army[] stays valid) instead of
                # skipping it, which would leave the doc permanently desynced.
                open(PFX + ".reseed.bin", "wb").write(p)
                doc = D.Doc(); es2 = {}
                _, world_id = D.seed_from_snapshot(PFX + ".reseed.bin", doc, es2)
                es = es2
                continue
            if p:
                total_resync += D.apply_patch(doc, p, es, world_id)
            sec = fr.time // 1000
            if sec > last_sec:
                last_sec = sec; t = totals()
                rows.append({"game_s": sec,
                             "side1": {"count": t[2][0], "hp": t[2][1]},
                             "side2": {"count": t[3][0], "hp": t[3][1]}})
                if end_s is None and sec >= 2 and (t[2][0] == 0 or t[3][0] == 0):
                    end_s = sec

with open(PFX + ".hp_log.jsonl", "w") as o:
    for r in rows:
        o.write(json.dumps(r) + "\n")
print(f"rows={len(rows)}  battle_end_game_s={end_s}  total_resyncs={total_resync}")
for r in rows:
    if r["game_s"] % 2 == 0 or r["game_s"] == end_s:
        m = "  <-- END" if r["game_s"] == end_s else ""
        print(f"  t={r['game_s']:3}s   S1 {r['side1']['count']:2}u /{r['side1']['hp']:6.0f}hp    "
              f"S2 {r['side2']['count']:2}u /{r['side2']['hp']:6.0f}hp{m}")
    if end_s is not None and r["game_s"] > end_s + 2:
        break
