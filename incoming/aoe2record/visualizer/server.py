#!/usr/bin/env python3
"""
Flask server for AoE2 Replay Visualizer.
Handles file uploads and processes replay files.
"""

import csv
import io
import json
import os
import sys
import tempfile
import zipfile
from collections import defaultdict, Counter
from datetime import datetime

import mgz
import mgz.model
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# AoE2 Companion API settings
AOE2_COMPANION_API = "https://data.aoe2companion.com/api"
AOE2_COMPANION_HEADERS = {"User-Agent": "https://github.com/aoe2record-visualizer"}
REPLAY_DOWNLOAD_URL = "https://aoe.ms/replay"
# Cache downloaded replays so the same match isn't re-fetched from aoe.ms on
# every load (aoe.ms rate-limits per IP and returns 429 under repeated pulls).
REPLAY_CACHE_DIR = os.path.join(tempfile.gettempdir(), "aoe2_replay_cache")

# Players list file
PLAYERS_CSV_PATH = os.path.join(os.path.dirname(__file__), "players.csv")

app = Flask(__name__, static_folder="public", static_url_path="")


def load_players_from_csv():
    """Load player list from CSV file."""
    players = []
    try:
        with open(PLAYERS_CSV_PATH, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                players.append(
                    {"name": row["name"], "profileId": int(row["profileId"])}
                )
    except FileNotFoundError:
        app.logger.warning(f"Players CSV not found: {PLAYERS_CSV_PATH}")
    return players


CORS(app)

# AoE2 standard player colors
PLAYER_COLORS = {
    0: {"name": "Blue", "hex": "#0042FF"},
    1: {"name": "Red", "hex": "#FF0000"},
    2: {"name": "Green", "hex": "#00FF00"},
    3: {"name": "Yellow", "hex": "#FFFF00"},
    4: {"name": "Cyan", "hex": "#00FFFF"},
    5: {"name": "Purple", "hex": "#FF00FF"},
    6: {"name": "Grey", "hex": "#404040"},
    7: {"name": "Orange", "hex": "#FFA500"},
}

# A unit with no further action for this long is assumed destroyed (it fades
# out). Mainly governs siege (trebuchets / bombard cannons), which are kept
# alive between commands so they can keep bombarding; other military units are
# hidden almost immediately after their last command.
DEATH_THRESHOLD = 3 * 60

# Unit type classification
INFANTRY_UNITS = {
    "militia",
    "manatarms",
    "longswordsman",
    "twohanded swordsman",
    "champion",
    "spearman",
    "pikeman",
    "halberdier",
    "eaglescout",
    "eaglewarrior",
    "eliteeaglewarrior",
    "condottiero",
    "kamayuk",
    "elitekamayuk",
    "shotelwarrior",
    "eliteshotelwarrior",
    "gbeto",
    "elitegbeto",
    "supplywaggon",
    "huskarl",
    "elitehuskarl",
    "teutonic knight",
    "eliteteutonic knight",
    "berserk",
    "eliteberserk",
    "jaguar warrior",
    "elitejaguar warrior",
    "woad raider",
    "elitewoad raider",
    "throwing axeman",
    "elitethrowing axeman",
    "samurai",
    "elitesamurai",
    "urumi swordsman",
    "eliteurumi swordsman",
    "obuch",
    "eliteobuch",
    "serjeant",
    "eliteserjeant",
    "flemish militia",
    "warrior priest",
}

CAVALRY_UNITS = {
    "scoutcavalry",
    "lightcavalry",
    "hussar",
    "wingedhussar",
    "knight",
    "cavalier",
    "paladin",
    "camelrider",
    "heavycamelrider",
    "imperialcamelrider",
    "battleelephant",
    "elitebattleelephant",
    "steppelancer",
    "elitesteppelancer",
    "cataphract",
    "elitecataphract",
    "boyar",
    "eliteboyar",
    "konnik",
    "elitekonnik",
    "leitis",
    "eliteleitis",
    "keshik",
    "elitekeshik",
    "magyar huszar",
    "elitemagyar huszar",
    "tarkan",
    "elitetarkan",
    "war elephant",
    "elitewar elephant",
    "mameluke",
    "elitemameluke",
    "shrivamsha rider",
    "eliteshrivamsha rider",
    "coustillier",
    "elitecoustillier",
    "monaspa",
    "elitemonaspa",
    "savar",
}

ARCHER_UNITS = {
    "archer",
    "crossbowman",
    "arbalester",
    "skirmisher",
    "eliteskirmisher",
    "imperialskirmisher",
    "cavalryarcher",
    "heavycavalryarcher",
    "handcannoneer",
    "slinger",
    "longbowman",
    "elitelongbowman",
    "chukonou",
    "elitechukonou",
    "mangudai",
    "elitemangudai",
    "warwagon",
    "elitewarwagon",
    "plumedarchery",
    "eliteplumedarchery",
    "genitour",
    "elitegenitour",
    "camel archer",
    "elitecamel archer",
    "genoese crossbowman",
    "elitegenoese crossbowman",
    "elephant archer",
    "eliteelephant archer",
    "rattan archer",
    "eliterattan archer",
    "kipchak",
    "elitekipchak",
    "arambai",
    "elitearambai",
    "janissary",
    "elitejanissary",
    "conquistador",
    "eliteconquistador",
    "rattaarcher",
    "eliterattaarcher",
    "chakram thrower",
    "elitechakram thrower",
    "thirisadai",
}

SIEGE_UNITS = {
    "batteringram",
    "cappedram",
    "siegeram",
    "mangonel",
    "onager",
    "siegeonager",
    "scorpion",
    "heavyscorpion",
    "bombardcannon",
    "siegetower",
    "trebuchet",
    "organ gun",
    "eliteorgan gun",
    "houfnice",
}

MONK_UNITS = {
    "monk",
    "missionary",
    "imam",
    "warrior priest",
}

SHIP_UNITS = {
    "galley",
    "war galley",
    "galleon",
    "fire galley",
    "fire ship",
    "fast fire ship",
    "demolition raft",
    "demolition ship",
    "heavy demolition ship",
    "cannon galleon",
    "elite cannon galleon",
    "longboat",
    "elitelongboat",
    "turtle ship",
    "eliteturtle ship",
    "caravel",
    "elitecaravel",
    "dromon",
    "transport ship",
    "fishing ship",
    "trade cog",
}


def classify_unit_type(unit_name):
    """Classify a unit into a category based on its name."""
    name_lower = unit_name.lower().replace("_", " ").replace("-", " ")

    # Check each category
    for infantry in INFANTRY_UNITS:
        if infantry in name_lower:
            return "infantry"

    for cavalry in CAVALRY_UNITS:
        if cavalry in name_lower:
            return "cavalry"

    for archer in ARCHER_UNITS:
        if archer in name_lower:
            return "archer"

    for siege in SIEGE_UNITS:
        if siege in name_lower:
            return "siege"

    for monk in MONK_UNITS:
        if monk in name_lower:
            return "monk"

    for ship in SHIP_UNITS:
        if ship in name_lower:
            return "ship"

    # Special cases
    if "villager" in name_lower:
        return "villager"
    if "scout" in name_lower:
        return "cavalry"  # Scout cavalry
    if "king" in name_lower:
        return "king"

    return "military"  # Default


def load_object_names():
    """Load object ID to name mappings."""
    try:
        import aocref

        aocref_path = os.path.dirname(aocref.__file__)
        dataset_file = os.path.join(aocref_path, "data", "datasets", "100.json")
        with open(dataset_file, "r") as f:
            data = json.load(f)
            return data.get("objects", {})
    except:
        return {}


# ---- Starting-map terrain + GAIA objects (visualizer map backdrop) ----

def _load_terrain_names(dataset_id):
    """terrain id -> name, from aocref's dataset table (best-effort)."""
    try:
        import aocref
        path = os.path.join(
            os.path.dirname(aocref.__file__), "data", "datasets", f"{dataset_id}.json"
        )
        with open(path, encoding="utf-8") as f:
            table = json.load(f).get("terrain", {})
        return {int(k): (v.get("name") if isinstance(v, dict) else v) for k, v in table.items()}
    except Exception:
        return {}


def _terrain_hex(name):
    """Map a terrain name to a backdrop color (keyword match, first wins)."""
    n = (name or "").lower()

    def has(*ws):
        return any(w in n for w in ws)

    if has("ice"):
        return "#d7e6f0"
    if has("snow"):
        return "#e8eef2"
    # Only true tree-forests here; ground covers (underbrush, leaves, bush,
    # reeds, moorland) are NOT forest and fall through to grass. Real forests
    # are also caught by the tree-density check in _extract_terrain.
    if has("forest", "jungle", "bamboo", "rainforest", "acacia", "baobab",
           "dragon", "dead forest", "mangrove forest", "taiga"):
        return "#2f4d24"
    if has("water") and has("deep", "ocean"):
        return "#1f4e79"
    if has("water", "azure"):
        return "#2e6699"
    if has("shallow", "bridge"):
        return "#4a86b8"
    if has("beach", "sand"):
        return "#d8c48a"
    if has("road", "foundation"):
        return "#9a9080"
    if has("desert", "quicksand", "savannah", "cracked"):
        return "#cdb87a"
    if has("dry grass", "bogland"):
        return "#9aa860"
    if has("dirt", "rock", "gravel"):
        return "#8c7d57"
    if has("farm"):
        return "#9c7b4a"
    if has("black"):
        return "#111111"
    return "#5c8a3c"  # default: grass (lighter, clearly distinct from forest)


def _is_tree(o):
    """Is this GAIA object a tree? DE leaves the bulk forest trees unnamed
    (e.g. object 1717) as class-10 with no name; named class-10 decorations
    (Grass, Plant) are excluded since they have a name."""
    n = (getattr(o, "name", None) or "").lower()
    if any(k in n for k in ("tree", "snag", "stump")):
        return True
    if not getattr(o, "name", None) and getattr(o, "class_id", None) == 10:
        return True
    return False


def _extract_terrain(match):
    """Flat terrain-id grid + palette (id -> hex). Forest terrain is detected by
    tree density (one tree per tile) so it's colored distinctly even when aocref
    has no name for the id (e.g. DE pine-forest terrain 110)."""
    import collections

    mp = match.map
    dim = mp.dimension
    grid = [0] * (dim * dim)
    terr_at = {}
    for t in mp.tiles:
        grid[t.position.y * dim + t.position.x] = t.terrain
        terr_at[(t.position.x, t.position.y)] = t.terrain

    tile_count = collections.Counter(terr_at.values())
    tree_on = collections.Counter()
    for o in getattr(match, "gaia", None) or []:
        if _is_tree(o):
            tid = terr_at.get((int(o.position.x), int(o.position.y)))
            if tid is not None:
                tree_on[tid] += 1
    # A terrain id is forest if (nearly) every tile of it carries a tree.
    forest_ids = {tid for tid, n in tile_count.items() if n and tree_on[tid] / n >= 0.4}

    names = _load_terrain_names(getattr(match, "dataset_id", 100))
    palette = {}
    for tid in tile_count:
        palette[str(tid)] = "#2f4d24" if tid in forest_ids else _terrain_hex(names.get(tid, ""))
    return {"dimension": dim, "ids": grid, "palette": palette}


# (category, keywords) — first match wins; everything else is decoration and skipped.
_OBJ_CATEGORIES = (
    ("relic", ("relic",)),
    ("gold", ("gold",)),
    ("stone", ("stone",)),
    ("boar", ("boar", "rhino", "elephant", "javelina")),
    ("hunt", ("deer", "ibex", "goose", "gazelle", "zebra", "ostrich", "stag", "crocodile", "emu", "elk")),
    ("fish", ("fish", "marlin", "dolphin", "turtle", "salmon", "snapper", "tuna", "perch")),
    ("sheep", ("sheep", "turkey", "llama", "goat", "cow", "buffalo", "pig")),
    ("forage", ("forage", "berry", "fruit")),
    ("tree", ("tree", "snag", "stump")),
)

# Huntable / herdable GAIA animals are drawn dynamically (so they can vanish the
# moment a player takes control), not baked into the static backdrop.
_ANIMAL_DOT_CATS = {"boar", "hunt", "sheep"}

# Map an object name to one of the three icon buckets the frontend draws.
_ANIMAL_ICON_CATS = (
    ("boar", ("boar", "rhino", "elephant", "javelina")),
    ("deer", ("deer", "ibex", "goose", "gazelle", "zebra", "ostrich", "stag", "crocodile", "emu", "elk")),
    ("sheep", ("sheep", "turkey", "llama", "goat", "cow", "buffalo", "pig")),
)


def _classify_animal(name):
    n = (name or "").lower()
    if not n:
        return None
    return next((c for c, kws in _ANIMAL_ICON_CATS if any(k in n for k in kws)), None)


def _extract_map_objects(match):
    """Resource/tree/relic GAIA objects at game start: [{c, x, y}]."""
    out = []
    for g in getattr(match, "gaia", None) or []:
        n = (getattr(g, "name", None) or "").lower()
        if not n:
            continue
        cat = next((c for c, kws in _OBJ_CATEGORIES if any(k in n for k in kws)), None)
        if cat is None or cat == "tree" or cat in _ANIMAL_DOT_CATS:
            continue  # forests come from terrain; animals are drawn dynamically
        p = getattr(g, "position", None)
        if p is None:
            continue
        out.append({"c": cat, "x": round(p.x, 1), "y": round(p.y, 1)})
    return out


def _extract_animals(match):
    """Huntable/herdable GAIA animals present at game start, each tagged with the
    time it first comes under a player's control (gone_at). Sheep get commanded
    (their id shows up as an action actor); boar/deer get attacked (their id is
    the action target). After gone_at the frontend stops drawing them, matching
    the game where the animal is converted/killed and no longer neutral."""
    animals = []
    by_id = {}
    for g in getattr(match, "gaia", None) or []:
        cat = _classify_animal(getattr(g, "name", None))
        if cat is None:
            continue
        p = getattr(g, "position", None)
        if p is None:
            continue
        a = {"c": cat, "x": round(p.x, 1), "y": round(p.y, 1), "gone_at": None}
        animals.append(a)
        iid = getattr(g, "instance_id", None)
        if iid is not None:
            by_id[iid] = a

    if by_id:
        def _touch(iid, ts):
            a = by_id.get(iid)
            if a is not None and (a["gone_at"] is None or ts < a["gone_at"]):
                a["gone_at"] = ts

        def _ref_ids(payload):
            # Any integer in the action payload that references an object id:
            # actor ids (object_ids), an attack/interaction target (target_id),
            # etc. Animal instance ids are large, so small fields (coords, tech
            # ids) won't collide — and we only ever match against known animals.
            for v in payload.values():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int):
                    yield v
                elif isinstance(v, (list, tuple, set)):
                    for x in v:
                        if isinstance(x, int) and not isinstance(x, bool):
                            yield x

        for action in match.actions:
            if not getattr(action, "player", None):
                continue  # only a player taking action removes the animal
            try:
                ts = action.timestamp.total_seconds()
            except Exception:
                continue
            for iid in _ref_ids(action.payload or {}):
                _touch(iid, ts)

    return animals


