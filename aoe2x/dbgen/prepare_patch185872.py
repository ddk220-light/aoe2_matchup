"""Prepare local patch data and a baseline diff; never run simulations or publish.

Example (output belongs in ignored generated storage)::

    python -m aoe2x.dbgen.prepare_patch185872 --dat <installed.dat> \
        --output-dir data/local/generated/patch-185872
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
import json
from pathlib import Path
import sqlite3

from aoe2x.paths import GOLDEN_DIR


KEY_FIELDS = ("civ_name", "unit_slug", "age")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        return {tuple(row[k] for k in KEY_FIELDS): dict(row)
                for row in db.execute("SELECT * FROM ref_units")}


def _equal(before, after):
    if isinstance(before, (float, int)) and isinstance(after, (float, int)):
        return abs(before - after) < 0.0001
    if isinstance(before, str) and isinstance(after, str):
        try:
            return json.loads(before) == json.loads(after)
        except (ValueError, TypeError):
            pass
    return before == after


def compare_references(baseline, candidate):
    """Compare stable civ/slug/age identities, not rebuild-dependent row IDs."""
    before, after = _rows(baseline), _rows(candidate)
    changed = []
    for key in sorted(before.keys() & after.keys()):
        old, new = before[key], after[key]
        changes = {field: {"before": old.get(field), "after": new.get(field)}
                   for field in sorted(old.keys() | new.keys())
                   if field != "id" and not _equal(old.get(field), new.get(field))}
        if changes:
            no_net = [field.removeprefix("base_") for field in changes
                      if field.startswith("base_")
                      and "final_" + field[5:] in new
                      and _equal(old.get("final_" + field[5:]), new["final_" + field[5:]])]
            changed.append({**dict(zip(KEY_FIELDS, key)), "unit_name": new.get("unit_name"),
                            "changes": changes, "unchanged_final_stats": no_net})
    return {
        "baseline_rows": len(before), "candidate_rows": len(after),
        "baseline_civilizations": len({k[0] for k in before}),
        "candidate_civilizations": len({k[0] for k in after}),
        "added": [after[k] for k in sorted(after.keys() - before.keys())],
        "removed": [before[k] for k in sorted(before.keys() - after.keys())],
        "changed": changed,
    }


def _audit_rows(path):
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute("""SELECT u.civ_name,u.unit_slug,u.age,t.*
            FROM ref_techs_applied t JOIN ref_units u ON u.id=t.ref_unit_id
            ORDER BY u.civ_name,u.unit_slug,t.id""")]


def _write_report(path, diff):
    lines = ["# Build 185872: complete local reference diff", "",
             "Comparison is against the checked-in reference, not a claim that every difference was introduced by this patch.",
             "Pre-existing data corrections are explained in the accompanying integration report.", "",
             f"Civilizations: {diff['baseline_civilizations']} -> {diff['candidate_civilizations']}. "
             f"Rows: {diff['baseline_rows']} -> {diff['candidate_rows']}.", "",
             f"Added: {len(diff['added'])}; removed: {len(diff['removed'])}; changed: {len(diff['changed'])}."]
    for heading, key in [("Added rows", "added"), ("Removed rows", "removed")]:
        lines += ["", "## " + heading, ""]
        lines += [f"- {r['civ_name']}: {r.get('unit_name', r['unit_slug'])} (`{r['unit_slug']}`)"
                  for r in diff[key]]
    lines += ["", "## Changed rows", ""]
    for row in diff["changed"]:
        lines += [f"### {row['civ_name']} — {row['unit_name']} ({row['unit_slug']})", ""]
        for field, change in row["changes"].items():
            lines.append(f"- `{field}`: `{change['before']}` -> `{change['after']}`")
        if row["unchanged_final_stats"]:
            lines += ["- Base changed but final value unchanged: " + ", ".join(row["unchanged_final_stats"])]
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare(dat, output_dir, *, baseline=GOLDEN_DIR / "aoe2_reference.db",
            tech_trees=None, reuse_extracted=False):
    from aoe2x.extract.run import extract_all
    from .unit_analyzer import UnitAnalyzer
    from .generate_reference import generate_reference_database
    from .generate_main_db import generate_main_database
    from .patch185872_effects import record_patch_effects

    dat, output_dir, baseline = Path(dat).resolve(), Path(output_dir).resolve(), Path(baseline).resolve()
    reference = output_dir / "aoe2_reference.db"
    if reference == baseline or output_dir == GOLDEN_DIR.resolve():
        raise ValueError("This data-only preparation must not overwrite the shipped golden databases")
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = output_dir / "reports"
    reports.mkdir(exist_ok=True)
    extracted = output_dir / "extracted"
    tree_dir = Path(tech_trees) if tech_trees else dat.parent / "CivTechTrees"
    source = {"build": 185872, "dat_sha256": digest(dat), "dat": str(dat),
              "tech_tree_sha256": {p.name: digest(p) for p in sorted(tree_dir.glob("*.json"))}}
    provenance = extracted / "source.json"
    parsed_data = None
    if reuse_extracted:
        if not provenance.is_file() or json.loads(provenance.read_text()) != source:
            raise ValueError("Reused extraction must have matching DAT and tech-tree provenance; run without --reuse-extracted")
    else:
        parsed_data = extract_all(dat, extracted, tree_dir)
        provenance.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")

    baseline_hash = digest(baseline)
    print("Building isolated reference candidate...", flush=True)
    with (reports / "reference-build.log").open("w", encoding="utf-8") as log, redirect_stdout(log):
        generate_reference_database(UnitAnalyzer(extracted), reference)
    print("Recording sourced conditional effects (not enabling runtime handlers)...", flush=True)
    evidence = record_patch_effects(reference, dat, data=parsed_data)
    (reports / "mechanics-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Building isolated flat stats candidate...", flush=True)
    with (reports / "main-build.log").open("w", encoding="utf-8") as log, redirect_stdout(log):
        generate_main_database(reference_db=reference, output_db=output_dir / "aoe2_units.db")
    diff = compare_references(baseline, reference)
    diff["baseline_tech_audit"] = _audit_rows(baseline)
    diff["candidate_tech_audit"] = _audit_rows(reference)
    (reports / "reference-diff.json").write_text(json.dumps(diff, indent=2) + "\n", encoding="utf-8")
    _write_report(reports / "reference-diff.md", diff)
    with sqlite3.connect(reference) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    manifest = {**source, "baseline_reference": str(baseline), "baseline_sha256": baseline_hash,
                "baseline_unchanged": baseline_hash == digest(baseline), "integrity": integrity,
                "candidate_rows": diff["candidate_rows"], "candidate_civilizations": diff["candidate_civilizations"],
                "added_rows": len(diff["added"]), "removed_rows": len(diff["removed"]),
                "changed_rows": len(diff["changed"]), "effect_records": evidence["recorded_effect_rows"],
                "stage": "data_candidate_before_simulation_validation",
                "simulations_run": False, "ranking_data_updated": False,
                "runtime_mechanics_regenerated": False,
                "outputs": {p.name: digest(p) for p in (reference, output_dir / "aoe2_units.db")}}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k not in ("tech_tree_sha256", "outputs")}, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dat", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=GOLDEN_DIR / "aoe2_reference.db")
    parser.add_argument("--tech-trees", type=Path)
    parser.add_argument("--reuse-extracted", action="store_true")
    prepare(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
