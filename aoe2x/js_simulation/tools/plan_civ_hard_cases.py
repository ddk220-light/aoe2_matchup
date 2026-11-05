#!/usr/bin/env python3
"""Offline hard-case queue; estimates stay provisional and no fights are run."""
import collections
import gzip
import hashlib
import json
import math
import os
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "calibration"
SOURCE = Path(os.environ.get("CIV_HARD_SOURCE_DIR",
    str(CAL / "campaigns/civ-matchups-provisional-estimates-phase020-2026-11-01")))
INFERENCE = Path(os.environ.get("CIV_HARD_INFERENCE_DIR",
    str(CAL / "campaigns/civ-matchups-inference-inert-group-r1-only-phase020-2026-11-01")))
V3 = Path(os.environ.get("CIV_HARD_V3_DIR",
    "/workspace/aoe2_civ_v3_phase020/aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31"))
PRIORITY = Path(os.environ.get("CIV_HARD_PRIORITY_REPORT",
    str(CAL / "reports/civ-matchups-ranking-inference-audit-2026-11-01/test-priority-phase020.json")))
OUTPUT = Path(os.environ.get("CIV_HARD_OUTPUT_DIR",
    str(CAL / "campaigns/civ-matchups-hard-case-plan-phase020-2026-11-01")))

def load_jsonl_gz(path):
    with gzip.open(path, "rt") as source:
        return [json.loads(line) for line in source]

def write_json(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def quantile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]

estimate_summary = json.loads((SOURCE / "summary.json").read_text())
estimated = load_jsonl_gz(SOURCE / "estimated.jsonl.gz")
unestimated = load_jsonl_gz(SOURCE / "still-unestimated.jsonl.gz")
assert len(estimated) == estimate_summary["estimatedProfilePairs"]
assert len(unestimated) == estimate_summary["stillUnestimatedProfilePairs"]

scenario_wall = collections.defaultdict(list)
for journal in sorted((V3 / "adaptive/runs").glob("*.jsonl")) + sorted((V3 / "pilot/runs").glob("*.jsonl")):
    for raw in journal.read_text().splitlines():
        run = json.loads(raw)
        if run.get("eventLogHash") and run.get("scenarioHash") and isinstance(run.get("wallSeconds"), (float, int)):
            scenario_wall[run["scenarioHash"]].append(run["wallSeconds"])
scenario_stats = {key: {"validSeeds": len(values), "medianWallSeconds": statistics.median(values),
                        "p90WallSeconds": quantile(values, .9)}
                  for key, values in scenario_wall.items()}
global_median = statistics.median([v for values in scenario_wall.values() for v in values])

variant_profiles = json.loads((INFERENCE / "variant-profiles.json").read_text())
line = {v["profileHash"]: v["line"] for v in variant_profiles}
variant_keys = collections.defaultdict(set)
for variant in variant_profiles:
    variant_keys[variant["profileHash"]].add(variant["key"])
def family_from_hashes(hashes):
    return "|".join(sorted(line[h] for h in hashes))

def known_pathing_hazard(row):
    """Defer repeatedly stalled geometry families without assigning outcomes."""
    a, b = row["context"]["profiles"]
    for ranged_hash, opponent_hash in ((a, b), (b, a)):
        keys = variant_keys[ranged_hash]
        if "Mapuche|imp_elite_skirm" in keys and line[opponent_hash] in {"knight", "elephant"}:
            return "mapuche_skirm_vs_heavy_cavalry_pathing"
        if ("Muisca|elite_guecha_warrior_muisca" in keys
                and any(key.endswith("|champion") for key in variant_keys[opponent_hash])):
            return "guecha_vs_champion_pathing"
    return None

# A winner-margin condition in R2/R3 must hold across every saved seed.
# Estimate those conditions from complete current-engine observed groups only.
groups = collections.defaultdict(list)
with gzip.open(INFERENCE / "evidence-ledger.jsonl.gz", "rt") as source:
    for raw in source:
        record = json.loads(raw)
        if not record.get("corrected") or not record.get("winnerHash"):
            continue
        hashes = record["profileHashes"]
        winner_index = hashes.index(record["winnerHash"])
        hp = record["unitRemainingHp"] if winner_index == 0 else record["opponentRemainingHp"]
        starting = record["unitStartingHp"] if winner_index == 0 else record["opponentStartingHp"]
        groups[record["matchupId"]].append((record["seed"], record["winnerHash"], hp / starting,
                                            family_from_hashes(hashes)))
margin_stats = collections.defaultdict(collections.Counter)
for records in groups.values():
    if not {0, 1, 2}.issubset({r[0] for r in records}) or len({r[1] for r in records}) != 1:
        continue
    minimum = min(r[2] for r in records)
    family = records[0][3]
    margin_stats[family]["decisive"] += 1
    margin_stats[family]["hp25"] += minimum >= .25
    margin_stats[family]["hp50"] += minimum >= .5
