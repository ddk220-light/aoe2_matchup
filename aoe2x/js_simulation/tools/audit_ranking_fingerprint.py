#!/usr/bin/env python3
"""Offline ranking-fingerprint hypotheses against saved V3 civ fights; no sims."""
import collections
import gzip
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT_PHASE = int(os.environ.get("CIV_HOLDOUT_PHASE_MIN", "15"))
CAL = ROOT / "calibration"
RANK = CAL / "campaigns/unit-rankings-consolidated-2026-10-29"
DEFINITION = CAL / "campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json"
CIV = Path(os.environ.get("CIV_INFERENCE_INPUT_DIR",
    "/workspace/aoe2_civ_inference_audit/aoe2x/js_simulation/calibration/campaigns/civ-matchups-inference-priority-phase019-2026-11-01"))
CANDIDATE = Path(os.environ.get("CIV_INFERENCE_CANDIDATE_DIR",
    str(CAL / "campaigns/civ-matchups-inference-inert-group-r1-only-audit-2026-11-01")))

definition = json.loads(DEFINITION.read_text())
variants = json.loads((CIV / "variant-profiles.json").read_text())
profile = {v["key"]: v["profileHash"] for v in variants}
line = {v["profileHash"]: v["line"] for v in variants}
matchup = {m["id"]: m for m in definition["matchups"]}
ranking = collections.defaultdict(list)
fingerprints = collections.defaultdict(list)

for source in ("runs.jsonl", "additional-recorded-runs.jsonl"):
    for raw in (RANK / source).read_text().splitlines():
        r = json.loads(raw)
        m = matchup[r["matchupId"]]
        a, b = (profile[k] for k in m["teamKeys"])
        winner = a if r["outcome"] == "win" else b if r["outcome"] == "loss" else None
        hp = (r["unitRemainingHp"] / r["unitStartingHp"] if winner == a
              else r["opponentRemainingHp"] / r["opponentStartingHp"] if winner == b else 0)
        engine = r["selectionProvenance"]["engineVersion"]
        key = (engine, "|".join(sorted((a, b))), m["scenarioHash"], tuple(sorted(zip((a, b), m["counts"]))))
        ranking[key].append((r["seed"], winner, hp))
        if engine == "original":
            fingerprints[(a, b, m["scenarioHash"], tuple(m["counts"]))].append((r["seed"], winner, hp))

fp = collections.defaultdict(dict)
fp_bounds = collections.defaultdict(dict)
for (a, b, scenario, counts), rows in fingerprints.items():
    if not {0, 1, 2}.issubset({r[0] for r in rows}):
        continue
    signed = [hp if winner == a else -hp if winner == b else 0 for _, winner, hp in rows]
    fp[a][b] = sum(signed) / len(signed)
    fp_bounds[a][b] = (min(signed), max(signed))

scores = collections.defaultdict(list)
for r in json.loads((CAL / "reports/unit-ranking-scores-final-2026-10-29/scores.json").read_text()):
    scores[profile[f'{r["civilization"]}|{r["unitSlug"]}']].append(r["score"])
scores = {k: sum(v) / len(v) for k, v in scores.items()}

phase_for_pair = {}
adaptive = Path(os.environ.get("CIV_ADAPTIVE_RUNS_DIR",
    "/workspace/aoe2_civ_v3_patrol_diag/aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31/adaptive/runs"))
for journal in sorted(adaptive.glob("*.jsonl")):
    if not journal.stem.isdigit():
        continue
    phase = int(journal.stem)
    for raw in journal.read_text().splitlines():
        r = json.loads(raw)
        if r.get("eventLogHash") and r.get("pairKey"):
            phase_for_pair.setdefault(r["pairKey"], phase)

direct = []
with gzip.open(CIV / "profile-matchups.jsonl.gz", "rt") as f:
    for raw in f:
        r = json.loads(raw)
        if r["evidenceType"] == "observed":
            direct.append(r)

# Cost affects the approved army-count calculation. Once both integer counts
# are fixed, it does not change combat in these homogeneous fights. Compare
# only profiles whose every other mechanics field is bytewise equal.
physical = {}
for v in variants:
    mechanics = definition["profiles"][v["key"]]["mechanics"]
    normalized = {k: value for k, value in mechanics.items() if k not in ("civilization", "cost")}
    physical[v["profileHash"]] = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def physical_key(row):
    c = row["context"]
    return tuple(physical[h] for h in c["profiles"]), tuple(c["counts"]), c["scenarioHash"]

