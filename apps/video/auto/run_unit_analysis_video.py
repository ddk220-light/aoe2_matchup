# apps/video/auto/run_unit_analysis_video.py
"""Turn an analysis storyboard JSON into a stitched unit-analysis video.

  python -m auto.run_unit_analysis_video path/to/storyboard.json --out DIR
  ... --dry-run          # print the plan, touch nothing
  ... --stitch-only      # re-join existing clips + cards

Plan structure (build_plan): a flat list of steps —
  intro -> per category in CATEGORY_ORDER (skipped when it has no segments):
  banner -> N fight specs (queue_runner) -> ranked_card -> ... -> even_card.
Fight recording uses the existing run_matchup pipeline driven by the GOLDEN rig
(build_fn=build_golden_from_sides); cards render via overlay.render_card; the
hi-res/gif intro degrades gracefully when AOE2_MEDIA_DIR is unset
(overlay.assets.AssetResolver).
"""
import argparse
import json
from pathlib import Path

CATEGORY_TITLES = {
    "expected_win": "Expected Win", "unexpected_win": "Unexpected Win",
    "expected_counter": "Expected Counter",
    "unexpected_counter": "Unexpected Counter",
}
CATEGORY_ORDER = ("expected_win", "unexpected_win",
                  "expected_counter", "unexpected_counter")


def build_plan(storyboard_path):
    sb = json.loads(Path(storyboard_path).read_text())
    subj = sb["subject"]
    plan = [{"kind": "intro", "subject": subj}]
    n_cats = len(CATEGORY_ORDER)
    for ci, cat in enumerate(CATEGORY_ORDER, 1):
        segs = [s for s in sb["segments"] if s["category"] == cat]
        if not segs:
            continue
        plan.append({"kind": "banner", "category": cat,
                     "title": f"{CATEGORY_TITLES[cat]}s",
                     "index": ci, "total": n_cats})
        for s in segs:
            plan.append({"kind": "fight", "spec": {
                "civ1": subj["civ"], "slug1": subj["slug"],
                "civ2": s["opponent"]["civ"], "slug2": s["opponent"]["slug"],
                "name": f"{cat}_{s['rank']}_{s['opponent']['slug']}",
                "label": (f"{CATEGORY_TITLES[cat]} #{s['rank']} — "
                          f"{s['opponent']['name']}"),
                "category": cat, "why": s["why"], "score": s["score"],
                "counts": s["counts"],
            }})
        plan.append({"kind": "ranked_card", "category": cat,
                     "title": f"{CATEGORY_TITLES[cat]}s — full ranking",
                     "rows": sb["category_lists"][cat]})
    plan.append({"kind": "even_card",
                 "rows": sb["category_lists"].get("even", [])})
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stitch-only", action="store_true")
    args = ap.parse_args()

    plan = build_plan(args.storyboard)
    if args.dry_run:
        for step in plan:
            label = step.get("spec", {}).get("label") or step.get(
                "title") or step["kind"]
            print(f"{step['kind']:>12}  {label}")
        return

    # Recording/composition half — Windows box with game + media.
    from auto.queue_runner import run_matchup_queue
    from auto.orchestrate_matchup import run_matchup, return_to_editor
    from auto import chapters  # noqa: F401  (stitch step)
    from overlay.assets import AssetResolver  # noqa: F401  (intro step)
    from build_golden_matchups import build_golden_from_sides
    out = Path(args.out)
    fights = [st["spec"] for st in plan if st["kind"] == "fight"]

    def run_one(spec, out_dir):
        # run_matchup writes the finished clip to <copy_to>/<name> and returns it;
        # name=<spec name>.mp4 lands it exactly where the queue's resume-skip looks
        # (out_dir/<name>.mp4). build_fn routes the scenario through the golden rig.
        return run_matchup(spec["civ1"], spec["slug1"],
                           spec["civ2"], spec["slug2"],
                           name=f"{spec['name']}.mp4", copy_to=str(out_dir),
                           mode="resources", live_overlay=True,
                           build_fn=build_golden_from_sides)

    if not args.stitch_only:
        run_matchup_queue(fights, out, run_one=run_one,
                          on_recover=return_to_editor)
    # Card rendering + intro + stitch: compose cards per plan order, build the
    # (label, path) list from the manifest + card segments, then
    # overlay.compose.concat_videos + chapters.write_chapters. Implemented on
    # the Windows checkout where ffmpeg output can actually be verified.
    raise SystemExit("recording plan executed; stitch step runs on Windows — "
                     "see docs/superpowers/specs/2026-07-04-unit-analysis-video-design.md")


if __name__ == "__main__":
    main()
