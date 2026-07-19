"""Build the V2 categorization for a unit-analysis video, end to end.

Three stages, each writable/resumable via --stage:

  extract   : build the opponent pool + arena counts + combat dicts (Python;
              reads data/golden/aoe2_reference.db, optionally a matchup baseline DB).
              -> <workdir>/pool_meta.json, <workdir>/combat_dicts_all.json
  simulate  : run the position-aware V2 sim (Node; run_pool_v2.js -> sim_v2_model.js
              -> the webapp simulate.js) for the subject vs every opponent.
              -> <workdir>/v2_slice_*.json
  categorize: apply the finalized rules (aoe2x.analysis.story_rules_v2) + showcase
              selection, honoring the per-subject overrides file.
              -> <workdir>/categorized.json, categorized.md, storyboard.json

Usage:
  python apps/video/sim_v2/build_v2_categorization.py \
      Muisca elite_temple_guard_muisca \
      --overrides apps/video/sim_v2/overrides/elite_temple_guard_muisca.json \
      --matchup-db C:/AI/matchup_baseline_177723.db \
      --workdir <dir>            # defaults to <this dir>/_work/<slug>
      --stage all                # or: extract | simulate | categorize
      --jobs 4                   # parallel Node sim processes (simulate stage)

The METHOD (V2 sim knobs, categorization scheme, showcase rule) lives in code:
  sim: apps/video/sim_v2/sim_v2_model.js + headless_sim.js + run_pool_v2.js
  rules: aoe2x/analysis/story_rules_v2.py
Per-subject curation (which elephant to use, in-game overrides, showcase excludes)
lives in the overrides JSON — see overrides/elite_temple_guard_muisca.json.
"""
import argparse
import glob
import json
import os
import subprocess
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]                       # apps/video/sim_v2 -> repo root
sys.path.insert(0, str(REPO))

from aoe2x.paths import GOLDEN_DIR                                    # noqa: E402
from aoe2x.analysis import story_rules_v2 as SR                      # noqa: E402
from aoe2x.analysis.opponent_pool import build_pool, load_subject    # noqa: E402
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref  # noqa: E402

REF_DB = GOLDEN_DIR / "aoe2_reference.db"
RES_BUDGET = 3000.0        # equal-resource budget (matches the recorder / DB scale)
UNIT_CAP = 21              # golden-template MAX_COUNT; cheaper unit capped here
SHOWCASE_MAX = 5


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #
def _ref():
    db = sqlite3.connect(str(REF_DB))
    db.row_factory = sqlite3.Row
    return db


def _ref_row(db, civ, slug):
    return db.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
        (civ, slug)).fetchone()


# Units the game trains in a BATCH — the dat's listed cost buys `batch` units, so the
# per-unit cost is cost/batch. This is NOT the same as half-population: the Blackwood
# Archer trains 2 per order (its 35W/45G is a per-PAIR price) AND is 0.5-pop, but the
# Karambit Warrior is 0.5-pop yet trains one at a time (its 25F/15G is already per-unit),
# so batch must come from this explicit allowlist, not from pop_space. Kept in lockstep
# with the recorder's TRAIN_BATCH (apps/video/overlay/overlay_data.py).
TRAIN_BATCH = {
    "blackwood_archer_tupi": 2,
    "elite_blackwood_archer_tupi": 2,
}


def _batch(row):
    try:
        slug = row["unit_slug"]
    except (KeyError, IndexError):
        slug = None
    return TRAIN_BATCH.get(slug, 1)


def weighted_cost(row):
    """Resource-weighted PER-UNIT cost used for equal-resource army sizing (food 1.0,
    wood 1.0, gold 1.5, then /batch for pair-trained units) — matches the recorder's
    equal_resource_counts weights (overlay_data.COST_WEIGHT_*)."""
    return (((row["final_cost_food"] or 0) * 1.0
            + (row["final_cost_wood"] or 0) * 1.0
            + (row["final_cost_gold"] or 0) * 1.5) / _batch(row))


