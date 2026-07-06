"""Prototype: pick the 12 'interesting matchups' for Elite Temple Guard (Muisca).

Throwaway design-validation script — abstract sim engine (simulation.py), not the
batch baseline. S = equal-resources HP margin; E = blended expectation prior.
"""
import json
import math
import sqlite3
import sys
from collections import Counter

REPO = "/Users/deepak/AI/aoe2_matchup"
sys.path.insert(0, REPO)

from aoe2x.sim.simulation import prepare_combat_unit, simulate_battle  # noqa: E402
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref    # noqa: E402

DB = sqlite3.connect(f"{REPO}/data/golden/aoe2_reference.db")
DB.row_factory = sqlite3.Row

SUBJECT_CIV, SUBJECT_SLUG = "Muisca", "elite_temple_guard_muisca"
BUDGET = 3000

# Generic staples: (line slug, canonical top-upgrade name). Civ auto-picked as
# the modal (stats+cost) variant among civs whose final form IS the canonical one.
STAPLES = [
    ("champion", "Champion"), ("halberdier", "Halberdier"),
    ("arbalester", "Arbalester"), ("imp_elite_skirm", "Elite Skirmisher"),
    ("heavy_cav_archer", "Heavy Cavalry Archer"), ("paladin", "Paladin"),
    ("hussar", "Hussar"), ("heavy_camel", "Heavy Camel Rider"),
    ("elite_steppe", "Elite Steppe Lancer"),
    ("elite_elephant", "Elite Battle Elephant"),
    ("siege_onager", "Siege Onager"),
    ("hand_cannoneer", "Hand Cannoneer"), ("elite_eagle", "Elite Eagle Warrior"),
]

# Units that don't meaningfully fight other units — pointless video segments.
PASSIVE_KEYWORDS = ("siege_ram", "battering_ram", "trebuchet", "petard",
                    "flaming_camel", "armored_elephant", "siege_elephant")

NAVAL_KEYWORDS = ("turtle_ship", "caravel", "longboat", "thirisadai",
                  "lou_chuan", "dromon", "galley", "cannon_galleon")

GUNPOWDER_KEYS = ("janissary", "conquistador", "organ_gun", "hand_cannoneer",
                  "hussite", "ribauldequin", "fire_thrower", "grenadier")

WEIGHTS = {"bonus": 0.5, "rps": 0.3, "cost": 0.2}
WIN_T = 15.0      # |S| threshold for win/loss
E_T = 0.15        # |E| threshold for "clearly expected"

# ---------------------------------------------------------------- categories
def categorize(slug, unit_class, is_ranged):
    s = slug.lower()
    if any(k in s for k in GUNPOWDER_KEYS):
        return "gunpowder"
    if "ballista_elephant" in s:
        return "siege"
    if "camel" in s:
        return "camel"
    if "elephant" in s:
        return "elephant"
    if any(k in s for k in ("eagle", "fire_lancer", "temple_guard")):
        return "eagle"
    if any(k in s for k in ("halberdier", "pikeman", "spearman", "kamayuk")):
        return "spear"
    if "skirm" in s or "genitour" in s:
        return "skirm"
    if (s in ("hussar", "winged_hussar") or "huszar" in s or "shrivamsha" in s
            or s == "elite_steppe" or "steppe_lancer" in s):
        return "light_cav"
    uc = (unit_class or "").lower()
    if uc == "siege" or s in ("siege_onager", "heavy_scorpion", "mounted_trebuchet_khitans"):
        return "siege"
    if "cavalry" in uc:
        return "cav_archer" if is_ranged else "cavalry"
    if uc == "archer":
        return "archer"
    if uc == "infantry" and is_ranged:
        return "archer"      # thrown-weapon infantry (gbeto, axeman, chakram)
    return "infantry"

