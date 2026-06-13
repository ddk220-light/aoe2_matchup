"""Build the per-unit asset folder under graphics/units/<slug>/.

For each unit in UNITS this creates:
  graphics/units/<slug>/
    icon.png                          — 256px game UI icon (from the .dat icon_id, DDS atlas)
    <slug>_idle_dir06.png             — copy of the first dir06 idle frame (Nano Banana pose ref)
    idle/   <slug>_idle_dir06_fNN.png — EVERY frame of the dir06 idle animation
    attack/ <slug>_attack_dir06_fNN.png
    death/  <slug>_death_dir06_fNN.png
    (final approved AI renders are dropped into <slug>/ later)

We fix the facing to dir06 and pull the FULL animation sequence (every frame) for that
direction, for each of idle / attack / death. Frames are transparent, tight-cropped decodes
of the elite _x2 SLDs. The game icon comes from the AoE2:DE unit-icon DDS atlas by icon_id.

Player color (player 2 = RED) is applied to both:
- Icons: the DDS alpha channel is NOT transparency — it is the player-color mask the game
  shader uses (low alpha = team color region). Verified by reconstructing the wiki's blue
  icon from the grey DDS to ~2.8/255 mean error. Blend:
      out = base_rgb*(1-m) + Luminance*TINT*m,   m = (255-alpha)/255
- Sprites: the SLD player-color BC4 mask layer, multiplied into the base (keeps the baked
  cloth shading; the old PLAYER_COLORS lerp in sld_decode is too bright/neon).

Usage
-----
  C:/Users/ddk22/miniconda3/python.exe graphics/units/build_unit_assets.py
  C:/Users/ddk22/miniconda3/python.exe graphics/units/build_unit_assets.py --slugs kona
"""
import os, sys, argparse, shutil, struct, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import sld_decode as D
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW  = os.path.join(ROOT, 'graphics', 'game_raw_files')
GAME = 'D:/SteamLibrary/steamapps/common/AoE2DE'
DDS_DIR = os.path.join(GAME, 'widgetui', 'textures', 'ingame', 'units')   # NNN_50730.DDS
UNITS_DIR = os.path.join(ROOT, 'graphics', 'units')
IDLE_DIR_ANGLE = 6

# Player 2 (red). Icon tint scales luminance; sprite tint multiplies the baked base color.
ICON_TINT   = (1.35, 0.27, 0.23)
SPRITE_TINT = (0.86, 0.18, 0.16)
# Player 1 (blue) — mirror of the red multiply tint (dominant blue channel).
SPRITE_TINT_BLUE = (0.16, 0.22, 0.90)

# slug -> (sld_basename_stub, icon_id)
#   sld_basename_stub: the part before "_<anim>A_x2.sld" (elite)
# These are the ELITE reference sets — the folder slug carries the elite_ prefix so
# the non-elite base unit can own the plain slug (its icon.png lives there).
UNITS = {
    'elite_blackwood_archer': ('u_arc_blackwood_archer_elite', 550),
    'elite_guecha_warrior':   ('u_arc_guecha_elite',           544),
    'elite_kona':             ('u_cav_kona_elite',             546),
}
ANIMS = ('idle', 'attack', 'death')   # SLD anim token is idleA / attackA / deathA

# --- UNIT_NAMES corrections (graphics roster only; the stats-pipeline source in
# aoe2x/extract/extract_units.py is intentionally left untouched). Two dat ids are
# mislabeled in UNIT_NAMES, verified against the .dat:
#   id 1660 = DSERJEANT (Donjon Serjeant), wrongly named "Houfnice"
#   id 1709 = HOUFNICE,                    wrongly named "Ratha"
# So Houfnice's icon/sprite must come from id 1709, and there is no generic "Ratha"
# unit (the real ones are "Ratha (Melee)"/"Ratha (Ranged)").
NAME_FORCE_ID = {'Houfnice': 1709}    # display name -> dat id to use for graphics
NAME_DROP = {'Ratha'}                 # bogus name; drop from the graphics roster


def decode_red(data, frame, tint=SPRITE_TINT):
    """Decode a frame and multiply `tint` into its player-color mask regions
    (default = player-2 red; pass SPRITE_TINT_BLUE for player-1 blue)."""
    im = D.decode_main(data, frame, player_color=None)
    if im is None:
        return None
    x1, y1, w, h, _ = D._main_geometry(data, frame)
    mask = D._decode_player_mask(data, frame, w, h)
    if mask:
        px = im.load()
        tr, tg, tb = tint
        for yy in range(h):
            row = mask[yy]
            for xx in range(w):
                if row[xx] > 15:
                    X, Y = x1 + xx, y1 + yy
                    if 0 <= X < im.width and 0 <= Y < im.height:
                        r, g, b, al = px[X, Y]
                        if al > 0:
                            px[X, Y] = (int(r * tr), int(g * tg), int(b * tb), al)
    return im


