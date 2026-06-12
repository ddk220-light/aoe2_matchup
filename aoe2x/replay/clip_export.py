"""Role: replay — server-side WebM clip generator for AoE2 replays.

Given a parsed mgz match + a focus player, produce a short (<=30s) WebM that:
  - clips to the biggest engagements (battle clusters), skipping idle stretches,
  - plays at 4x,
  - zooms a per-window camera onto the focus player's action,
  - draws units with the same sprites the web UI uses (player-colored disc +
    unit sprite), villagers smaller, the focus player outlined in white,
  - draws a timeline bar at the bottom so viewers see what was skipped,
  - returns the path to the .webm.

Pure Python (Pillow isometric renderer + ffmpeg) -- no headless browser, so it
runs on the python-slim deploy. Sprites are the WebP/PNG assets under
public/assets/sprites, matched to each unit's classified type via the same
normalize-key rule the frontend uses.

build_clip(match, focus_player, out_path) -> out_path
"""
import os
import re
import json
import math
import shutil
import struct
import subprocess
import tempfile
from collections import defaultdict

from PIL import Image, ImageDraw

# ---- output / timing config -------------------------------------------------
W, H = 960, 540          # 16:9, Discord-friendly
FPS = 20
SPEED = 4.0              # 4x game-speed
MAX_OUT_SEC = 30.0       # hard cap on the clip length
TL_H = 26                # timeline bar height (bottom)
MARGIN = 8
MAX_TW = 17.0            # max pixels-per-tile (camera zoom ceiling)

PLAYER_COLORS = {0: "#2f6fdb", 1: "#d33b3b", 2: "#33c04a", 3: "#f2d11b",
                 4: "#15c2c2", 5: "#d055d0", 6: "#9a9a9a", 7: "#f08a25"}

# ---- sprite system (mirrors renderer.js) ------------------------------------
_SPRITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "public", "assets", "sprites")
# Unit types whose icon lives under a different (closest-match) sprite name.
_SPRITE_ALIAS = {"camelscout": "camelrider"}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


_SPRITE_FILES = None


def _sprite_files():
    """normalized type/name -> sprite file path (relative to _SPRITE_DIR)."""
    global _SPRITE_FILES
    if _SPRITE_FILES is None:
        _SPRITE_FILES = {}
        try:
            with open(os.path.join(_SPRITE_DIR, "sprites.json")) as fh:
                data = json.load(fh)
            for grp in ("units", "buildings"):
                for name, info in (data.get(grp) or {}).items():
                    f = info.get("file") if isinstance(info, dict) else None
                    if f:
                        _SPRITE_FILES[_norm(name)] = f
        except Exception:
            pass
    return _SPRITE_FILES


_RAW_SPRITE = {}


def _raw_sprite(utype):
    """Loaded RGBA sprite Image for a unit type, or None."""
    key = _norm(utype)
    if key in _RAW_SPRITE:
        return _RAW_SPRITE[key]
    files = _sprite_files()
    f = files.get(key) or files.get(_norm(_SPRITE_ALIAS.get(key, "")))
    img = None
    if f:
        try:
            img = Image.open(os.path.join(_SPRITE_DIR, f)).convert("RGBA")
        except Exception:
            img = None
    _RAW_SPRITE[key] = img
    return img


_TILE_CACHE = {}