# ---- Building interactions (re-brighten a building when it's used) ----
# Production/research actions identify a building only by an internal
# instance_id and carry no map position. Instance_ids are assigned in creation
# order, so within each building CLASS the k-th building a player builds gets
# the k-th id. We infer each interacting building's class from what it
# trains/researches, then pair it (by id order) to that player's BUILD orders
# of the same class (by time) to recover its position. Buildings the player
# never produces/researches from are simply never re-brightened.


def _building_class(name):
    """Map a BUILD building name to a coarse class (None = non-interactive)."""
    n = (name or "").lower()
    table = [
        ("town cent", "tc"), ("barrack", "barracks"), ("archery", "range"),
        ("stable", "stable"), ("siege", "siege"), ("dock", "dock"),
        ("harbor", "dock"), ("monaster", "monastery"), ("castle", "castle"),
        ("krepost", "castle"), ("donjon", "castle"), ("blacksmith", "blacksmith"),
        ("market", "market"), ("univers", "university"),
        ("mining camp", "miningcamp"), ("lumber camp", "lumbercamp"),
        ("mill", "mill"), ("wonder", "wonder"),
    ]
    for kw, c in table:
        if kw in n:
            return c
    return None  # house / farm / wall / tower / gate / outpost: never "used"


def _unit_class(u):
    """Class of the building that trains unit `u`."""
    n = (u or "").lower()
    if "fishing ship" in n:
        return "dock"
    if "villager" in n:
        return "tc"
    if "elephant archer" in n:
        return "range"
    if any(k in n for k in ["archer", "crossbow", "arbalest", "skirmisher",
                            "slinger", "hand cannon", "genitour"]):
        return "range"
    if any(k in n for k in ["militia", "man-at-arms", "man at arms", "spearman",
                            "pikeman", "halberdier", "eagle", "champion",
                            "swordsman", "two-handed", "legionary", "condottiero"]):
        return "barracks"
    if any(k in n for k in ["scout", "knight", "cavalier", "paladin", "camel",
                            "lancer", "hussar", "light cav", "battle elephant",
                            "steppe", "shrivamsha", "cavalry"]):
        return "stable"
    if any(k in n for k in ["mangonel", "onager", "scorpion", " ram",
                            "bombard cannon", "siege tower", "siege ram",
                            "battering"]):
        return "siege"
    if any(k in n for k in ["monk", "missionary"]):
        return "monastery"
    if any(k in n for k in ["galley", "fire ship", "demolition", "transport",
                            "cannon galleon", "caravel", "longboat",
                            "turtle ship", "dromon", "thirisadai"]):
        return "dock"
    if any(k in n for k in ["trebuchet", "petard"]):
        return "castle"
    return "castle"  # unmatched trainable: almost always a Castle unique unit


