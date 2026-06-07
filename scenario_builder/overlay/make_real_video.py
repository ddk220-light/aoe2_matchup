"""Build a titled matchup video from a REAL AoE2:DE recording.

Pipeline: OCR the in-game survivor readout -> trim the clip to the fight ->
compose intro stat-card -> fight footage + live HUD -> outro result card.

This is matchup-agnostic: give it any recording + the two civ/unit slugs.

Usage:
  python make_real_video.py <recording.mkv> <civ1> <slug1> <civ2> <slug2> [out.mp4]
Defaults to the Fire Archer vs Jian (Wu) demo if no args.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from overlay_data import get_unit_card          # noqa: E402
from video_extract import extract_video_results  # noqa: E402
from compose import make_matchup_video, _ffmpeg   # noqa: E402

SIZE = (1920, 1248)  # everything (cards, HUD, fight) normalized to this.
# 1920x1248 keeps the 2940x1912 capture aspect (1.538) — no squish — and is a big
# quality bump over the old 1280x720 (which downscaled AND squished). Native 2940x1912
# can't sustain a high capture framerate (drops to ~11fps in busy fights), so we record
# scaled to 1920-wide @60fps; this stays smooth.


def make_real_matchup_video(recording, civ1, slug1, civ2, slug2, out_path,
                            end_pad=1.5, work_dir=None) -> Path:
    recording = Path(recording).resolve()
    result = extract_video_results(str(recording), civ1=civ1, slug1=slug1,
                                   civ2=civ2, slug2=slug2)
    names = {1: f"{slug1}", 2: f"{slug2}", 0: "draw"}
    print(f"OCR  start {result.start1} vs {result.start2}  ->  final "
          f"{result.survivors1}-{result.survivors2}  winner={names[result.winner]}  "
          f"fight window {result.fight_start_s:.1f}-{result.fight_end_s:.1f}s")

    # Trim the recording to the fight (output-seek = frame-accurate) and normalize
    # to SIZE so it matches the cards + HUD. HUD timeline is re-based to the fight
    # start, so trimming from fight_start_s keeps them aligned.
    tmp = Path(work_dir) if work_dir else recording.parent
    fight = tmp / "_fight_trim.mp4"
    subprocess.run(
        [_ffmpeg(), "-y", "-i", str(recording),
         "-ss", f"{result.fight_start_s}", "-to", f"{result.fight_end_s + end_pad}",
         # keep the captured game audio (optional — placeholder/silent clips have none)
         "-map", "0:v:0", "-map", "0:a:0?",
         "-vf", f"scale={SIZE[0]}:{SIZE[1]}", "-c:v", "libx264", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-ar", "48000", "-ac", "2",
         str(fight)],
        check=True, capture_output=True)

    u1 = get_unit_card(civ1, slug1)
    u2 = get_unit_card(civ2, slug2)
    out = make_matchup_video(result, u1, u2, out_path, battle_clip=str(fight), size=SIZE)
    print("WROTE", out, f"({Path(out).stat().st_size // 1024} KB)")
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    rec = a[0] if len(a) > 0 else "/tmp/battle2.mkv"
    civ1 = a[1] if len(a) > 1 else "Wu"
    slug1 = a[2] if len(a) > 2 else "elite_fire_archer_wu"
    civ2 = a[3] if len(a) > 3 else "Wu"
    slug2 = a[4] if len(a) > 4 else "jian_swordsman_wu"
    out = a[5] if len(a) > 5 else str(Path(__file__).parent / "samples" / "firearcher_vs_jian_REAL.mp4")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    make_real_matchup_video(rec, civ1, slug1, civ2, slug2, out)
