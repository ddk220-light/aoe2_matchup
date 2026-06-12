"""Experiment harness: try multiple exact-military-type strategies fueled by the
production queue + total_objects ticks, scored against gRPC ground truth.

Goal: maximize exact military type. We measure ONLY on units the classifier
correctly classed military (so this isolates type-alignment quality), per player.
munq = complete truth (trustworthy); ddk220 = partial.
"""
import sys, types, json, bisect
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer"]
from collections import Counter, defaultdict
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

REPLAY = "C:/dev/_tmp_replay/fresh_newpatch.aoe2record"
labels = json.load(open("labels.json"))
mt = mgz.model.parse_match(open(REPLAY, "rb"))
ctx = uc._run(mt)
weight = uc.cocommand_graph(ctx)
squads = uc.form_squads(ctx, weight)
squad_of = {cid: sid for sid, c in enumerate(squads) for cid in c}
pname = {1: "munq", 2: "ddk220"}
players_ts = {p.number: p.timeseries for p in mt.players}

# ---------- production stream per player (per-building serial completion) -------
def prod_stream(train_scale=1.0, train_times=None):
    tt = train_times or uc.TRAIN_TIMES
    streams = defaultdict(list)   # player -> [(completion_time, type)]
    for b, q in ctx.queues.items():
        player = ctx.owner.get(b)
        done = 0.0
        for ts, u in sorted(q):
            done = max(ts, done) + tt.get(u, 30) * train_scale
            streams[player].append((done, u))
    for pl in streams:
        streams[pl].sort()
    return streams

# ---------- which units to score: truth-military, classed military -------------
def scoring_units(owner):
    out = []
    for cid, g in ctx.guesses.items():
        if g.player != pname[owner]:
            continue
        if cid in ctx.building_ids or cid in ctx.gaia_all:
            continue
        if str(cid) not in labels:
            continue
        t = E.canon_truth(labels[str(cid)]["type"])
        if E.coarse(t) != "military":
            continue
        if g.cls != "military":
            continue
        out.append(cid)
    return sorted(out)

def first_seen(cid):
    return ctx.guesses[cid].behavior.get("first_seen", 1e9)

def score(pred, owner):
    units = scoring_units(owner)
    units = [c for c in units if c in pred]
    if not units:
        return (0, 0)
    ok = sum(E.canon_pred(pred[c]) == E.canon_truth(labels[str(c)]["type"]) for c in units)
    return ok, len(units)

# ============================ STRATEGIES =====================================
def strat_current():
    return {cid: g.type for cid, g in ctx.guesses.items()}

def strat_propRank(streams):
    pred = {}
    for owner in (1, 2):
        units = sorted(cid for cid, g in ctx.guesses.items()
                       if g.player == pname[owner] and g.cls == "military"
                       and cid not in ctx.building_ids and cid not in ctx.gaia_all)
        M = [t for _, t in streams.get(pname[owner], []) if t != "villager"]
        N = len(units)
        for i, cid in enumerate(units):
            pred[cid] = M[round(i * (len(M) - 1) / (N - 1))] if (N > 1 and M) else "unit"
    return pred

def strat_timeAnchor(streams, src="train"):
    """Each unit -> production type whose completion time is just <= unit first_seen."""
    pred = {}
    for owner in (1, 2):
        units = sorted((cid for cid, g in ctx.guesses.items()
                        if g.player == pname[owner] and g.cls == "military"
                        and cid not in ctx.building_ids and cid not in ctx.gaia_all),
                       key=first_seen)
        mil = [(ct, t) for ct, t in streams.get(pname[owner], []) if t != "villager"]
        PT = [ct for ct, _ in mil]; MT = [t for _, t in mil]
        for cid in units:
            fs = first_seen(cid)
            k = bisect.bisect_right(PT, fs) - 1
            k = max(0, min(k, len(MT) - 1)) if MT else 0
            pred[cid] = MT[k] if MT else "unit"
    return pred

def strat_rank_by_id(streams):
    """Map each unit to the military production stream by its instance_id rank among
    the player's commanded military (uses spawn-order == id order)."""
    return strat_propRank(streams)   # same family; kept for clarity