def _tech_class(t):
    """Class of the building that researches tech `t` (None = unknown)."""
    n = (t or "").lower()
    table = [
        (["feudal age", "castle age", "imperial age", "loom", "wheelbarrow",
          "hand cart", "town watch", "town patrol"], "tc"),
        (["forging", "iron casting", "blast furnace", "scale mail", "chain mail",
          "plate mail", "scale barding", "chain barding", "plate barding",
          "fletching", "bodkin", "bracer", "padded archer", "leather archer",
          "ring archer"], "blacksmith"),
        (["masonry", "architecture", "ballistics", "chemistry", "bombard tower",
          "siege engineers", "treadmill", "murder holes", "heated shot",
          "arrowslits", "fortified wall", "guard tower", "keep ", "conscription",
          "spies"], "university"),
        (["caravan", "guilds", "coinage", "banking"], "market"),
        (["horse collar", "heavy plow", "crop rotation"], "mill"),
        (["gold mining", "stone mining", "gold shaft", "stone shaft"], "miningcamp"),
        (["double-bit", "double bit", "bow saw", "two-man", "two man saw"], "lumbercamp"),
        (["redemption", "atonement", "herbal", "heresy", "sanctity", "fervor",
          "faith", "illumination", "block printing", "theocracy"], "monastery"),
        (["bloodlines", "husbandry"], "stable"),
        (["thumb ring", "parthian"], "range"),
        (["tracking", "squires", "arson", "supplies", "gambeson"], "barracks"),
        (["capped ram", "siege ram", "heavy scorpion", "siege onager"], "siege"),
        (["gillnets", "careening", "dry dock", "shipwright"], "dock"),
    ]
    for kws, c in table:
        if any(k in n for k in kws):
            return c
    return None


def _act_type(a):
    return str(a.type).replace("Action.", "")


