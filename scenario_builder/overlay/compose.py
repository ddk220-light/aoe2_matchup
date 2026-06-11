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

import os
import subprocess
import tempfile
from pathlib import Path

from overlay.render_card import render_intro, render_outro
from overlay.hud import render_hud_frame
from overlay.ffutil import find_ffmpeg, find_ffprobe


def _ffmpeg() -> str:
    exe = find_ffmpeg()
    if not exe:
        raise RuntimeError("ffmpeg not found.")
    return exe


def _ffprobe() -> str:
    exe = find_ffprobe()
    if not exe:
        raise RuntimeError("ffprobe not found.")
    return exe


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
# 'veryfast' encodes ~8x faster than 'slow' for a negligible quality/size change at
# CRF 17 — the fight segment is the compose bottleneck, so this is the big speed knob.
X264_PRESET = os.environ.get("MATCHUP_PRESET", "veryfast")
# how long the END results card holds on screen after the battle (footage permitting)
RESULTS_HOLD = float(os.environ.get("MATCHUP_RESULTS_HOLD", "3.0"))


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


def _fight_segment_plain(battle_clip: Path, out: Path, size, lead_in: float = 0.0,
                         tail_trim: float = 0.0) -> Path:
    """Battle footage normalized to `size`, KEEPING its captured audio, with NO HUD
    overlay (the no-OCR recap path has no survivor timeline to draw). `lead_in` trims
    the front (menu/load/countdown before the units charge in); `tail_trim` trims the
    end (the idle units-standing tail after the result)."""
    has_a = _has_audio(battle_clip)
    cmd = [_ffmpeg(), "-y"]
    if lead_in and lead_in > 0:
        cmd += ["-ss", f"{lead_in}"]            # input seek: drop the lead-in
    if tail_trim and tail_trim > 0:             # stop early: drop the idle tail
        cmd += ["-t", f"{max(0.5, _duration(battle_clip) - tail_trim - lead_in)}"]
    cmd += ["-i", str(battle_clip)]
    if not has_a:
        cmd += ["-f", "lavfi", "-i", _ANULLSRC]
    cmd += ["-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,"
                   f"pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2",
            "-map", "0:v:0", "-map", ("0:a:0?" if has_a else "1:a")]
    if not has_a:
        cmd += ["-shortest"]
    cmd += [*_x264(), *_AAC, str(out)]
    _run(cmd)
    return out


_FF_FONT = next((p for p in (
    "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf") if os.path.exists(p)), None)


