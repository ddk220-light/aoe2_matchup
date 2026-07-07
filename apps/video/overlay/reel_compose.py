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

import tempfile
from pathlib import Path

from overlay import reel_cards
from overlay.overlay_hp import build_hud_frames
from overlay.hud import hud_band_height
from overlay.compose import (
    _ffmpeg, _run, _duration, _has_audio, _x264, _AAC, _ANULLSRC, _atempo_chain,
    _ff_icon, _card_segment, _battle_end_at, concat_videos,
)

# ---- vertical canvas geometry (1080x1920) --------------------------------------
CANVAS = (1080, 1920)
BG = "0x0b0a07"
GAME_Y = 520            # gameplay top edge (top band = 0..520)
HUD_Y = 1215            # HP band top edge (below gameplay at 1128)
WHY_Y = 1470            # 'why' caption top edge
TOP_H = 520             # top band height
WHY_H = 180             # caption strip height
HUD_VSCALE = 2016       # virtual height fed to build_hud_frames -> sc=1.4, band~200px

# ---- tight reel ramp (seconds) -------------------------------------------------
LEAD_KEEP = 1.3         # keep the clash at 1x
TAIL_KEEP = 1.6         # keep the kill at 1x
MID_TARGET = 2.2        # sprint the middle to ~this long
END_BUFFER = 1.2        # seconds after the last death the clip holds

INTRO_S = 2.6
CTA_S = 2.2


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


def make_reel_fight(raw_clip, sidecar, out_path, u1, u2, subj_slug, *,
                    verdict_kind, why="", lead_in, work_dir=None) -> Path:
    """One vertical fight segment. u1 = subject (side1), u2 = opponent (side2)."""
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="reelfight_"))
    tmp.mkdir(parents=True, exist_ok=True)
    W, H = CANVAS
    src = Path(raw_clip).resolve()
    D = _duration(src)
    has_a = _has_audio(src)

    end_at = _battle_end_at(sidecar, buffer=END_BUFFER) if sidecar and Path(sidecar).exists() else None
    end = min(end_at, D - 0.1) if end_at is not None else min(D - 0.1, lead_in + 6.0)
    end = max(end, lead_in + 1.5)
    ranges = _ramp_ranges(lead_in, end)
    ramped = len(ranges) > 1

    # HP band (icons + names + live counts + HP), full 1080 wide, blank outside the fight.
    # Drop the "Elite " prefix for the band ONLY — at 1080 width the full name tabs are
    # wide enough to collide with the centre count plate.
    def _short(u):
        return {**u, "name": u["name"][6:] if u["name"].startswith("Elite ") else u["name"]}
    hud_dir, hud_fps = build_hud_frames(
        str(sidecar), _short(u1), _short(u2), D, tmp / "hud", fps=5.0, size=(W, HUD_VSCALE),
        t_min=max(0.0, lead_in - 1.0), t_max=end + 1.0)
    band_h = hud_band_height(HUD_VSCALE)

    top_png = reel_cards.render_top_band(
        tmp / "top.png", (W, TOP_H), u1["name"], subj_slug, u1["icon"], verdict_kind)
    why_png = reel_cards.render_caption(tmp / "why.png", (W, WHY_H), why) if why else None

    # ---- inputs (index bookkeeping) --------------------------------------------
    loop_t = f"{D + 0.5:.2f}"
    inputs = [["-i", str(src)]]
    idx = {"hud": len(inputs)}
    inputs.append(["-framerate", f"{hud_fps}", "-i", str(Path(hud_dir) / "f_%05d.png")])
    idx["top"] = len(inputs)
    inputs.append(["-loop", "1", "-t", loop_t, "-i", str(top_png)])
    if why_png is not None:
        idx["why"] = len(inputs)
        inputs.append(["-loop", "1", "-t", loop_t, "-i", str(why_png)])
    if ramped:
        icon = _ff_icon(tmp / "_fficon.png", scale=1.1)
        idx["icon"] = len(inputs)
        inputs.append(["-i", str(icon)])
    if not has_a:
        idx["anull"] = len(inputs)
        inputs.append(["-f", "lavfi", "-t", f"{max(1.0, end - lead_in)}", "-i", _ANULLSRC])

    # ---- compose the full canvas over the RAW clock, THEN ramp -----------------
    parts = [f"[0:v]scale={W}:-2,pad={W}:{H}:0:{GAME_Y}:color={BG}[base]"]
    parts.append(f"[{idx['hud']}:v]format=rgba[hudv]")
    parts.append(f"[base][hudv]overlay=0:{HUD_Y}:shortest=1[vh]")
    parts.append(f"[{idx['top']}:v]format=rgba[topv]")
    parts.append(f"[vh][topv]overlay=0:0[vt]")
    cur = "[vt]"
    if why_png is not None:
        parts.append(f"[{idx['why']}:v]format=rgba[whyv]")
        parts.append(f"[vt][whyv]overlay=0:{WHY_Y}[vw]")
        cur = "[vw]"

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
                         f"x=main_w-overlay_w-30:y={GAME_Y + 20}[vf{i}]")
            lbl = f"[vf{i}]"
        vlabels.append(lbl)
    if n > 1:
        parts.append("".join(vlabels) + f"concat=n={n}:v=1:a=0[v]")
    else:
        parts.append(f"{vlabels[0]}null[v]")

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


def make_intro(out_path, subject, work_dir, seconds=INTRO_S) -> Path:
    png = reel_cards.render_intro_hero(
        Path(work_dir) / "introhero.png", CANVAS, subject["name"], subject["civ"],
        subject["slug"], subject["icon"])
    return _card_segment(png, seconds, Path(out_path), CANVAS, card_width_frac=1.0, bg=BG)


def make_cta(out_path, subject, work_dir, seconds=CTA_S) -> Path:
    png = reel_cards.render_cta(
        Path(work_dir) / "cta.png", CANVAS, subject["name"], subject["slug"],
        subject["icon"])
    return _card_segment(png, seconds, Path(out_path), CANVAS, card_width_frac=1.0, bg=BG)


def build_reel_video(subject, fights, out_path, work_dir=None) -> Path:
    """subject: {name, civ, slug, icon}. fights: list of dicts with keys
    {raw, sidecar, u1, u2, subj_slug, verdict_kind, why, lead_in}."""
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="reel_"))
    tmp.mkdir(parents=True, exist_ok=True)

    segs = [make_intro(tmp / "seg_00_intro.mp4", subject, tmp)]
    for i, f in enumerate(fights):
        seg = tmp / f"seg_{i + 1:02d}_fight.mp4"
        make_reel_fight(f["raw"], f["sidecar"], seg, f["u1"], f["u2"], f["subj_slug"],
                        verdict_kind=f["verdict_kind"], why=f.get("why", ""),
                        lead_in=f["lead_in"], work_dir=tmp / f"fw{i}")
        segs.append(seg)
    segs.append(make_cta(tmp / f"seg_{len(fights) + 1:02d}_cta.mp4", subject, tmp))
    concat_videos(segs, out_path)
    return out_path
