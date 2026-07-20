"""intro_card.py — full-screen (1920x1080) UNIT-INTRO card: the opening ~3s hero
shot of a long-form unit-analysis video.

Entry points:
  make_unit_intro_card(civ, slug)  -> static PIL image (hero = a mid-swing frame
                                      of the unit's attack.gif when available)
  make_unit_intro_video(civ, slug, out_mp4, duration_s=3.0)
                                   -> animated card: the attack.gif loops as the
                                      hero over the static layout, ffmpeg-encoded.
                                      Falls back to a still video if no GIF exists.
  make_outro_thanks_video(civ, slug, out_mp4, duration_s=6.0)
                                   -> animated CLOSING card (new FINAL segment of
                                      the long-form video): a centered unit stage
                                      + looping hero, same parchment chrome, a
                                      generic "visit aoe2matchup.com" + "Thank You
                                      For Watching" banner. Shares its ffmpeg encode
                                      path with make_unit_intro_video (see
                                      `_encode_gif_loop_video`).

Visual family: "Unit Spotlight — Parchment" (user-approved design-tool mockup) —
an aged-parchment ground with a double sepia frame, rotated-diamond corner marks
and stage rings, IM Fell English / IM Fell English SC / EB Garamond type, and a
translucent parchment stats plate. The card is rendered as HTML via headless
Chrome/Edge (`overlay.render_card._screenshot`) rather than drawn with Pillow —
gradients, translucency and webfonts are impractical to reproduce pixel-for-pixel
with ImageDraw. The unit's own GIF/sprite is NOT part of the HTML; it is
composited by Pillow onto the screenshot afterward (see `_composite_hero`), so
the same static base image can be reused frame-to-frame for the animated card.

Stat rows carry PERCENTILE BARS: each core stat's bar is filled to the unit's
percentile among all units of its BROAD CLASS (infantry / cavalry / ranged, the
same collapse `aoe2x.analysis.story_rules_v2.broad_class` uses for the counter
triangle). Population definition (documented, deliberate):
  * every `ref_units` row (all Imperial) EXCLUDING ships and siege
    (unit_class_name in Unknown/Siege Weapon/Ballista/Unpacked Siege Unit),
  * deduped to DISTINCT unit_slug, taking the MEDIAN across civs per stat — so 40+
    civs of Champion count once and don't dominate the distribution,
  * each slug categorized via `story_rules.categorize` + collapsed with
    `broad_class` (eagle-speed override included), yielding ~26 infantry /
    ~22 cavalry / ~33 ranged lines.
Percentiles use the midrank rule ((less + equal/2) / n). Cost uses the module's
gold-weighted cost (food+wood+1.5*gold), so "expensive" = fuller bar.

Combat data source: apps/video/sim_v2/_work/elite_temple_guard_muisca/
combat_dicts_all.json (a flat "{civ}/{slug}" map covering many elite unique
units — works for any unit whose key is present). Armor-class id -> name comes
from the reference DB's `armor_classes` table with a hardcoded fallback.

CLI: python -m overlay.intro_card [civ] [slug] [out.png|out.mp4]
     (an .mp4 extension renders the animated card instead of the still PNG)
"""
from __future__ import annotations

import html
import json
import sqlite3
import statistics
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageFilter, ImageSequence

from overlay.ffutil import find_ffmpeg
from overlay.render_card import _screenshot  # headless Chrome/Edge HTML->PNG helper

REPO_ROOT = Path(__file__).resolve().parents[3]
# When this file lives in a `.claude/worktrees/<name>/` git worktree, REPO_ROOT is
# the worktree — which does NOT carry the gitignored apps/video/media/ hi-res
# sprite/GIF tree. Resolve the main checkout's root too; harmless no-op otherwise.
_MAIN_CHECKOUT_ROOT = REPO_ROOT
_parts = REPO_ROOT.parts
if ".claude" in _parts:
    _cut = _parts.index(".claude")
    _MAIN_CHECKOUT_ROOT = Path(*_parts[:_cut])

SPRITE_DIR = REPO_ROOT / "apps" / "website" / "static" / "img" / "unit_sprites"
ICON_DIR = REPO_ROOT / "apps" / "website" / "static" / "img" / "units"
REF_DB = REPO_ROOT / "data" / "golden" / "aoe2_reference.db"
COMBAT_DICTS_JSON = (REPO_ROOT / "apps" / "video" / "sim_v2" / "_work"
                     / "elite_temple_guard_muisca" / "combat_dicts_all.json")
_MEDIA_ROOTS = [
    REPO_ROOT / "apps" / "video" / "media" / "units",           # in-worktree, if present
    _MAIN_CHECKOUT_ROOT / "apps" / "video" / "media" / "units",  # main checkout fallback
]

# aoe2x imports (categorize/broad_class) need the repo root on sys.path.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# NOTE: the card's colour palette now lives entirely in `_card_html`'s inline
# CSS (the "Unit Spotlight — Parchment" mockup's own hex/rgba values) — there's
# no separate Pillow-side palette to keep in sync anymore.

# id -> name, from the extraction pipeline's armor_classes table (also mirrored at
# reference/armor-classes.md). Hardcoded fallback ONLY used if REF_DB is missing.
_ARMOR_CLASS_FALLBACK = {
    0: "Unused", 1: "Infantry", 2: "Turtle Ships", 3: "Base Pierce", 4: "Base Melee",
    5: "War Elephants", 6: "Unused", 7: "Unused", 8: "Cavalry", 9: "Unused",
    10: "Unused", 11: "All Buildings", 12: "Unused", 13: "Stone Defense",
    14: "Predator Animals", 15: "Archers", 16: "Ships & Saboteurs", 17: "Rams",
    18: "Trees", 19: "Unique Units", 20: "Siege Weapons", 21: "Standard Buildings",
    22: "Walls & Gates", 23: "Gunpowder Units", 24: "Boars", 25: "Monks",
    26: "Castles", 27: "Spearmen", 28: "Cavalry Archers", 29: "Eagle Warriors",
    30: "Camels", 31: "Leitis", 32: "Condottieri", 33: "Fishing Ships",
    34: "Mamelukes", 35: "Heroes & Kings", 36: "Hussite Wagons", 37: "Unused",
    38: "Skirmishers", 39: "Mounted Archers",
}
_BASE_ATTACK_CLASSES = {3, 4}  # Base Pierce, Base Melee — not bonuses