def _analyze_buildings(match):
    """Reconstruct building positions and produce both interaction and deletion
    events. Returns (interactions, deletions), each a list of
    {x, y, player, time}.

    Production/research actions reference a building only by instance_id (no
    position), and DELETE actions likewise. Instance_ids are assigned in
    creation order, so within each building CLASS the k-th building a player
    builds gets the k-th id. We:

      1. Find abandoned foundations first: a DELETE of an id that never produced
         is matched to that player's most recent prior un-claimed BUILD (the
         place-then-relocate / cancel pattern). These build slots are removed
         from the map and excluded from production pairing.
      2. Pair each producing/researching id (by id order) to that player's
         surviving BUILD orders of its inferred class (by time) -> position.
      3. Interactions = any action whose object_ids names a located building.
         Deletions = abandoned foundations + razes of located buildings.
    """
    from collections import Counter, defaultdict

    act_type = _act_type

    # All BUILDs with a position, per player (time-sorted, claimable), and the
    # interactive-class subset grouped by (player, class) for production pairing.
    all_builds = defaultdict(list)  # player -> [[time, x, y, claimed]]
    for a in match.actions:
        if not a.player or act_type(a) != "BUILD":
            continue
        pos = getattr(a, "position", None)
        if pos is None:
            continue
        all_builds[a.player.name].append(
            [a.timestamp.total_seconds(), round(pos.x), round(pos.y), False]
        )
    for p in all_builds:
        all_builds[p].sort()

    # Starting buildings (mainly the Town Center) anchored by instance_id.
    anchor = {}  # iid -> (player, x, y)
    for pl in match.players:
        for o in (pl.objects or []):
            if _building_class(o.name):
                pos = getattr(o, "position", None)
                if pos:
                    anchor[o.instance_id] = (pl.name, round(pos.x), round(pos.y))

    # Per producing/researching iid: owner, what it makes, first-seen time.
    prod = {}
    for a in match.actions:
        if not a.player:
            continue
        t = act_type(a)
        if t not in ("DE_QUEUE", "RESEARCH"):
            continue
        ts = a.timestamp.total_seconds()
        payload = a.payload or {}
        for oid in payload.get("object_ids", []):
            d = prod.setdefault(
                oid, {"player": a.player.name, "units": Counter(),
                      "techs": Counter(), "first": ts}
            )
            d["first"] = min(d["first"], ts)
            if t == "DE_QUEUE":
                d["units"][payload.get("unit")] += 1
            else:
                d["techs"][payload.get("technology")] += 1
    producing = set(prod)

    # ---- Pass 1: abandoned foundations (delete of a never-used building) ----
    deletions = []
    razes = []  # (iid, time): a located (used) building was razed; resolve later
    abandoned_pos = set()  # (player, x, y) build slots that were abandoned
    dels = sorted(
        (a for a in match.actions if a.player and act_type(a) == "DELETE"),
        key=lambda a: a.timestamp.total_seconds(),
    )
    for a in dels:
        ts = a.timestamp.total_seconds()
        player = a.player.name
        for oid in (a.payload or {}).get("object_ids", []):
            if oid in producing or oid in anchor:
                razes.append((oid, ts))  # a real building was destroyed
                continue
            # Abandoned: most recent prior un-claimed BUILD by this player.
            cand = None
            for rec in all_builds.get(player, []):
                if rec[0] < ts and not rec[3]:
                    cand = rec  # time-sorted, so last qualifying = most recent
            if cand is not None:
                cand[3] = True
                abandoned_pos.add((player, cand[1], cand[2]))
                deletions.append(
                    {"x": cand[1], "y": cand[2], "player": player, "time": ts}
                )

    # ---- Pass 2: pair producing ids to SURVIVING builds of their class ----
    def classify(d):
        cc = Counter()
        for u, k in d["units"].items():
            c = _unit_class(u)
            if c:
                cc[c] += k
        if cc:
            return cc.most_common(1)[0][0]
        for tech, k in d["techs"].items():
            c = _tech_class(tech)
            if c:
                cc[c] += k
        return cc.most_common(1)[0][0] if cc else None

    builds = defaultdict(list)  # (player, class) -> [(time, x, y)] surviving
    for a in match.actions:
        if not a.player or act_type(a) != "BUILD":
            continue
        c = _building_class((a.payload or {}).get("building"))
        pos = getattr(a, "position", None)
        if c and pos:
            key3 = (a.player.name, round(pos.x), round(pos.y))
            if key3 in abandoned_pos:
                continue  # this slot was abandoned, no production came from it
            builds[(a.player.name, c)].append(
                (a.timestamp.total_seconds(), round(pos.x), round(pos.y))
            )
    for k in builds:
        builds[k].sort()

    buckets = defaultdict(list)
    for iid, d in prod.items():
        if iid in anchor:
            continue
        c = classify(d)
        if c:
            buckets[(d["player"], c)].append(iid)

    iid_pos = dict(anchor)  # iid -> (player, x, y)
    for key, iids in buckets.items():
        iids.sort()  # ascending id == build order
        bl = builds.get(key, [])
        for i, iid in enumerate(iids):
            if i < len(bl):
                iid_pos[iid] = (key[0], bl[i][1], bl[i][2])

    # Resolve razes of located buildings now that iid_pos is known.
    for oid, ts in razes:
        loc = iid_pos.get(oid)
        if loc:
            deletions.append(
                {"x": loc[1], "y": loc[2], "player": loc[0], "time": ts}
            )

    # ---- Interactions: any action whose object_ids names a located building ----
    interactions = []
    seen = set()
    for a in match.actions:
        if not a.player:
            continue
        ts = a.timestamp.total_seconds()
        for oid in (a.payload or {}).get("object_ids", []):
            loc = iid_pos.get(oid)
            if not loc:
                continue
            kdup = (oid, round(ts, 2))
            if kdup in seen:
                continue
            seen.add(kdup)
            interactions.append(
                {"x": loc[1], "y": loc[2], "player": loc[0], "time": ts}
            )

    return interactions, deletions


# Commands only a VILLAGER can be the subject of.
_VIL_CMDS = {"BUILD", "REPAIR", "WALL"}
# Commands only a MILITARY unit can be the subject of.
_MIL_CMDS = {"STANCE", "FORMATION", "PATROL", "ATTACK_GROUND", "DE_ATTACK_MOVE", "GUARD"}
# Commands whose object_ids reference a BUILDING, not the acting unit.
_BLD_SUBJECT_CMDS = {
    "DE_QUEUE", "RESEARCH", "GATHER_POINT", "SELL", "BUY",
    "TOWN_BELL", "UNGARRISON", "DE_MULTI_GATHERPOINT",
}
# GAIA names that ONLY villagers interact with (no animals: scouts lure boar;
# no relics: monks; no terrain decoration).
_RESOURCE_KW = ("gold mine", "stone mine", "tree", "bush", "berr", "forage", "shrub", "plant")


