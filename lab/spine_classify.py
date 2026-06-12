"""spine_classify.py -- the id-spine classifier core.

Per player:
  1. Build the produced-slot sequence (spawn order) with class + type (from production).
  2. Resolve each commanded unit's CLASS iteratively:
       - hard signals (build/repair/wall = vil; patrol/stance/etc = mil)
       - spine-forcing (a unit whose slot-window between confident id-neighbors is
         class-homogeneous is forced to that class)
       - co-command (>=5 distinct confident neighbors of one class) -- gather-leaning
         units need a higher bar (10) to flip to military
     ...iterated, so newly-resolved units become anchors for the next pass.
  3. Guess the residual (gather -> villager; else slot-window / remaining-count majority).
  4. Bind military units to military slots (earliest-pack, id-order) -> exact type;
     villagers -> 'villager'.
Measures class + exact-type accuracy vs gRPC truth.
"""
import sys, types, json, bisect
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer", "C:/dev/aoe2/aoe2record/lab"]
from collections import defaultdict, Counter
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

GAMES = [
    ("GAME2", "C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/AgeIIDE_Replay_482723861.aoe2record", "labels_g2.json", 44.5),
    ("ORIGINAL", "C:/dev/_tmp_replay/fresh_newpatch.aoe2record", "labels.json", 42.6),
]
X, Y = 5, 5
X2, Y2 = 10, 10   # higher bar to flip a gather-leaning unit to military


def resolve(ctx, player):
    slots = sorted(ctx.prod_full.get(player, []))
    sc = ["villager" if t == "villager" else "military" for _t, t in slots]
    st = [t for _t, t in slots]
    S = len(slots)
    units = sorted(c for c, g in ctx.guesses.items()
                   if g.player == player and c not in ctx.building_ids
                   and c not in ctx.gaia_all and c not in ctx.start_ids
                   and g.behavior.get("first_seen") is not None)
    # co-command groups
    groups = defaultdict(list)   # cid -> list of frozenset(group)
    for _pl, ids in ctx.group_cmds:
        grp = frozenset(i for i in ids if i not in ctx.building_ids)
        if 2 <= len(grp) <= 60:
            for i in grp:
                groups[i].append(grp)

    cls = {}
    conf = {}
    gather = {}
    for c in units:
        b = ctx.guesses[c].behavior
        gather[c] = bool(b.get("gathers")) and not b.get("hard_build")
        if b.get("hard_build"):
            cls[c], conf[c] = "villager", True
        elif b.get("hard_mil"):
            cls[c], conf[c] = "military", True
        else:
            cls[c], conf[c] = (None, False)

    def bind():
        claimed = [False] * S
        slot_of = {}
        last = -1
        for c in units:
            j = last + 1
            if conf[c] and cls[c]:
                while j < S and (claimed[j] or sc[j] != cls[c]):
                    j += 1
            else:
                while j < S and claimed[j]:
                    j += 1
            if j < S:
                claimed[j] = True
                slot_of[c] = j
                last = j
        return slot_of

    for _ in range(8):
        changed = False
        slot_of = bind()
        anchors = sorted(c for c in units if conf[c] and c in slot_of)
        # spine forcing
        for c in units:
            if conf[c]:
                continue
            p = bisect.bisect_left(anchors, c)
            lo = anchors[p - 1] if p > 0 else None
            hi = anchors[p] if p < len(anchors) else None
            s_lo = slot_of[lo] if lo is not None else -1
            s_hi = slot_of[hi] if hi is not None else S
            w = set(sc[s_lo + 1:s_hi])
            if len(w) == 1:
                cls[c] = next(iter(w))
                conf[c] = True
                changed = True
        # co-command
        for c in units:
            if conf[c]:
                continue
            nb = defaultdict(set)
            ev = Counter()
            for grp in groups.get(c, []):
                hits = {j for j in grp if j != c and conf.get(j)}
                cl = {cls[j] for j in hits}
                for j in hits:
                    nb[cls[j]].add(j)
                for k in cl:
                    ev[k] += 1
            if not nb:
                continue
            best = max(nb, key=lambda k: len(nb[k]))
            need_x, need_y = (X2, Y2) if (gather[c] and best == "military") else (X, Y)
            if len(nb[best]) >= need_y and ev[best] >= need_x:
                cls[c] = best
                conf[c] = True
                changed = True
        if not changed:
            break

    # guess residual
    slot_of = bind()
    anchors = sorted(c for c in units if conf[c] and c in slot_of)
    for c in units:
        if conf[c]:
            continue
        if gather[c]:
            cls[c] = "villager"
            continue
        p = bisect.bisect_left(anchors, c)
        lo = anchors[p - 1] if p > 0 else None
        hi = anchors[p] if p < len(anchors) else None
        s_lo = slot_of[lo] if lo is not None else -1
        s_hi = slot_of[hi] if hi is not None else S
        w = Counter(sc[s_lo + 1:s_hi])
        cls[c] = (w.most_common(1)[0][0] if w else "military")

    # final typing: military units -> military slots via the VALIDATED match/skip DP
    # (spawn-before-command + earliest-pack, handles uncommanded-slot skips).
    mil_slots = [(slots[i][0], st[i]) for i in range(S) if sc[i] == "military"]
    ft = [t for t, _ in mil_slots]
    fu = [t for _, t in mil_slots]
    mil_units = sorted(c for c in units if cls[c] == "military")
    fs = [ctx.guesses[c].behavior["first_seen"] for c in mil_units]
    m = uc._match_dp(mil_units, fs, [True] * len(mil_units), ft, fu,
                     4.0, 22.0, 0.5, 1e9, pack=True)
    typ = {c: m.get(c, "unit") for c in mil_units}
    for c in units:
        if cls[c] == "villager":
            typ[c] = "villager"
    return cls, typ


for name, replay, labelsf, endmin in GAMES:
    labels = json.load(open(labelsf))
    mt = mgz.model.parse_match(open(replay, "rb"))
    ctx = uc.build_context(mt)
    uc.behavioral_labels(ctx)
    uc.production_timeline(ctx)
    ctx.group_cmds  # already populated
    CUT = (endmin - 5) * 60000
    cur_tm, _ = uc.build_type_map(mt)   # current classifier, for head-to-head
    print(f"\n######## {name} ########")
    for p in mt.players:
        cls, typ = resolve(ctx, p.name)
        tt = ty_ok = cc = c_ok = cur_ok = cur_c_ok = 0
        for c in typ:
            k = str(c)
            if k not in labels:
                continue
            u = labels[k]
            if (u.get("created_ms") or 0) >= CUT:
                continue
            truth_t = E.canon_truth(u["type"])
            truth_c = E.coarse(truth_t)
            if truth_c not in ("villager", "military"):
                continue
            cc += 1
            c_ok += (cls[c] == truth_c)
            cur_c = "villager" if cur_tm.get(c) == "villager" else "military"
            cur_c_ok += (cur_c == truth_c)
            if truth_c == "military":
                tt += 1
                ty_ok += (E.canon_pred(typ[c]) == truth_t)
                if c in cur_tm:
                    cur_ok += (E.canon_pred(cur_tm[c]) == truth_t)
        if cc:
            nm = f"{p.name}/{p.civilization}".encode("ascii", "replace").decode()
            print(f"  {nm:24} CLASS spine {100*c_ok/cc:5.1f}% vs current {100*cur_c_ok/cc:5.1f}%   |   "
                  f"MIL-TYPE spine {100*ty_ok/max(tt,1):.0f}% vs current {100*cur_ok/max(tt,1):.0f}%")
