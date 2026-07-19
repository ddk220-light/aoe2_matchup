"""Pre-flight a unit's storyboard before recording: trim the filmed showcase to a
manageable size (default 3 fights/category, keeping the ranked-list cards intact),
and validate that EVERY filmed opponent + the subject resolve to a scenario unit
const via build_run.unit_const (an unresolvable slug crashes the recorder mid-run).

  python preflight_record.py <storyboard.json> [--max-per-cat 3] [--out <path>]

Writes the trimmed storyboard next to the input as <name>.film.json (or --out) and
prints the filmed plan + any slug that fails to resolve. Run with the recording
interpreter (apps/video/.venv) so build_run imports.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))              # apps/video on path (build_run)

CATEGORY_ORDER = ("expected_win", "unexpected_win",
                  "expected_counter", "unexpected_counter")


def _strip_civ_suffix(civ, slug):
    suffix = "_" + civ.lower()
    return slug[: -len(suffix)] if slug.endswith(suffix) else slug


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--max-per-cat", type=int, default=3)
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    sb = json.loads(Path(args.storyboard).read_text())
    from build_run import unit_const

    subj = sb["subject"]
    # validate subject
    problems = []
    try:
        unit_const(_strip_civ_suffix(subj["civ"], subj["slug"]))
    except Exception as e:
        problems.append((f"SUBJECT {subj['civ']}/{subj['slug']}", repr(e)))

    # keep only rank<=max per category (segments are already rank-ordered per cat)
    kept, per_cat = [], defaultdict(int)
    for s in sb["segments"]:
        if s["rank"] <= args.max_per_cat:
            kept.append(s)
            per_cat[s["category"]] += 1
    # re-number 'order' so the plan stays contiguous
    for i, s in enumerate(sorted(kept, key=lambda s: (CATEGORY_ORDER.index(s["category"])
                                                       if s["category"] in CATEGORY_ORDER else 9,
                                                       s["rank"])), 1):
        s["order"] = i
    sb["segments"] = kept

    # validate every filmed opponent slug
    print(f"Subject: {subj['name']} ({subj['civ']}/{subj['slug']})")
    print(f"Filmed fights ({len(kept)}):")
    for cat in CATEGORY_ORDER:
        segs = [s for s in kept if s["category"] == cat]
        if not segs:
            continue
        print(f"  {cat} ({len(segs)}):")
        for s in segs:
            o = s["opponent"]
            try:
                c = unit_const(_strip_civ_suffix(o["civ"], o["slug"]))
                tag = f"const {c}"
            except Exception as e:
                tag = f"!! FAILS: {e!r}"
                problems.append((f"{o['civ']}/{o['slug']}", repr(e)))
            cnt = s.get("counts", {})
            print(f"      #{s['rank']} {o['name']:32} ({o['civ']})  "
                  f"{cnt.get('subject','?')}v{cnt.get('opponent','?')}  {tag}")

    out = Path(args.out) if args.out else Path(args.storyboard).with_suffix(".film.json")
    out.write_text(json.dumps(sb, indent=2))
    print(f"\ntrimmed storyboard -> {out}")
    if problems:
        print(f"\n!! {len(problems)} slug(s) FAIL to resolve — fix before recording:")
        for k, e in problems:
            print(f"   {k}: {e}")
        return 1
    print("\nAll filmed slugs resolve. Ready to record.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))
