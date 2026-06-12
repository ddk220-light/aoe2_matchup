"""Alignment experiments against the NOW-CORRECT production stream (multiqueue +
DB train times). Goal: map each commanded military unit to its production slot.
Scored on military-only exact, per player, vs gRPC truth."""
import sys, types, json, bisect
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer"]
from collections import defaultdict
import mgz.model, unit_classifier as uc, eval_against_truth as E

labels = json.load(open("labels.json"))
mt = mgz.model.parse_match(open("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", "rb"))
ctx = uc._run(mt)
ts_by_name = {p.name: [(e.timestamp.total_seconds(), e.total_objects) for e in p.timeseries] for p in mt.players}

def cum_spawn_curve(player):
    """time -> cumulative gross spawns (from total_objects positive increments)."""
    ts = ts_by_name[player]
    times, cum = [], []
    c = 0; prev = None
    for t, tot in ts:
        if prev is not None and tot > prev:
            c += tot - prev
        prev = tot if prev is None else max(prev, tot)
        times.append(t); cum.append(c)
    return times, cum

def units_for(player):
    u = [cid for cid, g in ctx.guesses.items() if g.player == player and g.cls == "military"
         and cid not in ctx.building_ids and cid not in ctx.gaia_all
         and str(cid) in labels and E.coarse(E.canon_truth(labels[str(cid)]["type"])) == "military"]
    return sorted(u)

def fs(cid):
    return ctx.guesses[cid].behavior.get("first_seen", 1e9)

def score(pred, player):
    u = units_for(player)
    ok = sum(E.canon_pred(pred.get(c)) == E.canon_truth(labels[str(c)]["type"]) for c in u if c in pred)
    return ok, len(u)

# -------- alignment methods --------
def m_propRank(player):
    u = units_for(player)
    M = [t for _, t in sorted(ctx.prod_mil.get(player, []))]
    N = len(u)
    return {c: M[round(i * (len(M) - 1) / (N - 1))] if (N > 1 and M) else "unit" for i, c in enumerate(u)}

def m_timeAnchor(player):
    pm = sorted(ctx.prod_mil.get(player, [])); PT = [c for c, _ in pm]; PU = [t for _, t in pm]
    out = {}
    for c in units_for(player):
        if not PU: continue
        k = max(0, min(bisect.bisect_right(PT, fs(c)) - 1, len(PU) - 1))
        out[c] = PU[k]
    return out

def m_mono_timeAnchor(player):
    """Monotonic: units in instance_id order consume production slots in order,
    each placed at the latest slot whose completion <= its first_seen."""
    u = units_for(player)
    pm = sorted(ctx.prod_mil.get(player, [])); PT = [c for c, _ in pm]; PU = [t for _, t in pm]
    out = {}; p = -1
    for c in u:
        if not PU: break
        hi = bisect.bisect_right(PT, fs(c)) - 1
        p = min(max(p + 1, 0), len(PU) - 1) if hi < p + 1 else min(hi, len(PU) - 1)
        out[c] = PU[p]
    return out

def m_id_via_count(player):
    """instance_id -> spawn time via the total_objects cumulative-spawn curve,
    then -> production slot. Sidesteps first-command lag."""
    u = units_for(player)
    if not u: return {}
    times, cum = cum_spawn_curve(player)
    # map a unit's spawn-RANK (its index among this player's spawns) to a time.
    # we approximate spawn-rank by the unit's rank within all the player's known
    # ids (start + commanded), scaled to the cumulative-spawn total.
    pm = sorted(ctx.prod_mil.get(player, [])); PT = [c for c, _ in pm]; PU = [t for _, t in pm]
    # build id->spawn-time: instance_id increases with spawn; use total cum spawns
    # to place each id proportionally between min and max id seen.
    allids = sorted(set(u) | set(ctx.start_ids))
    idmin, idmax = allids[0], allids[-1]
    total = cum[-1] if cum else 1
    out = {}
    for c in u:
        frac = (c - idmin) / max(1, (idmax - idmin))   # position in id space
        target = frac * total                           # cumulative-spawn index
        j = bisect.bisect_left(cum, target)
        st = times[min(j, len(times) - 1)] if times else fs(c)
        k = max(0, min(bisect.bisect_right(PT, st) - 1, len(PU) - 1)) if PU else 0
        out[c] = PU[k] if PU else "unit"
    return out

def m_id_interp(player):
    """Linear interpolate production-rank in instance_id space, anchoring the first
    and last commanded units' ranks via their first_seen. Robust to per-unit lag."""
    u = units_for(player)
    pm = sorted(ctx.prod_mil.get(player, [])); PT = [c for c, _ in pm]; PU = [t for _, t in pm]
    M = len(PU)
    if not u or not M:
        return {}
    r0 = max(0, min(bisect.bisect_right(PT, fs(u[0])) - 1, M - 1))
    r1 = max(0, min(bisect.bisect_right(PT, fs(u[-1])) - 1, M - 1))
    if r1 <= r0:
        r1 = M - 1
    id0, id1 = u[0], u[-1]
    out = {}
    for c in u:
        frac = (c - id0) / max(1, (id1 - id0))
        r = int(round(r0 + frac * (r1 - r0)))
        out[c] = PU[max(0, min(r, M - 1))]
    return out