def _duration(path) -> float:
    out = subprocess.run([_ffprobe(), "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def _atempo_chain(f: float) -> str:
    """atempo handles 0.5..2.0 per instance; chain to reach higher speed factors."""
    parts, r = [], f
    while r > 2.0:
        parts.append("atempo=2.0"); r /= 2.0
    parts.append(f"atempo={r:.5f}")
    return ",".join(parts)


def _ff_badge(text: str, out_png: Path) -> Path:
    """Render a 'FAST FORWARD' badge PNG (white text on a translucent pill) to overlay
    on the sped-up segment — this ffmpeg build has no drawtext, so we use PIL + overlay."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype(_FF_FONT, 54) if _FF_FONT else ImageFont.load_default()
    except OSError:
        font = ImageFont.load_default()
    d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    bb = d0.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    px, py = 44, 26
    img = Image.new("RGBA", (tw + 2 * px, th + 2 * py), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=18, fill=(0, 0, 0, 150))
    except AttributeError:
        d.rectangle([0, 0, img.width - 1, img.height - 1], fill=(0, 0, 0, 150))
    d.text((px - bb[0], py - bb[1]), text, font=font, fill=(255, 255, 255, 255))
    img.save(out_png)
    return out_png


def _ff_icon(out_png: Path, scale: float = 1.0) -> Path:
    """A small fast-forward ICON (two white right-pointing triangles on a translucent dark
    pill) — no text, no speed number. Drawn with PIL so it needs no font/drawtext."""
    from PIL import Image, ImageDraw
    s = scale
    pill_h = int(80 * s)
    th = int(40 * s)                 # triangle height
    tw = int(26 * s)                 # triangle width
    gap = int(5 * s)
    padx = int(24 * s)
    pill_w = padx * 2 + tw * 2 + gap
    img = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        d.rounded_rectangle([0, 0, pill_w - 1, pill_h - 1], radius=int(16 * s),
                            fill=(0, 0, 0, 140))
    except AttributeError:
        d.rectangle([0, 0, pill_w - 1, pill_h - 1], fill=(0, 0, 0, 140))
    cy = pill_h // 2
    x = padx
    for _ in range(2):
        d.polygon([(x, cy - th // 2), (x + tw, cy), (x, cy + th // 2)],
                  fill=(255, 255, 255, 240))
        x += tw + gap
    img.save(out_png)
    return out_png


def _fight_segment_ramped(battle_clip: Path, out: Path, size, lead_in: float = 0.0,
                          result_hold: float = 3.5, tail_trim: float = 3.0,
                          max_fight: float = 30.0) -> Path:
    """Battle footage normalized to `size`, capped so the COMBAT is at most `max_fight`
    seconds: a long fight plays first 10s + last 10s at normal speed with the middle
    sped up to 10s (a 'FAST FORWARD' badge marks it), then `result_hold` seconds of the
    who-won result at normal speed. `lead_in` trims the front (menu/load/countdown);
    `tail_trim` trims the idle units-standing tail off the end. Short fights pass
    through (front+tail trimmed). Keeps the captured audio."""
    W, H = size
    D = _duration(battle_clip)
    end = D - tail_trim                                     # drop the idle tail
    fc_dur = end - lead_in - result_hold                    # the combat portion length
    if fc_dur <= max_fight or fc_dur <= 0:
        return _fight_segment_plain(battle_clip, out, size, lead_in=lead_in,
                                    tail_trim=tail_trim)

    has_a = _has_audio(battle_clip)
    speed = (fc_dur - 20.0) / 10.0                          # middle compressed to 10s
    badge = _ff_badge(f"»  FAST FORWARD  »     {speed:.1f}x",
                      out.parent / "_ffbadge.png")
    a0, a1 = lead_in, lead_in + 10.0                        # A first 10s
    b0, b1 = a1, end - result_hold - 10.0                   # B middle (sped up)
    c0, c1 = b1, end - result_hold                          # C last 10s
    d0, d1 = c1, end                                        # D result hold
    # ONE decode + ONE encode: scale, split into the 4 ranges, speed the middle +
    # overlay the badge, concat. Far faster than encoding 4 segments separately.
    vfc = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,split=4[s0][s1][s2][s3];"
        f"[s0]trim={a0}:{a1},setpts=PTS-STARTPTS[va];"
        f"[s1]trim={b0}:{b1},setpts=(PTS-STARTPTS)/{speed:.6f}[vbr];"
        f"[vbr][1:v]overlay=x=(main_w-overlay_w)/2:y=60[vb];"
        f"[s2]trim={c0}:{c1},setpts=PTS-STARTPTS[vc];"
        f"[s3]trim={d0}:{d1},setpts=PTS-STARTPTS[vd];"
        f"[va][vb][vc][vd]concat=n=4:v=1:a=0[v]"
    )
    cmd = [_ffmpeg(), "-y", "-i", str(battle_clip), "-i", str(badge)]
    if has_a:
        afc = (
            f"[0:a]asplit=4[t0][t1][t2][t3];"
            f"[t0]atrim={a0}:{a1},asetpts=PTS-STARTPTS[aa];"
            f"[t1]atrim={b0}:{b1},asetpts=PTS-STARTPTS,{_atempo_chain(speed)}[ab];"
            f"[t2]atrim={c0}:{c1},asetpts=PTS-STARTPTS[ac];"
            f"[t3]atrim={d0}:{d1},asetpts=PTS-STARTPTS[ad];"
            f"[aa][ab][ac][ad]concat=n=4:v=0:a=1[a]"
        )
        cmd += ["-filter_complex", vfc + ";" + afc, "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-filter_complex", vfc, "-map", "[v]",
                "-f", "lavfi", "-i", _ANULLSRC, "-map", "2:a", "-shortest"]
    cmd += [*_x264(), *_AAC, "-movflags", "+faststart", str(out)]
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


def _overlay_hud(battle_clip: Path, hud_dir: str, hud_fps: float, out: Path, size) -> Path:
    """Composite the HUD frame-sequence (live HP bars + counts) onto the FULL battle clip,
    keeping its audio. Done before the lead-in trim + speed-ramp so the burned-in HUD rides
    along with the footage through those transforms. (Used by the legacy recap path; the
    live-overlay path does this inside its single-pass filter graph.)"""
    has_a = _has_audio(battle_clip)
    cmd = [_ffmpeg(), "-y", "-i", str(battle_clip),
           "-framerate", f"{hud_fps}", "-i", str(Path(hud_dir) / "f_%05d.png")]
    if not has_a:
        cmd += ["-f", "lavfi", "-i", _ANULLSRC]
    cmd += ["-filter_complex",
            f"[0:v]scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,"
            f"pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2[v0];"
            f"[1:v]format=rgba[h];[v0][h]overlay=0:0:shortest=1[v]",
            "-map", "[v]", "-map", ("0:a:0?" if has_a else "1:a")]
    if not has_a:
        cmd += ["-shortest"]
    cmd += [*_x264(), *_AAC, str(out)]
    _run(cmd)
    return out


def _sidecar_summary(sidecar, counts=(30, 30)):
    """Final-state summary for the END results card, read from the overlay sidecar:
    {winner: 0|1|2, s1: {start, left, hp}, s2: {...}, true_hp: bool}. `hp` is the
    fraction of the side's starting army HP still standing (with an OCR-only sidecar
    hp == count, so it equals the surviving-units fraction — true_hp says which).
    None if the sidecar can't be read."""
    import json
    try:
        with open(sidecar) as f:
            d = json.load(f)
    except (OSError, ValueError, TypeError):
        return None
    rows = d.get("rows") or []
    if not rows:
        return None
    first, last = rows[0], rows[-1]
    out = {}
    for i, side in ((1, "side1"), (2, "side2")):
        start = int(counts[i - 1] or first[side]["count"])
        hp0 = float(first[side]["hp"]) or 1.0
        left = int(last[side]["count"])
        hp = max(0.0, min(1.0, float(last[side]["hp"]) / hp0)) if left > 0 else 0.0
        out[f"s{i}"] = {"start": start, "left": left, "hp": hp}
    s1, s2 = out["s1"], out["s2"]
    if s1["left"] > 0 and s2["left"] <= 0:
        out["winner"] = 1
    elif s2["left"] > 0 and s1["left"] <= 0:
        out["winner"] = 2
    elif s1["left"] == s2["left"] and abs(s1["hp"] - s2["hp"]) < 0.02:
        out["winner"] = 0
    else:                                   # cap-hit with both alive: HP decides
        out["winner"] = 1 if (s1["hp"], s1["left"]) > (s2["hp"], s2["left"]) else 2
    out["true_hp"] = d.get("source") == "ocr_counts+grpc_hp" or "wall0_epoch" in d
    # fight duration = first sample -> the LAST change in either side's count
    prev, last_change = None, rows[0]["game_s"]
    for r in rows:
        cur = (int(r["side1"]["count"]), int(r["side2"]["count"]))
        if prev is not None and cur != prev:
            last_change = r["game_s"]
        prev = cur
    out["duration_s"] = round(last_change - rows[0]["game_s"], 1)
    return out


def _battle_end_at(sidecar, buffer: float = 2.5):
    """Raw-seconds where the clip should END: ~`buffer`s after the LAST change in either
    side's unit count (the last death = the battle end), read from the sidecar timeline, so
    there's no long idle tail. None if the sidecar can't be read."""
    try:
        import json
        with open(sidecar) as f:
            d = json.load(f)
        rows, vstart = d.get("rows") or [], d.get("video_game_start_s")
        if not rows or vstart is None:
            return None
        prev, last_change_gs = None, rows[0]["game_s"]
        for r in rows:
            cur = (int(r["side1"]["count"]), int(r["side2"]["count"]))
            if prev is not None and cur != prev:
                last_change_gs = r["game_s"]
            prev = cur
        return vstart + last_change_gs + buffer
    except Exception:
        return None


def make_live_overlay_video(u1: dict, u2: dict, out_path, battle_clip, sidecar,
                            lead_in: float, counts=(30, 30), size=(2560, 1440),
                            work_dir=None) -> Path:
    """Single-clip pipeline (no separate intro/outro card screens): the real fight footage
    with a TOP draining army-HP bar (icons + live "cur/start" unit counts + HP%) burned in
    from the `sidecar` timeline, the unit DETAIL cards composited over the opening 10s,
    ramped (10s @1x · middle→5s · last 5s @1x), then a short post-battle HOLD carrying the
    END results card (winner, units left, HP % left — from the same sidecar). Captured
    game audio is preserved.

    The HUD burn-in, trim/speed-ramp, panel + results-card overlays all happen in ONE
    ffmpeg filter graph — a single decode + encode (the old pipeline re-encoded the
    1440p60 footage three times: slower, and generational quality loss at each pass)."""
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="live_"))
    from overlay.overlay_hp import build_hud_frames
    from overlay.render_card import render_unit_panel

    W, H = size
    src = Path(battle_clip).resolve()
    D = _duration(src)
    has_a = _has_audio(src)

    # ---- the clip window: [lead_in, end] of the raw recording -----------------
    end_at = _battle_end_at(sidecar) if sidecar and Path(sidecar).exists() else None
    end = min(end_at, D - 0.2) if end_at is not None else D - 3.0
    end = max(end, lead_in + 2.0)
    combat = end - lead_in
    # Ramp only when the middle can run at >= 2x, and snap the factor to an INTEGER.
    # Fractional speeds (the old floor allowed 1.0-2.0x) make CFR drop frames on an
    # irregular cadence — e.g. 1.2x kills every 6th frame, ~10 tiny jumps per second,
    # which reads as judder exactly where the speedup starts (user-visible; the raw
    # footage is smooth). Integer factors drop uniformly (every 2nd/3rd frame) and
    # look clean; fights with combat <= 25s simply play in full at 1x.
    ramped = combat > 25.0
    speed = max(2, round((combat - 15.0) / 5.0)) if ramped else 1.0

    # ---- END results card + its hold segment ------------------------------------
    # The clip gains a short HOLD after the battle (the armies standing + the in-game
    # WINS line) carrying the results card: winner, units left (x/y), HP % left.
    hud_ok = bool(sidecar and Path(sidecar).exists())
    results_png, hold = None, 0.0
    if hud_ok:
        summary = _sidecar_summary(sidecar, counts)
        if summary:
            try:
                from overlay.render_card import render_results_panel
                results_png = render_results_panel(u1, u2, summary, tmp / "results.png")
            except Exception as e:
                print(f"[overlay] results card skipped: {type(e).__name__}: {e}")
    if results_png is not None:
        hold = min(RESULTS_HOLD, max(0.0, (D - 0.2) - end))
        if hold < 1.5:                       # not enough footage after the battle
            results_png, hold = None, 0.0
    end2 = end + hold

    # ---- inputs (index bookkeeping: optional inputs shift the indices) ---------
    inputs = [["-i", str(src)]]                                   # input 0: the raw clip
    idx = {}
    if hud_ok:
        # band-only HUD frames timed to the RAW clip; blank outside the fight window
        # (kept alive through the hold so the final bar state stays up under the card)
        hud_dir, hud_fps = build_hud_frames(
            str(sidecar), u1, u2, D, tmp / "hud", fps=5.0, size=size,
            t_min=max(0.0, lead_in - 1.0), t_max=end2 + 1.0)
        idx["hud"] = len(inputs)
        inputs.append(["-framerate", f"{hud_fps}", "-i", str(Path(hud_dir) / "f_%05d.png")])
    if ramped:
        icon = _ff_icon(tmp / "_fficon.png", scale=H / 1440.0)
        idx["icon"] = len(inputs)
        inputs.append(["-i", str(icon)])
    panels = None
    try:
        lp = render_unit_panel(u1, u2, tmp / "panel_L.png", side=1, count=counts[0])
        rp = render_unit_panel(u2, u1, tmp / "panel_R.png", side=2, count=counts[1])
        idx["L"], idx["R"] = len(inputs), len(inputs) + 1
        inputs.append(["-loop", "1", "-t", "10.6", "-i", str(lp)])
        inputs.append(["-loop", "1", "-t", "10.6", "-i", str(rp)])
        panels = (lp, rp)
    except Exception as e:
        print(f"[overlay] detail-card overlay skipped: {type(e).__name__}: {e}")
    if results_png is not None:
        idx["res"] = len(inputs)
        inputs.append(["-loop", "1", "-t", f"{hold + 0.2:.2f}", "-i", str(results_png)])
    if not has_a:
        idx["anull"] = len(inputs)
        inputs.append(["-f", "lavfi", "-t", f"{max(1.0, end2 - lead_in)}", "-i", _ANULLSRC])

    # ---- video graph -----------------------------------------------------------
    parts = [f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
             f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2[base]"]
    cur = "[base]"
    if hud_ok:
        parts.append(f"[{idx['hud']}:v]format=rgba[hudv]")
        parts.append(f"{cur}[hudv]overlay=0:0:shortest=1[vh]")
        cur = "[vh]"
    if panels:
        card_w = int(W * 0.30)                  # wide cards, battle visible between them
        pm = int(W * 0.012)                     # side margin
        mb = int(H * 0.025)                     # bottom margin
        prep = f"scale={card_w}:-1,format=rgba,fade=t=out:st=9.4:d=0.6:alpha=1"
        parts.append(f"[{idx['L']}:v]{prep}[Lp]")
        parts.append(f"[{idx['R']}:v]{prep}[Rp]")

    def _with_panels(label_in: str, label_out: str):
        """Overlay the two detail cards (first 10s of FINAL time) onto `label_in`."""
        parts.append(f"{label_in}[Lp]overlay=x={pm}:y=H-h-{mb}:enable='lte(t,10)'[pl1]")
        parts.append(f"[pl1][Rp]overlay=x=W-w-{pm}:y=H-h-{mb}:enable='lte(t,10)'{label_out}")

    # segments: (start, stop, speed) on the raw clock; the hold rides at 1x at the end
    if ramped:
        a0, a1 = lead_in, lead_in + 10.0                    # A: first 10s @1x
        b0, b1 = a1, end - 5.0                              # B: middle (sped to 5s)
        c0, c1 = b1, end                                    # C: last 5s @1x
        ranges = [(a0, a1, 1.0), (b0, b1, speed), (c0, c1, 1.0)]
    else:
        ranges = [(lead_in, end, 1.0)]
    if hold:
        ranges.append((end, end2, 1.0))                     # R: results-card hold @1x
    n_seg = len(ranges)

    if n_seg > 1:
        parts.append(f"{cur}split={n_seg}" + "".join(f"[s{i}]" for i in range(n_seg)))
    else:
        parts.append(f"{cur}null[s0]")
    vlabels = []
    for i, (r0, r1, spd) in enumerate(ranges):
        setpts = "PTS-STARTPTS" if spd == 1.0 else f"(PTS-STARTPTS)/{spd:.6f}"
        parts.append(f"[s{i}]trim={r0}:{r1},setpts={setpts}[vseg{i}]")
        label = f"[vseg{i}]"
        if i == 0 and panels:                               # detail cards on the opening
            _with_panels(label, f"[vp{i}]")
            label = f"[vp{i}]"
        if spd != 1.0:                                      # fast-forward icon on B
            im = int(W * 0.018)
            parts.append(f"{label}[{idx['icon']}:v]overlay="
                         f"x=main_w-overlay_w-{im}:y=main_h-overlay_h-{im}[vf{i}]")
            label = f"[vf{i}]"
        if hold and i == n_seg - 1:                         # results card on the hold
            parts.append(f"[{idx['res']}:v]format=rgba,"
                         f"fade=t=in:st=0.25:d=0.5:alpha=1[resc]")
            parts.append(f"{label}[resc]overlay=x=(main_w-overlay_w)/2:"
                         f"y=(main_h-overlay_h)*0.56[vr{i}]")
            label = f"[vr{i}]"
        vlabels.append(label)
    if n_seg > 1:
        parts.append("".join(vlabels) + f"concat=n={n_seg}:v=1:a=0[v]")
    else:
        parts.append(f"{vlabels[0]}null[v]")

    # ---- audio graph (trimmed/sped to match) ------------------------------------
    if has_a:
        if n_seg > 1:
            parts.append("[0:a]asplit=" + str(n_seg)
                         + "".join(f"[t{i}]" for i in range(n_seg)))
            alabels = []
            for i, (r0, r1, spd) in enumerate(ranges):
                tempo = "" if spd == 1.0 else f",{_atempo_chain(spd)}"
                parts.append(f"[t{i}]atrim={r0}:{r1},asetpts=PTS-STARTPTS{tempo}[aseg{i}]")
                alabels.append(f"[aseg{i}]")
            parts.append("".join(alabels) + f"concat=n={n_seg}:v=0:a=1[a]")
        else:
            r0, r1, _ = ranges[0]
            parts.append(f"[0:a]atrim={r0}:{r1},asetpts=PTS-STARTPTS[a]")
        amap = "[a]"
    else:
        amap = f"{idx['anull']}:a"

    cmd = [_ffmpeg(), "-y"]
    for inp in inputs:
        cmd += inp
    cmd += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", amap]
    if not has_a:
        cmd += ["-shortest"]
    cmd += [*_x264(), *_AAC, "-movflags", "+faststart", str(out_path)]
    _run(cmd)
    return out_path


def make_recap_video(u1: dict, u2: dict, out_path, battle_clip,
                     size=(1920, 1248), intro_seconds=5.0,
                     lead_in: float = 0.0, counts=(30, 30), sidecar=None,
                     work_dir=None) -> Path:
    """No-OCR pipeline: intro stat card -> real fight footage (+ audio). If `sidecar` (the
    gRPC <video>.hp.json) is given, a LIVE HP-bar HUD is composited onto the fight footage.
    The footage ends on the in-game result hold, so there's no outro card."""
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="recap_"))

    intro_png = render_intro(u1, u2, tmp / "intro.png", counts=counts)
    seg_intro = _card_segment(intro_png, intro_seconds, tmp / "seg_intro.mp4",
                              size, card_width_frac=0.94)

    fight_src = Path(battle_clip).resolve()
    if sidecar and Path(sidecar).exists():
        try:
            from overlay.overlay_hp import build_hud_frames
            hud_dir, hud_fps = build_hud_frames(str(sidecar), u1, u2,
                                                _duration(fight_src), tmp / "hud",
                                                fps=5.0, size=size)
            fight_src = _overlay_hud(fight_src, hud_dir, hud_fps, tmp / "battle_hud.mp4", size)
        except Exception as e:
            print(f"[overlay] HUD overlay skipped: {type(e).__name__}: {e}")

    seg_fight = _fight_segment_ramped(Path(fight_src).resolve(), tmp / "seg_fight.mp4",
                                      size, lead_in=lead_in)

    _concat([seg_intro, seg_fight], out_path)
    return out_path


def _concat(segments: list[Path], out: Path) -> Path:
    # the three segments come from this pipeline with identical codec/params, so a
    # stream-copy concat (no re-encode) joins them in a fraction of the time. Falls
    # back to a re-encode automatically (concat_videos) if a param ever drifts.
    return concat_videos(segments, out)


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
    from overlay.overlay_data import get_unit_card
    from overlay.results import extract_sim_results
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
