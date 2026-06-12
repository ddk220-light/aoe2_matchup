"""
hud.py — Pillow renderer for the LIVE bottom HUD strip (survivor counts + HP bars).

Pillow (not HTML) because the HUD updates every frame as units die; redrawing
text on an image is instant, whereas relaunching headless Chrome per frame is not.
Matches the site's gold/parchment palette so it sits next to the HTML intro/outro
cards. Output is a transparent RGBA PNG for ffmpeg overlay.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Cross-platform font resolution: map a logical name to per-OS candidate paths.
_FONT_MAP = {
    "georgiab.ttf": ["C:/Windows/Fonts/georgiab.ttf",
                     "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
                     "/Library/Fonts/Georgia Bold.ttf"],
    "arialbd.ttf": ["C:/Windows/Fonts/arialbd.ttf",
                    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                    "/Library/Fonts/Arial Bold.ttf",
                    "/System/Library/Fonts/Helvetica.ttc"],
    "georgia.ttf": ["C:/Windows/Fonts/georgia.ttf",
                    "/System/Library/Fonts/Supplemental/Georgia.ttf",
                    "/Library/Fonts/Georgia.ttf"],
}
GOLD = (201, 168, 76, 255)
GOLD_LIGHT = (219, 185, 96, 255)
TEXT = (239, 230, 210, 255)
MUTED = (168, 152, 120, 255)
PANEL = (20, 16, 10, 205)
PANEL_BORDER = (139, 105, 20, 255)
HP_GREEN = (110, 170, 70, 255)
HP_RED = (168, 48, 48, 255)
HP_TRACK = (40, 32, 22, 230)


@lru_cache(maxsize=16)
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_MAP.get(name, [name]):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


@lru_cache(maxsize=16)
def _icon(path: str, px: int) -> Image.Image | None:
    if not path or not Path(path).exists():
        return None
    im = Image.open(path).convert("RGBA").resize((px, px), Image.LANCZOS)
    return im


def _hp_color(pct: float):
    # green -> yellow -> red as pct falls
    if pct > 0.5:
        return HP_GREEN
    if pct > 0.2:
        return (210, 170, 60, 255)
    return HP_RED


def _draw_side(draw: ImageDraw.ImageDraw, base: Image.Image, *, x, w, cy,
               name, icon_path, cur, start, hp, align_left=True, dead=False,
               show_bar=True):
    icon_px = 72
    pad = 16
    if icon_path:
        icon = _icon(icon_path, icon_px)
        if icon is not None:
            iy = cy - icon_px // 2
            ix = x + pad if align_left else x + w - pad - icon_px
            if dead:
                icon = Image.eval(icon, lambda v: int(v * 0.45))
            base.alpha_composite(icon, (ix, iy))
            # gold frame
            draw.rectangle([ix, iy, ix + icon_px, iy + icon_px], outline=GOLD, width=2)

    txt_x0 = x + pad + icon_px + 14 if align_left else x + pad
    txt_x1 = x + w - pad if align_left else x + w - pad - icon_px - 14
    anchor_x = txt_x0 if align_left else txt_x1
    a = "la" if align_left else "ra"

    nm_font = _font("georgiab.ttf", 26)
    cnt_font = _font("arialbd.ttf", 40)
    sub_font = _font("georgia.ttf", 18)

    draw.text((anchor_x, cy - 34), name, font=nm_font,
              fill=MUTED if dead else GOLD_LIGHT, anchor=a)

    # survivor count (big) + "/ start"
    cnt = str(cur)
    if align_left:
        draw.text((anchor_x, cy + 2), cnt, font=cnt_font, fill=TEXT, anchor="la")
        bb = draw.textbbox((anchor_x, cy + 2), cnt, font=cnt_font, anchor="la")
        draw.text((bb[2] + 8, cy + 18), f"/ {start}", font=sub_font, fill=MUTED, anchor="la")
        bar_x0 = anchor_x
        bar_x1 = txt_x1
    else:
        draw.text((anchor_x, cy + 2), cnt, font=cnt_font, fill=TEXT, anchor="ra")
        bb = draw.textbbox((anchor_x, cy + 2), cnt, font=cnt_font, anchor="ra")
        draw.text((bb[0] - 8, cy + 18), f"/ {start}", font=sub_font, fill=MUTED, anchor="ra")
        bar_x0 = txt_x0
        bar_x1 = anchor_x

    if not show_bar:
        return
    # HP bar
    by = cy + 50
    bh = 9
    draw.rounded_rectangle([bar_x0, by, bar_x1, by + bh], radius=4, fill=HP_TRACK)
    fill_w = int((bar_x1 - bar_x0) * max(0.0, min(1.0, hp)))
    if fill_w > 2:
        if align_left:
            draw.rounded_rectangle([bar_x0, by, bar_x0 + fill_w, by + bh],
                                   radius=4, fill=_hp_color(hp))
        else:
            draw.rounded_rectangle([bar_x1 - fill_w, by, bar_x1, by + bh],
                                   radius=4, fill=_hp_color(hp))


def _draw_top_hpbar(draw, img, *, x0, x1, name1, hp1, cur1, start1,
                    name2, hp2, cur2, start2, t, scale=1.0,
                    icon1=None, icon2=None, trend=(0, 0)):
    """A prominent fighting-game style dual army-HP bar across the TOP. Each side's
    bar fills its half and DRAINS from the centre outward as the army's total HP falls
    (full health meets in the middle, damage recedes toward the outer edge). The bars
    carry quarter tick-marks and a live HP%% label at their outer end; the central
    plate shows each side's remaining units as "cur/start"; the name tabs cap the
    outer ends with the unit's ICON + name."""
    s = scale
    top_y = int(82 * s)                     # headroom above the bar for the name tabs
    bar_h = int(46 * s)
    gap = int(150 * s)                      # half-width of the centre count plate
    skew = int(16 * s)                      # parallelogram slant for an angular look
    center = (x0 + x1) // 2
    nm_font = _font("georgiab.ttf", int(40 * s))     # unit names in the tabs
    cnt_font = _font("arialbd.ttf", int(34 * s))     # centre plate: live count
    of_font = _font("arialbd.ttf", int(21 * s))      # centre plate: "/start"
    pct_font = _font("arialbd.ttf", int(24 * s))     # HP% at the bar's outer end
    by0, by1 = top_y, top_y + bar_h

    def _bar(bx0, bx1, hp, left_anchored):
        # outer shadow plate + dark track, then the coloured fill
        draw.rectangle([bx0 - 3, by0 - 3, bx1 + 3, by1 + 3], fill=PANEL)
        draw.rectangle([bx0, by0, bx1, by1], fill=HP_TRACK, outline=PANEL_BORDER, width=2)
        span = bx1 - bx0
        fw = int(span * max(0.0, min(1.0, hp)))
        if fw > 2:
            col = _hp_color(hp)
            if left_anchored:               # fill from the OUTER (left) edge inward
                draw.rectangle([bx0, by0, bx0 + fw, by1], fill=col)
                edge = bx0 + fw
                draw.polygon([(edge, by0), (edge + skew, by0), (edge, by1)], fill=col)
                draw.line([(edge, by0), (edge, by1)], fill=GOLD_LIGHT, width=2)
            else:                           # fill from the OUTER (right) edge inward
                draw.rectangle([bx1 - fw, by0, bx1, by1], fill=col)
                edge = bx1 - fw
                draw.polygon([(edge, by0), (edge - skew, by1), (edge, by1)], fill=col)
                draw.line([(edge, by0), (edge, by1)], fill=GOLD_LIGHT, width=2)
        # quarter ticks over fill + track (subtle scale reference)
        for q in (0.25, 0.5, 0.75):
            tx = int(bx0 + span * q) if left_anchored else int(bx1 - span * q)
            draw.line([(tx, by0 + 2), (tx, by1 - 2)], fill=(0, 0, 0, 90), width=max(1, int(2 * s)))
        # live HP% at the OUTER end, stroked for legibility on fill or empty track
        pct = f"{max(0.0, min(1.0, hp)):.0%}"
        px = bx0 + int(12 * s) if left_anchored else bx1 - int(12 * s)
        draw.text((px, (by0 + by1) // 2), pct, font=pct_font,
                  fill=(255, 255, 255, 235), anchor=("lm" if left_anchored else "rm"),
                  stroke_width=max(1, int(2 * s)), stroke_fill=(10, 8, 5, 220))

    l_x0, l_x1 = x0, center - gap
    r_x0, r_x1 = center + gap, x1
    _bar(l_x0, l_x1, hp1, left_anchored=True)
    _bar(r_x0, r_x1, hp2, left_anchored=False)

    # centre plate: LIVE remaining units of each side as "cur/start · cur/start"
    draw.rectangle([center - gap + 4, by0 - 4, center + gap - 4, by1 + 4],
                   fill=PANEL, outline=PANEL_BORDER, width=2)
    cy = (by0 + by1) // 2
    sep = int(14 * s)

    def _count_group(cur, start, left):
        cur_s, of_s = str(int(cur)), f"/{int(start)}"
        of_w = draw.textbbox((0, 0), of_s, font=of_font)[2]
        if left:        # ends at center - sep:  [cur][/start]
            draw.text((center - sep - of_w, cy + int(4 * s)), of_s, font=of_font,
                      fill=MUTED, anchor="lm")
            draw.text((center - sep - of_w - int(2 * s), cy), cur_s, font=cnt_font,
                      fill=TEXT, anchor="rm")
        else:           # starts at center + sep
            cur_w = draw.textbbox((0, 0), cur_s, font=cnt_font)[2]
            draw.text((center + sep, cy), cur_s, font=cnt_font, fill=TEXT, anchor="lm")
            draw.text((center + sep + cur_w + int(2 * s), cy + int(4 * s)), of_s,
                      font=of_font, fill=MUTED, anchor="lm")

    _count_group(cur1, start1, left=True)
    draw.text((center, cy), "·", font=cnt_font, fill=MUTED, anchor="mm")
    _count_group(cur2, start2, left=False)

    # momentum arrows at the plate's edges: ▲ green = winning the trade right now,
    # ▼ red = losing it (computed from each side's losses over the last few seconds)
    t1, t2 = trend
    ah, aw = int(15 * s), int(18 * s)

    def _arrow(cx_, tr):
        if not tr:
            return
        up = tr > 0
        col = (110, 190, 80, 240) if up else (210, 70, 60, 240)
        y0a, y1a = cy - ah // 2, cy + ah // 2
        pts = ([(cx_ - aw // 2, y1a), (cx_ + aw // 2, y1a), (cx_, y0a)] if up
               else [(cx_ - aw // 2, y0a), (cx_ + aw // 2, y0a), (cx_, y1a)])
        draw.polygon(pts, fill=col)

    _arrow(center - gap + int(22 * s), t1)
    _arrow(center + gap - int(22 * s), t2)

    # name TABS that read as PART of the bar: a light semi-transparent plate at the bar's
    # outer end, rounded on TOP only, bottom flush with the bar, carrying the unit's ICON
    # (outer side) + name. Black text for legibility over the bright sky/terrain.
    padx = int(16 * s)
    tab_h = int(64 * s)
    ic_px = int(50 * s)
    bytop = by0 - tab_h

    def _name_tab(name, icon_path, left):
        icon = _icon(icon_path, ic_px) if icon_path else None
        ic_w = (ic_px + int(10 * s)) if icon is not None else 0
        tw = draw.textbbox((0, 0), name, font=nm_font)[2]
        w = tw + ic_w + 2 * padx
        bx0, bx1 = (l_x0, l_x0 + w) if left else (r_x1 - w, r_x1)
        try:
            draw.rounded_rectangle([bx0, bytop, bx1, by0], radius=int(10 * s),
                                   fill=(239, 232, 213, 188), outline=PANEL_BORDER, width=2,
                                   corners=(True, True, False, False))
        except TypeError:                    # older Pillow without per-corner control
            draw.rectangle([bx0, bytop, bx1, by0], fill=(239, 232, 213, 188),
                           outline=PANEL_BORDER, width=2)
        cyt = (bytop + by0) // 2
        if icon is not None:                 # icon hugs the OUTER edge of the tab
            iy = cyt - ic_px // 2
            ix = bx0 + padx if left else bx1 - padx - ic_px
            img.alpha_composite(icon, (ix, iy))
            draw.rectangle([ix, iy, ix + ic_px, iy + ic_px],
                           outline=PANEL_BORDER, width=max(1, int(2 * s)))
            tx = ix + ic_px + int(10 * s) if left else ix - int(10 * s)
        else:
            tx = bx0 + padx if left else bx1 - padx
        draw.text((tx, cyt), name, font=nm_font, fill=(12, 10, 8, 255),
                  anchor=("lm" if left else "rm"))

    _name_tab(name1, icon1, True)
    _name_tab(name2, icon2, False)


def hud_band_height(H: int) -> int:
    """Height (px) of the band at the top of a `H`-tall canvas that the HUD actually
    occupies: bar bottom = (82+46)*sc, plus the centre plate (+4), borders and shadow.
    Rendering ONLY this band (instead of a full transparent frame) cuts the PNG
    encode/decode work ~85% — the overlay anchors at 0:0 either way."""
    return int(140 * (H / 1440.0)) + 4


def render_hud_frame(name1, icon1, start1, cur1, hp1,
                     name2, icon2, start2, cur2, hp2,
                     t=None, size=(1280, 720), band_only=False,
                     trend=(0, 0)) -> Image.Image:
    """Return an RGBA frame (transparent except the HUD). `size` is the FULL video
    canvas the HUD is scaled for; with band_only=True the returned image is cropped
    to the top hud_band_height() strip (composite it at 0:0).

    Layout: ONLY a prominent dual army-HP bar across the TOP (drains from the centre as
    each army loses HP). The unit DETAIL cards live at the bottom and are composited
    separately (compose.make_live_overlay_video) so they can be wider/shorter/more
    transparent — there's no bottom count strip anymore.
    """
    W, H = size
    img = Image.new("RGBA", (W, hud_band_height(H) if band_only else H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    sc = H / 1440.0                          # all sizes tuned at 1440p

    bar_margin = int(46 * sc)
    _draw_top_hpbar(draw, img, x0=bar_margin, x1=W - bar_margin,
                    name1=name1, hp1=hp1, cur1=cur1, start1=start1,
                    name2=name2, hp2=hp2, cur2=cur2, start2=start2, t=t, scale=sc,
                    icon1=icon1, icon2=icon2, trend=trend)
    return img


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scenario_builder/
    from overlay.overlay_data import get_unit_card
    u1 = get_unit_card("Wu", "elite_fire_archer_wu")
    u2 = get_unit_card("Wu", "jian_swordsman_wu")
    frame = render_hud_frame(u1["name"], u1["icon"], 30, 30, 1.0,
                             u2["name"], u2["icon"], 30, 6, 0.06, t=24)
    out = Path(__file__).parent / "samples" / "_hud_frame_test.png"
    out.parent.mkdir(exist_ok=True)
    frame.save(out)
    print("WROTE", out)
