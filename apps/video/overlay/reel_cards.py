"""reel_cards.py — Pillow cards for the vertical short-form (Reels/Shorts/TikTok)
unit-analysis reel.

Separate from render_card.py (which shells out to headless Chrome for the long-form
HTML cards): the reel's bands are simple, need no browser, and must render fast next to
the per-frame HP band. Every card is a transparent RGBA PNG sized to a BAND of the
1080x1920 canvas (or a full-canvas hero), overlaid at a fixed y by reel_compose. Palette
matches hud.py so the bands sit next to the burned-in HP bar.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from overlay.hud import _font  # shared cross-platform font resolver + palette

REPO_ROOT = Path(__file__).resolve().parents[3]
SPRITE_DIR = REPO_ROOT / "apps" / "website" / "static" / "img" / "unit_sprites"

CREAM = (239, 232, 213, 255)
GOLD = (201, 168, 76, 255)
MUTED = (168, 152, 120, 255)
BG_DARK = (11, 10, 7, 255)

# verdict kind -> (accent colour, chip label). Keys are the V2 categorization category
# names, plus generic win/loss for hand-curated reels with no categorization.
VERDICT = {
    "expected_win":    ((120, 200, 90, 255),  "EXPECTED WIN"),
    "unexpected_win":  ((130, 220, 130, 255), "UNEXPECTED WIN"),
    "expected_loss":   ((205, 100, 80, 255),  "EXPECTED LOSS"),
    "unexpected_loss": ((230, 74, 62, 255),   "UNEXPECTED LOSS"),
    "win":             ((120, 200, 90, 255),  "VICTORY"),
    "loss":            ((225, 74, 62, 255),   "DEFEAT"),
}


def verdict_style(kind: str):
    return VERDICT.get(kind, ((200, 200, 200, 255), str(kind).replace("_", " ").upper()))


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
    """Load an image and scale it to fit inside `box` (w, h), preserving aspect."""
    im = Image.open(path).convert("RGBA")
    bw, bh = box
    scale = min(bw / im.width, bh / im.height)
    return im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                     Image.LANCZOS)


def _ctext(draw, cx, y, text, font, fill, anchor="ma", stroke=3,
           stroke_fill=(8, 6, 4, 255)):
    draw.text((cx, y), text, font=font, fill=fill, anchor=anchor,
              stroke_width=stroke, stroke_fill=stroke_fill)


def _pill(draw, cx, cy, text, font, textcol, *, bg=(16, 12, 8, 235), border=None,
          padx=36, pady=18):
    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    w, h = tw + 2 * padx, th + 2 * pady
    x0, y0 = cx - w // 2, cy - h // 2
    try:
        draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=h // 2, fill=bg,
                               outline=border or textcol, width=4)
    except AttributeError:
        draw.rectangle([x0, y0, x0 + w, y0 + h], fill=bg, outline=border or textcol,
                       width=4)
    draw.text((cx, cy), text, font=font, fill=textcol, anchor="mm")
    return h


def render_top_band(out_png, size, subject_name, subject_slug, subject_icon,
                    verdict_kind) -> Path:
    """TOP band: verdict chip + subject NAME + hero sprite (the unit being analysed)."""
    W, H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col, label = verdict_style(verdict_kind)
    _pill(d, W // 2, 150, label, _font("arialbd.ttf", 54), col)
    _ctext(d, W // 2, 205, subject_name.upper(), _font("georgiab.ttf", 62), CREAM)
    sp = _sprite(subject_slug, subject_icon)
    if sp is not None:
        top = 300
        spr = _fit(sp, (int(W * 0.55), H - top - 10))
        img.alpha_composite(spr, ((W - spr.width) // 2, top + (H - top - spr.height) // 2))
    img.save(out_png)
    return Path(out_png)


def render_caption(out_png, size, text) -> Path:
    """A centred, wrapped 'why this matchup' caption strip for the bottom band."""
    W, H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font("georgia.ttf", 40)
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if cur and d.textlength(t, font=font) > W - 120:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    y = 16
    for ln in lines[:3]:
        _ctext(d, W // 2, y, ln, font, CREAM, stroke=3)
        y += 52
    img.save(out_png)
    return Path(out_png)


def render_intro_hero(out_png, size, subject_name, civ, subject_slug,
                      subject_icon) -> Path:
    """Full-canvas opening hero: 'UNIT ANALYSIS' + NAME + civ + big sprite."""
    W, H = size
    img = Image.new("RGBA", (W, H), BG_DARK)
    d = ImageDraw.Draw(img)
    _ctext(d, W // 2, 210, "UNIT ANALYSIS", _font("arialbd.ttf", 50), GOLD)
    _ctext(d, W // 2, 290, subject_name.upper(), _font("georgiab.ttf", 88), CREAM)
    _ctext(d, W // 2, 420, civ, _font("georgia.ttf", 46), MUTED)
    sp = _sprite(subject_slug, subject_icon)
    if sp is not None:
        spr = _fit(sp, (int(W * 0.8), int(H * 0.46)))
        img.alpha_composite(spr, ((W - spr.width) // 2, 560))
    _ctext(d, W // 2, H - 360, "vs every unique unit", _font("georgia.ttf", 44), GOLD)
    img.save(out_png)
    return Path(out_png)


def render_cta(out_png, size, subject_name, subject_slug, subject_icon,
               handle="@aoe2matchup") -> Path:
    """Full-canvas closing call-to-action driving to the long-form breakdown."""
    W, H = size
    img = Image.new("RGBA", (W, H), BG_DARK)
    d = ImageDraw.Draw(img)
    _ctext(d, W // 2, H // 2 - 300, "WATCH THE FULL", _font("georgiab.ttf", 64), CREAM)
    _ctext(d, W // 2, H // 2 - 210, "BREAKDOWN", _font("georgiab.ttf", 104), GOLD)
    sp = _sprite(subject_slug, subject_icon)
    if sp is not None:
        spr = _fit(sp, (int(W * 0.5), int(H * 0.3)))
        img.alpha_composite(spr, ((W - spr.width) // 2, H // 2 - 30))
    _pill(d, W // 2, H - 380, handle, _font("arialbd.ttf", 54), BG_DARK,
          bg=GOLD, border=GOLD)
    img.save(out_png)
    return Path(out_png)