def _unit_tile(utype, color, px, foc):
    """A ready-to-paste RGBA tile: player-colored disc + unit sprite on top
    (focus units get a white outline). Cached per (type, color, size, focus)."""
    ck = (_norm(utype), color, px, foc)
    t = _TILE_CACHE.get(ck)
    if t is not None:
        return t
    size = max(6, px)
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    d.ellipse([0, 0, size - 1, size - 1], fill=color + (235,))
    if foc:
        d.ellipse([0, 0, size - 1, size - 1],
                  outline=(255, 255, 255, 255), width=max(1, size // 11))
    sp = _raw_sprite(utype)
    if sp is not None:
        s2 = int(size * 0.82)
        if s2 >= 2:
            spr = sp.resize((s2, s2), Image.LANCZOS)
            tile.alpha_composite(spr, ((size - s2) // 2, (size - s2) // 2))
    _TILE_CACHE[ck] = tile
    return tile


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _at(a):
    return str(a.type).replace("Action.", "")


def _is_vil(utype):
    u = (utype or "").lower()
    return "villager" in u or "fishing" in u


# Building name (from BUILD payload / starting object) -> (sprite key, footprint
# multiplier). Order matters: more specific keywords first. Keys with no sprite
# (gate/wall) still render as a player-colored diamond.
_BLD_KW = [
    ("town cent", "towncenter", 1.5), ("wonder", "towncenter", 1.7),
    ("castle", "castle", 1.5), ("krepost", "castle", 1.2),
    ("donjon", "castle", 1.2), ("monaster", "monastery", 1.25),
    ("univers", "university", 1.25), ("market", "market", 1.25),
    ("barrack", "barracks", 1.15), ("archery", "archeryrange", 1.15),
    ("stable", "stable", 1.15), ("siege", "siegeworkshop", 1.15),
    ("harbor", "dock", 1.15), ("dock", "dock", 1.15),
    ("blacksmith", "blacksmith", 1.1), ("mining camp", "miningcamp", 0.9),
    ("lumber camp", "lumbercamp", 0.9), ("bombard tower", "bombardtower", 0.95),
    ("watch tower", "watchtower", 0.85), ("guard tower", "watchtower", 0.9),
    ("keep", "watchtower", 0.95), ("tower", "watchtower", 0.85),
    ("outpost", "outpost", 0.7), ("mill", "mill", 1.0),
    ("house", "house", 0.85), ("farm", "farm", 0.9),
    ("gate", "gate", 1.0), ("wall", "wall", 0.7),
]


def _building_info(name):
    n = (name or "").lower()
    for kw, key, mult in _BLD_KW:
        if kw in n:
            return key, mult
    return None


_BTILE = {}


def _building_tile(key, color, size):
    """RGBA tile: low-opacity player-colored isometric diamond with the building
    sprite raised on top (so it reads like a structure, matching the UI)."""
    size = max(12, int(size))
    ck = (key, color, size)
    t = _BTILE.get(ck)
    if t is not None:
        return t
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    cx = size / 2.0
    cy = size * 0.66
    halfW = size / 2.0 - 1
    halfH = size / 4.0
    d.polygon([(cx, cy - halfH), (cx + halfW, cy), (cx, cy + halfH), (cx - halfW, cy)],
              fill=color + (220,), outline=(0, 0, 0, 170))
    sp = _raw_sprite(key)
    if sp is not None:
        s2 = int(size * 0.72)
        if s2 >= 2:
            spr = sp.resize((s2, s2), Image.LANCZOS)
            px = int(cx - s2 / 2.0)
            py = max(0, int(cy - s2 * 0.82))     # bottom of sprite sits on diamond
            tile.alpha_composite(spr, (px, py))
    # Dim the whole structure a touch so units read on top of it.
    tile.putalpha(tile.getchannel("A").point(lambda a: int(a * 0.85)))
    _BTILE[ck] = (tile, cy)
    return tile, cy


# ---------------------------------------------------------------------------
# 1. unit position timelines + attack events
# ---------------------------------------------------------------------------
def _build(match):
    try:
        import unit_classifier as uc
        type_map, remap = uc.build_type_map(match)
    except Exception:
        type_map, remap = {}, {}

    def canon(o):
        return remap.get(o, o)

    pcolor = {}
    for p in match.players:
        pcolor[p.name] = _hex(PLAYER_COLORS.get(getattr(p, "color_id", 0), "#cccccc"))

    units = {}          # cid -> {player,color,mil,utype,moves,birth,death}
    attacks = []        # (t, x, y, player)
    buildings = []      # {player,color,key,mult,x,y,birth}
    seen_bld = set()
    dim = getattr(match.map, "dimension", 220)

    # seed starting units (skip buildings/gaia -- only ids the classifier kept
    # as mobile units appear in type_map). Starting buildings (mainly the Town
    # Center) are captured separately into `buildings`.
    for p in match.players:
        pcol = pcolor.get(p.name, (200, 200, 200))
        for o in (p.objects or []):
            info = _building_info(getattr(o, "name", None))
            sp0 = getattr(o, "position", None)
            if info and sp0 is not None:
                key, mult = info
                k = (p.name, round(sp0.x), round(sp0.y), key)
                if k not in seen_bld:
                    seen_bld.add(k)
                    buildings.append({"player": p.name, "color": pcol, "key": key,
                                      "mult": mult, "x": float(sp0.x),
                                      "y": float(sp0.y), "birth": 0.0})
            cid = canon(o.instance_id)
            utype = type_map.get(cid)
            if not utype and not (o.name and "villager" in o.name.lower()):
                # Not a classified unit and not obviously a villager: likely a
                # building/town center -- don't draw it as a unit.
                if type_map and cid not in type_map:
                    continue
            if not utype:
                utype = "villager" if (o.name and "villager" in o.name.lower()) else "unit"
            sp = getattr(o, "position", None)
            units[cid] = {"player": p.name, "color": pcolor.get(p.name, (200, 200, 200)),
                          "mil": not _is_vil(utype), "utype": utype,
                          "moves": [], "birth": 0.0, "death": None}
            if sp is not None:
                units[cid]["moves"].append((0.0, sp.x, sp.y))

    for a in match.actions:
        if not a.player:
            continue
        at = _at(a)
        t = a.timestamp.total_seconds()
        pl = a.player.name
        pay = a.payload or {}
        pos = getattr(a, "position", None)
        x, y = (pos.x, pos.y) if pos is not None else (None, None)
        tgt = pay.get("target_id")
        ids = [canon(o) for o in pay.get("object_ids", [])]
        is_attack = at == "ORDER" and isinstance(tgt, int)
        if at == "BUILD" and pos is not None:
            info = _building_info(pay.get("building"))
            if info:
                key, mult = info
                k = (pl, round(x), round(y), key)
                if k not in seen_bld:
                    seen_bld.add(k)
                    buildings.append({"player": pl, "color": pcolor.get(pl, (200, 200, 200)),
                                      "key": key, "mult": mult, "x": float(x),
                                      "y": float(y), "birth": t})
            continue
        if at in ("MOVE", "ORDER", "PATROL", "DE_ATTACK_MOVE", "GUARD") and x is not None and y is not None:
            for cid in ids:
                u = units.get(cid)
                if u is None:
                    utype = type_map.get(cid) or "unit"
                    u = units[cid] = {"player": pl, "color": pcolor.get(pl, (200, 200, 200)),
                                      "mil": not _is_vil(utype), "utype": utype,
                                      "moves": [], "birth": t, "death": None}
                u["moves"].append((t, float(x), float(y)))
            if is_attack and len(ids) >= 1:
                attacks.append((t, float(x), float(y), pl))
        elif at == "DE_ATTACK_MOVE" and x is not None and y is not None:
            attacks.append((t, float(x), float(y), pl))

    for u in units.values():
        u["moves"].sort()
        if u["moves"]:
            u["birth"] = min(u["birth"], u["moves"][0][0])
    attacks.sort()
    return units, attacks, buildings, dim


def _pos(u, t):
    """Interpolated (x,y) of a unit at time t, or None if not yet present."""
    mv = u["moves"]
    if not mv or t < u["birth"]:
        return None
    if u["death"] is not None and t > u["death"]:
        return None
    if t <= mv[0][0]:
        return mv[0][1], mv[0][2]
    if t >= mv[-1][0]:
        return mv[-1][1], mv[-1][2]
    lo, hi = 0, len(mv) - 1
    while lo + 1 < hi:
        m = (lo + hi) // 2
        if mv[m][0] <= t:
            lo = m
        else:
            hi = m
    (t0, x0, y0), (t1, x1, y1) = mv[lo], mv[lo + 1]
    f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
    return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f


# ---------------------------------------------------------------------------
# 2. engagement detection + window selection
# ---------------------------------------------------------------------------
def _windows(attacks, duration, budget_game_sec):
    """Pick time windows (start,end) covering the most attack-dense stretches,
    totalling <= budget_game_sec. Returns sorted, merged windows."""
    if not attacks:
        return [(0.0, min(budget_game_sec, duration))]
    BIN = 6.0
    bins = defaultdict(int)
    for t, _x, _y, _p in attacks:
        bins[int(t // BIN)] += 1
    order = sorted(bins, key=lambda b: -bins[b])
    chosen = []
    total = 0.0
    for b in order:
        s = max(0.0, (b - 1) * BIN)
        e = min(duration, (b + 2) * BIN)
        chosen.append((s, e))
        total += e - s
        if total >= budget_game_sec:
            break
    chosen.sort()
    merged = []
    for s, e in chosen:
        if merged and s <= merged[-1][1] + 1.0:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


# ---------------------------------------------------------------------------
# 3. per-window camera (zoom onto the focus player's action)
# ---------------------------------------------------------------------------
def _iso(x, y):
    return (x + y), (y - x)


def _focus_points(units, attacks, focus, s, e, dim):
    """Game-space points the camera should frame for window [s,e]. We zoom onto
    the *engagement*, not the focus player's whole economy: seed on the focus
    player's attack locations (the fight), then keep only the units of either
    side that are near that battle centroid -- so the enemy army shows but the
    far-off base villagers don't drag the framing out to the whole map."""
    times = (s, (s + e) / 2.0, e)
    seeds = [(x, y) for (t, x, y, p) in attacks
             if s <= t <= e and focus and p == focus]
    if len(seeds) < 3:
        # Focus player issued few attack orders here (defending, or the fight is
        # between others) -- seed on every attack in the window instead.
        seeds += [(x, y) for (t, x, y, p) in attacks if s <= t <= e]
    if not seeds:
        # No battles at all: frame the focus player's units (else whole map).
        pts = []
        for u in units.values():
            if focus and u["player"] != focus:
                continue
            p = _pos(u, (s + e) / 2.0)
            if p:
                pts.append(p)
        return pts

    cx = sum(p[0] for p in seeds) / len(seeds)
    cy = sum(p[1] for p in seeds) / len(seeds)
    dists = sorted(math.hypot(p[0] - cx, p[1] - cy) for p in seeds)
    rad = dists[int(0.9 * (len(dists) - 1))] if dists else 8.0
    rad = max(9.0, min(rad, dim * 0.4)) + 6.0      # cover the seed cloud + margin

    pts = list(seeds)
    for u in units.values():
        for tt in times:
            p = _pos(u, tt)
            if p and math.hypot(p[0] - cx, p[1] - cy) <= rad:
                pts.append(p)
                break
    return pts


def _camera(points, dim):
    """Build an isometric projector framing `points`, clamped to MAX_TW zoom.
    Returns (proj, tw). Uses 4/96 percentiles so a stray straggler doesn't
    blow the framing out."""
    if not points:
        points = [(0, 0), (dim, 0), (0, dim), (dim, dim)]
    us = sorted(_iso(x, y)[0] for (x, y) in points)
    vs = sorted(_iso(x, y)[1] for (x, y) in points)

    def pct(a, p):
        i = min(len(a) - 1, max(0, int(round(p * (len(a) - 1)))))
        return a[i]

    umin, umax = pct(us, 0.04), pct(us, 0.96)
    vmin, vmax = pct(vs, 0.04), pct(vs, 0.96)
    du = (umax - umin) or 1.0
    dv = (vmax - vmin) or 1.0
    umin -= du * 0.18; umax += du * 0.18
    vmin -= dv * 0.18; vmax += dv * 0.18
    uw = max(umax - umin, 10.0)
    vh = max(vmax - vmin, 10.0)
    availw = W - 2 * MARGIN
    availh = H - TL_H - 2 * MARGIN
    # screen-x span = uw*tw/2 ; screen-y span = vh*tw/4
    tw = min(2 * availw / uw, 4 * availh / vh, MAX_TW)
    tw = max(tw, 1.5)
    uc = (umin + umax) / 2.0
    vc = (vmin + vmax) / 2.0
    ox = MARGIN + availw / 2.0 - uc * tw / 2.0
    oy = MARGIN + availh / 2.0 - vc * tw / 4.0

    def proj(x, y):
        u, v = _iso(x, y)
        return u * tw / 2.0 + ox, v * tw / 4.0 + oy
    return proj, tw


# ---------------------------------------------------------------------------
# 4. render
# ---------------------------------------------------------------------------
def _terrain_bg(match, dim, proj, tw):
    th = tw / 2.0
    img = Image.new("RGBA", (W, H), (24, 28, 22, 255))
    d = ImageDraw.Draw(img)
    try:
        mp = match.map
        from aoe2x.replay.blueprint import _terrain_hex, _load_terrain_names
        names = _load_terrain_names(getattr(match, "dataset_id", 100))
        tiles = getattr(mp, "tiles", None) or []
        if not tiles:
            raise RuntimeError("no tiles")
        for tile in tiles:
            tx, tyy = tile.position.x, tile.position.y
            px, py = proj(tx, tyy)
            if px < -tw or px > W + tw or py < -tw or py > H + tw:
                continue
            col = _terrain_hex(names.get(tile.terrain, "") if names else "")
            d.polygon([(px, py - th / 2), (px + tw / 2, py),
                       (px, py + th / 2), (px - tw / 2, py)], fill=_hex(col))
    except Exception:
        pts = [proj(0, 0), proj(dim, 0), proj(dim, dim), proj(0, dim)]
        d.polygon(pts, fill=(70, 110, 55, 255))
    return img


def _usize(tw, mil):
    base = max(12.0, min(40.0, tw * 1.9))
    return int(base if mil else base * 0.8)


def _frame(bg, units, buildings, attacks, proj, tw, t, focus, tl):
    img = bg.copy()
    # buildings first (under everything), once they've been placed
    for b in buildings:
        if t < b["birth"]:
            continue
        px, py = proj(b["x"], b["y"])
        if px < -70 or px > W + 70 or py < -70 or py > H + 70:
            continue
        bsize = int(max(16.0, min(72.0, tw * 3.0 * b["mult"])))
        tile, cyc = _building_tile(b["key"], b["color"], bsize)
        img.alpha_composite(tile, (int(px - bsize / 2.0), int(py - cyc)))
    d = ImageDraw.Draw(img, "RGBA")
    # recent attack flashes
    for (at_, ax, ay, _p) in attacks:
        dt = t - at_
        if 0 <= dt < 1.2:
            px, py = proj(ax, ay)
            r = (5 + 10 * dt) * max(1.0, tw / 5.0)
            a = int(180 * (1 - dt / 1.2))
            d.ellipse([px - r, py - r, px + r, py + r], outline=(255, 220, 120, a), width=2)
    # units as sprites (villagers first so military sits on top)
    drawn = sorted(units.values(), key=lambda u: 0 if not u["mil"] else 1)
    for u in drawn:
        p = _pos(u, t)
        if p is None:
            continue
        px, py = proj(*p)
        if px < -50 or px > W + 50 or py < -50 or py > H + 50:
            continue
        foc = bool(focus) and (u["player"] == focus)
        size = _usize(tw, u["mil"])
        if foc:
            size += 2
        tile = _unit_tile(u["utype"], u["color"], size, foc)
        img.alpha_composite(tile, (int(px - size / 2), int(py - size / 2)))
    _timeline(d, t, tl)
    return img


def _timeline(d, t, tl):
    duration, windows = tl
    y0 = H - TL_H + 4
    y1 = H - 6
    x0, x1 = MARGIN, W - MARGIN
    d.rectangle([x0, y0, x1, y1], fill=(40, 44, 50, 230), outline=(90, 96, 105, 255))
    span = x1 - x0
    for s, e in windows:
        sx = x0 + span * (s / duration)
        ex = x0 + span * (e / duration)
        d.rectangle([sx, y0, ex, y1], fill=(70, 130, 200, 200))
    hx = x0 + span * (t / duration)
    d.line([(hx, y0 - 2), (hx, y1 + 2)], fill=(255, 230, 120, 255), width=2)


def _ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()      # bundled binary -> no apt dependency
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def _encode(frames_dir, out_path):
    # Encode to a UNIQUE temp file and atomically rename, so a killed/timed-out
    # worker never leaves a half-written .webm that would be served from cache,
    # and two concurrent renders of the same match can't share a tmp path and
    # cache a corrupt clip (the old fixed out_path + '.tmp.webm' could).
    fd, tmp_out = tempfile.mkstemp(
        suffix=".tmp.webm", dir=os.path.dirname(out_path) or None)
    os.close(fd)
    cmd = [_ffmpeg_exe(), "-y", "-framerate", str(FPS),
           "-i", os.path.join(frames_dir, "f%05d.png"),
           "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34", "-pix_fmt", "yuv420p",
           "-row-mt", "1", "-an", tmp_out]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.replace(tmp_out, out_path)
    finally:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except OSError:
                pass


def build_clip(match, focus_player, out_path):
    duration = match.duration.total_seconds()
    units, attacks, buildings, dim = _build(match)
    budget_game = MAX_OUT_SEC * SPEED                 # game-seconds we can show
    windows = _windows(attacks, duration, budget_game)
    shown = sum(e - s for s, e in windows)
    if shown > budget_game:                            # trim last window
        over = shown - budget_game
        s, e = windows[-1]
        windows[-1] = (s, max(s, e - over))
    tl = (duration, windows)

    tmp = tempfile.mkdtemp(prefix="clip_")
    try:
        fi = 0
        dt = SPEED / FPS                                # game-seconds advanced per frame
        for (s, e) in windows:
            # Per-window camera: zoom onto where the focus player is fighting.
            pts = _focus_points(units, attacks, focus_player, s, e, dim)
            proj, tw = _camera(pts, dim)
            bg = _terrain_bg(match, dim, proj, tw)
            t = s
            while t < e:
                img = _frame(bg, units, buildings, attacks, proj, tw, t, focus_player, tl)
                img.convert("RGB").save(os.path.join(tmp, f"f{fi:05d}.png"))
                fi += 1
                t += dt
        if fi == 0:
            raise RuntimeError("no frames")
        _encode(tmp, out_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out_path