def combat_dict(db, civ, slug):
    """Exactly what /api/ref/combat-unit serves, plus the fields the V2 harness /
    categorizer need (name, civ, total_cost, outline_size)."""
    row = _ref_row(db, civ, slug)
    if row is None:
        raise SystemExit(f"no Imperial ref row for {civ}/{slug}")
    d = build_combat_dict_from_ref(row)
    d["name"] = row["unit_name"]
    d["civ"] = civ
    d["total_cost"] = (((row["final_cost_food"] or 0) + (row["final_cost_wood"] or 0)
                       + (row["final_cost_gold"] or 0)) / _batch(row))
    d["outline_size"] = row["outline_size_x"] or 0.2
    return d


def arena_counts(subject_wc, opp_wc):
    """equal_resource_counts (apps/video/auto/pure.py) with cap 21: the cheaper
    unit gets min(cap, budget//cost); the pricier is rescaled to the same spend."""
    if subject_wc <= opp_wc:
        n1 = max(1, min(UNIT_CAP, int(RES_BUDGET // subject_wc)))
        return n1, max(1, int(n1 * subject_wc // opp_wc))
    n2 = max(1, min(UNIT_CAP, int(RES_BUDGET // opp_wc)))
    return max(1, int(n2 * opp_wc // subject_wc)), n2


def load_overrides(path):
    if not path:
        return {}
    return json.loads(Path(path).read_text())


def _key(civ, slug):
    return f"{civ}/{slug}"


# --------------------------------------------------------------------------- #
# stage: extract
# --------------------------------------------------------------------------- #
def stage_extract(subject_civ, subject_slug, workdir, overrides, matchup_db=None):
    db = _ref()
    remove = {tuple(k.split("/", 1)) for k in overrides.get("remove", [])}
    add = [tuple(k.split("/", 1)) for k in overrides.get("add", [])]
    extras = {tuple(k.split("/", 1)) for k in overrides.get("extra_results", {})}

    subj_row = _ref_row(db, subject_civ, subject_slug)
    if subj_row is None:
        raise SystemExit(f"subject {subject_civ}/{subject_slug} not in ref DB")
    subj_wc = weighted_cost(subj_row)

    pool = [(p["civ"], p["slug"]) for p in build_pool(subject_civ, subject_slug)
            if (p["civ"], p["slug"]) not in remove]
    for civ, slug in add:
        if (civ, slug) not in pool:
            pool.append((civ, slug))

    subj_key = _key(subject_civ, subject_slug)
    combat = {subj_key: combat_dict(db, subject_civ, subject_slug)}
    meta = []
    mdb = None
    if matchup_db and Path(matchup_db).exists():
        mdb = sqlite3.connect(matchup_db)
        mdb.row_factory = sqlite3.Row

    def db_column(civ, slug):
        if mdb is None:
            return None
        m = mdb.execute(
            "SELECT mean,sd,n,verdict FROM matchup_means WHERE my_civ=? AND my_slug=? "
            "AND opp_civ=? AND opp_slug=? AND scale='3k'",
            (subject_civ, subject_slug, civ, slug)).fetchone()
        b = mdb.execute(
            "SELECT my_count,opp_count,team1_hp_pct,team2_hp_pct FROM matchup_battles "
            "WHERE my_civ=? AND my_unit_slug=? AND opp_civ=? AND opp_unit_slug=? AND scale='3k'",
            (subject_civ, subject_slug, civ, slug)).fetchone()
        if m is None or b is None:
            return None
        return {"mean": m["mean"], "sd": m["sd"], "n": m["n"], "verdict": m["verdict"],
                "my_count": b["my_count"], "opp_count": b["opp_count"],
                "hp1": b["team1_hp_pct"], "hp2": b["team2_hp_pct"]}

    # A tiny repack so pool_meta carries cat/ranged (categorize reads them from the
    # sim rows, which run_pool copies from here).
    packed = {(p["civ"], p["slug"]): p
              for p in build_pool(subject_civ, subject_slug)}
    for civ, slug in add:
        if (civ, slug) not in packed:
            packed[(civ, slug)] = load_subject(civ, slug)

    for civ, slug in pool:
        opp_row = _ref_row(db, civ, slug)
        if opp_row is None:
            print(f"[extract] WARNING no ref row for {civ}/{slug}; skipping", file=sys.stderr)
            continue
        n_subject, n_opp = arena_counts(subj_wc, weighted_cost(opp_row))
        k = _key(civ, slug)
        if k not in combat:
            combat[k] = combat_dict(db, civ, slug)
        p = packed[(civ, slug)]
        meta.append({"civ": civ, "slug": slug, "name": p.get("name"),
                     "cat": p["cat"], "ranged": p["ranged"],
                     "n_subject": n_subject, "n_opp": n_opp,
                     "db": db_column(civ, slug)})

    # extra_results matchups are NOT simmed by the batch, but their combat dict is
    # still needed so categorize can read their stats.
    for civ, slug in extras:
        k = _key(civ, slug)
        if k not in combat:
            combat[k] = combat_dict(db, civ, slug)

    Path(workdir).mkdir(parents=True, exist_ok=True)
    (Path(workdir) / "pool_meta.json").write_text(json.dumps(meta, indent=1))
    (Path(workdir) / "combat_dicts_all.json").write_text(json.dumps(combat))
    print(f"[extract] pool={len(meta)} combat_dicts={len(combat)} "
          f"extras={len(extras)} subject_wc={subj_wc:.1f} -> {workdir}")


# --------------------------------------------------------------------------- #
# stage: simulate (drives Node)
# --------------------------------------------------------------------------- #
def stage_simulate(subject_civ, subject_slug, workdir, jobs=1, escalate_abs=33):
    meta = json.loads((Path(workdir) / "pool_meta.json").read_text())
    n = len(meta)
    # clear stale slices so a re-run doesn't merge old results
    for f in glob.glob(str(Path(workdir) / "v2_slice_*.json")):
        os.remove(f)
    base_env = dict(os.environ)
    base_env["SUBJECT"] = _key(subject_civ, subject_slug)
    base_env["WORKDIR"] = str(workdir)
    base_env["ESCALATE_ABS"] = str(escalate_abs)
    jobs = max(1, jobs)
    size = -(-n // jobs)                       # ceil division -> slice size
    procs = []
    for j in range(jobs):
        start = j * size
        if start >= n:
            break
        env = dict(base_env, START=str(start), COUNT=str(min(size, n - start)))
        procs.append(subprocess.Popen(["node", "run_pool_v2.js"], cwd=str(HERE), env=env))
    rc = 0
    for p in procs:
        rc = p.wait() or rc
    if rc != 0:
        raise SystemExit(f"[simulate] node run_pool_v2.js exited {rc}")
    print(f"[simulate] {n} matchups over {len(procs)} job(s) -> v2_slice_*.json")


# --------------------------------------------------------------------------- #
# stage: categorize
# --------------------------------------------------------------------------- #
def _sim_get(row, *names):
    """Read a sim-row field tolerant of the old etg_* names (for legacy slices)."""
    for nm in names:
        if nm in row:
            return row[nm]
    raise KeyError(names)


def stage_categorize(subject_civ, subject_slug, workdir, overrides, *,
                     melee_only=True):
    workdir = Path(workdir)
    combat = json.loads((workdir / "combat_dicts_all.json").read_text())
    subj_key = _key(subject_civ, subject_slug)
    cdS = combat[subj_key]

    # subject descriptor: cat/ranged from the ref packing (so its broad class is
    # right for any subject), stats from the combat dict (the exact served values).
    subj_pack = load_subject(subject_civ, subject_slug)
    subject = SR.make_subject(subj_pack["cat"], subj_pack["ranged"],
                              cdS["movement_speed"], cdS["attacks_json"], cdS["armors_json"])
    subj_name = cdS.get("name", subject_slug)

    # gather sim rows (batch slices + spliced extra_results)
    sim = {}
    for f in sorted(glob.glob(str(workdir / "v2_slice_*.json"))):
        for r in json.loads(Path(f).read_text()):
            sim[(r["civ"], r["slug"])] = r
    for k, r in overrides.get("extra_results", {}).items():
        civ, slug = k.split("/", 1)
        sim[(civ, slug)] = dict(r, civ=civ, slug=slug)
    for k in overrides.get("remove", []):
        civ, slug = k.split("/", 1)
        sim.pop((civ, slug), None)

    ingame = overrides.get("ingame_outcome", {})
    exclude = [tuple(k.split("/", 1)) for k in overrides.get("exclude_showcase", [])]

    rows = []
    for (civ, slug), r in sim.items():
        u = combat[_key(civ, slug)]
        wr = _sim_get(r, "subject_winrate", "etg_winrate")
        shp = _sim_get(r, "subject_hp", "etg_hp")
        ohp = _sim_get(r, "opp_hp")
        c = SR.classify(
            subject, cat=r["cat"], ranged=r["ranged"], speed=u["movement_speed"],
            attacks=u["attacks_json"], armors=u["armors_json"],
            subject_winrate=wr, subject_hp=shp, opp_hp=ohp,
            ingame_outcome=ingame.get(_key(civ, slug)), melee_only=melee_only)
        rows.append({
            "civ": civ, "slug": slug, "name": r.get("name") or u.get("name"),
            "cat": r["cat"], "class": c["class"], "cost": u["total_cost"],
            "n_subject": _sim_get(r, "n_subject", "n_etg"),
            "n_opp": r["n_opp"], "subject_hp": shp, "opp_hp": ohp,
            "mean_S": r["mean_S"], "wr": wr, "bimodal": r.get("bimodal", False),
            "outcome": c["outcome"], "favored": c["favored"], "category": c["category"],
            "ingame": _key(civ, slug) in ingame,
            "subject_bonus": c["subject_bonus"], "subject_counter": c["subject_counter"],
            "opp_bonus": c["opp_bonus"], "opp_counter": c["opp_counter"],
        })

    rows = SR.sort_rows(rows)
    # showcase_override (per-subject curation, like the ETG "controlled showcase"):
    # an explicit {v2_category: [[civ, slug], ...]} that REPLACES the automatic
    # cheapest/most-expensive pick so the video can feature specific recorded fights.
    # Each pick keeps whatever category its row resolved to (after ingame_outcome), so
    # place a unit under the category key it actually belongs to.
    sc_override = overrides.get("showcase_override")
    if sc_override:
        by_key = {(r["civ"], r["slug"]): r for r in rows}
        showcase, missing = {}, []
        for cat in SR.CATEGORY_ORDER:
            picks = []
            for p in sc_override.get(cat, []):
                key = tuple(p)
                if key in by_key:
                    picks.append(by_key[key])
                else:
                    missing.append((cat, "/".join(key)))
            showcase[cat] = picks
        if missing:
            print(f"[categorize] WARNING showcase_override keys not found in rows: "
                  f"{missing}", file=sys.stderr)
    else:
        showcase = SR.pick_showcase(rows, max_per_cat=SHOWCASE_MAX, exclude=exclude)
    show_keys = {(r["civ"], r["slug"]) for cat in showcase for r in showcase[cat]}

    out = {
        "subject": {"civ": subject_civ, "slug": subject_slug, "name": subj_name},
        "params": {"win_rate": SR.WIN_RATE, "loss_rate": SR.LOSS_RATE,
                   "win_hp_min": SR.WIN_HP_MIN, "bonus_min": SR.BONUS_MIN,
                   "melee_only": melee_only, "showcase_max": SHOWCASE_MAX},
        "counts": {cat: sum(1 for r in rows if r["category"] == cat)
                   for cat in SR.CATEGORY_ORDER},
        "rows": rows,
        "showcase": {cat: [(r["civ"], r["slug"]) for r in showcase[cat]]
                     for cat in SR.CATEGORY_ORDER},
    }
    (workdir / "categorized.json").write_text(json.dumps(out, indent=1))
    (workdir / "categorized.md").write_text(
        _render_md(subj_name, rows, showcase, show_keys, exclude), encoding="utf-8")
    _write_storyboard(workdir, subject_civ, subject_slug, subj_name, rows, showcase)

    dist = "  ".join(f"{cat}={out['counts'][cat]}" for cat in SR.CATEGORY_ORDER)
    print(f"[categorize] {subj_name}: {dist}")
    print(f"[categorize] -> {workdir/'categorized.md'}, categorized.json, storyboard.json")
    return out


# --- markdown deliverable (the human-readable segmentation report) ----------- #
CN = {"expected_win": "EXPECTED WIN", "unexpected_win": "UNEXPECTED WIN",
      "coin_flip": "COIN FLIP", "unexpected_loss": "UNEXPECTED LOSS",
      "expected_loss": "EXPECTED LOSS"}


def _render_md(subj, rows, showcase, show_keys, exclude):
    exclude = {tuple(e) for e in exclude}
    md = [f"# {subj} — V2 categorization", "",
          "**Outcome** (V2 model, arena counts): **Win** = subject win-rate ≥80% and "
          "the subject keeps >5% army HP; **Loss** = win-rate ≤20% and the opponent keeps "
          ">5%; **Coin-flip** = the rest (contested win-rate, or the winner too thin).", "",
          "**Expected vs unexpected** — who is FAVORED decides, by cascade: only-subject bonus "
          "→ subject; only-opponent bonus → opponent; both → 'both' (always unexpected); neither "
          "→ the normal-counter class decides. Win + subject/neither = expected win; win + "
          "opp/both = unexpected win; loss + opp/neither = expected loss; loss + subject/both = "
          "unexpected loss.", "",
          "**Melee-gated bonus:** a melee subject's damage bonus only counts vs opponents it can "
          "catch; against ranged/kiting units the on-paper bonus is ignored and the counter class "
          "decides.", "",
          "Counter triangle: infantry↩{cav,inf}, ranged↩{inf,ranged}, cav↩{ranged,cav}. "
          "`Sb`=subject usable bonus vs opp · `Sc`=subject counters opp · `Ob`=opp bonus vs "
          "subject · `Oc`=opp counters subject.", "",
          "## Showcase picks (≤5 per category — wins: most expensive; losses: cheapest the "
          "subject loses to; coin-flips: none, listed with odds)",
          "| Category | # in cat | Showcase units (cost) |", "|---|--|---|"]
    for cat in SR.CATEGORY_ORDER:
        cnt = sum(1 for r in rows if r["category"] == cat)
        if cat == "coin_flip":
            md.append(f"| **{CN[cat]}** | {cnt} | *(no showcase — see odds below)* |")
            continue
        picks = ", ".join(f"{r['name']} ({r['cost']:.0f})" for r in showcase[cat]) or "—"
        md.append(f"| **{CN[cat]}** | {cnt} | {picks} |")

    coinflips = [r for r in rows if r["category"] == "coin_flip"]
    md += ["", "### Coin-flip matchups — odds (subject win% : opp win%), listed at the end",
           "", "| Matchup | subject : opp | S |", "|---|--|--|"]
    for r in sorted(coinflips, key=lambda r: -r["wr"]):
        md.append(f"| {r['name']} ({r['civ']}) | **{r['wr']*100:.0f}% : "
                  f"{100-r['wr']*100:.0f}%** | {r['mean_S']:+.0f} |")

    md += ["", "**Bold** rows are the showcase picks. `(x)` = excluded from showcase. "
           "`(in-game)` = category set from multi-run in-game recordings, overriding V2.", "",
           f"## Full table ({len(rows)} opponents)", "",
           "| # | Opponent | Class | Cnt | subj hp% | opp hp% | S | wr | Sb Sc Ob Oc | Category |",
           "|--|---|---|--|--|--|--|--|--|---|"]
    for i, r in enumerate(rows, 1):
        flags = " ".join("Y" if r[f] else "·" for f in
                         ("subject_bonus", "subject_counter", "opp_bonus", "opp_counter"))
        tag = "(x) " if (r["civ"], r["slug"]) in exclude else ""
        nm = f"{tag}{r['name']}{' (in-game)' if r['ingame'] else ''} ({r['civ']})"
        if (r["civ"], r["slug"]) in show_keys:
            nm = f"**{nm}**"
        md.append(f"| {i} | {nm} | {r['class']} | {r['n_subject']}v{r['n_opp']} | "
                  f"{r['subject_hp']:.0f} | {r['opp_hp']:.0f} | {r['mean_S']:+.0f} | "
                  f"{r['wr']*100:.0f}% | {flags} | {CN[r['category']]} |")
    return "\n".join(md)


# --- storyboard bridge (feeds apps/video/auto/run_unit_analysis_video.py) ----- #
# The recorder films four categories + lists "even". Map the V2 categories onto
# the recorder's keys; coin-flips become the listed-only "even" group.
FILM_CATEGORY = {"expected_win": "expected_win", "unexpected_win": "unexpected_win",
                 "unexpected_loss": "unexpected_counter", "expected_loss": "expected_counter",
                 "coin_flip": "even"}


def _why(r, subj):
    if r["category"] == "expected_win":
        return (f"{subj}'s bonus damage shreds the {r['name']}." if r["subject_bonus"]
                else f"{subj} out-classes the {r['name']}.")
    if r["category"] == "unexpected_win":
        return f"{subj} wins despite the {r['name']}'s advantage."
    if r["category"] == "expected_loss":
        return (f"The {r['name']}'s bonus damage overwhelms {subj}." if r["opp_bonus"]
                else f"The {r['name']} counters {subj}.")
    if r["category"] == "unexpected_loss":
        return f"{subj} loses despite its advantage — the {r['name']} over-performs."
    return f"{subj} vs the {r['name']} is a coin flip."


def _write_storyboard(workdir, civ, slug, subj_name, rows, showcase):
    subject = {"civ": civ, "slug": slug, "name": subj_name}
    segments, order = [], 0
    category_lists = {v: [] for v in set(FILM_CATEGORY.values())}
    for cat in SR.CATEGORY_ORDER:
        film = FILM_CATEGORY[cat]
        for rank, r in enumerate([x for x in rows if x["category"] == cat], 1):
            category_lists[film].append({
                "rank": rank, "name": r["name"], "civ": r["civ"], "slug": r["slug"],
                "score": r["mean_S"], "sd": 0,
                "picked": (r["civ"], r["slug"]) in
                          {(s["civ"], s["slug"]) for s in showcase.get(cat, [])}})
        for rank, r in enumerate(showcase.get(cat, []), 1):
            order += 1
            segments.append({
                "order": order, "category": film, "rank": rank,
                "opponent": {"civ": r["civ"], "slug": r["slug"], "name": r["name"]},
                "score": r["mean_S"],
                "counts": {"subject": r["n_subject"], "opponent": r["n_opp"]},
                "why": _why(r, subj_name)})
    story = {"schema_version": 2, "source": "sim_v2",
             "subject": {**subject, "stats": {}},
             "segments": segments, "category_lists": category_lists,
             # all_results = every ranked opponent (drives the intro "N matchups
             # ranked" subtitle in stitch_analysis).
             "all_results": [{"slug": r["slug"], "civ": r["civ"], "S": r["mean_S"],
                              "category": r["category"]} for r in rows],
             "missing": []}
    (Path(workdir) / "storyboard.json").write_text(json.dumps(story, indent=2))


# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("civ")
    ap.add_argument("slug")
    ap.add_argument("--overrides")
    ap.add_argument("--matchup-db")
    ap.add_argument("--workdir")
    ap.add_argument("--stage", choices=("extract", "simulate", "categorize", "all"),
                    default="all")
    ap.add_argument("--jobs", type=int, default=1, help="parallel Node sim processes")
    ap.add_argument("--no-melee-gate", action="store_true",
                    help="count subject bonuses even vs ranged/kiting opponents")
    args = ap.parse_args(argv)

    workdir = Path(args.workdir) if args.workdir else HERE / "_work" / args.slug
    overrides = load_overrides(args.overrides)
    melee_only = not args.no_melee_gate

    if args.stage in ("extract", "all"):
        stage_extract(args.civ, args.slug, workdir, overrides, matchup_db=args.matchup_db)
    if args.stage in ("simulate", "all"):
        stage_simulate(args.civ, args.slug, workdir, jobs=args.jobs)
    if args.stage in ("categorize", "all"):
        stage_categorize(args.civ, args.slug, workdir, overrides, melee_only=melee_only)


if __name__ == "__main__":
    main()
