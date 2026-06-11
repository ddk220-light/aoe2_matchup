"""Measure the true-ambiguity floor for the proposed id-spine algorithm on a game.
Categorize each commanded unit (that has gRPC truth) into:
  A hard  : has a hard villager (build/repair/wall) or hard military (patrol/stance/
            formation/attack-ground/attack-move/guard) signal -> pinned by its own command
  B cocmd : soft, but co-commanded with >=5 distinct CONFIDENT(=hard) units of one class
  C forced: soft, no co-consensus, but its id-interval between nearest confident neighbors
            is class-homogeneous -> the monotonic spine forces the class (no guess)
  D guess : soft, no co-consensus, id-interval STRADDLES vil<->mil -> a genuine guess
Reports counts/% per player and whether A/B/C agree with truth (so we know the ceiling).
"""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer", "C:/dev/aoe2/aoe2record/lab"]
from collections import defaultdict, Counter
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

REPLAY = "C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/AgeIIDE_Replay_482723861.aoe2record"
LABELS = "labels_g2.json"
labels = json.load(open(LABELS))
mt = mgz.model.parse_match(open(REPLAY, "rb"))

ctx = uc.build_context(mt)
uc.behavioral_labels(ctx)
uc.production_timeline(ctx)

# truth class per canonical id
truth = {}
for k, u in labels.items():
    c = E.coarse(E.canon_truth(u.get("type")))
    if c in ("villager", "military"):
        truth[int(k)] = c

# co-command adjacency (exclude buildings)
co_events = defaultdict(list)   # unit -> list of group sets it appeared in
for _pl, ids in ctx.group_cmds:
    grp = [i for i in ids if i not in ctx.building_ids]
    if 2 <= len(grp) <= 60:
        for i in grp:
            co_events[i].append(set(grp))

X, Y = 5, 5   # co-command thresholds


def hard_class(g):
    if g.behavior.get("hard_build"):
        return "villager"
    if g.behavior.get("hard_mil"):
        return "military"
    return None


for player in [p.name for p in mt.players]:
    units = []
    for cid, g in ctx.guesses.items():
        if g.player != player:
            continue
        if cid in ctx.building_ids or cid in ctx.gaia_all or cid in ctx.start_ids:
            continue
        if g.behavior.get("first_seen") is None:
            continue
        if cid not in truth:
            continue
        units.append(cid)
    units.sort()
    if not units:
        continue
    hc = {cid: hard_class(ctx.guesses[cid]) for cid in units}
    # B: co-command resolvable
    cocmd = {}
    for cid in units:
        if hc[cid]:
            continue
        hard_neighbors = Counter()
        n_events = 0
        for grp in co_events.get(cid, []):
            hn = {j for j in grp if j != cid and hc.get(j)}
            if hn:
                n_events += 1
                for j in hn:
                    hard_neighbors[hc[j]] += 1
        distinct = sum(1 for grp in [] for _ in grp)  # placeholder
        # distinct confident neighbors of the dominant class
        neigh_units = defaultdict(set)
        for grp in co_events.get(cid, []):
            for j in grp:
                if j != cid and hc.get(j):
                    neigh_units[hc[j]].add(j)
        best = max(neigh_units, key=lambda c: len(neigh_units[c])) if neigh_units else None
        if best and len(neigh_units[best]) >= Y and n_events >= X:
            cocmd[cid] = best
    import bisect
    # produced SLOT sequence (spawn order): class per slot
    slots = [("villager" if t == "villager" else "military")
             for _tm, t in sorted(ctx.prod_full.get(player, []))]
    # ORACLE monotonic bind: each commanded unit (id-order) -> earliest unclaimed slot
    # of its TRUE class, with strictly increasing slot index (the id-spine).
    claimed = [False] * len(slots)
    slot_of = {}
    last = -1
    for cid in units:
        tc = truth[cid]
        j = last + 1
        while j < len(slots) and (claimed[j] or slots[j] != tc):
            j += 1
        if j < len(slots):
            claimed[j] = True
            slot_of[cid] = j
            last = j
    # confident anchors = hard or cocmd (slots known via oracle)
    confident = {cid for cid in units if hc[cid] or cid in cocmd}
    anchor_ids = sorted(c for c in confident if c in slot_of)
    cat = {}
    for cid in units:
        if hc[cid]:
            cat[cid] = ("A_hard", hc[cid]); continue
        if cid in cocmd:
            cat[cid] = ("B_cocmd", cocmd[cid]); continue
        # window between nearest confident anchors' SLOTS
        p = bisect.bisect_left(anchor_ids, cid)
        lo = anchor_ids[p - 1] if p > 0 else None
        hi = anchor_ids[p] if p < len(anchor_ids) else None
        s_lo = slot_of[lo] if lo is not None else -1
        s_hi = slot_of[hi] if hi is not None else len(slots)
        window = set(slots[s_lo + 1:s_hi])
        if len(window) == 1:                       # slot range is class-homogeneous
            cat[cid] = ("C_forced", next(iter(window)))
        else:                                       # straddles vil<->mil -> true guess
            cat[cid] = ("D_guess", None)
    # report
    n = len(units)
    cnt = Counter(c for c, _ in cat.values())
    print(f"\n=== {player}  ({n} commanded units with truth) ===")
    for key in ("A_hard", "B_cocmd", "C_forced", "D_guess"):
        c = cnt.get(key, 0)
        # accuracy: for A/B/C, does the assigned class match truth?
        if key != "D_guess":
            ok = sum(1 for cid, (k, cls) in cat.items() if k == key and cls == truth[cid])
            print(f"   {key:9} {c:4} ({100*c/n:4.1f}%)   class matches truth: {ok}/{c}")
        else:
            comp = Counter(truth[cid] for cid, (k, _) in cat.items() if k == key)
            print(f"   {key:9} {c:4} ({100*c/n:4.1f}%)   truth: {dict(comp)}   <-- TRUE GUESS FLOOR")
