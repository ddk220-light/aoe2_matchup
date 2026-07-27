"""Record one matchup at SEVERAL army sizes, to separate a geometry artifact from a
stats/ability gap.

simulation_real seats each army as a single vertical column, so at large counts only the
fronts of the two lines ever touch and the bigger army's numbers barely register; at small
counts every unit engages, so numbers apply. If a matchup is broken by that geometry, the
sim's win-rate MOVES WITH ARMY SIZE at a fixed ratio — and the in-game result should track
the small-count sim, where the real game also cannot envelop.

  python record_scaletest.py <subj_civ> <subj_slug> <opp_civ> <opp_slug> <out_dir> \
         <cap>[xN] [<cap>[xN] ...]

`cap` is run_matchup's equal-resource unit cap (21 = the standard arena size); the optional
xN records that size N times, since small fights are noisy. Clips are named
scale_<n1>v<n2>_roll<k>. Game must be open in the Scenario Editor, frontmost.

Example (Elite Temple Guard vs Armenian Warrior Priest, 3 small rolls + 1 full):
  python record_scaletest.py Muisca elite_temple_guard_muisca Armenians \
      warrior_priest_armenians OUT 5x3 21
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))              # apps/video on path


def main(argv):
    if len(argv) < 6:
        print(__doc__)
        return 2
    subj_civ, subj_slug, opp_civ, opp_slug, out_dir = argv[:5]
    specs = []
    for tok in argv[5:]:
        cap, _, n = tok.partition("x")
        specs.append((int(cap), int(n or 1)))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    from auto.orchestrate_matchup import run_matchup, return_to_editor
    from auto.pure import equal_resource_counts
    from build_golden_v2 import build_v2_from_sides as build_golden_from_sides

    # The on-screen keyboard host steals foreground and eats the rig's injected keys
    # (2026-07-20). It respawns on demand, so killing it is safe.
    subprocess.run(["taskkill", "/f", "/im", "TextInputHost.exe"],
                   capture_output=True)

    plan = []
    for cap, rolls in specs:
        n1, n2 = equal_resource_counts(subj_civ, subj_slug, opp_civ, opp_slug, cap)
        for k in range(1, rolls + 1):
            plan.append((cap, n1, n2, k))
    print(f"plan: {[(f'{n1}v{n2}', f'roll{k}') for _, n1, n2, k in plan]}", flush=True)

    done, failed = [], []
    for cap, n1, n2, k in plan:
        name = f"scale_{n1}v{n2}_roll{k}.mp4"
        if (out / name).exists():
            print(f"[skip] {name} already recorded", flush=True)
            continue
        print(f"\n===== {name}: {subj_civ}/{subj_slug} ({n1}) vs "
              f"{opp_civ}/{opp_slug} ({n2}), cap={cap} =====", flush=True)
        try:
            clip = run_matchup(subj_civ, subj_slug, opp_civ, opp_slug,
                               name=name, copy_to=str(out), raw_copy_to=str(out),
                               mode="resources", unit_cap=cap, live_overlay=True,
                               build_fn=build_golden_from_sides)
            done.append(name)
            print(f"[record] OK -> {clip}", flush=True)
        except Exception as e:
            failed.append(name)
            print(f"[record] FAILED {name}: {e!r}", flush=True)
            try:
                return_to_editor(str(out / "recover.log"))
            except Exception:
                pass

    print(f"\nALL DONE: {len(done)} recorded, {len(failed)} failed")
    if failed:
        print("failed:", failed)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))
