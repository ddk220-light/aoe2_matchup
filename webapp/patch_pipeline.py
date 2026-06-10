"""End-to-end patch pipeline. Run ONCE per new patch from the repo root:

  python -m webapp.patch_pipeline --build 177723 --release-date 2026-06-02 \
      --source-url https://www.ageofempires.com/news/...update-177723/ \
      --summary-file notes_177723.md --pypy /path/to/pypy3 \
      --matchup-db D:/AI/matchup_db.db

Steps:
  1. Archive extracted_data/ and snapshot aoe2_reference.db (the 'before').
  2. Re-extract the new .dat; rebuild ref + main DBs; re-apply surgical patches.
  3. Diff ref_units (before vs after) -> stat deltas + changed-slug set.
  4. Snapshot matchup outcomes for changed slugs (the 'before').
  5. Force re-sim only changed slugs (PyPy run_matchup_battles --force --changed-units).
  6. Diff matchup outcomes -> patch_matchup_changes.
  7. Carry forward prior-build battle_scores; re-derive land rankings + pool +
     civ_power_units at the NEW build (a complete snapshot).
  8. Diff ranking snapshots -> patch_unit_ranking. Insert patches row; flip current.
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys

_WEBAPP = os.path.dirname(__file__)
_ROOT = os.path.dirname(_WEBAPP)
# When invoked as `python -m webapp.patch_pipeline` from the repo root, only the
# root is on sys.path — add webapp/ so the bare `import patches_db` etc. resolve.
if _WEBAPP not in sys.path:
    sys.path.insert(0, _WEBAPP)
DERIVED_DB = os.path.join(_WEBAPP, "derived_data.db")
POOL_DB = os.path.join(_WEBAPP, "pool_scores.db")
REF_DB = os.path.join(_WEBAPP, "aoe2_reference.db")
PATCHES_DB = os.path.join(_WEBAPP, "patches.db")
EXTRACTED = os.path.join(_ROOT, "extraction", "extracted_data")
EXTRACTED_PREV = os.path.join(_ROOT, "extraction", "extracted_data_prev")
REF_PREV = os.path.join(_WEBAPP, "aoe2_reference_prev.db")


def carry_forward_battle_scores(derived_db_path, old_build, new_build):
    """Copy every old-build battle_scores row to new_build (idempotent).

    Ensures the new build is a COMPLETE snapshot before re-derivation overwrites
    the land rows it owns; naval/siege rows (written by other pipelines and not
    re-derived) survive."""
    conn = sqlite3.connect(derived_db_path)
    conn.execute(
        "INSERT OR REPLACE INTO battle_scores "
        "(line_slug, age, civ_name, unit_slug, score_type, score_value, rank, "
        " median_delta, build_number) "
        "SELECT line_slug, age, civ_name, unit_slug, score_type, score_value, "
        " rank, median_delta, ? FROM battle_scores WHERE build_number=?",
        (new_build, old_build))
    conn.commit(); conn.close()


def write_patch_records(conn, patch_id, *, unit_changes, ranking_changes, matchup_changes):
    for d in unit_changes:
        conn.execute(
            "INSERT INTO patch_unit_changes (patch_id, civ_name, unit_slug, field, "
            "old_value, new_value, note) VALUES (?,?,?,?,?,?,?)",
            (patch_id, d["civ_name"], d["unit_slug"], d["field"],
             d.get("old_value"), d.get("new_value"), d.get("note")))
    for d in ranking_changes:
        conn.execute(
            "INSERT INTO patch_unit_ranking (patch_id, civ_name, unit_slug, "
            "score_type, old_score, new_score, old_rank, new_rank) VALUES (?,?,?,?,?,?,?,?)",
            (patch_id, d["civ_name"], d["unit_slug"], d["score_type"],
             d.get("old_score"), d.get("new_score"), d.get("old_rank"), d.get("new_rank")))
    for d in matchup_changes:
        conn.execute(
            "INSERT INTO patch_matchup_changes (patch_id, my_civ, my_unit_slug, "
            "opp_civ, opp_unit_slug, scale, old_winner, new_winner, old_score, "
            "new_score, swing) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (patch_id, d["my_civ"], d["my_unit_slug"], d["opp_civ"], d["opp_unit_slug"],
             d["scale"], d["old_winner"], d["new_winner"], d["old_score"],
             d["new_score"], d["swing"]))


def _run(cmd, **kw):
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, **kw)


def run(*, build, release_date, source_url, summary_md, baseline_build,
        pypy, matchup_db):
    import patches_db, ref_diff, matchup_diff

    # 1. Archive + snapshot the 'before'
    if os.path.isdir(EXTRACTED):
        if os.path.isdir(EXTRACTED_PREV):
            shutil.rmtree(EXTRACTED_PREV)
        shutil.copytree(EXTRACTED, EXTRACTED_PREV)
    shutil.copyfile(REF_DB, REF_PREV)
    print("[1/8] Archived extracted_data + aoe2_reference.db (before).")

    # 2. Re-extract + rebuild
    _run([sys.executable, "-m", "extraction.run"], cwd=_ROOT)
    _run([sys.executable, "-m", "analysis.generate_reference"], cwd=_ROOT)
    _run([sys.executable, "-m", "analysis.generate_main_db"], cwd=_ROOT)
    _run([sys.executable, os.path.join("analysis", "patches",
          "patch_mayan_archer_cost.py")], cwd=_ROOT)
    print("[2/8] Re-extracted + rebuilt ref/main DBs.")

    # 3. ref_units diff
    deltas, changed_slugs = ref_diff.diff(REF_PREV, REF_DB)
    print(f"[3/8] {len(deltas)} stat deltas across {len(changed_slugs)} changed slugs:"
          f" {sorted(changed_slugs)}")
    if not changed_slugs:
        print("[3/8] WARNING: no unit stat changes detected. If you expected combat "
              "changes, verify the new .dat is actually the new patch. Continuing — "
              "the patch will still be recorded (notes only, no re-sim impact).")
    cu_file = os.path.join(_WEBAPP, f"changed_units_{build}.json")
    with open(cu_file, "w") as f:
        json.dump(sorted(changed_slugs), f)

    # 4. Snapshot before-outcomes
    before = matchup_diff.snapshot(matchup_db, changed_slugs)
    print(f"[4/8] Snapshotted {len(before)} before-outcomes.")

    # 5. Force re-sim changed slugs (PyPy)
    _run([pypy, "-m", "webapp.run_matchup_battles", "--force",
          "--changed-units", cu_file, "--db", matchup_db], cwd=_ROOT)
    print("[5/8] Re-sim complete.")

    # 6. Matchup diff
    matchup_changes = matchup_diff.diff_outcomes(before, matchup_db, changed_slugs)
    print(f"[6/8] {len(matchup_changes)} matchup changes.")

    # 7. Carry forward + re-derive at NEW build
    carry_forward_battle_scores(DERIVED_DB, baseline_build, build)
    # --allow-stale: the scoped --changed-units re-sim above legitimately
    # leaves the matchup DB at mixed sim_versions when the engine changed.
    _run([sys.executable, "-m", "webapp.derive_unit_rankings",
          "--matchup-db", matchup_db, "--build", build, "--allow-stale"], cwd=_ROOT)
    _run([sys.executable, "-m", "webapp.derive_pool_scores",
          "--matchup-db", matchup_db, "--out", POOL_DB, "--build", build,
          "--allow-stale"], cwd=_ROOT)
    # civ_power_units for the new build (best_units reads current build; set it first)
    pconn = patches_db.create_db(PATCHES_DB)
    pid = patches_db.insert_patch(pconn, build_number=build, release_date=release_date,
        title=f"Update {build}", summary_md=summary_md, source_url=source_url,
        baseline_build=baseline_build, is_current=0, created_at=release_date)
    patches_db.set_current_build(pconn, build)
    pconn.commit(); pconn.close()
    _run([sys.executable, "-c",
          "import sys; sys.path.insert(0, 'webapp'); import best_units; "
          f"best_units.save_civ_power_units('{build}')"], cwd=_ROOT)
    print("[7/8] Re-derived rankings/pool/power-units at new build.")

    # 8. Ranking diff + write records
    ranking_changes = matchup_diff.diff_rankings(DERIVED_DB, baseline_build, build,
                                                 changed_slugs)
    pconn = patches_db.create_db(PATCHES_DB)
    pid = patches_db.patch_id_for(pconn, build)
    # clear any prior run's records for this patch (idempotent re-run)
    for t in ("patch_unit_changes", "patch_unit_ranking", "patch_matchup_changes"):
        pconn.execute(f"DELETE FROM {t} WHERE patch_id=?", (pid,))
    write_patch_records(pconn, pid, unit_changes=deltas,
                        ranking_changes=ranking_changes, matchup_changes=matchup_changes)
    pconn.commit(); pconn.close()
    print(f"[8/8] Wrote patch {build}: {len(deltas)} stat deltas, "
          f"{len(ranking_changes)} ranking moves, {len(matchup_changes)} matchup flips.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--build", required=True)
    p.add_argument("--release-date", required=True)
    p.add_argument("--source-url", required=True)
    p.add_argument("--summary-file", required=True,
                   help="Path to a file with the user-pasted relevant patch notes (markdown).")
    p.add_argument("--baseline-build", default=None,
                   help="Defaults to the current build in patches.db.")
    p.add_argument("--pypy", default="pypy3",
                   help="pypy3 executable (default: 'pypy3' on PATH).")
    p.add_argument("--matchup-db", required=True, help="Path to the (local) matchup_db.db.")
    a = p.parse_args()
    import patches_db
    baseline = a.baseline_build or patches_db.get_current_build(patches_db_path=PATCHES_DB)
    if not baseline:
        sys.exit("ERROR: no baseline build found. Run `python webapp/migrate_baseline.py` "
                 "first (it seeds patches.db with the 170934 baseline), or pass "
                 "--baseline-build explicitly.")
    with open(a.summary_file, encoding="utf-8") as f:
        summary_md = f.read()
    run(build=a.build, release_date=a.release_date, source_url=a.source_url,
        summary_md=summary_md, baseline_build=baseline, pypy=a.pypy,
        matchup_db=a.matchup_db)


if __name__ == "__main__":
    main()
