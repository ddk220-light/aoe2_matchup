"""_wf_review_hpdetail.py - classify the 100 HP increases seen on army units.

Distinguishes:
  (a) genuine regen in the stream: increases occur in patches with NO reanchor
      before them, exact small steps, regular cadence, consistent per side;
  (b) mis-anchor garbage: increases concentrated right after reanchor landings,
      irregular values.

Also reruns the same instrumentation against the PRE-FIX decoder backup: if the
same increases (same unit, time, value) appear there too, they are stream data,
not artifacts of the new re-anchor logic.
ASCII output only.
"""
import contextlib
import importlib.util
import io
import os
import struct
import sys

D_DIR = r"C:\dev\aoe2\aoe2record\lab"
sys.path.insert(0, D_DIR)
import cade_api_pb2 as pb  # noqa: E402

GT = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
      "\\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs)")
TMP = os.path.join(D_DIR, "_wf_review_hpdetail.reseed.bin")
F_MASTER, F_OWNER, F_HP = 1, 2, 12
ARMY_MT = {9, 11, 12}
SCOUT = 448


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


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


def run_decoder(mod, tag):
    """Decode GT with module `mod`; log all army HP writes + per-patch reanchor flag."""
    events = []          # (patch_idx, t, key, old, new, reanchored_before_in_patch)
    state = {"pi": -1, "t": None, "re_in_patch": 0}

    class LogEnt(dict):
        __slots__ = ("ekey",)

        def __init__(self, ekey, base):
            super().__init__(base)
            self.ekey = ekey

        def __setitem__(self, f, v):
            if f == F_HP and self.ekey in ALLK:
                events.append((state["pi"], state["t"], self.ekey,
                               self.get(f), v, state["re_in_patch"]))
            super().__setitem__(f, v)

    class LogStore(dict):
        def __setitem__(self, k, v):
            if not isinstance(v, LogEnt):
                v = LogEnt(k, v)
            super().__setitem__(k, v)

    has_marker = hasattr(mod, "_next_delta_marker")
    if has_marker:
        orig = mod._next_delta_marker

        def wrap(data, pos, kk):
            state["re_in_patch"] += 1
            return orig(data, pos, kk)
        mod._next_delta_marker = wrap

    doc = es = world_id = None
    ALLK = set()
    army = None
    seed_hp = {}
    for t, p in read_frames(GT + ".frames.bin"):
        state["t"] = round(t, 2)
        if p is not None and len(p) > 400_000:
            with open(TMP, "wb") as sf:
                sf.write(p)
            doc, es0 = mod.Doc(), {}
            with contextlib.redirect_stdout(io.StringIO()):
                _, world_id = mod.seed_from_snapshot(TMP, doc, es0)
            a = derive_army(es0)
            if (len(a[2]), len(a[3])) == (24, 30):
                army = a
                ALLK.clear()
                ALLK.update(a[2] | a[3])
                seed_hp = {k: es0[k].get(F_HP) for k in ALLK}
                es = LogStore()
                for k, v in es0.items():
                    es[k] = v
                events.clear()
            continue
        if es is None or p is None:
            continue
        state["pi"] += 1
        state["re_in_patch"] = 0
        mod.apply_patch(doc, p, es, world_id)
    if has_marker:
        mod._next_delta_marker = orig
    return events, army, seed_hp


def analyze(tag, events, army, seed_hp):
    print(f"\n==== {tag} ====  total army hp writes: {len(events)}")
    last = dict(seed_hp)
    incs = []
    for pi, t, k, old, new, re_flag in events:
        prev = last.get(k)
        if (isinstance(new, (int, float)) and isinstance(prev, (int, float))
                and new > prev + 1e-6):
            incs.append((pi, t, k, prev, new, re_flag))
        if isinstance(new, (int, float)):
            last[k] = new
    n_tainted = sum(1 for x in incs if x[5] > 0)
    side = lambda k: 1 if k in army[2] else 2
    by_side = {1: 0, 2: 0}
    steps = {}
    for x in incs:
        by_side[side(x[2])] += 1
        st = round(x[4] - x[3], 3)
        steps[st] = steps.get(st, 0) + 1
    print(f"increases={len(incs)}  in_patches_with_a_reanchor_before={n_tainted}  "
          f"by_side={by_side}")
    print(f"step-size histogram: {dict(sorted(steps.items()))}")
    ts = sorted({x[1] for x in incs})
    print(f"distinct increase times ({len(ts)}): {ts[:30]}")
    # full timeline for the two most-increasing units
    cnt = {}
    for x in incs:
        cnt[x[2]] = cnt.get(x[2], 0) + 1
    worst = sorted(cnt, key=cnt.get, reverse=True)[:2]
    for k in worst:
        tl = [(t, new) for pi, t, kk, old, new, rf in events if kk == k]
        print(f"unit {k} (side{side(k)}, seed_hp={seed_hp.get(k)}, "
              f"{cnt[k]} increases) timeline:")
        print("   " + " ".join(f"({t},{v})" for t, v in tl))
    return incs


def main():
    new_mod = load_module("dec_new", os.path.join(D_DIR, "decode_state_v2.py"))
    old_mod = load_module("dec_old", os.path.join(D_DIR, "decode_state_v2.pre_fix.bak.py"))
    ev_new, army_n, hp_n = run_decoder(new_mod, "new")
    incs_new = analyze("FIXED decoder", ev_new, army_n, hp_n)
    ev_old, army_o, hp_o = run_decoder(old_mod, "old")
    incs_old = analyze("PRE-FIX decoder", ev_old, army_o, hp_o)
    set_new = {(x[1], x[2], x[4]) for x in incs_new}
    set_old = {(x[1], x[2], x[4]) for x in incs_old}
    print(f"\nincrease events (t,key,val) shared new&old: {len(set_new & set_old)}  "
          f"only_new: {len(set_new - set_old)}  only_old: {len(set_old - set_new)}")
    only_new = sorted(set_new - set_old)[:15]
    print("only_new samples:", only_new)


if __name__ == "__main__":
    main()
