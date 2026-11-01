#!/usr/bin/env python3
"""Offline, time-held-out coverage audit for matchup winner predictors.

All ranking values are features only. This script never runs combat or writes
to the live campaign. It does not promote statistical guesses into evidence.
"""

import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, ExtraTreesClassifier


SIM = Path(__file__).resolve().parents[1]
RANK = SIM / "calibration/campaigns/unit-rankings-consolidated-2026-10-29"
DEFINITION = SIM / "calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json"


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(path):
    with gzip.open(path, "rt") as source:
        yield from map(json.loads, source)


def phase_of(row):
    phases = {int(part.rsplit("/", 1)[-1].split(".jsonl:")[0])
              for part in row.get("sourceRunIds", ())
              if "/adaptive/runs/" in part and ".jsonl:" in part}
    return max(phases) if phases else 0


def make_edges(rows, profile_index):
    n = len(profile_index)
    graph = np.full((n, n), np.nan, dtype=np.float32)
    for row in rows:
        a, b = (profile_index[h] for h in row["profiles"])
        value = (1 if row["outcome"] == "a_win" else -1 if row["outcome"] == "b_win" else 0)
        graph[a, b], graph[b, a] = value, -value
    return graph


def rank_fingerprints(variants, definition, profile_index):
    profiles = {v["key"]: v["profileHash"] for v in variants}
    standards = sorted({m["teamKeys"][1] for m in definition["matchups"]})
    standard_index = {key: i for i, key in enumerate(standards)}
    jobs = {m["id"]: m for m in definition["matchups"]}
    values = collections.defaultdict(list)
    for name in ("runs.jsonl", "additional-recorded-runs.jsonl"):
        for raw in (RANK / name).read_text().splitlines():
            run = json.loads(raw)
            if run["selectionProvenance"]["engineVersion"] != "original":
                continue
            job = jobs[run["matchupId"]]
            a, c = (profiles[key] for key in job["teamKeys"])
            margin = (run["unitRemainingHp"] / run["unitStartingHp"] if run["outcome"] == "win"
                      else -run["opponentRemainingHp"] / run["opponentStartingHp"]
                      if run["outcome"] == "loss" else 0)
            values[(a, c)].append((run["seed"], margin))
    matrix = np.full((len(profile_index), len(standards)), np.nan, dtype=np.float32)
    for (a, c), entries in values.items():
        if {0, 1, 2}.issubset({seed for seed, _ in entries}):
            matrix[profile_index[a], standard_index[next(key for key in standards
                if profiles[key] == c)]] = np.mean([margin for _, margin in entries])
    return standards, matrix


def stats_matrix(variants, definition, profile_index):
    result = np.full((len(profile_index), 21), np.nan, dtype=np.float32)
    for v in variants:
        m = definition["profiles"][v["key"]]["mechanics"]
        a, armor = m["attack_classes"], m["armor_classes"]
        cost = m["cost"]
        effects, ranged = m.get("effects") or {}, m.get("ranged") or {}
        charge = m.get("charge") or {}
        melee_charge = m.get("melee_charge") or {}
        result[profile_index[v["profileHash"]]] = [m["hp"], m["speed_tiles_per_second"],
            m["reload_seconds"], m["attack_range_tiles"],
            a.get("3", 0), a.get("4", 0), armor.get("3", 0), armor.get("4", 0),
            m["collision_size_tiles"]["x"], m["outline_size_tiles"]["x"],
            cost.get("food", 0), cost.get("wood", 0), cost.get("gold", 0),
            ranged.get("extra_projectile_count", 0), ranged.get("accuracy_percent", 100),
            charge.get("max_charge", 0), melee_charge.get("attack_bonus", 0),
            int(bool(effects.get("ignores_melee_armor"))),
            int(bool(effects.get("ignores_pierce_armor"))),
            effects.get("bonus_damage_reduction", 0),
            int(m.get("mode") == "repeating_volley")]
    return result