# classes not worth naming as a combat "counters" target — buildings, defenses,
# and terrain/wildlife dressing rather than field-army unit types.
_NON_COMBAT_CLASSES = {0, 6, 7, 9, 10, 11, 12, 13, 18, 21, 22, 23, 24, 26, 33, 37}

# armor classes NOT shown in the WEAKNESSES list: 31 (Leitis) is carried by
# virtually every unit purely so the Leitis' armor-ignoring attack has a hook —
# it says nothing about this unit (user-requested suppression).
_WEAKNESS_SUPPRESS = {31}

# priority order for picking a unit's own "identity" (infantry/cavalry/archer/...)
# from the armor classes it carries — first match wins. Deliberately excludes the
# near-universal 19 (Unique Units) / 31 (Leitis) tags.
_IDENTITY_PRIORITY = [8, 1, 15, 30, 29, 28, 39, 38, 27, 5, 34, 25, 23]
_IDENTITY_LABEL = {
    8: "cavalry", 1: "infantry", 15: "archer", 30: "camel", 29: "shock infantry",
    28: "cavalry archer", 39: "mounted archer", 38: "skirmisher", 27: "spearman",
    5: "elephant", 34: "mameluke", 25: "monk", 23: "gunpowder unit",
}

_DISPLAY_NAME_OVERRIDE = {
    "Eagle Warriors": "Shock Infantry",     # current game terminology
    "Standard Buildings": "buildings", "All Buildings": "buildings",
    "Walls & Gates": "walls", "Stone Defense": "defensive buildings",
    "Ships & Saboteurs": "ships",
}


def _armor_class_names() -> dict[int, str]:
    if REF_DB.exists():
        try:
            conn = sqlite3.connect(str(REF_DB))
            try:
                rows = conn.execute("SELECT id, name FROM armor_classes").fetchall()
                if rows:
                    return {int(i): n for i, n in rows}
            finally:
                conn.close()
        except sqlite3.Error:
            pass
    return dict(_ARMOR_CLASS_FALLBACK)


def _display_name(name: str) -> str:
    return _DISPLAY_NAME_OVERRIDE.get(name, name)


def load_combat_dict(civ: str, slug: str, json_path: Path = COMBAT_DICTS_JSON) -> dict:
    with open(json_path, encoding="utf-8") as f:
        all_dicts = json.load(f)
    key = f"{civ}/{slug}"
    if key not in all_dicts:
        raise KeyError(f"{key!r} not found in {json_path}")
    return all_dicts[key]


# ---------------------------------------------------------------------------
# Percentile population (broad class -> per-slug median stats)
# ---------------------------------------------------------------------------

# ref_units unit_class_name values excluded from the percentile population:
# ships (the "Unknown" rows are all water units) and all siege families.
_POP_EXCLUDE_CLASSES = ("Unknown", "Siege Weapon", "Ballista", "Unpacked Siege Unit")
_COST_WEIGHT = {"food": 1.0, "wood": 1.0, "gold": 1.5}  # matches overlay_data.py
_COST_LOW, _COST_HIGH = 65, 120   # typical unit-cost band (summary's cost tier)

_STAT_KEYS = ("hp", "attack", "melee_armor", "pierce_armor", "speed", "cost")


@lru_cache(maxsize=1)
def _population() -> dict[str, list[dict]]:
    """{broad_class: [{slug, hp, attack, melee_armor, pierce_armor, speed, cost}]}
    from ref_units — distinct slugs, median across civs (see module docstring)."""
    from aoe2x.analysis.story_rules import categorize
    from aoe2x.analysis.story_rules_v2 import broad_class

    conn = sqlite3.connect(str(REF_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT unit_slug, unit_class_name, is_ranged, final_hp, final_attack,"
            " final_melee_armor, final_pierce_armor, final_speed, final_cost_food,"
            " final_cost_wood, final_cost_gold FROM ref_units"
            " WHERE unit_class_name NOT IN (?,?,?,?)", _POP_EXCLUDE_CLASSES,
        ).fetchall()
    finally:
        conn.close()

    by_slug: dict[str, list] = {}
    for r in rows:
        by_slug.setdefault(r["unit_slug"], []).append(r)

    pop: dict[str, list[dict]] = {}
    for slug, rs in by_slug.items():
        med = {
            "slug": slug,
            "hp": statistics.median(r["final_hp"] or 0 for r in rs),
            "attack": statistics.median(r["final_attack"] or 0 for r in rs),
            "melee_armor": statistics.median(r["final_melee_armor"] or 0 for r in rs),
            "pierce_armor": statistics.median(r["final_pierce_armor"] or 0 for r in rs),
            "speed": statistics.median(r["final_speed"] or 0 for r in rs),
            "cost": statistics.median(
                (r["final_cost_food"] or 0) * _COST_WEIGHT["food"]
                + (r["final_cost_wood"] or 0) * _COST_WEIGHT["wood"]
                + (r["final_cost_gold"] or 0) * _COST_WEIGHT["gold"] for r in rs),
        }
        r0 = rs[0]
        cat = categorize(slug, r0["unit_class_name"], r0["is_ranged"], med["speed"])
        pop.setdefault(broad_class(cat, r0["is_ranged"]), []).append(med)
    return pop


def _subject_broad(civ: str, slug: str, d: dict) -> str:
    """The subject's broad class, via the same categorize+collapse the population
    uses. unit_class_name comes from the subject's own ref_units row."""
    from aoe2x.analysis.story_rules import categorize
    from aoe2x.analysis.story_rules_v2 import broad_class

    class_name = None
    try:
        conn = sqlite3.connect(str(REF_DB))
        try:
            row = conn.execute(
                "SELECT unit_class_name FROM ref_units WHERE unit_slug=? LIMIT 1",
                (slug,)).fetchone()
            if row:
                class_name = row[0]
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    is_ranged = (d.get("attack_range") or 0) > 0
    cat = categorize(slug, class_name, is_ranged, d.get("movement_speed") or 1.0)
    return broad_class(cat, is_ranged)


def _pctile(vals: list[float], x: float) -> float:
    """Midrank percentile of x among vals, in [0, 1]."""
    if not vals:
        return 0.5
    less = sum(1 for v in vals if v < x)
    eq = sum(1 for v in vals if v == x)
    return (less + 0.5 * eq) / len(vals)


def stat_percentiles(civ: str, slug: str, d: dict) -> tuple[dict[str, float], str, int]:
    """(percentiles keyed by _STAT_KEYS, broad class name, population size)."""
    broad = _subject_broad(civ, slug, d)
    peers = _population().get(broad, [])
    subject = {
        "hp": d.get("hp") or 0,
        "attack": d.get("attack") or 0,
        "melee_armor": d.get("melee_armor") or 0,
        "pierce_armor": d.get("pierce_armor") or 0,
        "speed": d.get("movement_speed") or 0,
        "cost": _weighted_cost(d),
    }
    pcts = {k: _pctile([p[k] for p in peers], subject[k]) for k in _STAT_KEYS}
    return pcts, broad, len(peers)


# ---------------------------------------------------------------------------
# Hero media resolution (3-tier: media tree -> sprite tree -> website icon)
# ---------------------------------------------------------------------------

def _media_file(slug: str, name: str) -> Path | None:
    for root in _MEDIA_ROOTS:
        p = root / slug / name
        if p.exists():
            return p
    return None


def _hero_gif(slug: str) -> Path | None:
    return _media_file(slug, "attack.gif")


def _hero_still(slug: str, unit_name: str = "") -> Path | None:
    """Best static hero: hi-res sprite_full, else the checked-in game-sprite tree
    (civ-suffix-stripped slug convention), else the website's square unit icon."""
    p = _media_file(slug, "sprite_full.png")
    if p is not None:
        return p
    for cand in (slug, slug.rsplit("_", 1)[0]):
        sp = SPRITE_DIR / f"{cand}.png"
        if sp.exists():
            return sp
    if unit_name:
        ic = ICON_DIR / f"{unit_name.replace(' ', '_')}.png"
        if ic.exists():
            return ic
    return None


def _gif_frames(path: Path) -> list[tuple[Image.Image, int]]:
    """[(RGBA frame, duration_ms)] for every frame of the GIF, cropped to the
    UNION alpha bbox across all frames (one shared crop, so the animation doesn't
    jitter) — the game-capture GIFs leave a lot of empty canvas around the unit,
    and cropping lets the hero render much larger in the same box."""
    im = Image.open(path)
    out = []
    for frame in ImageSequence.Iterator(im):
        out.append((frame.convert("RGBA"), int(frame.info.get("duration", 100)) or 100))
    boxes = [f.getchannel("A").getbbox() for f, _ in out]
    boxes = [b for b in boxes if b]
    if boxes:
        pad = 8
        x0 = max(0, min(b[0] for b in boxes) - pad)
        y0 = max(0, min(b[1] for b in boxes) - pad)
        x1 = min(im.width, max(b[2] for b in boxes) + pad)
        y1 = min(im.height, max(b[3] for b in boxes) + pad)
        out = [(f.crop((x0, y0, x1, y1)), d) for f, d in out]
    return out


def _fit_img(im: Image.Image, box) -> Image.Image:
    bw, bh = box
    scale = min(bw / im.width, bh / im.height)
    return im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                     Image.LANCZOS)


