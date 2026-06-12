"""iterate.py [g0|train|both] -- fast scoring loop for the ensemble-arbiter classifier copy.

Parses each replay once and pickles the match object beside this file; later runs
load the pickle (seconds instead of ~1 min). Scores EXACTLY like
_improve/score_game.py (same canon mapping, same window) and additionally prints a
per-source attribution table: which pipeline stage made the final type decision,
and that stage's precision (overall and military-only), plus per-source confusion.
"""
import sys, types, json, os, pickle
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = r"C:\dev\aoe2\aoe2record\lab\_improve\ensemble-arbiter"
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab", WORK]
from collections import Counter, defaultdict
import unit_classifier as uc
assert uc.__file__.startswith(WORK), uc.__file__
import eval_against_truth as E

GAMES = {
    "g0": (r"C:\dev\_tmp_replay\fresh_newpatch.aoe2record",
           r"C:\dev\aoe2\aoe2record\lab\labels.json", 42.6),
    "train": (r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
              r"C:\dev\aoe2\aoe2record\lab\labels_g2.json", 44.5),
}


def get_match(key):
    pk = os.path.join(WORK, f"match_{key}.pkl")
    if os.path.exists(pk):
        with open(pk, "rb") as f:
            return pickle.load(f)
    import mgz.model
    with open(GAMES[key][0], "rb") as f:
        mt = mgz.model.parse_match(f)
    # the parsed match carries live _hashlib.HASH objects and a CodecInfo
    # (unpicklable / un-unpicklable); the classifier never reads them ->
    # stringify so the match pickles.
    for obj in (mt, getattr(mt, "file", None)):
        h = getattr(obj, "hash", None)
        if h is not None and hasattr(h, "hexdigest"):
            obj.hash = h.hexdigest()
    f_ = getattr(mt, "file", None)
    if f_ is not None and getattr(f_, "encoding", None) is not None:
        f_.encoding = getattr(f_.encoding, "name", str(f_.encoding))
    try:
        with open(pk, "wb") as f:
            pickle.dump(mt, f)
        print(f"[pickled {key}]")
    except Exception as e:
        print(f"[pickle of {key} FAILED: {e}]")
    return mt


def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")


def score(key, verbose=True):
    replay, labels_path, end_min = GAMES[key]
    labels = json.load(open(labels_path))
    mt = get_match(key)
    ctx = uc._run(mt)
    # rebuild the flat map exactly like build_type_map
    tm = {}
    src = {}
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.gaia_all:
            continue
        t = g.type if g.type not in uc.GENERIC_TYPES else ("villager" if g.cls == "villager" else "unit")
        tm[cid] = t
        src[cid] = getattr(g, "type_src", "none")

    CUT = (end_min - 5) * 60000
    truth_units = {int(k): u for k, u in labels.items()
                   if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}
    overlap = [k for k in truth_units if k in tm]
    cov = 100 * len(overlap) / max(len(truth_units), 1)

    res = {"coverage": cov}
    for label, milonly in (("overall", False), ("military", True)):
        tot = ok = 0
        for k in overlap:
            t = E.canon_truth(truth_units[k]["type"])
            if E.coarse(t) != "military" and milonly:
                continue
            p = E.canon_pred(tm[k])
            tot += 1
            ok += (p == t)
        res[label] = 100 * ok / max(tot, 1)
        res[label + "_n"] = (ok, tot)

    print(f"== {key}: coverage={cov:.1f} overall={res['overall']:.1f} "
          f"({res['overall_n'][0]}/{res['overall_n'][1]}) "
          f"military={res['military']:.1f} ({res['military_n'][0]}/{res['military_n'][1]})")

    if verbose:
        # per-source attribution (overall + military-only) and confusion
        stat = defaultdict(lambda: [0, 0, 0, 0])  # src -> [ok_all, n_all, ok_mil, n_mil]
        conf = defaultdict(Counter)               # src -> Counter[(truth,pred)]
        err_ids = defaultdict(list)
        for k in overlap:
            t = E.canon_truth(truth_units[k]["type"])
            p = E.canon_pred(tm[k])
            s = src[k]
            ismil = E.coarse(t) == "military"
            stat[s][1] += 1
            stat[s][0] += (p == t)
            if ismil:
                stat[s][3] += 1
                stat[s][2] += (p == t)
            if p != t:
                conf[s][(t, p)] += 1
                err_ids[(t, p)].append((k, s))
        print(f"   {'source':16}{'all':>10}{'mil':>10}   top confusions (truth->pred)")
        for s in sorted(stat, key=lambda s: -stat[s][1]):
            a, n, am, nm = stat[s]
            top = ", ".join(f"{t}->{p} x{c}" for (t, p), c in conf[s].most_common(4))
            print(f"   {s:16}{a:>4}/{n:<5}{am:>4}/{nm:<5}   {top}")
        print("   -- military errors by (truth->pred): id list --")
        for (t, p), ids in sorted(err_ids.items(), key=lambda kv: -len(kv[1])):
            if E.coarse(t) == "military" or p != "villager":
                print(f"     {t}->{p} x{len(ids)}: {ids[:8]}")
        # overwrite-flow analysis: for every unit with a multi-write history, did
        # the LAST write fix a wrong earlier type, break a right one, or neither?
        flow = Counter()
        broke = []
        for k in overlap:
            g = ctx.guesses.get(k)
            if g is None or len(g.type_hist) < 2:
                continue
            t = E.canon_truth(truth_units[k]["type"])
            (s0, t0), (s1, t1) = g.type_hist[-2], g.type_hist[-1]
            ok0 = E.canon_pred(t0) == t
            ok1 = E.canon_pred(t1) == t
            kind = "fix" if (ok1 and not ok0) else ("break" if (ok0 and not ok1) else "same")
            flow[(s0, s1, kind)] += 1
            if kind == "break":
                broke.append((k, s0, t0, s1, t1, t))
        print("   -- overwrite flow (prev_src -> last_src: fix/break/same) --")
        for (s0, s1, kind), c in sorted(flow.items()):
            print(f"     {s0:13}->{s1:13} {kind:5} x{c}")
        for b in broke:
            print(f"       BROKE id={b[0]} {b[1]}:{b[2]} -> {b[3]}:{b[4]}  truth={b[5]}")
    return res, ctx, tm, truth_units


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    keys = ["g0", "train"] if which == "both" else [which]
    out = {}
    for k in keys:
        out[k], _, _, _ = score(k)
    line = "  ".join(f"{k}: mil={out[k]['military']:.1f} ovr={out[k]['overall']:.1f}" for k in keys)
    print("SUMMARY " + line)
