"""Build a unit-analysis-video storyboard: classify every opponent, pick the
top-3 per category (narrative order), emit storyboard JSON + printed summary.

Faithful productionization of the validated DB-backed dry run
(docs/superpowers/specs/2026-07-05-etg-dbsource-dryrun.py) and the locked
decisions (docs/superpowers/specs/2026-07-05-etg-picks-locked.md). The dry-run
picks + category lists are the golden target.

CLI:
  python -m aoe2x.analysis.unit_video_story Muisca elite_temple_guard_muisca \\
      --source matchup-db --matchup-db C:\\AI\\matchup_baseline_177723.db \\
      --out apps/video/media/units/elite_temple_guard_muisca/storyboard.json
  ... --source local-sim --seeds 8
"""
import argparse
import datetime
import json
import sqlite3
import sys

from aoe2x.paths import GOLDEN_DIR
from aoe2x.analysis import story_rules as SR
from aoe2x.analysis.captions import why_caption, hidden_mechanics
from aoe2x.analysis.matchup_sources import (
    BUDGET, SCALE, LocalSimSource, MatchupDbSource)
from aoe2x.analysis.opponent_pool import build_pool, load_subject

REF_DB = GOLDEN_DIR / "aoe2_reference.db"

# Narrative order of the four filmed categories (even is listed, not filmed).
CATEGORY_ORDER = ("expected_win", "unexpected_win",
                  "expected_counter", "unexpected_counter")

_MECH_COLS = ("armor_strip_per_hit", "charge_attack_melee",
              "charge_recharge_time", "bleed_dps", "bleed_duration",
              "trample_percent", "splash_on_hit_radius",
              "attack_bonus_per_kill", "dodge_shield_max")


def _class_names(db):
    return dict(db.execute("SELECT id, name FROM armor_classes"))


def _bonus_pairs(att_json, opp_armors_json, names):
    atts = {int(k): v for k, v in json.loads(att_json or "{}").items()}
    arms = {int(k): v for k, v in json.loads(opp_armors_json or "{}").items()}
    return [(names.get(c, str(c)), a) for c, a in sorted(atts.items())
            if c not in (3, 4) and c in arms and a - arms[c] > 0]


def _counts(subject, opponent, budget=BUDGET):
    """Equal-resource counts for the recorder (subject / opponent army sizes)."""
    return {"subject": max(1, round(budget / max(subject["cost"], 1))),
            "opponent": max(1, round(budget / max(opponent["cost"], 1)))}


def _evaluate(subject, opponent, source):
    """One opponent -> a full result row. Returns None if the source has no
    data for the pair (missing-pair skip; source already warned)."""
    detail = source.detail(subject, opponent)
    if detail is None:
        return None
    S = detail["S"]                          # raw multi-seed mean (subject-positive)
    E, factors = SR.expectation(subject, opponent)   # E is raw (unrounded)
    kited = (opponent["ranged"] and not subject["ranged"]
             and opponent["speed"] - subject["speed"] > -0.15)
    r = {
        "civ": opponent["civ"], "slug": opponent["slug"], "name": opponent["name"],
        "cat": opponent["cat"], "cost": opponent["cost"], "gold": opponent["gold"],
        "is_unique": opponent["is_unique"], "ranged": opponent["ranged"],
        "kited": kited,
        "S": round(S, 1), "E": round(E, 2),
        "sd": detail["sd"], "n": detail["n"],
        "hp_left": round((detail["hp1"] or 0.0) * 100),
        "opp_hp_left": round((detail["hp2"] or 0.0) * 100),
        "counts_db": detail["counts"],
        # surprise uses RAW S and RAW E (matches the dry run) — not the rounded
        # display values — so the last-digit rounding matches the golden output.
        "surprise": round(S / 100.0 - E, 2),
        "factors": factors,
    }
    r["category"] = SR.classify(r)
    return r


def _pick_for(cat, bucket):
    """Apply the per-category pick rule (dry run): expected_counter uses the
    curated gunpowder+archer MIX; every other category uses prefer_uniques over
    the deduped, pick-filtered bucket."""
    if cat == "expected_counter":
        return SR.pick_counter_mix(bucket)
    return SR.prefer_uniques(SR.dedupe_line(bucket))