def m_squad_then_interp(player):
    """Current squad-based types, but OVERRIDE ball (low type-confidence) units via
    id-interpolation to the corrected stream."""
    base = {c: ctx.guesses[c].type for c in units_for(player)}
    interp = m_id_interp(player)
    out = {}
    for c in units_for(player):
        g = ctx.guesses[c]
        # override only units typed by weak group signal (the ball)
        if g.type_conf <= uc.CONF["idrank_type"] and c in interp:
            out[c] = interp[c]
        else:
            out[c] = base[c]
    return out

def m_current(player):
    return {c: ctx.guesses[c].type for c in units_for(player)}

from collections import Counter, defaultdict
def smooth_cocmd(pred, player, thresh=0.6):
    """Co-command refinement: within each squad, if a type dominates, snap the
    minority members to it (fixes alignment noise inside a homogeneous squad)."""
    members = defaultdict(list)
    for c in pred:
        sid = ctx.guesses[c].squad_id
        if sid is not None:
            members[sid].append(c)
    out = dict(pred)
    for sid, mem in members.items():
        votes = Counter(E.canon_pred(pred[c]) for c in mem if c in pred)
        if not votes:
            continue
        dom, dn = votes.most_common(1)[0]
        if dn / sum(votes.values()) >= thresh:
            for c in mem:
                out[c] = dom
    return out

def stage2(stage1_fn):
    return lambda player: smooth_cocmd(stage1_fn(player), player)

def m_collision_anchor(player):
    """Stage1: timeAnchor by first_seen, but resolve COLLISIONS only (two units to
    the same slot) by spreading in instance_id order -- keeps timeAnchor's accuracy
    for sparse production, spreads dense production. Unified for both play styles."""
    u = units_for(player)   # instance_id order
    pm = sorted(ctx.prod_mil.get(player, [])); PT = [c for c, _ in pm]; PU = [t for _, t in pm]
    M = len(PU)
    if not u or not M:
        return {}
    out = {}; last = -1
    for c in u:
        hi = bisect.bisect_right(PT, fs(c)) - 1     # latest slot spawned-before-first-cmd
        s = hi if hi > last else last + 1            # only bump on collision/backwards
        s = max(0, min(s, M - 1))
        out[c] = PU[s]; last = s
    return out

HARD = uc.CONF["hard_class"]
def ball_members(player):
    sm = defaultdict(list)
    for cid, g in ctx.guesses.items():
        if g.squad_id is not None:
            sm[g.squad_id].append(cid)
    out = set()
    for sid, mem in sm.items():
        hm = any(ctx.guesses[m].cls == "military" and ctx.guesses[m].cls_conf >= HARD for m in mem)
        hv = any(ctx.guesses[m].cls == "villager" and ctx.guesses[m].cls_conf >= HARD for m in mem)
        if hm and hv:
            out |= set(mem)
    return out

def m_adaptive(player):
    """Dense ball -> mono spreading; separable units -> timeAnchor by first_seen."""
    ball = ball_members(player)
    ta = m_timeAnchor(player); mo = m_mono_timeAnchor(player)
    return {c: (mo.get(c, ta.get(c)) if c in ball else ta.get(c)) for c in units_for(player)}

def m_best(player):
    """timeAnchor+cocmd for SEPARABLE units (its strength); keep current's
    count-cal handling for the mass-select BALL (where cocmd/anchor fail)."""
    ball = ball_members(player)
    ta = smooth_cocmd(m_timeAnchor(player), player)
    cur = {c: ctx.guesses[c].type for c in units_for(player)}
    return {c: (cur[c] if c in ball else ta.get(c, cur[c])) for c in units_for(player)}

def m_perplayer(player):
    """Per-PLAYER switch: a player who blobs a mass-select ball -> current's
    adaptive handling; a player with separable production -> timeAnchor+cocmd."""
    if ball_members(player):
        return {c: ctx.guesses[c].type for c in units_for(player)}
    return smooth_cocmd(m_timeAnchor(player), player)

methods = [("current", m_current),
           ("timeAnchor+cocmd", stage2(m_timeAnchor)),
           ("perplayer-switch", m_perplayer)]
print(f"{'method':18}  {'munq':>14}  {'ddk220':>14}")
for name, fn in methods:
    row = []
    for player in ("munq", "ddk220"):
        ok, n = score(fn(player), player)
        row.append(f"{100*ok/n:.1f}% ({ok}/{n})" if n else "-")
    print(f"{name:18}  {row[0]:>14}  {row[1]:>14}")