def strat_squad_homog(base):
    """Refinement: pure-ish squads vote a single type (majority of base preds),
    but hard-class & solo units keep their base pred."""
    pred = dict(base)
    members = defaultdict(list)
    for cid in base:
        if cid in squad_of:
            members[squad_of[cid]].append(cid)
    for sid, mem in members.items():
        votes = Counter(E.canon_pred(base[c]) for c in mem if c in base)
        if not votes:
            continue
        dom, dn = votes.most_common(1)[0]
        # only homogenize if squad is reasonably pure (avoid mixed-ball squads)
        if dn / sum(votes.values()) >= 0.7:
            for c in mem:
                pred[c] = dom
    return pred

# ---------------- total_objects-calibrated completion times -------------------
def calibrated_stream(owner):
    """Use total_objects increments to time military completions.
    Build the military queue (per building serial ORDER preserved), then assign
    each military completion to successive net-positive ticks of total_objects so
    completion times track the REAL object-count growth instead of guessed train
    times. Order within the merged stream still follows per-building queue order
    merged by queue time."""
    # merged military queue events in queue-time order, per building serial
    events = []  # (queue_time, building_serial_index, type)
    for b, q in ctx.queues.items():
        if ctx.owner.get(b) != pname[owner]:
            continue
        for j, (ts, u) in enumerate(sorted(q)):
            if u != "villager":
                events.append((ts, u))
    events.sort()
    # net-positive tick times (spawn windows) from total_objects
    ts = players_ts[owner]
    incs = []
    prev = None
    for e in ts:
        if prev is not None and e.total_objects > prev:
            for _ in range(e.total_objects - prev):
                incs.append(e.timestamp.total_seconds())
        prev = e.total_objects
    # assign each military event a completion time = next available increment >= queue_time
    stream = []
    ii = 0
    for qt, u in events:
        while ii < len(incs) and incs[ii] < qt:
            ii += 1
        ct = incs[ii] if ii < len(incs) else qt + 30
        stream.append((ct, u))
        ii += 1
    stream.sort()
    return stream

def streams_calibrated():
    return {pname[o]: calibrated_stream(o) for o in (1, 2)}

# ---- BUILD timestamps per player (for isolating military from the count curve) ----
build_times = defaultdict(list)
for a in mt.actions:
    if a.player and str(a.type).replace("Action.", "") == "BUILD":
        build_times[a.player.name].append(a.timestamp.total_seconds())
for pl in build_times:
    build_times[pl].sort()

def calibrated_stream_v2(owner):
    """Isolate the MILITARY spawn timeline: military_count(t) = total_objects(t)
    - villagers_produced(t) - buildings_built(t) - starting. Its positive deltas
    are military spawns; assign the queue's military events (in order) to them."""
    player = pname[owner]
    ts = players_ts[owner]
    # villager completion times (serial per building)
    vil_ev = []
    for b, q in ctx.queues.items():
        if ctx.owner.get(b) != player:
            continue
        done = 0.0
        for t, u in sorted(q):
            done = max(t, done) + (25 if u == "villager" else uc.TRAIN_TIMES.get(u, 30))
            if u == "villager":
                vil_ev.append(done)
    vil_ev.sort()
    bld_ev = build_times.get(player, [])
    start_nonmil = ts[0].total_objects                # baseline at first tick
    mil_events = []
    prev = 0
    for e in ts:
        t = e.timestamp.total_seconds()
        nv = bisect.bisect_right(vil_ev, t)
        nb = bisect.bisect_right(bld_ev, t)
        milc = e.total_objects - start_nonmil - nv - nb
        if milc > prev:
            for _ in range(milc - prev):
                mil_events.append(t)
        prev = max(prev, milc)
    # military queue events in queue order
    mq = sorted((t, u) for b, q in ctx.queues.items() if ctx.owner.get(b) == player
                for t, u in q if u != "villager")
    stream = []
    for i, (qt, u) in enumerate(mq):
        ct = mil_events[i] if i < len(mil_events) else qt + 30
        stream.append((ct, u))
    stream.sort()
    return stream

def streams_calibrated_v2():
    return {pname[o]: calibrated_stream_v2(o) for o in (1, 2)}

