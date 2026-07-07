"""Merge V2-sim / matchup-DB / in-game(showcase) results for the 4 unit-analysis
subjects into one JSON the comparison dashboard reads.

Per matchup we emit three source blocks (any may be null):
  v2     : the V2 headless sim  (sim_v2/results/<slug>.json rows)
  db     : the production position sim, equal-RESOURCES scale '3k'
           (C:/AI/matchup_baseline_177723.db matchup_battles)
  ingame : the golden-rig gRPC recording, SHOWCASE fights only
           (~/Videos/aoe2_matchups/<dir>/<filmcat>_<rank>_<oppslug>.hp.json)

HP is normalised to PERCENT of the side's starting total HP (0..100) for all three.
delta = subject_hp% - opponent_hp%  (the HP-margin the analysis cares about).
"""
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
OVERRIDES = HERE.parent / "overrides"
DB_PATH = "C:/AI/matchup_baseline_177723.db"
VID = Path(os.path.expanduser("~/Videos/aoe2_matchups"))

# subject key -> (results json stem, in-game SHOWCASE dir)
UNITS = [
    ("elite_temple_guard_muisca",  "etg_v2"),
    ("elite_kona_mapuche",         "kona_v2"),
    ("elite_blackwood_archer_tupi","blackwood_v2"),
    ("elite_guecha_warrior_muisca","guecha_v2"),
]

CAT_ORDER = ["expected_win", "unexpected_win", "coin_flip", "unexpected_loss", "expected_loss"]

# film-clip category prefix -> V2 category (for matching showcase files to rows)
FILM_TO_CAT = {
    "expected_win": "expected_win", "unexpected_win": "unexpected_win",
    "expected_counter": "expected_loss", "unexpected_counter": "unexpected_loss",
    "coin_flip": "coin_flip", "even": "coin_flip",
}
PREFIX = re.compile(
    r"^(expected_win|unexpected_win|expected_counter|unexpected_counter"
    r"|coin_flip|even|newpick|diag2?|gdiag|g2)_\d+_(.+)$")


def slug_from_hpfile(stem):
    stem = stem[:-3] if stem.endswith(".hp") else stem   # strip trailing .hp (name.hp.json)
    m = PREFIX.match(stem)
    return m.group(2) if m else None


def ingame_for_dir(dirname):
    """slug -> in-game result dict, from the showcase .hp.json files in one dir."""
    d = VID / dirname
    out = {}
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.hp.json")):
        slug = slug_from_hpfile(f.stem)
        if not slug:
            continue
        try:
            hp = json.loads(f.read_text())
            rows = hp.get("rows") or []
            if len(rows) < 2:
                continue
            s, e = rows[0], rows[-1]
            s1h, s2h = s["side1"]["hp"] or 1, s["side2"]["hp"] or 1
            subj = 100.0 * (e["side1"]["hp"] or 0) / s1h
            opp = 100.0 * (e["side2"]["hp"] or 0) / s2h
            se, oe = e["side1"]["count"], e["side2"]["count"]
            outcome = "win" if (oe == 0 and se > 0) else ("loss" if (se == 0 and oe > 0) else "coinflip")
            out[slug] = {
                "n_subject": s["side1"]["count"], "n_opp": s["side2"]["count"],
                "n_subject_end": se, "n_opp_end": oe,
                "subject_hp": round(subj, 1), "opp_hp": round(opp, 1),
                "delta": round(subj - opp, 1), "outcome": outcome,
                "file": f.name,
            }
        except Exception as ex:
            print(f"  [warn] {f.name}: {ex}", file=sys.stderr)
    return out


def db_lookup(db, my_civ, my_slug):
    """(opp_civ, opp_slug) -> db result dict, equal-RESOURCES scale '3k'."""
    out = {}
    for r in db.execute(
        """SELECT opp_civ, opp_unit_slug, my_count, opp_count, winner,
                  team1_hp_pct, team2_hp_pct, runs_count
           FROM matchup_battles
           WHERE my_civ=? AND my_unit_slug=? AND scale='3k'""",
        (my_civ, my_slug),
    ):
        subj = 100.0 * (r["team1_hp_pct"] or 0)
        opp = 100.0 * (r["team2_hp_pct"] or 0)
        out[(r["opp_civ"], r["opp_unit_slug"])] = {
            "n_subject": r["my_count"], "n_opp": r["opp_count"],
            "subject_hp": round(subj, 1), "opp_hp": round(opp, 1),
            "delta": round(subj - opp, 1),
            "outcome": "win" if r["winner"] == 1 else ("loss" if r["winner"] == 2 else "coinflip"),
            "runs": r["runs_count"],
        }
    return out


def main():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    units_out = []
    for slug, vid_dir in UNITS:
        res = json.loads((RESULTS / f"{slug}.json").read_text())
        subject = res["subject"]
        civ = subject["civ"]
        db_rows = db_lookup(db, civ, slug)
        ingame = ingame_for_dir(vid_dir)
        n_db = n_ig = 0
        matchups = []
        for r in res["rows"]:
            oc, os_, on = r["civ"], r["slug"], r.get("name")
            v2 = {
                "n_subject": r["n_subject"], "n_opp": r["n_opp"],
                "subject_hp": round(r["subject_hp"], 1), "opp_hp": round(r["opp_hp"], 1),
                "delta": round(r["subject_hp"] - r["opp_hp"], 1),
                "wr": r.get("wr"), "outcome": r.get("outcome"),
            }
            db_r = db_rows.get((oc, os_))
            ig_r = ingame.get(os_)
            if db_r:
                n_db += 1
            if ig_r:
                n_ig += 1
            matchups.append({
                "opp_civ": oc, "opp_slug": os_, "opp_name": on,
                "opp_class": r.get("class"), "category": r.get("category"),
                "v2": v2, "db": db_r, "ingame": ig_r,
            })
        # sort: category order, then in-game-present first, then V2 delta desc
        matchups.sort(key=lambda m: (
            CAT_ORDER.index(m["category"]) if m["category"] in CAT_ORDER else 9,
            0 if m["ingame"] else 1,
            -(m["v2"]["delta"]),
        ))
        units_out.append({
            "key": slug, "subject": subject,
            "counts": {"total": len(matchups), "db": n_db, "ingame": n_ig},
            "matchups": matchups,
        })
        print(f"{subject['name']:24s} {len(matchups)} matchups | db {n_db} | ingame(showcase) {n_ig}")

    payload = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "weights": {"food": 1.0, "wood": 1.0, "gold": 1.5},
        "db_scale": "3k (equal resources, 3000 weighted; cap 30)",
        "note_weights": "All four V2 tabs were re-simmed 2026-07-07 at the new weights (wood 1.0) with "
                        "the fixed sim (trample body-hull, Arambai miss-graze, CHURN 3.5->2.25 so the "
                        "Temple Guard ramp survives revive/swarm grinds — ETG-vs-Konnik now the in-game "
                        "coin-flip). The DB columns are still the OLD weights (wood 0.7) + pre-fix "
                        "production sim (a full re-sim is a separate 500k-matchup job) — so V2-vs-DB gaps "
                        "show where the fixes moved the needle.",
        "cat_order": CAT_ORDER,
        "units": units_out,
    }
    out = HERE / "dashboard_data.json"
    out.write_text(json.dumps(payload, indent=1))
    print("wrote", out, f"({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
