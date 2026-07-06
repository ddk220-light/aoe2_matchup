"""DB-backed dry run of the unit-analysis-video classification for Elite Temple Guard.

Identical rules/constants to docs/superpowers/specs/2026-07-04-unit-analysis-video-prototype.py
(the reference implementation), but S comes from the REAL matchup baseline
C:\\AI\\matchup_baseline_177723.db (matchup_means, scale '3k') instead of local sims.
hp_left comes from the representative matchup_battles row (team1 = subject).
"""
import json
import math
import sqlite3
import sys
from collections import Counter

REPO = r"C:\dev\aoe2\aoe2_matchup"
MATCHUP_DB = r"C:\AI\matchup_baseline_177723.db"

DB = sqlite3.connect(f"{REPO}\\data\\golden\\aoe2_reference.db")
DB.row_factory = sqlite3.Row
MDB = sqlite3.connect(MATCHUP_DB)

SUBJECT_CIV, SUBJECT_SLUG = "Muisca", "elite_temple_guard_muisca"
BUDGET = 3000

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
PASSIVE_KEYWORDS = ("siege_ram", "battering_ram", "trebuchet", "petard",
                    "flaming_camel", "armored_elephant", "siege_elephant")
NAVAL_KEYWORDS = ("turtle_ship", "caravel", "longboat", "thirisadai",
                  "lou_chuan", "dromon", "galley", "cannon_galleon")
GUNPOWDER_KEYS = ("janissary", "conquistador", "organ_gun", "hand_cannoneer",
                  "hussite", "ribauldequin", "fire_thrower", "grenadier")
WEIGHTS = {"bonus": 0.5, "rps": 0.3, "cost": 0.2}
WIN_T, E_T, B_T, B_STRONG = 15.0, 0.15, 0.2, 0.45


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
        return "archer"
    return "infantry"


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
    "camel": {"elephant": .3, "cav_archer": .3, "infantry": -.3, "archer": -.3},
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


def get_row(civ, slug):
    return DB.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
        (civ, slug)).fetchone()


def modal_civ(slug, canonical_name):
    rows = DB.execute(
        "SELECT civ_name, final_hp, final_attack, final_melee_armor,"
        " final_pierce_armor, final_speed, final_attacks_json, final_armors_json,"
        " final_cost_food, final_cost_wood, final_cost_gold"
        " FROM ref_units WHERE unit_slug=? AND age='Imperial' AND unit_name=?",
        (slug, canonical_name)).fetchall()
    if not rows:
        return None
    sig, by_sig = Counter(), {}
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


def bonus_gain(att_json, base_atk, opp_armors_json, attacker_ranged):
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


def pack(row, is_unique=False):
    cat = categorize(row["unit_slug"], row["unit_class_name"], bool(row["is_ranged"]))
    speed = row["final_speed"] or 1.0
    if cat == "eagle" and speed < 1.2:
        cat = "infantry"
    return {
        "civ": row["civ_name"], "slug": row["unit_slug"], "name": row["unit_name"],
        "atk": row["final_attack"], "attacks": row["final_attacks_json"],
        "armors": row["final_armors_json"], "cost": cost_of(row),
        "gold": row["final_cost_gold"] or 0,
        "ranged": bool(row["is_ranged"]), "speed": speed,
        "is_unique": is_unique, "cat": cat,
    }


def db_margin(opp_civ, opp_slug):
    """S from matchup_means (subject-positive) + hp-left from the representative battle."""
    m = MDB.execute(
        "SELECT mean, sd, n, verdict FROM matchup_means"
        " WHERE my_civ=? AND my_slug=? AND opp_civ=? AND opp_slug=? AND scale='3k'",
        (SUBJECT_CIV, SUBJECT_SLUG, opp_civ, opp_slug)).fetchone()
    if m is None:
        return None
    b = MDB.execute(
        "SELECT team1_hp_pct, team2_hp_pct, my_count, opp_count,"
        " team1_start_count, team2_start_count FROM matchup_battles"
        " WHERE my_civ=? AND my_unit_slug=? AND opp_civ=? AND opp_unit_slug=? AND scale='3k'",
        (SUBJECT_CIV, SUBJECT_SLUG, opp_civ, opp_slug)).fetchone()
    hp1 = b[0] if b else 0.0
    hp2 = b[1] if b else 0.0
    return {"S": m[0], "sd": m[1], "n": m[2], "verdict": m[3],
            "hp1": hp1, "hp2": hp2,
            "counts": (b[4], b[5]) if b else (None, None)}


