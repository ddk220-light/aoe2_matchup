"""reel_cards.py — cards/bands for the vertical short-form (Reels/Shorts/TikTok) cut.

Every visible surface is the SAME "Unit Spotlight — Parchment" family as the long-form
video, rendered the same way: HTML + IM Fell English / IM Fell English SC / EB Garamond
webfonts, screenshotted via headless Chrome (`render_card._screenshot`, transparent
background), with unit sprites composited by Pillow afterward. The page chrome (radial
parchment, vignette, double border, corner diamonds) and the font stack come from
`category_card`; accents are the family's own bonus-green / armor-red.

The animated intro card lives in `intro_card.make_unit_intro_video_vertical` (the full
stats plate + attack-gif hero); this module renders the in-fight bands and the CTA.
"""
from __future__ import annotations

import base64
import html as _html
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from overlay.category_card import _font_stack
from overlay.render_card import _screenshot

REPO_ROOT = Path(__file__).resolve().parents[3]
SPRITE_DIR = REPO_ROOT / "apps" / "website" / "static" / "img" / "unit_sprites"

# Parchment family tokens (identical to intro_card/category_card CSS).
INK = "#3d2a16"
INK_BODY = "#4a3220"
INK_MUTED = "#5c4326"
SEPIA = "#6b4a1e"
ACCENT_WIN = "#48561f"       # the long-form bonus-damage green
ACCENT_LOSS = "#6e3325"      # the long-form armor-categories red
PLATE = "rgba(236,223,194,.9)"
HAIRLINE = "rgba(94,66,30,.5)"

VERDICT = {
    "expected_win":    (ACCENT_WIN,  "Expected Win"),
    "unexpected_win":  (ACCENT_WIN,  "Unexpected Win"),
    "expected_loss":   (ACCENT_LOSS, "Expected Loss"),
    "unexpected_loss": (ACCENT_LOSS, "Unexpected Loss"),
    "coin_flip":       (SEPIA,       "Too Close To Call"),
    "win":             (ACCENT_WIN,  "Victory"),
    "loss":            (ACCENT_LOSS, "Defeat"),
}


def verdict_style(kind: str):
    return VERDICT.get(kind, (SEPIA, str(kind).replace("_", " ").title()))


def _sprite(slug: str, icon_fallback=None) -> Path | None:
    """A hero image for the unit: the big game sprite if present, else the square icon.
    unit_sprites/ uses the civ-suffix-STRIPPED slug (elite_bolas_rider_mapuche ->
    elite_bolas_rider.png), so try the full slug then the stripped form."""
    for cand in (slug, slug.rsplit("_", 1)[0]):
        p = SPRITE_DIR / f"{cand}.png"
        if p.exists():
            return p
    if icon_fallback and Path(icon_fallback).exists():
        return Path(icon_fallback)
    return None


def _fit(path: Path, box) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    bw, bh = box
    scale = min(bw / im.width, bh / im.height)
    return im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                     Image.LANCZOS)


def _shoot(html_doc: str, out_png, size) -> Path:
    """Screenshot at 1x with the webfont grace period (transparent background is the
    _screenshot default)."""
    return _screenshot(html_doc, out_png, size[0], size[1], scale=1,
                       extra_args=["--virtual-time-budget=10000"])


def _band_doc(fonts: dict, size, body: str) -> str:
    """A transparent standalone band document (no page ground — bands sit on the
    parchment page the fight canvas already carries)."""
    W, H = size
    return f"""<!doctype html><html><head><meta charset="utf-8">
{fonts['link']}
<style>* {{ box-sizing:border-box; }} body{{margin:0;background:transparent;}}</style>
</head><body>
<div style="position:relative;width:{W}px;height:{H}px;overflow:hidden;
  font-family:{fonts['body']};color:{INK_BODY};">{body}</div>
</body></html>"""


