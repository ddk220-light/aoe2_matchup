"""_wf_review_instr.py - instrumented decode of the ground-truth dump with the
CURRENT decoder. Does NOT modify decode_state_v2.py; instruments via:
  * monkeypatched decode_state_v2._next_delta_marker (logs every re-anchor scan)
  * a logging dict subclass wrapped around entity_store after seeding
  * monkeypatched Doc.register (logs World-type registrations during deltas)

Checks:
  A. re-anchor economics: count, scanned bytes, max scan, landed marker types
  B. HP-write plausibility per army unit: monotone non-increasing, <= seed HP,
     sane magnitude, numeric type  (no healing exists in this scenario)
  C. removal plausibility: last-known HP at the moment an army unit is removed
  D. re-adds of removed army keys (should be 0)
  E. mt==1 (World) model registrations during the delta phase (op4 ctx loss check)
  F. death channel split for side1/side2 (removal op vs hp<=0)
ASCII output only.
"""
import contextlib
import io
import os
import struct
import sys

D_DIR = r"C:\dev\aoe2\aoe2record\lab"
sys.path.insert(0, D_DIR)
import decode_state_v2 as D  # noqa: E402
import cade_api_pb2 as pb    # noqa: E402

GT = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
      "\\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs)")
TMP = os.path.join(D_DIR, "_wf_review_instr.reseed.bin")
F_MASTER, F_OWNER, F_HP = 1, 2, 12
ARMY_MT = {9, 11, 12}
SCOUT = 448
SNAP_RESEED = 400_000
EXPECT = (24, 30)

EVENTS = []          # (seq, kind, payload) global ordered log
SEQ = [0]
CUR = {"t": None, "patch": -1}


def ev(kind, **kw):
    SEQ[0] += 1
    kw["t"] = CUR["t"]
    kw["patch"] = CUR["patch"]
    EVENTS.append((SEQ[0], kind, kw))


# --- marker scan logging ----------------------------------------------------
_orig_marker = D._next_delta_marker


def marker_logged(data, pos, known_keys):
    res = _orig_marker(data, pos, known_keys)
    scanned = (res - pos) if res is not None else (len(data) - pos)
    info = {"from": pos, "to": res, "scanned": scanned, "n": len(data)}
    if res is not None:
        b = data[res]
        info["op"] = b
        if b == 8:
            info["key"] = struct.unpack_from("<i", data, res + 3)[0]
            info["mt"] = data[res + 2]
        else:
            info["key"] = struct.unpack_from("<i", data, res + 2)[0]
    ev("reanchor", **info)
    return res


D._next_delta_marker = marker_logged

# --- Doc.register logging (delta phase only) ---------------------------------
_orig_register = D.Doc.register
DELTA_PHASE = [False]


def register_logged(self, mtype):
    if DELTA_PHASE[0] and mtype == 1:
        ev("register_world", mt=mtype)
    return _orig_register(self, mtype)


D.Doc.register = register_logged


# --- logging entity store -----------------------------------------------------
class LogEnt(dict):
    __slots__ = ("ekey",)

    def __init__(self, ekey, base):
        super().__init__(base)
        self.ekey = ekey

    def __setitem__(self, f, v):
        old = self.get(f, "<absent>")
        if f == F_HP:
            ev("hp_write", key=self.ekey, old=old, new=v)
        super().__setitem__(f, v)


class LogStore(dict):
    def __setitem__(self, k, v):
        if k in REMOVED_ONCE:
            ev("readd", key=k)
        if not isinstance(v, LogEnt):
            v = LogEnt(k, v)
        super().__setitem__(k, v)

    def pop(self, k, *a):
        if k in self:
            e = self[k]
            ev("remove", key=k, last_hp=e.get(F_HP))
            REMOVED_ONCE.add(k)
        return super().pop(k, *a)


REMOVED_ONCE = set()


