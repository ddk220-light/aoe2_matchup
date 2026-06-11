"""overlay_hp.py — turn the gRPC HP sidecar (<video>.hp.json) into a sequence of HUD
overlay frames timed to the RAW recording, then composite them onto the fight footage.

The sidecar has `video_game_start_s` (seconds into the raw recording where game-time 0 is)
and `rows` = [{game_s, side1:{count,hp}, side2:{count,hp}}, ...]. The timeline is coarse
(~2 s snapshots), so we LINEAR-INTERPOLATE HP between rows for a smooth draining bar; the
count steps at the midpoint. HP fraction = current_hp / initial_hp (row 0).

Render via hud.render_hud_frame (icons + names + survivor counts + HP bars). Frames are
generated for the raw footage so they survive the later lead-in trim + speed-ramp in compose.
"""
from __future__ import annotations

import json
from pathlib import Path

from overlay.hud import render_hud_frame, hud_band_height


def clean_rows(rows):
    """Repair transient decode dropouts (a snapshot that loses one side's entities, reading
    it as ~0 before it reappears) WITHOUT assuming HP only ever falls — some units heal/
    regen, so a genuine HP *rise* is left intact.

      * COUNT is monotonic non-increasing: units never resurrect, so any count that dips
        and recovers is a glitch — lift each count to the max of all LATER counts.
      * HP is repaired only for clear dropouts: a reading with units alive but ~0 total HP
        (`hp < count`, i.e. <1 hp/unit — impossible), or a down-spike that recovers (much
        lower than BOTH neighbours). Such points are linearly interpolated from the nearest
        good readings. A steady HP rise (healing) is NOT a down-spike, so it's preserved.
    """
    n = len(rows)
    for side in ("side1", "side2"):
        run = 0
        for r in reversed(rows):
            run = max(run, int(r[side]["count"])); r[side]["count"] = run
        hp = [float(r[side]["hp"]) for r in rows]
        cnt = [int(r[side]["count"]) for r in rows]
        gs = [r["game_s"] for r in rows]
        bad = [False] * n
        for i in range(n):
            dropout = cnt[i] > 0 and hp[i] < cnt[i]
            spike = (0 < i < n - 1 and hp[i] < hp[i - 1]
                     and hp[i] < 0.6 * min(hp[i - 1], hp[i + 1]))
            bad[i] = dropout or spike
        for i in range(n):
            if not bad[i]:
                continue
            lo = next((j for j in range(i - 1, -1, -1) if not bad[j]), None)
            hi = next((j for j in range(i + 1, n) if not bad[j]), None)
            if lo is not None and hi is not None:
                f = (gs[i] - gs[lo]) / max(1e-6, gs[hi] - gs[lo])
                rows[i][side]["hp"] = round(hp[lo] + f * (hp[hi] - hp[lo]), 1)
            elif lo is not None:
                rows[i][side]["hp"] = hp[lo]
            elif hi is not None:
                rows[i][side]["hp"] = hp[hi]
    return rows


def load_sidecar(path, clean=True):
    with open(path) as f:
        d = json.load(f)
    rows = clean_rows(d["rows"]) if clean else d["rows"]
    return d["video_game_start_s"], rows


def _interp(rows, gs, side):
    """count, hp at game-second `gs` for 'side1'/'side2' (linear HP, stepped count)."""
    if gs <= rows[0]["game_s"]:
        r = rows[0][side]; return r["count"], float(r["hp"])
    if gs >= rows[-1]["game_s"]:
        r = rows[-1][side]; return r["count"], float(r["hp"])
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        if a["game_s"] <= gs <= b["game_s"]:
            sa, sb = a[side], b[side]
            span = max(1e-6, b["game_s"] - a["game_s"])
            f = (gs - a["game_s"]) / span
            hp = sa["hp"] + f * (sb["hp"] - sa["hp"])
            cnt = sb["count"] if f >= 0.5 else sa["count"]
            return cnt, hp
    r = rows[-1][side]; return r["count"], float(r["hp"])


