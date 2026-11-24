"""Live ranking overlays for ranking videos: three concepts (A banner row, B scroll ladder, C battle line).

Each concept renders full-frame 2560x1440 RGBA frames for
  - rest(entries, n)            : what shows during a battle (A: a mini strip; B/C: nothing)
  - beat(entries, n, t)          : the 4.2 s result beat after battle n ends (n = index of the new entry)
  - finale(entries, t)           : the closing full ranking
`entries` is the video's list of Entry in play order; final ranks are precomputed.
Specs: data/local/review/cavarcher-video/overlay-concepts.md (local design notes).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from overlay.static_stats import GAME, GameFont

W, H = 2560, 1440


def hexc(h, a=255):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


P = {k: hexc(v) for k, v in dict(
    parchment='E8D5A8', parchment_light='F6EBCB', parchment_dim='CDBE9A', parchment_edge='B79A62',
    wood_dark='24160B', wood_mid='4A2E18', gold='D9A93A', gold_bright='FFD76A', gold_dark='8A6420',
    ink='2B1B0E', ink_soft='6B5433', cream='F3E6C4', win='3E8E41', win_light='7CC46A',
    loss='B3261E', loss_light='D9584A', draw='8F8A7A').items()}


def out_cubic(u): u = min(max(u, 0), 1); return 1 - (1 - u) ** 3
def in_cubic(u): u = min(max(u, 0), 1); return u ** 3
def in_out_cubic(u):
    u = min(max(u, 0), 1)
    return 4 * u ** 3 if u < .5 else 1 - (-2 * u + 2) ** 3 / 2
def out_back(u):
    u = min(max(u, 0), 1)
    return 1 + 2.70158 * (u - 1) ** 3 + 1.70158 * (u - 1) ** 2
def pulse(u): return math.sin(math.pi * min(max(u, 0), 1))
def seg(t, a, b): return (t - a) / (b - a) if b > a else 1.0
def lerp(a, b, u): return a + (b - a) * u
def lerp_box(a, b, u): return tuple(lerp(x, y, u) for x, y in zip(a, b))


@dataclass
class Entry:
    key: str
    civ: str
    unit: str
    count: int
    opp: int
    record: list          # e.g. ['W','W','D'] (wins, then draws, then losses)
    margin: float
    rank: int             # final rank, 1 = best
    icon: Path
    emblem: Path

    @property
    def side(self): return 'win' if self.record.count('W') * 2 > len(self.record) else 'loss'


# ---------------------------------------------------------------- text & widgets
_FONT = None
SUBST = {'−': '-', '▲': '', '▼': '', '·': '-', '—': '-', '×': 'x'}


def font():
    global _FONT
    if _FONT is None:
        _FONT = GameFont(GAME)
    return _FONT


def clean(text):
    f = font()
    text = ''.join(SUBST.get(c, c) for c in text)
    return ''.join(c if c in f.glyphs else '?' for c in text)


@lru_cache(maxsize=4096)
def text_tile(text, size, color, shadow=False):
    """Tight RGBA tile of game-font text; size is the font em size in px."""
    text = clean(text)
    f = font()
    w = math.ceil(f.width(text, size)) + 8
    tile = Image.new('RGBA', (max(w, 1), int(size * 1.45) + 8))
    f.draw(tile, (2, 0), text, size, color)
    if shadow:
        sh = Image.new('RGBA', tile.size, (0, 0, 0, 0))
        f.draw(sh, (2, 2), text, size, (0, 0, 0, 150))
        sh.alpha_composite(tile)
        tile = sh
    box = tile.getbbox() or (0, 0, 1, 1)
    return tile.crop((0, box[1] - 1 if box[1] else 0, tile.width, box[3] + 1))


def text_fit(text, size, color, max_w, floor, shadow=False):
    while size > floor and text_tile(text, size, color, shadow).width > max_w:
        size -= 1
    tile = text_tile(text, size, color, shadow)
    if tile.width > max_w:
        while len(text) > 3 and text_tile(text + '...', size, color, shadow).width > max_w:
            text = text[:-1]
        tile = text_tile(text.rstrip() + '...', size, color, shadow)
    return tile


def put(canvas, tile, x, y, anchor='lt', alpha=1.0):
    """Composite tile at (x,y) with anchor l/c/r + t/m/b."""
    if alpha <= 0:
        return
    if alpha < 1:
        tile = tile.copy()
        tile.putalpha(tile.getchannel('A').point(lambda v: int(v * alpha)))
    ax = {'l': 0, 'c': tile.width / 2, 'r': tile.width}[anchor[0]]
    ay = {'t': 0, 'm': tile.height / 2, 'b': tile.height}[anchor[1]]
    x, y = round(x - ax), round(y - ay)
    # clip to canvas
    if x >= canvas.width or y >= canvas.height or x + tile.width <= 0 or y + tile.height <= 0:
        return
    cx0, cy0 = max(0, -x), max(0, -y)
    if cx0 or cy0 or x + tile.width > canvas.width or y + tile.height > canvas.height:
        tile = tile.crop((cx0, cy0, min(tile.width, canvas.width - x), min(tile.height, canvas.height - y)))
        x, y = x + cx0, y + cy0
    canvas.alpha_composite(tile, (x, y))


@lru_cache(maxsize=512)
def rrect(w, h, r, fill, outline=None, width=0):
    im = Image.new('RGBA', (max(1, int(w)), max(1, int(h))))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=fill, outline=outline, width=width)
    return im


@lru_cache(maxsize=128)
def plate(w, h, alpha=0.94, radius=10):
    """Dark wood plate with gold trim and drop shadow (returned padded by 24 px on each side)."""
    w, h = int(w), int(h)
    pad = 24
    im = Image.new('RGBA', (w + 2 * pad, h + 2 * pad))
    sh = Image.new('RGBA', im.size)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 6, pad + w, pad + h + 6), radius, fill=(0, 0, 0, 128))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((pad, pad, pad + w - 1, pad + h - 1), radius, fill=P['wood_dark'][:3] + (int(255 * alpha),),
                        outline=P['gold'], width=3)
    d.rounded_rectangle((pad + 3, pad + 3, pad + w - 4, pad + h - 4), max(radius - 3, 1), outline=P['gold_dark'], width=1)
    return im


def put_plate(canvas, box, alpha=0.94, radius=10, offset=(0, 0)):
    x0, y0, x1, y1 = box
    put(canvas, plate(round(x1 - x0), round(y1 - y0), alpha, radius), x0 - 24 + offset[0], y0 - 24 + offset[1])


@lru_cache(maxsize=256)
def icon(path, size, dim=False):
    im = Image.open(path).convert('RGBA')
    bb = im.getbbox()
    if bb and 'menu/civs' in str(path).replace('\\', '/'):
        im = im.crop(bb)
    im.thumbnail((size, size), Image.Resampling.LANCZOS) if 'menu/civs' in str(path).replace('\\', '/') else None
    if 'menu/civs' not in str(path).replace('\\', '/'):
        im = im.resize((size, size), Image.Resampling.LANCZOS)
    if dim:
        rgb = ImageEnhance.Brightness(im.convert('RGB')).enhance(.85).convert('RGBA')
        rgb.putalpha(im.getchannel('A'))
        im = rgb
    return im


@lru_cache(maxsize=256)
def framed_icon(path, size, dim=False, border=None):
    im = icon(path, size, dim)
    out = Image.new('RGBA', (size + 8, size + 8))
    d = ImageDraw.Draw(out)
    d.rectangle((0, 0, size + 7, size + 7), fill=border or P['gold'])
    d.rectangle((2, 2, size + 5, size + 5), fill=P['wood_dark'])
    out.alpha_composite(im, (4, 4))
    return out


@lru_cache(maxsize=256)
def pip(kind, d):
    s = 4
    im = Image.new('RGBA', (d * s, d * s))
    dr = ImageDraw.Draw(im)
    fill = {'W': P['win'], 'L': P['loss'], 'D': P['draw']}[kind]
    dr.ellipse((0, 0, d * s - 1, d * s - 1), fill=P['gold'])
    dr.ellipse((2 * s, 2 * s, d * s - 1 - 2 * s, d * s - 1 - 2 * s), fill=fill)
    if kind == 'L':
        m = d * s * .3
        dr.line((m, m, d * s - m, d * s - m), fill=P['wood_dark'], width=3 * s)
        dr.line((m, d * s - m, d * s - m, m), fill=P['wood_dark'], width=3 * s)
    if kind == 'D':
        dr.line((d * s * .28, d * s / 2, d * s * .72, d * s / 2), fill=P['wood_dark'], width=3 * s)
    return im.resize((d, d), Image.Resampling.LANCZOS)


def put_pips(canvas, record, x, y, d, gap, anchor='lm', shown=3, pop=None):
    total = 3 * d + 2 * gap
    x0 = x - {'l': 0, 'c': total / 2, 'r': total}[anchor[0]]
    for i, k in enumerate(record[:shown]):
        sc = pop[i] if pop else 1.0
        if sc <= 0:
            continue
        p = pip(k, d) if sc == 1 else pip(k, d).resize((max(1, round(d * sc)),) * 2, Image.Resampling.LANCZOS)
        put(canvas, p, x0 + i * (d + gap) + d / 2, y, 'cm')


def glow(tile, alpha, radius=14, color=None):
    color = color or P['gold_bright']
    pad = radius * 2
    g = Image.new('RGBA', (tile.width + 2 * pad, tile.height + 2 * pad))
    sil = Image.new('RGBA', tile.size, color)
    sil.putalpha(tile.getchannel('A'))
    g.alpha_composite(sil, (pad, pad))
    g = g.filter(ImageFilter.GaussianBlur(radius))
    g.putalpha(g.getchannel('A').point(lambda v: min(255, int(v * 2.2 * alpha))))
    return g, pad


def scrim(canvas, alpha, box=None):
    if alpha <= 0:
        return
    box = box or (0, 0, W, H)
    layer = Image.new('RGBA', (box[2] - box[0], box[3] - box[1]), (0, 0, 0, int(255 * alpha)))
    canvas.alpha_composite(layer, (box[0], box[1]))


def margin_text(m):
    return f"{'+' if m >= 0 else '-'}{abs(round(m))}%"


def sweep(canvas, box, u, width=300, alpha=.55):
    """Bright band crossing box left->right as u goes 0->1."""
    x0, y0, x1, y1 = [round(v) for v in box]
    if not 0 < u < 1:
        return
    band = Image.new('RGBA', (width, 1))
    for i in range(width):
        band.putpixel((i, 0), P['gold_bright'][:3] + (int(255 * alpha * pulse(i / width)),))
    band = band.resize((width, y1 - y0))
    cx = lerp(x0 - width, x1, u)
    layer = Image.new('RGBA', (x1 - x0, y1 - y0))
    layer.alpha_composite(band, (round(cx - x0), 0)) if 0 <= round(cx - x0) < layer.width else None
    if round(cx - x0) < 0:
        layer.alpha_composite(band.crop((-round(cx - x0), 0, width, y1 - y0)), (0, 0))
    canvas.alpha_composite(layer, (x0, y0))


def running(entries, n):
    """Entries revealed after battle n (0-based) is added, sorted by final rank."""
    return sorted(entries[:n + 1], key=lambda e: e.rank)


def blank():
    return Image.new('RGBA', (W, H))


# ================================================================== Concept B: Scroll of Honour
class ScrollOfHonour:
    name = 'B - Scroll of Honour'
    show_pips = True
    X0, X1, BOTTOM = 620, 1940, 1424
    HEADER, DIV, PAD = 84, 44, 28

    def __init__(self, opponent_plural, title):
        self.opp = opponent_plural.upper()
        self.title = title

    def h(self, n): return max(52, min(96, 1196 // max(n, 1)))

    def layout(self, rows):
        """rows: sorted entries. Returns panel box, {key: row box}, divider y."""
        n = len(rows)
        h = self.h(n)
        height = self.HEADER + n * h + self.DIV + self.PAD
        top = self.BOTTOM - height
        y = top + self.HEADER
        boxes, div = {}, None
        for e in rows:
            if div is None and e.side == 'loss':
                div = y; y += self.DIV
            boxes[e.key] = (648, y + 1, 1912, y + h - 1)
            y += h
        if div is None:
            div = y
        return (self.X0, top, self.X1, self.BOTTOM), boxes, div, h

    def row(self, e, h, fill=None, bar=1.0, number=None, pips_pop=None, rank_text=True, rank=None):
        """Render one row tile (1264 x h)."""
        s = h / 96
        loss = e.side == 'loss'
        fill = fill or (P['parchment_dim'] if loss else P['parchment'])
        im = rrect(1264, h - 2, 4, fill).copy()
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 7, h - 3), fill=P['loss'] if loss else P['win'])
        ink = P['ink']
        mid = (h - 2) / 2
        if rank_text and rank is not None:
            size = max(30, round(48 * s))
            col = P['gold'] if rank == 1 else ink
            put(im, text_tile(str(rank), size, col), 76, mid, 'rm')
        isz = max(44, min(84, h - 12))
        put(im, framed_icon(str(e.icon), isz - 8, loss), 92, mid, 'lm')
        esz = max(36, round(60 * s))
        put(im, icon(str(e.emblem), esz), 92 + isz + 16 + esz / 2, mid, 'cm')
        nsize = max(26, round(36 * s))
        csize = max(20, round(22 * s))
        name = text_fit(e.unit, nsize, ink, 440, 26)
        civ = text_tile(e.civ, csize, P['ink_soft'])
        if h >= 72:
            put(im, name, 268, mid - 4, 'lb')
            put(im, civ, 268, mid + 6, 'lt')
        else:
            put(im, name, 268, mid, 'lm')
            if 268 + name.width + 16 + civ.width < 700:
                put(im, civ, 268 + name.width + 16, mid + 2, 'lm')
        put(im, text_tile(f'{e.count} vs {e.opp}', max(22, round(28 * s)), ink), 852, mid, 'rm')
        if self.show_pips:
            put_pips(im, e.record, 880, mid, max(18, round(28 * s)), max(6, round(10 * s)), 'lm', pop=pips_pop)
        # diverging bar, zero tick at 1080
        d.line((1080, 8, 1080, h - 10), fill=P['ink_soft'], width=2)
        bh = max(14, round(22 * s))
        length = abs(e.margin) * bar
        if length >= 1:
            col0, col1 = (P['win'], P['win_light']) if e.margin >= 0 else (P['loss'], P['loss_light'])
            x0, x1 = (1081, 1081 + length) if e.margin >= 0 else (1079 - length, 1079)
            d.rounded_rectangle((x0, mid - bh / 2, x1, mid + bh / 2), 3, fill=col0 if e.margin < 0 else col1)
        value = e.margin if number is None else number
        put(im, text_tile(margin_text(value), max(26, round(36 * s)), P['win'] if e.margin >= 0 else P['loss']),
            1256, mid, 'rm')
        return im

    @lru_cache(maxsize=1024)
    def row_cached(self, e_key, h, rank):
        e = self._by[e_key]
        return self.row(e, h, rank=rank)

    def bind(self, entries):
        self._by = {e.key: e for e in entries}
        self.entries = entries
        return self

    def panel(self, canvas, box, div, h, dy, header_alt=None, header_alpha=0.0, n_text=''):
        x0, y0, x1, y1 = box
        put_plate(canvas, (x0, y0 + dy, x1, y1 + dy), .94)
        band = rrect(1264, self.HEADER - 16, 6, P['wood_mid'])
        put(canvas, band, 648, y0 + dy + 10)
        title = text_tile(f'RANKING vs 15 {self.opp}', 34, P['gold'], True)
        put(canvas, title, 668, y0 + dy + 10 + (self.HEADER - 16) / 2, 'lm', 1 - header_alpha)
        if header_alt:
            put(canvas, text_tile(header_alt, 38, P['gold_bright'], True), 668, y0 + dy + 10 + (self.HEADER - 16) / 2,
                'lm', header_alpha)
        put(canvas, text_tile(n_text, 28, P['cream'], True), 1892, y0 + dy + 10 + (self.HEADER - 16) / 2, 'rm')
        # divider band
        dv = rrect(1264, self.DIV - 4, 4, P['wood_mid']).copy()
        dd = ImageDraw.Draw(dv)
        label = text_tile(f'BEAT THE {self.opp}   -   FELL TO THE {self.opp}', 24, P['gold_bright'])
        gap0, gap1 = 632 - label.width / 2 - 20, 632 + label.width / 2 + 20
        dd.line((12, 19, gap0, 19), fill=P['gold'], width=3)
        dd.line((gap1, 19, 1252, 19), fill=P['gold'], width=3)
        put(dv, label, 632, 19, 'cm')
        put(canvas, dv, 648, div + dy + 2)

    def rest(self, n):
        return None

    def beat(self, n, t):
        entries = self.entries
        prev = sorted(entries[:n], key=lambda e: e.rank)
        new = entries[n]
        now = running(entries, n)
        c = blank()
        rise = out_cubic(seg(t, 0, .5))
        fall = in_cubic(seg(t, 3.6, 4.2))
        sc = .35 * (rise - fall)
        scrim(c, sc)
        A, B = self.layout(prev), self.layout(now)
        u = in_out_cubic(seg(t, .6, 1.0))
        hA, hB = A[3], B[3]
        h = hA if t < .8 and prev else hB
        box = lerp_box(A[0], B[0], u)
        height = box[3] - box[1]
        dy = (1 - rise) * (height + 40) + fall * (height + 40)
        div = lerp(A[2], B[2], u)
        new_lead = new.rank == min(e.rank for e in now) and len(now) > 1
        ha = 0.0
        if new_lead:
            ha = min(out_cubic(seg(t, 1.4, 1.6)), 1 - out_cubic(seg(t, 3.0, 3.2)))
        self.panel(c, [round(v) for v in box], round(div), h, dy, 'NEW LEADER' if new_lead else None, ha,
                   f'{n + 1 if t >= 1.4 else n} of {len(entries)}')
        ranks_new = {e.key: i + 1 for i, e in enumerate(now)}
        ranks_old = {e.key: i + 1 for i, e in enumerate(prev)}
        for e in prev:
            b = lerp_box(A[1][e.key], B[1][e.key], u)
            rk = ranks_old[e.key] if t < 1.5 else ranks_new[e.key]
            tile = self.row_cached(e.key, h, rk)
            put(c, tile, b[0], b[1] + dy)
        # new row
        if t >= .9:
            b = B[1][new.key]
            xo = (1 - out_back(seg(t, .9, 1.4))) * 1400
            scale = 1.12 - .12 * out_cubic(seg(t, 1.4, 1.6))
            light = 1 - seg(t, 2.6, 3.4)
            fill = tuple(round(lerp(x, y, max(0, min(1, light))))
                         for x, y in zip(P['parchment_dim' if new.side == 'loss' else 'parchment'], P['parchment_light']))
            bar = out_cubic(seg(t, 1.4, 1.9)) if t >= 1.4 else 0
            pops = [out_back(seg(t, a, a + .15)) if t >= a else 0 for a in (1.5, 1.65, 1.8)]
            tile = self.row(new, hB, fill=fill, bar=bar, number=new.margin * bar, pips_pop=pops, rank=ranks_new[new.key])
            if t < 3.4 and t >= 1.4:
                ring = rrect(tile.width + 8, tile.height + 8, 6, None, P['gold_bright'], 4)
                tile2 = Image.new('RGBA', ring.size)
                tile2.alpha_composite(tile, (4, 4))
                tile2.alpha_composite(ring)
                tile = tile2
            if scale != 1:
                tile = tile.resize((round(tile.width * scale), round(tile.height * scale)), Image.Resampling.BILINEAR)
            cx, cy = (b[0] + b[2]) / 2 + xo, (b[1] + b[3]) / 2 + dy
            g = .85 * pulse(seg(t, 1.4, 2.0)) + .85 * pulse(seg(t, 2.0, 2.6))
            if g > .02:
                gl, pad = glow(tile, g)
                put(c, gl, cx, cy, 'cm')
            put(c, tile, cx, cy, 'cm')
            if new_lead and 1.4 <= t <= 1.9:
                sweep(c, (b[0], b[1] + dy, b[2], b[3] + dy), seg(t, 1.4, 1.9))
        return c

    def finale(self, t, title2=''):
        entries = self.entries
        final = sorted(entries, key=lambda e: e.rank)
        c = blank()
        scrim(c, .82 * out_cubic(seg(t, 0, 1)) + .0)
        single = self.layout(final)
        u = in_out_cubic(seg(t, 0, 1))
        h = single[3] if t < .5 else 96
        # two-column target layout
        target, div_boxes = {}, []
        for col, (lo, hi, x0) in enumerate(((0, 12, 40), (12, 23, 1300))):
            y = 216
            for e in final[lo:hi]:
                if e.side == 'loss' and (not div_boxes) and any(x.side == 'win' for x in final) and \
                        final.index(e) > 0 and final[final.index(e) - 1].side == 'win':
                    div_boxes.append((x0, y)); y += self.DIV
                target[e.key] = (x0, y + 1, x0 + 1220, y + 95)
                y += 96
        fade_all = 1 - seg(t, 19, 20)
        ta = out_cubic(seg(t, 1, 2)) * fade_all
        put(c, text_tile(f'FINAL RANKING - vs 15 {self.opp}', 64, P['gold'], True), W / 2, 96, 'cm', ta)
        put(c, text_tile(title2, 30, P['cream'], True), W / 2, 168, 'cm', ta)
        for x0, y in div_boxes:
            dv = rrect(1220, self.DIV - 4, 4, P['wood_mid']).copy()
            label = text_tile(f'BEAT THE {self.opp}   -   FELL TO THE {self.opp}', 24, P['gold_bright'])
            put(dv, label, 610, 19, 'cm')
            put(c, dv, x0, y + 2, alpha=u * fade_all)
        for i, e in enumerate(final):
            r = i + 1
            a = single[1][e.key]
            b = target[e.key]
            box = lerp_box(a, b, u)
            tile = self.row_cached(e.key, h, r)
            if t >= .5 and tile.width != 1220:
                tile = tile.crop((0, 0, 1220, tile.height)) if False else tile.resize((1220, tile.height))
            lit = False
            if 2 <= t < 10:
                idx = 22 - int((t - 2) / .4)
                lit = r - 1 == idx and r >= 4
            scale = 1.0
            if 10 <= t and r <= 3:
                start = 10 + (3 - r) * 1.5
                if t >= start:
                    scale = 1 + .08 * out_cubic(seg(t, start, start + .4))
                    lit = True
            if scale != 1:
                tile = tile.resize((round(tile.width * scale), round(tile.height * scale)), Image.Resampling.BILINEAR)
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            if lit:
                gl, pad = glow(tile, .7)
                put(c, gl, cx, cy, 'cm', fade_all)
            put(c, tile, cx, cy, 'cm', fade_all)
        return c


# ================================================================== Concept A: Banner Row
class BannerRow:
    name = 'A - Banner Row'

    def __init__(self, opponent_plural, title):
        self.opp = opponent_plural.upper()

    def bind(self, entries):
        self.entries = entries
        return self

    # ---- resting strip
    def rest_layout(self, rows):
        n = max(len(rows), 1)
        pitch = min(72, 1296 // n)
        gap = 12 if any(e.side == 'win' for e in rows) and any(e.side == 'loss' for e in rows) else 0
        total = pitch * len(rows) + gap
        x = 1280 - total / 2
        boxes, pole = {}, None
        for e in rows:
            if pole is None and e.side == 'loss' and gap:
                pole = x + gap / 2; x += gap
            boxes[e.key] = (x + 4, 1334, x + pitch - 4, 1334 + pitch - 8)
            x += pitch
        return boxes, pole, pitch

    def draw_rest(self, c, rows, highlight=None, alpha=1.0):
        put_plate(c, (620, 1296, 1940, 1424), .9)
        boxes, pole, pitch = self.rest_layout(rows)
        for i, e in enumerate(rows):
            b = boxes[e.key]
            sz = round(b[2] - b[0])
            ic = framed_icon(str(e.icon), sz - 8, e.side == 'loss', P['win'] if e.side == 'win' else P['loss'])
            put(c, text_tile(str(i + 1), 22, P['cream'], True), (b[0] + b[2]) / 2, 1314, 'cm', alpha)
            put(c, ic, b[0], b[1], alpha=alpha)
            if highlight == e.key:
                put(c, rrect(ic.width + 6, ic.height + 6, 3, None, P['gold_bright'], 3), b[0] - 3, b[1] - 3)
        if pole:
            c.alpha_composite(Image.new('RGBA', (4, 84), P['gold']), (round(pole - 2), 1328))

    def rest(self, n, highlight_prev=True):
        rows = sorted(self.entries[:n], key=lambda e: e.rank)
        c = blank()
        self.draw_rest(c, rows, self.entries[n - 1].key if n and highlight_prev else None)
        return c

    # ---- expanded
    def full_layout(self, rows, gap_for=None):
        n = max(len(rows), 1)
        has_div = any(e.side == 'win' for e in rows) and any(e.side == 'loss' for e in rows)
        dg = 28 if has_div else 0
        pitch = min(240, (2472 - dg) // n)
        total = pitch * len(rows) + dg
        x = 1280 - total / 2
        boxes, pole = {}, None
        for e in rows:
            if pole is None and e.side == 'loss' and dg:
                pole = x + dg / 2; x += dg
            boxes[e.key] = (x + 4, 1112, x + pitch - 4, 1412)
            x += pitch
        return boxes, pole, pitch - 8

    @lru_cache(maxsize=2048)
    def chip(self, key, w, rank, newest=False):
        e = next(x for x in self.entries if x.key == key)
        loss = e.side == 'loss'
        fill = P['parchment_light'] if newest else P['parchment_dim'] if loss else P['parchment']
        im = rrect(w, 300, 8, fill, P['gold_bright'] if newest else P['parchment_edge'], 4 if newest else 2).copy()
        ink = P['ink']
        cx = w / 2
        if w >= 180:
            badge = Image.new('RGBA', (44, 44))
            ImageDraw.Draw(badge).ellipse((0, 0, 43, 43), fill=P['gold'] if rank == 1 else P['wood_dark'], outline=P['gold'], width=2)
            put(badge, text_tile(str(rank), 26, P['wood_dark'] if rank == 1 else P['cream']), 22, 22, 'cm')
            put(im, badge, 8, 8)
            put(im, framed_icon(str(e.icon), 88, loss), cx, 14, 'ct')
            put(im, icon(str(e.emblem), 48), cx + 48, 100, 'cm')
            lines = wrap(e.unit, 24, w - 16)
            for i, ln in enumerate(lines[:2]):
                put(im, ln, cx, 124 + i * 28, 'ct')
            put(im, text_tile(f'{e.count} vs {e.opp}', 20, P['ink_soft']), cx, 184, 'ct')
            put_pips(im, e.record, cx, 218, 22, 8, 'cm')
            put(im, text_tile(margin_text(e.margin), 40, P['win'] if e.margin >= 0 else P['loss']), cx, 260, 'cm')
        else:
            put(im, text_tile(str(rank), 28, P['gold_dark'] if rank == 1 else ink), cx, 22, 'cm')
            isz = min(96, w - 12)
            put(im, framed_icon(str(e.icon), isz - 8, loss), cx, 44, 'ct')
            put(im, icon(str(e.emblem), 40), cx + isz / 2 - 6, 44 + isz - 6, 'cm')
            lines = wrap(e.unit, 18, w - 8, floor=15)
            for i, ln in enumerate(lines[:3]):
                put(im, ln, cx, 44 + isz + 10 + i * 20, 'ct')
            put_pips(im, e.record, cx, 230, 18, 6, 'cm')
            put(im, text_tile(margin_text(e.margin), 30, P['win'] if e.margin >= 0 else P['loss']), cx, 266, 'cm')
        ImageDraw.Draw(im).rectangle((2, 292, w - 3, 297), fill=P['loss'] if loss else P['win'])
        return im

    def hero(self, e, stamp_u):
        im = rrect(560, 300, 10, P['parchment'], P['gold'], 3).copy()
        put(im, framed_icon(str(e.icon), 152), 24, 24)
        put(im, icon(str(e.emblem), 96), 24 + 160 - 24, 24 + 160 - 24 + 24, 'cm')
        put(im, text_fit(e.unit, 44, P['ink'], 330, 28), 208, 28)
        put(im, text_tile(e.civ, 28, P['ink_soft']), 208, 84)
        put(im, text_tile(f'{e.count} vs {e.opp}', 28, P['ink']), 208, 124)
        put_pips(im, e.record, 208, 189, 34, 12, 'lm')
        if stamp_u > 0:
            win = e.side == 'win'
            st = text_tile(('VICTORY ' if win else 'DEFEAT ') + margin_text(e.margin), 56, P['win'] if win else P['loss'])
            s = lerp(1.8, 1.0, out_cubic(stamp_u))
            st2 = st.resize((round(st.width * s), round(st.height * s)), Image.Resampling.BILINEAR)
            put(im, st2, 536 - st.width / 2, 250, 'cm', out_cubic(stamp_u))
        return im

    def beat(self, n, t):
        entries = self.entries
        prev = sorted(entries[:n], key=lambda e: e.rank)
        new = entries[n]
        now = running(entries, n)
        ranks_new = {e.key: i + 1 for i, e in enumerate(now)}
        ranks_old = {e.key: i + 1 for i, e in enumerate(prev)}
        c = blank()
        expand = out_cubic(seg(t, 0, .4)) - in_out_cubic(seg(t, 3.6, 4.2))
        if expand <= 0.001:
            self.draw_rest(c, now if t > 2 else prev, new.key if t > 2 else None)
            return c
        sc = .35 * (out_back(seg(t, .3, .5)) if t < 1.5 else 1 - seg(t, 1.5, 2.1))
        scrim(c, max(0, min(.35, sc)), (0, 0, W, 1068))
        rest_box, full_box = (620, 1296, 1940, 1424), (24, 1068, 2536, 1424)
        pb = lerp_box(rest_box, full_box, expand)
        put_plate(c, [round(v) for v in pb], lerp(.9, .96, expand))
        ca = out_cubic(seg(t, .15, .4)) * min(1, expand * 1.5)
        put(c, text_tile(f'RANKING vs 15 {self.opp}', 26, P['cream'], True), 44, 1080, 'lt', ca * (expand > .9))
        put(c, text_tile(f'{n + 1 if t > 2.1 else n} of {len(entries)}', 26, P['gold'], True), 2516, 1080, 'rt',
            ca * (expand > .9))
        FA, poleA, wA = self.full_layout(prev)
        FB, poleB, wB = self.full_layout(now)
        u = in_out_cubic(seg(t, .9, 1.4))
        rb, _, _ = self.rest_layout(prev)
        for e in prev:
            full = lerp_box(FA[e.key], FB[e.key], u)
            box = lerp_box(rb[e.key], full, expand)
            w = round(wA if u < .5 else wB)
            rk = ranks_old[e.key] if t < 2.1 else ranks_new[e.key]
            tile = self.chip(e.key, w, rk)
            tw, th = max(1, round(box[2] - box[0])), max(1, round(box[3] - box[1]))
            if (tw, th) != tile.size:
                tile = tile.resize((tw, th), Image.Resampling.BILINEAR)
            put(c, tile, box[0], box[1], alpha=max(.3, ca))
        pole = lerp(poleA or poleB or 0, poleB or poleA or 0, u)
        if pole and expand > .9:
            c.alpha_composite(Image.new('RGBA', (6, 316), P['gold']), (round(pole - 3), 1104))
            put(c, text_tile('WON', 22, P['win_light'], True), pole - 10, 1096, 'rb', ca)
            put(c, text_tile('LOST', 22, P['loss_light'], True), pole + 10, 1096, 'lb', ca)
        # hero card -> chip
        if t >= .3:
            hero = self.hero(new, seg(t, .7, .85))
            pop = out_back(seg(t, .3, .5))
            fly = in_out_cubic(seg(t, 1.5, 2.1))
            target = FB[new.key]
            hb = (1280 - 280, 620 - 150, 1280 + 280, 620 + 150)
            box = lerp_box(hb, target, fly)
            if fly < .6:
                tile = hero
            else:
                tile = self.chip(new.key, round(wB), ranks_new[new.key], newest=True)
            tw, th = max(1, round((box[2] - box[0]) * (pop if fly == 0 else 1))), max(1, round((box[3] - box[1]) * (pop if fly == 0 else 1)))
            tile = tile.resize((tw, th), Image.Resampling.BILINEAR)
            land = 6 * pulse(seg(t, 2.1, 2.25))
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2 + land
            g = .9 * pulse(seg(t, 2.1, 2.5)) + .9 * pulse(seg(t, 2.5, 2.9))
            if g > .02:
                gl, _ = glow(tile, g)
                put(c, gl, cx, cy, 'cm')
            put(c, tile, cx, cy, 'cm', min(1, pop * 1.2) if fly == 0 else 1)
            if new.rank == min(e.rank for e in now) and len(now) > 1 and 2.1 <= t <= 3.4:
                a = min(seg(t, 2.1, 2.3), 1 - seg(t, 3.2, 3.4))
                put(c, text_tile('NEW LEADER', 30, P['gold_bright'], True), (target[0] + target[2]) / 2, 1030, 'cm', a)
                sweep(c, [round(v) for v in full_box], seg(t, 2.1, 2.7), 240, .5)
        return c

    def finale(self, t, title2=''):
        final = sorted(self.entries, key=lambda e: e.rank)
        c = blank()
        fade = 1 - seg(t, 17, 18)
        scrim(c, .8 * out_cubic(seg(t, 0, 1)))
        put_plate(c, (40, 200, 2520, 1320), .96)
        put(c, text_tile(f'FINAL RANKING - vs 15 {self.opp}', 56, P['gold'], True), W / 2, 216, 'ct', fade)
        put(c, text_tile(title2, 28, P['cream'], True), W / 2, 296, 'ct', fade)
        rows = (final[:12], final[12:])
        for ri, row in enumerate(rows):
            total = 200 * len(row)
            x = 1280 - total / 2
            y = 360 if ri == 0 else 820
            for e in row:
                r = final.index(e) + 1
                tile = self.chip(e.key, 192, r)
                s = 1.0
                lit = False
                rc = 1.0 + (23 - r) * .35
                if rc <= t < rc + .35:
                    s = 1 + .12 * pulse(seg(t, rc, rc + .35)); lit = True
                if r <= 3 and t >= 9.05:
                    s = 1 + .15 * out_cubic(seg(t, 9.05, 9.6)); lit = True
                if s != 1:
                    tile = tile.resize((round(192 * s), round(300 * s)), Image.Resampling.BILINEAR)
                cx, cy = x + 100, y + 150 - (24 if r <= 3 and t >= 9.05 else 0)
                if lit:
                    gl, _ = glow(tile, .6)
                    put(c, gl, cx, cy, 'cm', fade)
                put(c, tile, cx, cy, 'cm', fade)
                if e.side == 'win' and r < len(final) and final[r].side == 'loss' and final[r] in row:
                    c.alpha_composite(Image.new('RGBA', (6, 316), P['gold']), (round(x + 200 - 1), y - 8))
                x += 200
        return c


def wrap(text, size, max_w, floor=20):
    words = text.split()
    for sz in range(size, floor - 1, -1):
        lines, cur = [], ''
        for w in words:
            trial = (cur + ' ' + w).strip()
            if text_tile(trial, sz, P['ink']).width <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur); cur = w
        lines.append(cur)
        if len(lines) <= (2 if size >= 24 else 3) and all(text_tile(l, sz, P['ink']).width <= max_w for l in lines):
            return [text_tile(l, sz, P['ink']) for l in lines]
    return [text_fit(l, floor, P['ink'], max_w, floor) for l in lines]


# ================================================================== Concept C: The Battle Line
class BattleLine:
    name = 'C - The Battle Line'
    show_pips = True
    ZERO, SCALE = 836, 4.8

    def __init__(self, opponent_plural, title):
        self.opp = opponent_plural.upper()

    def bind(self, entries):
        self.entries = entries
        return self

    def cols(self, n):
        p = min(160, 1920 // max(n, 1))
        return p, round(.62 * p), min(96, p - 12)

    def xs(self, n):
        p = self.cols(n)[0]
        return [1280 - p * n / 2 + p * (i + .5) for i in range(n)]

    def column(self, c, e, cx, rank, p, grow=1.0, number=None, pips=3, name_a=1.0, alpha=1.0, scale=1.0, lit=0.0):
        _, bw, isz = self.cols(1920 // p if p < 160 else 1)
        bw, isz = round(.62 * p), min(96, p - 12)
        up = e.margin >= 0
        length = max(6, self.SCALE * abs(e.margin) * grow)
        z = self.ZERO
        bar = Image.new('RGBA', (bw, round(length)))
        bd = ImageDraw.Draw(bar)
        c0, c1 = (P['win'], P['win_light']) if up else (P['loss'], P['loss_light'])
        for y in range(bar.height):
            f = y / max(1, bar.height - 1)
            f = 1 - f if up else f
            bd.line((0, y, bw, y), fill=tuple(round(lerp(a, b, f)) for a, b in zip(c0[:3], c1[:3])) + (255,))
        bd.rectangle((0, 0, bw - 1, bar.height - 1), outline=P['gold_dark'], width=2)
        put(c, bar, cx, z, 'cb' if up else 'ct', alpha)
        tip = z - length if up else z + length
        ic = framed_icon(str(e.icon), max(8, round((isz - 8) * scale)), not up)
        if lit > .02:
            gl, _ = glow(ic, lit)
            put(c, gl, cx, tip - 8 - ic.height / 2 if up else tip + 8 + ic.height / 2, 'cm', alpha)
        if up:
            put(c, ic, cx, tip - 8, 'cb', alpha)
            yy = tip - 8 - ic.height - 6
            num = text_tile(margin_text(e.margin if number is None else number), 34 if p >= 100 else 30, P['win_light'], True)
            put(c, num, cx, yy, 'cb', alpha)
            if pips and self.show_pips:
                put_pips(c, e.record, cx, yy - num.height - 4 - 8, 16 if p >= 100 else 13, 5 if p >= 100 else 4, 'cm',
                         shown=pips)
        else:
            put(c, ic, cx, tip + 8, 'ct', alpha)
            yy = tip + 8 + ic.height + 6
            num = text_tile(margin_text(e.margin if number is None else number), 34 if p >= 100 else 30, P['loss_light'], True)
            put(c, num, cx, yy, 'ct', alpha)
            if pips and self.show_pips:
                put_pips(c, e.record, cx, yy + num.height + 4 + 8, 16 if p >= 100 else 13, 5 if p >= 100 else 4, 'cm',
                         shown=pips)
        # emblem on the line
        esz = 48 if p >= 100 else 40
        disc = Image.new('RGBA', (esz + 6, esz + 6))
        ImageDraw.Draw(disc).ellipse((0, 0, esz + 5, esz + 5), fill=P['wood_dark'], outline=P['gold'], width=2)
        put(disc, icon(str(e.emblem), esz - 8), (esz + 6) / 2, (esz + 6) / 2, 'cm')
        put(c, disc, cx, z, 'cm', alpha)
        # rotated name in the opposite half
        if name_a > 0:
            nm = text_fit(e.unit, 26, P['cream'], 300, 22, True).rotate(90, expand=True)
            if up:
                put(c, nm, cx, z + 34, 'ct', alpha * name_a)
            else:
                put(c, nm, cx, z - 34, 'cb', alpha * name_a)
        put(c, text_tile(str(rank), 30, P['gold_bright'] if rank == 1 else P['cream'], True), cx, 1372, 'cm', alpha)

    def frame_base(self, c, n_text, alpha, dy=0, title=None):
        put_plate(c, (280, 60 + dy, 2280, 1410 + dy), .55)
        for pct in (75, 50, 25, -25, -50):
            y = self.ZERO - pct * self.SCALE + dy
            c.alpha_composite(Image.new('RGBA', (1920, 1), P['cream'][:3] + (int(30 * alpha),)), (320, round(y)))
            put(c, text_tile(f'{pct:+d}', 22, P['cream']), 300, y, 'rm', .6 * alpha)
        line = Image.new('RGBA', (1960, 6), P['gold'])
        gl, pad = glow(line, .5 * alpha, 8)
        put(c, gl, 1280, self.ZERO + dy, 'cm')
        put(c, line, 1280, self.ZERO + dy, 'cm', alpha)
        put(c, text_tile(title or f'RANKING vs 15 {self.opp}', 52, P['gold'], True), W / 2, 96 + dy, 'cm', alpha)
        if n_text:
            put(c, text_tile(n_text, 30, P['cream'], True), 2240, 110 + dy, 'rm', alpha)

    def rest(self, n):
        return None

    def beat(self, n, t):
        entries = self.entries
        prev = sorted(entries[:n], key=lambda e: e.rank)
        new = entries[n]
        now = running(entries, n)
        c = blank()
        a_in = out_cubic(seg(t, 0, .5))
        a_out = in_cubic(seg(t, 3.7, 4.3))
        alpha = a_in * (1 - a_out)
        scrim(c, .82 * alpha)
        dy = 40 * (1 - a_in) + 40 * a_out
        self.frame_base(c, f'{n + 1 if t >= 2.4 else n} of {len(entries)}', alpha, dy)
        n0, n1 = len(prev), len(now)
        u = in_out_cubic(seg(t, .5, .9))
        x_prev, x_stage = self.xs(max(n0, 1)), self.xs(n1)
        p = round(lerp(self.cols(max(n0, 1))[0], self.cols(n1)[0], u))
        final_slot = now.index(new)
        # mover x: staged at last slot, slides to final slot 2.4-3.1
        mv = in_out_cubic(seg(t, 2.4, 3.1))
        mover_x = lerp(x_stage[-1], x_stage[final_slot], mv)
        for i, e in enumerate(prev):
            staged = x_stage[i]                       # before the overtake, previous entries keep order
            final_x = x_stage[now.index(e)]
            x = lerp(x_prev[i] if n0 else staged, staged, u)
            # passed columns step right while the mover crosses them
            if final_x != staged and t >= 2.4:
                s = min(1, max(0, (staged + p * .5 - mover_x) / p))
                x = lerp(staged, final_x, out_cubic(s))
            rk = i + 1 if t < 3.1 else now.index(e) + 1
            self.column(c, e, x, rk, p, alpha=alpha)
        if t >= .8:
            drop = out_back(seg(t, .8, 1.2))
            grow = out_cubic(seg(t, 1.2, 2.1)) if t >= 1.2 else 0
            pipn = sum(t >= a for a in (2.1, 2.2, 2.3))
            lift = (1.06 if 2.4 <= t < 3.1 else 1 + .06 * (1 - seg(t, 3.1, 3.4))) if t >= 2.4 else 1
            lit = .8 if 2.4 <= t < 3.1 else .8 * pulse(seg(t, 3.1, 3.6))
            self.column(c, new, mover_x, final_slot + 1 if t >= 3.1 else len(now), p, grow=grow,
                        number=new.margin * grow, pips=pipn, name_a=seg(t, 2.1, 2.4), alpha=alpha * min(1, drop * 1.5),
                        scale=lift, lit=lit)
            if new.rank == min(e.rank for e in now) and n1 > 1 and 3.1 <= t <= 3.7:
                k = seg(t, 3.1, 3.6)
                ring = Image.new('RGBA', (460, 460))
                r = lerp(40, 220, k)
                ImageDraw.Draw(ring).ellipse((230 - r, 230 - r, 230 + r, 230 + r), outline=P['gold_bright'][:3] + (int(230 * (1 - k)),), width=6)
                tip = self.ZERO - self.SCALE * abs(new.margin)
                put(c, ring, mover_x, tip - 60, 'cm')
                put(c, text_tile('NEW LEADER', 36, P['gold_bright'], True), mover_x, 190, 'cm', alpha)
        return c

    def finale(self, t, title2=''):
        final = sorted(self.entries, key=lambda e: e.rank)
        c = blank()
        fade = 1 - seg(t, 18, 19)
        scrim(c, .82 * out_cubic(seg(t, 0, 1)))
        self.frame_base(c, '', fade * out_cubic(seg(t, 0, 1)), title=f'FINAL RANKING - vs 15 {self.opp}')
        xs = self.xs(len(final))
        p = self.cols(len(final))[0]
        for i, e in enumerate(final):
            start = 1 + (len(final) - 1 - i) * .3
            g = out_cubic(seg(t, start, start + .6))
            lit = .6 if i < 3 and t >= 8.5 else 0
            self.column(c, e, xs[i], i + 1, p, grow=g, number=e.margin * g, pips=3 if g >= 1 else 0,
                        name_a=g, alpha=fade * (1 if t >= start else .0), scale=1.15 if lit else 1, lit=lit)
        wins = sum(e.side == 'win' for e in final)
        if t >= 11.5 and wins:
            a = out_cubic(seg(t, 11.5, 12)) * fade
            put(c, text_tile(f'{wins} of {len(final)} beat the {self.opp.title()}', 30, P['gold_bright'], True),
                (xs[0] + xs[wins - 1]) / 2, 170, 'cm', a)
        return c


class LadderThenLine:
    """Chosen mix: B's ladder for each battle's result, C's Battle Line for the finale."""
    name = 'D - Ladder then Battle Line'

    def __init__(self, opponent_plural, title):
        self.ladder = ScrollOfHonour(opponent_plural, title)
        self.line = BattleLine(opponent_plural, title)
        # one shown run per unit: the number is that run's HP left, no 3-run pips
        self.ladder.show_pips = self.line.show_pips = False

    def bind(self, entries):
        self.ladder.bind(entries)
        self.line.bind(entries)
        self.entries = entries
        return self

    def rest(self, n):
        return None

    def beat(self, n, t):
        return self.ladder.beat(n, t)

    def finale(self, t, title2=''):
        return self.line.finale(t, title2)


