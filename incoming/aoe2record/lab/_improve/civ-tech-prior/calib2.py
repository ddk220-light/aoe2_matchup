"""calib2.py -- measure FIFO completion-time accuracy vs gRPC truth spawn times,
per PRIORS config. k-th aligned within (player, canonical token) so unit-line
upgrades (Man-at-Arms vs Militia) line up. Lower mean |diff| = better timing model."""
import sys, types, json, statistics
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WS = r"C:\dev\aoe2\aoe2record\lab\_improve\civ-tech-prior"
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab", WS]
import mgz.model
sys.path.insert(0, WS)
import unit_classifier as uc
import eval_against_truth as E
from collections import defaultdict

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
           r"C:\dev\aoe2\aoe2record\lab\labels.json", 42.6),
    "train": (r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
              r"C:\dev\aoe2\aoe2record\lab\labels_g2.json", 44.5),
}
matches = {n: mgz.model.parse_match(open(rp, "rb")) for n, (rp, lb, em) in GAMES.items()}
labels = {n: json.load(open(lb)) for n, (rp, lb, em) in GAMES.items()}

ALL = ["blocks", "lb_blocks", "upgrades", "eagle_age", "line_speed", "speed_techs"]


def canon_model(tok):
    if tok == "villager":
        return "villager"
    return E.canon_pred(tok) if E.canon_pred(tok) != "unit" else tok


def canon_truth_name(nm):
    t = E.canon_truth(nm)
    return t


def drift(game, verbose=False):
    rp, lb, end_min = GAMES[game]
    mt = matches[game]
    ctx = uc.build_context(mt)
    uc.production_timeline(ctx)
    num2name = {getattr(p, "number", None): p.name for p in mt.players}
    truth = defaultdict(list)
    for k, u in labels[game].items():
        nm = u.get("type") or ""
        o = u.get("owner")
        cms = u.get("created_ms")
        if cms is None or o not in num2name or not nm or nm.lower() == "flare" or nm.startswith("id"):
            continue
        ct = canon_truth_name(nm)
        if E.coarse(ct) not in ("villager", "military"):
            continue
        truth[(num2name[o], ct)].append(cms / 1000.0)
    model = defaultdict(list)
    for pl, comp in ctx.prod_full.items():
        for t, u in comp:
            model[(pl, canon_model(u))].append(t)
    for d in (truth, model):
        for v in d.values():
            v.sort()
    tot = n_tot = 0.0
    rows = []
    for key in sorted(model):
        mts, sts = model[key], truth.get(key, [])
        n = min(len(mts), len(sts))
        if n == 0:
            continue
        diffs = [mts[i] - sts[i] for i in range(n)]
        tot += sum(abs(d) for d in diffs)
        n_tot += n
        rows.append((key, n, statistics.median(diffs), sum(abs(d) for d in diffs) / n))
    if verbose:
        for key, n, med, mad in sorted(rows, key=lambda r: -r[1] * 0 - r[3] * r[1]):
            print(f"   {key[0]:10} {key[1]:14} n={n:3} med={med:+7.1f}s meanabs={mad:7.1f}s")
    return tot / max(n_tot, 1)


CONFIGS = [
    ("all-off", []),
    ("all-on", ALL),
    ("blocks", ["blocks", "lb_blocks"]),
    ("upgrades", ["upgrades"]),
    ("eagle_age", ["eagle_age"]),
    ("speeds", ["line_speed", "speed_techs"]),
]
if len(sys.argv) > 1 and sys.argv[1] == "-v":
    for nm, keys in (("all-off", []), ("all-on", ALL)):
        for k in ALL:
            uc.PRIORS[k] = k in keys
        for game in GAMES:
            print(f"--- {nm} {game} ---")
            drift(game, verbose=True)
    sys.exit()

print(f"{'config':12} {'g0 mean|d|':>11} {'train mean|d|':>14}")
for name, keys in CONFIGS:
    for k in ALL:
        uc.PRIORS[k] = k in keys
    print(f"{name:12} {drift('g0'):11.1f} {drift('train'):14.1f}", flush=True)
