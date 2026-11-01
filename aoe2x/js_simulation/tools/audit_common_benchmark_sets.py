#!/usr/bin/env python3
"""Select common ranking opponents C per unit-line pair, with pair-level CV."""
import collections
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "calibration"
CIV = Path(os.environ.get("CIV_INFERENCE_INPUT_DIR",
    "/workspace/aoe2_civ_inference_audit/aoe2x/js_simulation/calibration/campaigns/civ-matchups-inference-priority-phase019-2026-11-01"))
CANDIDATE = Path(os.environ.get("CIV_INFERENCE_CANDIDATE_DIR",
    str(CAL / "campaigns/civ-matchups-inference-inert-group-r1-only-audit-2026-11-01")))
definition = json.loads((CAL / "campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json").read_text())
variants = json.loads((CIV / "variant-profiles.json").read_text())
profile = {v["key"]: v["profileHash"] for v in variants}
line = {v["profileHash"]: v["line"] for v in variants}
std_names = {profile[m["teamKeys"][1]]: m["teamKeys"][1] for m in definition["matchups"]}
matchup = {m["id"]: m for m in definition["matchups"]}
fingerprint_rows = collections.defaultdict(list)
for source in ("runs.jsonl", "additional-recorded-runs.jsonl"):
    for raw in (CAL / "campaigns/unit-rankings-consolidated-2026-10-29" / source).read_text().splitlines():
        r = json.loads(raw)
        if r["selectionProvenance"]["engineVersion"] != "original":
            continue
        m = matchup[r["matchupId"]]
        a, c = [profile[k] for k in m["teamKeys"]]
        winner = a if r["outcome"] == "win" else c if r["outcome"] == "loss" else None
        hp = (r["unitRemainingHp"] / r["unitStartingHp"] if winner == a else
              r["opponentRemainingHp"] / r["opponentStartingHp"] if winner == c else 0)
        fingerprint_rows[(a, c)].append((r["seed"], hp if winner == a else -hp if winner == c else 0))

fp = collections.defaultdict(dict)
for (a, c), rows in fingerprint_rows.items():
    if {0, 1, 2}.issubset({seed for seed, _ in rows}):
        fp[a][c] = sum(value for _, value in rows) / len(rows)

def features(row):
    a, b = row["profiles"]
    return {c: fp[a][c] - fp[b][c] for c in (set(fp[a]) & set(fp[b])) - {a, b}}

def predict(values, standards, threshold):
    if not all(c in values for c in standards):
        return None
    delta = [values[c] for c in standards]
    if all(x >= threshold for x in delta):
        return 0
    if all(x <= -threshold for x in delta):
        return 1
    return None

def truth(row):
    if row["outcome"] == "close_uncertain":
        return None
    return row["profiles"].index(row["winnerProfileHash"])

observed = collections.defaultdict(list)
with gzip.open(CIV / "profile-matchups.jsonl.gz", "rt") as f:
    for raw in f:
        row = json.loads(raw)
        a, b = row["profiles"]
        if row["evidenceType"] == "observed":
            observed["|".join(sorted((line[a], line[b])))].append((row, features(row)))

THRESHOLDS = (.1, .25, .5)

def candidates(rows):
    standards = sorted({c for _, vals in rows for c in vals})
    for size in (1, 2, 3, 4):
        for selection in itertools.combinations(standards, size):
            for threshold in THRESHOLDS:
                yield selection, threshold

def evaluate(rows, rule):
    selection, threshold = rule
    counts = collections.Counter()
    for row, vals in rows:
        guess = predict(vals, selection, threshold)
        if guess is None:
            continue
        counts["predicted"] += 1
        counts["correct" if guess == truth(row) else "wrong"] += 1
        if truth(row) is None:
            counts["closeCalledDecisive"] += 1
    return counts

def choose(rows, minimum=8, min_size=1):
    best = None
    for rule in candidates(rows):
        if len(rule[0]) < min_size:
            continue
        counts = evaluate(rows, rule)
        if counts["predicted"] < minimum or counts["wrong"]:
            continue
        # Favour coverage, then more independent C checks and a larger gap.
        key = (counts["predicted"], len(rule[0]), rule[1], tuple(rule[0]))
        if best is None or key > best[0]:
            best = (key, rule, counts)
    return best