# Folk-knowledge matrix, subject-row perspective (+ = row favored). Sparse;
# missing pair -> antisymmetric lookup -> 0.
RPS = {
    "eagle": {"archer": .5, "skirm": .4, "cav_archer": .4, "siege": .6,
              "gunpowder": .4, "infantry": -.5, "spear": .2, "cavalry": -.3,
              "light_cav": .0, "camel": .0, "elephant": -.2},
    "infantry": {"spear": .4, "eagle": .5, "siege": .5, "elephant": .2,
                 "archer": -.4, "cav_archer": -.4, "cavalry": -.2,
                 "gunpowder": -.3, "skirm": .3},
    "spear": {"cavalry": .7, "light_cav": .6, "camel": .5, "elephant": .7,
              "archer": -.6, "skirm": -.5, "cav_archer": -.6,
              "gunpowder": -.5, "siege": .2},
    "archer": {"infantry": .4, "spear": .6, "elephant": .3, "siege": .2,
               "cavalry": -.4, "light_cav": -.3, "camel": -.3, "skirm": -.5},
    "skirm": {"archer": .5, "cav_archer": .4, "spear": .5,
              "cavalry": -.5, "light_cav": -.4, "gunpowder": .2},
    "cav_archer": {"infantry": .5, "spear": .6, "siege": .3, "elephant": .2,
                   "cavalry": -.2, "camel": -.2},
    "cavalry": {"archer": .4, "skirm": .5, "siege": .6, "gunpowder": .5,
                "cav_archer": .2, "light_cav": .3, "camel": -.5},
    "light_cav": {"siege": .6, "archer": .3, "skirm": .4, "gunpowder": .4,
                  "camel": -.4},
    "camel": {"elephant": .3, "cav_archer": .3, "infantry": -.3,
              "archer": -.3},
    "elephant": {"siege": .4, "gunpowder": .2},
    "siege": {"gunpowder": .2},
    "gunpowder": {},
}

def rps(a, b):
    if a == b:
        return 0.0
    if b in RPS.get(a, {}):
        return RPS[a][b]
    if a in RPS.get(b, {}):
        return -RPS[b][a]
    return 0.0

# ---------------------------------------------------------------- data access
def get_row(civ, slug):
    return DB.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
        (civ, slug)).fetchone()

def modal_civ(slug, canonical_name):
    """Pick a civ whose final form is the canonical top upgrade AND whose
    stats+costs are the most common variant (avoids civ discounts/bonuses)."""
    rows = DB.execute(
        "SELECT civ_name, final_hp, final_attack, final_melee_armor,"
        " final_pierce_armor, final_speed, final_attacks_json, final_armors_json,"
        " final_cost_food, final_cost_wood, final_cost_gold"
        " FROM ref_units WHERE unit_slug=? AND age='Imperial' AND unit_name=?",
        (slug, canonical_name)).fetchall()
    if not rows:
        return None
    sig = Counter()
    by_sig = {}
    for r in rows:
        key = tuple(r[k] for k in ("final_hp", "final_attack", "final_melee_armor",
                                   "final_pierce_armor", "final_speed",
                                   "final_attacks_json", "final_armors_json",
                                   "final_cost_food", "final_cost_wood",
                                   "final_cost_gold"))
        sig[key] += 1
        by_sig.setdefault(key, r["civ_name"])
    return by_sig[sig.most_common(1)[0][0]]

def cost_of(row):
    return ((row["final_cost_food"] or 0) + (row["final_cost_wood"] or 0)
            + (row["final_cost_gold"] or 0) * 1.0)

# ---------------------------------------------------------------- expectation
def bonus_gain(att_json, base_atk, opp_armors_json, attacker_ranged):
    """Relative extra damage from class bonuses vs this opponent."""
    atts = {int(k): v for k, v in json.loads(att_json or "{}").items()}
    arms = {int(k): v for k, v in json.loads(opp_armors_json or "{}").items()}
    base_armor = arms.get(3, 0) if attacker_ranged else arms.get(4, 0)
    base_eff = max((base_atk or 0) - base_armor, 1.0)
    gain = 0.0
    for cls, amt in atts.items():
        if cls in (3, 4):
            continue
        if cls in arms:
            eff = amt - arms[cls]
            if eff > 0:
                gain += eff
    return gain / base_eff