physical_roots = collections.defaultdict(list)
for row in direct:
    if phase_for_pair.get(row["pairKey"], 0) >= HOLDOUT_PHASE:
        continue
    winner = None if row["outcome"] == "close_uncertain" else row["context"]["profiles"].index(row["winnerProfileHash"])
    physical_roots[physical_key(row)].append(winner)

def strong_common_prediction(row, threshold=.5):
    a, b = row["profiles"]
    common = (set(fp[a]) & set(fp[b])) - {a, b}
    if len(common) < 3:
        return None
    gaps = [fp[a][s] - fp[b][s] for s in common]
    if all(g >= threshold for g in gaps):
        return a
    if all(g <= -threshold for g in gaps):
        return b
    return None

def family(row):
    return "|".join(sorted(line[h] for h in row["profiles"]))

def interval_prediction(row, minimum=.25):
    a, b = row["profiles"]
    common = (set(fp_bounds[a]) & set(fp_bounds[b])) - {a, b}
    if len(common) < 3:
        return None
    if all(fp_bounds[a][s][0] - fp_bounds[b][s][1] >= minimum for s in common):
        return a
    if all(fp_bounds[b][s][0] - fp_bounds[a][s][1] >= minimum for s in common):
        return b
    return None

def evaluate_family_rule(threshold):
    family_train = collections.defaultdict(collections.Counter)
    for row in direct:
        if phase_for_pair.get(row["pairKey"], 0) >= 15:
            continue
        prediction = strong_common_prediction(row, threshold)
        if prediction is None:
            continue
        actual = row.get("winnerProfileHash") if row["outcome"] != "close_uncertain" else None
        family_train[family(row)]["predicted"] += 1
        family_train[family(row)]["correct" if prediction == actual else "wrong"] += 1
    enabled = {f for f, counts in family_train.items()
               if counts["predicted"] >= 10 and counts["wrong"] == 0}
    holdout = collections.Counter()
    for row in direct:
        if phase_for_pair.get(row["pairKey"], 0) < 15 or family(row) not in enabled:
            continue
        prediction = strong_common_prediction(row, threshold)
        if prediction is None:
            continue
        actual = row.get("winnerProfileHash") if row["outcome"] != "close_uncertain" else None
        holdout["predicted"] += 1
        holdout["correct" if prediction == actual else "wrong"] += 1
    return {"train": {k: dict(v) for k, v in sorted(family_train.items())},
            "enabledFamilies": sorted(enabled), "laterPhaseHoldout": dict(holdout)}

family_filtered = {str(t): evaluate_family_rule(t) for t in (.25, .5, .75)}

results = collections.defaultdict(collections.Counter)
unresolved_candidates = collections.Counter()
wrong_examples = collections.defaultdict(list)
alias = {v["profileHash"]: v["key"] for v in variants}

def record(name, prediction, row):
    if prediction is None:
        return
    actual = row.get("winnerProfileHash") if row["outcome"] != "close_uncertain" else None
    results[name]["predicted"] += 1
    results[name]["correct" if prediction == actual else "wrong"] += 1
    if prediction != actual and len(wrong_examples[name]) < 5:
        wrong_examples[name].append({"pairKey": row["pairKey"],
            "units": [alias[h] for h in row["profiles"]],
            "predicted": alias.get(prediction), "actual": alias.get(actual),
            "close": actual is None})
    if actual is None:
        results[name]["close_called_decisive"] += 1

