"""Independently audit the consolidated table against raw journal records."""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = ROOT / "aoe2x/js_simulation/calibration/campaigns/unit-rankings-consolidated-2026-10-29"


def read(path):
    return json.loads(path.read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    manifest = read(DIRECTORY / "manifest.json")
    for entry in manifest["sources"]:
        assert sha((ROOT / entry["path"]).read_bytes()) == entry["sha256"], entry["path"]
    for entry in manifest["outputs"]:
        assert sha((DIRECTORY / entry["path"]).read_bytes()) == entry["sha256"], entry["path"]
    assert sha((ROOT / manifest["generator"]["path"]).read_bytes()) == manifest["generator"]["sha256"]
    matches = {m["id"]: m for m in manifest["matchups"]}
    original_manifest = read(ROOT / manifest["engineVersions"]["original"]["manifestPath"])
    assert manifest["roster"] == original_manifest["roster"]
    assert manifest["matchups"] == original_manifest["matchups"]
    for matchup in matches.values():
        canonical = matches[matchup["canonicalMatchupId"]]
        assert canonical["canonicalMatchupId"] == canonical["id"]
        assert matchup["counts"] == canonical["counts"]
        assert matchup["scenarioHash"] == canonical["scenarioHash"]
        for left, right in zip(matchup["teamKeys"], canonical["teamKeys"]):
            a = {k: v for k, v in original_manifest["profiles"][left]["mechanics"].items() if k != "civilization"}
            b = {k: v for k, v in original_manifest["profiles"][right]["mechanics"].items() if k != "civilization"}
            assert a == b, (left, right)
    rows_by_id = defaultdict(list)
    seen = set()
    source_files = {}
    counts = Counter()
    for name in ["runs.jsonl", "additional-recorded-runs.jsonl"]:
        for line in (DIRECTORY / name).read_text().splitlines():
            row = json.loads(line)
            identity = (row["matchupId"], row["seed"])
            assert identity not in seen, identity
            seen.add(identity)
            assert row["outcome"] in {"win", "loss", "draw"}
            p = row["selectionProvenance"]
            assert p["inputCampaignHash"] == manifest["engineVersions"][p["engineVersion"]]["campaignHash"]
            if p["file"] not in source_files:
                raw_bytes = (ROOT / p["file"]).read_bytes()
                source_files[p["file"]] = (sha(raw_bytes), raw_bytes.decode().splitlines())
            file_hash, source_lines = source_files[p["file"]]
            assert file_hash == p["fileSha256"]
            raw_line = source_lines[p["line"] - 1]
            assert sha(raw_line.encode()) == p["recordSha256"]
            raw = json.loads(raw_line)
            assert (raw["matchupId"], raw["seed"]) == identity
            assert raw["result"] == row["result"], identity
            assert raw["wallSeconds"] == row["wallSeconds"]
            result = raw["result"]
            expected = "draw" if result["outcome"] == "draw" else "win" if result["winnerOwner"] == 2 else "loss"
            assert row["outcome"] == expected
            assert row["ticks"] == result["ticks"]
            assert row["finalStateHash"] == result["finalStateHash"]
            assert row["eventLogHash"] == result["eventLogHash"]
            assert row["simulationSeconds"] == result["ticks"] / 60
            for prefix, owner in [("unit", "2"), ("opponent", "3")]:
                assert row[prefix + "RemainingHp"] == result["remainingByOwner"][owner]["hp"]
                assert row[prefix + "Survivors"] == result["remainingByOwner"][owner]["units"]
                assert row[prefix + "StartingHp"] == result["startingHpByOwner"][owner]
                assert math.isclose(row[prefix + "HpPercent"], 100 * row[prefix + "RemainingHp"] / row[prefix + "StartingHp"])
            if name == "runs.jsonl":
                rows_by_id[row["matchupId"]].append(row)
                counts[p["sourceKind"]] += 1
    table = read(DIRECTORY / "summary.json")
    assert len(table) == len(matches) == 3591
    assert len({r["matchupId"] for r in table}) == len(table)
    assert len(rows_by_id) == 2398
    pools = {
        "Infantry": {"champion", "hussar", "arbalester", "paladin", "cavalier"},
        "Ranged": {"champion", "arbalester", "cavalier", "hca", "hand_cannoneer", "hussar", "skirmisher"},
        "Cavalry": {"champion", "arbalester", "paladin", "halberdier", "camel", "cavalier", "hca"},
    }
    roster_rows = defaultdict(set)
    for row in table:
        matchup = matches[row["matchupId"]]
        assert row["simulationSourceMatchupId"] == matchup["canonicalMatchupId"]
        samples = rows_by_id[matchup["canonicalMatchupId"]]
        seeds = {r["seed"] for r in samples}
        initial = [r for r in samples if r["seed"] < 3]
        required = 10 if len({r["outcome"] for r in initial}) > 1 else 3
        assert len(initial) == 3 and seeds == set(range(required)), matchup["id"]
        assert row["requiredRuns"] == row["recordedRuns"] == required
        assert row["state"] == "complete" and row["undecided"] == 0
        for name, outcome in [("wins", "win"), ("losses", "loss"), ("draws", "draw")]:
            assert row[name] == sum(r["outcome"] == outcome for r in samples)
        for output_key, run_key in [("meanUnitHpPercentDecided", "unitHpPercent"),
                                    ("meanOpponentHpPercentDecided", "opponentHpPercent"),
                                    ("meanSimulationSecondsDecided", "simulationSeconds"),
                                    ("meanWallSeconds", "wallSeconds")]:
            assert math.isclose(row[output_key], mean(r[run_key] for r in samples), rel_tol=1e-12, abs_tol=1e-12)
        assert row["minUnitHpPercentDecided"] == min(r["unitHpPercent"] for r in samples)
        assert row["maxUnitHpPercentDecided"] == max(r["unitHpPercent"] for r in samples)
        assert row["unitCount"] == matchup["counts"][0] and row["opponentCount"] == matchup["counts"][1]
        costs = matchup["weightedCosts"]
        expected_counts = [27 if c == min(costs) else math.floor(27 * math.sqrt(min(costs) / c) + .5) for c in costs]
        assert expected_counts == matchup["counts"]
        assert row["originalEngineRuns"] == sum(r["selectionProvenance"]["engineVersion"] == "original" for r in samples)
        assert row["correctedEngineRuns"] == required - row["originalEngineRuns"]
        assert row["mixedEngineVersions"] == (0 < row["originalEngineRuns"] < required)
        roster_rows[(row["civilization"], row["slug"], row["group"])].add(row["opponentKey"])
    assert len(roster_rows) == len(manifest["roster"]["units"]) == 555
    for unit in manifest["roster"]["units"]:
        assert roster_rows[(unit["civilization"], unit["slug"], unit["group"])] == pools[unit["group"]], unit
    with (DIRECTORY / "summary.csv").open(newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == len(table)
    for csv_row, row in zip(csv_rows, table):
        assert csv_row.keys() == row.keys()
        for field, value in row.items():
            expected = str(value).lower() if isinstance(value, bool) else str(value) if value is not None else ""
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                assert float(csv_row[field]) == value
            else:
                assert csv_row[field] == expected
    assert read(DIRECTORY / "pending.json") == read(DIRECTORY / "undecided.json") == []
    validation = read(DIRECTORY / "validation.json")
    assert validation["requiredRuns"] == sum(map(len, rows_by_id.values()))
    assert validation["includedSourceCounts"] == dict(counts)
    result = {"status": "passed", "requiredRuns": validation["requiredRuns"], "uniqueSavedResults": len(seen),
              "tableRows": len(table), "civilizationUnitVariants": len(roster_rows), "sourceCounts": dict(counts),
              "checks": ["all raw source hashes and results", "exact seed sets", "all table aggregates",
                         "CSV/JSON parity", "cost-balanced counts", "every roster/opponent row", "engine provenance",
                         "exact mechanics equivalence for every shared civilization result"]}
    (DIRECTORY / "independent-validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
