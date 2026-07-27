"""stitch_analysis.py — assemble the finished unit-analysis video from the recorded
fight clips + rendered cards.

Given the storyboard (aoe2x.analysis output) + the plan (run_unit_analysis_video.
build_plan) + the directory of recorded fight clips, produce ONE stitched mp4:

  INTRO (subject hero card: hi-res sprite + stats)  ->  attack-gif showcase
  -> for each category in order:
       category BANNER  ->  its 3 recorded FIGHT clips  ->  full-ranking CARD
  -> EVEN-matchups CARD

plus a YouTube chapters .txt (cumulative timestamps).

Every segment is rendered/normalized to the SAME codec/size/fps as the fight clips
(2560x1440 @ OUT_FPS, libx264, AAC) so concat_videos stream-copy-joins them. Card
PNGs render via headless Chrome (overlay.render_card); the intro's hi-res sprite +
attack gif come from overlay.assets.AssetResolver (AOE2_MEDIA_DIR / the in-repo
media tree). Each card render is guarded — a single failed card is skipped (logged)
rather than sinking the whole stitch.
"""
from __future__ import annotations

import html
import traceback
from pathlib import Path

from overlay.render_card import (render_category_banner,
                                 _screenshot, _img_data_uri, _css, _res_iconic,
                                 PALETTE)
from overlay.compose import (_card_segment, _card_segment_gif, voice_track, concat_videos,
                             _duration)
from overlay.assets import AssetResolver
from auto.chapters import write_chapters

# ---- segment durations (seconds) -------------------------------------------
INTRO_HERO_S = 5.5
INTRO_GIF_S = 3.0
BANNER_S = 3.5
EVEN_S = 5.5
RANKED_BASE_S = 3.0        # + per-row time, clamped
RANKED_PER_ROW_S = 0.28
RANKED_MAX_S = 11.0


def _log(msg):
    print(f"[stitch] {msg}", flush=True)


# --------------------------------------------------------------------------- #
# subject INTRO hero card (hi-res sprite + stat block), styled like the cards
# --------------------------------------------------------------------------- #
def build_subject_intro_html(u: dict, hires_uri: str, subtitle: str) -> str:
    P = PALETTE
    name = html.escape(str(u.get("name", "")))
    civ = html.escape(str(u.get("civ", "")))
    utype = html.escape(str(u.get("unit_type", "")))
    sub = html.escape(str(subtitle))
    stat_rows = "".join(
        f'<div class="s"><span class="k">{html.escape(str(k))}</span>'
        f'<span class="v">{html.escape(str(v))}</span></div>'
        for k, v in u.get("stats", []))
    cost = _res_iconic(u.get("cost", {}) or {})
    sprite = (f'<img class="hero" src="{hires_uri}">' if hires_uri
              else (f'<img class="hero" src="{_img_data_uri(u.get("icon", ""))}">'
                    if u.get("icon") else '<div class="hero"></div>'))
    override = f"""
.wrap {{ padding:0; }}
.intro {{ width:1600px; margin:0 auto; padding:48px 60px 52px; border-radius:20px;
  background:linear-gradient(165deg, rgba(42,31,20,0.94), rgba(18,13,7,0.96));
  border:2px solid rgba(201,168,76,0.75);
  box-shadow:0 10px 40px rgba(0,0,0,0.6), inset 0 0 0 1px rgba(201,168,76,0.12); }}
.intro .top {{ text-align:center; margin-bottom:30px; }}
.intro .nm {{ font-size:80px; letter-spacing:2px; color:{P['gold']}; text-transform:uppercase;
  text-shadow:0 3px 14px #000; line-height:1.02; }}
.intro .sc {{ font-size:30px; color:{P['text_muted']}; margin-top:8px; }}
.body {{ display:flex; gap:52px; align-items:center; justify-content:center; }}
.hero {{ width:440px; height:440px; object-fit:contain; border-radius:18px;
  border:3px solid {P['gold']}; background:{P['bg_deep']};
  box-shadow:0 0 26px rgba(201,168,76,0.3); flex:0 0 auto; }}
.info {{ flex:1 1 auto; max-width:820px; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px 40px; }}
.s {{ display:flex; justify-content:space-between; font-size:32px;
  border-bottom:1px dotted rgba(168,152,120,.32); padding:8px 2px; }}
.s .k {{ color:{P['text_muted']}; }} .s .v {{ color:{P['text']}; font-weight:bold; }}
.cost {{ margin-top:22px; font-size:34px; display:flex; align-items:center; gap:12px; }}
.cost .cl {{ color:{P['gold']}; font-size:20px; letter-spacing:2px; text-transform:uppercase; }}
.resi {{ display:inline-flex; align-items:center; gap:6px; font-weight:bold; color:{P['text']}; }}
.ri {{ width:30px; height:30px; vertical-align:middle; }}
.subt {{ text-align:center; margin-top:34px; font-size:30px; color:{P['gold_light']};
  letter-spacing:1px; }}
.brand {{ text-align:center; margin-top:14px; font-size:20px; letter-spacing:3px;
  color:rgba(168,152,120,0.8); }}
"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_css()}
{override}</style></head>
<body><div class="wrap"><div class="intro">
  <div class="top"><div class="nm">{name}</div><div class="sc">{civ} &middot; {utype}</div></div>
  <div class="body">
    {sprite}
    <div class="info">
      <div class="grid">{stat_rows}</div>
      <div class="cost"><span class="cl">Cost</span>{cost}</div>
    </div>
  </div>
  <div class="subt">{sub}</div>
  <div class="brand">aoe2matchup.com</div>
</div></div></body></html>"""


