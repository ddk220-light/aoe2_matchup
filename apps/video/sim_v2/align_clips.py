"""Rename already-recorded fight clips to match a (re-categorized) storyboard, so
run_unit_analysis_video --stitch-only finds them under their corrected category.

A clip's content is category-agnostic (it shows the real fight + gRPC HP overlay), so
when a matchup moves category after in-game correction we just RENAME the .mp4 + .hp.json
to the name the new storyboard expects — no need to re-record.

The stitch expects each segment's clip at <film_category>_<rank>_<opponent_slug>.mp4
(see auto.run_unit_analysis_video.build_plan). We match an existing clip to a segment by
its opponent SLUG (ignoring the old category/rank prefix) and rename to the new name.

  python align_clips.py <storyboard.json> <clip_dir>

Prints the rename plan, the segments still missing a clip (need recording), and any
orphaned clips (recorded but not in the storyboard).
"""
import json
import re
import sys
from pathlib import Path

PREFIX = re.compile(
    r"^(expected_win|unexpected_win|expected_counter|unexpected_counter|newpick|diag2?"
    r"|gdiag|g2|even)"
    r"_\d+_(.+)$")
FILM_ORDER = ("expected_win", "unexpected_win", "expected_counter", "unexpected_counter")


def _slug_of(stem):
    m = PREFIX.match(stem)
    return m.group(2) if m else stem


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    sb = json.loads(Path(argv[0]).read_text())
    d = Path(argv[1])

    # index existing clips by opponent slug
    clips = {}
    for f in d.glob("*.mp4"):
        clips.setdefault(_slug_of(f.stem), []).append(f)

    segs = sorted(sb["segments"],
                  key=lambda s: (FILM_ORDER.index(s["category"]) if s["category"] in FILM_ORDER else 9,
                                 s["rank"]))
    used, missing, renames = set(), [], []
    for s in segs:
        slug = s["opponent"]["slug"]
        want = f"{s['category']}_{s['rank']}_{slug}"
        cand = [f for f in clips.get(slug, []) if f not in used]
        if not cand:
            missing.append((s["category"], s["rank"], s["opponent"]["civ"], slug))
            continue
        src = cand[0]
        used.add(src)
        if src.stem != want:
            renames.append((src, want))

    print(f"storyboard: {len(segs)} filmed segments; {len(clips)} recorded slugs")
    # perform renames (mp4 + .hp.json sidecar)
    for src, want in renames:
        for suffix in (".mp4", ".hp.json"):
            old = src.with_name(src.stem + suffix)
            new = d / (want + suffix)
            if old.exists():
                old.replace(new)
        print(f"  renamed  {src.stem}  ->  {want}")
    if not renames:
        print("  (no renames needed)")
    if missing:
        print(f"\nMISSING clips (record these):")
        for cat, rank, civ, slug in missing:
            print(f"  {cat} #{rank}  {civ}/{slug}")
    used_stems = {f.stem for f in used}
    orphans = [f.stem for f in d.glob("*.mp4")
               if _slug_of(f.stem) not in {s["opponent"]["slug"] for s in segs}]
    if orphans:
        print(f"\norphaned clips (not in storyboard, ignored by stitch): {len(orphans)}")
    return 0 if not missing else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))
