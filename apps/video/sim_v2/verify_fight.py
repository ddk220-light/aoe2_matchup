"""Read recorded fight .hp.json sidecars and report the in-game outcome per fight,
checking it against the category the storyboard filmed it under.

The sidecar is SUBJECT-NORMALIZED by record_until_end.select_sidecar: side1 = the
subject (the analysis unit), side2 = the opponent. We still cross-check against the
storyboard's expected (subject, opponent) start counts and warn on a mismatch (an
equal-count fight can't be disambiguated by the swap heuristic).

Outcome from the final decoded row:
  win   = opponent wiped (count 0) AND subject survives (count > 0)
  loss  = subject wiped   (count 0) AND opponent survives (count > 0)
  draw/unclear = neither wiped (timed out) or both wiped

Expected by category:
  expected_win / unexpected_win           -> subject WINS
  expected_counter / unexpected_counter   -> subject LOSES   (film-category names)
  expected_loss / unexpected_loss         -> subject LOSES   (v2-category names)
  even / coin_flip                         -> either (informational)

Usage:
  python verify_fight.py <dir-with-hp.json>       # scan every *.hp.json in a dir
  python verify_fight.py <one.hp.json> [more ...]  # specific files
"""
import glob
import json
import os
import sys

WIN_CATS = {"expected_win", "unexpected_win"}
LOSS_CATS = {"expected_counter", "unexpected_counter", "expected_loss", "unexpected_loss"}
EITHER_CATS = {"even", "coin_flip"}

# film-category prefix (as run_unit_analysis_video / record_fights name the clips)
FILECAT = ("expected_win", "unexpected_win", "expected_counter",
           "unexpected_counter", "expected_loss", "unexpected_loss",
           "coin_flip", "even")


def _cat_from_name(path):
    b = os.path.basename(path)
    for c in FILECAT:
        if b.startswith(c + "_"):
            return c
    return None


def outcome(rows):
    """(result, subj_ct, subj_hp, opp_ct, opp_hp) from the last row where at least
    one side is decoded; result in win/loss/draw/unclear."""
    last = rows[-1]
    s, o = last["side1"], last["side2"]
    sc, oc = s["count"], o["count"]
    if oc == 0 and sc > 0:
        r = "win"
    elif sc == 0 and oc > 0:
        r = "loss"
    elif sc == 0 and oc == 0:
        r = "draw(both wiped)"
    else:
        r = "unclear(timeout)"
    return r, sc, s["hp"], oc, o["hp"]


def check(path):
    d = json.load(open(path))
    rows = d.get("rows") or []
    if not rows:
        return {"path": path, "error": "no rows"}
    r0 = rows[0]
    res, sc, shp, oc, ohp = outcome(rows)
    cat = _cat_from_name(path)
    expect = ("WIN" if cat in WIN_CATS else "LOSS" if cat in LOSS_CATS
              else "either" if cat in EITHER_CATS else "?")
    match = (expect == "either" or expect == "?"
             or (expect == "WIN" and res == "win")
             or (expect == "LOSS" and res == "loss"))
    return {
        "path": path, "category": cat, "expect": expect, "result": res,
        "start": (r0["side1"]["count"], r0["side2"]["count"]),
        "subject_end": (sc, shp), "opp_end": (oc, ohp),
        "match": match,
    }


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    files = []
    for a in argv:
        if os.path.isdir(a):
            files += sorted(glob.glob(os.path.join(a, "*.hp.json")))
        else:
            files.append(a)
    rows, bad = [], 0
    for f in files:
        r = check(f)
        rows.append(r)
    for r in rows:
        if "error" in r:
            print(f"  !! {os.path.basename(r['path'])}: {r['error']}")
            bad += 1
            continue
        flag = "OK " if r["match"] else "!! MISMATCH"
        if not r["match"]:
            bad += 1
        print(f"  {flag} {os.path.basename(r['path'])}")
        print(f"       cat={r['category']} expect={r['expect']} -> in-game={r['result'].upper()}"
              f"   start(subj v opp)={r['start'][0]}v{r['start'][1]}"
              f"   end subj={r['subject_end'][0]}u/{r['subject_end'][1]:.0f}hp"
              f" opp={r['opp_end'][0]}u/{r['opp_end'][1]:.0f}hp")
    print(f"\n{len(rows)-bad}/{len(rows)} match their filmed category"
          + (f"  ({bad} to review)" if bad else ""))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))