def derive_army(es):
    army = {2: set(), 3: set()}
    for k, e in es.items():
        if (e.get("__type__") in ARMY_MT and e.get(F_OWNER) in (2, 3)
                and e.get(F_MASTER) != SCOUT
                and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
            army[e.get(F_OWNER)].add(k)
    return army


def read_frames(path):
    with open(path, "rb") as f:
        while True:
            hdr = f.read(4)
            if len(hdr) < 4:
                return
            ln = struct.unpack("<I", hdr)[0]
            buf = f.read(ln)
            if len(buf) < ln:
                return
            sq = pb.FrameSequence()
            sq.ParseFromString(buf)
            for fr in sq.frame:
                yield fr.time / 1000.0, (fr.patch if fr.patch else None)


def main():
    doc = es = world_id = army = None
    seed_hp = {}
    pi = -1
    for t, p in read_frames(GT + ".frames.bin"):
        CUR["t"] = round(t, 2)
        if p is not None and len(p) > SNAP_RESEED:
            with open(TMP, "wb") as sf:
                sf.write(p)
            doc, es0 = D.Doc(), {}
            DELTA_PHASE[0] = False
            with contextlib.redirect_stdout(io.StringIO()):
                _, world_id = D.seed_from_snapshot(TMP, doc, es0)
            a = derive_army(es0)
            if (len(a[2]), len(a[3])) == EXPECT:
                es = LogStore()
                for k, v in es0.items():
                    es[k] = v
                REMOVED_ONCE.clear()
                EVENTS.clear()
                army = a
                seed_hp = {k: es0[k].get(F_HP) for k in (a[2] | a[3])}
                DELTA_PHASE[0] = True
                print(f"[seed] fight snapshot at t={t:.2f} army=24v30")
            continue
        if es is None or p is None:
            continue
        pi += 1
        CUR["patch"] = pi
        D.apply_patch(doc, p, es, world_id)

    allk = army[2] | army[3]

    # A. reanchor economics
    re_ev = [e for e in EVENTS if e[1] == "reanchor"]
    total_scan = sum(e[2]["scanned"] for e in re_ev)
    max_scan = max((e[2]["scanned"] for e in re_ev), default=0)
    none_land = sum(1 for e in re_ev if e[2]["to"] is None)
    by_op = {}
    army_land = 0
    for e in re_ev:
        if e[2]["to"] is None:
            continue
        by_op[e[2]["op"]] = by_op.get(e[2]["op"], 0) + 1
        if e[2].get("key") in allk:
            army_land += 1
    print(f"\nA. reanchors={len(re_ev)} total_scanned_bytes={total_scan:,} "
          f"max_single_scan={max_scan:,} landed_none(abort_tail)={none_land}")
    print(f"   landed marker op distribution: {by_op}  landings_on_army_keys={army_land}")

    # B. HP plausibility on army units
    hp_writes = [e for e in EVENTS if e[1] == "hp_write" and e[2]["key"] in allk]
    units_with_hp = {e[2]["key"] for e in hp_writes}
    bad_type = [e for e in hp_writes if not isinstance(e[2]["new"], (int, float))]
    bad_mag = [e for e in hp_writes if isinstance(e[2]["new"], (int, float))
               and abs(e[2]["new"]) > 5000]
    over_seed, increases = [], []
    last = dict(seed_hp)
    for s, _, w in sorted(hp_writes):
        k, v = w["key"], w["new"]
        if isinstance(v, (int, float)):
            if seed_hp.get(k) is not None and v > seed_hp[k] + 1e-6:
                over_seed.append((w["t"], k, v))
            if isinstance(last.get(k), (int, float)) and v > last[k] + 1e-6:
                increases.append((w["t"], k, last[k], v))
            last[k] = v
    print(f"\nB. army hp_writes={len(hp_writes)} units_covered={len(units_with_hp)}/54")
    print(f"   non_numeric={len(bad_type)} magnitude>5000={len(bad_mag)} "
          f"writes_above_seed_hp={len(over_seed)} hp_INCREASES={len(increases)}")
    for x in (over_seed + [(t, k, f'{a}->{b}') for t, k, a, b in increases])[:10]:
        print("   anomaly:", x)

    # C. removal plausibility
    removes = [e for e in EVENTS if e[1] == "remove" and e[2]["key"] in allk]
    print(f"\nC. army removals={len(removes)}")
    susp = []
    for s, _, w in removes:
        lh = w["last_hp"]
        sd = seed_hp.get(w["key"]) or 1
        if isinstance(lh, (int, float)) and lh > 0.5 * sd:
            susp.append((w["t"], w["key"], lh, sd))
    print(f"   removals with last_known_hp > 50% of seed (possible spurious): {len(susp)}")
    for x in susp[:12]:
        print("   suspicious:", x)
    hist = {}
    for s, _, w in removes:
        lh = w["last_hp"]
        sd = seed_hp.get(w["key"]) or 1
        frac = -1 if not isinstance(lh, (int, float)) else lh / sd
        b = ("none" if frac < 0 else "<=0" if lh <= 0 else
             "0-10%" if frac <= .10 else "10-25%" if frac <= .25 else
             "25-50%" if frac <= .50 else ">50%")
        hist[b] = hist.get(b, 0) + 1
    print(f"   last-hp-at-removal histogram: {hist}")

    # D. re-adds
    readds = [e for e in EVENTS if e[1] == "readd" and e[2]["key"] in allk]
    print(f"\nD. army re-adds after removal: {len(readds)}")

    # E. World registrations in delta phase
    wreg = [e for e in EVENTS if e[1] == "register_world"]
    print(f"\nE. mt==1 (World) registrations during deltas: {len(wreg)}")

    # F. deaths per side at end of stream
    for side, name in ((2, "side1"), (3, "side2")):
        gone = [k for k in army[side] if k not in es]
        zero = [k for k in army[side] if k in es
                and isinstance(es[k].get(F_HP), (int, float)) and es[k].get(F_HP) <= 0]
        alive = len(army[side]) - len(gone) - len(zero)
        print(f"F. {name}: removed={len(gone)} hp<=0={len(zero)} alive_at_end={alive}")

    # G. writes immediately after a reanchor landing (at-risk window check)
    landings = {s: e[2] for s, k, e2 in [] for e in []}  # placeholder
    at_risk = []
    re_seqs = [(s, w) for s, k, w in [(a, b, c) for a, b, c in EVENTS] if k == "reanchor"]
    # map seq -> next 3 events
    idx = {s: i for i, (s, k, w) in enumerate(EVENTS)}
    for i, (s, k, w) in enumerate(EVENTS):
        if k != "reanchor" or w["to"] is None:
            continue
        for j in range(i + 1, min(i + 4, len(EVENTS))):
            s2, k2, w2 = EVENTS[j]
            if w2.get("patch") != w.get("patch"):
                break
            if k2 == "hp_write" and w2["key"] in allk:
                at_risk.append((w["t"], w.get("op"), w.get("key"), w2["key"], w2["new"]))
    print(f"\nG. army HP writes within 3 events after a reanchor landing: {len(at_risk)}")
    for x in at_risk[:12]:
        print("   ", x)


if __name__ == "__main__":
    main()
