"""Freeze population and shared-unit classification for the geometric benchmark.

Costs remain in the independently audited purchase-cost catalog. This catalog
does not rewrite prices. Rebuild explicitly when changing the benchmark roster.
"""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    from genieutils.datfile import DatFile

    p = argparse.ArgumentParser()
    p.add_argument("--dat", type=Path, required=True)
    p.add_argument(
        "--classifications",
        type=Path,
        help="Reviewed additions, keyed by master ID with sharedAcrossCivilizations and classificationEvidence",
    )
    p.add_argument(
        "--identity",
        action="append",
        default=[],
        help="Additional audited CIV|slug identity",
    )
    args = p.parse_args()
    data = DatFile.parse(args.dat)
    roster = json.loads((ROOT / "data/unique-unit-roster.json").read_text())["units"]
    costs = json.loads((ROOT / "data/recording-costs.json").read_text())["units"]
    keys = {r["civ"] + "|" + r["slug"] for r in roster}
    keys.update(k for k, r in costs.items() if r["master"] == 2554)
    keys.add("Spanish|paladin")
    keys.update(args.identity)
    # Existing classifications are reviewed evidence, not a heuristic based on
    # building, name, or the number of roster entries. New masters require input.
    existing_path = ROOT / "data/recording-balance.json"
    reviewed = {}
    if existing_path.exists():
        existing = json.loads(existing_path.read_text())["units"]
        keys.update(existing)
        for entry in existing.values():
            classification = {
                k: entry[k]
                for k in ("sharedAcrossCivilizations", "classificationEvidence")
            }
            if (
                entry["master"] in reviewed
                and reviewed[entry["master"]] != classification
            ):
                raise ValueError("Conflicting reviewed classifications")
            reviewed[entry["master"]] = classification
    if args.classifications:
        reviewed.update(
            {int(k): v for k, v in json.loads(args.classifications.read_text()).items()}
        )
    entries = {}
    for key in sorted(keys):
        row = costs[key]
        classification = reviewed.get(row["master"])
        if (
            not classification
            or type(classification.get("sharedAcrossCivilizations")) is not bool
            or not classification.get("classificationEvidence")
        ):
            raise ValueError(
                f"Review population effects and shared/exclusive classification for {key} first"
            )
        # Population is per physical unit, including units produced in pairs.
        unit = data.civs[1].units[row["master"]]
        pop = -sum(r.amount for r in unit.resource_storages if r.type == 4)
        used = sum(r.amount for r in unit.resource_storages if r.type == 11)
        if not (pop > 0 and abs(pop - used) < 1e-6):
            raise ValueError(f"Invalid DAT population for {key}")
        entries[key] = dict(
            master=row["master"],
            population=pop,
            **classification,
            populationEvidence="Installed DAT resource_storages: negative resource 4, cross-checked resource 11",
        )
    out = dict(
        schemaVersion=1,
        policy="geometric_shared_discount_v1",
        foodDiscountEffectiveness=0.5,
        woodDiscountEffectiveness=0.5,
        goldDiscountEffectiveness=1.0,
        datSha256=hashlib.sha256(args.dat.read_bytes()).hexdigest(),
        units=entries,
    )
    (ROOT / "data/recording-balance.json").write_text(json.dumps(out, indent=2) + "\n")
    print(
        json.dumps(
            {
                "entries": len(entries),
                "nonStandardPopulation": {
                    k: v["population"]
                    for k, v in entries.items()
                    if v["population"] != 1
                },
            }
        )
    )


if __name__ == "__main__":
    main()
