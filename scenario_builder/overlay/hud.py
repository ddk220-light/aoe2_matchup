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
               name, icon_path, cur, start, hp, align_left=True, dead=False):
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


def render_hud_frame(name1, icon1, start1, cur1, hp1,
                     name2, icon2, start2, cur2, hp2,
                     t=None, size=(1280, 720)) -> Image.Image:
    """Return an RGBA frame (full video size, transparent except the HUD strip)."""
    W, H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    strip_h = 132
    margin = 26
    y0 = H - strip_h - margin
    x0, x1 = margin, W - margin
    draw.rounded_rectangle([x0, y0, x1, y0 + strip_h], radius=16,
                           fill=PANEL, outline=PANEL_BORDER, width=2)
    cy = y0 + strip_h // 2

    half = (x1 - x0) // 2
    center = (x0 + x1) // 2
    _draw_side(draw, img, x=x0, w=half - 30, cy=cy, name=name1, icon_path=icon1,
               cur=cur1, start=start1, hp=hp1, align_left=True, dead=cur1 == 0)
    _draw_side(draw, img, x=center + 30, w=half - 30, cy=cy, name=name2, icon_path=icon2,
               cur=cur2, start=start2, hp=hp2, align_left=False, dead=cur2 == 0)

    # center VS + timer
    vs_font = _font("georgiab.ttf", 34)
    draw.text((center, cy - 6), "VS", font=vs_font, fill=GOLD, anchor="mm")
    if t is not None:
        draw.text((center, cy + 30), f"{t:0.0f}s", font=_font("georgia.ttf", 16),
                  fill=MUTED, anchor="mm")
    return img


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from overlay_data import get_unit_card
    u1 = get_unit_card("Wu", "elite_fire_archer_wu")
    u2 = get_unit_card("Wu", "jian_swordsman_wu")
    frame = render_hud_frame(u1["name"], u1["icon"], 30, 30, 1.0,
                             u2["name"], u2["icon"], 30, 6, 0.06, t=24)
    out = Path(__file__).parent / "samples" / "_hud_frame_test.png"
    out.parent.mkdir(exist_ok=True)
    frame.save(out)
    print("WROTE", out)
