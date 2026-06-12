"""Fast iteration driver: load cached parsed matches, run THIS dir's unit_classifier,
score vs labels (same math as _improve/score_game.py), and print ledger diagnostics
(predicted production stream vs truth spawn stream per player).

Usage: python _improve/queue-ledger/iterate.py [g0] [train] [--diag] [--errors]
"""
import sys, types, json, pickle, os
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WS = r"C:\dev\aoe2\aoe2record\lab\_improve\queue-ledger"
UCDIR = os.environ.get("UCDIR", WS)
sys.path[:0] = [UCDIR, "C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab"]
if UCDIR != WS:
    sys.path.insert(1, WS)
from collections import Counter, defaultdict
import unit_classifier as uc
import eval_against_truth as E

assert uc.__file__.startswith(UCDIR), f"wrong classifier: {uc.__file__}"

GAMES = {
    "g0": dict(replay="C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
               labels=r"C:\dev\aoe2\aoe2record\lab\labels.json", end_min=42.6),
    "train": dict(replay=r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
                  labels=r"C:\dev\aoe2\aoe2record\lab\labels_g2.json", end_min=44.5),
}
_MT = {}


def get_match(key):
    if key not in _MT:
        pkl = os.path.join(WS, f"match_cache_{key}.pkl")
        if os.path.exists(pkl):
            _MT[key] = pickle.load(open(pkl, "rb"))
        else:
            import mgz.model
            _MT[key] = mgz.model.parse_match(open(GAMES[key]["replay"], "rb"))
    return _MT[key]

args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = set(a for a in sys.argv[1:] if a.startswith("--"))
keys = args or ["g0", "train"]


def score(key, diag=False, errors=False):
    cfg = GAMES[key]
    labels = json.load(open(cfg["labels"]))
    mt = get_match(key)
    END_MIN = cfg["end_min"]
    CUT = (END_MIN - 5) * 60000

    tm, _ = uc.build_type_map(mt)
    ctx = uc._run(mt)  # for diagnostics (second run is cheap)

    def known(name):
        if not name or name.lower() == "flare" or name.startswith("id"):
            return False
        return E.coarse(E.canon_truth(name)) in ("villager", "military")

    truth_units = {int(k): u for k, u in labels.items()
                   if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}
    overlap = [k for k in truth_units if k in tm]
    coverage = 100 * len(overlap) / max(len(truth_units), 1)

    out = {}
    conf = Counter()
    err_rows = []
    for label, milonly in (("overall", False), ("military", True)):
        gtot = gok = 0
        for k in overlap:
            t = E.canon_truth(truth_units[k]["type"])
            if E.coarse(t) != "military" and milonly:
                continue
            p = E.canon_pred(tm[k])
            gtot += 1
            if p == t:
                gok += 1
            elif milonly:
                conf[(t, p)] += 1
                err_rows.append((k, truth_units[k]["type"], t, p,
                                 truth_units[k].get("owner"),
                                 (truth_units[k].get("created_ms") or 0) / 1000))
        out[label] = 100 * gok / max(gtot, 1)
    print(f"[{key}] coverage={coverage:.1f} overall={out['overall']:.1f} military={out['military']:.1f}")
    for (t, p), c in conf.most_common():
        print(f"    truth={t:16} pred={p:16} x{c}")
    if errors:
        for k, tn, t, p, o, cs in sorted(err_rows, key=lambda r: (r[4], r[5])):
            print(f"    ERR id={k:6} owner={o} created={cs:7.1f}s truth={tn:20} ({t}) pred={p}")

    if diag:
        ledger_diag(key, ctx, mt, labels, CUT)
    return out, coverage


def ledger_diag(key, ctx, mt, labels, CUT):
    """Compare predicted completion stream vs truth spawn stream, per player."""
    num2name = {p.number: p.name for p in mt.players}
    print(f"\n=== LEDGER DIAG {key} ===")
    for p in mt.players:
        pname = p.name
        # truth military spawns for this player (ALL, even uncommanded)
        tr = []
        for k, u in labels.items():
            if u.get("owner") != p.number:
                continue
            nm = u.get("type") or ""
            if not nm or nm.lower() == "flare" or nm.startswith("id"):
                continue
            tok = E.canon_truth(nm)
            if E.coarse(tok) != "military":
                continue
            tr.append(((u.get("created_ms") or 0) / 1000, tok, int(k)))
        tr.sort()
        pred = [(t, E.canon_pred(u)) for t, u in ctx.prod_mil.get(pname, [])]
        # align by order and count token agreement
        n = min(len(tr), len(pred))
        agree = sum(1 for i in range(n) if tr[i][1] == pred[i][1])
        dts = [pred[i][0] - tr[i][0] for i in range(n)]
        med = sorted(dts)[len(dts) // 2] if dts else 0
        print(f"  {pname:12} truth_mil={len(tr):3} pred_mil={len(pred):3} "
              f"order-type-agree={agree}/{n} median_dt={med:+.1f}s")
        if "--dump" in flags:
            for i in range(max(len(tr), len(pred))):
                a = f"{tr[i][0]:7.1f} {tr[i][1]:>16} id={tr[i][2]}" if i < len(tr) else " " * 30
                b = f"{pred[i][0]:7.1f} {pred[i][1]:<16}" if i < len(pred) else ""
                mark = "" if (i < n and tr[i][1] == pred[i][1]) else "   <<<"
                print(f"    {a}   ||  {b}{mark}")


tot = {}
for k in keys:
    out, cov = score(k, diag="--diag" in flags, errors="--errors" in flags)
    tot[k] = out
print("\nSUMMARY: " + "  ".join(f"{k}: mil={v['military']:.1f} overall={v['overall']:.1f}" for k, v in tot.items()))
