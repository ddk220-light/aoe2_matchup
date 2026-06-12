"""Gate harness for the v2 unit classifier (unit_classifier.py).

Runs the pipeline with per-stage snapshots and checks the gates that must hold
before redeploy:
  G1 every confidence stage changes >0 (no inert stages)
  G2 co-moving groups are mostly homogeneous in type (heterogeneity low)
  G3 type proportions track production
  G4 hard-class co-command purity stays ~100%
  G5 no phantom-duplicate units (shifted ids collapse to one canonical unit)

Usage: python eval_classifier.py [replay.aoe2record] [target_player]
"""
import os
import sys
import types
from collections import Counter, defaultdict


def _bootstrap():
    for m in ("flask", "flask_cors", "requests"):
        sys.modules.setdefault(m, types.ModuleType(m))
    sys.modules["flask"].Flask = lambda *a, **k: types.SimpleNamespace(route=lambda *a, **k: (lambda f: f))
    sys.modules["flask"].jsonify = lambda *a, **k: None
    sys.modules["flask"].request = None
    sys.modules["flask"].send_from_directory = lambda *a, **k: None
    sys.modules["flask_cors"].CORS = lambda *a, **k: None
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    for p in (os.environ.get("MGZ_PATH", "C:/dev/aoe2/aoc-mgz-67x"), root):
        if p not in sys.path:
            sys.path.insert(0, p)


def main():
    _bootstrap()
    import mgz.model
    from aoe2x.replay import unit_classifier as uc

    replay = sys.argv[1] if len(sys.argv) > 1 else "C:/dev/_tmp_replay/AgeIIDE_Replay_481391706.aoe2record"
    target = sys.argv[2] if len(sys.argv) > 2 else None
    with open(replay, "rb") as f:
        match = mgz.model.parse_match(f)
    print(f"replay: {os.path.basename(replay)}  players: {[p.name for p in match.players]}")
    GEN = uc.GENERIC_TYPES

    # ---- run with per-stage snapshots (G1) ----
    def snap(ctx):
        return {cid: (g.cls, g.type) for cid, g in ctx.guesses.items()}

    def delta(prev, cur):
        cs = cc = tf = tflip = 0
        for cid, (c, t) in cur.items():
            pc, pt = prev.get(cid, ("unknown", "unit"))
            if c != pc:
                cs += pc == "unknown"
                cc += pc != "unknown"
            if t != pt:
                tf += pt in GEN and t not in GEN
                tflip += pt not in GEN and t not in GEN
        return cs, cc, tf, tflip

    ctx = uc.build_context(match); prev = snap(ctx); rows = [("build_context", delta({}, prev))]
    uc.behavioral_labels(ctx); c = snap(ctx); rows.append(("behavioral_labels", delta(prev, c))); prev = c
    w = uc.cocommand_graph(ctx); uc.propagate_class(ctx, w); c = snap(ctx); rows.append(("propagate_class", delta(prev, c))); prev = c
    uc.production_timeline(ctx); c = snap(ctx); rows.append(("production_timeline*", delta(prev, c))); prev = c
    sq = uc.form_squads(ctx, w); c = snap(ctx); rows.append(("form_squads*", delta(prev, c))); prev = c
    uc.assign_types(ctx, sq); c = snap(ctx); rows.append(("assign_types", delta(prev, c))); prev = c
    uc.finalize(ctx); c = snap(ctx); rows.append(("finalize", delta(prev, c))); prev = c
    g = ctx.guesses

    print("\n== G1 per-stage marginal effect (cls_set/cls_chg/type_fill/type_flip) ==  (* = data/grouping stage)")
    for name, (cs, cc, tf, tflip) in rows:
        tot = cs + cc + tf + tflip
        flag = "" if (tot or name.endswith("*")) else "  <-- INERT (gate fail)"
        print(f"  {name:22} {cs:6} {cc:6} {tf:7} {tflip:7}{flag}")

    # ---- G5 phantom dedup ----
    flat, remap = uc.build_type_map(match)
    leak = [k for k in flat if k >= uc.SHIFT_THRESHOLD]
    print(f"\n== G5 phantom dedup ==  shifted refs in remap: {len(remap)}  | shifted ids leaking into type map: {len(leak)} (want 0)")

    # ---- per-player + target metrics ----
    def prod_of(player):
        c = Counter()
        for a in match.actions:
            if str(a.type).endswith("DE_QUEUE") and a.player and a.player.name == player and a.payload:
                c[uc._norm(a.payload.get("unit"))] += a.payload.get("amount", 1) or 1
        return c

    units_by_p = defaultdict(list)
    for cid, gu in g.items():
        if cid in ctx.building_ids or cid in ctx.start_ids:
            continue
        units_by_p[gu.player].append(gu)
    if target is None:
        target = max(units_by_p, key=lambda p: len(units_by_p[p]))

    tgt = units_by_p[target]
    typed = sum(1 for u in tgt if u.type not in GEN)
    print(f"\n== G3 types for {target} ({typed}/{len(tgt)} = {100*typed/len(tgt):.0f}% typed) ==")
    print(f"  classified: {dict(Counter(u.type for u in tgt).most_common())}")
    print(f"  produced:   {dict(prod_of(target).most_common())}")

    # ---- G4 hard-class co-command purity ----
    HC = uc.CONF["hard_class"]
    hs = hd = 0
    for (x, y), wt in w.items():
        gx, gy = g.get(x), g.get(y)
        if gx and gy and gx.cls_conf >= HC and gy.cls_conf >= HC and gx.cls != "unknown" and gy.cls != "unknown":
            if gx.cls == gy.cls:
                hs += 1
            else:
                hd += 1
    print(f"\n== G4 hard-class co-command purity ==  {100*hs/(hs+hd):.1f}% same ({hd} mixed of {hs+hd})" if hs + hd else "G4 n/a")

    # ---- G2 group heterogeneity (final types within a single group command) ----
    GROUP = {"MOVE", "PATROL", "ORDER", "DE_ATTACK_MOVE", "GUARD"}
    total = het = 0
    by_cmd = defaultdict(lambda: [0, 0])
    for a in match.actions:
        if not a.player:
            continue
        at = str(a.type).replace("Action.", "")
        if at not in GROUP:
            continue
        ids = set(ctx.canon(o) for o in (a.payload or {}).get("object_ids", []))
        typed_ids = [i for i in ids if g.get(i) and g[i].type not in GEN]
        if len(typed_ids) < 3:
            continue
        nd = len(set(g[i].type for i in typed_ids))
        total += 1; by_cmd[at][1] += 1
        if nd > 1:
            het += 1; by_cmd[at][0] += 1
    print(f"\n== G2 heterogeneous co-moving groups (>=3 typed members) ==")
    if total:
        print(f"  {het}/{total} = {100*het/total:.0f}% MIXED  (was 68% before the rework)")
        for cmd, (h, t) in sorted(by_cmd.items()):
            print(f"    {cmd:14} {100*h/t:.0f}% mixed ({h}/{t})")


if __name__ == "__main__":
    main()