def make_margin_edges(train, profile_index, ledger_path):
    lookup = {r["pairKey"]: r for r in train}
    margins = collections.defaultdict(list)
    for record in records(ledger_path):
        if not record["corrected"]:
            continue
        hashes = record["profileHashes"]
        key = "|".join(sorted(hashes))
        target = lookup.get(key)
        if not target or target["context"]["scenarioHash"] != record["scenarioHash"]:
            continue
        counts = dict(zip(hashes, record["counts"]))
        expected = dict(zip(target["context"]["profiles"], target["context"]["counts"]))
        if counts != expected:
            continue
        a = target["profiles"][0]
        margin = (record["unitRemainingHp"] / record["unitStartingHp"]
                  if record["winnerHash"] == a and hashes[0] == a
                  else record["opponentRemainingHp"] / record["opponentStartingHp"]
                  if record["winnerHash"] == a else
                  -record["unitRemainingHp"] / record["unitStartingHp"]
                  if record["winnerHash"] == hashes[0] else
                  -record["opponentRemainingHp"] / record["opponentStartingHp"]
                  if record["winnerHash"] else 0)
        margins[key].append(margin)
    matrix = np.full((len(profile_index), len(profile_index)), np.nan, dtype=np.float32)
    for key, values in margins.items():
        a, b = [profile_index[h] for h in lookup[key]["profiles"]]
        matrix[a, b] = np.mean(values)
        matrix[b, a] = -matrix[a, b]
    return matrix, len(margins)


def features(rows, index, rank, stats, line_ids, graph, margin_graph,
             damage, standard_indices):
    n = len(line_ids)
    grouped = collections.defaultdict(list)
    for i, line in enumerate(line_ids):
        grouped[line].append(i)
    all_lines = sorted(grouped)
    vectors = []
    for row in rows:
        a, b = [index[h] for h in row["profiles"]]
        counts = dict(zip(row["context"]["profiles"], row["context"]["counts"]))
        ca, cb = counts[row["profiles"][0]], counts[row["profiles"][1]]
        ranks = rank[a] - rank[b]
        valid_rank = np.isfinite(ranks)
        rank_values = np.where(valid_rank, ranks, 0)
        row_stats = stats[a] - stats[b]
        direct_damage = float(damage[a, b]), float(damage[b, a])
        dps_a = direct_damage[0] / max(stats[a, 2], .1)
        dps_b = direct_damage[1] / max(stats[b, 2], .1)
        combat = [*direct_damage, dps_a, dps_b,
            ca * dps_a, cb * dps_b, stats[b, 0] / max(direct_damage[0], 1),
            stats[a, 0] / max(direct_damage[1], 1),
            ca * stats[a, 0], cb * stats[b, 0],
            dps_a / max(dps_b, .01),
            (ca * dps_a) / max(cb * dps_b, .01)]
        common = np.isfinite(graph[a]) & np.isfinite(graph[b])
        common[a] = common[b] = False
        diffs = graph[a, common] - graph[b, common]
        margin_common = np.isfinite(margin_graph[a]) & np.isfinite(margin_graph[b])
        margin_common[a] = margin_common[b] = False
        margin_diffs = margin_graph[a, margin_common] - margin_graph[b, margin_common]
        summary = [len(diffs), np.mean(diffs) if len(diffs) else 0,
                   np.min(diffs) if len(diffs) else 0,
                   np.max(diffs) if len(diffs) else 0,
                   np.mean(diffs > 0) if len(diffs) else 0,
                   np.mean(diffs < 0) if len(diffs) else 0]
        margin_summary = [len(margin_diffs), np.mean(margin_diffs) if len(margin_diffs) else 0,
                          np.min(margin_diffs) if len(margin_diffs) else 0,
                          np.max(margin_diffs) if len(margin_diffs) else 0,
                          np.std(margin_diffs) if len(margin_diffs) else 0]
        ranked = rank_values[valid_rank]
        rank_consensus = [len(ranked), np.min(ranked) if len(ranked) else 0,
                          np.max(ranked) if len(ranked) else 0,
                          np.std(ranked) if len(ranked) else 0,
                          np.sum(ranked >= .1), np.sum(ranked <= -.1),
                          np.sum(ranked >= .25), np.sum(ranked <= -.25)]
        standard_relevance = []
        for c, value in zip(standard_indices, rank_values):
            similarity_a = 1 / (1 + abs(stats[c, 6]-stats[a, 6])
                + abs(stats[c, 7]-stats[a, 7]) + abs(stats[c, 1]-stats[a, 1]))
            similarity_b = 1 / (1 + abs(stats[c, 6]-stats[b, 6])
                + abs(stats[c, 7]-stats[b, 7]) + abs(stats[c, 1]-stats[b, 1]))
            standard_relevance.extend((value * similarity_a, value * similarity_b))
        by_line = []
        margins_by_line = []
        for line in all_lines:
            pos = [c for c in grouped[line] if common[c]]
            d = graph[a, pos] - graph[b, pos]
            by_line += [len(d), float(np.mean(d)) if len(d) else 0]
            pos_margin = [c for c in grouped[line] if margin_common[c]]
            dm = margin_graph[a, pos_margin] - margin_graph[b, pos_margin]
            margins_by_line += [len(dm), float(np.mean(dm)) if len(dm) else 0]
        vectors.append(np.r_[ca, cb, ca / cb, line_ids[a], line_ids[b],
            row_stats, stats[a], stats[b], combat,
            rank_values, valid_rank.astype(float), standard_relevance, rank_consensus,
            np.mean(rank_values[valid_rank]) if valid_rank.any() else 0,
            valid_rank.sum(), summary, margin_summary, by_line, margins_by_line])
    return np.asarray(vectors, dtype=np.float32)