def battle_trend(rows, gs, win=6.0, margin=2):
    """Who's winning the trade RIGHT NOW: compare each side's losses over the last
    `win` game-seconds. Returns (t1, t2) with +1 = trading up (enemy losing at least
    `margin` more units), -1 = trading down, 0 = even/quiet/too early."""
    if gs < 3.0:
        return (0, 0)
    c1n, _ = _interp(rows, gs, "side1")
    c2n, _ = _interp(rows, gs, "side2")
    c1o, _ = _interp(rows, max(0.0, gs - win), "side1")
    c2o, _ = _interp(rows, max(0.0, gs - win), "side2")
    l1, l2 = max(0, c1o - c1n), max(0, c2o - c2n)
    adv = l2 - l1                          # >0: side1 is winning the trade
    if (l1 == 0 and l2 == 0) or abs(adv) < margin:
        return (0, 0)
    return (1, -1) if adv > 0 else (-1, 1)


def build_hud_frames(sidecar_path, u1, u2, raw_duration, out_dir, fps=5.0,
                     size=(2560, 1440), t_min=None, t_max=None):
    """Generate f_%05d.png HUD frames for [0, raw_duration] of the RAW recording. Returns
    (frame_dir, fps).

    Frames are BAND-ONLY (just the top strip the HUD occupies — composite at 0:0), and
    frames outside [t_min, t_max] (raw-video seconds; the fight window) are written as a
    cached fully-transparent blank instead of being drawn — most of the sequence used to
    be full-resolution transparent PNGs that cost render+encode+decode for nothing."""
    import shutil
    vstart, rows = load_sidecar(sidecar_path)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    s1_max = float(rows[0]["side1"]["hp"]) or 1.0
    s2_max = float(rows[0]["side2"]["hp"]) or 1.0
    s1_start = rows[0]["side1"]["count"]
    s2_start = rows[0]["side2"]["count"]
    n = max(1, int(raw_duration * fps))
    from PIL import Image
    blank_path = out / "_blank.png"
    Image.new("RGBA", (size[0], hud_band_height(size[1])), (0, 0, 0, 0)).save(blank_path)
    for i in range(n):
        v = i / fps
        if (t_min is not None and v < t_min) or (t_max is not None and v > t_max):
            shutil.copyfile(blank_path, out / f"f_{i:05d}.png")
            continue
        gs = v - vstart
        c1, h1 = _interp(rows, gs, "side1")
        c2, h2 = _interp(rows, gs, "side2")
        frame = render_hud_frame(
            u1["name"], u1["icon"], s1_start, round(c1), max(0.0, h1 / s1_max),
            u2["name"], u2["icon"], s2_start, round(c2), max(0.0, h2 / s2_max),
            t=max(0.0, gs), size=size, band_only=True,
            trend=battle_trend(rows, gs))
        frame.save(out / f"f_{i:05d}.png")
    return str(out), fps


if __name__ == "__main__":
    # quick PNG test from the last run's sidecar (no ffmpeg)
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scenario_builder/
    from overlay.overlay_data import get_unit_card
    sc = sys.argv[1] if len(sys.argv) > 1 else \
        r"C:\Users\ddk22\Videos\aoe2_matchups\Elite Temple Guard vs Jaguar Warrior (Muisca vs Aztecs).hp.json"
    u1 = get_unit_card("Muisca", "elite_temple_guard_muisca")
    u2 = get_unit_card("Aztecs", "elite_jaguar_warrior_aztecs")
    vstart, rows = load_sidecar(sc)
    print(f"sidecar: game-start at video +{vstart:.1f}s, {len(rows)} rows, "
          f"end={rows[-1]['game_s']}s")
    out = Path(__file__).parent / "samples" / "hud_test"
    d, fps = build_hud_frames(sc, u1, u2, raw_duration=rows[-1]['game_s'] + vstart + 2,
                              out_dir=out, fps=2.0)
    n = len(list(Path(d).glob("f_*.png")))
    print(f"generated {n} HUD frames @ {fps}fps -> {d}")
    # print the HP trajectory we'd draw
    for r in rows:
        print(f"  game_s={r['game_s']:2}  S1 {r['side1']['count']}u/{r['side1']['hp']:.0f}hp"
              f"  S2 {r['side2']['count']}u/{r['side2']['hp']:.0f}hp")
