"""For each current-classifier military error on game 2, tag whether window-forcing
(slot-window between confident anchors is homogeneous) or co-attack (co-commanded in
ATTACK actions with confident-military units) would fix it."""
import sys, types, json, bisect
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/visualizer", "C:/dev/aoe2/aoe2record/lab"]
from collections import defaultdict, Counter
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

REPLAY = "C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/AgeIIDE_Replay_482723861.aoe2record"
labels = json.load(open("labels_g2.json"))
CUT = (44.5 - 5) * 60000
mt = mgz.model.parse_match(open(REPLAY, "rb"))
tm, _ = uc.build_type_map(mt)
ctx = uc._run(mt)

# rich group commands: (player, action_type, [ids])
ATTACK_ATS = {"ORDER", "ATTACK_GROUND", "PATROL", "DE_ATTACK_MOVE", "GUARD"}
rich = []
for a in mt.actions:
    if not a.player:
        continue
    at = str(a.type).replace("Action.", "")
    ids = [ctx.canon(o) for o in (a.payload or {}).get("object_ids", []) if ctx.canon(o) not in ctx.building_ids]
    tgt = (a.payload or {}).get("target_id")
    is_atk = at in ("ATTACK_GROUND", "PATROL", "DE_ATTACK_MOVE", "GUARD") or \
        (at == "ORDER" and isinstance(tgt, int) and tgt not in ctx.gaia_all
         and ctx.owner.get(tgt) and ctx.owner.get(tgt) != a.player.name)
    if 2 <= len(ids) <= 60:
        rich.append((a.player.name, is_atk, set(ids)))

# confident class from CURRENT classifier (its prediction, treated as the anchor truth)
pred_cls = {c: ("villager" if tm.get(c) == "villager" else "military") for c in tm}

for owner, player in ((1, "ddk220"), (2, "wR.Baxter")):
    slots = sorted(ctx.prod_full.get(player, []))
    sc = ["villager" if t == "villager" else "military" for _t, t in slots]
    units = sorted(c for c, g in ctx.guesses.items()
                   if g.player == player and c not in ctx.building_ids
                   and c not in ctx.gaia_all and c not in ctx.start_ids
                   and g.behavior.get("first_seen") is not None and str(c) in labels)
    # oracle-bind by current predicted class to get slot windows
    claimed = [False] * len(slots)
    slot_of = {}
    last = -1
    for c in units:
        cl = pred_cls.get(c, "military")
        j = last + 1
        while j < len(slots) and (claimed[j] or sc[j] != cl):
            j += 1
        if j < len(slots):
            claimed[j] = True
            slot_of[c] = j
            last = j
    # confident anchors = units with a hard signal
    anchors = sorted(c for c in units
                     if (ctx.guesses[c].behavior.get("hard_build") or ctx.guesses[c].behavior.get("hard_mil"))
                     and c in slot_of)

    classerr = typeerr = win_fix = atk_fix = 0
    rows = []
    for c in units:
        u = labels[str(c)]
        if (u.get("created_ms") or 0) >= CUT:
            continue
        tt = E.canon_truth(u["type"])
        if E.coarse(tt) != "military":
            continue
        if E.canon_pred(tm.get(c, "unit")) == tt:
            continue
        is_class = (tm.get(c) == "villager" or tm.get(c) in ("unit", "military"))
        # window homogeneity
        p = bisect.bisect_left(anchors, c)
        lo = anchors[p - 1] if p > 0 else None
        hi = anchors[p] if p < len(anchors) else None
        s_lo = slot_of[lo] if lo is not None else -1
        s_hi = slot_of[hi] if hi is not None else len(slots)
        w = set(sc[s_lo + 1:s_hi])
        win = next(iter(w)) if len(w) == 1 else None
        # co-attack with confident military
        atk_mil = set()
        for _pl, is_atk, grp in rich:
            if c in grp and is_atk:
                for j in grp:
                    if j != c and pred_cls.get(j) == "military" and \
                       (ctx.guesses[j].behavior.get("hard_mil")):
                        atk_mil.add(j)
        b = ctx.guesses[c].behavior
        if is_class:
            classerr += 1
            if win == "military":
                win_fix += 1
            if len(atk_mil) >= 3:
                atk_fix += 1
        else:
            typeerr += 1
        rows.append((c, tt, tm.get(c), is_class, win, len(atk_mil),
                     bool(b.get("gathers")), bool(b.get("hard_mil"))))
    print(f"\n=== {player}: {classerr} class-errors, {typeerr} type-errors ===")
    print(f"   class-errors fixable by WINDOW-forcing(mil): {win_fix}/{classerr}   "
          f"by CO-ATTACK(>=3 mil): {atk_fix}/{classerr}")
    for c, tt, pr, isc, win, na, ga, hm in rows[:14]:
        kind = "CLASS" if isc else "type"
        print(f"   id={c} {kind} TRUE={tt:13} GOT={str(pr):13} win={str(win):8} co_atk_mil={na} gather={ga} hardmil={hm}")