def outcome(row):
    return 1 if row["outcome"] == "a_win" else -1 if row["outcome"] == "b_win" else 0


def assessed(prob, labels, thresholds):
    direction = np.where(prob[:, 2] >= prob[:, 0], 1, -1)
    confidence = np.maximum(prob[:, 2], prob[:, 0])
    result = []
    for t in thresholds:
        choose = confidence >= t
        n = int(choose.sum())
        wrong = int(np.sum(direction[choose] != labels[choose]))
        close = int(np.sum(labels[choose] == 0))
        result.append({"threshold": t, "selected": n,
                       "coverage": n / len(labels) if len(labels) else 0,
                       "wrongOrClose": wrong, "closeCalledDecisive": close,
                       "precision": (n-wrong)/n if n else None})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--damage-source", type=Path, required=True,
                        help="Full-health damage features exported by export-static-damage.mjs")
    parser.add_argument("--predictions-output", type=Path,
                        help="Write provisional model guesses, never accepted matchup results")
    args = parser.parse_args()
    root = args.campaign / "latest-inference"
    rows = list(records(root / "profile-matchups.jsonl.gz"))
    variants = load(root / "variant-profiles.json")
    definition = load(DEFINITION)
    hashes = sorted({v["profileHash"] for v in variants})
    index = {h: i for i, h in enumerate(hashes)}
    lines = {v["profileHash"]: v["line"] for v in variants}
    line_labels = {line: i for i, line in enumerate(sorted(set(lines.values())))}
    line_ids = np.asarray([line_labels[lines[h]] for h in hashes], dtype=int)
    standards, rank = rank_fingerprints(variants, definition, index)
    standard_indices = [index[next(v["profileHash"] for v in variants if v["key"] == key)]
                        for key in standards]
    stats = stats_matrix(variants, definition, index)
    damage_source = load(args.damage_source)
    assert damage_source["hashes"] == hashes and damage_source["exceptions"] == 0
    damage = np.asarray(damage_source["damage"], dtype=np.float32)
    observed = [r for r in rows if r["evidenceType"] == "observed"]
    unresolved = [r for r in rows if r["outcome"] == "unresolved"]
    train = [r for r in observed if phase_of(r) <= 20]
    calibration = [r for r in observed if 21 <= phase_of(r) <= 22]
    test = [r for r in observed if 23 <= phase_of(r) <= 24]
    graph = make_edges(train, index)
    margin_graph, margin_pairs = make_margin_edges(train, index,
        root / "evidence-ledger.jsonl.gz")
    assert margin_pairs > 4000, margin_pairs
    print(f"loaded {len(train)} train, {len(calibration)} calibration, {len(test)} test, "
          f"{len(unresolved)} unresolved; {margin_pairs} compatible margin pairs", flush=True)
    def featurize(group):
        return features(group, index, rank, stats, line_ids, graph,
                        margin_graph, damage, standard_indices)
    x_train = featurize(train)
    x_cal = featurize(calibration)
    x_test = featurize(test)
    y_train = np.asarray([outcome(r) for r in train])
    y_cal = np.asarray([outcome(r) for r in calibration])
    y_test = np.asarray([outcome(r) for r in test])
    models = {
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=120, max_leaf_nodes=15, learning_rate=0.05, l2_regularization=5,
            random_state=42),
        "extra_trees": ExtraTreesClassifier(n_estimators=160, min_samples_leaf=4,
            max_features=0.6, n_jobs=2, random_state=42)}
    results = {}
    probabilities = {}
    thresholds = sorted(set([round(x, 2) for x in np.arange(.5, 1.001, .05)]
                            + [0.96, 0.97, 0.98, 0.99, 0.995]))
    aliases = {v["profileHash"]: v["key"] for v in reversed(variants)}
    for name, model in models.items():
        print(f"fitting {name}", flush=True)
        model.fit(x_train, y_train)
        classes = list(model.classes_)
        assert classes == [-1, 0, 1], classes
        pc, pt = model.predict_proba(x_cal), model.predict_proba(x_test)
        probabilities[name] = (pc, pt)
        results[name] = {"calibration": assessed(pc, y_cal, thresholds),
                         "test": assessed(pt, y_test, thresholds)}
        decisive = np.where(pt[:, 2] >= pt[:, 0], 1, -1)
        confidence = np.maximum(pt[:, 2], pt[:, 0])
        results[name]["testMistakesAt90Percent"] = [
            {"pairKey": test[i]["pairKey"],
             "units": [aliases[h] for h in test[i]["profiles"]],
             "phase": phase_of(test[i]), "actual": int(y_test[i]),
             "predicted": int(decisive[i]), "confidence": float(confidence[i]),
             "family": "|".join(sorted(lines[h] for h in test[i]["profiles"]))}
            for i in range(len(test)) if confidence[i] >= 0.9 and decisive[i] != y_test[i]]
    pc_h, pt_h = probabilities["hist_gradient_boosting"]
    pc_e, pt_e = probabilities["extra_trees"]
    def agree(left, right):
        result = (left + right) / 2
        same = (left[:, 2] >= left[:, 0]) == (right[:, 2] >= right[:, 0])
        result[~same, 0] = result[~same, 2] = 0
        return result
    ensemble_cal, ensemble_test = agree(pc_h, pc_e), agree(pt_h, pt_e)
    results["ensemble_agreement"] = {
        "calibration": assessed(ensemble_cal, y_cal, thresholds),
        "test": assessed(ensemble_test, y_test, thresholds)}
    print("featurizing unresolved pairs", flush=True)
    x_unresolved = featurize(unresolved)
    for name, model in models.items():
        pu = model.predict_proba(x_unresolved)
        results[name]["unresolvedPredictedCoverageUsingTrainingGraph"] = [
            {"threshold": t, "selected": int((np.maximum(pu[:, 2], pu[:, 0]) >= t).sum())}
            for t in thresholds]
        probabilities[name] = (*probabilities[name], pu)
    ensemble_unresolved = agree(probabilities["hist_gradient_boosting"][2],
                                probabilities["extra_trees"][2])
    results["ensemble_agreement"]["unresolvedPredictedCoverageUsingTrainingGraph"] = [
        {"threshold": t, "selected": int((np.maximum(ensemble_unresolved[:, 2],
                                                       ensemble_unresolved[:, 0]) >= t).sum())}
        for t in thresholds]
    if args.predictions_output:
        args.predictions_output.parent.mkdir(parents=True, exist_ok=True)
        with args.predictions_output.open('wb') as raw, gzip.GzipFile(
                fileobj=raw, mode='wb', mtime=0) as out:
            hgb = probabilities['hist_gradient_boosting'][2]
            trees = probabilities['extra_trees'][2]
            for i, row in enumerate(unresolved):
                out.write((json.dumps({
                    'pairKey': row['pairKey'], 'profiles': row['profiles'],
                    'family': '|'.join(sorted(lines[h] for h in row['profiles'])),
                    'histGradientBoostingProbabilities': {
                        'bWin': float(hgb[i, 0]), 'close': float(hgb[i, 1]),
                        'aWin': float(hgb[i, 2])},
                    'extraTreesProbabilities': {
                        'bWin': float(trees[i, 0]), 'close': float(trees[i, 1]),
                        'aWin': float(trees[i, 2])},
                    'status': 'prediction_only_not_an_observed_or_inferred_result',
                }, sort_keys=True) + '\n').encode())
    # The direct-common-C consensus rule is an independent, interpretable
    # baseline. It abstains if the training graph has contradictory witnesses.
    baseline = {}
    for name, group in (("calibration", calibration), ("test", test)):
        signs = []
        for r in group:
            a, b = [index[h] for h in r["profiles"]]
            common = np.isfinite(graph[a]) & np.isfinite(graph[b]);common[a]=common[b]=False
            d = graph[a, common] - graph[b, common]
            meaningful = d[d != 0]
            signs.append(1 if len(meaningful) >= 2 and np.all(meaningful > 0)
                         else -1 if len(meaningful) >= 2 and np.all(meaningful < 0) else 0)
        actual = np.asarray([outcome(r) for r in group]);estimated = np.asarray(signs)
        chosen = estimated != 0
        baseline[name] = {"selected": int(chosen.sum()), "coverage": float(np.mean(chosen)),
            "wrongOrClose": int(np.sum(estimated[chosen] != actual[chosen])),
            "closeCalledDecisive": int(np.sum(actual[chosen] == 0))}
    report = {"kind": "offline exploratory selective winner prediction; no fights or accepted skips",
        "split": {"trainThroughPhase": 20, "calibrationPhases": [21, 22],
                  "testPhases": [23, 24], "train": len(train),
                  "calibration": len(calibration), "test": len(test),
                  "unresolved": len(unresolved)},
        "profiles": len(index), "benchmarks": standards,
        "compatibleTrainingMarginPairs": margin_pairs,
        "rankingFeatureSource": "original ranking runs; predictive features only, never compatible measurements",
        "commonOpponentWitnessBaseline": baseline, "models": results,
        "sourceHashes": {"inference": sha(root / "profile-matchups.jsonl.gz"),
                         "variants": sha(root / "variant-profiles.json"),
                         "ranking": sha(RANK / "runs.jsonl"),
                         "damageFeatures": sha(args.damage_source)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"split": report["split"], "commonOpponent": baseline,
                      "bestAt90Percent": {name: next((r for r in reversed(v["test"])
                          if r["coverage"] >= 0.5), None) for name, v in results.items()}}, indent=2))


if __name__ == "__main__":
    main()
