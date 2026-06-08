"""SLD v4 decoder (Age of Empires II: DE sprite format) -> transparent PNG.

AoE2:DE stores unit/building sprites as `.sld` files (introduced ~build 66692),
which use lossy texture compression (DXT1/BC1 for color, DXT4/BC4 for masks)
instead of indexed palettes. No maintained headless decoder was installable
here (openage needs a Cython/C++/Qt build; the community SLD Extractors are
minified browser apps), so this implements the format directly from the
openage reference spec (doc/media/sld-files.md).

What it decodes: the MAIN graphics layer (BC1), which carries the unit's RGB.
Transparency comes from the command-array (skipped 4x4 blocks) + BC1 1-bit
alpha. Shadow / "???" / damage / player-color layers are skipped (their sizes
are used only to walk to the next layer/frame), so player-color areas appear in
their baked-in default tint — fine for portraits/reference. Per-direction layout:
frames are grouped by angle (frame_count per angle, angle_count angles); the
first frame of angle A is index A*frame_count.

Find a unit's .sld + frame layout from the dat via genieutils (conda `python`):
    u = dat.civs[0].units[UNIT_ID]
    gid = u.standing_graphic[0]            # or dead_fish.walking_graphic, type_50.attack_graphic, dying_graphic
    dat.graphics[gid].file_name            # -> "<name>" => "<name>.sld"
    dat.graphics[gid].frame_count, .angle_count

Usage:
    python sld_decode.py <in.sld> <out_dir> [--frame N | --all | --max M]
                         [--angle-stride S] [--crop] [--margin N]
  --frame N        decode a single frame (default: frame 0)
  --all            decode every frame
  --max M          decode the first M frames
  --angle-stride S decode the first frame of each angle (S = frame_count), i.e. one image per facing
  --crop           tight-crop each output to the non-transparent bounding box
  --margin N       transparent margin (px) added around a --crop result (default 0)

Prefer the `_x2.sld` variant for double-resolution output.
"""
import os
import sys
import struct
import math
import argparse
from PIL import Image

# --- BC1 / DXT1 -------------------------------------------------------------

def _rgb565(c):
    r = (c >> 11) & 0x1F
    g = (c >> 5) & 0x3F
    b = c & 0x1F
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 1), (b << 3) | (b >> 2))

