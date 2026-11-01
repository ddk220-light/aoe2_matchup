#!/usr/bin/env python3
"""Build a versioned adaptive selection from completed journals; run no combat."""
import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = Path(os.environ.get("CIV_SELECTION_CAMPAIGN_DIR",
    str(ROOT / "calibration/campaigns/civ-matchups-campaign-2026-10-31")))
RULES = Path(os.environ.get("CIV_SELECTION_RULES_DIR",
    str(ROOT / "calibration/campaigns/civ-matchups-adaptive-rule-v1-2026-11-01")))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, required=True, help="last completed phase")
    args = parser.parse_args()
    assert args.phase >= 20
    frozen = json.loads((RULES / "manifest.json").read_text())
    assert frozen["version"] == "common-c-adaptive-v1"
    for name, checksum in frozen["sources"].items():
        assert sha(RULES / name) == checksum, f"adaptive rule source changed: {name}"
    inference = Path(os.environ.get("CIV_SELECTION_INFERENCE_DIR",
        str(CAMPAIGN / "latest-inference")))
    estimates = inference / "adaptive-estimates"
    selection = inference / "adaptive-selection"
    common = dict(os.environ, CIV_ESTIMATE_SOURCE_PHASE=str(args.phase),
        CIV_INFERENCE_CANDIDATE_DIR=str(inference), CIV_ESTIMATE_OUTPUT_DIR=str(estimates),
        CIV_VARIANT_PROFILES=str(inference / "variant-profiles.json"),
        CIV_COMMON_C_RULES=str(RULES / "common-benchmark-sets.json"),
        CIV_VALIDATION_BASELINE_SHAPES=str(RULES / "baseline-count-shapes.json"),
        CIV_VALIDATION_BASELINE_SUPPORTED_KEYS=str(RULES / "baseline-supported-pair-keys.json.gz"),
        CIV_PROSPECTIVE_RUNS_DIR=str(CAMPAIGN / "adaptive/runs"),
        CIV_PROSPECTIVE_FIRST_PHASE=str(frozen["firstProspectivePhase"]),
        CIV_MINIMUM_PROSPECTIVE_PAIRS=str(frozen["minimumProspectivePairsPerFamily"]),
        CIV_MINIMUM_PROSPECTIVE_PROFILES=str(frozen["minimumProspectiveDistinctProfiles"]),
        CIV_HARD_SOURCE_DIR=str(estimates), CIV_HARD_INFERENCE_DIR=str(inference),
        CIV_HARD_V3_DIR=str(CAMPAIGN), CIV_HARD_OUTPUT_DIR=str(selection),
        CIV_HARD_PRIORITY_REPORT=str(RULES / "phase020-inference-potential.json"))
    subprocess.run(["python3", str(ROOT / "tools/build_civ_matchup_estimates.py")],
        env=common, check=True, stdout=subprocess.DEVNULL)
    priority_report = inference / "adaptive-test-priority.json"
    priority_status = "recomputed"
    try:
        subprocess.run(["node", str(ROOT / "node/civ-matchups/plan-active-tests.mjs"),
            str(inference), str(priority_report)], env={**common,
                "CIV_TEST_PLAN_LIMIT": os.environ.get("CIV_ADAPTIVE_PRIORITY_LIMIT", "600")},
            check=True, stdout=subprocess.DEVNULL, timeout=180)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        priority_report = RULES / "phase020-inference-potential.json"
        priority_status = f"frozen_phase020_fallback:{type(error).__name__}"
    common["CIV_HARD_PRIORITY_REPORT"] = str(priority_report)
    subprocess.run(["python3", str(ROOT / "tools/plan_civ_hard_cases.py")],
        env=common, check=True, stdout=subprocess.DEVNULL)
    proposal = json.loads((selection / "proposed-phase.json").read_text())
    assert proposal["policyVersion"] == frozen["version"]
    assert proposal["sourcePhase"] == args.phase
    assert len({r["pairKey"] for r in proposal["selected"]}) == len(proposal["selected"])
    estimate_summary = json.loads((estimates / "summary.json").read_text())
    assert len(proposal["skippedVerifiedEstimateKeys"]) <= estimate_summary["skippableProfilePairs"]
    assert not set(proposal["skippedVerifiedEstimateKeys"]).intersection(
        r["pairKey"] for r in proposal["selected"])

    # Every skipped winner remains an explicit, reviewable estimate with root
    # benchmark margins and a rule validation record. Historical snapshots are
    # kept if a later counterexample causes the rule to be disabled/requeued.
    archive = CAMPAIGN / "adaptive/estimates" / f"{args.phase:03d}"
    archive.mkdir(parents=True, exist_ok=True)
    skipped_keys = set(proposal["skippedVerifiedEstimateKeys"])
    with gzip.open(estimates / "estimated.jsonl.gz", "rt") as source, (
            archive / "verified-estimates.jsonl.gz").open("wb") as target, gzip.GzipFile(
            filename="", mode="wb", fileobj=target, compresslevel=6, mtime=0) as out:
        kept = 0
        for raw in source:
            row = json.loads(raw)
            if row["skippable"] and row["pairKey"] in skipped_keys:
                out.write((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode())
                kept += 1
    assert kept == len(skipped_keys)
    shutil.copyfile(estimates / "summary.json", archive / "estimate-summary.json")
    priority = json.loads(priority_report.read_text())
    compact_priority = {"status": priority_status,
        "sourceSha256": sha(priority_report),
        "evaluatedCandidates": priority.get("evaluatedCandidates"),
        "top": [{"pairKey": row["pairKey"], "possibleByWinner": [
            {key: side[key] for key in ("r1Cells", "r2CellsIfWinnerHpAtLeast50Percent",
                                   "r3CellsIfWinnerHpAtLeast25Percent")}
            for side in row["possibleByWinner"]]} for row in priority["top"]]}
    (archive / "priority.json").write_text(json.dumps(compact_priority, sort_keys=True, indent=2) + "\n")
    archive_manifest = {"policyVersion": frozen["version"], "sourcePhase": args.phase,
        "frozenRuleManifestSha256": sha(RULES / "manifest.json"),
        "sourceInferenceManifestSha256": sha(inference / "manifest.json"),
        "estimateSummarySha256": sha(archive / "estimate-summary.json"),
        "verifiedEstimatesSha256": sha(archive / "verified-estimates.jsonl.gz"),
        "prioritySha256": sha(archive / "priority.json"),
        "priorityPlannerSha256": sha(ROOT / "node/civ-matchups/plan-active-tests.mjs"),
        "selectedPairs": len(proposal["selected"]), "skippedVerifiedEstimates": kept}
    (archive / "manifest.json").write_text(json.dumps(archive_manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"policyVersion": frozen["version"], "sourcePhase": args.phase,
        "selected": proposal["selected"], "skippedVerifiedEstimateKeys": proposal["skippedVerifiedEstimateKeys"],
        "archiveManifestSha256": sha(archive / "manifest.json"),
        "priorityStatus": priority_status,
        "verifiedFamilies": estimate_summary["prospectivePhase"]["verifiedFamilies"],
        "disabledFamilies": estimate_summary["prospectivePhase"]["disabledFamilies"]}))

if __name__ == "__main__":
    main()