def render_subject_intro(u, hires_path, out_png, subtitle, width=1720, height=760,
                         scale=2) -> Path:
    hires_uri = _img_data_uri(str(hires_path)) if hires_path else ""
    return _screenshot(build_subject_intro_html(u, hires_uri, subtitle),
                       out_png, width, height, scale)


# --------------------------------------------------------------------------- #
# full-ranking card — MULTI-COLUMN so all rows (up to ~30) fit a 1440p frame
# --------------------------------------------------------------------------- #
def _cols_for(n: int) -> int:
    return 1 if n <= 16 else (2 if n <= 34 else 3)


def build_ranking_grid_html(title: str, rows: list, cols: int) -> str:
    """Full ranking laid COLUMN-MAJOR across `cols` columns (rank 1..k down the first
    column, then continue) so a long list stays wider-than-tall and fits the video frame.
    `picked` rows (the recorded fights) get a gold highlight."""
    P = PALETTE
    import math
    per = max(1, math.ceil(len(rows) / cols))

    def cell(r):
        cls = "rr picked" if r.get("picked") else "rr"
        rk = html.escape(str(r.get("rank", "")))
        nm = html.escape(str(r.get("name", "")))
        civ = html.escape(str(r.get("civ", "")))
        sc = r.get("score", "")
        sc = html.escape(f"{sc:+.0f}" if isinstance(sc, (int, float)) else str(sc))
        return (f'<div class="{cls}"><span class="rk">{rk}</span>'
                f'<span class="rn">{nm}</span><span class="rc">{civ}</span>'
                f'<span class="rv">{sc}</span></div>')

    colhtml = []
    for c in range(cols):
        chunk = rows[c * per:(c + 1) * per]
        colhtml.append('<div class="col">' + "".join(cell(r) for r in chunk) + "</div>")
    t = html.escape(str(title))
    override = f"""
.wrap {{ padding:0; }}
.rank {{ display:inline-block; padding:30px 40px 34px; border-radius:16px;
  background:linear-gradient(165deg, rgba(42,31,20,0.92), rgba(18,13,7,0.94));
  border:2px solid rgba(201,168,76,0.7); }}
.rank .h {{ font-size:44px; color:{P['gold']}; text-transform:uppercase; letter-spacing:2px;
  text-align:center; margin-bottom:22px; text-shadow:0 2px 8px #000; white-space:nowrap; }}
.cols {{ display:flex; gap:46px; align-items:flex-start; }}
.col {{ display:flex; flex-direction:column; min-width:560px; }}
.rr {{ display:flex; align-items:center; gap:16px; padding:9px 12px;
  border-bottom:1px dotted rgba(168,152,120,.28); font-size:29px; white-space:nowrap; }}
.rr.picked {{ background:linear-gradient(90deg, rgba(201,168,76,.20), transparent);
  border-bottom-color:rgba(201,168,76,.55); border-radius:8px; }}
.rk {{ width:52px; font-size:31px; font-weight:bold; color:{P['gold_light']}; text-align:right; }}
.rn {{ color:{P['text']}; font-weight:bold; }}
.rr.picked .rn {{ color:{P['gold_light']}; }}
.rc {{ color:{P['text_muted']}; font-size:22px; }}
.rv {{ margin-left:auto; color:{P['gold_light']}; font-weight:bold; padding-left:18px; }}
"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_css()}
{override}</style></head>
<body><div class="wrap"><div class="rank"><div class="h">{t}</div>
  <div class="cols">{''.join(colhtml)}</div></div></div></body></html>"""