def build_storyboard(subject_civ, subject_slug, source, *, build="177723",
                     matchup_db_name=None):
    with_combat = isinstance(source, LocalSimSource)
    subject = load_subject(subject_civ, subject_slug, with_combat=with_combat)
    pool = build_pool(subject_civ, subject_slug, with_combat=with_combat)

    results, missing = [], []
    for opp in pool:
        r = _evaluate(subject, opp, source)
        if r is None:
            missing.append((opp["civ"], opp["slug"]))
            continue
        results.append(r)

    # Exhaustive categorization: every measured opponent lands in exactly one.
    full = {k: [] for k in SR.SORTS}
    for r in results:
        full[r["category"]].append(r)
    lists = {k: sorted(full[k], key=SR.SORTS[k]) for k in SR.SORTS}

    # Pick buckets: the dry run's stricter filters (PICK_FILTERS) on wins/losses.
    wins = [r for r in results if r["S"] > SR.WIN_T]
    losses = [r for r in results if r["S"] < -SR.WIN_T]
    buckets = {
        "expected_win": sorted(
            [r for r in wins if SR.PICK_FILTERS["expected_win"](r)],
            key=lambda r: -r["S"]),
        "unexpected_win": sorted(
            [r for r in wins if SR.PICK_FILTERS["unexpected_win"](r)],
            key=lambda r: (r["factors"]["bonus"], r["S"])),
        "expected_counter": sorted(
            [r for r in losses if SR.PICK_FILTERS["expected_counter"](r)],
            key=lambda r: (r["S"], r["factors"]["bonus"])),
        "unexpected_counter": sorted(
            [r for r in losses if SR.PICK_FILTERS["unexpected_counter"](r)],
            key=lambda r: -r["S"]),
    }

    db = sqlite3.connect(str(REF_DB))
    db.row_factory = sqlite3.Row
    names = _class_names(db)
    by_slug = {o["slug"]: o for o in pool}

    picks_by_cat, segments, order = {}, [], 0
    for cat in CATEGORY_ORDER:
        picks = _pick_for(cat, buckets[cat])
        picks_by_cat[cat] = picks
        for rank, r in enumerate(picks, 1):
            order += 1
            opp = by_slug[r["slug"]]
            mech_row = db.execute(
                f"SELECT {', '.join(_MECH_COLS)} FROM ref_units"
                " WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
                (r["civ"], r["slug"])).fetchone()
            segments.append({
                "order": order,
                "category": cat,
                "rank": rank,
                "opponent": {"civ": r["civ"], "slug": r["slug"],
                             "name": r["name"]},
                "score": r["S"],
                "expectation": r["E"],
                "surprise": r["surprise"],
                "sd": r["sd"], "n": r["n"],
                "hp_left": {"subject": r["hp_left"], "opponent": r["opp_hp_left"]},
                "counts": _counts(subject, opp),
                "factors": r["factors"],
                "why": why_caption(
                    r, subject_name=subject["name"], opp_name=r["name"],
                    subject_bonus_vs_opp=_bonus_pairs(
                        subject["attacks"], opp["armors"], names),
                    opp_bonus_vs_subject=_bonus_pairs(
                        opp["attacks"], subject["armors"], names),
                    mechanics=hidden_mechanics(mech_row)),
            })

    pick_slugs = {r["slug"] for ps in picks_by_cat.values() for r in ps}

    generated = {
        "source": type(source).__name__,
        "budget_res": BUDGET,
        "scale": SCALE,
        "date": datetime.date.today().isoformat(),
        "params": {"WIN_T": SR.WIN_T, "B_T": SR.B_T, "B_STRONG": SR.B_STRONG,
                   "E_T": SR.E_T, "OUTLIER_MARGIN": SR.OUTLIER_MARGIN,
                   "weights": SR.WEIGHTS},
    }
    if matchup_db_name:
        generated["matchup_db"] = matchup_db_name

    story = {
        "schema_version": 1,
        "build": build,
        "subject": {
            "civ": subject_civ, "slug": subject_slug, "name": subject["name"],
            "stats": {"cost": subject["cost"], "gold": subject["gold"],
                      "speed": subject["speed"], "cat": subject["cat"],
                      "ranged": subject["ranged"]},
        },
        "generated": generated,
        "missing": [{"civ": c, "slug": s} for c, s in missing],
        "segments": segments,
        "category_lists": {
            cat: [{"rank": i, "name": r["name"], "civ": r["civ"],
                   "slug": r["slug"], "score": r["S"], "sd": r["sd"],
                   "picked": r["slug"] in pick_slugs}
                  for i, r in enumerate(items, 1)]
            for cat, items in lists.items()},
        "all_results": [{"slug": r["slug"], "civ": r["civ"], "S": r["S"],
                         "E": r["E"], "surprise": r["surprise"],
                         "category": r["category"], "factors": r["factors"]}
                        for r in results],
    }
    db.close()
    return story


def print_summary(sb):
    subj = sb["subject"]
    print(f"=== {subj['name']} ({subj['civ']}) — {len(sb['all_results'])} "
          f"opponents, source={sb['generated']['source']} @{sb['generated'].get('scale')} ===")
    counts = {}
    for r in sb["all_results"]:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    print("  " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    if sb.get("missing"):
        print(f"  MISSING ({len(sb['missing'])}): "
              + ", ".join(f"{m['civ']}/{m['slug']}" for m in sb["missing"]))
    print("\n=== FINAL 12 PICKS ===")
    for s in sb["segments"]:
        print(f"  {s['category']:20s} #{s['rank']}  {s['opponent']['name']} "
              f"({s['opponent']['civ']})  S={s['score']}")
    for cat, items in sb["category_lists"].items():
        print(f"\n### {cat} — {len(items)} units")
        for u in items:
            mark = "*" if u["picked"] else " "
            print(f"  {mark}{u['rank']:>2}. {u['score']:>6}  "
                  f"{u['name']} ({u['civ']})")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build a unit-analysis-video storyboard.")
    ap.add_argument("civ")
    ap.add_argument("slug")
    ap.add_argument("--source", choices=("local-sim", "matchup-db"),
                    default="matchup-db")
    ap.add_argument("--matchup-db")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--build", default="177723")
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    matchup_db_name = None
    if args.source == "matchup-db":
        if not args.matchup_db:
            raise SystemExit("--matchup-db required with --source matchup-db")
        source = MatchupDbSource(args.matchup_db)
        import os
        matchup_db_name = os.path.basename(args.matchup_db)
    else:
        source = LocalSimSource(seeds=tuple(range(1, args.seeds + 1)))

    sb = build_storyboard(args.civ, args.slug, source, build=args.build,
                          matchup_db_name=matchup_db_name)
    print_summary(sb)
    if args.out:
        import os
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(sb, f, indent=2)
        print(f"\n[storyboard] {len(sb['segments'])} segments, "
              f"{sum(len(v) for v in sb['category_lists'].values())} listed "
              f"units -> {args.out}")
    return sb


if __name__ == "__main__":
    main()
