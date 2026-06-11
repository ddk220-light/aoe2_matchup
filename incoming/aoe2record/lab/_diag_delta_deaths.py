"""_diag_delta_deaths.py — diagnose WHERE army state changes land in a recorded stream:
delta frames vs full snapshots. Answers, against the Guecha-vs-Jaguar ground truth:
  1. how often full snapshots arrive in the fight segment,
  2. whether army-entity HP changes decode from DELTA frames between snapshots,
  3. whether a retrospective 'death = last delta HP change' rule reproduces the
     footage-OCR death curve (the fix candidate that needs NO decoder RE work).
"""
import struct
import sys

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D          # noqa: E402
import cade_api_pb2 as pb            # noqa: E402

PFX = sys.argv[1]
F_MASTER, F_OWNER, F_HP = 1, 2, 12
TMP = PFX + ".diag_reseed.bin"

# footage-OCR ground truth (video-anchored game seconds, side1 = Guecha)
OCR_S1 = [(0.5, 24), (6.5, 21), (7.5, 18), (8.5, 17), (9.5, 14), (10.5, 11),
          (11.5, 10), (12.5, 8), (13.5, 5), (15.5, 2), (16.5, 0)]

doc = es = army = world_id = None
fight = False
snap_times = []
hp_events = {}        # key -> list of (game_s, old_hp, new_hp) from DELTA frames
snap_alive = []       # (game_s, set(alive keys)) at each snapshot
last_sec = None


def derive_army(entities):
    a = {2: set(), 3: set()}
    for k, e in entities.items():
        if (e.get("__type__") in (9, 11, 12) and e.get(F_OWNER) in (2, 3)
                and e.get(F_MASTER) != 448
                and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
            a[e.get(F_OWNER)].add(k)
    return a


def alive_now():
    out = set()
    for o in (2, 3):
        for k in army[o]:
            e = es.get(k)
            v = e.get(F_HP) if e else None
            if isinstance(v, (int, float)) and v > 0:
                out.add(k)
    return out


with open(PFX + ".frames.bin", "rb") as f:
    while True:
        hdr = f.read(4)
        if len(hdr) < 4:
            break
        ln = struct.unpack("<I", hdr)[0]
        buf = f.read(ln)
        if len(buf) < ln:
            break
        sq = pb.FrameSequence()
        sq.ParseFromString(buf)
        for fr in sq.frame:
            p = fr.patch
            t = fr.time / 1000.0
            if p and len(p) > 400_000:
                with open(TMP, "wb") as sf:
                    sf.write(p)
                doc = D.Doc()
                es2 = {}
                _, world_id = D.seed_from_snapshot(TMP, doc, es2)
                es = es2
                a = derive_army(es)
                if len(a[2]) == 24 and len(a[3]) == 30:    # the fight instance
                    if not fight:
                        fight = True
                        army = a
                if fight:
                    snap_times.append(round(t, 2))
                    snap_alive.append((round(t, 2), alive_now()))
                continue
            if not fight or es is None:
                continue
            if last_sec is not None and t < last_sec - 2:
                continue
            last_sec = t
            if p:
                allk = army[2] | army[3]
                pre = {k: (es.get(k) or {}).get(F_HP) for k in allk}
                D.apply_patch(doc, p, es, world_id)
                for k in allk:
                    post = (es.get(k) or {}).get(F_HP)
                    if post != pre[k]:
                        hp_events.setdefault(k, []).append((round(t, 2), pre[k], post))

print(f"fight snapshots at game_s: {snap_times}")
n_units_with_delta = sum(1 for k, v in hp_events.items() if v)
n_delta_events = sum(len(v) for v in hp_events.values())
print(f"army units with DELTA hp changes: {n_units_with_delta}/54   "
      f"total delta hp events: {n_delta_events}")

# distribution of delta hp events over time
from collections import Counter
hist = Counter()
for v in hp_events.values():
    for (t, a, b) in v:
        hist[int(t)] += 1
print("delta hp-events per game-second:", dict(sorted(hist.items())))

# retrospective death rule: dead at END OF STREAM (entity_store authority; the fight
# segment may contain only ONE snapshot, at t=0) -> death time = last delta hp change
if army is not None:
    final_alive = alive_now()
    deaths = []
    for k in (army[2] | army[3]):
        if k in final_alive:
            continue
        ev = hp_events.get(k)
        side = 1 if k in army[2] else 2
        deaths.append((round(ev[-1][0], 2) if ev else None, side))
    timed = sorted(t for t, s in deaths if t is not None and s == 1)
    print(f"side1 deaths: {len([d for d in deaths if d[1] == 1])} "
          f"(with delta-timed: {len(timed)})")
    print("side1 retrospective death times:", timed)
    # reconstruct side1 count curve and compare to OCR ground truth
    start1 = len(army[2])
    print("OCR ground truth (game_s, side1count):", OCR_S1)
    curve = [(t, start1 - i - 1) for i, t in enumerate(timed)]
    print("delta-rule curve  (game_s, side1count):", curve)
