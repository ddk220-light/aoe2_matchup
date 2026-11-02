#!/usr/bin/env python3
"""Read-only prospective audit for narrower common-opponent matchup rules.

Ranking margins are predictive features, never combat evidence. This script
does not change the live selector or promote a prediction to a result.
"""

import argparse
import collections
import gzip
import hashlib
import itertools
import json
from pathlib import Path


SIM = Path(__file__).resolve().parents[1]
CAMPAIGN = SIM / "calibration/campaigns/civ-matchups-campaign-2026-10-31"
RULE_DIR = SIM / "calibration/campaigns/civ-matchups-adaptive-rule-v1-2026-11-01"
RANK = SIM / "calibration/campaigns/unit-rankings-consolidated-2026-10-29"
DEFINITION = SIM / "calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json"
THRESHOLDS = (0.1, 0.2, 0.25, 0.35, 0.5, 0.75, 1.0)
# These are questions for future prospective fights, not accepted rules.
REFINEMENTS = {
    "archer|archer": {"standards": ["Saracens|hand_cannoneer"],
                      "threshold": 0.2, "hypothesis": "mirror archers require a wider margin; small gaps remain close/unknown"},
    "archer|light_cav": {"standards": ["Chinese|arbalester"],
                         "threshold": 0.35, "excludedModes": ["repeating_volley"],
                         "hypothesis": "a larger archer-benchmark gap avoids cavalry close/wrong calls; repeating volleys need a separate rule"},
    "cav_archer|knight": {"standards": ["Chinese|arbalester"],
                          "threshold": 0.35, "hypothesis": "require a larger anti-ranged margin; subtype checks still needed"},
    "knight|militia": {"standards": ["Spanish|paladin", "Turks|paladin"],
                       "threshold": 0.1, "hypothesis": "two cavalry benchmarks agree where Champion benchmark failed"},
    "light_cav|militia": {"standards": ["Spanish|champion", "Turks|paladin"],
                          "threshold": 0.1, "hypothesis": "require both infantry and cavalry benchmarks to agree"},
}


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def phase_provenance(source, phase, latest_eligible_phase):
    metadata = {"sourcePhase": latest_eligible_phase,
                "latestEligibleObservationPhase": latest_eligible_phase}
    if phase is None:
        return metadata
    state = load(source / "adaptive/state.json")
    assert f"{phase:03d}" in state["completedPhases"], "source phase is not reviewed"
    review_path = source / "adaptive/phases" / f"{phase:03d}-review.json"
    review = load(review_path)
    assert review["status"] in ("passed", "complete_with_blocked")
    manifest_path = source / "latest-inference/manifest.json"
    snapshot_phases = [int(Path(item["path"]).stem)
                       for item in load(manifest_path)["sourceFiles"]
                       if "/adaptive/runs/" in item["path"]
                       and Path(item["path"]).suffix == ".jsonl"
                       and Path(item["path"]).stem.isdigit()]
    assert max(snapshot_phases, default=0) == phase, "inference snapshot phase mismatch"
    assert latest_eligible_phase is None or latest_eligible_phase <= phase
    metadata.update(sourcePhase=phase, sourceReviewSha256=sha(review_path),
                    sourceInferenceManifestSha256=sha(manifest_path))
    return metadata


def rows(path):
    with gzip.open(path, "rt") as source:
        yield from map(json.loads, source)


def score(predictions):
    output = collections.Counter()
    for predicted, actual in predictions:
        if predicted is None:
            continue
        output["predicted"] += 1
        output["correct" if predicted == actual else "wrong"] += 1
        if actual is None:
            output["closeCalledDecisive"] += 1
    return dict(output)


def predict(item, standards, threshold):
    values = [item["deltas"].get(name) for name in standards]
    if any(v is None for v in values):
        return None
    if all(v >= threshold for v in values):
        return item["profiles"][0]
    if all(v <= -threshold for v in values):
        return item["profiles"][1]
    return None


def predict_refinement(item, refinement):
    if set(item["modes"]) & set(refinement.get("excludedModes", ())):
        return None
    return predict(item, refinement["standards"], refinement["threshold"])


