"""Shared helpers for compositing AoE2 ship hulls with their architecture sails.

Hull SLD (u_shp_<ship>) and sail SLD (u_shp_sail_<region>_<cls>_<N>) are authored
in the SAME canvas/hotspot space, so the engine just draws both at the unit's
anchor. We replicate that: decode a hull frame + a sail frame and overlay them
aligned by each frame's hotspot (hx,hy). Sails are animated (frames-per-direction
> 1); the hull is static (1 frame/direction).

dir convention: IDLE_DIR_ANGLE=6 (same facing the rest of the unit pipeline uses).
"""
import os, re, glob, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import sld_decode as D
from PIL import Image

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(_ROOT, 'graphics', 'game_raw_files')
DIRS = 16          # ships store 16 directions (validated: dir06 facing matches the hull)
IDLE_DIR = 6

SAIL_REGIONS = ('afri', 'asia', 'ceas', 'east', 'medi', 'meso', 'orie', 'seas', 'slav', 'west')


def load(basename, res='_x2'):
    p = os.path.join(RAW, basename + res + '.sld')
    if not os.path.exists(p):
        return None
    data = open(p, 'rb').read()
    hdr, frames = D.parse(data)
    return {'data': data, 'hdr': hdr, 'frames': frames,
            'nf': hdr['num_frames'], 'fpd': max(1, hdr['num_frames'] // DIRS)}


def dir_frame_indices(sld, direction=IDLE_DIR):
    """All frame indices for one direction (the animation block), in order."""
    fpd = sld['fpd']
    return list(range(direction * fpd, direction * fpd + fpd))


def decode_frame(sld, idx, tint=None):
    """Decode one frame to its full 800x800 canvas. If tint=(r,g,b) multiply it
    into the player-color mask regions (player tint), like build_unit_assets."""
    fr = sld['frames'][idx]
    im = D.decode_main(sld['data'], fr, player_color=None)
    if im is None:
        return None, fr
    if tint:
        x1, y1, w, h, _ = D._main_geometry(sld['data'], fr)
        mask = D._decode_player_mask(sld['data'], fr, w, h)
        if mask:
            px = im.load(); tr, tg, tb = tint
            for yy in range(h):
                row = mask[yy]
                for xx in range(w):
                    if row[xx] > 15:
                        X, Y = x1 + xx, y1 + yy
                        if 0 <= X < im.width and 0 <= Y < im.height:
                            r, g, b, al = px[X, Y]
                            if al > 0:
                                px[X, Y] = (int(r*tr), int(g*tg), int(b*tb), al)
    return im, fr


def first_nonempty(sld, direction=IDLE_DIR, tint=None):
    """First decodable frame of a direction (skip 'reuse previous' frames)."""
    for idx in dir_frame_indices(sld, direction):
        im, fr = decode_frame(sld, idx, tint=tint)
        if im is not None:
            return im, fr, idx
    return None, None, None


def overlay(hull_img, hull_fr, sail_img, sail_fr):
    """Overlay sail on hull aligned by hotspot (hx,hy). Returns RGBA full canvas."""
    hhx, hhy = hull_fr['hx'], hull_fr['hy']
    shx, shy = sail_fr['hx'], sail_fr['hy']
    HW, HH = hull_img.size
    SW, SH = sail_img.size
    left = max(hhx, shx); top = max(hhy, shy)
    right = max(HW - hhx, SW - shx); bottom = max(HH - hhy, SH - shy)
    out = Image.new('RGBA', (left + right, top + bottom), (0, 0, 0, 0))
    out.alpha_composite(hull_img, (left - hhx, top - hhy))
    out.alpha_composite(sail_img, (left - shx, top - shy))
    return out


def sail_inventory():
    """region -> {'ship': [Ns...], 'boat': [Ns...]} from the x2 sail SLDs on disk."""
    inv = {r: {'ship': [], 'boat': []} for r in SAIL_REGIONS}
    for p in glob.glob(os.path.join(RAW, 'u_shp_sail_*_x2.sld')):
        m = re.match(r'u_shp_sail_([a-z]+)_(ship|boat)_(\d+)_x2', os.path.basename(p))
        if m and m.group(1) in inv:
            inv[m.group(1)][m.group(2)].append(int(m.group(3)))
    for r in inv:
        inv[r]['ship'].sort(); inv[r]['boat'].sort()
    return inv


def sail_basename(region, cls, n):
    return f'u_shp_sail_{region}_{cls}_{n}'


# Player tints (match build_unit_assets): player2 red, player1 blue.
TINT_RED = (0.86, 0.18, 0.16)
TINT_BLUE = (0.16, 0.22, 0.90)

# Sail assignment per generic ship, derived by matching each hull's recreated
# composite against the REAL in-game reference render (sail count + bow/midship/
# stern position), not by size. The universal dir06 rigs are ship_2/3/5/6 and
# boat_2/4/5 — each lands at a hull-dependent position, so the right rig is chosen
# per hull. None = bare hull: the ship either has NO sail (rowed/barge) or already
# carries its sail baked into the hull SLD (galley furled stern, fishing bow lateen).
# NOTE: war_galley/galleon/cannon_galleon really have 2 sails; no universal rig is
# multi-sail, so they use the best-positioned single sail (approximation).
SAIL_ASSIGN = {
    'galley':                 None,          # hull already has furled stern sail
    'war_galley':             ('ship', 5),   # ~2 sails (approx, single big fore/main)
    'galleon':                ('ship', 5),   # ~2 sails (approx)
    'fire_galley':            None,          # rowed, no sail
    'fire_ship':              ('ship', 6),   # single bow lateen
    'fast_fire_ship':         None,          # no sail (bow flame cannon)
    'demolition_raft':        ('boat', 5),   # small low stern canvas
    'demolition_ship':        ('ship', 2),   # single bow lateen
    'heavy_demolition_ship':  None,          # barge of barrels, no sail
    'cannon_galleon':         ('ship', 2),   # ~2 sails midship-stern (approx)
    'elite_cannon_galleon':   ('ship', 3),   # central midship rig
    'transport_ship':         ('ship', 3),   # single midship square sail
    'trade_cog':              ('boat', 4),   # single midship square sail
    'fishing_ship':           None,          # hull already has bow lateen
}

# Generic ships that vary by architecture region (uniques like longboat/caravel/
# turtle/dromon/thirisadai have their own baked art and are excluded).
SHIP_HULLS = {
    'galley': 'u_shp_galley',
    'war_galley': 'u_shp_war_galley',
    'galleon': 'u_shp_galleon',
    'fire_galley': 'u_shp_fire_galley',
    'fire_ship': 'u_shp_fire_ship',
    'fast_fire_ship': 'u_shp_fast_fire_ship',
    'demolition_raft': 'u_shp_demo_raft',
    'demolition_ship': 'u_shp_demo_ship',
    'heavy_demolition_ship': 'u_shp_heavy_demo_ship',
    'cannon_galleon': 'u_shp_cannon_galleon',
    'elite_cannon_galleon': 'u_shp_elite_cannon_galleon',
    'transport_ship': 'u_shp_transport_ship',
    'trade_cog': 'u_shp_trade_cog',
    'fishing_ship': 'u_shp_fishing_ship',
}