def main():
    subj = pack(get_row(SUBJECT_CIV, SUBJECT_SLUG))

    opponents, missing = [], []
    uniques = json.load(open(f"{REPO}\\apps\\video\\auto\\unique_units.json"))
    for u in uniques:
        if u["slug"] == SUBJECT_SLUG:
            continue
        if any(k in u["slug"] for k in NAVAL_KEYWORDS + PASSIVE_KEYWORDS):
            continue
        row = get_row(u["civ"], u["slug"])
        if row is None:
            missing.append(("ref", u["civ"], u["slug"]))
            continue
        opponents.append(pack(row, is_unique=True))
    for slug, canonical in STAPLES:
        civ = modal_civ(slug, canonical)
        if civ is None:
            missing.append(("staple-ref", "?", slug))
            continue
        opponents.append(pack(get_row(civ, slug), is_unique=False))

    results = []
    for opp in opponents:
        d = db_margin(opp["civ"], opp["slug"])
        if d is None:
            missing.append(("matchup-db", opp["civ"], opp["slug"]))
            continue
        S = d["S"]
        E, factors = expectation(subj, opp)
        kited = (opp["ranged"] and not subj["ranged"]
                 and opp["speed"] - subj["speed"] > -0.15)
        results.append({
            "civ": opp["civ"], "slug": opp["slug"], "name": opp["name"],
            "cat": opp["cat"], "cost": opp["cost"], "gold": opp["gold"],
            "is_unique": opp["is_unique"], "ranged": opp["ranged"], "kited": kited,
            "S": round(S, 1), "E": round(E, 2), "sd": d["sd"], "n": d["n"],
            "hp_left": round(d["hp1"] * 100), "opp_hp_left": round(d["hp2"] * 100),
            "surprise": round(S / 100.0 - E, 2), "factors": factors,
        })

    wins = [r for r in results if r["S"] > WIN_T]
    losses = [r for r in results if r["S"] < -WIN_T]
    buckets = {
        "expected_win": sorted(
            [r for r in wins if r["factors"]["bonus"] >= B_T and r["gold"] > 0],
            key=lambda r: -r["S"]),
        "unexpected_win": sorted(
            [r for r in wins if r["factors"]["bonus"] <= -B_T],
            key=lambda r: (r["factors"]["bonus"], r["S"])),
        "expected_counter": sorted(
            [r for r in losses
             if r["factors"]["bonus"] <= -B_STRONG or r["E"] < -E_T or r["kited"]],
            key=lambda r: (r["S"], r["factors"]["bonus"])),
        "unexpected_counter": sorted(
            [r for r in losses
             if r["factors"]["bonus"] > -B_STRONG and not r["ranged"]
             and r["E"] >= -E_T],
            key=lambda r: -r["S"]),
    }

    def prefer_uniques(items, margin=15.0):
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
            key = r["slug"].split("_(")[0]
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    print(f"=== {subj['name']} ({SUBJECT_CIV}) vs {len(results)} opponents, "
          f"S from matchup_baseline_177723.db @3k ===")
    print(f"wins: {len(wins)}  losses: {len(losses)}  "
          f"even: {len(results) - len(wins) - len(losses)}")
    if missing:
        print(f"MISSING ({len(missing)}): {missing}")
    print()

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
                  f"n={r['n']}{star}")
        print()

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

    print("=== FULL categorization ===")
    for cat in ("expected_win", "unexpected_win", "expected_counter",
                "unexpected_counter", "even"):
        items = sorted(full[cat], key=SORTS[cat])
        print(f"\n### {cat} — {len(items)} units")
        for i, r in enumerate(items, 1):
            rng = "rng" if r["ranged"] else "mel"
            print(f"  {i:>2}. S={r['S']:>6}  B={r['factors']['bonus']:>5}  "
                  f"E={r['E']:>5}  {rng}  {r['name']} ({r['civ']})")

    # ---- emit a storyboard-shaped JSON artifact (picks + exhaustive lists) ----
    def seg(r, cat, rank):
        return {"category": cat, "rank": rank, "opponent": {
            "civ": r["civ"], "slug": r["slug"], "name": r["name"]},
            "score": r["S"], "expectation": r["E"], "surprise": r["surprise"],
            "sd": r["sd"], "n": r["n"], "hp_left": {"subject": r["hp_left"],
            "opponent": r["opp_hp_left"]}, "factors": r["factors"]}

    # expected_counter pick rule (user 2026-07-05): a MIX, not 3 identical wipes --
    # 1 gunpowder shock + 2 iconic archer counters (the classic "archers shred
    # infantry" story). Curated trio by slug; falls back to margin sort if absent.
    COUNTER_MIX = ["grenadier_jurchens", "elite_chakram_thrower_gurjaras",
                   "elite_chu_ko_nu_chinese"]

    def pick_counter_mix(items):
        by_slug = {r["slug"]: r for r in items}
        curated = [by_slug[s] for s in COUNTER_MIX if s in by_slug]
        return curated if len(curated) == 3 else prefer_uniques(dedupe_line(items))

    segments, picks_by_cat = [], {}
    for cat in ("expected_win", "unexpected_win", "expected_counter",
                "unexpected_counter"):
        picks = (pick_counter_mix(buckets[cat]) if cat == "expected_counter"
                 else prefer_uniques(dedupe_line(buckets[cat])))
        picks_by_cat[cat] = picks
        for rank, r in enumerate(picks, 1):
            segments.append(seg(r, cat, rank))
    story = {
        "schema_version": 1, "build": "177723",
        "subject": {"civ": SUBJECT_CIV, "slug": SUBJECT_SLUG,
                    "name": subj["name"]},
        "generated": {"source": "MatchupDbSource",
                      "matchup_db": "matchup_baseline_177723.db",
                      "budget_res": BUDGET, "scale": "3k",
                      "params": {"WIN_T": WIN_T, "B_T": B_T, "B_STRONG": B_STRONG,
                                 "E_T": E_T, "OUTLIER_MARGIN": 15,
                                 "weights": WEIGHTS}},
        "segments": segments,
        "category_lists": {cat: [
            {"rank": i, "name": r["name"], "civ": r["civ"], "slug": r["slug"],
             "score": r["S"], "sd": r["sd"],
             "picked": r in picks_by_cat.get(cat, [])}
            for i, r in enumerate(sorted(full[cat], key=SORTS[cat]), 1)]
            for cat in SORTS},
        "all_results": [{"slug": r["slug"], "civ": r["civ"], "S": r["S"],
                         "E": r["E"], "surprise": r["surprise"],
                         "category": classify(r), "factors": r["factors"]}
                        for r in results],
    }
    out = (f"{REPO}\\apps\\video\\media\\units\\elite_temple_guard_muisca"
           f"\\storyboard.json")
    json.dump(story, open(out, "w"), indent=2)
    print(f"\n=== FINAL 12 PICKS (decisions applied) ===")
    for s in segments:
        print(f"  {s['category']:20s} #{s['rank']}  {s['opponent']['name']} "
              f"({s['opponent']['civ']})  S={s['score']}")
    print(f"\n[storyboard] {len(segments)} segments, "
          f"{sum(len(v) for v in story['category_lists'].values())} listed units "
          f"-> {out}")


if __name__ == "__main__":
    main()
