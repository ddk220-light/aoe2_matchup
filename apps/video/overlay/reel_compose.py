"""reel_compose.py — assemble a vertical (9:16) short-form unit-analysis reel.

    [intro hero] -> [fight A] -> [fight B] -> [CTA]

Each fight is one SINGLE-PASS ffmpeg graph (mirrors compose.make_live_overlay_video):
the raw 16:9 footage is fit-to-width into the middle of a 1080x1920 canvas (NEVER
cropped — the armies are column-seated at the arena edges), the live HP band is overlaid
into the bottom band, the subject/verdict TOP band + 'why' caption are composited, then
a TIGHT integer speed-ramp trims the whole thing to ~5s. Segments stream-copy-concat
because they share codec/size/fps/audio with the intro/CTA cards.

Reuses the overlay stack: overlay_hp.build_hud_frames (HP band), compose.* (ffmpeg
helpers, ramp/atempo, concat, card segments), reel_cards (Pillow bands).
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from overlay import reel_cards
from overlay.overlay_hp import build_hud_frames
from overlay.hud import hud_band_height
from overlay.compose import (
    _ffmpeg, _ffprobe, _run, _duration, _has_audio, _x264, _AAC, _ANULLSRC,
    _atempo_chain, _ff_icon, _card_segment, _battle_end_at, concat_videos, voice_track,
)

# ---- vertical canvas geometry (1080x1920) --------------------------------------
CANVAS = (1080, 1920)
TOP_H = 420             # top band: verdict chip + hero-vs-competitor icons/names
GAME_Y = TOP_H          # gameplay top edge
# Zoom: crop the tree ring off the golden arena so the battlefield fills the frame —
# 1/ZOOM_X of the source width and 1/ZOOM_Y of its height, centre-biased slightly UP
# (the arena centre sits a touch above frame centre on the panda map). The horizontal
# crop is deeper than the vertical so the gameplay band also gets TALLER on the canvas.
ZOOM_X = 1.52
ZOOM_Y = 1.30
CROP_Y_BIAS = 0.45      # fraction of the spare height removed from the top
# The gameplay crop window, USER-CALIBRATED on the golden arena template: the red box
# the user marked on a v6 frame (2026-07-25), mapped through v6's TRUE rendered geometry
# (recovered by pixel-matching the output against the raw — v6's coded x was clamped by
# the cx-shadowing bug, so the box must be mapped via the clamped window, x0=480):
# source x [480,2344] y [104,1334] of 2560x1440, stored as fractions so any capture
# resolution scales. Left edge = "same as before" per the user — the armies clash
# against it, it must not creep right. Set to None to fall back to the sand-detection
# (_arena_crop) for non-golden maps.
ARENA_WINDOW = (0.1875, 0.0722, 0.7281, 0.8542)
# Virtual height fed to build_hud_frames. The band is authored for a 2560-wide frame, so
# at 1080 the name tabs are proportionally huge and collided ("Temple G|Battle Elephant"
# overlapped at 2016 -> sc 1.4). 1680 -> sc ~1.17 keeps them clear of the centre plate.
HUD_VSCALE = 1680
WHY_H = 430             # caption strip height (manual mode, no stats panel)

# ---- tight reel ramp (seconds) -------------------------------------------------
LEAD_KEEP = 1.3         # keep the clash at 1x
TAIL_KEEP = 1.6         # keep the kill at 1x
MID_TARGET = 2.2        # sprint the middle to ~this long
END_BUFFER = 1.2        # seconds after the last death the clip holds

INTRO_S = 2.6
CTA_S = 2.2


def _ramp_ranges_long(lead_in: float, end: float):
    """The LONG-FORM pacing, verbatim from compose.make_live_overlay_video: fights under
    25s play straight through, longer ones keep the first 10s and last 5s at 1x and sprint
    the middle at an INTEGER factor toward ~5s. Used by the per-category short so a fight
    runs at exactly the length it has in the YouTube cut — no extra tightening on top."""
    combat = end - lead_in
    if combat <= 25.0:
        return [(lead_in, end, 1.0)]
    speed = float(max(2, round((combat - 15.0) / 5.0)))
    return [(lead_in, lead_in + 10.0, 1.0),
            (lead_in + 10.0, end - 5.0, speed),
            (end - 5.0, end, 1.0)]


def _ramp_ranges(lead_in: float, end: float):
    """(start, stop, speed) tuples on the raw clock. Short fights play 1x; long fights
    keep the clash + kill at 1x and sprint the middle at an INTEGER factor (anti-judder,
    same rule as the long-form)."""
    combat = end - lead_in
    if combat <= LEAD_KEEP + TAIL_KEEP + 1.0:
        return [(lead_in, end, 1.0)]
    raw_mid = combat - LEAD_KEEP - TAIL_KEEP
    speed = float(max(2, round(raw_mid / MID_TARGET)))
    return [(lead_in, lead_in + LEAD_KEEP, 1.0),
            (lead_in + LEAD_KEEP, end - TAIL_KEEP, speed),
            (end - TAIL_KEEP, end, 1.0)]


def _gif_png_seq(gif_path, out_dir: Path, total_s: float):
    """Expand a looping gif into `total_s` seconds of RGBA PNG frames at its native
    frame timing. Returns (dir, fps) or (None, 0) on an unreadable gif."""
    from overlay.intro_card import _gif_frames
    try:
        frames = _gif_frames(Path(gif_path))
    except Exception:
        return None, 0
    if not frames:
        return None, 0
    dur_ms = frames[0][1] or 50
    fps = max(5, min(30, int(round(1000.0 / dur_ms))))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = int(total_s * fps) + 2
    for i in range(n):
        frames[i % len(frames)][0].convert("RGBA").save(out_dir / f"f_{i:05d}.png")
    return out_dir, fps


def _arena_crop(src, t_sample: float, iw: int, ih: int, work: Path):
    """Detect the battlefield's crop box from an actual fight frame, so the zoom trims
    the tree-lined diamond TIPS and nothing else. The arena diamond spans the full
    frame tip-to-tip, so a blind centre crop (v5) cut into sand — and into the army
    whenever the fight drifted off-centre (2026-07-25 Karambit report).

    Method: sample a mid-fight frame, mask sand-coloured pixels (tan: r>g>b with wide
    margins), and keep the columns/rows whose sand density is over 30% of the peak —
    the narrow tips fall below that naturally. Returns (x, y, w, h) with margin, or
    None (caller falls back to the fixed ZOOM crop) when detection degenerates, e.g.
    on a different map without a sand ground."""
    frame = Path(work) / "arena_probe.png"
    try:
        _run([_ffmpeg(), "-y", "-ss", f"{t_sample:.2f}", "-i", str(src),
              "-frames:v", "1", str(frame)])
        im = Image.open(frame).convert("RGB")
    except Exception:
        return None
    s = 4
    sm = im.resize((iw // s, ih // s))
    px = sm.load()
    w, h = sm.size
    cols, rows = [0] * w, [0] * h
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            if (150 < r < 245 and 110 < g < 205 and 60 < b < 165
                    and r > g > b and (r - b) > 45 and (r - g) > 15):
                cols[x] += 1
                rows[y] += 1
    mc, mr = max(cols), max(rows)
    if mc < h * 0.25 or mr < w * 0.25:          # not a sand map — bail out
        return None

    def bounds(arr, peak):
        idx = [i for i, v in enumerate(arr) if v > peak * 0.30]
        return idx[0], idx[-1]

    x0, x1 = bounds(cols, mc)
    y0, y1 = bounds(rows, mr)
    m = 24                                       # safety margin, source px
    x0, y0 = max(0, x0 * s - m), max(0, y0 * s - m)
    x1, y1 = min(iw, x1 * s + m), min(ih, y1 * s + m)
    if (x1 - x0) < iw * 0.5 or (y1 - y0) < ih * 0.5:   # degenerate box
        return None
    return x0, y0, (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2


def _src_dims(path) -> tuple[int, int]:
    p = subprocess.run([_ffprobe(), "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of", "csv=p=0",
                        str(path)], capture_output=True, text=True)
    w, h = p.stdout.strip().split(",")[:2]
    return int(w), int(h)


def make_reel_fight(raw_clip, sidecar, out_path, u1, u2, subj_slug, *,
                    verdict_kind, why="", lead_in, work_dir=None,
                    pacing="reel", panel=None) -> Path:
    """One vertical fight segment. u1 = subject (side1), u2 = opponent (side2).

    pacing="reel" trims the fight to ~5s; pacing="long" uses the YouTube cut's own
    ramp so the fight runs at full length with no extra speed-up.
    panel = {"hero": {name, cd}, "opp": {name, cd}, "n1", "n2"}: render the
    stats/time-to-kill comparison panel under the HP band (the 'why' moves into it);
    without it the old caption strip is used."""
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="reelfight_"))
    tmp.mkdir(parents=True, exist_ok=True)
    W, H = CANVAS
    src = Path(raw_clip).resolve()
    D = _duration(src)
    has_a = _has_audio(src)
    iw, ih = _src_dims(src)

    # gameplay geometry: the calibrated arena window gives x; the design's fixed
    # 1080x562 window dictates the aspect, so the vertical take is the centre of the
    # calibrated y-range at that ratio (trims the top/bottom tree lines evenly, keeps
    # the user's x calibration exactly).
    G = reel_cards.GEOM
    if ARENA_WINDOW is not None:
        fx, fy, fw, fh = ARENA_WINDOW
        cx = int(iw * fx)
        cw = int(iw * fw) // 2 * 2
        full_cy, full_ch = int(ih * fy), int(ih * fh) // 2 * 2
    else:
        end_probe = _battle_end_at(sidecar, buffer=0) if sidecar and Path(sidecar).exists() else None
        t_sample = (lead_in + (end_probe or lead_in + 12.0)) / 2.0
        box = _arena_crop(src, t_sample, iw, ih, tmp)
        if box is None:
            box = ((iw - int(iw / ZOOM_X)) // 2, int((ih - int(ih / ZOOM_Y)) * CROP_Y_BIAS),
                   int(iw / ZOOM_X), int(ih / ZOOM_Y))
        cx, full_cy, cw, full_ch = box
    ch = int(cw * G["game_h"] / 1080) // 2 * 2
    cy = max(0, min(ih - ch, full_cy + (full_ch - ch) // 2))
    game_h = G["game_h"]
    # Freeze the crop into its filter string HERE. A later loop variable shadowing `cx`
    # once clobbered the offset between computation and use — ffmpeg then silently
    # CLAMPED the out-of-range x and right-aligned every fight (v5-v8, found 2026-07-25
    # by pixel-matching the output against the raw). The assert makes any future
    # out-of-range crop fail loudly instead of sliding the window.
    assert 0 <= cx and 0 <= cy and cx + cw <= iw and cy + ch <= ih, \
        f"crop {cw}x{ch}+{cx}+{cy} exceeds source {iw}x{ih}"
    crop_expr = f"crop={cw}:{ch}:{cx}:{cy}"
    print(f"[crop] {src.name}: src={iw}x{ih} {crop_expr} game_h={game_h}", flush=True)

    end_at = _battle_end_at(sidecar, buffer=END_BUFFER) if sidecar and Path(sidecar).exists() else None
    end = min(end_at, D - 0.1) if end_at is not None else min(D - 0.1, lead_in + 6.0)
    end = max(end, lead_in + 1.5)
    ranges = (_ramp_ranges_long if pacing == "long" else _ramp_ranges)(lead_in, end)
    ramped = len(ranges) > 1

    # Static layer (one Chrome shot: chrome + header + plates + Numbers, holes cut for
    # gameplay + HP bars) and the parchment HP-bar frames (Pillow, design style).
    n1 = panel["n1"] if panel else 0
    n2 = panel["n2"] if panel else 0
    rows = (reel_cards.build_numbers_rows(panel["hero"]["cd"], panel["opp"]["cd"],
                                          n1, n2, u1["name"], u2["name"])
            if panel else [])
    costs = (reel_cards.build_cost_lines(panel["hero"]["cd"], panel["opp"]["cd"], n1, n2,
                                         panel["hero"].get("slug", ""),
                                         panel["opp"].get("slug", ""))
             if panel else None)
    static_png = reel_cards.render_fight_static(
        tmp / "static.png", CANVAS, u1, u2, verdict_kind, rows, why, costs=costs)
    hud_dir, hud_fps = reel_cards.render_hp_frames(
        sidecar, D, tmp / "hud", n1 or 1, n2 or 1, fps=5.0,
        t_min=max(0.0, lead_in - 1.0), t_max=end + 1.0)

    # ---- inputs (index bookkeeping) --------------------------------------------
    loop_t = f"{D + 0.5:.2f}"
    inputs = [["-i", str(src)]]
    idx = {"static": len(inputs)}
    inputs.append(["-loop", "1", "-t", loop_t, "-i", str(static_png)])
    idx["hud"] = len(inputs)
    inputs.append(["-framerate", f"{hud_fps}", "-i", str(Path(hud_dir) / "f_%05d.png")])
    if ramped:
        icon = _ff_icon(tmp / "_fficon.png", scale=1.1)
        idx["icon"] = len(inputs)
        inputs.append(["-i", str(icon)])
    if not has_a:
        idx["anull"] = len(inputs)
        inputs.append(["-f", "lavfi", "-t", f"{max(1.0, end - lead_in)}", "-i", _ANULLSRC])

    # The two units' attack gifs, looping live in the top band's TOP_GIF slots for the
    # whole segment (overlaid AFTER the speed ramp so they animate at native speed even
    # while the fight fast-forwards). Each gif is pre-expanded to a PNG frame sequence
    # (same mechanism as the HP band) — feeding ffmpeg the gif directly via its demuxer
    # + -ignore_loop stalled an encode to 0.0007x real time (2026-07-25, 8h hang).
    # Static icon fallback when a unit has no gif.
    out_dur = sum((r1 - r0) / spd for r0, r1, spd in ranges)
    heroes = []                                       # (input idx, is_gif, slot centre x)
    for k, (u, slot_cx) in enumerate(((u1, reel_cards.TOP_GIF_CX[0]),
                                      (u2, reel_cards.TOP_GIF_CX[1]))):
        art = u.get("gif") or u.get("icon")
        if not art or not Path(art).exists():
            continue
        art_idx = len(inputs)
        if str(art).lower().endswith(".gif"):
            seq_dir, seq_fps = _gif_png_seq(art, tmp / f"heroseq{k}", out_dur + 0.5)
            if seq_dir is None:
                continue
            inputs.append(["-framerate", str(seq_fps), "-i",
                           str(seq_dir / "f_%05d.png")])
            heroes.append((art_idx, True, slot_cx))
        else:
            inputs.append(["-loop", "1", "-t", f"{out_dur + 0.5:.2f}", "-i", str(art)])
            heroes.append((art_idx, False, slot_cx))

    # ---- compose the full canvas over the RAW clock, THEN ramp -----------------
    # layers: gameplay into the design's window -> static parchment layer (holes let
    # gameplay + HP bars show through) -> live HP-bar frames in the bar frame.
    parts = [
        f"color=c=0x1a140c:s={W}x{H}:d={loop_t}:r=30[bg]",
        f"[0:v]{crop_expr},scale={W}:{game_h}[game]",
        f"[bg][game]overlay=0:{G['game_top']}:shortest=1[b1]",
        f"[{idx['static']}:v]format=rgba[st]",
        f"[b1][st]overlay=0:0[b2]",
        f"[{idx['hud']}:v]format=rgba[hudv]",
        f"[b2][hudv]overlay={reel_cards.HP_INT_X}:{G['hp_bar_top'] + 2}:shortest=1[vt]",
    ]
    cur = "[vt]"

    n = len(ranges)
    if n > 1:
        parts.append(f"{cur}split={n}" + "".join(f"[c{i}]" for i in range(n)))
    else:
        parts.append(f"{cur}null[c0]")
    vlabels = []
    for i, (r0, r1, spd) in enumerate(ranges):
        setpts = "PTS-STARTPTS" if spd == 1.0 else f"(PTS-STARTPTS)/{spd:.6f}"
        parts.append(f"[c{i}]trim={r0}:{r1},setpts={setpts}[v{i}]")
        lbl = f"[v{i}]"
        if spd != 1.0:                                  # fast-forward icon over gameplay
            parts.append(f"{lbl}[{idx['icon']}:v]overlay="
                         f"x=main_w-overlay_w-30:y={G['game_top'] + 20}[vf{i}]")
            lbl = f"[vf{i}]"
        vlabels.append(lbl)
    if n > 1:
        parts.append("".join(vlabels) + f"concat=n={n}:v=1:a=0[vr]")
    else:
        parts.append(f"{vlabels[0]}null[vr]")
    # live attack gifs into the top band's slots (bottom-anchored, centred on cx)
    cur = "[vr]"
    for k, (ai, is_gif, scx) in enumerate(heroes):
        h = reel_cards.TOP_GIF_H if is_gif else int(reel_cards.TOP_GIF_H * 0.75)
        parts.append(f"[{ai}:v]format=rgba,scale=-2:{h}[hg{k}]")
        nxt = f"[vg{k}]"
        parts.append(f"{cur}[hg{k}]overlay=x={scx}-overlay_w/2:"
                     f"y={reel_cards.TOP_GIF_Y + reel_cards.TOP_GIF_H}-overlay_h:"
                     f"shortest=0:eof_action=repeat{nxt}")
        cur = nxt
    parts.append(f"{cur}null[v]")

    # ---- audio (trimmed/sped to match) -----------------------------------------
    if has_a:
        if n > 1:
            parts.append("[0:a]asplit=" + str(n) + "".join(f"[t{i}]" for i in range(n)))
            alabels = []
            for i, (r0, r1, spd) in enumerate(ranges):
                tempo = "" if spd == 1.0 else f",{_atempo_chain(spd)}"
                parts.append(f"[t{i}]atrim={r0}:{r1},asetpts=PTS-STARTPTS{tempo}[a{i}]")
                alabels.append(f"[a{i}]")
            parts.append("".join(alabels) + f"concat=n={n}:v=0:a=1[a]")
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


def make_intro(out_path, subject, work_dir, seconds=INTRO_S, voices=()) -> Path:
    """The opening scene = the SAME animated 'Unit Spotlight — Parchment' stats card as
    the long-form video (attack-gif hero looping over the plate), laid vertically, with
    the civ's military attack barks over it. Re-encoded through the segment codec params
    so it stream-copy-concats with the fights."""
    from overlay.intro_card import make_unit_intro_video_vertical
    raw = Path(work_dir) / "intro_card_raw.mp4"
    make_unit_intro_video_vertical(subject["civ"], subject["slug"], raw,
                                   duration_s=seconds, fps=30)
    track = voice_track(voices, seconds, Path(work_dir) / "intro_voice.wav")[0] \
        if voices else None
    cmd = [_ffmpeg(), "-y", "-i", str(raw),
           *(["-i", str(track)] if track
             else ["-f", "lavfi", "-t", f"{seconds}", "-i", _ANULLSRC]),
           "-map", "0:v", "-map", "1:a", *_x264(), *_AAC, "-shortest",
           "-movflags", "+faststart", str(out_path)]
    _run(cmd)
    return Path(out_path)


def make_cta(out_path, subject, work_dir, seconds=CTA_S, n_matchups=0) -> Path:
    png = reel_cards.render_cta(
        Path(work_dir) / "cta.png", CANVAS, subject["name"], subject["slug"],
        subject["icon"], n_matchups=n_matchups)
    # the CTA png is already a full parchment page; the bg fill never shows
    return _card_segment(png, seconds, Path(out_path), CANVAS, card_width_frac=1.0)


def build_reel_video(subject, fights, out_path, work_dir=None, *,
                     pacing="reel", voices=(), n_matchups=0) -> Path:
    """subject: {name, civ, slug, icon}. fights: list of dicts with keys
    {raw, sidecar, u1, u2, subj_slug, verdict_kind, why, lead_in}.
    pacing="long" runs each fight at its YouTube-cut length (no extra speed-up)."""
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="reel_"))
    tmp.mkdir(parents=True, exist_ok=True)

    # A stats card needs reading time: the long-pacing (per-category) cut holds it 5s,
    # the tight 15s reel keeps the short INTRO_S.
    intro_s = 5.0 if pacing == "long" else INTRO_S
    segs = [make_intro(tmp / "seg_00_intro.mp4", subject, tmp, seconds=intro_s,
                       voices=voices)]
    for i, f in enumerate(fights):
        seg = tmp / f"seg_{i + 1:02d}_fight.mp4"
        make_reel_fight(f["raw"], f["sidecar"], seg, f["u1"], f["u2"], f["subj_slug"],
                        verdict_kind=f["verdict_kind"], why=f.get("why", ""),
                        lead_in=f["lead_in"], work_dir=tmp / f"fw{i}",
                        pacing=pacing, panel=f.get("panel"))
        segs.append(seg)
    segs.append(make_cta(tmp / f"seg_{len(fights) + 1:02d}_cta.mp4", subject, tmp,
                         n_matchups=n_matchups))
    concat_videos(segs, out_path)
    return out_path
