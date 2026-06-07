"""
compose.py — assemble the full matchup video with ffmpeg:

    [intro card, fade] -> [battle footage + LIVE HUD] -> [outro results card]

The live HUD is driven by a MatchResult.timeline (from results.py): one Pillow
HUD frame per timeline sample, sequenced as a transparent video and overlaid on
the battle footage so survivor counts / HP bars tick down in sync.

No real battle clip yet? `demo()` synthesizes a placeholder field clip matching
the sim duration so the whole thing can be produced and reviewed offline. When
recording works, pass the real clip as `battle_clip=`.

Requires ffmpeg (+ffprobe) on PATH.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from render_card import render_intro, render_outro
from hud import render_hud_frame


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    hits = glob.glob(os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\ffmpeg.exe"),
        recursive=True)
    if hits:
        return hits[0]
    raise RuntimeError("ffmpeg not found.")


def _run(cmd: list):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + p.stderr[-1500:])
    return p


def make_placeholder_clip(out, seconds, size=(1280, 720)) -> Path:
    out = Path(out).resolve()
    w, h = size
    _run([_ffmpeg(), "-y", "-f", "lavfi",
          "-i", f"color=c=0x33401c:s={w}x{h}:d={seconds}:r=30",
          "-vf", "noise=alls=8:allf=t",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)])
    return out


def _card_segment(card_png: Path, seconds: float, out: Path, size, *,
                  card_width_frac: float, bg="0x12100b") -> Path:
    """A standalone clip: card fades in/out, centered over a dark background."""
    w, h = size
    target_w = int(w * card_width_frac)
    fade = 0.4
    _run([_ffmpeg(), "-y",
          "-f", "lavfi", "-i", f"color=c={bg}:s={w}x{h}:d={seconds}:r=30",
          "-loop", "1", "-t", f"{seconds}", "-i", str(card_png),
          "-filter_complex",
          f"[1:v]scale={target_w}:-1,format=rgba,"
          f"fade=t=in:st=0:d={fade}:alpha=1,"
          f"fade=t=out:st={seconds-fade}:d={fade}:alpha=1[c];"
          f"[0:v][c]overlay=(W-w)/2:(H-h)/2:format=auto[v]",
          "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
          str(out)])
    return out


def _fight_segment(battle_clip: Path, hud_dir: Path, hud_fps: float,
                   out: Path, size) -> Path:
    """Battle footage with the live HUD frame-sequence overlaid."""
    _run([_ffmpeg(), "-y",
          "-i", str(battle_clip),
          "-framerate", f"{hud_fps}", "-i", str(hud_dir / "f_%05d.png"),
          "-filter_complex", "[1:v]format=rgba[hud];[0:v][hud]overlay=0:0:shortest=1[v]",
          "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
          str(out)])
    return out


def _concat(segments: list[Path], out: Path) -> Path:
    n = len(segments)
    inputs = []
    for s in segments:
        inputs += ["-i", str(s)]
    streams = "".join(f"[{i}:v]" for i in range(n))
    _run([_ffmpeg(), "-y", *inputs,
          "-filter_complex", f"{streams}concat=n={n}:v=1:a=0[v]",
          "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
          "-movflags", "+faststart", str(out)])
    return out


def make_matchup_video(result, u1: dict, u2: dict, out_path,
                       battle_clip=None, size=(1280, 720),
                       intro_seconds=4.5, outro_seconds=5.0,
                       work_dir=None) -> Path:
    """Produce intro -> fight(+live HUD) -> outro. `result` is a results.MatchResult."""
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="matchup_"))
    hud_dir = tmp / "hud"
    hud_dir.mkdir(parents=True, exist_ok=True)

    # 1. intro + outro cards
    intro_png = render_intro(u1, u2, tmp / "intro.png")
    outro_png = render_outro(result, u1, u2, tmp / "outro.png")

    # 2. live HUD frames from the timeline
    tl = result.timeline
    for i, row in enumerate(tl):
        frame = render_hud_frame(
            u1["name"], u1["icon"], result.start1, row["s1"], row["hp1"],
            u2["name"], u2["icon"], result.start2, row["s2"], row["hp2"],
            t=row["t"], size=size)
        frame.save(hud_dir / f"f_{i:05d}.png")
    fight_dur = max(1.0, result.duration_s)
    hud_fps = max(1.0, len(tl) / fight_dur)

    # 3. battle footage (placeholder if none supplied)
    battle = Path(battle_clip).resolve() if battle_clip else \
        make_placeholder_clip(tmp / "battle.mp4", fight_dur, size)

    # 4. segments
    seg_intro = _card_segment(intro_png, intro_seconds, tmp / "seg_intro.mp4",
                              size, card_width_frac=0.94)
    seg_fight = _fight_segment(battle, hud_dir, hud_fps, tmp / "seg_fight.mp4", size)
    seg_outro = _card_segment(outro_png, outro_seconds, tmp / "seg_outro.mp4",
                              size, card_width_frac=0.74)

    # 5. concat
    _concat([seg_intro, seg_fight, seg_outro], out_path)
    return out_path


def demo():
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from overlay_data import get_unit_card
    from results import extract_sim_results
    s = Path(__file__).parent / "samples"
    s.mkdir(exist_ok=True)
    u1 = get_unit_card("Wu", "elite_fire_archer_wu")
    u2 = get_unit_card("Wu", "jian_swordsman_wu")
    res = extract_sim_results("Wu", "elite_fire_archer_wu", "Wu", "jian_swordsman_wu")
    out = make_matchup_video(res, u1, u2, s / "firearcher_vs_jian_full.mp4")
    print("WROTE", out, f"({out.stat().st_size//1024} KB)  result: team{res.winner} "
          f"{res.survivors1}-{res.survivors2}")
    return out


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    demo()