# ---------------------------------------------------------------------------
# Stat derivation (bonuses / weaknesses / one-line summary)
# ---------------------------------------------------------------------------

def _weighted_cost(d: dict) -> float:
    return (d.get("cost_food", 0) * _COST_WEIGHT["food"]
            + d.get("cost_wood", 0) * _COST_WEIGHT["wood"]
            + d.get("cost_gold", 0) * _COST_WEIGHT["gold"])


def _num(v) -> str:
    f = float(v or 0)
    return str(int(f)) if f == int(f) else f"{f:.2f}".rstrip("0").rstrip(".")


def _identity(armor_ids: set[int]) -> str:
    for cid in _IDENTITY_PRIORITY:
        if cid in armor_ids:
            return _IDENTITY_LABEL[cid]
    return "unit"


def analyze_unit(d: dict) -> dict:
    """Derive every display value (bonuses, weaknesses, summary) from one combat
    dict. Pure function of the data — no unit-specific hardcoding."""
    names = _armor_class_names()
    attacks = {int(k): v for k, v in json.loads(d.get("attacks_json") or "{}").items()}
    armors = {int(k): v for k, v in json.loads(d.get("armors_json") or "{}").items()}

    base_attack = attacks.get(4) or attacks.get(3) or 0
    bonuses = sorted(
        ((cid, amt) for cid, amt in attacks.items()
         if cid not in _BASE_ATTACK_CLASSES and amt > 0
         and names.get(cid, "Unused") != "Unused"),
        key=lambda t: -t[1],
    )
    carried = [cid for cid in armors
               if cid not in _BASE_ATTACK_CLASSES
               and cid not in _WEAKNESS_SUPPRESS
               and names.get(cid, "Unused") != "Unused"]
    carried.sort(key=lambda c: -abs(armors[c]))

    own_armor_ids = set(armors) - _BASE_ATTACK_CLASSES
    identity = _identity(own_armor_ids)
    is_elite = "elite" in (d.get("unit_name") or "").lower()
    is_ranged = (d.get("attack_range") or 0) > 0

    # cost tier from the gold-weighted cost (a gold-heavy unit reads as pricier
    # than its raw total, matching how players actually feel its cost).
    wcost = _weighted_cost(d)
    if wcost > _COST_HIGH:
        tier = "High-cost"
    elif wcost < _COST_LOW:
        tier = "Low-cost"
    else:
        tier = ""

    # "counters" phrase: biggest non-base, non-static-target attack bonus.
    combat_bonuses = [(cid, amt) for cid, amt in bonuses if cid not in _NON_COMBAT_CLASSES]
    counters_phrase = ""
    if combat_bonuses:
        cid, amt = combat_bonuses[0]
        target = _display_name(names.get(cid, f"class {cid}")).lower()
        ratio = amt / base_attack if base_attack else 0
        verb = "shreds" if ratio >= 0.4 else ("punishes" if ratio > 0 else "trades with")
        counters_phrase = f"{verb} {target}"
    elif bonuses:
        cid, amt = bonuses[0]
        counters_phrase = f"punishes {_display_name(names.get(cid, '')).lower()}"

    # special-ability clause (checked in a fixed priority order; first match wins
    # so the one-liner stays a single clause).
    special_phrase = None
    for cond, phrase in (
        (d.get("attack_speed_ramp", 0) > 0, "its attack speed ramps up the longer it fights"),
        (d.get("bonus_damage_reduction", 0) > 0,
         f"shrugs off {d.get('bonus_damage_reduction', 0) * 100:.0f}% of bonus damage"),
        (d.get("ignores_melee_armor") or d.get("ignores_pierce_armor"), "ignores armor"),
        ((d.get("trample_flat_damage") or 0) > 0 or (d.get("trample_percent") or 0) > 0,
         "splashes damage onto nearby enemies with every hit"),
        ((d.get("charge_attack_melee") or 0) > 0, "can charge in for a burst of bonus damage"),
        ((d.get("extra_projectiles") or 0) > 0, "fires a spread of extra projectiles"),
        ((d.get("hp_regen") or 0) > 0, "regenerates HP over time"),
        ((d.get("dodge_shield_max") or 0) > 0, "can block incoming hits"),
        ((d.get("armor_strip_per_hit") or 0) > 0, "strips enemy armor on hit"),
        ((d.get("attack_bonus_per_kill") or 0) > 0, "gets stronger with every kill"),
    ):
        if cond:
            special_phrase = phrase
            break

    # weaknesses: melee units get kited by ranged fire; every unit is exposed to
    # "anti-<its own identity>" bonuses by definition of carrying that class.
    weaknesses = []
    if not is_ranged:
        weaknesses.append("ranged fire")
    if identity != "unit":
        weaknesses.append(f"anti-{identity} bonuses")
    base_acc = d.get("base_accuracy")
    if is_ranged and base_acc is not None and base_acc < 90:
        weaknesses.append(f"poor accuracy ({base_acc:.0f}%)")

    lead = " ".join(p for p in (tier, "elite" if is_elite else "", identity) if p)
    lead = lead[0].upper() + lead[1:] if lead else identity.capitalize()
    summary = f"{lead} that {counters_phrase}" if counters_phrase else lead
    if special_phrase:
        summary += f" — {special_phrase}"
    if weaknesses:
        summary += f" — but folds to {' and '.join(weaknesses)}."
    else:
        summary += "."

    reload_s = (1.0 / d["attack_speed"]) if d.get("attack_speed") else None
    reload_min_s = (1.0 / d["attack_speed_min"]) if d.get("attack_speed_min") else None

    return {
        "names": names,
        "attacks": attacks,
        "armors": armors,
        "bonuses": bonuses,
        "carried": carried,
        "identity": identity,
        "is_ranged": is_ranged,
        "reload_s": reload_s,
        "reload_min_s": reload_min_s,
        "weighted_cost": wcost,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# HTML card renderer (headless Chrome/Edge screenshot) — "Unit Spotlight —
# Parchment" design. Matches the design-tool mockup `Unit Spotlight
# Parchment.dc.html`: aged-parchment radial ground + corner stains + inset
# vignette, a 3px-double + 1px inset frame, four rotated-square (diamond)
# corner marks, IM Fell English / IM Fell English SC / EB Garamond type, a
# translucent parchment stats plate with olive "Bonus Damage" and rust "Armor
# Categories" chip rows, and a top/bottom-ruled "The Verdict" band. The unit's
# GIF/sprite is NOT part of the HTML — see `_composite_hero` below.
# ---------------------------------------------------------------------------

CARD_W, CARD_H = 1920, 1080
HERO_BOX = (150, 360, 760, 600)     # (x, y, w, h) — mirrors the mockup's unit-stage div
HERO_MAX_H = 520                    # mirrors the mockup's img height:520px
HERO_BOTTOM_MARGIN = 70             # mirrors the mockup's img marginBottom:70px

# Outro "thank you" card — the same stage motif (glow ellipse + two diamond
# rings) as HERO_BOX above, but CENTERED horizontally on the 1920-wide canvas
# and generously sized (the intro's stage shares the frame with a title +
# stats plate; the outro's stage IS the frame, so it gets to be bigger).
OUTRO_STAGE_BOX = (510, 150, 900, 660)   # (x, y, w, h) — centered: x = (1920-900)/2
OUTRO_HERO_MAX_H = 560
OUTRO_HERO_BOTTOM_MARGIN = 90

_GOOGLE_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link href="https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1'
    '&family=IM+Fell+English+SC&family=EB+Garamond:ital,wght@0,500;0,600;0,700;1,500'
    '&display=swap" rel="stylesheet">'
)

