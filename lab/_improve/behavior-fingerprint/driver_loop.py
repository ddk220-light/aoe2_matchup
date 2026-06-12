"""Resident scoring driver v2: parse both replays ONCE, then loop:
  - go.txt empty  -> reload workspace unit_classifier, score both games -> result.txt
  - go.txt = path -> exec that python file with ns {MTS, uc, E, score_all, reload_uc};
                     its stdout goes to result.txt
  - stop.txt      -> exit
sys.path is PINNED so reload always resolves the WORKSPACE classifier copy
(eval_against_truth.py prepends the production visualizer dir -- strip it).
"""
import sys, types, json, time, os, importlib, traceback, io, contextlib
from collections import Counter
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = r"C:\dev\aoe2\aoe2record\lab\_improve\behavior-fingerprint"
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab", WORK]
import mgz.model
import unit_classifier as uc
assert uc.__file__.lower().startswith(WORK.lower()), uc.__file__
import eval_against_truth as E   # this pollutes sys.path with the production dir


def _pin_path():
    """Keep WORK strictly ahead of the production visualizer dir."""
    sys.path[:] = [p for p in sys.path if "aoe2record" not in p.replace("\\", "/")]
    if sys.path[0] != WORK:
        sys.path.insert(0, WORK)


def reload_uc():
    _pin_path()
    importlib.reload(uc)
    assert uc.__file__.lower().startswith(WORK.lower()), uc.__file__
    return uc


GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", r"C:\dev\aoe2\aoe2record\lab\labels.json", 42.6),
    "train": (r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
              r"C:\dev\aoe2\aoe2record\lab\labels_g2.json", 44.5),
}

MTS, LBL = {}, {}
for g, (rep, lab, em) in GAMES.items():
    t0 = time.time()
    MTS[g] = mgz.model.parse_match(open(rep, "rb"))
    LBL[g] = json.load(open(lab))
    print(f"parsed {g} in {time.time()-t0:.0f}s", flush=True)


def known(name):
    if not name or name.lower() == "flare" or name.startswith("id"):
        return False
    return E.coarse(E.canon_truth(name)) in ("villager", "military")


def score_all(verbose=True):
    lines, summary = [], []
    nums = {}
    for g, (rep, lab, END_MIN) in GAMES.items():
        CUT = (END_MIN - 5) * 60000
        tm, _ = uc.build_type_map(MTS[g])
        truth_units = {int(k): u for k, u in LBL[g].items()
                       if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}
        overlap = [k for k in truth_units if k in tm]
        cov = 100 * len(overlap) / max(len(truth_units), 1)
        res = {}
        for label, milonly in (("overall", False), ("military", True)):
            gtot = gok = 0
            conf = Counter()
            for k in overlap:
                t = E.canon_truth(truth_units[k]["type"])
                if milonly and E.coarse(t) != "military":
                    continue
                p = E.canon_pred(tm[k])
                gtot += 1
                if p == t:
                    gok += 1
                else:
                    conf[(t, p, k)] += 1
            res[label] = (100 * gok / max(gtot, 1), gok, gtot)
            if milonly and verbose:
                lines.append(f"{g} military errors (truth->pred id):")
                for (t, p, k), c in sorted(conf.items()):
                    lines.append(f"  {t}->{p} id={k}")
        o, m = res["overall"], res["military"]
        nums[g] = (cov, o[0], m[0])
        summary.append(f"{g}: coverage={cov:.1f} overall={o[0]:.1f} ({o[1]}/{o[2]}) "
                       f"military={m[0]:.1f} ({m[1]}/{m[2]})")
    txt = "\n".join(summary)
    if verbose:
        txt += "\n\n" + "\n".join(lines)
    return txt


GO = os.path.join(WORK, "go.txt")
STOP = os.path.join(WORK, "stop.txt")
RESULT = os.path.join(WORK, "result.txt")
TMP = RESULT + ".tmp"
print("driver ready", flush=True)
while True:
    if os.path.exists(STOP):
        os.remove(STOP)
        print("stopping", flush=True)
        break
    if os.path.exists(GO):
        cmd = open(GO).read().strip()
        os.remove(GO)
        buf = io.StringIO()
        try:
            t0 = time.time()
            if cmd:
                src = open(cmd, encoding="utf-8").read()
                ns = {"MTS": MTS, "LBL": LBL, "E": E, "uc": uc, "score_all": score_all,
                      "reload_uc": reload_uc, "known": known, "GAMES": GAMES, "WORK": WORK}
                with contextlib.redirect_stdout(buf):
                    exec(compile(src, cmd, "exec"), ns)
            else:
                reload_uc()
                with contextlib.redirect_stdout(buf):
                    print(score_all())
            txt = buf.getvalue() + f"\n[{time.time()-t0:.1f}s]"
        except Exception:
            txt = buf.getvalue() + "\nERROR\n" + traceback.format_exc()
        with open(TMP, "w", encoding="utf-8", errors="replace") as f:
            f.write(txt)
        os.replace(TMP, RESULT)
        print("scored", flush=True)
    time.sleep(0.5)