unresolved = collections.defaultdict(list)
with gzip.open(CANDIDATE / "profile-matchups.jsonl.gz", "rt") as f:
    for raw in f:
        row = json.loads(raw)
        a, b = row["profiles"]
        if row["outcome"] == "unresolved":
            unresolved["|".join(sorted((line[a], line[b])))].append((row, features(row)))

report = {}
for unit_line, rows in sorted(observed.items()):
    if len(rows) < 25:
        continue
    folds = [[] for _ in range(5)]
    for row, vals in rows:
        index = int(hashlib.sha256(row["pairKey"].encode()).hexdigest()[:8], 16) % 5
        folds[index].append((row, vals))
    cv = collections.Counter()
    selected = collections.Counter()
    for fold in range(5):
        train = [item for i, group in enumerate(folds) if i != fold for item in group]
        best = choose(train)
        if best is None:
            continue
        rule = best[1]
        selected[tuple(std_names.get(c, c) for c in rule[0])] += 1
        cv.update(evaluate(folds[fold], rule))
    final = choose(rows)
    if final is None:
        report[unit_line] = {"observedPairs": len(rows), "crossValidation": dict(cv),
                             "status": "no error-free training rule with 8 predictions"}
        continue
    rule = final[1]
    report[unit_line] = {
        "observedPairs": len(rows),
        "selectedStandardsC": [std_names.get(c, c) for c in rule[0]],
        "minimumSignedMarginGapPerC": rule[1],
        "training": dict(final[2]),
        "crossValidation": dict(cv),
        "foldSelections": {"+".join(k): v for k, v in selected.items()},
        "unresolvedCandidates": sum(predict(vals, rule[0], rule[1]) is not None
                                    for _, vals in unresolved[unit_line]),
        "candidatesWithUnsupportedEffect": sum(
            predict(vals, rule[0], rule[1]) is not None
            and "unsupported_effect" in (row.get("reasonCodes") or [])
            for row, vals in unresolved[unit_line]),
        "singleBenchmarkTrials": {
            std_names.get(c, c): {str(t): dict(evaluate(rows, ((c,), t))) for t in THRESHOLDS}
            for c in sorted({c for _, vals in rows for c in vals})
        },
    }
    # The user-requested multi-C version is evaluated independently of the
    # unconstrained search; a perfect single benchmark may be too brittle.
    multi_cv = collections.Counter()
    for fold in range(5):
        train = [item for i, group in enumerate(folds) if i != fold for item in group]
        best_multi = choose(train, min_size=2)
        if best_multi is not None:
            multi_cv.update(evaluate(folds[fold], best_multi[1]))
    multi = choose(rows, min_size=2)
    report[unit_line]["multiStandard"] = ({"status": "no eligible two-or-more-C rule",
        "crossValidation": dict(multi_cv)} if multi is None else {
        "selectedStandardsC": [std_names.get(c, c) for c in multi[1][0]],
        "minimumSignedMarginGapPerC": multi[1][1],
        "training": dict(multi[2]),
        "crossValidation": dict(multi_cv),
        "unresolvedCandidates": sum(predict(vals, multi[1][0], multi[1][1]) is not None
                                    for _, vals in unresolved[unit_line]),
    })
    if unit_line == "archer|archer":
        named = [
            ("Chinese|arbalester", "Saracens|hand_cannoneer"),
            ("Chinese|arbalester", "Spanish|imp_elite_skirm"),
            ("Chinese|arbalester", "Spanish|champion"),
            ("Chinese|arbalester", "Saracens|hand_cannoneer", "Spanish|imp_elite_skirm"),
        ]
        by_name = {name: h for h, name in std_names.items()}
        report[unit_line]["namedSetTrials"] = {
            "+".join(group): {str(t): {"observed": dict(evaluate(rows, (tuple(by_name[n] for n in group), t))),
                "unresolvedCandidates": sum(predict(vals, tuple(by_name[n] for n in group), t) is not None
                                            for _, vals in unresolved[unit_line])}
                for t in THRESHOLDS}
            for group in named
        }

print(json.dumps({"kind": "offline common-C subset search by unit-line pair",
    "source": "original ranking seeds as features; verified V3 civ profile pairs as labels",
    "validation": "five pair-key hash folds; select C and threshold on four folds, test untouched fifth; close is an error",
    "rules": report, "simulationJobsRun": 0}, indent=2))