# Inline SVG stat icons — identical path data to the mockup's React icon() helper
# (currentColor stroke, so the wrapping span's `color:` sets the tint).
_ICON_PATHS = {
    "hp": ["M12 21C7 16.5 3.5 13.2 3.5 9.3 3.5 6.4 5.7 4.5 8.2 4.5c1.5 0 2.9.7 3.8 2"
           " .9-1.3 2.3-2 3.8-2 2.5 0 4.7 1.9 4.7 4.8 0 3.9-3.5 7.2-8.5 11.7z"],
    "atk": ["M6.5 17.5L18 6V3h-3L3.5 14.5", "M5 15l4 4", "M4 20l1-1", "M7.5 21.5L2.5 16.5"],
    "melee": ["M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6z"],
    "pierce": ["M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6z", "M12 8v8",
               "M8.5 11.5L12 8l3.5 3.5"],
    "speed": ["M4 12h9", "M4 7h11", "M4 17h7", "M15 12l5-5v10z"],
    "rate": ["M12 21a9 9 0 1 1 9-9", "M12 7v5l3 3", "M17 17l4 4", "M21 17v4h-4"],
    "gold": ["M12 3l9 6-9 12L3 9z", "M3 9h18", "M12 3l-3 6 3 12 3-12z"],
}


def _svg_icon(key: str) -> str:
    """Not in the mockup's icon set (ranged units only) — a simple crosshair,
    same stroke style as the rest so it reads as part of the family."""
    if key == "range":
        return ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none" '
                'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
                'stroke-linejoin="round"><circle cx="12" cy="12" r="8"/>'
                '<circle cx="12" cy="12" r="3"/><path d="M12 2v4"/><path d="M12 18v4"/>'
                '<path d="M2 12h4"/><path d="M18 12h4"/></svg>')
    ds = "".join(f'<path d="{p}"/>' for p in _ICON_PATHS[key])
    return (f'<svg viewBox="0 0 24 24" width="22" height="22" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round">{ds}</svg>')


