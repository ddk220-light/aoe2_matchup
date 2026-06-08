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

from render_card import render_intro, render_outro, render_outro_recap
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


def _ffprobe() -> str:
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    # derive from the ffmpeg path (ffprobe sits beside ffmpeg)
    fp = _ffmpeg()
    return fp.replace("ffmpeg.exe", "ffprobe.exe") if fp.endswith(".exe") \
        else fp[::-1].replace("ffmpeg"[::-1], "ffprobe"[::-1], 1)[::-1]


def _has_audio(path) -> bool:
    """True if `path` has at least one audio stream."""
    p = subprocess.run([_ffprobe(), "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return bool(p.stdout.strip())


# silent stereo 48k source — gives the (silent) intro/outro cards an audio track so
# the final concat can mux one continuous audio stream across all segments.
_ANULLSRC = "anullsrc=channel_layout=stereo:sample_rate=48000"
_AAC = ["-c:a", "aac", "-ar", "48000", "-ac", "2"]


def _run(cmd: list):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + p.stderr[-1500:])
    return p


# Output quality knobs (env-overridable for quick experiments).
OUT_FPS = int(os.environ.get("MATCHUP_FPS", "60"))       # smoother motion
X264_CRF = os.environ.get("MATCHUP_CRF", "17")           # lower = higher quality
X264_PRESET = os.environ.get("MATCHUP_PRESET", "slow")   # better compression/quality


def _x264() -> list:
    """High-quality libx264 output args."""
    return ["-c:v", "libx264", "-preset", X264_PRESET, "-crf", X264_CRF,
            "-pix_fmt", "yuv420p", "-r", str(OUT_FPS)]


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
          "-f", "lavfi", "-t", f"{seconds}", "-i", _ANULLSRC,  # silent audio track
          "-filter_complex",
          f"[1:v]scale={target_w}:-1,format=rgba,"
          f"fade=t=in:st=0:d={fade}:alpha=1,"
          f"fade=t=out:st={seconds-fade}:d={fade}:alpha=1[c];"
          f"[0:v][c]overlay=(W-w)/2:(H-h)/2:format=auto[v]",
          "-map", "[v]", "-map", "2:a", *_x264(), *_AAC, str(out)])
    return out


def _fight_segment(battle_clip: Path, hud_dir: Path, hud_fps: float,
                   out: Path, size) -> Path:
    """Battle footage with the live HUD frame-sequence overlaid, KEEPING the
    battle clip's audio (the captured game sound). Falls back to a silent track
    if the clip has no audio (e.g. the synthesized placeholder)."""
    has_a = _has_audio(battle_clip)
    cmd = [_ffmpeg(), "-y",
           "-i", str(battle_clip),
           "-framerate", f"{hud_fps}", "-i", str(hud_dir / "f_%05d.png")]
    if not has_a:
        cmd += ["-f", "lavfi", "-i", _ANULLSRC]
    cmd += ["-filter_complex",
            "[1:v]format=rgba[hud];[0:v][hud]overlay=0:0:shortest=1[v]",
            "-map", "[v]", "-map", ("0:a:0" if has_a else "2:a"),
            # match audio length to the (HUD-bounded) video
            "-shortest", *_x264(), *_AAC, str(out)]
    _run(cmd)
    return out


def _fight_segment_plain(battle_clip: Path, out: Path, size, lead_in: float = 0.0) -> Path:
    """Battle footage normalized to `size`, KEEPING its captured audio, with NO HUD
    overlay (the no-OCR recap path has no survivor timeline to draw). `lead_in` trims
    that many seconds off the front (skip the menu/load before the fight)."""
    has_a = _has_audio(battle_clip)
    cmd = [_ffmpeg(), "-y"]
    if lead_in and lead_in > 0:
        cmd += ["-ss", f"{lead_in}"]            # input seek: drop the lead-in
    cmd += ["-i", str(battle_clip)]
    if not has_a:
        cmd += ["-f", "lavfi", "-i", _ANULLSRC]
    cmd += ["-vf", f"scale={size[0]}:{size[1]}",
            "-map", "0:v:0", "-map", ("0:a:0?" if has_a else "1:a")]
    if not has_a:
        cmd += ["-shortest"]
    cmd += [*_x264(), *_AAC, str(out)]
    _run(cmd)
    return out


def concat_videos(paths, out_path) -> Path:
    """Join several finished mp4s into one. They all come from this pipeline (same
    codec/size/fps/audio), so try a fast stream-copy concat first; fall back to a
    re-encode if the demuxer balks at any parameter drift."""
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    paths = [str(Path(p).resolve()) for p in paths]
    fd, listf = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    try:
        sc = subprocess.run(
            [_ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", listf,
             "-c", "copy", "-movflags", "+faststart", str(out_path)],
            capture_output=True, text=True)
        if sc.returncode != 0 or not out_path.exists():
            inputs = []
            for p in paths:
                inputs += ["-i", p]
            streams = "".join(f"[{i}:v][{i}:a]" for i in range(len(paths)))
            _run([_ffmpeg(), "-y", *inputs, "-filter_complex",
                  f"{streams}concat=n={len(paths)}:v=1:a=1[v][a]",
                  "-map", "[v]", "-map", "[a]", *_x264(), *_AAC,
                  "-movflags", "+faststart", str(out_path)])
    finally:
        try:
            os.unlink(listf)
        except OSError:
            pass
    return out_path


def make_recap_video(u1: dict, u2: dict, out_path, battle_clip,
                     size=(1920, 1248), intro_seconds=5.0, outro_seconds=5.0,
                     lead_in: float = 0.0, work_dir=None) -> Path:
    """No-OCR pipeline: intro stat card -> real fight footage (+ audio) -> recap card.
    No live HUD, no survivor counts — just the matchup bookends around the real fight."""
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="recap_"))

    intro_png = render_intro(u1, u2, tmp / "intro.png")
    outro_png = render_outro_recap(u1, u2, tmp / "outro.png")

    seg_intro = _card_segment(intro_png, intro_seconds, tmp / "seg_intro.mp4",
                              size, card_width_frac=0.94)
    seg_fight = _fight_segment_plain(Path(battle_clip).resolve(), tmp / "seg_fight.mp4",
                                     size, lead_in=lead_in)
    seg_outro = _card_segment(outro_png, outro_seconds, tmp / "seg_outro.mp4",
                              size, card_width_frac=0.74)

    _concat([seg_intro, seg_fight, seg_outro], out_path)
    return out_path


def _concat(segments: list[Path], out: Path) -> Path:
    n = len(segments)
    inputs = []
    for s in segments:
        inputs += ["-i", str(s)]
    # every segment carries one video + one audio stream (cards silent, fight real)
    streams = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    _run([_ffmpeg(), "-y", *inputs,
          "-filter_complex", f"{streams}concat=n={n}:v=1:a=1[v][a]",
          "-map", "[v]", "-map", "[a]", *_x264(), *_AAC,
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