def render_page_ground(out_png, size=(1080, 1920)) -> Path:
    """The full-canvas parchment page the gameplay + bands composite onto: the long-form
    page chrome (radial ground, corner stains, vignette, double border + hairline,
    corner diamonds) at reel dimensions."""
    fonts = _font_stack()
    W, H = size
    corners = "".join(
        f'<div style="position:absolute;top:{t}px;left:{l}px;width:16px;height:16px;'
        f'background:{SEPIA};transform:rotate(45deg);"></div>'
        for t, l in [(18, 18), (18, W - 34), (H - 34, 18), (H - 34, W - 34)])
    doc = f"""<!doctype html><html><head><meta charset="utf-8">
{fonts['link']}
<style>body{{margin:0;background:#cbb28a;}}</style></head><body>
<div style="position:relative;width:{W}px;height:{H}px;overflow:hidden;
  background:radial-gradient(1000px 1500px at 50% 42%, #ecdfc2 0%, #e2d1ac 55%, #cdb489 100%);">
  <div style="position:absolute;inset:0;background:
    radial-gradient(500px 380px at 12% 92%, rgba(122,90,42,.14), transparent 70%),
    radial-gradient(420px 320px at 90% 6%, rgba(122,90,42,.12), transparent 70%);"></div>
  <div style="position:absolute;inset:0;box-shadow:inset 0 0 220px rgba(94,66,30,.45);"></div>
  <div style="position:absolute;inset:26px;border:3px double rgba(94,66,30,.55);"></div>
  <div style="position:absolute;inset:38px;border:1px solid rgba(94,66,30,.3);"></div>
  {corners}
</div></body></html>"""
    return _shoot(doc, out_png, size)