def _stat_rows_for(d: dict, a: dict, pcts: dict) -> list[dict]:
    """[{label, value, width (0..1), icon}] in mockup row order. Bar widths are
    the unit's PERCENTILE among its broad-class peers (`stat_percentiles`),
    NOT value/max — a user-locked decision, unlike the mockup's placeholder
    `pct(v, max)` logic. Range (ranged units only) and Attack Rate have no
    percentile population defined (`_STAT_KEYS` doesn't cover them) — both
    fall back to a flat 50% fill per spec ("keep it simple")."""
    rows = [
        {"label": "Hit Points", "value": _num(d.get("hp")), "width": pcts["hp"], "icon": "hp"},
        {"label": "Attack", "value": _num(d.get("attack")), "width": pcts["attack"], "icon": "atk"},
        {"label": "Melee Armor", "value": _num(d.get("melee_armor")),
         "width": pcts["melee_armor"], "icon": "melee"},
        {"label": "Pierce Armor", "value": _num(d.get("pierce_armor")),
         "width": pcts["pierce_armor"], "icon": "pierce"},
        {"label": "Speed", "value": _num(d.get("movement_speed")),
         "width": pcts["speed"], "icon": "speed"},
    ]
    if a["is_ranged"] and d.get("attack_range"):
        rows.append({"label": "Range", "value": _num(d.get("attack_range")),
                     "width": 0.5, "icon": "range"})

    reload_txt = f"{a['reload_s']:.2f}s" if a["reload_s"] else "—"
    if a["reload_min_s"] and a["reload_s"] and a["reload_min_s"] < a["reload_s"] - 1e-6:
        reload_txt = f"{a['reload_s']:.1f}s → {a['reload_min_s']:.1f}s"
    rows.append({"label": "Attack Rate", "value": reload_txt, "width": 0.5, "icon": "rate"})

    food, wood, gold = d.get("cost_food") or 0, d.get("cost_wood") or 0, d.get("cost_gold") or 0
    cost_parts = [f"{int(v)} {lbl}" for v, lbl
                 in ((food, "Food"), (wood, "Wood"), (gold, "Gold")) if v]
    cost_txt = " · ".join(cost_parts) if cost_parts else "—"
    rows.append({"label": "Cost", "value": cost_txt, "width": pcts["cost"], "icon": "gold"})
    return rows


def _stat_row_html(s: dict) -> str:
    width_pct = max(0, min(100, round(s["width"] * 100)))
    return f"""
      <div style="display:flex;flex-direction:column;gap:4px;margin-bottom:10px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <div style="display:flex;align-items:center;gap:10px;">
            <span style="display:flex;width:22px;height:22px;color:#6b4a1e;">{_svg_icon(s['icon'])}</span>
            <span style="font-size:24px;font-weight:600;color:#5c4326;">{html.escape(s['label'])}</span>
          </div>
          <span style="font-size:26px;font-weight:700;color:#3d2a16;">{html.escape(str(s['value']))}</span>
        </div>
        <div style="height:11px;background:rgba(107,74,30,.12);border:1px solid rgba(94,66,30,.4);">
          <div style="height:100%;width:{width_pct}%;background:linear-gradient(90deg,#8a6428,#6b4a1e);"></div>
        </div>
      </div>"""


def _is_unique(civ: str, slug: str) -> bool:
    """Unique units carry the civ suffix on their slug (project convention)."""
    return slug.rsplit("_", 1)[-1] == civ.lower().replace(" ", "")


def _chip_label(name: str) -> str:
    """`_DISPLAY_NAME_OVERRIDE` has a few lowercase entries (e.g. "ships",
    "buildings") tuned for the old inline-sentence phrasing ("folds to ...
    ships"). Title-case for a standalone chip so it matches the rest (already
    title-cased names like "War Elephants" pass through unchanged)."""
    return name.title()


