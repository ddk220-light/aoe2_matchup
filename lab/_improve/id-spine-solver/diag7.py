"""diag7.py [g0|train] -- validate the ub (id-spine spawn upper bound) against truth
created_ms, per reference-source variant. Counts ub < created violations (bad: an id
referenced before this unit spawned, with a LARGER id) and their magnitude.
"""
import sys, types, json, os
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab"]
sys.path.insert(0, WORK)
from collections import Counter
import unit_classifier as uc
assert uc.__file__.startswith(WORK)
import eval_against_truth as E
import mgz.model
import bisect

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
           "C:/dev/aoe2/aoe2record/lab/labels.json", 42.6),
    "train": ("C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/AgeIIDE_Replay_482723861.aoe2record",
              "C:/dev/aoe2/aoe2record/lab/labels_g2.json", 44.5),
}
key = sys.argv[1] if len(sys.argv) > 1 else "g0"
replay, labels_path, end_min = GAMES[key]
labels = json.load(open(labels_path))
mt = mgz.model.parse_match(open(replay, "rb"))

ctx = uc.build_context(mt)
uc.behavioral_labels(ctx)

# truth created (sec) for every labelled id (any type, incl buildings)
created = {}
for k, u in labels.items():
    c = u.get("created_ms")
    if c is not None:
        created[int(k)] = c / 1000.0

def build_refs(use_fs=True, use_queues=True, use_targets=True):
    refs = {}
    def note(cid, t):
        if 0 < cid < uc.SHIFT_THRESHOLD and (cid not in refs or t < refs[cid]):
            refs[cid] = t
    if use_fs:
        for cid, g in ctx.guesses.items():
            fs = g.behavior.get("first_seen")
            if fs is not None:
                note(cid, fs)
    if use_queues:
        for b, q in ctx.queues.items():
            if q:
                note(b, min(t for t, _ in q))
    if use_targets:
        for a in ctx.match.actions:
            if not a.player:
                continue
            p = a.payload or {}
            t = a.timestamp.total_seconds()
            tgt = p.get("target_id")
            if isinstance(tgt, int):
                note(ctx.canon(tgt), t)
    items = sorted(refs.items())
    ids = [i for i, _ in items]
    ubs = [t for _, t in items]
    for k2 in range(len(ubs) - 2, -1, -1):
        if ubs[k2 + 1] < ubs[k2]:
            ubs[k2] = ubs[k2 + 1]
    return refs, ids, ubs

for name, kw in (("fs+q+tgt", {}), ("fs+q", {"use_targets": False}), ("fs only", {"use_queues": False, "use_targets": False})):
    refs, ids, ubs = build_refs(**kw)
    def ub_of(cid):
        k2 = bisect.bisect_left(ids, cid)
        return ubs[k2] if k2 < len(ids) else float("inf")
    viol = []
    for cid, cr in created.items():
        u = ub_of(cid)
        if u < cr - 2.0:    # allow 2s timestamp slop
            viol.append((cr - u, cid, cr, u))
    viol.sort(reverse=True)
    mags = [v[0] for v in viol]
    print(f"[{key}] variant={name:9} ids-with-ref={len(ids):6}  truthed={len(created):5}  "
          f"viol(ub<created-2s)={len(viol):4}  mags: max={mags[0] if mags else 0:.0f} "
          f"p50={mags[len(mags)//2] if mags else 0:.0f}")
    # who drags the bound down? find the culprit ref for the worst violations
    for mag, cid, cr, u in viol[:6]:
        # culprit = the smallest id >= cid with refs == ub
        k2 = bisect.bisect_left(ids, cid)
        culprit = None
        for kk in range(k2, len(ids)):
            if refs[ids[kk]] == u:
                culprit = ids[kk]
                break
        print(f"    id={cid:7} created={cr:7.1f} ub={u:7.1f} (-{mag:.0f}s)  culprit_id={culprit} "
              f"culprit_truth={labels.get(str(culprit),{}).get('type')}")