def render_ranking_grid(out_png, title, rows, scale=2) -> Path:
    """Render a full-ranking card sized to its content; columns auto-chosen so it never
    exceeds ~16 rows tall (keeps it frame-friendly). Auto-cropped to the card bounds."""
    from overlay.render_card import _autocrop
    cols = _cols_for(len(rows))
    per = max(1, (len(rows) + cols - 1) // cols)
    # generous window; content is auto-cropped after
    w = 260 + cols * 660
    h = 200 + per * 58
    return _autocrop(_screenshot(build_ranking_grid_html(title, rows, cols),
                                 out_png, w, h, scale))


def _fit_frac(png, size, *, max_w_frac=0.86, target_h_frac=0.82) -> float:
    """Width fraction for _card_segment so the card renders ~`target_h_frac` of frame
    height, capped at `max_w_frac` of frame width. Keeps variable-size cards visually
    consistent AND fully on-screen (no vertical overflow)."""
    W, H = size
    try:
        from PIL import Image
        with Image.open(png) as im:
            cw, ch = im.size
        frac_by_h = (target_h_frac * H) * (cw / ch) / W
        return round(min(max_w_frac, frac_by_h), 4)
    except Exception:
        return 0.80


# --------------------------------------------------------------------------- #
# main stitch
# --------------------------------------------------------------------------- #
def _ranked_seconds(rows) -> float:
    return max(RANKED_BASE_S,
              min(RANKED_MAX_S, RANKED_BASE_S + RANKED_PER_ROW_S * len(rows or [])))


def _fight_clip(clips_dir: Path, name: str) -> Path | None:
    p = clips_dir / f"{name}.mp4"
    return p if p.exists() else None


def stitch_analysis_video(plan, storyboard, clips_dir, out_path, *,
                          media_dir=None, size=(2560, 1440), work_dir=None) -> dict:
    """Build the final stitched video from `plan` (build_plan output) + the recorded
    clips in `clips_dir`. Returns {out, chapters, segments, missing}. `missing` lists
    fight step names whose clip wasn't found (skipped)."""
    clips_dir = Path(clips_dir)
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(work_dir) if work_dir else (out_path.parent / "_stitch_work")
    tmp.mkdir(parents=True, exist_ok=True)

    from overlay.overlay_data import get_unit_card
    subj = storyboard["subject"]
    assets = AssetResolver(media_dir)

    # chapters = ordered list of (label, [segment paths]); segments concat in flat order
    chapters: list[tuple[str, list[Path]]] = []
    missing: list[str] = []
    seg_i = 0

    def card_seg(png, seconds, frac, audio=None):
        nonlocal seg_i
        out = tmp / f"seg_{seg_i:03d}.mp4"
        seg_i += 1
        return _card_segment(Path(png), seconds, out, size, card_width_frac=frac,
                             audio=audio)

    def gif_seg(gif, seconds, frac, audio=None):
        nonlocal seg_i
        out = tmp / f"seg_{seg_i:03d}.mp4"
        seg_i += 1
        return _card_segment_gif(Path(gif), seconds, out, size, card_width_frac=frac,
                                 audio=audio)

    # ---- INTRO: subject hero card (+ hi-res sprite) then the attack-gif showcase --
    # The civ's military attack barks play over the (otherwise silent) intro cards,
    # chained across both so each line is heard once: the stat card takes as many as
    # fit, the gif showcase picks up from there.
    voices = assets.voice_lines(subj["civ"])
    voice_used = 0
    intro_segs: list[Path] = []
    try:
        u = get_unit_card(subj["civ"], subj["slug"])
        hires = assets.hi_res_image(subj["slug"])
        n_matchups = len(storyboard.get("all_results", []))
        subtitle = (f"{n_matchups} matchups ranked — everything it beats, "
                    f"and everything that beats it")
        hero_png = render_subject_intro(u, hires, tmp / "intro_hero.png", subtitle)
        track, voice_used = voice_track(voices, INTRO_HERO_S, tmp / "intro_voice_hero.wav")
        intro_segs.append(card_seg(hero_png, INTRO_HERO_S, frac=0.94, audio=track))
        _log(f"intro hero card ok (hi-res={'yes' if hires else 'no'}, "
             f"voice lines={voice_used}/{len(voices)})")
    except Exception as e:
        _log(f"intro hero card FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
    try:
        gif = assets.attack_gif(subj["slug"])
        if gif:
            track, n = voice_track(voices[voice_used:], INTRO_GIF_S,
                                   tmp / "intro_voice_gif.wav", lead=0.25, gap=0.45)
            intro_segs.append(gif_seg(gif, INTRO_GIF_S, frac=0.42, audio=track))
            _log(f"intro attack-gif showcase ok (voice lines={n})")
    except Exception as e:
        _log(f"intro attack-gif FAILED: {type(e).__name__}: {e}")
    if intro_segs:
        chapters.append(("Intro", intro_segs))

    # ---- per plan step ----------------------------------------------------------
    CATLABEL = {"expected_win": "Expected Win", "unexpected_win": "Unexpected Win",
                "expected_counter": "Expected Counter",
                "unexpected_counter": "Unexpected Counter"}
    for step in plan:
        kind = step["kind"]
        if kind == "intro":
            continue                                     # handled above
        if kind == "banner":
            try:
                png = render_category_banner(tmp / f"banner_{step['category']}.png",
                                             step["title"], step["index"], step["total"])
                chapters.append((step["title"], [card_seg(png, BANNER_S, frac=0.86)]))
            except Exception as e:
                _log(f"banner {step['category']} FAILED: {type(e).__name__}: {e}")
        elif kind == "fight":
            spec = step["spec"]
            clip = _fight_clip(clips_dir, spec["name"])
            catlab = CATLABEL.get(spec["category"], spec["category"])
            label = f"{catlab} #{spec.get('_rank', '')}".strip()
            # chapter label = opponent name (readable in the YT chapter list)
            opp = spec["slug2"]
            chap = f"{CATLABEL.get(spec['category'], '')} — {_pretty(opp)}".strip(" —")
            if clip:
                chapters.append((chap, [clip]))
            else:
                missing.append(spec["name"])
                _log(f"MISSING fight clip: {spec['name']} (skipped)")
        elif kind == "ranked_card":
            rows = step["rows"]
            try:
                png = render_ranking_grid(tmp / f"ranked_{step['category']}.png",
                                          step["title"], rows)
                chapters.append((step["title"],
                                 [card_seg(png, _ranked_seconds(rows), _fit_frac(png, size))]))
            except Exception as e:
                _log(f"ranked_card {step['category']} FAILED: {type(e).__name__}: {e}")
                traceback.print_exc()
        elif kind == "even_card":
            rows = step.get("rows") or []
            if rows:
                try:
                    png = render_ranking_grid(tmp / "even.png", "Even Matchups", rows)
                    chapters.append(("Even matchups",
                                     [card_seg(png, EVEN_S, _fit_frac(png, size))]))
                except Exception as e:
                    _log(f"even_card FAILED: {type(e).__name__}: {e}")
                    traceback.print_exc()

    # ---- concat + chapters ------------------------------------------------------
    all_segs = [s for _, segs in chapters for s in segs]
    if not all_segs:
        raise RuntimeError("no segments produced — nothing to stitch")
    _log(f"concatenating {len(all_segs)} segments -> {out_path.name}")
    concat_videos(all_segs, out_path)

    chap_entries = [(label, sum(_duration(s) for s in segs)) for label, segs in chapters]
    chapters_txt = out_path.with_suffix(".chapters.txt")
    write_chapters(chap_entries, chapters_txt)

    return {"out": out_path, "chapters": chapters_txt,
            "segments": len(all_segs), "missing": missing,
            "chapter_list": chap_entries}


def _pretty(slug: str) -> str:
    """'elite_chu_ko_nu_chinese' -> 'Elite Chu Ko Nu' (drop trailing civ token best-effort;
    used only for chapter labels, so a rough title-case is fine)."""
    s = slug.replace("_", " ").strip()
    return " ".join(w.capitalize() for w in s.split())
