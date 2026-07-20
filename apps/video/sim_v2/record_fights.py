"""Record specific subject-vs-opponent matchups via the GOLDEN rig (the exact call
run_unit_analysis_video uses per fight), one at a time, returning to the editor
between fights. For diagnostics and targeted re-films where the full storyboard
pipeline is overkill.

Writes <out>/<name>.mp4 + <name>.hp.json per fight. Clip names follow the stitch
convention <category>_<rank>_<oppslug> so run_unit_analysis_video --stitch-only can
reuse them. Run with apps/video/.venv (game must be open in the Scenario Editor,
frontmost).

  python record_fights.py <subj_civ> <subj_slug> <category> <out_dir> \
         <opp_civ>/<opp_slug> [<opp_civ>/<opp_slug> ...]

Example (Kona diagnostic — one expected win + two suspect archer losses):
  python record_fights.py Mapuche elite_kona_mapuche diag OUT \
      Romans/elite_centurion_romans Tupi/elite_blackwood_archer_tupi Britons/elite_longbowman_britons
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))              # apps/video on path (auto, build_run)


def main(argv):
    if len(argv) < 5:
        print(__doc__)
        return 2
    subj_civ, subj_slug, category, out_dir = argv[:4]
    opps = argv[4:]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    from auto.orchestrate_matchup import run_matchup, return_to_editor
    # 2026-07-19: records on the FINAL golden engagement templates (panda map,
    # ddkMatchupAI patrol + NoneAi). The old build_golden_matchups adapter used
    # the retired 2026-07-05 flat template — do not switch back.
    from build_golden_v2 import build_v2_from_sides as build_golden_from_sides

    results = []
    for rank, spec in enumerate(opps, 1):
        opp_civ, opp_slug = spec.split("/", 1)
        name = f"{category}_{rank}_{opp_slug}.mp4"
        print(f"\n===== RECORD {rank}/{len(opps)}: {subj_civ}/{subj_slug} vs "
              f"{opp_civ}/{opp_slug}  -> {name} =====", flush=True)
        try:
            clip = run_matchup(subj_civ, subj_slug, opp_civ, opp_slug,
                               name=name, copy_to=str(out), raw_copy_to=str(out),
                               mode="resources", unit_cap=21, live_overlay=True,
                               build_fn=build_golden_from_sides)
            results.append((name, str(clip)))
            print(f"[record] OK -> {clip}", flush=True)
        except Exception as e:
            print(f"[record] FAILED {name}: {e!r}", flush=True)
            try:
                return_to_editor()
            except Exception:
                pass
            results.append((name, None))
    print("\n===== DONE =====")
    for n, c in results:
        print(f"  {'OK ' if c else '!! '} {n}  {c or 'FAILED'}")
    return 0 if all(c for _, c in results) else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))