def _icon_uri(path) -> str:
    """Embed a unit icon as a data: URI (headless Chrome can't fetch sibling files
    from a temp-dir page)."""
    try:
        return ("data:image/png;base64,"
                + base64.b64encode(Path(path).read_bytes()).decode())
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Fight-screen geometry — the "Shorts Overlays Parchment" design (claude.ai/design
# project 593f0d30, 2026-07-25). One dict so the HTML static layer, the Pillow HP
# strip and the ffmpeg compositor cannot disagree. All values are 1080x1920 canvas px.
# ---------------------------------------------------------------------------
GEOM = dict(
    header_top=46, header_h=384,
    chip_top=72,                      # chip centre line inside the card
    sprite_bottom=334,                # gif heroes bottom-anchor (page y)
    sprite_cx=(262, 818),             # slot centres (grid 1fr/120px/1fr in 44px margins)
    sprite_max_h=185, sprite_max_w=330,
    name_row_top=352,
    cost_row_top=398,                 # equal-resources line under each name
    # gameplay window (borders sit just outside). User 2026-07-26: the empty parchment
    # strips above/below the window were cut — the window now runs from just under the
    # header card (430) to just above the HP plates (1152), so the map shows ~136px more.
    game_top=446, game_h=698,
    hp_top=1152, hp_plate_h=64, hp_gap=8,
    hp_bar_h=56,                      # interior (inside its own 2px frame)
    num_top=1306, num_bottom=46,
)
GEOM["hp_bar_top"] = GEOM["hp_top"] + GEOM["hp_plate_h"] + GEOM["hp_gap"]   # frame top
# bar frame: x 44..1036 (border 2) -> interior 46..1034 split 344/300/344
HP_INT_X, HP_INT_W = 46, 988
HP_SIDE_W, HP_MID_W = 344, 300

# Back-compat aliases for the compositor's gif-slot maths.
TOP_GIF_CX = GEOM["sprite_cx"]
TOP_GIF_Y = GEOM["sprite_bottom"] - GEOM["sprite_max_h"]
TOP_GIF_H = GEOM["sprite_max_h"]


def _page_chrome(W, H, fonts) -> str:
    """The design's page chrome: parchment ground + corner stains + vignette + double
    border (inset 20) + hairline (inset 31) + 16px corner diamonds at 12px."""
    corners = "".join(
        f'<div style="position:absolute;top:{t}px;left:{l}px;width:16px;height:16px;'
        f'background:{SEPIA};transform:rotate(45deg);z-index:4;"></div>'
        for t, l in [(12, 12), (12, W - 24), (H - 24, 12), (H - 24, W - 24)])
    return f"""
  <div style="position:absolute;inset:0;background:
    radial-gradient(360px 300px at 10% 92%, rgba(122,90,42,.14), transparent 70%),
    radial-gradient(320px 280px at 92% 8%, rgba(122,90,42,.12), transparent 70%),
    radial-gradient(260px 240px at 75% 68%, rgba(122,90,42,.1), transparent 70%);"></div>
  <div style="position:absolute;inset:0;box-shadow:inset 0 0 180px rgba(94,66,30,.45);"></div>
  <div style="position:absolute;inset:20px;border:3px double rgba(94,66,30,.55);z-index:3;"></div>
  <div style="position:absolute;inset:31px;border:1px solid rgba(94,66,30,.3);z-index:3;"></div>
  {corners}"""


def _page_doc(fonts, W, H, body) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
{fonts['link']}
<style>* {{ box-sizing:border-box; }} body{{margin:0;background:transparent;}}</style>
</head><body>
<div style="position:relative;width:{W}px;height:{H}px;overflow:hidden;
  font-family:{fonts['body']};color:{INK_BODY};
  background:radial-gradient(1100px 1400px at 50% 40%, #ecdfc2 0%, #e2d1ac 60%, #cdb489 100%);">
{_page_chrome(W, H, fonts)}
{body}
</div></body></html>"""


def build_numbers_rows(hero_cd, opp_cd, n1, n2, hero_name, opp_name):
    """The Numbers rows in the design's shape: value/sub/colour per side. Colours:
    win green / loss red on the rows where one side holds a real edge, neutral ink
    elsewhere — same advantage rules as before, presented per the design mock."""
    hp1, hp2 = float(hero_cd.get("hp") or 0), float(opp_cd.get("hp") or 0)
    t1, d1, b1 = _ttk(hero_cd, opp_cd)
    t2, d2, b2 = _ttk(opp_cd, hero_cd)

    def n(x):
        return f"{x:.0f}" if abs(x - round(x)) < 1e-6 else f"{x:.1f}"

    def short(name):
        return name.replace("Elite ", "").split()[-1].lower()

    GREEN, RED, NEUT = ACCENT_WIN, ACCENT_LOSS, INK
    dmg_adv = 1 if d1 / max(hp2, 1) > d2 / max(hp1, 1) else 2
    ttk_adv = 1 if t1 < t2 else (2 if t2 < t1 else 0)

    def cols(adv):
        if adv == 1:
            return GREEN, RED
        if adv == 2:
            return RED, GREEN
        return NEUT, NEUT

    dl, dr = cols(dmg_adv)
    tl, tr = cols(ttk_adv)
    ramp1 = float(hero_cd.get("attack_speed_ramp") or 0) > 0
    ramp2 = float(opp_cd.get("attack_speed_ramp") or 0) > 0
    return [
        dict(label="Army", left=f"{n1} × {n(hp1)} HP", left_sub=f"{n(n1 * hp1)} total",
             right=f"{n2} × {n(hp2)} HP", right_sub=f"{n(n2 * hp2)} total",
             lc=NEUT, rc=NEUT),
        dict(label="Damage / Hit", left=n(d1),
             left_sub=f"incl. +{n(b1)} bonus" if b1 else "no bonus",
             right=n(d2), right_sub=f"incl. +{n(b2)} bonus" if b2 else "no bonus",
             lc=dl, rc=dr),
        dict(label="Attack Rate", left=_rate_str(hero_cd),
             left_sub="ramped up" if ramp1 else "flat",
             right=_rate_str(opp_cd), right_sub="ramped up" if ramp2 else "flat",
             lc=NEUT, rc=NEUT),
        dict(label="Time to Kill One", left=f"{t1:.1f}s",
             left_sub=f"for the {short(opp_name)}",
             right=f"{t2:.1f}s", right_sub=f"for the {short(hero_name)}",
             lc=tl, rc=tr),
    ]


def build_cost_lines(hero_cd, opp_cd, n1, n2, hero_slug="", opp_slug=""):
    """The equal-resources lines under the header names: count × (per-unit cost) =
    total weighted resources. The total uses the SAME gold ×1.5 weighting the arena
    counts were sized with, so the two sides land within a unit's cost of each other —
    that near-equality IS the message (a small centred 'gold ×1.5' note explains why
    the arithmetic isn't a plain sum). Returns (left, right) or None if either side
    has no cost data."""
    from overlay.overlay_data import TRAIN_BATCH

    def line(cd, n, slug):
        b = TRAIN_BATCH.get(slug, 1)
        f = float(cd.get("cost_food") or 0) / b
        w = float(cd.get("cost_wood") or 0) / b
        g = float(cd.get("cost_gold") or 0) / b
        wc = f + w + 1.5 * g
        if wc <= 0 or not n:
            return None
        comp = " + ".join(s for s in (
            f"{f:g}F" if f else "", f"{w:g}W" if w else "", f"{g:g}G" if g else "") if s)
        return f"{n} × ({comp}) = {n * wc:,.0f} res"

    left, right = line(hero_cd, n1, hero_slug), line(opp_cd, n2, opp_slug)
    return (left, right) if left and right else None


def render_fight_static(out_png, size, u1: dict, u2: dict, verdict_kind,
                        rows, why: str, costs=None) -> Path:
    """The ENTIRE static layer of the Matchup screen as one Chrome screenshot —
    page chrome, header card (chip + names; gif slots stay empty), the gameplay
    window borders, the health-strip name plates + bar frame, and The Numbers
    panel with the verdict line. The gameplay window and the HP-bar interior are
    then cut to transparent so the live layers show through."""
    W, H = size
    G = GEOM
    fonts = _font_stack()
    accent, label = verdict_style(verdict_kind)
    side_w = (W - 88 - 120) // 2

    def name_div(name, nid, cx):
        return f"""<div style="position:absolute;left:{cx - side_w // 2}px;
      top:{G['name_row_top']}px;width:{side_w}px;text-align:center;z-index:2;">
      <div id="{nid}" style="display:inline-block;font-family:{fonts['title']};
        font-size:42px;line-height:1.05;color:{INK};white-space:nowrap;">
        {_html.escape(name)}</div></div>"""

    # equal-resources line under each name: count × unit cost = ~equal weighted total
    cost_html = ""
    if costs:
        def cost_div(text, cx):
            return f"""<div style="position:absolute;left:{cx - side_w // 2}px;
          top:{G['cost_row_top']}px;width:{side_w}px;text-align:center;z-index:2;
          font-size:20px;font-weight:600;color:{INK_MUTED};white-space:nowrap;">
          {_html.escape(text)}</div>"""
        cost_html = (cost_div(costs[0], G['sprite_cx'][0])
                     + cost_div(costs[1], G['sprite_cx'][1])
                     + f"""<div style="position:absolute;left:{W // 2 - 60}px;width:120px;
          top:{G['cost_row_top'] + 2}px;text-align:center;z-index:2;font-size:17px;
          font-style:italic;color:#7a5a36;">gold ×1.5</div>""")

    num_rows = "".join(f"""
      <div style="display:grid;grid-template-columns:1fr 300px 1fr;align-items:center;
        padding:10px 0;border-bottom:1px solid rgba(94,66,30,.28);">
        <div style="text-align:center;display:flex;flex-direction:column;gap:2px;">
          <span style="font-size:34px;font-weight:700;color:{r['lc']};">{_html.escape(r['left'])}</span>
          <span style="font-size:20px;font-style:italic;color:#7a5a36;">{_html.escape(r['left_sub'])}</span>
        </div>
        <div style="text-align:center;font-family:{fonts['title_sc']};font-size:24px;
          letter-spacing:3px;color:{SEPIA};">{_html.escape(r['label'])}</div>
        <div style="text-align:center;display:flex;flex-direction:column;gap:2px;">
          <span style="font-size:34px;font-weight:700;color:{r['rc']};">{_html.escape(r['right'])}</span>
          <span style="font-size:20px;font-style:italic;color:#7a5a36;">{_html.escape(r['right_sub'])}</span>
        </div>
      </div>""" for r in rows)

    body = f"""
  <!-- header card -->
  <div style="position:absolute;left:44px;right:44px;top:{G['header_top']}px;
    height:{G['header_h']}px;background:rgba(236,223,194,.78);border:2px solid {SEPIA};
    box-shadow:0 0 0 5px rgba(107,74,30,.12), 0 12px 28px rgba(94,66,30,.25);"></div>
  <div style="position:absolute;left:44px;right:44px;top:{G['header_top'] + 26}px;
    display:flex;justify-content:center;z-index:2;">
    <div style="border:1.5px solid {accent};color:{accent};font-family:{fonts['title_sc']};
      letter-spacing:6px;font-size:34px;padding:6px 30px;">{_html.escape(label)}</div>
  </div>
  <div style="position:absolute;left:{W // 2 - 60}px;width:120px;top:{G['sprite_bottom'] - 150}px;
    display:flex;flex-direction:column;align-items:center;gap:10px;z-index:2;">
    <div style="width:9px;height:9px;background:{SEPIA};transform:rotate(45deg);"></div>
    <div style="font-family:{fonts['title_sc']};font-size:30px;letter-spacing:4px;
      color:{INK_MUTED};">vs</div>
    <div style="width:9px;height:9px;background:{SEPIA};transform:rotate(45deg);"></div>
  </div>
  {name_div(u1['name'], 'n1', G['sprite_cx'][0])}
  {name_div(u2['name'], 'n2', G['sprite_cx'][1])}
  {cost_html}

  <!-- gameplay window borders (the window itself is cut to alpha afterward) -->
  <div style="position:absolute;left:0;right:0;top:{G['game_top'] - 2}px;height:2px;
    background:rgba(94,66,30,.55);z-index:2;"></div>
  <div style="position:absolute;left:0;right:0;top:{G['game_top'] + G['game_h']}px;height:2px;
    background:rgba(94,66,30,.55);z-index:2;"></div>

  <!-- health strip: name plates + bar frame (interior cut to alpha afterward) -->
  <div style="position:absolute;left:44px;right:44px;top:{G['hp_top']}px;
    display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    <div style="background:rgba(236,223,194,.85);border:2px solid {SEPIA};
      height:{G['hp_plate_h']}px;display:flex;align-items:center;justify-content:center;
      font-family:{fonts['title']};font-size:42px;color:{INK};white-space:nowrap;
      overflow:hidden;">{_html.escape(u1['name'].replace('Elite ', ''))}</div>
    <div style="background:rgba(236,223,194,.85);border:2px solid {SEPIA};
      height:{G['hp_plate_h']}px;display:flex;align-items:center;justify-content:center;
      font-family:{fonts['title']};font-size:42px;color:{INK};white-space:nowrap;
      overflow:hidden;">{_html.escape(u2['name'].replace('Elite ', ''))}</div>
  </div>
  <div style="position:absolute;left:44px;right:44px;top:{G['hp_bar_top']}px;
    height:{G['hp_bar_h'] + 4}px;border:2px solid {SEPIA};"></div>

  <!-- the numbers -->
  <div style="position:absolute;left:44px;right:44px;top:{G['num_top']}px;
    bottom:{G['num_bottom']}px;background:rgba(236,223,194,.78);border:2px solid {SEPIA};
    box-shadow:0 0 0 5px rgba(107,74,30,.12), 0 12px 28px rgba(94,66,30,.25);
    padding:22px 34px 24px;display:flex;flex-direction:column;">
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:10px;">
      <div style="width:10px;height:10px;background:{SEPIA};transform:rotate(45deg);"></div>
      <div style="font-family:{fonts['title_sc']};font-size:30px;letter-spacing:3px;
        color:{INK_BODY};">The Numbers</div>
      <div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(94,66,30,.55),transparent);"></div>
    </div>
    {num_rows}
    <div style="margin-top:auto;display:flex;align-items:center;gap:14px;padding-top:16px;">
      <div style="width:9px;height:9px;background:{SEPIA};transform:rotate(45deg);flex:none;"></div>
      <div style="font-size:32px;font-style:italic;color:{INK_BODY};text-wrap:pretty;">
        {_html.escape(why)}</div>
    </div>
  </div>
  <script>
    (function(){{ for (const id of ['n1','n2']) {{ var t=document.getElementById(id); var s=42;
      while (t.scrollWidth > {side_w - 16} && s > 24) {{ s -= 2; t.style.fontSize = s+'px'; }} }} }})();
  </script>"""
    _shoot(_page_doc(fonts, W, H, body), out_png, size)

    # cut the live windows to transparent
    img = Image.open(out_png).convert("RGBA")
    holes = [
        (0, G["game_top"], W, G["game_top"] + G["game_h"]),
        (HP_INT_X, G["hp_bar_top"] + 2, HP_INT_X + HP_INT_W,
         G["hp_bar_top"] + 2 + G["hp_bar_h"]),
    ]
    empty = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    for x0, y0, x1, y1 in holes:
        img.paste(empty.resize((x1 - x0, y1 - y0)), (x0, y0))
    img.save(out_png)
    return Path(out_png)


def render_hp_frames(sidecar, raw_duration, out_dir, n1, n2, *, fps=5.0,
                     t_min=None, t_max=None):
    """Parchment health-bar strips (design: segmented green bars + dark counts plate),
    one PNG per 1/fps of the RAW clock, sized to the bar frame's interior. Replaces the
    dark hud.py band on the shorts. Returns (dir, fps)."""
    from overlay.overlay_hp import load_sidecar, _interp
    from overlay.hud import _font
    vstart, rows = load_sidecar(str(sidecar))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    Wb, Hb = HP_INT_W, GEOM["hp_bar_h"]
    s1_max = float(rows[0]["side1"]["hp"]) or 1.0
    s2_max = float(rows[0]["side2"]["hp"]) or 1.0
    TRACK = (107, 74, 30, 36)
    FILL = (111, 138, 78, 255)          # #6f8a4e
    DIV = (94, 66, 30, 140)
    PLATE_BG = (74, 50, 32, 255)        # #4a3220
    TXT = (242, 233, 210, 255)          # #f2e9d2
    DIM = (242, 233, 210, 180)
    f_pct = _font("georgiab.ttf", 30)
    f_big = _font("georgiab.ttf", 38)
    f_small = _font("georgiab.ttf", 24)

    def strip(c1, h1, c2, h2):
        img = Image.new("RGBA", (Wb, Hb), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for x0, frac, right in ((0, h1, False), (HP_SIDE_W + HP_MID_W, h2, True)):
            d.rectangle([x0, 0, x0 + HP_SIDE_W, Hb], fill=TRACK)
            w = int(HP_SIDE_W * max(0.0, min(1.0, frac)))
            if w > 0:
                fx0 = x0 + (HP_SIDE_W - w if right else 0)
                d.rectangle([fx0, 0, fx0 + w, Hb], fill=FILL)
            for k in range(1, 5):
                dx = x0 + int(HP_SIDE_W * k / 5)
                d.rectangle([dx - 1, 0, dx + 1, Hb], fill=DIV)
            pct = f"{round(frac * 100)}%"
            if right:
                d.text((x0 + HP_SIDE_W - 14, Hb // 2), pct, font=f_pct, fill=TXT,
                       anchor="rm", stroke_width=2, stroke_fill=(60, 45, 20, 200))
            else:
                d.text((x0 + 14, Hb // 2), pct, font=f_pct, fill=TXT, anchor="lm",
                       stroke_width=2, stroke_fill=(60, 45, 20, 200))
        d.rectangle([HP_SIDE_W, 0, HP_SIDE_W + HP_MID_W, Hb], fill=PLATE_BG)
        cx = HP_SIDE_W + HP_MID_W // 2
        left_txt, right_txt = str(int(c1)), str(int(c2))
        lw = d.textlength(left_txt, font=f_big)
        d.text((cx - 14, Hb // 2), f"/{n1}", font=f_small, fill=DIM, anchor="rm")
        d.text((cx - 14 - d.textlength(f"/{n1}", font=f_small), Hb // 2), left_txt,
               font=f_big, fill=TXT, anchor="rm")
        d.rectangle([cx - 4, Hb // 2 - 4, cx + 4, Hb // 2 + 4], fill=(216, 196, 154, 255))
        d.text((cx + 14, Hb // 2), right_txt, font=f_big, fill=TXT, anchor="lm")
        d.text((cx + 14 + d.textlength(right_txt, font=f_big), Hb // 2), f"/{n2}",
               font=f_small, fill=DIM, anchor="lm")
        return img

    n = max(1, int(raw_duration * fps))
    blank = Image.new("RGBA", (Wb, Hb), (0, 0, 0, 0))
    last_key, last_img = None, None
    for i in range(n):
        v = i / fps
        if (t_min is not None and v < t_min) or (t_max is not None and v > t_max):
            blank.save(out / f"f_{i:05d}.png")
            continue
        gs = v - vstart
        c1, h1 = _interp(rows, gs, "side1")
        c2, h2 = _interp(rows, gs, "side2")
        key = (round(c1), round(h1, 1), round(c2), round(h2, 1))
        if key != last_key:
            last_img = strip(c1, max(0.0, h1 / s1_max), c2, max(0.0, h2 / s2_max))
            last_key = key
        last_img.save(out / f"f_{i:05d}.png")
    return str(out), fps


# ---------------------------------------------------------------------------
# Matchup stats / time-to-kill panel — generic, derived from the combat dicts
# ---------------------------------------------------------------------------
def _dmg_per_hit(atk_cd: dict, def_cd: dict) -> tuple[float, float]:
    """(total, bonus_part) damage per hit, the game's own formula: for every attack
    class the defender carries an armor entry for, max(0, attack - armor); floor 1.
    Base melee/pierce are classes 4/3; everything else counts as bonus damage."""
    atk = json.loads(atk_cd.get("attacks_json") or "{}")
    arm = json.loads(def_cd.get("armors_json") or "{}")
    total = base = 0.0
    for k, v in atk.items():
        if k in arm and v:
            d = max(0.0, float(v) - float(arm[k]))
            total += d
            if k in ("3", "4"):
                base += d
    total = max(1.0, total)
    return total, max(0.0, total - base)


def _reload_s(cd: dict) -> float:
    """Seconds between swings. The combat dict's `attack_speed` is a RATE
    (attacks per second, = 1/reload — see combat_unit_loader / BattleUnit)."""
    rate = float(cd.get("attack_speed") or 0.5)
    return 1.0 / rate if rate > 0 else 2.0


def _eff_reload_s(cd: dict) -> float:
    """Seconds between swings, SIMPLIFIED to one number (user 2026-07-25: no ranges/
    arrows in the panel). A ramping unit (attack_speed_ramp > 0) spends the fight
    between its base reload and its floor, so it is shown as their average."""
    base = _reload_s(cd)
    if float(cd.get("attack_speed_ramp") or 0) > 0:
        floor = float(cd.get("attack_speed_min") or 0)      # min reload, SECONDS
        if floor > 0:
            return (base + floor) / 2.0
    return base


def _ttk(atk_cd: dict, def_cd: dict) -> tuple[float, float, float]:
    """(seconds to kill ONE defender, dmg/hit, bonus part). hits = ceil(hp/dmg);
    the first swing lands at t=0, so ttk = (hits-1) * effective reload."""
    dmg, bonus = _dmg_per_hit(atk_cd, def_cd)
    hp = float(def_cd.get("hp") or 1)
    hits = math.ceil(hp / dmg)
    return max(0.0, (hits - 1) * _eff_reload_s(atk_cd)), dmg, bonus


def _rate_str(cd: dict) -> str:
    return f"{_eff_reload_s(cd):.1f}s"


def render_matchup_panel(out_png, size, hero: dict, opp: dict, n1: int, n2: int,
                         why: str) -> Path:
    """The bottom panel while the fight plays: army totals, per-hit damage (with the
    bonus called out), attack rate, and the time-to-kill-one-enemy line — each row's
    advantaged side set in the accent green, disadvantaged in the red — closed by the
    'why' verdict line. hero/opp: {"name", "cd": combat-dict}. Fully generic: every
    number derives from the two combat dicts, nothing is hand-written per matchup."""
    W, H = size
    fonts = _font_stack()
    c1, c2 = hero["cd"], opp["cd"]
    hp1, hp2 = float(c1.get("hp") or 0), float(c2.get("hp") or 0)
    t1, d1, b1 = _ttk(c1, c2)          # hero killing one opponent
    t2, d2, b2 = _ttk(c2, c1)          # opponent killing one hero

    def n(x):
        return f"{x:.0f}" if abs(x - round(x)) < 1e-6 else f"{x:.1f}"

    def row(label, v1, v2, adv, sub1="", sub2="", strong=False):
        """adv: 1 = hero advantaged, 2 = opponent, 0 = neutral."""
        cl = ACCENT_WIN if adv == 1 else (ACCENT_LOSS if adv == 2 else INK)
        cr = ACCENT_WIN if adv == 2 else (ACCENT_LOSS if adv == 1 else INK)
        wl = "700" if (strong or adv == 1) else "500"
        wr = "700" if (strong or adv == 2) else "500"
        fs = 40 if strong else 34
        subs = (f'<div style="font-size:22px;color:{INK_MUTED};">{sub1}</div>' if sub1 else "",
                f'<div style="font-size:22px;color:{INK_MUTED};">{sub2}</div>' if sub2 else "")
        return f"""<div style="display:flex;align-items:center;gap:14px;padding:9px 0;
      border-bottom:1px solid rgba(94,66,30,.22);">
      <div style="flex:1;text-align:right;">
        <div style="font-size:{fs}px;font-weight:{wl};color:{cl};">{v1}</div>{subs[0]}
      </div>
      <div style="width:250px;text-align:center;font-family:{fonts['title_sc']};
        font-size:24px;letter-spacing:2px;color:{INK_MUTED};">{label}</div>
      <div style="flex:1;text-align:left;">
        <div style="font-size:{fs}px;font-weight:{wr};color:{cr};">{v2}</div>{subs[1]}
      </div>
    </div>"""

    rows = [
        row("Army", f"{n1} × {n(hp1)} HP", f"{n2} × {n(hp2)} HP",
            0, f"{n(n1 * hp1)} total", f"{n(n2 * hp2)} total"),
        row("Damage / Hit", n(d1), n(d2),
            1 if d1 / max(hp2, 1) > d2 / max(hp1, 1) else 2,
            f"incl. +{n(b1)} bonus" if b1 else "no bonus",
            f"incl. +{n(b2)} bonus" if b2 else "no bonus"),
        row("Attack Rate", _rate_str(c1), _rate_str(c2), 0),
        row("Time to Kill One", f"{t1:.1f}s", f"{t2:.1f}s",
            1 if t1 < t2 else (2 if t2 < t1 else 0), strong=True),
    ]
    body = f"""
  <div style="position:absolute;left:44px;right:44px;top:10px;bottom:12px;
    background:{PLATE};border:2px solid {SEPIA};
    box-shadow:0 0 0 5px rgba(107,74,30,.12), 0 14px 30px rgba(94,66,30,.3);
    padding:16px 34px 12px;display:flex;flex-direction:column;">
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:4px;">
      <div style="width:10px;height:10px;background:{SEPIA};transform:rotate(45deg);"></div>
      <div style="font-family:{fonts['title_sc']};font-size:28px;letter-spacing:3px;
        color:{INK_BODY};">The Numbers</div>
      <div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(94,66,30,.55),transparent);"></div>
    </div>
    {''.join(rows)}
    <div style="flex:1;display:flex;align-items:center;gap:18px;padding-top:10px;">
      <div style="width:9px;height:9px;background:{SEPIA};transform:rotate(45deg);flex:none;"></div>
      <div style="font-size:31px;font-style:italic;color:{INK_BODY};line-height:1.3;">
        {_html.escape(why)}</div>
    </div>
  </div>"""
    return _shoot(_band_doc(fonts, size, body), out_png, size)


def render_caption(out_png, size, text) -> Path:
    """The 'why' caption, styled as the long-form Verdict band: hairline rules above and
    below, italic EB Garamond between them."""
    W, H = size
    body = f"""
  <div style="position:absolute;left:44px;right:44px;top:16px;
    border-top:1.5px solid {HAIRLINE};border-bottom:1.5px solid {HAIRLINE};
    padding:22px 34px;display:flex;align-items:center;gap:22px;">
    <div style="width:9px;height:9px;background:{SEPIA};transform:rotate(45deg);flex:none;"></div>
    <div style="font-size:38px;font-weight:500;font-style:italic;color:{INK_BODY};
      line-height:1.35;">{_html.escape(text)}</div>
  </div>"""
    return _shoot(_band_doc(_font_stack(), size, body), out_png, size)


def render_cta(out_png, size, subject_name, subject_slug, subject_icon,
               handle="aoe2matchup.com", n_matchups=0) -> Path:
    """The design's Outro screen: Watch the Full / Breakdown, diamond divider, the
    dynamic 'All N matchups' subtitle, the unit on a glow stage, and the site pill."""
    W, H = size
    fonts = _font_stack()
    sub = (f"All {n_matchups} matchups, tested and timed — full unit deep dive "
           f"on the channel." if n_matchups else
           "Every matchup, tested and timed — full unit deep dive on the channel.")
    body = f"""
  <div style="position:absolute;left:70px;right:70px;top:260px;display:flex;
    flex-direction:column;align-items:center;gap:12px;text-align:center;">
    <div style="font-family:{fonts['title_sc']};font-size:44px;letter-spacing:6px;
      color:{INK_MUTED};">Watch the Full</div>
    <div style="font-family:{fonts['title']};font-size:130px;line-height:1;color:{INK};
      text-shadow:0 2px 0 rgba(236,223,194,.8), 0 4px 6px rgba(94,66,30,.35);">Breakdown</div>
    <div style="display:flex;align-items:center;gap:16px;width:520px;margin-top:8px;">
      <div style="height:1.5px;flex:1;background:linear-gradient(90deg,transparent,rgba(94,66,30,.6));"></div>
      <div style="width:10px;height:10px;background:{SEPIA};transform:rotate(45deg);flex:none;"></div>
      <div style="height:1.5px;flex:1;background:linear-gradient(90deg,rgba(94,66,30,.6),transparent);"></div>
    </div>
    <div style="font-size:36px;font-style:italic;color:{INK_MUTED};max-width:760px;
      line-height:1.4;text-wrap:pretty;">{_html.escape(sub)}</div>
  </div>
  <div style="position:absolute;left:50%;transform:translateX(-50%);top:1400px;
    width:440px;height:110px;border-radius:50%;
    background:radial-gradient(closest-side, rgba(122,90,42,.3), transparent 70%);"></div>
  <div style="position:absolute;left:0;right:0;bottom:150px;display:flex;justify-content:center;">
    <div style="border:1.5px solid {SEPIA};color:{SEPIA};background:rgba(236,223,194,.55);
      font-family:{fonts['title_sc']};letter-spacing:7px;font-size:38px;
      padding:12px 44px;">{_html.escape(handle)}</div>
  </div>"""
    _shoot(_page_doc(fonts, W, H, body), out_png, size)
    img = Image.open(out_png).convert("RGBA")
    sp = _sprite(subject_slug, subject_icon)
    if sp is not None:
        spr = _fit(sp, (int(W * 0.7), 540))
        img.alpha_composite(spr, ((W - spr.width) // 2, 1500 - spr.height))
    img.save(out_png)
    return Path(out_png)