def expectation(subj, opp):
    gs = bonus_gain(subj["attacks"], subj["atk"], opp["armors"], subj["ranged"])
    go = bonus_gain(opp["attacks"], opp["atk"], subj["armors"], opp["ranged"])
    B = math.tanh(gs - go)
    R = rps(subj["cat"], opp["cat"])
    C = max(-1.0, min(1.0, math.log(subj["cost"] / max(opp["cost"], 1)) / math.log(3)))
    E = WEIGHTS["bonus"] * B + WEIGHTS["rps"] * R + WEIGHTS["cost"] * C
    return max(-1.0, min(1.0, E)), {"bonus": round(B, 2), "rps": round(R, 2),
                                    "cost": round(C, 2)}

def pack(row, is_unique=False, unit_class=None):
    uc = unit_class or row["unit_class_name"]
    cat = categorize(row["unit_slug"], uc, bool(row["is_ranged"]))
    speed = row["final_speed"] or 1.0
    if cat == "eagle" and speed < 1.2:
        cat = "infantry"     # eagle-classed but infantry-speed: can't play eagle
    return {
        "civ": row["civ_name"], "slug": row["unit_slug"], "name": row["unit_name"],
        "atk": row["final_attack"], "attacks": row["final_attacks_json"],
        "armors": row["final_armors_json"], "cost": cost_of(row),
        "ranged": bool(row["is_ranged"]), "speed": speed,
        "is_unique": is_unique, "cat": cat,
        "combat": prepare_combat_unit(build_combat_dict_from_ref(row)),
    }

