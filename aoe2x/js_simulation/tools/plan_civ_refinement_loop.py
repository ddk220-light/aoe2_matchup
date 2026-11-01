#!/usr/bin/env python3
"""Version rule refinements and select prospective fights without running combat.

Each completed phase is an immutable decision point. New or revised rules start
with zero prospective credit; only later completed phase results can promote them.
"""

import argparse
import collections
import hashlib
import json
import subprocess
from pathlib import Path


SIM = Path(__file__).resolve().parents[1]
AUDIT = SIM / "tools/audit_civ_common_c_refinements.py"
V2_STATE = Path("/workspace/aoe2_civ_collision_repair/aoe2x/js_simulation/"
                "calibration/campaigns/civ-matchups-collision-repair-v2-2026-10-31/state.json")


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def predict(case, rule):
    if set(case["modes"]) & set(rule.get("excludedModes", [])):
        return None
    values = [case["deltas"].get(c) for c in rule["standards"]]
    if any(value is None for value in values):
        return None
    threshold = rule["threshold"]
    if all(value >= threshold for value in values):
        return case["profiles"][0]
    if all(value <= -threshold for value in values):
        return case["profiles"][1]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--phase", type=int, required=True,
                        help="last fully reviewed phase")
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--probe-limit", type=int, default=48)
    args = parser.parse_args()
    assert args.phase >= 24 and args.probe_limit > 0
    state = load(args.source / "adaptive/state.json")
    v2_state = load(V2_STATE)
    v2_ready = (v2_state["status"] == "caught_up"
                and not v2_state.get("changedResults")
                and not v2_state.get("failedKeys")
                and v2_state.get("savedReplays", 0) >= state.get("savedSeeds", 0))
    assert len(state["completedPhases"]) >= args.phase
    review = load(args.source / "adaptive/phases" / f"{args.phase:03d}-review.json")
    assert review["status"] in ("passed", "complete_with_blocked")
    output = args.archive_root / f"{args.phase:03d}.json"
    audit_path = args.archive_root / f"{args.phase:03d}-audit.json"
    args.archive_root.mkdir(parents=True, exist_ok=True)
    if output.exists():
        saved = load(output)
        assert saved["auditSha256"] == sha(audit_path)
        assert saved["sourceReviewSha256"] == sha(
            args.source / "adaptive/phases" / f"{args.phase:03d}-review.json")
        assert load(audit_path)["sourceHashes"]["inference"] == sha(
            args.source / "latest-inference/profile-matchups.jsonl.gz")
        print(json.dumps({"archive": str(output), "probes": len(saved["selected"]),
                          "verifiedRules": len(saved["verifiedRules"]), "reused": True}))
        return
    subprocess.run(["python3", str(AUDIT), "--source", str(args.source),
                    "--output", str(audit_path)], check=True, stdout=subprocess.DEVNULL)
    audit = load(audit_path)
    assert audit["sourcePhase"] == args.phase, (audit["sourcePhase"], args.phase)
    previous_path = args.archive_root / f"{args.phase-1:03d}.json"
    previous = load(previous_path)["rules"] if previous_path.exists() else {}
    rules = {}
    pools = {}
    verified = {}
    for family, data in sorted(audit["families"].items()):
        refined = data.get("refinement")
        if not refined:
            continue
        candidate = refined.get("ruleHash")
        old = previous.get(family)
        introduced = (old["introducedAfterPhase"] if old and
                      old.get("ruleHash") == candidate else args.phase)
        independent = collections.Counter()
        distinct_profiles = set()
        for case in refined.get("prospectiveCases", []):
            if case["phase"] <= introduced:
                continue
            winner = predict(case, refined)
            if winner is None:
                continue
            independent["predicted"] += 1
            independent["correct" if winner == case["actual"] else "wrong"] += 1
            if case["actual"] is None:
                independent["closeCalledDecisive"] += 1
            distinct_profiles.update(case["profiles"])
        historical = refined.get("historical", {})
        can_verify = bool(v2_ready and candidate and historical.get("predicted", 0) >= 20
                          and not historical.get("wrong", 0)
                          and not historical.get("closeCalledDecisive", 0)
                          and independent["predicted"] >= 60
                          and len(distinct_profiles) >= 12
                          and not independent["wrong"]
                          and not independent["closeCalledDecisive"])
        if can_verify:
            verified[family] = {"ruleHash": candidate,
                "eligibleSkipDecisions": refined["eligibleUnresolvedDecisions"]}
        rules[family] = {"ruleHash": candidate,
            "introducedAfterPhase": introduced,
            "status": "verified" if can_verify else refined["status"],
            "standards": refined.get("standards"),
            "threshold": refined.get("threshold"),
            "excludedModes": refined.get("excludedModes", []),
            "historical": historical,
            "seenProspective": refined.get("prospective", {}),
            "newProspective": dict(independent),
            "newDistinctProfiles": len(distinct_profiles),
            "unresolvedEligiblePredictions": refined.get("unresolvedEligiblePredictions", 0),
            "counterexampleCount": len(data["originalFailures"])}
        if not can_verify:
            pools[family] = refined.get("futureProbePairKeys", [])

    # Round-robin prevents one large family from consuming the whole phase.
    selected = []
    seen = set()
    for index in range(max((len(values) for values in pools.values()), default=0)):
        for family in sorted(pools):
            if index >= len(pools[family]):
                continue
            key = pools[family][index]
            if key in seen:
                continue
            selected.append({"pairKey": key, "family": family,
                             "kind": "refinement_probe", "ruleHash": rules[family]["ruleHash"]})
            seen.add(key)
            if len(selected) == args.probe_limit:
                break
        if len(selected) == args.probe_limit:
            break
    snapshot = {"policyVersion": "common-c-refinement-v1", "sourcePhase": args.phase,
        "v2ReplayReadyForPromotion": v2_ready,
        "v2ReplayStateSha256": sha(V2_STATE),
        "sourceReviewSha256": sha(args.source / "adaptive/phases" / f"{args.phase:03d}-review.json"),
        "auditSha256": sha(audit_path), "previousSnapshotSha256":
        sha(previous_path) if previous_path.exists() else None,
        "rules": rules, "verifiedRules": verified,
        "selected": selected,
        "skipPairKeys": sorted({row["pairKey"] for result in verified.values()
                                for row in result["eligibleSkipDecisions"]}),
        "promotionPolicy": "20 historical zero-error predictions and 60 independent post-introduction prospective predictions across 12 profiles, with zero wrong winners or close-as-decisive errors; no inferred roots"}
    output.write_text(json.dumps(snapshot, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"archive": str(output), "probes": len(selected),
                      "verifiedRules": len(verified), "reused": False}))


if __name__ == "__main__":
    main()