def _decode_bc1_block(b):
    """8-byte BC1 block -> list of 16 RGBA tuples (row-major 4x4)."""
    c0, c1, idx = struct.unpack_from('<HHI', b, 0)
    r0, g0, b0 = _rgb565(c0)
    r1, g1, b1 = _rgb565(c1)
    pal = [(r0, g0, b0, 255), (r1, g1, b1, 255)]
    if c0 > c1:
        pal.append(((2*r0+r1)//3, (2*g0+g1)//3, (2*b0+b1)//3, 255))
        pal.append(((r0+2*r1)//3, (g0+2*g1)//3, (b0+2*b1)//3, 255))
    else:
        pal.append(((r0+r1)//2, (g0+g1)//2, (b0+b1)//2, 255))
        pal.append((0, 0, 0, 0))  # 1-bit alpha
    return [pal[(idx >> (2 * i)) & 0x3] for i in range(16)]

# --- SLD container ----------------------------------------------------------

# layer presence bits (LSB); validated by openage example 0x17 = main+shadow+???+playercolor
L_MAIN, L_SHADOW, L_UNK, L_DAMAGE, L_PLAYER = 0x01, 0x02, 0x04, 0x08, 0x10
LAYER_ORDER = [L_MAIN, L_SHADOW, L_UNK, L_DAMAGE, L_PLAYER]

def _pad4(n):
    return n + ((4 - n % 4) % 4)

def parse(data):
    """Return (header_dict, [frame_dict, ...]). Each frame_dict records the
    canvas size, hotspot, type bitfield, and (offset, content_length) of each
    present layer."""
    sig, ver, num_frames, _u1, frame_start = struct.unpack_from('<4sHHHH', data, 0)
    if sig != b'SLDX':
        raise ValueError(f'not an SLD file (signature {sig!r})')
    # The uint16 at 0x0A is the header length / offset where frame data begins.
    # It is usually 16 but some files use 14 — hardcoding 16 desyncs those.
    off = frame_start if 12 <= frame_start <= 64 else 16
    frames = []
    for _ in range(num_frames):
        cw, ch, hx, hy, ftype, _fu1, fidx = struct.unpack_from('<HHhhBBH', data, off)
        off += 12
        layers = {}
        for bit in LAYER_ORDER:
            if not (ftype & bit):
                continue
            content_len = struct.unpack_from('<I', data, off)[0]
            layers[bit] = (off, content_len)
            off += _pad4(content_len)
        frames.append({'i': fidx, 'w': cw, 'h': ch, 'hx': hx, 'hy': hy,
                       'type': ftype, 'layers': layers})
    return {'version': ver, 'num_frames': num_frames}, frames

# --- BC4 / DXT4 (single-channel mask: shadow, player-color, damage) ---------

def _decode_bc4_block(b):
    """8-byte BC4 block -> list of 16 intensity values (0-255), row-major 4x4."""
    a0, a1 = b[0], b[1]
    pal = [a0, a1]
    if a0 > a1:
        for k in range(1, 7):
            pal.append(((7 - k) * a0 + k * a1) // 7)
    else:
        for k in range(1, 5):
            pal.append(((5 - k) * a0 + k * a1) // 5)
        pal += [0, 255]
    g1 = b[2] | (b[3] << 8) | (b[4] << 16)
    g2 = b[5] | (b[6] << 8) | (b[7] << 16)
    out = [pal[(g1 >> (3 * i)) & 7] for i in range(8)]
    out += [pal[(g2 >> (3 * i)) & 7] for i in range(8)]
    return out

# Player-color ramps: (shadow_rgb, highlight_rgb), lerped by mask intensity/255.
PLAYER_COLORS = {
    'red':    ((40, 0, 0),   (255, 70, 70)),
    'blue':   ((0, 0, 48),   (80, 110, 255)),
    'green':  ((0, 36, 0),   (90, 230, 90)),
    'yellow': ((48, 40, 0),  (255, 235, 90)),
    'orange': ((48, 22, 0),  (255, 150, 50)),
    'cyan':   ((0, 40, 44),  (90, 235, 235)),
    'purple': ((36, 0, 44),  (190, 90, 235)),
    'gray':   ((30, 30, 30), (225, 225, 225)),
}

def _main_geometry(data, frame):
    loff, _ = frame['layers'][L_MAIN]
    x1, y1, x2, y2, flag1, _ = struct.unpack_from('<HHHHBB', data, loff + 4)
    return x1, y1, x2 - x1, y2 - y1, flag1

def _read_commands(data, p):
    ncmd = struct.unpack_from('<H', data, p)[0]
    p += 2
    cmds = [struct.unpack_from('<BB', data, p + 2 * i) for i in range(ncmd)]
    return cmds, p + 2 * ncmd

def _decode_player_mask(data, frame, w, h):
    """Decode the player-color BC4 mask into a w x h grid of 0-255 intensities
    (0 where not present). Uses the MAIN layer geometry. Returns None if absent."""
    if L_PLAYER not in frame['layers']:
        return None
    loff, _ = frame['layers'][L_PLAYER]
    p = loff + 4 + 2  # content_length + 2-byte mask header
    cmds, p = _read_commands(data, p)
    bpr = math.ceil(w / 4)
    mask = [[0] * w for _ in range(h)]
    bidx = 0
    for skip, draw in cmds:
        bidx += skip
        for _ in range(draw):
            blk = _decode_bc4_block(data[p:p+8])
            p += 8
            bx, by = (bidx % bpr) * 4, (bidx // bpr) * 4
            for i, v in enumerate(blk):
                xx, yy = bx + (i % 4), by + (i // 4)
                if xx < w and yy < h:
                    mask[yy][xx] = v
            bidx += 1
    return mask

def decode_main(data, frame, player_color=None):
    """Decode a frame's MAIN graphics layer onto its full canvas. If
    `player_color` (a key of PLAYER_COLORS) is given, the player-color mask
    (BC4) is composited so team-colored regions are tinted accordingly.
    Returns an RGBA Image, or None if the frame has no main layer / reuses data."""
    if L_MAIN not in frame['layers']:
        return None
    x1, y1, w, h, flag1 = _main_geometry(data, frame)
    if flag1 & 0x01:  # reuse previous frame's pixel data
        return None
    if w <= 0 or h <= 0:
        return None
    loff, _clen = frame['layers'][L_MAIN]
    cmds, p = _read_commands(data, loff + 4 + 10)  # skip content_length + 10-byte header
    bpr = math.ceil(w / 4)
    layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    px = layer.load()
    bidx = 0
    for skip, draw in cmds:
        bidx += skip
        for _ in range(draw):
            blk = _decode_bc1_block(data[p:p+8])
            p += 8
            bx, by = (bidx % bpr) * 4, (bidx // bpr) * 4
            for i, col in enumerate(blk):
                xx, yy = bx + (i % 4), by + (i // 4)
                if xx < w and yy < h:
                    px[xx, yy] = col
            bidx += 1

    if player_color:
        mask = _decode_player_mask(data, frame, w, h)
        if mask:
            (sr, sg, sb), (hr, hg, hb) = PLAYER_COLORS[player_color]
            for yy in range(h):
                row = mask[yy]
                for xx in range(w):
                    m = row[xx]
                    if m <= 0:
                        continue
                    r, g, b, a = px[xx, yy]
                    if a == 0:
                        continue
                    t = m / 255.0
                    px[xx, yy] = (int(sr + (hr - sr) * t),
                                  int(sg + (hg - sg) * t),
                                  int(sb + (hb - sb) * t), a)

    canvas = Image.new('RGBA', (frame['w'], frame['h']), (0, 0, 0, 0))
    canvas.alpha_composite(layer, (x1, y1))
    return canvas

def _finish(img, crop, margin):
    if not crop:
        return img
    bbox = img.getbbox()
    if not bbox:
        return img
    c = img.crop(bbox)
    if margin <= 0:
        return c
    out = Image.new('RGBA', (c.width + 2 * margin, c.height + 2 * margin), (0, 0, 0, 0))
    out.alpha_composite(c, (margin, margin))
    return out

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('sld')
    ap.add_argument('outdir')
    ap.add_argument('--frame', type=int, default=None)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--max', type=int, default=0)
    ap.add_argument('--angle-stride', type=int, default=0,
                    help='decode first frame of each angle (stride = frame_count)')
    ap.add_argument('--crop', action='store_true')
    ap.add_argument('--margin', type=int, default=0)
    ap.add_argument('--player-color', choices=sorted(PLAYER_COLORS), default=None,
                    help='tint the player-color mask regions with this team color')
    a = ap.parse_args(argv)

    data = open(a.sld, 'rb').read()
    hdr, frames = parse(data)
    print(f"version={hdr['version']} num_frames={hdr['num_frames']}")
    os.makedirs(a.outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.sld))[0]

    if a.frame is not None:
        sel = [a.frame]
    elif a.angle_stride:
        sel = list(range(0, len(frames), a.angle_stride))
    elif a.all:
        sel = range(len(frames))
    elif a.max:
        sel = range(min(a.max, len(frames)))
    else:
        sel = [0]

    n = 0
    for fi in sel:
        img = decode_main(data, frames[fi], player_color=a.player_color)
        if img is None:
            continue
        img = _finish(img, a.crop, a.margin)
        img.save(os.path.join(a.outdir, f"{base}_f{fi:03d}.png"))
        n += 1
    print(f"wrote {n} png(s) to {a.outdir}")

if __name__ == '__main__':
    main()
