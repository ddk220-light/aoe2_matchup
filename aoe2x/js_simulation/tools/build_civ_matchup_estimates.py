#!/usr/bin/env python3
"""Build provisional common-opponent estimates; never runs or imports combat."""
import collections
import gzip
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "calibration"
SOURCE_PHASE = int(os.environ.get("CIV_ESTIMATE_SOURCE_PHASE", "19"))
SOURCE = Path(os.environ.get("CIV_INFERENCE_CANDIDATE_DIR",
    str(CAL / "campaigns/civ-matchups-inference-inert-group-r1-only-audit-2026-11-01")))
RULES = Path(os.environ.get("CIV_COMMON_C_RULES",
    str(CAL / "reports/civ-matchups-ranking-inference-audit-2026-11-01/common-benchmark-sets.json")))
OUTPUT = Path(os.environ.get("CIV_ESTIMATE_OUTPUT_DIR",
    str(CAL / "campaigns/civ-matchups-provisional-estimates-phase019-2026-11-01")))
VARIANTS = Path(os.environ.get("CIV_VARIANT_PROFILES",
    "/workspace/aoe2_civ_inference_audit/aoe2x/js_simulation/calibration/campaigns/civ-matchups-inference-priority-phase019-2026-11-01/variant-profiles.json"))
DEFINITION = CAL / "campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json"
RANK = CAL / "campaigns/unit-rankings-consolidated-2026-10-29"
VETO = {"incomplete_current_seeds", "prior_engine_conflict", "orientation_conflict", "conflicting_inferences"}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")

