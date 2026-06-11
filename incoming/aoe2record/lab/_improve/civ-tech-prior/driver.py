"""Long-lived scoring driver: parse g0+train ONCE, then on each new token in cmd.txt
reload unit_classifier (this dir's copy) and score both games, writing out_<token>.txt
with SCORES lines + full per-error detail. Poll-based so the agent can iterate fast.
"""
import sys, types, json, os, time, traceback, importlib
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WS = r"C:\dev\aoe2\aoe2record\lab\_improve\civ-tech-prior"
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab", WS]
import mgz.model
sys.path.insert(0, WS)
import unit_classifier as uc      # MUST precede eval_against_truth (it imports uc too)
import eval_against_truth as E

assert uc.__file__.lower().startswith(WS.lower()), f"wrong uc: {uc.__file__}"

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
           r"C:\dev\aoe2\aoe2record\lab\labels.json", 42.6),
    "train": (r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
              r"C:\dev\aoe2\aoe2record\lab\labels_g2.json", 44.5),
}
matches, labels = {}, {}
for name, (rp, lb, em) in GAMES.items():
    t0 = time.time()
    matches[name] = mgz.model.parse_match(open(rp, "rb"))
    labels[name] = json.load(open(lb))
    print(f"{name}: parsed in {time.time()-t0:.0f}s", flush=True)
print("READY", flush=True)


def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")


def score(game, f):
    rp, lb, end_min = GAMES[game]
    cut = (end_min - 5) * 60000
    mt = matches[game]
    ctx = uc._run(mt)
    tm = {}
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.gaia_all:
            continue
        tm[cid] = g.type if g.type not in uc.GENERIC_TYPES else (
            "villager" if g.cls == "villager" else "unit")
    truth_units = {int(k): u for k, u in labels[game].items()
                   if (u.get("created_ms") or 0) < cut and known(u.get("type"))}
    overlap = [k for k in truth_units if k in tm]
    cov = 100 * len(overlap) / max(len(truth_units), 1)
    res = {}
    from collections import Counter, defaultdict
    for label, milonly in (("OVERALL", False), ("MILITARY", True)):
        gtot = gok = 0
        for k in overlap:
            t = E.canon_truth(truth_units[k]["type"])
            if E.coarse(t) != "military" and milonly:
                continue
            gtot += 1
            if E.canon_pred(tm[k]) == t:
                gok += 1
        res[label] = 100 * gok / max(gtot, 1)
        res[label + "_n"] = (gok, gtot)
    f.write(f"== {game} ==  SCORES coverage={cov:.1f} overall={res['OVERALL']:.1f} "
            f"military={res['MILITARY']:.1f}  "
            f"(mil {res['MILITARY_n'][0]}/{res['MILITARY_n'][1]}, "
            f"all {res['OVERALL_n'][0]}/{res['OVERALL_n'][1]})\n")
    conf = Counter()
    for k in sorted(overlap):
        t = E.canon_truth(truth_units[k]["type"])
        p = E.canon_pred(tm[k])
        if p != t:
            conf[(t, p)] += 1
    f.write("confusion truth->pred:\n")
    for (t, p), c in conf.most_common():
        f.write(f"   {t:16}->{p:16} x{c}\n")
    f.write("error detail:\n")
    for k in sorted(overlap):
        t = E.canon_truth(truth_units[k]["type"])
        p = E.canon_pred(tm[k])
        if p == t:
            continue
        g = ctx.guesses[k]
        cms = (truth_units[k].get("created_ms") or 0) / 60000
        fs = (g.behavior.get("first_seen") or 0) / 60
        beh = {k2: v for k2, v in g.behavior.items() if k2 != "first_seen"}
        f.write(f" id={k:6} truth={truth_units[k]['type']:>20}({t}) pred={g.type}->{p} "
                f"ply={g.player} cls={g.cls}/{g.cls_conf:.2f} tc={g.type_conf:.2f} "
                f"sig={','.join(g.signals)} created={cms:5.2f}m fs={fs:5.2f}m beh={beh}\n")
    return res


last = ""
while True:
    try:
        tok = open(os.path.join(WS, "cmd.txt")).read().strip()
    except Exception:
        tok = ""
    if tok and tok != last:
        last = tok
        out = os.path.join(WS, f"out_{tok}.txt")
        with open(out, "w") as f:
            try:
                importlib.reload(uc)
                for game in GAMES:
                    score(game, f)
            except Exception:
                f.write("EXCEPTION:\n" + traceback.format_exc())
        print(f"done {tok}", flush=True)
    if tok == "QUIT":
        break
    time.sleep(2)