all_margin = collections.Counter()
for counts in margin_stats.values():
    all_margin.update(counts)

blocked = set(json.loads((V3 / "adaptive/state.json").read_text()).get("blockedPairs", []))
priority = {}
if PRIORITY.exists():
    report = json.loads(PRIORITY.read_text())
    priority = {row["pairKey"]: row for row in report.get("top", [])}

def prospective_gain(row, pair_family):
    option = priority.get(row["pairKey"])
    if not option:
        return 0, False
    family_stats = margin_stats.get(pair_family, all_margin)
    total = family_stats["decisive"] or 1
    p25 = family_stats["hp25"] / total
    p50 = family_stats["hp50"] / total
    sides = option["possibleByWinner"]
    gains = [side["r1Cells"] + p25 * side["r3CellsIfWinnerHpAtLeast25Percent"]
             + p50 * side["r2CellsIfWinnerHpAtLeast50Percent"] for side in sides]
    return min(gains), True

def worker_cost(row):
    scenario = row["context"]["scenarioHash"]
    return 3 * scenario_stats.get(scenario, {}).get("medianWallSeconds", global_median)

deferred = [row for row in estimated if row["skippable"]]
hard = [row for row in estimated if not row["skippable"]] + unestimated
assert len(deferred) + len(hard) == estimate_summary["sourceUnresolvedProfilePairs"]
queue = []
blocked_or_partial = []
hazard_deferred = []
category = collections.Counter()
for row in hard:
    reason = row.get("whyNoEstimate", row.get("tier"))
    if row["pairKey"] in blocked or reason == "source_conflict_or_missing_seeds":
        blocked_or_partial.append({"pairKey": row["pairKey"], "reason": reason,
                                   "blockedInFrozenV3": row["pairKey"] in blocked})
        continue
    hazard = known_pathing_hazard(row)
    if hazard:
        hazard_deferred.append({"pairKey": row["pairKey"], "hazard": hazard,
                                "aliases": row["aliases"]})
        continue
    pair_family = row["family"]
    cost = worker_cost(row)
    gain, scanned = prospective_gain(row, pair_family)
    # Direct coverage is certain only if the fight completes. Prospective
    # transfer is conditional on the outcome and observed survivor margin.
    expected_cells = row["aliases"] + gain
    score = expected_cells / max(cost, 1)
    queue.append({"pairKey": row["pairKey"], "family": pair_family,
        "reason": reason, "aliases": row["aliases"],
        "scenarioHash": row["context"]["scenarioHash"],
        "counts": row["context"]["counts"],
        "threeSeedMedianWorkerSeconds": cost,
        "prospectiveExtraCells": gain, "prospectiveScanIncluded": scanned,
        "priorityCellsPerWorkerSecond": score,
        "mustUseConsistentEngine": True})
    category[reason] += 1
queue.sort(key=lambda row: (-row["priorityCellsPerWorkerSecond"], row["pairKey"]))
assert len(queue) + len(blocked_or_partial) + len(hazard_deferred) == len(hard)

# Spend part of each phase on independent checks of promising common-C rules.
# These are real fights until the family passes the prospective gate. A skipped
# pair is never counted as an observation, and any counterexample unskips its
# entire family on the next build.
family_potential = collections.Counter(row["family"] for row in estimated
    if row["tier"] == "supported_context_estimate" and not row["skippable"])
probes = []
for row in estimated:
    if row["tier"] != "supported_context_estimate" or not row["eligibleForProspectiveValidation"]:
        continue
    if row["pairKey"] in blocked:
        continue
    if known_pathing_hazard(row):
        continue
    threshold = row["minimumSignedMarginGapPerC"]
    smallest_gap = min(abs(c["delta"]) for c in row["commonOpponents"])
    cost = worker_cost(row)
    # Prefer families with many potentially saved fights. Within a family,
    # probe near the accepted margin boundary and spread across unit profiles.
    score = family_potential[row["family"]] / max(cost, 1)
    probes.append({"pairKey": row["pairKey"], "family": row["family"],
        "profiles": row["profiles"], "aliases": row["aliases"],
        "predictedWinnerProfileHash": row["predictedWinnerProfileHash"],
        "minimumGapAboveThreshold": smallest_gap - threshold,
        "potentialFamilySavings": family_potential[row["family"]],
        "threeSeedMedianWorkerSeconds": cost, "priority": score,
        "ruleStatus": row["ruleStatus"], "skippable": row["skippable"]})
probes.sort(key=lambda p: (-p["priority"], p["minimumGapAboveThreshold"], p["pairKey"]))
validation_batch = []
probe_family_quota = collections.Counter()
used_profiles = collections.defaultdict(set)
for probe in probes:
    if not probe["skippable"] or probe_family_quota[probe["family"]] >= 2:
        continue
    validation_batch.append(probe)
    probe_family_quota[probe["family"]] += 1
    used_profiles[probe["family"]].update(probe["profiles"])
    if len(validation_batch) >= 16:
        break