def calibrated_stream_v3(owner):
    """Time EVERY produced unit (villagers + military) by assigning all queue
    events, in queue order, to successive total_objects increments. Villagers
    consume villager increments, leaving correctly-timed slots for military.
    Returns the MILITARY subset with calibrated completion times."""
    player = pname[owner]
    ts = players_ts[owner]
    incs = []
    prev = None
    for e in ts:
        if prev is not None and e.total_objects > prev:
            incs += [e.timestamp.total_seconds()] * (e.total_objects - prev)
        prev = e.total_objects if prev is None else max(prev, e.total_objects)
    # ALL queue events in queue-time order (villagers + military)
    allq = sorted((t, u) for b, q in ctx.queues.items() if ctx.owner.get(b) == player
                  for t, u in q)
    stream = []
    ii = 0
    for qt, u in allq:
        while ii < len(incs) and incs[ii] < qt:
            ii += 1
        ct = incs[ii] if ii < len(incs) else qt + 30
        ii += 1
        if u != "villager":
            stream.append((ct, u))
    stream.sort()
    return stream

def streams_calibrated_v3():
    return {pname[o]: calibrated_stream_v3(o) for o in (1, 2)}

# ============================ RUN ============================================
streams_tm = prod_stream()
strategies = {
    "current": strat_current(),
    "propRank(train)": strat_propRank(streams_tm),
    "timeAnchor(train)": strat_timeAnchor(streams_tm),
    "timeAnchor(countcal)": strat_timeAnchor(streams_calibrated()),
    "propRank(countcal)": strat_propRank(streams_calibrated()),
}
# military-isolated count calibration
sc2 = streams_calibrated_v2()
strategies["timeAnchor(milcal)"] = strat_timeAnchor(sc2)
sc3 = streams_calibrated_v3()
strategies["timeAnchor(v3full)"] = strat_timeAnchor(sc3)
strategies["propRank(v3full)"] = strat_propRank(sc3)
strategies["timeAnchor(v3full)+squadHomog"] = strat_squad_homog(strat_timeAnchor(sc3))
# add a refined version of the best base
strategies["timeAnchor(countcal)+squadHomog"] = strat_squad_homog(strategies["timeAnchor(countcal)"])
strategies["current+squadHomog"] = strat_squad_homog(strategies["current"])

print(f"{'strategy':34}  {'munq(complete)':>16}  {'ddk220(partial)':>16}")
for name, pred in strategies.items():
    a1 = score(pred, 1); a2 = score(pred, 2)
    s1 = f"{100*a1[0]/a1[1]:.1f}% ({a1[0]}/{a1[1]})" if a1[1] else "-"
    s2 = f"{100*a2[0]/a2[1]:.1f}% ({a2[0]}/{a2[1]})" if a2[1] else "-"
    print(f"{name:34}  {s1:>16}  {s2:>16}")

# ============ COMBINED pipeline: current class + count-anchored military type =====
def combined():
    mil = strat_squad_homog(strat_timeAnchor(streams_calibrated()))
    out = {}
    for cid, g in ctx.guesses.items():
        if g.cls == "military" and cid in mil:
            out[cid] = mil[cid]
        else:
            out[cid] = g.type
    return out

def score_overall(pred, owner):
    """Exact over ALL truth units (villagers + military) that are classed & emitted."""
    units = []
    for cid, g in ctx.guesses.items():
        if g.player != pname[owner] or cid in ctx.building_ids or cid in ctx.gaia_all:
            continue
        if str(cid) not in labels:
            continue
        t = E.canon_truth(labels[str(cid)]["type"])
        if E.coarse(t) not in ("villager", "military"):
            continue
        units.append(cid)
    ok = sum(E.canon_pred(pred.get(c, "unit")) == E.canon_truth(labels[str(c)]["type"]) for c in units)
    cc = sum(E.coarse(pred.get(c, "unit")) == E.coarse(E.canon_truth(labels[str(c)]["type"])) for c in units)
    return ok, cc, len(units)

print("\n=== OVERALL exact (villagers+military), best combined pipeline ===")
comb = combined()
cur = strat_current()
for label_, pred in (("current", cur), ("combined(count-anchored mil)", comb)):
    for owner in (1, 2):
        ok, cc, n = score_overall(pred, owner)
        print(f"  {label_:30} {pname[owner]:7}: exact {100*ok/n:.1f}%  vil/mil {100*cc/n:.1f}%  ({n} units)")
