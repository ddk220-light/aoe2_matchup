"""Build the opponent pool: validated unique units + generic land staples.

Uniques come from apps/video/auto/unique_units.json (the validated list the
video sweep uses). Staples are line-imperial slugs pinned to a canonical
top-upgrade name, with the civ picked as the modal stats+cost variant so civ
discounts/bonuses don't skew equal-resource fights. siege_onager was DROPPED
from the staples (user 2026-07-05: exclude mangonel/scorpion units).

IMPORTANT: the combat-dict packing (prepare_combat_unit /
build_combat_dict_from_ref) is LAZY. It is only needed by LocalSimSource and
importing aoe2x.sim pulls in numpy. The MatchupDbSource path never asks for it,
so building a pool for the DB source works without importing aoe2x.sim.
"""
import json
import sqlite3
from collections import Counter

from aoe2x.paths import GOLDEN_DIR, REPO_ROOT
from aoe2x.analysis.story_rules import categorize

REF_DB = GOLDEN_DIR / "aoe2_reference.db"
UNIQUE_UNITS_JSON = REPO_ROOT / "apps" / "video" / "auto" / "unique_units.json"

# Generic staples: (line slug, canonical top-upgrade name). Civ auto-picked as
# the modal (stats+cost) variant among civs whose final form IS the canonical
# one. siege_onager dropped 2026-07-05.
STAPLES = [
    ("champion", "Champion"), ("halberdier", "Halberdier"),
    ("arbalester", "Arbalester"), ("imp_elite_skirm", "Elite Skirmisher"),
    ("heavy_cav_archer", "Heavy Cavalry Archer"), ("paladin", "Paladin"),
    ("hussar", "Hussar"), ("heavy_camel", "Heavy Camel Rider"),
    ("elite_steppe", "Elite Steppe Lancer"),
    ("elite_elephant", "Elite Battle Elephant"),
    # siege_onager dropped 2026-07-05 (user: exclude mangonel/scorpion units).
    ("hand_cannoneer", "Hand Cannoneer"), ("elite_eagle", "Elite Eagle Warrior"),
]

NAVAL_KEYWORDS = ("turtle_ship", "caravel", "longboat", "thirisadai",
                  "lou_chuan", "dromon", "galley", "cannon_galleon")
PASSIVE_KEYWORDS = ("siege_ram", "battering_ram", "trebuchet", "petard",
                    "flaming_camel", "armored_elephant", "siege_elephant")

_SIG_COLS = ("final_hp", "final_attack", "final_melee_armor",
             "final_pierce_armor", "final_speed", "final_attacks_json",
             "final_armors_json", "final_cost_food", "final_cost_wood",
             "final_cost_gold")


def _connect():
    db = sqlite3.connect(str(REF_DB))
    db.row_factory = sqlite3.Row
    return db


def _get_row(db, civ, slug):
    return db.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
        (civ, slug)).fetchone()


def _cost_of(row):
    return ((row["final_cost_food"] or 0) + (row["final_cost_wood"] or 0)
            + (row["final_cost_gold"] or 0) * 1.0)


def _combat_dict(row):
    """Lazily build the prepared combat dict. Imports aoe2x.sim (numpy) — only
    call this for LocalSimSource, never on the MatchupDb path."""
    from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref
    from aoe2x.sim.simulation import prepare_combat_unit
    return prepare_combat_unit(build_combat_dict_from_ref(row))


def _pack(row, is_unique, with_combat=False):
    speed = row["final_speed"] or 1.0
    cat = categorize(row["unit_slug"], row["unit_class_name"],
                     bool(row["is_ranged"]), speed)
    packed = {
        "civ": row["civ_name"], "slug": row["unit_slug"], "name": row["unit_name"],
        "atk": row["final_attack"], "attacks": row["final_attacks_json"],
        "armors": row["final_armors_json"], "cost": _cost_of(row),
        "gold": row["final_cost_gold"] or 0,
        "ranged": bool(row["is_ranged"]), "speed": speed,
        "is_unique": is_unique, "cat": cat,
    }
    if with_combat:
        packed["combat"] = _combat_dict(row)
    return packed


def modal_civ(db, slug, canonical_name):
    """Pick a civ whose final form is the canonical top upgrade AND whose
    stats+costs are the most common variant (avoids civ discounts/bonuses)."""
    rows = db.execute(
        f"SELECT civ_name, {', '.join(_SIG_COLS)} FROM ref_units"
        " WHERE unit_slug=? AND age='Imperial' AND unit_name=?",
        (slug, canonical_name)).fetchall()
    if not rows:
        return None
    sig, by_sig = Counter(), {}
    for r in rows:
        key = tuple(r[c] for c in _SIG_COLS)
        sig[key] += 1
        by_sig.setdefault(key, r["civ_name"])
    return by_sig[sig.most_common(1)[0][0]]


def load_subject(civ, slug, with_combat=False):
    """Pack the subject unit. Uniques are is_unique=True."""
    db = _connect()
    row = _get_row(db, civ, slug)
    if row is None:
        raise SystemExit(f"no Imperial ref row for {civ}/{slug}")
    return _pack(row, is_unique=True, with_combat=with_combat)


def build_pool(subject_civ, subject_slug, with_combat=False):
    """Uniques (minus subject/naval/passive) + the 12 generic staples.

    Set with_combat=True only for LocalSimSource (needs prepared combat dicts).
    The MatchupDb path leaves it False and never imports aoe2x.sim.
    """
    db = _connect()
    pool = []
    for u in json.loads(UNIQUE_UNITS_JSON.read_text()):
        if u["slug"] == subject_slug:
            continue
        if any(k in u["slug"] for k in NAVAL_KEYWORDS + PASSIVE_KEYWORDS):
            continue
        row = _get_row(db, u["civ"], u["slug"])
        if row is None:
            continue                       # dat-build drift; skip loudly upstream
        pool.append(_pack(row, is_unique=True, with_combat=with_combat))
    for slug, canonical in STAPLES:
        civ = modal_civ(db, slug, canonical)
        if civ is None:
            raise SystemExit(f"staple {slug} ({canonical}) not found in ref DB")
        pool.append(_pack(_get_row(db, civ, slug), is_unique=False,
                          with_combat=with_combat))
    return pool