def _classify_units(match):
    """Identify every commanded unit's type from player behavior + production.

    Recorded games never announce a produced unit's type — only the starting
    units are named — so we reconstruct it in three steps:

      1. Behavioral hard-labels (a unit's OWN commands betray its class):
           villager <- it BUILD/REPAIRs, builds a WALL, or gathers a resource
           military <- it sets a STANCE/FORMATION, PATROLs, attack-grounds,
                       GUARDs, or attacks an enemy-owned object
         Military-only commands win conflicts; eco-definitive beats attack.
      2. Resolve the remaining 'unknown' units against each player's exact
         villager count (from DE_QUEUE): earliest-appearing unknowns fill the
         villager quota, the rest are military.
      3. Give each military unit a concrete type by greedily matching it to the
         most-recently-queued MILITARY unit (villagers excluded) for that player
         before it first appeared. Searching the military-only queue keeps the
         constant stream of villager queues from stealing military units — the
         core bug in the old time-only matcher.

    Returns {instance_id: type_string} for commanded (non-starting) units.
    """
    def norm(s):
        return (s or "").lower().replace(" ", "")

    # Owner of every instance id (players only).
    owner = {}
    for p in match.players:
        for o in (p.objects or []):
            owner[o.instance_id] = p.name
    for a in match.actions:
        if not a.player:
            continue
        for oid in (a.payload or {}).get("object_ids", []):
            owner.setdefault(oid, a.player.name)

    # GAIA ids: all (to recognise non-resource targets) and villager-only resources.
    gaia = getattr(match, "gaia", None) or []
    gaia_all = {getattr(g, "instance_id", None) for g in gaia}
    resource_ids = set()
    for g in gaia:
        iid = getattr(g, "instance_id", None)
        nm = (getattr(g, "name", None) or "").lower()
        if iid is None or not nm:
            continue
        if any(k in nm for k in _RESOURCE_KW) and "dry" not in nm and "grass" not in nm:
            resource_ids.add(iid)

    start_ids = {o.instance_id for p in match.players for o in (p.objects or [])}

    # Pass 1: behavioral signals + first-seen time.
    mil_def, vil_def, mil_atk = set(), set(), set()
    first_seen = {}
    for a in match.actions:
        if not a.player:
            continue
        at = str(a.type).replace("Action.", "")
        if at in _BLD_SUBJECT_CMDS:
            continue
        payload = a.payload or {}
        t = a.timestamp.total_seconds()
        tgt = payload.get("target_id")
        for oid in payload.get("object_ids", []):
            first_seen.setdefault(oid, t)
            if at in _MIL_CMDS:
                mil_def.add(oid)
            if at in _VIL_CMDS:
                vil_def.add(oid)
            if at == "ORDER" and isinstance(tgt, int):
                if tgt in resource_ids:
                    vil_def.add(oid)
                elif tgt not in gaia_all and owner.get(tgt) and owner.get(tgt) != owner.get(oid):
                    mil_atk.add(oid)

    # Per-player production slots: a villager queue and a typed military queue,
    # each a list of one slot per produced unit (DE_QUEUE amounts expanded).
    prod = defaultdict(Counter)
    vil_queue = defaultdict(list)
    mil_queue = defaultdict(list)
    for a in match.actions:
        if str(a.type).endswith("DE_QUEUE") and a.player and a.payload:
            u = norm(a.payload.get("unit"))
            amt = a.payload.get("amount", 1) or 1
            prod[a.player.name][u] += amt
            ts = a.timestamp.total_seconds()
            q = vil_queue if u == "villager" else mil_queue
            for _ in range(amt):
                q[a.player.name].append({"time": ts, "type": u, "used": False})
    for d in (vil_queue, mil_queue):
        for q in d.values():
            q.sort(key=lambda x: x["time"])

    MIL, UNK = "\x00mil", "\x00unk"
    cls = {}
    for oid in first_seen:
        if oid in start_ids:
            continue
        if oid in mil_def or oid in mil_atk:
            cls[oid] = MIL if (oid in mil_def or oid not in vil_def) else "villager"
        elif oid in vil_def:
            cls[oid] = "villager"
        else:
            cls[oid] = UNK

    # Nearest unused slot in a queue to time `t`, preferring a slot at or before
    # `t` (a unit appears after it is produced); later slots are distance-
    # penalised. `peek` returns (slot, distance) without consuming; `take` marks
    # a slot used.
    def peek(queue, t):
        best, best_d = None, float("inf")
        for s in queue:
            if s["used"]:
                continue
            d = (t - s["time"]) if s["time"] <= t else (s["time"] - t) * 3
            if d < best_d:
                best_d, best = d, s
        return best, best_d

    # Resolve every unit in appearance order so earlier units claim the closest
    # production slots first.
    result = {}
    for oid in sorted(cls, key=lambda o: first_seen.get(o, 0)):
        c = cls[oid]
        p = owner.get(oid)
        t = first_seen.get(oid, 0)
        if c == "villager":
            sv, _ = peek(vil_queue.get(p, []), t)  # consume to keep counts honest
            if sv:
                sv["used"] = True
            result[oid] = "villager"
        elif c == MIL:
            sm, _ = peek(mil_queue.get(p, []), t)
            if sm:
                sm["used"] = True
                result[oid] = sm["type"]
            else:
                mt = [(u, n) for u, n in prod[p].items() if u != "villager"]
                result[oid] = max(mt, key=lambda x: x[1])[0] if mt else "unit"
        else:
            # Unknown (no behavioural tell): villager vs military decided by which
            # production was happening nearest its appearance — the timeline, not
            # its raw timestamp. Stops an early military unit from being swept
            # into the villager count just for appearing early.
            sv, dv = peek(vil_queue.get(p, []), t)
            sm, dm = peek(mil_queue.get(p, []), t)
            if sv is not None and dv <= dm:
                sv["used"] = True
                result[oid] = "villager"
            elif sm is not None:
                sm["used"] = True
                result[oid] = sm["type"]
            elif sv is not None:
                sv["used"] = True
                result[oid] = "villager"
            else:
                result[oid] = "unit"
    return result


