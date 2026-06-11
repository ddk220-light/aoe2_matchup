"""Targeted army-entity HP decode: for each known army entity, scan ALL occurrences of its
marker (08 01 mt key) and accept the one whose decoded owner+master match the seed (robust
against coincidental byte matches). Reads the stable Entity model (mt 9-14) directly,
skipping the type-49 drift zone and the fragile band-locator."""
import os, struct, sys
sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D
D_DIR = r"C:\dev\aoe2\aoe2record\lab"
F_MASTER, F_OWNER, F_HP = 1, 2, 12

_doc = D.Doc(); es0 = {}
D.seed_from_snapshot(os.path.join(D_DIR, "val_first_snap.bin"), _doc, es0)
army = {}                                   # key -> (mt, owner, master)
for k, e in es0.items():
    mt = e.get("__type__"); o = e.get(F_OWNER)
    if (mt in (9, 11, 12) and o in (2, 3) and e.get(F_MASTER) != 448
            and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
        army[k] = (mt, o, e.get(F_MASTER))
print("army:", len(army), "S1=%d S2=%d" % (sum(o == 2 for _, o, _ in army.values()),
                                            sum(o == 3 for _, o, _ in army.values())))


def _decode_entity(data, pos, mt):
    """Read top-level op2 fields of the entity starting at marker `pos`; return {1,2,12,...}."""
    r = D.Reader(data); r.p = pos + 7
    SCH = D.SCHEMA.get(mt, {}); out = {}; depth = 0; n = 0
    while r.p < len(data) and n < 400:
        n += 1
        try:
            op = r.u8()
            if op == 2:
                f = r.u8()
                fi = (SCH.get(f) if depth == 0 else None) or ("value", False, None)
                v = D.read_value(r, *fi)
                if depth == 0:
                    out[f] = v
                    if F_MASTER in out and F_OWNER in out and F_HP in out:
                        break
            elif op == 1:
                if depth == 0:
                    break
                depth -= 1
            elif op == 8:
                if depth == 0:
                    break
                r.u8(); r.i32(); depth += 1
            elif op == 3:
                r.u8(); depth += 1
            elif op == 4:
                r.u8(); r.u8(); depth += 1
            elif op == 7:
                r.u8(); r.i32(); depth += 1
            elif op == 11:
                r.u8(); r.u8(); r.i32(); depth += 1
            elif op == 5:
                r.u8()
            elif op in (6, 10):
                f = r.u8(); r.i32()
                fi = (SCH.get(f) if depth == 0 else None) or ("value", False, None)
                D.read_value(r, *fi)
            elif op in (9, 12):
                r.u8(); r.i32()
            elif op == 13:
                r.u8(); r.i32(); r.i32()
            elif op == 14:
                r.u8(); r.i32()
            else:
                break
        except Exception:
            break
    return out


def army_hp(data, key, mt, owner, master):
    """Scan every marker occurrence; accept the entity whose owner+master match the seed."""
    marker = bytes([8, 1, mt]) + struct.pack("<i", key)
    start = 0
    while True:
        pos = data.find(marker, start)
        if pos < 0:
            return None
        e = _decode_entity(data, pos, mt)
        if e.get(F_OWNER) == owner and e.get(F_MASTER) == master:
            hp = e.get(F_HP)
            return hp if isinstance(hp, (int, float)) else None
        start = pos + 1


for label, fn in (("INITIAL", "val_first_snap.bin"), ("MID/POST-COMBAT", "val_latest_snap.bin")):
    data = open(os.path.join(D_DIR, fn), "rb").read()
    side = {2: [], 3: []}
    for k, (mt, o, master) in army.items():
        hp = army_hp(data, k, mt, o, master)
        if isinstance(hp, (int, float)) and hp > 0:
            side[o].append(round(hp, 1))
    print(f"{label:16}  S1(P2) {len(side[2]):2}u / {sum(side[2]):6.0f}hp     "
          f"S2(P3) {len(side[3]):2}u / {sum(side[3]):6.0f}hp")