# ---------------------------------------------------------------- main
def main():
    subj_row = get_row(SUBJECT_CIV, SUBJECT_SLUG)
    subj = pack(subj_row, "Infantry")

    opponents = []
    uniques = json.load(open(f"{REPO}/apps/video/auto/unique_units.json"))
    for u in uniques:
        if u["slug"] == SUBJECT_SLUG:
            continue
        if any(k in u["slug"] for k in NAVAL_KEYWORDS + PASSIVE_KEYWORDS):
            continue
        row = get_row(u["civ"], u["slug"])
        if row is None:
            print(f"  !! no ref row: {u['civ']} {u['slug']}", file=sys.stderr)
            continue
        opponents.append(pack(row, is_unique=True))
    for slug, canonical in STAPLES:
        civ = modal_civ(slug, canonical)
        if civ is None:
            print(f"  !! staple missing: {slug} ({canonical})", file=sys.stderr)
            continue
        row = get_row(civ, slug)
        opponents.append(pack(row, is_unique=False))

    results = []
    for opp in opponents:
        w, r1, r2, hp1, hp2 = simulate_battle(
            subj["combat"], opp["combat"], BUDGET, return_hp=True)
        S = (hp1 - hp2) * 100.0
        E, factors = expectation(subj, opp)
        # kiting: a faster ranged unit vs a melee subject — every player
        # expects the melee side to lose, bonus tables or not.
        kited = (opp["ranged"] and not subj["ranged"]
                 and opp["speed"] - subj["speed"] > -0.15)
        results.append({
            "civ": opp["civ"], "slug": opp["slug"], "name": opp["name"],
            "cat": opp["cat"], "cost": opp["cost"],
            "gold": opp["combat"].get("cost_gold") or 0,
            "is_unique": opp["is_unique"], "ranged": opp["ranged"],
            "kited": kited,
            "S": round(S, 1), "E": round(E, 2),
            "hp_left": round(hp1 * 100), "opp_hp_left": round(hp2 * 100),
            "surprise": round(S / 100.0 - E, 2), "factors": factors,
        })

    # Buckets keyed on bonus-damage direction (B) + kiting knowledge:
    #   expected win      = our bonus applies, we win big (no trash: gold=0)
    #   unexpected win    = THEY have the bonus (should counter us), we survive
    #                       and win — the closer the better
    #   expected counter  = they have the bonus / clear prior / they kite us
    #   unexpected counter= no bonus either way, straight melee brawl, and the
    #                       'safe' matchup loses anyway (hidden mechanics)
    B_T = 0.2
    B_STRONG = 0.45
    wins = [r for r in results if r["S"] > WIN_T]
    losses = [r for r in results if r["S"] < -WIN_T]
    buckets = {
        "expected_win": sorted(
            [r for r in wins if r["factors"]["bonus"] >= B_T and r["gold"] > 0],
            key=lambda r: -r["S"]),
        "unexpected_win": sorted(
            [r for r in wins if r["factors"]["bonus"] <= -B_T],
            key=lambda r: (r["factors"]["bonus"], r["S"])),
        # B_STRONG splits "dedicated counter" (big bonus: samurai, cataphract)
        # from "incidental bonus" (a few points via Infantry/Eagle/UU classes —
        # nominally a safe matchup that still loses = the upset).
        "expected_counter": sorted(
            [r for r in losses
             if r["factors"]["bonus"] <= -B_STRONG or r["E"] < -E_T or r["kited"]],
            key=lambda r: (r["S"], r["factors"]["bonus"])),
        "unexpected_counter": sorted(
            [r for r in losses
             if r["factors"]["bonus"] > -B_STRONG and not r["ranged"]
             and r["E"] >= -E_T],
            key=lambda r: -r["S"]),      # melee brawls only; narrowest loss first
    }

    def prefer_uniques(items, margin=15.0):
        """Top-3 favoring unique units; a generic takes a slot only when it
        outclasses the next unique by >= margin points of |S|."""
        picks, rest = [], list(items)
        while rest and len(picks) < 3:
            head = rest.pop(0)
            if head["is_unique"]:
                picks.append(head)
                continue
            next_uni = next((r for r in rest if r["is_unique"]), None)
            if next_uni is None or abs(head["S"]) - abs(next_uni["S"]) >= margin:
                picks.append(head)
        return picks

    def dedupe_line(items):
        seen, out = set(), []
        for r in items:
            key = r["slug"].split("_(")[0]  # ratha melee/ranged collapse
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    print(f"\n=== {subj['name']} ({SUBJECT_CIV}) vs {len(results)} opponents, "
          f"budget {BUDGET} ===")
    print(f"wins: {len(wins)}  losses: {len(losses)}  "
          f"even: {len(results) - len(wins) - len(losses)}\n")

    for cat, items in buckets.items():
        items = dedupe_line(items)
        picks = prefer_uniques(items)
        print(f"--- {cat} ({len(items)} candidates) ---")
        shown = picks + [r for r in items if r not in picks][:3]
        for r in shown:
            star = " <== PICK" if r in picks else ""
            uni = "U" if r["is_unique"] else "g"
            print(f"  {r['name']:<28} ({r['civ']:<12}) S={r['S']:>6}  "
                  f"hpL={r['hp_left']:>3}% vs {r['opp_hp_left']:>3}%  "
                  f"E={r['E']:>5}  [{uni}|{r['cat']}] B={r['factors']['bonus']} "
                  f"R={r['factors']['rps']} C={r['factors']['cost']}{star}")
        print()

    # ------- exhaustive categorization: EVERY unit lands in exactly one list
    def classify(r):
        B = r["factors"]["bonus"]
        if abs(r["S"]) <= WIN_T:
            return "even"
        if r["S"] > WIN_T:
            if B >= B_T:
                return "expected_win"
            if B <= -B_T:
                return "unexpected_win"
            return "expected_win" if r["E"] >= 0 else "unexpected_win"
        if B <= -B_STRONG or r["kited"] or r["E"] < -E_T:
            return "expected_counter"
        if not r["ranged"]:
            return "unexpected_counter"
        return "expected_counter"

    SORTS = {
        "expected_win":       lambda r: -r["S"],
        "unexpected_win":     lambda r: (r["factors"]["bonus"], r["S"]),
        "expected_counter":   lambda r: (r["S"], r["factors"]["bonus"]),
        "unexpected_counter": lambda r: -r["S"],
        "even":               lambda r: -r["S"],
    }
    full = {k: [] for k in SORTS}
    for r in results:
        full[classify(r)].append(r)

    print("=== FULL categorization (video shows top-3 fights, then this ranked list) ===")
    for cat in ("expected_win", "unexpected_win", "expected_counter",
                "unexpected_counter", "even"):
        items = sorted(full[cat], key=SORTS[cat])
        print(f"\n### {cat} — {len(items)} units")
        for i, r in enumerate(items, 1):
            rng = "rng" if r["ranged"] else "mel"
            print(f"  {i:>2}. {r['S']:>6}  B={r['factors']['bonus']:>5}  "
                  f"E={r['E']:>5}  {rng}  {r['name']} ({r['civ']})")

if __name__ == "__main__":
    main()