for probe in probes:
    if probe["skippable"]:
        continue
    family = probe["family"]
    if probe_family_quota[family] >= 8:
        continue
    # Add diversity before filling up a family with close mechanics copies.
    if all(h in used_profiles[family] for h in probe["profiles"]) and probe_family_quota[family] >= 2:
        continue
    validation_batch.append(probe)
    probe_family_quota[family] += 1
    used_profiles[family].update(probe["profiles"])
    if len(validation_batch) == 64:
        break

# Limit correlated batches: take at most two tests per line-pair in a first
# review phase. This is a proposed queue only, never a runner schedule.
first = []
family_quota = collections.Counter()
for row in queue:
    if family_quota[row["family"]] >= 2:
        continue
    first.append(row)
    family_quota[row["family"]] += 1
    if len(first) == 32:
        break

OUTPUT.mkdir(parents=True, exist_ok=True)
with gzip.open(OUTPUT / "hard-queue.jsonl.gz", "wt", compresslevel=6) as out:
    for row in queue:
        out.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
write_json(OUTPUT / "first-review-candidates.json", first)
write_json(OUTPUT / "validation-probes.json", validation_batch)
selected = []
selected_keys = set()
for probe in validation_batch:
    if len(selected) == 64:
        break
    selected.append({"pairKey": probe["pairKey"], "kind": "prospective_rule_check",
        "family": probe["family"], "ruleStatus": probe["ruleStatus"]})
    selected_keys.add(probe["pairKey"])
hard_family_quota = collections.Counter()
for row in queue:
    if len(selected) == 256:
        break
    if row["pairKey"] in selected_keys or hard_family_quota[row["family"]] >= 16:
        continue
    selected.append({"pairKey": row["pairKey"], "kind": "hard_case",
        "family": row["family"], "priorityCellsPerWorkerSecond": row["priorityCellsPerWorkerSecond"]})
    selected_keys.add(row["pairKey"])
    hard_family_quota[row["family"]] += 1
for row in queue:
    if len(selected) == 256:
        break
    if row["pairKey"] not in selected_keys:
        selected.append({"pairKey": row["pairKey"], "kind": "hard_case_fill",
            "family": row["family"], "priorityCellsPerWorkerSecond": row["priorityCellsPerWorkerSecond"]})
        selected_keys.add(row["pairKey"])
assert len(selected_keys) == len(selected)
write_json(OUTPUT / "proposed-phase.json", {"policyVersion": "common-c-adaptive-v1",
    "sourcePhase": estimate_summary["sourcePhase"], "selected": selected,
    "skippedVerifiedEstimateKeys": [row["pairKey"] for row in deferred if row["pairKey"] not in selected_keys],
    "deferredPathingHazardKeys": [row["pairKey"] for row in hazard_deferred],
    "estimateSummarySha256": sha(SOURCE / "summary.json"),
    "inferenceSummarySha256": sha(INFERENCE / "summary.json")})
summary = {"kind": "offline proposed hard-case queue; no combat run or live selection change",
    "sourcePhase": estimate_summary["sourcePhase"],
    "sourceUnresolvedProfilePairs": estimate_summary["sourceUnresolvedProfilePairs"],
    "deferredProvisionalEstimates": len(deferred),
    "deferredEstimateDisplayedCells": sum(row["aliases"] for row in deferred),
    "deferredThreeSeedMedianWorkerHours": sum(worker_cost(row) for row in deferred) / 3600,
    "mustRunOrValidateProfilePairs": len(hard),
    "ordinaryRunnableQueue": len(queue), "blockedOrPartial": len(blocked_or_partial),
    "deferredPathingHazards": len(hazard_deferred),
    "pathingHazardKinds": dict(collections.Counter(r["hazard"] for r in hazard_deferred)),
    "hardCategories": dict(category),
    "firstReviewCandidateCount": len(first),
    "validationProbeCount": len(validation_batch),
    "validationProbeByFamily": dict(probe_family_quota),
    "proposedPhasePairCount": len(selected),
    "prospectiveCandidatesScanned": len(priority),
    "scenarios": scenario_stats,
    "blockedOrPartialPairs": blocked_or_partial,
    "pathingHazardPairs": hazard_deferred,
    "simulationJobsRun": 0,
    "note": "Only prospective-verified, supported-context estimates are deferred as predictions. Known repeatedly stalled pathing families are separately deferred for V2-stream/physics review, never called wins or close fights. Candidate rules remain in the simulation queue and supply explicit validation probes. Conditional inference gains are estimated from existing corrected-engine winner margins and are not guaranteed."}
write_json(OUTPUT / "summary.json", summary)
print(json.dumps({k: v for k, v in summary.items() if k not in ("scenarios", "blockedOrPartialPairs")}, indent=2))
