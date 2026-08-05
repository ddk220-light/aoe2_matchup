"""run_focus_sets.py — record N rounds of specific matchups, each into its OWN named
folder, and Taildrop each one the moment it finishes.

For settling a single matchup the main batch left ambiguous: the batch records each
matchup once, which is enough to spot a question but not to answer it.

  python run_focus_sets.py <rounds> <drop_to> <civ>/<slug>:<civ>/<slug>:<name> ...
"""
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

BASE = Path(r"C:\Users\ddk22\Videos\aoe2_golden")
REPORTER = HERE / "golden_report.py"


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    rounds, drop_to, specs = int(argv[0]), argv[1], argv[2:]

    from record_golden import record_many
    import run_golden_overnight as R

    for spec in specs:
        a, b, name = spec.split(":")
        c1, s1 = a.split("/")
        c2, s2 = b.split("/")
        out = BASE / name
        # RESUME: count rounds already on disk and record only what is missing, seeding
        # the repeat counter so the new rounds continue the _rN numbering. Without this a
        # re-run starts at the base tag again and overwrites the rounds already recorded.
        dec = out / "decoded"
        base_tag = f"{s1}__vs__{s2}"
        existing = len(list(dec.glob(f"{base_tag}*.summary.json"))) if dec.exists() else 0
        remaining = max(0, rounds - existing)
        print(f"\n########## {name}: {rounds} rounds of {c1}/{s1} vs {c2}/{s2}"
              f" ({existing} already on disk, {remaining} to record)", flush=True)
        res = record_many(out, [((c1, s1), (c2, s2))] * remaining,
                          tag_offset=Counter({base_tag: existing})) if remaining else []
        ok = sum(1 for _, st in res if st == "ok") + existing
        print(f"########## {name}: {ok}/{rounds} rounds recorded", flush=True)
        if not ok:
            print(f"FOCUS DROP {name}: NOTHING RECORDED", flush=True)
            continue
        subprocess.run([sys.executable, str(REPORTER), str(out / "decoded"),
                        "--md", str(out / "GROUND_TRUTH.md")], capture_output=True)
        R.build_and_drop(str(out), drop_to, f"{rounds}rounds", regen_report=False)
        print(f"FOCUS DROP {name}: sent", flush=True)
    print("\nFOCUS SETS COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))