CONCEPTS = {'A': BannerRow, 'B': ScrollOfHonour, 'C': BattleLine, 'D': LadderThenLine}


def card_title(e, line2, t, length):
    """Animated matchup title for the card that opens each battle (transparent frame)."""
    c = blank()
    a = out_cubic(seg(t, .25, .8)) * (1 - in_cubic(seg(t, length - .35, length + .1)))
    if a <= .01:
        return c
    rise = 36 * (1 - out_cubic(seg(t, .25, .9)))
    put(c, glow(icon(str(e.emblem), 150), .5)[0], W / 2, 430 + rise, 'cm', a * .8)
    put(c, icon(str(e.emblem), 150), W / 2, 430 + rise, 'cm', a)
    put(c, text_fit(e.unit, 112, P['gold'], 2200, 60, True), W / 2, 620 + rise, 'cm', a)
    u = out_cubic(seg(t, .45, 1.0))
    rule = Image.new('RGBA', (max(2, round(900 * u)), 4), P['gold_dark'])
    put(c, rule, W / 2, 712 + rise, 'cm', a)
    put(c, text_tile(e.civ, 54, P['cream'], True), W / 2, 780 + rise, 'cm', a * u)
    put(c, text_tile(line2, 44, P['cream'], True), W / 2, 856 + rise, 'cm', a * u * .85)
    return c