def process_replay(replay_file):
    """Process a replay file and return JSON data."""

    object_names = load_object_names()

    match = mgz.model.parse_match(replay_file)
    match_duration = match.duration.total_seconds()

    # Build unit owner map
    unit_owner_map = {}
    for player in match.players:
        if player.objects:
            for obj in player.objects:
                unit_owner_map[obj.instance_id] = player.name

    for action in match.actions:
        if not action.player:
            continue
        payload = action.payload or {}
        if "object_ids" in payload:
            for obj_id in payload["object_ids"]:
                if obj_id not in unit_owner_map:
                    unit_owner_map[obj_id] = action.player.name

    # Track actions per unit with first seen time
    unit_actions = defaultdict(list)
    unit_first_seen = {}  # obj_id -> first time seen
    for action in match.actions:
        if not action.player:
            continue
        payload = action.payload or {}
        action_time = action.timestamp.total_seconds()
        if "object_ids" in payload:
            for obj_id in payload["object_ids"]:
                unit_actions[obj_id].append(
                    {
                        "time": action_time,
                        "type": str(action.type).replace("Action.", ""),
                    }
                )
                if obj_id not in unit_first_seen:
                    unit_first_seen[obj_id] = action_time

    # Identify each commanded unit's type from behavior + production. See
    # _classify_units: villager/military split from each unit's own commands,
    # then a concrete military type from the player's military-only train queue.
    # v2: group-first, confidence-based classifier (unit_classifier.py). Falls
    # back to the legacy greedy matcher if anything goes wrong. See
    # CLASSIFIER_REWORK.md.
    _canon = lambda x: x  # noqa: E731
    try:
        import unit_classifier as _uc
        unit_type_map, _remap = _uc.build_type_map(match)
        _canon = lambda o: _remap.get(o, o)  # noqa: E731  collapse shifted dups
    except Exception as e:
        app.logger.warning(f"v2 classification failed, falling back to legacy: {e}")
        try:
            unit_type_map = _classify_units(match)
        except Exception as e2:
            app.logger.warning(f"legacy classification also failed: {e2}")
            unit_type_map = {}

    # Build unit names
    unit_name_map = {}
    unit_counters = defaultdict(lambda: defaultdict(int))

    # Name starting units (these have obj.name from the replay)
    starting_obj_ids = set()
    for player in match.players:
        if player.objects:
            for obj in player.objects:
                starting_obj_ids.add(obj.instance_id)
                unit_type = obj.name.lower().replace(" ", "") if obj.name else "unit"
                unit_counters[player.name][unit_type] += 1
                count = unit_counters[player.name][unit_type]
                unit_name_map[obj.instance_id] = f"{unit_type}_{player.name}_{count}"

    # Build data structure
    data = {
        "match": {
            "map_name": match.map.name
            if hasattr(match.map, "name")
            else str(match.map),
            "map_size": 220,
            "duration_seconds": match_duration,
            "duration_formatted": str(match.duration).split(".")[0],
        },
        "players": [],
        "starting_units": [],
        "actions": [],
        "walls": [],
        "unit_deaths": {},
        "building_interactions": [],
        "building_deletions": [],
    }

    # Recover building activity: re-brighten on use (interactions) and remove
    # abandoned/razed buildings from the map (deletions).
    try:
        interactions, deletions = _analyze_buildings(match)
        data["building_interactions"] = interactions
        data["building_deletions"] = deletions
    except Exception as e:
        app.logger.warning(f"building analysis failed: {e}")
        data["building_interactions"] = []
        data["building_deletions"] = []

    # Starting-map backdrop: terrain grid + GAIA resource/tree objects.
    try:
        data["match"]["map_size"] = match.map.dimension
        data["terrain"] = _extract_terrain(match)
        data["map_objects"] = _extract_map_objects(match)
        data["animals"] = _extract_animals(match)
    except Exception as e:
        app.logger.warning(f"terrain/object extraction failed: {e}")
        data["terrain"] = None
        data["map_objects"] = []
        data["animals"] = []

    # Add players
    for player in match.players:
        color = PLAYER_COLORS.get(
            player.color_id, {"name": "Unknown", "hex": "#FFFFFF"}
        )
        # Get team info - player.team contains list of Player objects, convert to string names
        team_names = (
            [str(tm) for tm in player.team]
            if hasattr(player, "team") and player.team
            else []
        )
        data["players"].append(
            {
                "name": player.name,
                "color_id": player.color_id,
                "color_hex": color["hex"],
                "color_name": color["name"],
                "civilization": player.civilization
                if hasattr(player, "civilization")
                else "",
                "team": team_names,
            }
        )

    # Add starting units
    for player in match.players:
        if player.objects:
            for obj in player.objects:
                unit_name = unit_name_map.get(
                    obj.instance_id, f"unit_{obj.instance_id}"
                )
                raw_type = obj.name.lower().replace(" ", "") if obj.name else "unit"
                unit_class = classify_unit_type(raw_type)

                # Prefer the unit's true spawn point from the replay. Land Nomad
                # scatters the 3 starting villagers far apart, so falling back to
                # the first MOVE command (often a single select-all order) would
                # stack them all at one target instead of their real spawns.
                start_x, start_y = None, None
                spawn = getattr(obj, "position", None)
                if spawn is not None:
                    start_x = spawn.x
                    start_y = spawn.y
                else:
                    for action in match.actions:
                        if not action.player:
                            continue
                        payload = action.payload or {}
                        if obj.instance_id in payload.get("object_ids", []):
                            if hasattr(action, "position") and action.position:
                                start_x = action.position.x
                                start_y = action.position.y
                                break

                data["starting_units"].append(
                    {
                        "id": unit_name,
                        "instance_id": obj.instance_id,
                        "player": player.name,
                        "type": unit_class,
                        "x": start_x,
                        "y": start_y,
                    }
                )

    # Process actions
    action_id = 0
    for action in match.actions:
        if not action.player:
            continue

        action_id += 1
        action_type = str(action.type).replace("Action.", "")
        payload = action.payload or {}
        pos = action.position if hasattr(action, "position") else None

        unit_ids = payload.get("object_ids", [])
        subject_names = []

        for obj_id in unit_ids:
            # Canonicalize so a unit referenced by both its raw id (MOVE) and its
            # shifted id (SPECIAL/UNGARRISON) is ONE on-map unit, not two.
            cid = _canon(obj_id)
            if cid not in unit_name_map:
                owner = unit_owner_map.get(obj_id, action.player.name)

                # Type comes from the behavior+production classifier; default to
                # generic "unit" only if it never appeared in the classifier pass.
                unit_type = unit_type_map.get(cid, "unit")

                unit_counters[owner][unit_type] += 1
                count = unit_counters[owner][unit_type]
                unit_name_map[cid] = f"{unit_type}_{owner}_{count}"

            subject_names.append(unit_name_map[cid])

        target_name = ""
        if action_type == "BUILD":
            building_id = payload.get("building_id", payload.get("building", ""))
            building_type = object_names.get(str(building_id), f"building{building_id}")
            target_name = building_type.lower().replace(" ", "")
        elif action_type == "DE_QUEUE":
            unit_type = payload.get("unit", "unit")
            target_name = unit_type.lower().replace(" ", "")
        elif action_type == "RESEARCH":
            tech = payload.get("technology", payload.get("tech_id", ""))
            target_name = str(tech).lower().replace(" ", "")

        # For ORDER actions, capture target_id for attack visualization
        target_id = payload.get("target_id") if action_type == "ORDER" else None

        data["actions"].append(
            {
                "id": action_id,
                "time": action.timestamp.total_seconds(),
                "player": action.player.name,
                "type": action_type,
                "subjects": subject_names,
                "target": target_name,
                "target_id": target_id,  # For ORDER (attack) actions
                "x": pos.x if pos else None,
                "y": pos.y if pos else None,
                "amount": payload.get("amount"),
            }
        )

        # Capture wall placements
        if action_type == "WALL":
            wall_type = payload.get("building", "Palisade Wall")
            building_id = payload.get("building_id", 72)
            x_start = pos.x if pos else None
            y_start = pos.y if pos else None
            x_end = payload.get("x_end", x_start)
            y_end = payload.get("y_end", y_start)

            if x_start is not None and y_start is not None:
                data["walls"].append(
                    {
                        "time": action.timestamp.total_seconds(),
                        "player": action.player.name,
                        "type": wall_type.lower().replace(" ", ""),
                        "building_id": building_id,
                        "x_start": x_start,
                        "y_start": y_start,
                        "x_end": x_end,
                        "y_end": y_end,
                    }
                )

    # Calculate unit deaths
    for obj_id, actions in unit_actions.items():
        if not actions:
            continue

        unit_name = unit_name_map.get(_canon(obj_id))
        if not unit_name:
            continue

        # Villagers don't "die" from idleness (only military units do).
        if unit_name.startswith("villager"):
            continue

        last_time = actions[-1]["time"]
        if match_duration - last_time > DEATH_THRESHOLD:
            death_time = last_time + DEATH_THRESHOLD
            data["unit_deaths"][unit_name] = death_time

    return data