def decode_shadow(data, frame):
    """Decode the SHADOW layer (BC4, own bbox) -> ((x, y), intensity ndarray) or None."""
    if D.L_SHADOW not in frame['layers']:
        return None
    loff, _ = frame['layers'][D.L_SHADOW]
    x1, y1, x2, y2, _f1, _f2 = struct.unpack_from('<HHHHBB', data, loff + 4)
    w, h = x2 - x1, y2 - y1
    p = loff + 4 + 10
    cmds, p = D._read_commands(data, p)
    bpr = math.ceil(w / 4)
    g = np.zeros((h, w), dtype=np.uint8)
    bidx = 0
    for skip, draw in cmds:
        bidx += skip
        for _ in range(draw):
            blk = D._decode_bc4_block(data[p:p + 8])
            p += 8
            bx, by = (bidx % bpr) * 4, (bidx // bpr) * 4
            for i, v in enumerate(blk):
                xx, yy = bx + (i % 4), by + (i // 4)
                if xx < w and yy < h:
                    g[yy, xx] = v
            bidx += 1
    return (x1, y1), g


def enhanced_pose_ref(stub, dir_angle=IDLE_DIR_ANGLE, shadow_opacity=0.55):
    """Native-res red pose ref with the soft shadow layer composited underneath.

    Returns a tight-cropped RGBA image, or None if the idle SLD is missing.
    """
    sld = find_sld(stub, 'idle')
    if not sld:
        return None
    data = open(sld, 'rb').read()
    _hdr, frames = D.parse(data)
    fc = len(frames) // 16
    fr = frames[dir_angle * fc]
    im = decode_red(data, fr)
    if im is None:
        return None
    canvas = Image.new('RGBA', (fr['w'], fr['h']), (0, 0, 0, 0))
    sh = decode_shadow(data, fr)
    if sh:
        (sx, sy), g = sh
        layer = np.zeros((g.shape[0], g.shape[1], 4), dtype=np.uint8)
        layer[..., 3] = (g * shadow_opacity).astype(np.uint8)
        canvas.alpha_composite(Image.fromarray(layer), (sx, sy))
    canvas.alpha_composite(im, (0, 0))
    return canvas.crop(canvas.getbbox())


def animation_frames(sld_path, dir_angle=IDLE_DIR_ANGLE):
    """Decode EVERY frame of one direction's animation, with red player color applied.

    Frames are grouped by angle: angle A occupies frames[A*fc : (A+1)*fc], where
    fc = frame_count per angle. Returns a list of (frame_index, image-or-None).
    """
    data = open(sld_path, 'rb').read()
    _hdr, frames = D.parse(data)
    fc = len(frames) // 16
    out = []
    for i in range(fc):
        idx = dir_angle * fc + i
        if idx >= len(frames):
            break
        im = decode_red(data, frames[idx])
        out.append((i, D._finish(im, crop=True, margin=4) if im else None))
    return out


def find_sld(stub, anim):
    name = f'{stub}_{anim}A_x2.sld'
    for base in (RAW, os.path.join(GAME, 'resources', '_common', 'drs', 'graphics')):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None


def _bg_alpha(rgb, thresh=14, frame_thresh=30, hole_thresh=4, hole_min=100,
              border=3, feather=0.6):
    """Remove the icon's baked OPAQUE BLACK background. The DDS bakes the bg as
    solid black (alpha 255), so we flood-fill near-black pixels inward from the
    border -> that reaches the background but not the figure's interior dark bits
    (hair, dark horse) which are walled off by the lit silhouette.

    Parts:
    - border flood (`thresh`): the main exterior background.
    - `border`-zone extension up to `frame_thresh`: clears the faint ~1px outer
      frame (luminance ~16-24, above `thresh`) without eating interior dark figure.
    - enclosed PURE-BLACK pockets the border flood can't reach (e.g. the gap inside
      a drawn bow, or the wedge between a horse's head and the rider): remove any
      CONTINUOUS near-black (`< hole_thresh`) component of `>= hole_min` px. The
      threshold is kept at true black (4) so a horse's slightly-lighter dark fur
      (~5-7) doesn't bridge a background pocket into the body; the size floor leaves
      scattered dark texture (individual strands) alone.
    Returns a uint8 alpha (0 = bg) with a sub-pixel feather for clean AA edges."""
    from scipy import ndimage
    lum = rgb.max(axis=2)
    dark = lum < thresh
    seed = np.zeros_like(dark)
    seed[0, :] = seed[-1, :] = seed[:, 0] = seed[:, -1] = True
    seed &= dark
    bg = ndimage.binary_propagation(seed, mask=dark)
    H, W = lum.shape
    yy, xx = np.indices((H, W))
    border_zone = (yy < border) | (yy >= H - border) | (xx < border) | (xx >= W - border)
    extend = border_zone & (lum < frame_thresh)
    bg = ndimage.binary_propagation(bg, mask=(bg | extend))
    cand = (lum < hole_thresh) & ~bg
    lbl, n = ndimage.label(cand)
    if n:
        sizes = ndimage.sum(np.ones_like(lbl), lbl, index=range(1, n + 1))
        big = np.flatnonzero(sizes >= hole_min) + 1
        if big.size:
            bg |= np.isin(lbl, big)
    alpha = np.where(bg, 0.0, 255.0)
    alpha = ndimage.gaussian_filter(alpha, feather)   # ~1px feather -> smooth edge
    return np.clip(alpha, 0, 255).astype('uint8')


def save_icon(icon_id, dst):
    """Extract the icon with red player color (alpha-channel mask). Writes the OPAQUE
    icon to `dst` (icon.png) and a background-removed copy alongside (icon_transparent.png)."""
    src = os.path.join(DDS_DIR, f'{icon_id:03d}_50730.DDS')
    if not os.path.exists(src):
        print(f'    icon DDS not found: {src}'); return False
    arr = np.array(Image.open(src)).astype(float)
    rgb, a = arr[..., :3], arr[..., 3]
    m = ((255 - a) / 255.0)[..., None]
    L = (rgb[..., 0] * 0.30 + rgb[..., 1] * 0.59 + rgb[..., 2] * 0.11)[..., None]
    out = np.clip(rgb * (1 - m) + L * np.array(ICON_TINT) * m, 0, 255)
    opaque = np.dstack([out, np.full(a.shape, 255.0)]).astype('uint8')
    Image.fromarray(opaque).save(dst)
    transparent = np.dstack([out, _bg_alpha(out)]).astype('uint8')
    tdst = os.path.join(os.path.dirname(dst), 'icon_transparent.png')
    Image.fromarray(transparent).save(tdst)
    return True


def build_slug(slug, stub, icon_id):
    udir = os.path.join(UNITS_DIR, slug)
    os.makedirs(udir, exist_ok=True)
    # 1. game icon
    if save_icon(icon_id, os.path.join(udir, 'icon.png')):
        print(f'    icon.png (id {icon_id})')
    # 2. animations — every frame of the dir06 sequence
    idle06 = None
    for anim in ANIMS:
        sld = find_sld(stub, anim)
        if not sld:
            print(f'    SKIP {anim}: no SLD'); continue
        adir = os.path.join(udir, anim)
        if os.path.isdir(adir):
            shutil.rmtree(adir)          # clear stale per-direction files
        os.makedirs(adir, exist_ok=True)
        seq = animation_frames(sld, IDLE_DIR_ANGLE)
        n = 0
        for i, im in seq:
            if im is None:
                continue
            im.save(os.path.join(adir, f'{slug}_{anim}_dir{IDLE_DIR_ANGLE:02d}_f{i:02d}.png'))
            n += 1
            if anim == 'idle' and idle06 is None:
                idle06 = im              # first non-empty idle frame = pose ref
        print(f'    {anim}/: {n} frames at dir{IDLE_DIR_ANGLE:02d}')
    # 3. dir06 idle copy in the unit folder root (the canonical pose ref)
    if idle06 is not None:
        idle06.save(os.path.join(udir, f'{slug}_idle_dir{IDLE_DIR_ANGLE:02d}.png'))
        print(f'    {slug}_idle_dir{IDLE_DIR_ANGLE:02d}.png (pose ref)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slugs', nargs='*', help='subset of slugs (default: all)')
    args = ap.parse_args()
    slugs = args.slugs or list(UNITS)
    for slug in slugs:
        if slug not in UNITS:
            print(f'SKIP {slug}: not in UNITS'); continue
        print(f'{slug}:')
        build_slug(slug, *UNITS[slug])
    print(f'Done -> {UNITS_DIR}')


if __name__ == '__main__':
    main()