for row in direct:
    if phase_for_pair.get(row["pairKey"], 0) < HOLDOUT_PHASE:
        continue
    a, b = row["profiles"]
    context = row["context"]
    root_winners = set(physical_roots.get(physical_key(row), []))
    if len(root_winners) == 1 and None not in root_winners:
        record("cost_neutral_exact_physics", context["profiles"][next(iter(root_winners))], row)
    for minimum in (.25, .5):
        record(f"common_seed_interval_n3_gap{int(minimum*100)}", interval_prediction(row, minimum), row)
    rkey = (row["pairKey"], context["scenarioHash"], tuple(sorted(zip(context["profiles"], context["counts"]))))
    old = ranking.get(("original",) + rkey)
    if old and {0, 1, 2}.issubset({r[0] for r in old}):
        winners = {r[1] for r in old}
        if len(winners) == 1:
            old_winner = next(iter(winners))
            margin = min(r[2] for r in old)
            for threshold in (0, .1, .25, .5):
                if margin >= threshold:
                    record(f"old_direct_margin_ge_{threshold}", old_winner, row)

    if a in scores and b in scores:
        gap = scores[a] - scores[b]
        for threshold in (0, 5, 10, 20):
            if abs(gap) >= threshold:
                record(f"global_score_gap_ge_{threshold}", a if gap > 0 else b, row)
                if line[a] == line[b]:
                    record(f"same_line_score_gap_ge_{threshold}", a if gap > 0 else b, row)

    common = sorted((set(fp[a]) & set(fp[b])) - {a, b})
    if not common:
        continue
    gaps = [fp[a][s] - fp[b][s] for s in common]
    mean = sum(gaps) / len(gaps)
    for minimum in (1, 2, 3):
        if len(common) < minimum:
            continue
        for threshold in (.25, .5, 1.0):
            if abs(mean) >= threshold:
                record(f"common_mean_n{minimum}_gap{threshold}", a if mean > 0 else b, row)
            if all(g >= threshold for g in gaps):
                record(f"common_unanimous_n{minimum}_gap{threshold}", a, row)
            elif all(g <= -threshold for g in gaps):
                record(f"common_unanimous_n{minimum}_gap{threshold}", b, row)
    if any(fp[a][s] >= .25 and fp[b][s] <= -.25 for s in common):
        record("common_winner_vs_loser_margin25", a, row)
    elif any(fp[b][s] >= .25 and fp[a][s] <= -.25 for s in common):
        record("common_winner_vs_loser_margin25", b, row)
    relevant = [g for s, g in zip(common, gaps) if line[s] in (line[a], line[b])]
    if relevant and abs(sum(relevant) / len(relevant)) >= .5:
        record("relevant_line_mean_gap50", a if sum(relevant) > 0 else b, row)
    if relevant and all(g >= .25 for g in relevant):
        record("relevant_line_unanimous_gap25", a, row)
    elif relevant and all(g <= -.25 for g in relevant):
        record("relevant_line_unanimous_gap25", b, row)
    if line[a] == line[b]:
        if abs(mean) >= .5:
            record("same_line_common_mean_gap50", a if mean > 0 else b, row)
        if all(g >= .25 for g in gaps):
            record("same_line_common_unanimous_gap25", a, row)
        elif all(g <= -.25 for g in gaps):
            record("same_line_common_unanimous_gap25", b, row)

with gzip.open(CANDIDATE / "profile-matchups.jsonl.gz", "rt") as f:
    for raw in f:
        row = json.loads(raw)
        if row["outcome"] != "unresolved":
            continue
        a, b = row["profiles"]
        common = (set(fp[a]) & set(fp[b])) - {a, b}
        if not common:
            continue
        gaps = [fp[a][s] - fp[b][s] for s in common]
        if abs(sum(gaps) / len(gaps)) >= .5:
            unresolved_candidates["common_mean_gap50"] += 1
        if all(g >= .5 for g in gaps) or all(g <= -.5 for g in gaps):
            unresolved_candidates["common_unanimous_gap50"] += 1
            if len(common) >= 3:
                unresolved_candidates["common_unanimous_n3_gap50"] += 1
        if len(common) >= 3 and (all(g >= .25 for g in gaps) or all(g <= -.25 for g in gaps)):
            unresolved_candidates["common_unanimous_n3_gap25"] += 1
        for threshold in (.25, .5, .75):
            if family(row) in family_filtered[str(threshold)]["enabledFamilies"] and len(common) >= 3 and (all(g >= threshold for g in gaps) or all(g <= -threshold for g in gaps)):
                unresolved_candidates[f"trained_family_common_unanimous_n3_gap{int(threshold*100)}"] += 1
        if line[a] == line[b] and abs(sum(gaps) / len(gaps)) >= .5:
            unresolved_candidates["same_line_common_mean_gap50"] += 1
        if line[a] == line[b] and (all(g >= .25 for g in gaps) or all(g <= -.25 for g in gaps)):
            unresolved_candidates["same_line_common_unanimous_gap25"] += 1
        for minimum in (.25, .5):
            if interval_prediction(row, minimum) is not None:
                unresolved_candidates[f"common_seed_interval_n3_gap{int(minimum*100)}"] += 1

output = {
    "kind": "offline holdout of ranking-outcome fingerprints against direct V3 civ fights",
    "holdout": f"adaptive phases {HOLDOUT_PHASE:03d}-019; whole profile pair and all its seeds held out",
    "rankingSource": "original-engine ranking records only; predictive features, not eligible current-engine measurements",
    "directHoldoutPairs": sum(phase_for_pair.get(r["pairKey"], 0) >= HOLDOUT_PHASE for r in direct),
    "metrics": {k: dict(v) for k, v in sorted(results.items())},
    "wrongExamples": dict(wrong_examples),
    "candidateUnresolvedProfilePairs": dict(unresolved_candidates),
    "familyFilteredRules": family_filtered,
    "simulationJobsRun": 0,
}
print(json.dumps(output, indent=2))