def write_gzip_jsonl(path, rows):
    with path.open("wb") as target:
        with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as compressed:
            for row in rows:
                compressed.write((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode())

definition = json.loads(DEFINITION.read_text())
variants = json.loads(VARIANTS.read_text())
rules_file = json.loads(RULES.read_text())
rules = rules_file["rules"]
profiles = {v["key"]: v["profileHash"] for v in variants}
lines = {v["profileHash"]: v["line"] for v in variants}
aliases = collections.defaultdict(list)
for v in variants:
    aliases[v["profileHash"]].append(v["key"])
standard_hash = {m["teamKeys"][1]: profiles[m["teamKeys"][1]] for m in definition["matchups"]}
matchups = {m["id"]: m for m in definition["matchups"]}

ranking_rows = collections.defaultdict(list)
for filename in ("runs.jsonl", "additional-recorded-runs.jsonl"):
    for raw in (RANK / filename).read_text().splitlines():
        run = json.loads(raw)
        if run["selectionProvenance"]["engineVersion"] != "original":
            continue
        matchup = matchups[run["matchupId"]]
        a, c = [profiles[k] for k in matchup["teamKeys"]]
        winner = a if run["outcome"] == "win" else c if run["outcome"] == "loss" else None
        margin = (run["unitRemainingHp"] / run["unitStartingHp"] if winner == a
                  else -run["opponentRemainingHp"] / run["opponentStartingHp"] if winner == c else 0)
        ranking_rows[(a, c)].append((run["seed"], margin))

fingerprints = collections.defaultdict(dict)
for (a, c), records in ranking_rows.items():
    if not {0, 1, 2}.issubset({seed for seed, _ in records}):
        continue
    fingerprints[a][c] = sum(margin for _, margin in records) / len(records)

def family(row):
    return "|".join(sorted(lines[h] for h in row["profiles"]))

def count_shape(row):
    context = row["context"]
    return tuple(sorted((lines[h], n) for h, n in zip(context["profiles"], context["counts"])))

observed_shapes = collections.defaultdict(set)
source_rows = []
with gzip.open(SOURCE / "profile-matchups.jsonl.gz", "rt") as source:
    for raw in source:
        row = json.loads(raw)
        source_rows.append(row)
        if row["evidenceType"] == "observed":
            observed_shapes[family(row)].add(count_shape(row))

baseline_dir = Path(os.environ.get("CIV_VALIDATION_BASELINE_DIR", str(SOURCE)))
baseline_shapes = collections.defaultdict(set)
baseline_shapes_file = os.environ.get("CIV_VALIDATION_BASELINE_SHAPES")
baseline_supported_file = os.environ.get("CIV_VALIDATION_BASELINE_SUPPORTED_KEYS")
baseline_supported = (set(json.loads(gzip.open(baseline_supported_file, "rt").read()))
                      if baseline_supported_file else None)
if baseline_shapes_file:
    for name, shapes in json.loads(Path(baseline_shapes_file).read_text()).items():
        baseline_shapes[name].update(tuple((line, count) for line, count in shape) for shape in shapes)
else:
    with gzip.open(baseline_dir / "profile-matchups.jsonl.gz", "rt") as source:
        for raw in source:
            row = json.loads(raw)
            if row["evidenceType"] == "observed":
                baseline_shapes[family(row)].add(count_shape(row))

prospective_journal = os.environ.get("CIV_PROSPECTIVE_PHASE_JOURNAL")
prospective_runs_dir = os.environ.get("CIV_PROSPECTIVE_RUNS_DIR")
prospective_first_phase = int(os.environ.get("CIV_PROSPECTIVE_FIRST_PHASE", "20"))
minimum_prospective = int(os.environ.get("CIV_MINIMUM_PROSPECTIVE_PAIRS", "60"))
minimum_distinct_profiles = int(os.environ.get("CIV_MINIMUM_PROSPECTIVE_PROFILES", "12"))
prospective_journals = ([Path(prospective_journal)] if prospective_journal else [])
if prospective_runs_dir:
    runs_dir = Path(prospective_runs_dir)
    prospective_journals += sorted(p for p in runs_dir.glob("*.jsonl")
        if p.stem.isdecimal() and int(p.stem) >= prospective_first_phase
        and (runs_dir.parent / "phases" / f"{p.stem}-review.json").exists()
        and json.loads((runs_dir.parent / "phases" / f"{p.stem}-review.json").read_text())["status"] in ("passed", "complete_with_blocked"))
prospective_pairs = set()
prospective_source_markers = set()
prospective_checks = collections.defaultdict(collections.Counter)
prospective_profiles = collections.defaultdict(set)
for journal_path in prospective_journals:
    prospective_source_markers.add(f"/{journal_path.name}:")
    for raw in journal_path.read_text().splitlines():
        run = json.loads(raw)
        if run.get("eventLogHash") and run.get("pairKey"):
            prospective_pairs.add(run["pairKey"])
for row in source_rows:
    if row["evidenceType"] != "observed" or row["pairKey"] not in prospective_pairs:
        continue
    if baseline_supported is not None and row["pairKey"] not in baseline_supported:
        continue
    if not any(marker in source_id for source_id in row.get("sourceRunIds", [])
               for marker in prospective_source_markers):
        continue
    pair_family = family(row)
    rule = rules.get(pair_family)
    if not rule or not rule.get("selectedStandardsC"):
        continue
    cv = rule.get("crossValidation") or {}
    if cv.get("predicted", 0) < 20 or cv.get("wrong", 0) or cv.get("closeCalledDecisive", 0):
        continue
    if "unsupported_effect" in (row.get("reasonCodes") or []) or count_shape(row) not in baseline_shapes[pair_family]:
        continue
    a, b = row["profiles"]
    cs = [standard_hash[name] for name in rule["selectedStandardsC"]]
    if a in cs or b in cs or any(c not in fingerprints[a] or c not in fingerprints[b] for c in cs):
        continue
    deltas = [fingerprints[a][c] - fingerprints[b][c] for c in cs]
    threshold = rule["minimumSignedMarginGapPerC"]
    predicted = a if all(d >= threshold for d in deltas) else b if all(d <= -threshold for d in deltas) else None
    if predicted is None:
        continue
    actual = row.get("winnerProfileHash") if row["outcome"] != "close_uncertain" else None
    checked = prospective_checks[pair_family]
    checked["predicted"] += 1
    checked["correct" if predicted == actual else "wrong"] += 1
    prospective_profiles[pair_family].update(row["profiles"])
    if actual is None:
        checked["closeCalledDecisive"] += 1
disabled_families = set(json.loads(os.environ.get("CIV_DISABLED_COMMON_C_FAMILIES", "[]")))
disabled_families.update(name for name, checked in prospective_checks.items() if checked["wrong"])
verified_families = {name for name, checked in prospective_checks.items()
    if checked["predicted"] >= minimum_prospective
    and len(prospective_profiles[name]) >= minimum_distinct_profiles
    and name not in disabled_families}

estimates = []
unestimated = []
reasons = collections.Counter()
family_counts = collections.defaultdict(collections.Counter)
for row in source_rows:
    if row["outcome"] != "unresolved":
        continue
    pair_family = family(row)
    rule = rules.get(pair_family)
    if not rule or not rule.get("selectedStandardsC"):
        reason = "no_calibrated_common_c_rule"
    elif pair_family in disabled_families:
        reason = "prospective_counterexample"
    else:
        cv = rule.get("crossValidation") or {}
        if cv.get("predicted", 0) < 20 or cv.get("wrong", 0) or cv.get("closeCalledDecisive", 0):
            reason = "common_c_rule_failed_minimum_validation"
        elif VETO.intersection(row.get("reasonCodes") or []):
            reason = "source_conflict_or_missing_seeds"
        else:
            a, b = row["profiles"]
            standards = rule["selectedStandardsC"]
            cs = [standard_hash[name] for name in standards]
            if a in cs or b in cs or any(c not in fingerprints[a] or c not in fingerprints[b] for c in cs):
                reason = "missing_independent_common_c"
            else:
                deltas = [fingerprints[a][c] - fingerprints[b][c] for c in cs]
                threshold = rule["minimumSignedMarginGapPerC"]
                winner = a if all(delta >= threshold for delta in deltas) else b if all(delta <= -threshold for delta in deltas) else None
                if winner is None:
                    reason = "common_c_disagreement_or_small_margin"
                else:
                    unsupported = "unsupported_effect" in (row.get("reasonCodes") or [])
                    new_count_shape = count_shape(row) not in observed_shapes[pair_family]
                    tier = ("effect_and_count_extrapolation" if unsupported and new_count_shape else
                            "effect_extrapolation" if unsupported else
                            "count_extrapolation" if new_count_shape else "supported_context_estimate")
                    evidence = [{"standard": name, "aSignedMargin": fingerprints[a][c],
                                 "bSignedMargin": fingerprints[b][c], "delta": delta}
                                for name, c, delta in zip(standards, cs, deltas)]
                    estimates.append({"pairKey": row["pairKey"], "aliases": row["aliases"],
                        "profiles": row["profiles"], "representativeUnits": [aliases[h][0] for h in row["profiles"]],
                        "predictedWinnerProfileHash": winner, "tier": tier, "family": pair_family,
                        "context": row["context"], "reasonCodes": row.get("reasonCodes", []),
                        "commonOpponents": evidence, "minimumSignedMarginGapPerC": threshold,
                        "ruleCrossValidation": cv, "sourceConclusion": row["outcome"],
                        "ruleStatus": "verified" if pair_family in verified_families else "candidate",
                        "eligibleForProspectiveValidation": (baseline_supported is None or row["pairKey"] in baseline_supported),
                        "skippable": tier == "supported_context_estimate" and pair_family in verified_families
                            and (baseline_supported is None or row["pairKey"] in baseline_supported)})
                    family_counts[pair_family][tier] += 1
                    continue
    reasons[reason] += 1
    unestimated.append({"pairKey": row["pairKey"], "aliases": row["aliases"],
        "family": pair_family, "context": row["context"], "whyNoEstimate": reason,
        "reasonCodes": row.get("reasonCodes", [])})

expected_unresolved = json.loads((SOURCE / "summary.json").read_text())["coverage"]["profiles"]["unresolved"]
assert len(estimates) + len(unestimated) == expected_unresolved
assert len({x["pairKey"] for x in estimates}) == len(estimates)
assert len({x["pairKey"] for x in unestimated}) == len(unestimated)
assert not ({x["pairKey"] for x in estimates} & {x["pairKey"] for x in unestimated})
OUTPUT.mkdir(parents=True, exist_ok=True)
write_gzip_jsonl(OUTPUT / "estimated.jsonl.gz", sorted(estimates, key=lambda x: x["pairKey"]))
write_gzip_jsonl(OUTPUT / "still-unestimated.jsonl.gz", sorted(unestimated, key=lambda x: x["pairKey"]))
summary = {
    "kind": "provisional common-opponent estimates; not current-engine observations or decisive inferred conclusions",
    "sourcePhase": SOURCE_PHASE, "totalProfilePairs": 68916,
    "sourceUnresolvedProfilePairs": expected_unresolved,
    "estimatedProfilePairs": len(estimates), "estimatedDisplayedCells": sum(x["aliases"] for x in estimates),
    "stillUnestimatedProfilePairs": len(unestimated), "stillUnestimatedDisplayedCells": sum(x["aliases"] for x in unestimated),
    "estimateTiers": dict(collections.Counter(x["tier"] for x in estimates)),
    "supportedCandidateProspectivePool": sum(x["tier"] == "supported_context_estimate"
        and x["eligibleForProspectiveValidation"] for x in estimates),
    "noEstimateReasons": dict(reasons),
    "prospectivePhase": {"journals": [str(p) for p in prospective_journals],
        "completedPairKeys": len(prospective_pairs),
        "byFamily": {k: dict(v) for k, v in sorted(prospective_checks.items())},
        "distinctProfilesByFamily": {k: len(v) for k, v in sorted(prospective_profiles.items())},
        "disabledFamilies": sorted(disabled_families), "verifiedFamilies": sorted(verified_families),
        "minimumIndependentPairsForVerification": minimum_prospective,
        "minimumDistinctProfilesForVerification": minimum_distinct_profiles,
        "baselineObservedShapes": baseline_shapes_file or str(baseline_dir)},
    "skippableProfilePairs": sum(x["skippable"] for x in estimates),
    "byFamily": {k: dict(v) for k, v in sorted(family_counts.items())},
    "simulationJobsRun": 0,
    "rules": "unit-line rule must have >=20 pair-level CV predictions, zero wrong winners and zero close-as-decisive errors",
    "sourceHashes": {"profileMatchups": sha(SOURCE / "profile-matchups.jsonl.gz"),
        "inferenceSummary": sha(SOURCE / "summary.json"),
        "variantProfiles": sha(VARIANTS), "commonCSelection": sha(RULES),
        "rankingRuns": sha(RANK / "runs.jsonl"),
        "rankingExtraRuns": sha(RANK / "additional-recorded-runs.jsonl"),
        "definition": sha(DEFINITION),
        "validationBaseline": sha(Path(baseline_shapes_file) if baseline_shapes_file else baseline_dir / "profile-matchups.jsonl.gz"),
        **({"validationBaselineSupportedPairs": sha(Path(baseline_supported_file))} if baseline_supported_file else {}),
        "prospectiveJournals": {str(p): sha(p) for p in prospective_journals}},
}
write_json(OUTPUT / "summary.json", summary)
print(json.dumps(summary, indent=2))