@app.route("/")
def index():
    return send_from_directory("public", "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("public", path)


@app.route("/api/upload", methods=["POST"])
def upload_replay():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.endswith(".aoe2record"):
        return jsonify(
            {"error": "Invalid file type. Please upload a .aoe2record file"}
        ), 400

    try:
        # Save to temp file since mgz needs a proper file handle
        with tempfile.NamedTemporaryFile(suffix=".aoe2record", delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                data = process_replay(f)
            return jsonify(data)
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to process replay: {str(e)}"}), 500


@app.route("/api/default", methods=["GET"])
def get_default_replay():
    """Return the default replay_data.json if it exists."""
    try:
        with open("replay_data.json", "r") as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({"error": "No default replay data found"}), 404


@app.route("/api/matches", methods=["GET"])
def get_matches():
    """Fetch recent Land Nomad matches from all players in the CSV."""
    try:
        # Load players from CSV
        players = load_players_from_csv()
        if not players:
            return jsonify({"error": "No players found in players.csv"}), 404

        # Get all profile IDs
        profile_ids = [p["profileId"] for p in players]

        # Fetch matches for all players (API accepts comma-separated profile_ids)
        all_matches = {}
        matches_url = f"{AOE2_COMPANION_API}/matches"

        # Fetch in batches to avoid URL length limits
        batch_size = 10
        for i in range(0, len(profile_ids), batch_size):
            batch_ids = profile_ids[i : i + batch_size]
            matches_resp = requests.get(
                matches_url,
                params={"profile_ids": ",".join(map(str, batch_ids)), "perPage": 50},
                headers=AOE2_COMPANION_HEADERS,
                timeout=30,
            )
            matches_data = matches_resp.json()

            # Deduplicate by match ID and filter for Land Nomad
            for match in matches_data.get("matches", []):
                match_id = match.get("matchId")
                map_name = match.get("mapName", "").lower()

                # Only include Land Nomad maps
                if "land nomad" not in map_name:
                    continue

                if match_id and match_id not in all_matches:
                    all_matches[match_id] = match

        # Sort by start time (newest first) and take top 25
        sorted_matches = sorted(
            all_matches.values(),
            key=lambda x: x.get("started", ""),
            reverse=True,
        )[:25]

        return jsonify(
            {
                "players": players,
                "matches": sorted_matches,
            }
        )

    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch matches: {str(e)}"}), 500
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Error: {str(e)}"}), 500


@app.route("/api/matches/<player_name>", methods=["GET"])
def get_matches_for_player(player_name):
    """Fetch recent matches for a specific player from AoE2 Companion API."""
    try:
        # First, search for the player to get their profile ID
        search_url = f"{AOE2_COMPANION_API}/profiles"
        search_resp = requests.get(
            search_url,
            params={"search": player_name},
            headers=AOE2_COMPANION_HEADERS,
            timeout=15,
        )
        search_data = search_resp.json()

        profiles = search_data.get("profiles", [])
        if not profiles:
            return jsonify({"error": f"Player '{player_name}' not found"}), 404

        # Find exact match or use first result
        profile = None
        for p in profiles:
            if p.get("name", "").lower() == player_name.lower():
                profile = p
                break
        if not profile:
            profile = profiles[0]

        profile_id = profile.get("profileId")

        # Fetch recent matches
        matches_url = f"{AOE2_COMPANION_API}/matches"
        matches_resp = requests.get(
            matches_url,
            params={"profile_ids": profile_id, "perPage": 10},
            headers=AOE2_COMPANION_HEADERS,
            timeout=15,
        )
        matches_data = matches_resp.json()

        return jsonify(
            {
                "player": {
                    "profileId": profile_id,
                    "name": profile.get("name"),
                    "country": profile.get("country"),
                    "games": profile.get("games"),
                },
                "matches": matches_data.get("matches", []),
            }
        )

    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch matches: {str(e)}"}), 500
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Error: {str(e)}"}), 500


@app.route("/api/players", methods=["GET"])
def search_players():
    """Search the AoE2 Companion player directory by name and return the list of
    candidate profiles so the user can pick the right one before browsing their
    games. Query param: ?search=<name> (alias ?q=). Returns up to 15 profiles."""
    query = (request.args.get("search") or request.args.get("q") or "").strip()
    if not query:
        return jsonify({"error": "Missing 'search' query parameter"}), 400

    try:
        search_resp = requests.get(
            f"{AOE2_COMPANION_API}/profiles",
            params={"search": query},
            headers=AOE2_COMPANION_HEADERS,
            timeout=15,
        )
        search_data = search_resp.json()

        profiles = []
        for p in search_data.get("profiles", []):
            pid = p.get("profileId")
            if pid is None:
                continue
            # Number of games can come back as a string from the API.
            try:
                games = int(p.get("games") or 0)
            except (TypeError, ValueError):
                games = 0
            profiles.append(
                {
                    "profileId": pid,
                    "name": p.get("name"),
                    "country": p.get("country"),
                    "clan": p.get("clan") or "",
                    "games": games,
                    "verified": bool(p.get("verified")),
                    "platformName": p.get("platformName"),
                }
            )

        # Most-played first so the well-known account tends to surface on top.
        profiles.sort(key=lambda x: x["games"], reverse=True)

        return jsonify({"query": query, "players": profiles[:15]})

    except requests.RequestException as e:
        return jsonify({"error": f"Failed to search players: {str(e)}"}), 500
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Error: {str(e)}"}), 500


@app.route("/api/player/<int:profile_id>/matches", methods=["GET"])
def get_player_matches(profile_id):
    """Fetch a specific player's most recent games (all maps/modes) by profile id.
    Optional ?limit=<n> (default 10, max 25). Used after the user picks a player
    from the search results."""
    try:
        limit = request.args.get("limit", default=10, type=int) or 10
        limit = max(1, min(limit, 25))

        matches_resp = requests.get(
            f"{AOE2_COMPANION_API}/matches",
            params={"profile_ids": profile_id, "perPage": limit},
            headers=AOE2_COMPANION_HEADERS,
            timeout=15,
        )
        matches_data = matches_resp.json()
        matches = matches_data.get("matches", [])[:limit]

        # Pull the player's display name from the returned matches if present.
        name = None
        for match in matches:
            for team in match.get("teams", []):
                for player in team.get("players", []):
                    if player.get("profileId") == profile_id:
                        name = player.get("name")
                        break
                if name:
                    break
            if name:
                break

        return jsonify(
            {
                "player": {"profileId": profile_id, "name": name},
                "matches": matches,
            }
        )

    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch matches: {str(e)}"}), 500
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Error: {str(e)}"}), 500


def _fetch_replay_to_cache(match_id, profile_id):
    """Return a local path to the match's .aoe2record, downloading from aoe.ms
    only if it isn't already cached. Retries briefly on HTTP 429 (rate limit).
    Raises RuntimeError with a user-facing message on failure."""
    import time

    os.makedirs(REPLAY_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(REPLAY_CACHE_DIR, f"{match_id}.aoe2record")
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        app.logger.info(f"Replay cache hit: {cache_path}")
        return cache_path

    download_url = f"{REPLAY_DOWNLOAD_URL}/?gameId={match_id}&profileId={profile_id}"
    app.logger.info(f"Downloading replay from: {download_url}")

    resp = None
    for attempt in range(3):
        resp = requests.get(
            download_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60
        )
        if resp.status_code == 200:
            break
        if resp.status_code == 429 and attempt < 2:
            try:
                wait = int(resp.headers.get("Retry-After", "2"))
            except ValueError:
                wait = 2
            time.sleep(min(max(wait, 1), 5))
            continue
        break

    if resp is None or resp.status_code != 200:
        code = resp.status_code if resp is not None else "n/a"
        if code == 429:
            raise RuntimeError(
                "The replay host (aoe.ms) is rate-limiting downloads right now "
                "(HTTP 429). Please wait a minute and try again."
            )
        raise RuntimeError(f"Failed to download replay: HTTP {code}")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        record_file = next(
            (n for n in zf.namelist() if n.endswith(".aoe2record")), None
        )
        if not record_file:
            raise RuntimeError("No .aoe2record file found in ZIP")
        # Write to a temp file then atomically move into the cache.
        with tempfile.NamedTemporaryFile(
            dir=REPLAY_CACHE_DIR, suffix=".part", delete=False
        ) as tmp:
            tmp.write(zf.read(record_file))
            tmp_path = tmp.name
    os.replace(tmp_path, cache_path)
    return cache_path


@app.route("/api/load-match", methods=["POST"])
def load_match():
    """Download (or reuse cached) replay from aoe.ms, parse, return replay data."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    match_id = data.get("matchId")
    profile_id = data.get("profileId")

    if not match_id or not profile_id:
        return jsonify({"error": "matchId and profileId are required"}), 400

    download_url = f"{REPLAY_DOWNLOAD_URL}/?gameId={match_id}&profileId={profile_id}"
    try:
        cache_path = _fetch_replay_to_cache(match_id, profile_id)
    except RuntimeError as e:
        # 429 -> surface as 429 so the client can show a clear retry message.
        status = 429 if "429" in str(e) else 502
        return jsonify({"error": str(e)}), status
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to download replay: {str(e)}"}), 502
    except zipfile.BadZipFile:
        return jsonify({"error": "Downloaded file is not a valid ZIP"}), 502

    try:
        with open(cache_path, "rb") as f:
            replay_data = process_replay(f)

        replay_data["source"] = {
            "matchId": match_id,
            "profileId": profile_id,
            "downloadUrl": download_url,
        }
        return jsonify(replay_data)
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to process replay: {str(e)}"}), 500


CLIP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "clips")


@app.route("/api/clip", methods=["GET"])
def make_clip():
    """Generate (or reuse a cached) short shareable WebM of a match's biggest
    engagements (<=30s, 8x, with a skip-aware timeline). Reuses the same replay
    download/cache as /api/load-match.

    Query: matchId, profileId, [player]. Returns {clip_url, view_url}."""
    import re as _re

    match_id = request.args.get("matchId") or request.args.get("match_id")
    profile_id = request.args.get("profileId") or request.args.get("profile_id")
    player = request.args.get("player")
    if not match_id or not profile_id:
        return jsonify({"error": "matchId and profileId are required"}), 400
    try:
        cache_path = _fetch_replay_to_cache(match_id, profile_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), (429 if "429" in str(e) else 502)
    except Exception as e:
        return jsonify({"error": f"download failed: {e}"}), 502

    safe = _re.sub(r"[^A-Za-z0-9_-]", "", (player or "all"))[:40] or "all"
    os.makedirs(CLIP_DIR, exist_ok=True)
    out_name = f"{match_id}_{safe}.webm"
    out_path = os.path.join(CLIP_DIR, out_name)
    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
        try:
            import clip_export
            with open(cache_path, "rb") as f:
                match = mgz.model.parse_match(f)
            focus = None
            if player:
                focus = next((p.name for p in match.players if p.name == player), None)
            if not focus:
                focus = next((p.name for p in match.players
                              if str(getattr(p, "profile_id", "")) == str(profile_id)), None)
            if not focus and match.players:
                focus = match.players[0].name
            clip_export.build_clip(match, focus or "", out_path)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"clip generation failed: {e}"}), 500

    # respect the proxy's scheme (Railway terminates TLS) so shared links are https
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    base = f"{proto}://{request.host}"
    return jsonify({
        "clip_url": f"{base}/clips/{out_name}",
        # Use the ?match=&profile= deep-link params the frontend actually reads
        # (app.js init()) so the shared "Watch in UI" link auto-loads the replay.
        "view_url": f"{base}/?match={match_id}&profile={profile_id}",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    print("Starting AoE2 Replay Visualizer server...")
    print(f"Open http://localhost:{port} in your browser")
    app.run(debug=debug, host="0.0.0.0", port=port)