def pick_diverse(candidates, limit, used=()):
    """Choose independent profile/count contexts before repeating near copies."""
    chosen = []
    seen_profiles = set(used)
    seen_shapes = set()
    remaining = {item["pairKey"]: item for item in candidates}
    while remaining and len(chosen) < limit:
        def rank(item):
            return (sum(profile not in seen_profiles for profile in item["profiles"]),
                    tuple(map(tuple, item["countShape"])) not in seen_shapes,
                    item["aliases"], item["pairKey"])
        best = max(remaining.values(), key=rank)
        chosen.append(best["pairKey"])
        seen_profiles.update(best["profiles"])
        seen_shapes.add(tuple(map(tuple, best["countShape"])))
        del remaining[best["pairKey"]]
    return chosen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=CAMPAIGN)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", type=int, help="fully reviewed source snapshot phase")
    args = parser.parse_args()
    source = args.source
    definition = load(DEFINITION)
    variants = load(source / "latest-inference/variant-profiles.json")
    mechanics = {v["profileHash"]: definition["profiles"][v["key"]]["mechanics"]
                 for v in variants}
    rules = load(RULE_DIR / "common-benchmark-sets.json")["rules"]
    state = load(source / "adaptive/state.json")
    blocked = set(state.get("blockedPairs", []))
    baseline_shapes = load(RULE_DIR / "baseline-count-shapes.json")
    baseline_supported = set(json.loads(gzip.open(
        RULE_DIR / "baseline-supported-pair-keys.json.gz", "rt").read()))
    profiles = {v["key"]: v["profileHash"] for v in variants}
    lines = {v["profileHash"]: v["line"] for v in variants}
    aliases = {v["profileHash"]: v["key"] for v in reversed(variants)}
    standards = {m["teamKeys"][1]: profiles[m["teamKeys"][1]]
                 for m in definition["matchups"]}
    matchups = {m["id"]: m for m in definition["matchups"]}

    # The historical ranking margins are features only. Corrected-engine
    # ranking seeds are replayed separately and not silently mixed here.
    ranking = collections.defaultdict(list)
    for name in ("runs.jsonl", "additional-recorded-runs.jsonl"):
        for raw in (RANK / name).read_text().splitlines():
            run = json.loads(raw)
            if run["selectionProvenance"]["engineVersion"] != "original":
                continue
            a, c = (profiles[key] for key in matchups[run["matchupId"]]["teamKeys"])
            value = (run["unitRemainingHp"] / run["unitStartingHp"] if run["outcome"] == "win"
                     else -run["opponentRemainingHp"] / run["opponentStartingHp"]
                     if run["outcome"] == "loss" else 0)
            ranking[a, c].append((run["seed"], value))
    fingerprints = {pair: sum(v for _, v in values) / len(values)
                    for pair, values in ranking.items()
                    if {0, 1, 2}.issubset({seed for seed, _ in values})}

    family_rows = collections.defaultdict(list)
    baseline_rows = collections.defaultdict(list)
    unresolved_rows = collections.defaultdict(list)
    for row in rows(source / "latest-inference/profile-matchups.jsonl.gz"):
        phases = {int(identifier.rsplit("/", 1)[-1].split(".jsonl:")[0])
                  for identifier in row.get("sourceRunIds", [])
                  if "/adaptive/runs/" in identifier and ".jsonl:" in identifier}
        phases = {phase for phase in phases if phase >= 20}
        assert len(phases) <= 1, (row["pairKey"], phases)
        if (phases or row["outcome"] == "unresolved") and row["pairKey"] not in baseline_supported:
            continue
        family = "|".join(sorted(lines[h] for h in row["profiles"]))
        rule = rules.get(family)
        if not rule or not rule.get("singleBenchmarkTrials"):
            continue
        shape = tuple(sorted((lines[h], count) for h, count in
                             zip(row["context"]["profiles"], row["context"]["counts"])))
        if [list(part) for part in shape] not in baseline_shapes.get(family, []):
            continue
        if "unsupported_effect" in (row.get("reasonCodes") or []):
            continue
        a, b = row["profiles"]
        deltas = {name: fingerprints[(a, standard)] - fingerprints[(b, standard)]
                  for name, standard in standards.items()
                  if a != standards[name] and b != standards[name]
                  and (a, standard) in fingerprints
                  and (b, standard) in fingerprints}
        item = {"pairKey": row["pairKey"], "profiles": [a, b],
            "aliases": row["aliases"],
            "representativeUnits": [aliases[a], aliases[b]],
            "modes": [mechanics[a]["mode"], mechanics[b]["mode"]],
            "phase": next(iter(phases)) if phases else None,
            "actual": row.get("winnerProfileHash")
            if row["outcome"] != "close_uncertain" else None,
            "countShape": [list(part) for part in shape], "deltas": deltas}
        if row["evidenceType"] == "observed":
            (family_rows if phases else baseline_rows)[family].append(item)
        elif row["outcome"] == "unresolved":
            unresolved_rows[family].append(item)

    latest_eligible_phase = max(
        (r["phase"] for group in family_rows.values() for r in group), default=None)
    report = {"kind": "read-only conditional common-C rule refinement audit",
        "status": "candidate rules only; never skip live fights from this report",
        **phase_provenance(source, args.phase, latest_eligible_phase),
        "families": {}, "sourceHashes": {
            "inference": sha(source / "latest-inference/profile-matchups.jsonl.gz"),
            "rankingRuns": sha(RANK / "runs.jsonl"),
            "rankingExtras": sha(RANK / "additional-recorded-runs.jsonl"),
            "ruleCandidates": sha(RULE_DIR / "common-benchmark-sets.json"),
            "baselineShapes": sha(RULE_DIR / "baseline-count-shapes.json"),
            "baselineSupported": sha(RULE_DIR / "baseline-supported-pair-keys.json.gz")}}
    for family, items in sorted(family_rows.items()):
        if family not in rules:
            continue
        all_standards = sorted(standards)
        holdout_phase = max(item["phase"] for item in items)
        train = [r for r in items if r["phase"] < holdout_phase]
        holdout = [r for r in items if r["phase"] == holdout_phase]
        candidates = []
        for size in range(1, min(3, len(all_standards)) + 1):
            for chosen in itertools.combinations(all_standards, size):
                for threshold in THRESHOLDS:
                    dev = score((predict(item, chosen, threshold), item["actual"])
                                for item in train)
                    test = score((predict(item, chosen, threshold), item["actual"])
                                 for item in holdout)
                    if not dev.get("predicted") and not test.get("predicted"):
                        continue
                    candidates.append({"standards": chosen, "threshold": threshold,
                        "development": dev, "laterPhase": test,
                        "historical": score((predict(item, chosen, threshold), item["actual"])
                                            for item in baseline_rows[family]),
                        "all": score((predict(item, chosen, threshold), item["actual"])
                                     for item in items)})
        original = rules[family]
        chosen = tuple(original["selectedStandardsC"])
        threshold = original["minimumSignedMarginGapPerC"]
        failures = [item for item in items if (p := predict(item, chosen, threshold))
                    is not None and p != item["actual"]]
        # Strictly zero wrong/close calls in development. The later phase is
        # independent evidence, so report it even when it contradicts a rule.
        viable = [r for r in candidates if r["development"].get("predicted", 0) >= 3
                  and r["development"].get("wrong", 0) == 0
                  and r["development"].get("closeCalledDecisive", 0) == 0]
        viable.sort(key=lambda r: (
            -(r["laterPhase"].get("correct", 0) if r["laterPhase"].get("wrong", 0) == 0
               and r["laterPhase"].get("closeCalledDecisive", 0) == 0 else -1),
            -r["development"].get("correct", 0), len(r["standards"]), r["threshold"], r["standards"]))
        zero_error_all = [r for r in candidates if r["all"].get("predicted", 0) >= 2
                          and r["all"].get("wrong", 0) == 0
                          and r["all"].get("closeCalledDecisive", 0) == 0]
        zero_error_all.sort(key=lambda r: (-r["all"]["correct"], len(r["standards"]),
                                         r["threshold"], r["standards"]))
        zero_error_both = [r for r in zero_error_all
                           if r["historical"].get("wrong", 0) == 0
                           and r["historical"].get("closeCalledDecisive", 0) == 0
                           and r["historical"].get("predicted", 0) >= 10]
        zero_error_both.sort(key=lambda r: (-r["all"]["correct"],
            -r["historical"]["correct"], len(r["standards"]), r["threshold"], r["standards"]))
        report["families"][family] = {"originalStandards": chosen,
            "originalThreshold": threshold, "prospectivePairs": len(items),
            "developmentPhases": sorted({r["phase"] for r in train}),
            "laterPhase": holdout_phase, "laterPhasePairs": len(holdout),
            "original": score((predict(item, chosen, threshold), item["actual"])
                              for item in items),
            "originalFailures": [{k: item[k] for k in
                ("pairKey", "phase", "profiles", "countShape", "actual", "deltas")}
                for item in failures],
            "bestDevelopmentCandidates": viable[:10],
            "zeroErrorOnSeenProspectivePairs": zero_error_all[:10],
            "zeroErrorHistoricalAndProspective": zero_error_both[:10],
            "allCandidateCount": len(candidates)}
        if family in REFINEMENTS or failures:
            refined = REFINEMENTS.get(family)
            if refined is None or any(
                    (predicted := predict_refinement(item, refined)) is not None
                    and predicted != item["actual"] for item in items + baseline_rows[family]):
                refined = ({"standards": zero_error_both[0]["standards"],
                            "threshold": zero_error_both[0]["threshold"],
                            "hypothesis": "candidate narrowed after a new counterexample"}
                           if zero_error_both else None)
            if refined is None:
                report["families"][family]["refinement"] = {
                    "status": "research_new_benchmark_or_subtype_needed",
                    "promotionAllowed": False,
                    "futureProbePairKeys": pick_diverse(
                        [item for item in unresolved_rows[family] if item["pairKey"] not in blocked
                         and predict(item, chosen, threshold) is not None], 8)}
                continue
            prospect = score((predict_refinement(item, refined), item["actual"])
                             for item in items)
            historical = score((predict_refinement(item, refined), item["actual"])
                               for item in baseline_rows[family])
            predicted_unresolved = [item for item in unresolved_rows[family]
                                    if item["pairKey"] not in blocked
                                    and predict_refinement(item, refined) is not None]
            boundary_unresolved = [item for item in unresolved_rows[family]
                if item["pairKey"] not in blocked
                and predict_refinement(item, refined) is None
                and predict(item, chosen, threshold) is not None]
            future_probes = pick_diverse(predicted_unresolved, 4,
                (profile for item in items for profile in item["profiles"]))
            future_probes += [key for key in pick_diverse(boundary_unresolved, 4)
                              if key not in future_probes]
            rule_body = {k: refined[k] for k in ("standards", "threshold")}
            rule_body["excludedModes"] = refined.get("excludedModes", [])
            rule_hash = hashlib.sha256(json.dumps(rule_body, sort_keys=True,
                separators=(",", ":")).encode()).hexdigest()
            report["families"][family]["refinement"] = {
                **refined, "ruleHash": rule_hash,
                "status": "unvalidated_candidate_keep_probing",
                "historical": historical, "prospective": prospect,
                "historicalFailures": [{k: item[k] for k in
                    ("pairKey", "representativeUnits", "countShape", "actual", "deltas")}
                    for item in baseline_rows[family]
                    if (predicted := predict_refinement(item, refined)) is not None
                    and predicted != item["actual"]][:20],
                "unresolvedEligiblePredictions": len(predicted_unresolved),
                "eligibleUnresolvedPairKeys": [r["pairKey"] for r in predicted_unresolved],
                "eligibleUnresolvedDecisions": [{"pairKey": item["pairKey"],
                    "profiles": item["profiles"], "countShape": item["countShape"],
                    "predictedWinnerProfileHash": predict_refinement(item, refined),
                    "benchmarkDeltas": {name: item["deltas"][name]
                                        for name in refined["standards"]}}
                    for item in predicted_unresolved],
                "futureProbePairKeys": future_probes,
                "prospectiveCases": [{k: item[k] for k in
                    ("pairKey", "phase", "profiles", "countShape", "actual", "modes", "deltas")}
                    for item in items],
                "promotionAllowed": False}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"sourcePhase": report["sourcePhase"],
        "familiesWithTests": len(report["families"]),
        "familiesWithOriginalFailures": [k for k, v in report["families"].items()
            if v["originalFailures"]]}, indent=2))


if __name__ == "__main__":
    main()
