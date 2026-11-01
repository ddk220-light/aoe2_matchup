#!/usr/bin/env python3
"""Inventory blocked V3 seeds for a future separately journaled V2-stream pass.

Read-only: this never imports the fight runner or treats an absent replay as a
new fight. The V2 replay must recompute every valid V3 seed first.
"""

import argparse
import collections
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess


SIM = Path(__file__).resolve().parents[1]
V3 = Path(os.environ.get("CIV_V3_WORKTREE", "/workspace/aoe2_path_recovery")) / (
    "aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31")
V2 = Path(os.environ.get("CIV_V2_WORKTREE", "/workspace/aoe2_civ_collision_repair")) / (
    "aoe2x/js_simulation/calibration/campaigns/civ-matchups-collision-repair-v2-2026-10-31")
CERT = SIM / "calibration/campaigns/civ-matchups-v2-stream-compatibility-2026-11-01/manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def records(path):
    with path.open("rb") as source:
        for number, raw in enumerate(source, 1):
            if raw.strip():
                yield number, json.loads(raw), hashlib.sha256(raw.rstrip(b"\n")).hexdigest()


def complete(seeds):
    first = [seeds.get(i) for i in range(3)]
    if not all(first):
        return False
    return len({r["outcome"] for r in first}) == 1 or all(i in seeds for i in range(3, 10))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    subprocess.run(["node", str(SIM / "node/civ-matchups/certify-v2-stream-compatibility.mjs"),
                    "--verify"], check=True, stdout=subprocess.DEVNULL)
    cert = load(CERT)
    pilot_manifest = load(V3 / "pilot/manifest.json")
    v3_manifest = load(V3 / "adaptive/manifest.json")
    v2_manifest = load(V2 / "manifest.json")
    assert cert["v2CampaignHash"] == v2_manifest["campaignHash"]
    assert v3_manifest["campaignHash"] in v2_manifest["sourceCampaignHashes"]
    inventory_path = V3 / "adaptive" / v3_manifest["matchupInventory"]["file"]
    assert sha(inventory_path) == v3_manifest["matchupInventory"]["sha256"]
    with gzip.open(inventory_path, "rt") as source:
        jobs = {row["pairKey"]: row for row in map(json.loads, source)}
    jobs_by_id = {row["id"]: row for row in jobs.values()}
    state = load(V3 / "adaptive/state.json")
    blocked = set(state["blockedPairs"])
    archive_root = V3 / "adaptive/estimates"
    archives = sorted(p for p in archive_root.glob("[0-9][0-9][0-9]")
                      if (p / "selection-summary.json").exists())
    selection_path = archives[-1] / "selection-summary.json" if archives else None
    hazards = {r["pairKey"]: r["hazard"] for r in load(selection_path)["pathingHazardPairs"]} if selection_path else {}
    inference_path = V3 / "latest-inference/profile-matchups.jsonl.gz"
    with gzip.open(inference_path, "rt") as source:
        unresolved = {r["pairKey"] for r in map(json.loads, source) if r["outcome"] == "unresolved"}
    targets = (blocked | set(hazards)) & unresolved
    assert targets <= set(jobs)

    valid = collections.defaultdict(dict)
    source_hashes = {}
    source_journals = {}
    for area in ("pilot", "adaptive"):
        source_campaign_hash = (pilot_manifest if area == "pilot" else v3_manifest)["campaignHash"]
        for path in sorted((V3 / area / "runs").glob("*.jsonl")):
            source_journals[str(path.relative_to(V3))] = sha(path)
            for number, row, record_hash in records(path):
                job = jobs_by_id.get(row["matchupId"])
                key = (row.get("pairKey") or job["pairKey"]) if job else None
                if key not in targets or row.get("error") or row["outcome"] not in ("win", "loss", "draw"):
                    continue
                job = jobs[key]
                assert row["campaignHash"] == source_campaign_hash
                assert row["matchupId"] == job["id"]
                assert [row["unitCount"], row["opponentCount"]] == job["counts"]
                assert row["seed"] not in valid[key], (key, row["seed"])
                valid[key][row["seed"]] = row
                source_hashes[(key, row["seed"])] = record_hash

    replayed = collections.defaultdict(dict)
    for _, row, _ in records(V2 / "replays.jsonl"):
        if row["sourceCampaignHash"] not in (pilot_manifest["campaignHash"],
                                               v3_manifest["campaignHash"]):
            continue
        key = row["pairKey"] or jobs_by_id[row["matchupId"]]["pairKey"]
        if key not in targets:
            continue
        seed = row["seed"]
        assert seed in valid[key], (key, seed, "V2 replay lacks a valid V3 source")
        assert seed not in replayed[key], (key, seed, "duplicate V2 replay")
        assert row["campaignHash"] == v2_manifest["campaignHash"]
        assert row["sourceCampaignHash"] == valid[key][seed]["campaignHash"]
        assert row["sourceRecordSha256"] == source_hashes[key, seed]
        replayed[key][seed] = row

    rows = []
    for key in sorted(targets):
        saved = valid[key]
        if complete(saved):
            continue
        first_missing = [seed for seed in range(3) if seed not in saved]
        first_v2 = [replayed[key].get(seed) for seed in range(3)]
        mixed_v2 = all(first_v2) and len({r["outcome"] for r in first_v2}) > 1
        extra_missing = [seed for seed in range(3, 10) if seed not in saved] if mixed_v2 else []
        rows.append({"pairKey": key, "matchupId": jobs[key]["id"],
            "teamKeys": jobs[key]["teamKeys"], "counts": jobs[key]["counts"],
            "scenarioHash": jobs[key]["scenarioHash"],
            "sourceKinds": [kind for kind, yes in (("blocked_v3", key in blocked),
                 ("deferred_pathing_hazard", key in hazards)) if yes],
            "pathingHazard": hazards.get(key),
            "validV3Seeds": sorted(saved), "replayedV2Seeds": sorted(replayed[key]),
            "waitingForV2ReplaySeeds": sorted(set(saved) - set(replayed[key])),
            "missingInitialSeeds": first_missing, "missingExtraSeedsIfV2Mixed": extra_missing,
            "extraSeedDecisionPending": not all(first_v2)})

    output = {"kind": "read-only preliminary V2-stream gap inventory; no result or fight",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "v3CompletedPhases": len(state["completedPhases"]), "v3ActivePhase": state["activePhase"],
        "targetProfilePairs": len(rows),
        "blockedTargetPairs": sum("blocked_v3" in r["sourceKinds"] for r in rows),
        "hazardTargetPairs": sum("deferred_pathing_hazard" in r["sourceKinds"] for r in rows),
        "missingInitialSeeds": sum(len(r["missingInitialSeeds"]) for r in rows),
        "missingExtraSeedsIfV2Mixed": sum(len(r["missingExtraSeedsIfV2Mixed"]) for r in rows),
        "waitingForV2ReplaySeeds": sum(len(r["waitingForV2ReplaySeeds"]) for r in rows),
        "rows": rows,
        "sourceHashes": {"compatibilityCertificate": sha(CERT),
            "v3AdaptiveManifest": sha(V3 / "adaptive/manifest.json"),
            "v3PilotManifest": sha(V3 / "pilot/manifest.json"),
            "v3State": sha(V3 / "adaptive/state.json"),
            "v3Inventory": sha(inventory_path), "v3Inference": sha(inference_path),
            "v3Selection": sha(selection_path) if selection_path else None,
            "v3Journals": source_journals, "v2Manifest": sha(V2 / "manifest.json"),
            "v2Replays": sha(V2 / "replays.jsonl")},
        "note": "Only missing V3 seeds are possible new V2-stream jobs for these blocked/deferred targets. Valid V3 seeds await their own V2 replay; no old outcome is copied. Extra seeds 3..9 are selected only from completed V2 outcomes for seeds 0..2. Rebuild after either source campaign grows. This is not an inventory of every pair that may become mixed after V2 replay."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: v for k, v in output.items() if k not in ("rows", "sourceHashes", "note")}, indent=2))


if __name__ == "__main__":
    main()