def _card_html(civ: str, slug: str, d: dict, a: dict, pcts: dict) -> str:
    """The full static card (parchment ground, header, stage decorations minus
    the hero image itself, stats plate, verdict band) as a standalone HTML
    document. All dynamic text is `html.escape`d."""
    names = a["names"]
    unit_name = d.get("unit_name") or d.get("name") or slug.replace("_", " ").title()
    unit_name_esc = html.escape(unit_name)
    civ_esc = html.escape(civ)
    type_txt = (f"Unique {a['identity']}" if _is_unique(civ, slug) else a["identity"]).title()
    type_esc = html.escape(type_txt)

    stat_html = "".join(_stat_row_html(s) for s in _stat_rows_for(d, a, pcts))

    bonus_chips = "".join(
        f'<div style="background:rgba(92,107,60,.1);border:1px solid rgba(92,107,60,.55);'
        f'color:#48561f;font-weight:700;font-size:22px;padding:6px 14px;">'
        f'+{int(amt)} vs {html.escape(_chip_label(_display_name(names.get(cid, f"class {cid}"))))}</div>'
        for cid, amt in a["bonuses"][:4]
    )
    if not bonus_chips:
        bonus_chips = ('<div style="background:rgba(92,107,60,.1);border:1px dashed '
                       'rgba(92,107,60,.55);color:#48561f;font-weight:700;font-size:20px;'
                       'padding:6px 14px;">No bonus damage vs any class</div>')

    weak_names = [_chip_label(_display_name(names.get(cid, f"class {cid}")))
                 for cid in a["carried"][:6]]
    weakness_chips = "".join(
        f'<div style="background:rgba(138,69,52,.08);border:1px solid rgba(138,69,52,.5);'
        f'color:#6e3325;font-weight:700;font-size:22px;padding:6px 14px;">{html.escape(w)}</div>'
        for w in weak_names
    )
    if not weakness_chips:
        weakness_chips = ('<div style="background:rgba(138,69,52,.08);border:1px dashed '
                          'rgba(138,69,52,.5);color:#6e3325;font-weight:700;font-size:20px;'
                          'padding:6px 14px;">Carries no bonus-target armor classes</div>')

    verdict = html.escape(a["summary"])

    return f"""<!doctype html><html><head><meta charset="utf-8">
{_GOOGLE_FONTS_LINK}
<style>
body{{margin:0;background:#cbb28a;}}
@keyframes glowpulse{{0%,100%{{opacity:.4}}50%{{opacity:.65}}}}
</style></head><body>
<div style="position:relative;width:{CARD_W}px;height:{CARD_H}px;overflow:hidden;
  font-family:'EB Garamond',serif;
  background:radial-gradient(1400px 900px at 45% 40%, #ecdfc2 0%, #e2d1ac 55%, #cdb489 100%);
  color:#4a3220;">
  <div style="position:absolute;inset:0;background:
    radial-gradient(500px 380px at 12% 88%, rgba(122,90,42,.14), transparent 70%),
    radial-gradient(420px 320px at 90% 10%, rgba(122,90,42,.12), transparent 70%),
    radial-gradient(300px 260px at 70% 92%, rgba(122,90,42,.1), transparent 70%);"></div>
  <div style="position:absolute;inset:0;box-shadow:inset 0 0 220px rgba(94,66,30,.45);"></div>
  <div style="position:absolute;inset:26px;border:3px double rgba(94,66,30,.55);pointer-events:none;"></div>
  <div style="position:absolute;inset:38px;border:1px solid rgba(94,66,30,.3);pointer-events:none;"></div>
  <div style="position:absolute;top:18px;left:18px;width:16px;height:16px;background:#6b4a1e;transform:rotate(45deg);"></div>
  <div style="position:absolute;top:18px;left:1886px;width:16px;height:16px;background:#6b4a1e;transform:rotate(45deg);"></div>
  <div style="position:absolute;top:1046px;left:18px;width:16px;height:16px;background:#6b4a1e;transform:rotate(45deg);"></div>
  <div style="position:absolute;top:1046px;left:1886px;width:16px;height:16px;background:#6b4a1e;transform:rotate(45deg);"></div>

  <div style="position:absolute;left:100px;top:66px;display:flex;flex-direction:column;gap:12px;width:1000px;">
    <div style="display:flex;align-items:center;gap:16px;">
      <div style="border:1.5px solid #6b4a1e;color:#6b4a1e;font-family:'IM Fell English SC',serif;
        letter-spacing:5px;font-size:26px;padding:6px 24px;">Unit Spotlight</div>
      <div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(94,66,30,.55),transparent);"></div>
    </div>
    <div id="unit-title" style="font-family:'IM Fell English',serif;font-weight:400;font-size:92px;
      line-height:1;white-space:nowrap;color:#3d2a16;
      text-shadow:0 2px 0 rgba(236,223,194,.8), 0 3px 4px rgba(94,66,30,.35);">{unit_name_esc}</div>
    <div style="display:flex;gap:16px;align-items:center;font-family:'IM Fell English SC',serif;">
      <div style="color:#6b4a1e;letter-spacing:4px;font-size:26px;">{civ_esc}</div>
      <div style="width:8px;height:8px;background:#6b4a1e;transform:rotate(45deg);"></div>
      <div style="color:#5c4326;letter-spacing:4px;font-size:26px;">{type_esc}</div>
    </div>
  </div>
  <script>
    (function(){{
      var t = document.getElementById('unit-title');
      var maxWidth = 1000;
      var size = 92;
      while (t.scrollWidth > maxWidth && size > 34) {{
        size -= 2;
        t.style.fontSize = size + 'px';
      }}
    }})();
  </script>

  <div style="position:absolute;left:150px;top:360px;width:760px;height:600px;
    display:flex;align-items:flex-end;justify-content:center;">
    <div style="position:absolute;bottom:60px;left:50%;transform:translateX(-50%);width:500px;
      height:130px;border-radius:50%;background:radial-gradient(closest-side, rgba(122,90,42,.3),
      transparent 70%);animation:glowpulse 3.5s ease-in-out infinite;"></div>
    <div style="position:absolute;bottom:110px;left:50%;transform:translateX(-50%) rotate(45deg);
      width:350px;height:350px;border:1.5px solid rgba(94,66,30,.4);"></div>
    <div style="position:absolute;bottom:130px;left:50%;transform:translateX(-50%) rotate(45deg);
      width:295px;height:295px;border:1px solid rgba(94,66,30,.25);"></div>
  </div>

  <div style="position:absolute;right:80px;top:72px;width:640px;background:rgba(236,223,194,.75);
    border:2px solid #6b4a1e;box-shadow:0 0 0 5px rgba(107,74,30,.12), 0 18px 40px rgba(94,66,30,.3);
    padding:28px 38px 26px;">
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:18px;">
      <div style="width:11px;height:11px;background:#6b4a1e;transform:rotate(45deg);"></div>
      <div style="font-family:'IM Fell English SC',serif;font-size:34px;letter-spacing:3px;
        color:#4a3220;">Core Stats</div>
      <div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(94,66,30,.55),transparent);"></div>
    </div>
    {stat_html}
    <div style="display:flex;align-items:center;gap:14px;margin:20px 0 12px;">
      <div style="width:11px;height:11px;background:#5c6b3c;transform:rotate(45deg);"></div>
      <div style="font-family:'IM Fell English SC',serif;font-size:30px;letter-spacing:3px;
        color:#51602f;">Bonus Damage</div>
      <div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(92,107,60,.6),transparent);"></div>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:10px;">{bonus_chips}</div>
    <div style="display:flex;align-items:center;gap:14px;margin:20px 0 12px;">
      <div style="width:11px;height:11px;background:#8a4534;transform:rotate(45deg);"></div>
      <div style="font-family:'IM Fell English SC',serif;font-size:30px;letter-spacing:3px;
        color:#7a3a2a;">Armor Categories</div>
      <div style="height:1px;flex:1;background:linear-gradient(90deg,rgba(138,69,52,.6),transparent);"></div>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:10px;">{weakness_chips}</div>
  </div>

  <div style="position:absolute;left:60px;right:60px;bottom:56px;border-top:1.5px solid rgba(94,66,30,.5);
    border-bottom:1.5px solid rgba(94,66,30,.5);padding:14px 30px;display:flex;align-items:center;gap:24px;">
    <div style="font-family:'IM Fell English SC',serif;font-size:28px;letter-spacing:3px;
      color:#5c4326;white-space:nowrap;">The Verdict</div>
    <div style="width:9px;height:9px;background:#6b4a1e;transform:rotate(45deg);flex:none;"></div>
    <div style="font-size:29px;font-weight:500;font-style:italic;color:#4a3220;">{verdict}</div>
  </div>
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# Hero compositing (Pillow, onto the Chrome screenshot)
# ---------------------------------------------------------------------------

def _hero_with_shadow(im: Image.Image, *, offset=(0, 18), blur: int = 20,
                      tint=(94, 66, 30), shadow_opacity: int = 130,
                      sepia_opacity: float = 0.15) -> tuple[Image.Image, int]:
    """Approximates the mockup's `filter: drop-shadow(0 24px 24px
    rgba(94,66,30,.45)) sepia(.15)` on the composited hero: a Gaussian-blurred,
    tinted copy of the hero's own alpha silhouette sits underneath (the drop
    shadow), plus a low-opacity warm-brown wash masked by that same alpha over
    the hero itself (the sepia). This is a deliberate visual approximation, not
    a literal filter port — Pillow has no sepia()/drop-shadow() op, and a
    proper sepia color-matrix looked worse than a simple alpha tint on these
    sprites' hard cel-shaded edges. Returns (padded_image, pad); `pad` is how
    much the canvas grew on each side so callers can shift placement to match."""
    pad = blur * 2 + max(abs(offset[0]), abs(offset[1]))
    canvas = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))

    alpha = im.split()[-1]
    shadow = Image.new("RGBA", im.size, (*tint, 0))
    shadow.putalpha(alpha.point(lambda a: int(a * shadow_opacity / 255)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(shadow, (pad + offset[0], pad + offset[1]))

    tint_layer = Image.new("RGBA", im.size, (*tint, 0))
    tint_layer.putalpha(alpha.point(lambda a: int(a * sepia_opacity)))
    tinted = Image.alpha_composite(im, tint_layer)
    canvas.alpha_composite(tinted, (pad, pad))
    return canvas, pad


def _composite_hero(base: Image.Image, hero: Image.Image, box=HERO_BOX, *,
                    max_h: int = HERO_MAX_H, bottom_margin: int = HERO_BOTTOM_MARGIN) -> None:
    """Fits `hero` into `box` (width-capped, height-capped at `max_h` — mirrors
    the mockup's img height:520px) and BOTTOM-anchors it `bottom_margin` px
    above the box's bottom edge (mirrors marginBottom:70px), horizontally
    centred — so the unit visually "stands" on the glow ellipse/diamond rings
    instead of floating centred in the box."""
    bx, by, bw, bh = box
    spr = _fit_img(hero, (bw, max_h))
    shadowed, pad = _hero_with_shadow(spr)
    x = bx + (bw - spr.width) // 2 - pad
    y = by + bh - bottom_margin - spr.height - pad
    base.alpha_composite(shadowed, (x, y))


def _render_card_base(civ: str, slug: str, d: dict, a: dict, pcts: dict) -> Image.Image:
    """Screenshot the static HTML card (parchment ground + stats + banner, NO
    hero image) via headless Chrome, at native 1920x1080 (scale=1 — a
    full-bleed opaque card, no autocrop needed). `--virtual-time-budget` gives
    the Google Fonts webfonts (IM Fell English / IM Fell English SC / EB
    Garamond) time to load before the shot; if the network is unavailable,
    every font-family stack in `_card_html` ends in the generic `serif`
    fallback (matching the mockup's own CSS), so no separate fallback path is
    needed — Chrome just renders its default serif instead."""
    html_doc = _card_html(civ, slug, d, a, pcts)
    with tempfile.TemporaryDirectory(prefix="intro_card_base_") as td:
        out_png = Path(td) / "base.png"
        _screenshot(html_doc, out_png, CARD_W, CARD_H, scale=1,
                   extra_args=["--virtual-time-budget=10000"])
        return Image.open(out_png).convert("RGBA")


def make_unit_intro_card(civ: str, slug: str, *,
                         json_path: Path = COMBAT_DICTS_JSON) -> Image.Image:
    """Static 1920x1080 intro card. Hero preference: a mid-swing frame of the
    unit's attack.gif, else the best still (sprite_full -> sprite tree -> icon)."""
    d = load_combat_dict(civ, slug, json_path)
    a = analyze_unit(d)
    pcts, _broad, _n = stat_percentiles(civ, slug, d)
    img = _render_card_base(civ, slug, d, a, pcts)

    gif = _hero_gif(slug)
    if gif is not None:
        # frame 0 is the idle/ready pose — the cleanest single frame for a still
        _composite_hero(img, _gif_frames(gif)[0][0])
    else:
        still = _hero_still(slug, d.get("unit_name") or "")
        if still is not None:
            _composite_hero(img, Image.open(still).convert("RGBA"))
    return img


def _encode_gif_loop_video(base: Image.Image, frames: list[tuple[Image.Image, int]],
                           box, out_mp4: Path, *, duration_s: float, fps: int,
                           max_h: int, bottom_margin: int) -> Path:
    """Shared animated-card renderer: composites `frames` (from `_gif_frames`,
    looped at their native per-frame timing) onto `box` of a copy of `base` for
    each of `duration_s * fps` output frames — the screenshotted HTML base is
    reused unchanged frame-to-frame, only the hero moves — then PNG-sequence
    -encodes via ffmpeg to 1920x1080 H.264. Used by both `make_unit_intro_video`
    and `make_outro_thanks_video` so the two animated cards share one encode
    path. If `frames` is empty, `base` (already composited with a static hero
    by the caller, if any) is simply held for the full duration."""
    out_mp4 = Path(out_mp4)
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found (PATH or WinGet install)")

    # gif frame lookup by cumulative native durations, looped
    starts, t_acc = [], 0
    for _, dur in frames:
        starts.append(t_acc)
        t_acc += dur
    loop_ms = t_acc or 1

    def frame_at(ms: float) -> Image.Image:
        m = ms % loop_ms
        idx = 0
        for i, s in enumerate(starts):
            if s <= m:
                idx = i
            else:
                break
        return frames[idx][0]

    n_out = max(1, int(round(duration_s * fps)))
    with tempfile.TemporaryDirectory(prefix="gif_loop_card_") as td:
        for i in range(n_out):
            frame = base.copy()
            if frames:
                _composite_hero(frame, frame_at(i * 1000.0 / fps), box,
                                max_h=max_h, bottom_margin=bottom_margin)
            frame.convert("RGB").save(Path(td) / f"f{i:04d}.png")
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [ffmpeg, "-y", "-framerate", str(fps), "-i", str(Path(td) / "f%04d.png"),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
             "-movflags", "+faststart", str(out_mp4)],
            check=True, capture_output=True)
    return out_mp4


def make_unit_intro_video(civ: str, slug: str, out_mp4, *, duration_s: float = 3.0,
                          fps: int = 30,
                          json_path: Path = COMBAT_DICTS_JSON) -> Path:
    """Animated intro card: the unit's attack.gif loops (at its native frame
    timing) as the hero over the static card; everything else is unchanged
    frame-to-frame — the HTML base is screenshotted ONCE and reused for every
    output frame. Encoded 1920x1080 H.264 via ffmpeg. If the unit has no
    attack.gif the output is a still video of the static card."""
    d = load_combat_dict(civ, slug, json_path)
    a = analyze_unit(d)
    pcts, _broad, _n = stat_percentiles(civ, slug, d)
    base = _render_card_base(civ, slug, d, a, pcts)

    gif = _hero_gif(slug)
    frames = _gif_frames(gif) if gif is not None else []
    if not frames:                       # static fallback
        still = _hero_still(slug, d.get("unit_name") or "")
        if still is not None:
            _composite_hero(base, Image.open(still).convert("RGBA"))

    return _encode_gif_loop_video(base, frames, HERO_BOX, out_mp4, duration_s=duration_s,
                                  fps=fps, max_h=HERO_MAX_H, bottom_margin=HERO_BOTTOM_MARGIN)


# ---------------------------------------------------------------------------
# Outro "thank you" card — the FINAL segment of the long-form video. Same
# parchment page chrome as `overlay.category_card` (radial parchment ground,
# corner stains, vignette, double+hairline border, four corner diamonds, IM
# Fell English SC / EB Garamond with the Georgia offline fallback — reused
# directly via `category_card._font_stack` / `_page_open` rather than
# re-implemented here), a CENTERED unit stage (glow ellipse + two diamond
# rings, `OUTRO_STAGE_BOX` above — bigger than the intro's since it doesn't
# share the frame with a title/stats plate), and a bottom banner: an italic
# site-plug line + a large letter-spaced "Thank You For Watching". No
# unit-specific text anywhere — only the hero image (composited by Pillow,
# same as the intro) is civ/slug-specific, so the wording stays generic.
# ---------------------------------------------------------------------------

def build_outro_thanks_html(civ: str, slug: str) -> str:
    """Static (no-hero) base HTML for the closing thank-you card. `civ`/`slug`
    are accepted for interface parity with the rest of this module's card
    builders (and so callers can extend this later) but do not affect the
    markup — the card's text is deliberately generic."""
    from overlay.category_card import _font_stack, _page_open, _PAGE_CLOSE

    fonts = _font_stack()
    bx, by, bw, bh = OUTRO_STAGE_BOX

    stage = f"""
  <style>@keyframes glowpulse{{0%,100%{{opacity:.4}}50%{{opacity:.65}}}}</style>
  <div style="position:absolute;left:{bx}px;top:{by}px;width:{bw}px;height:{bh}px;
    display:flex;align-items:flex-end;justify-content:center;">
    <div style="position:absolute;bottom:70px;left:50%;transform:translateX(-50%);width:620px;
      height:150px;border-radius:50%;background:radial-gradient(closest-side, rgba(122,90,42,.3),
      transparent 70%);animation:glowpulse 3.5s ease-in-out infinite;"></div>
    <div style="position:absolute;bottom:125px;left:50%;transform:translateX(-50%) rotate(45deg);
      width:420px;height:420px;border:1.5px solid rgba(94,66,30,.4);"></div>
    <div style="position:absolute;bottom:150px;left:50%;transform:translateX(-50%) rotate(45deg);
      width:355px;height:355px;border:1px solid rgba(94,66,30,.25);"></div>
  </div>
"""
    banner = f"""
  <div style="position:absolute;left:0;right:0;bottom:90px;display:flex;flex-direction:column;
    align-items:center;gap:22px;padding:0 260px;text-align:center;">
    <div style="font-size:30px;font-style:italic;color:#5c4326;max-width:1300px;line-height:1.45;">
      Visit AOE2MATCHUP.COM to test your own version of the matchups — any number of units,
      simulate the results, and view additional details.</div>
    <div style="display:flex;align-items:center;gap:18px;width:640px;">
      <div style="height:1.5px;flex:1;background:linear-gradient(90deg,transparent,rgba(94,66,30,.6));"></div>
      <div style="width:10px;height:10px;background:#6b4a1e;transform:rotate(45deg);flex:none;"></div>
      <div style="height:1.5px;flex:1;background:linear-gradient(90deg,rgba(94,66,30,.6),transparent);"></div>
    </div>
    <div style="font-family:{fonts['title_sc']};font-size:64px;letter-spacing:10px;
      color:#3d2a16;text-shadow:0 2px 0 rgba(236,223,194,.8), 0 3px 4px rgba(94,66,30,.35);">
      Thank You For Watching</div>
  </div>
"""
    return _page_open(fonts, "Outro Thanks") + stage + banner + _PAGE_CLOSE


def _render_outro_base(civ: str, slug: str) -> Image.Image:
    """Screenshot the static outro HTML (parchment chrome + stage rings +
    banner, NO hero image) via headless Chrome, at native 1920x1080 — mirrors
    `_render_card_base` above."""
    html_doc = build_outro_thanks_html(civ, slug)
    with tempfile.TemporaryDirectory(prefix="outro_thanks_base_") as td:
        out_png = Path(td) / "base.png"
        _screenshot(html_doc, out_png, CARD_W, CARD_H, scale=1,
                   extra_args=["--virtual-time-budget=10000"])
        return Image.open(out_png).convert("RGBA")


def make_outro_thanks_video(civ: str, slug: str, out_mp4, *, duration_s: float = 6.0,
                            fps: int = 30) -> Path:
    """Animated closing 'thank you' card — the new FINAL segment of the
    long-form video, after the coin-flip close. Same machinery as
    `make_unit_intro_video`: a Chrome-rendered static base (screenshotted once)
    + `_gif_frames` per-frame hero compositing (native GIF timing, looped) +
    `_encode_gif_loop_video`'s shared ffmpeg encode. Hero resolution goes
    through the same `_hero_gif` 3-tier lookup as the intro (in-worktree media
    tree, else the main checkout's — e.g. Muisca/elite_temple_guard_muisca's
    attack.gif). Falls back to a still video (via `_hero_still`) if the unit
    has no attack.gif, and to a static hold of the bare card if it has neither."""
    base = _render_outro_base(civ, slug)

    gif = _hero_gif(slug)
    frames = _gif_frames(gif) if gif is not None else []
    if not frames:                       # static fallback
        still = _hero_still(slug)
        if still is not None:
            _composite_hero(base, Image.open(still).convert("RGBA"), OUTRO_STAGE_BOX,
                            max_h=OUTRO_HERO_MAX_H, bottom_margin=OUTRO_HERO_BOTTOM_MARGIN)

    return _encode_gif_loop_video(base, frames, OUTRO_STAGE_BOX, out_mp4, duration_s=duration_s,
                                  fps=fps, max_h=OUTRO_HERO_MAX_H,
                                  bottom_margin=OUTRO_HERO_BOTTOM_MARGIN)


def main(argv: list[str]) -> None:
    civ = argv[1] if len(argv) > 1 else "Muisca"
    slug = argv[2] if len(argv) > 2 else "elite_temple_guard_muisca"
    out = Path(argv[3]) if len(argv) > 3 else (
        Path(__file__).parent / "samples" / f"_intro_card_{slug}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".mp4":
        make_unit_intro_video(civ, slug, out)
    else:
        make_unit_intro_card(civ, slug).convert("RGB").save(out)
    print("WROTE", out)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # apps/video/
    main(sys.argv)
