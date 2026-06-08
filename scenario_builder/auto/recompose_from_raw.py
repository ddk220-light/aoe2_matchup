"""recompose_from_raw.py — rebuild matchup clips from the raw recordings with a
corrected clip-start, WITHOUT re-running the game.

The live macro starts the clip a fixed offset after a wall-clock game-start guess,
which drifted late (into the fighting). The raw `.mov` recordings are kept, so we
can detect game-start FRAME-ACCURATELY in each recording (the on-screen title/readout
'N vs M' first appearing) and start the clip `PATROL_LEAD` seconds after that — landing
on the charge-in, past the ~2s camera pan, before contact.

Re-composes a `--list` sweep (opponent vs each entry) into per-clip mp4s and an
optional joined video + chapters, reading the raw clips from --raw-glob.

  python -m auto.recompose_from_raw \
      --list auto/unique_units.json --opponent "Muisca:elite_temple_guard_muisca" \
      --raw "/tmp/auto_fight_{i}.mov" --out "/tmp/auto_matchup_{i}.mp4" \
      --copy-to "/Volumes/Orchid/AOEII_videos/3kResMatchUpVideos" \
      --join "Temple Guard vs All Uniques (resources).mp4" --resources
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SB = HERE.parent
sys.path.insert(0, str(SB))
sys.path.insert(0, str(SB / "overlay"))

from auto import platform_io                                   # noqa: E402
from auto.orchestrate_matchup import resolve_side, equal_resource_counts  # noqa: E402
from auto.record_until_end import log, detect_game_start, PATROL_LEAD     # noqa: E402
from auto.batch_matchups import _civ_adj, write_chapters       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", dest="list_path", required=True)
    ap.add_argument("--opponent", required=True, metavar="CIV:slug")
    ap.add_argument("--raw", required=True, help="raw clip path with {i}, e.g. /tmp/auto_fight_{i}.mov")
    ap.add_argument("--out", required=True, help="per-clip out path with {i}")
    ap.add_argument("--resources", action="store_true")
    ap.add_argument("--unit-cap", type=int, default=30)
    ap.add_argument("--copy-to", default=None)
    ap.add_argument("--join", default=None)
    ap.add_argument("--slice", default=None)
    ap.add_argument("--log", default=str(Path(platform_io.TMP_DIR) / "recompose.log"))
    a = ap.parse_args()
    open(a.log, "w").close()

    from overlay_data import get_unit_card
    from compose import make_recap_video, concat_videos, _duration
    from auto.batch_matchups import _slice_1based

    entries = json.loads(Path(a.list_path).read_text())
    lo, hi = _slice_1based(a.slice, len(entries))
    opp_civ, opp_slug = a.opponent.split(":", 1)

    clips, chapters, results = [], [], []
    for idx in range(lo, hi):
        i = idx + 1                                   # raw clips are 1-indexed by sweep order
        e = entries[idx]
        raw = Path(a.raw.format(i=i))
        out = Path(a.out.format(i=i))
        if not raw.exists():
            log(f"[{i}] SKIP — raw clip missing: {raw}", a.log); continue
        try:
            counts = (equal_resource_counts(opp_civ, opp_slug, e["civ"], e["slug"], a.unit_cap)
                      if a.resources else (a.unit_cap, a.unit_cap))
            u1 = get_unit_card(opp_civ, opp_slug)
            u2 = get_unit_card(e["civ"], e["slug"])
            gs = detect_game_start(raw)
            lead_in = (gs + PATROL_LEAD) if gs is not None else 7.0
            make_recap_video(u1, u2, out, battle_clip=raw, lead_in=lead_in, counts=counts)
            log(f"[{i}] {e['civ']} {e['name']}  game_start={gs}  lead_in={lead_in:.1f}  -> {out.name}", a.log)
            clips.append(str(out))
            chapters.append((f"{_civ_adj(e['civ'])} {e['name'].replace('Elite ', '')}", str(out)))
            results.append((e["name"], "OK"))
        except Exception as ex:
            log(f"[{i}] FAILED: {ex}", a.log)
            results.append((e["name"], f"FAILED: {ex}"))

    if a.join and clips:
        log(f"[join] {len(clips)} clips -> {a.join}", a.log)
        joined = concat_videos(clips, str(Path(platform_io.TMP_DIR) / "joined_recompose.mp4"))
        if a.copy_to:
            Path(a.copy_to).mkdir(parents=True, exist_ok=True)
            shutil.copy2(joined, Path(a.copy_to) / a.join)
            ch = write_chapters([(lbl, _duration(c)) for lbl, c in chapters],
                                Path(a.copy_to) / f"{Path(a.join).stem} chapters.txt")
            log(f"[join] -> {Path(a.copy_to) / a.join}   chapters -> {ch}", a.log)
    ok = sum(1 for _, s in results if s == "OK")
    log(f"=== RECOMPOSE COMPLETE — {ok}/{len(results)} ===", a.log)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
