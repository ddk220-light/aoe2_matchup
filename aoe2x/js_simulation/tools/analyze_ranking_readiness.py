"""Preview rankings and audit web integration; does not modify serving data."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from statistics import mean, median
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from apps.website.services.rankings import get_unit_line_data
from aoe2x.batch.patches_db import get_current_build

DATA = ROOT / "aoe2x/js_simulation/calibration/campaigns/unit-rankings-consolidated-2026-10-29"
OUT = ROOT / "aoe2x/js_simulation/calibration/reports/ranking-readiness-2026-10-29"
GROUPS = ["Infantry", "Ranged", "Cavalry"]


def read(path):
    return json.loads(path.read_text())


def fingerprint(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n")


def write_csv(name, rows):
    with (OUT / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def signed_margin(row):
    return row["unitHpPercent"] if row["outcome"] == "win" else -row["opponentHpPercent"] if row["outcome"] == "loss" else 0.0


def rank(values, value):
    # Equal numeric scores share their competition rank; display rounding is later.
    return 1 + sum(v > value + 1e-10 for v in values)


def main():
    manifest = read(DATA / "manifest.json")
    for entry in manifest["outputs"]:
        assert fingerprint(DATA / entry["path"])["sha256"] == entry["sha256"]
    summary = read(DATA / "summary.json")
    records = [json.loads(line) for line in (DATA / "runs.jsonl").read_text().splitlines()]
    assert len(records) == 7600 and len({(r["matchupId"], r["seed"]) for r in records}) == 7600
    assert all(r["outcome"] in {"win", "loss", "draw"} for r in records)
    samples = defaultdict(list)
    for row in records:
        samples[row["matchupId"]].append(row)
    units = {(u["civilization"], u["slug"]): {**u, "opponents": {}} for u in manifest["roster"]["units"]}
    breakdown = []
    for row in summary:
        runs = samples[row["simulationSourceMatchupId"]]
        values = [signed_margin(r) for r in runs]
        raw = mean(values)
        assert math.isclose(raw, row["meanUnitHpPercentDecided"] - row["meanOpponentHpPercentDecided"], abs_tol=1e-9)
        detail = {"civilization": row["civilization"], "unitSlug": row["slug"], "unit": row["unit"],
                  "group": row["group"], "opponentKey": row["opponentKey"], "opponent": row["opponent"],
                  "signedHpMargin": raw, "score": 50 + raw / 2, "wins": row["wins"], "losses": row["losses"],
                  "draws": row["draws"], "runs": len(runs), "unitCount": row["unitCount"],
                  "opponentCount": row["opponentCount"], "simulationSourceMatchupId": row["simulationSourceMatchupId"],
                  "originalEngineRuns": row["originalEngineRuns"], "correctedEngineRuns": row["correctedEngineRuns"],
                  "minRunMargin": min(values), "maxRunMargin": max(values)}
        units[(row["civilization"], row["slug"])]["opponents"][row["opponentKey"]] = detail
        breakdown.append(detail)
    for u in units.values():
        opponents = list(u["opponents"].values())
        u["signedHpMargin"] = mean(r["signedHpMargin"] for r in opponents)
        u["score"] = 50 + u["signedHpMargin"] / 2
        u["opponentBalancedWinRate"] = mean(100 * r["wins"] / r["runs"] for r in opponents)
        u["sampledRuns"] = sum(r["runs"] for r in opponents)
        u["originalEngineRuns"] = sum(r["originalEngineRuns"] for r in opponents)
        u["correctedEngineRuns"] = sum(r["correctedEngineRuns"] for r in opponents)
        u["engineCoverage"] = "original" if u["correctedEngineRuns"] == 0 else "corrected" if u["originalEngineRuns"] == 0 else "mixed"
    rankings = []
    sensitivity = {}
    for group in GROUPS:
        members = sorted((u for u in units.values() if u["group"] == group),
                         key=lambda u: (-u["score"], u["civilization"], u["name"]))
        scores = [u["score"] for u in members]
        excluded_opponents = sorted(members[0]["opponents"])
        omitted_scores = {key: [mean(r["signedHpMargin"] for k, r in u["opponents"].items() if k != key)
                                for u in members] for key in excluded_opponents}
        for i, u in enumerate(members):
            group_rank = rank(scores, u["score"])
            line_scores = [v["score"] for v in members if v["line"] == u["line"]]
            loo_ranks = [rank(values, values[i]) for values in omitted_scores.values()]
            rankings.append({"group": group, "rank": group_rank, "civilization": u["civilization"],
                             "unit": u["name"], "unitSlug": u["slug"], "line": u["line"],
                             "lineRank": rank(line_scores, u["score"]), "score": u["score"],
                             "signedHpMargin": u["signedHpMargin"], "opponentBalancedWinRate": u["opponentBalancedWinRate"],
                             "opponents": len(u["opponents"]), "sampledRuns": u["sampledRuns"],
                             "originalEngineRuns": u["originalEngineRuns"], "correctedEngineRuns": u["correctedEngineRuns"],
                             "engineCoverage": u["engineCoverage"], "bestRankOmittingOneOpponent": min(loo_ranks),
                             "worstRankOmittingOneOpponent": max(loo_ranks)})
        sensitivity[group] = {"opponents": excluded_opponents,
                              "leadersOmittingOneOpponent": {key: [f"{members[i]['civilization']} {members[i]['name']}"
                                                                     for i, value in enumerate(values) if rank(values, value) == 1]
                                                               for key, values in omitted_scores.items()}}

    def db(filename):
        conn = sqlite3.connect(f"file:{ROOT / 'data/golden' / filename}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    build = get_current_build(patches_db_path=str(ROOT / "data/golden/patches.db"))
    app_audit = {}
    for group, line in zip(GROUPS, ["infantry", "archery", "stable"]):
        data = get_unit_line_data(line, get_ref_db=lambda: db("aoe2_reference.db"),
                                 get_rankings_derived_db=lambda: db("derived_data_v3.db"), current_build=lambda: build)
        counts = Counter((r["civ_name"], r["unit_slug"]) for r in data["imperial"])
        actual = set(counts)
        expected = {(u["civilization"], u["slug"]) for u in units.values() if u["group"] == group}
        app_audit[group] = {"appRows": len(data["imperial"]), "appUniqueRows": len(actual), "datasetVariants": len(expected),
                            "missingInApp": sorted(expected - actual), "appOutsideDataset": sorted(actual - expected),
                            "duplicates": [{"civilization": c, "slug": s, "count": n} for (c, s), n in counts.items() if n > 1]}

    original = read(ROOT / manifest["engineVersions"]["original"]["manifestPath"])
    old_dir = ROOT / manifest["engineVersions"]["original"]["manifestPath"]
    old_records = {(r["matchupId"], r["seed"]): r for file in (old_dir.parent / "runs").glob("*.jsonl")
                   for line in file.read_text().splitlines() for r in [json.loads(line)]}
    paired = [(old_records[(r["matchupId"], r["seed"])], r) for r in records
              if r["selectionProvenance"]["engineVersion"] == "corrected"
              and (r["matchupId"], r["seed"]) in old_records
              and old_records[(r["matchupId"], r["seed"])]["outcome"] in {"win", "loss", "draw"}]
    engine_comparison = {"comparableSuccessfulRuns": len(paired),
                         "changedWinners": sum(a["outcome"] != b["outcome"] for a, b in paired),
                         "medianAbsoluteMarginChange": median(abs(signed_margin(a) - signed_margin(b)) for a, b in paired),
                         "maxAbsoluteMarginChange": max(abs(signed_margin(a) - signed_margin(b)) for a, b in paired),
                         "caveat": "Selected overlap, concentrated in early infantry phases; not a random sample of all units."}
    mirrors = [r for r in breakdown if r["unit"] == r["opponent"]]
    price_examples = []
    for civ, name, opponent in [("Persians", "Elite War Elephant", "halberdier"),
                                ("Teutons", "Elite Teutonic Knight", "arbalester"),
                                ("Khmer", "Elite Ballista Elephant", "cavalier")]:
        unit = next(u for u in units.values() if u["civilization"] == civ and u["name"] == name)
        matchup = next(r for r in original["matchups"] if r["civilization"] == civ and r["slug"] == unit["slug"] and r["opponent"] == opponent)
        price_examples.append({"unit": f"{civ} {name}", "opponent": opponent, "counts": matchup["counts"],
                               "weightedUnitCosts": matchup["weightedCosts"],
                               "weightedArmyCosts": [n * cost for n, cost in zip(matchup["counts"], matchup["weightedCosts"])]})
    result = {"status": "preview_complete_not_published_to_web_app", "dataComplete": True, "directImportReady": False,
              "datasetHash": manifest["datasetHash"], "variants": len(rankings), "groups": manifest["roster"]["counts"],
              "currentAppBuild": build, "currentPublishedMetadata": read(ROOT / "data/golden/derived_data_v3.metadata.json"),
              "formula": {"status": "provisional, for this analysis; not an approved production formula",
                          "runMargin": "win: own remaining HP percent; loss: negative opponent remaining HP percent; draw: zero",
                          "aggregation": "average seeds inside each opponent matchup, then equal-weight the agreed opponents",
                          "displayScore": "50 + mean signed HP margin / 2 (fixed 0..100 scale; 50 is neutral)",
                          "mobilityBonus": None, "costAdjustment": "already incorporated in approved army counts; no second multiplier",
                          "ties": "competition ranks using unrounded scores; exact ties share rank",
                          "comparison": "rank within each group; groups have different opponent pools"},
              "runEngineCounts": dict(Counter(r["selectionProvenance"]["engineVersion"] for r in records)),
              "unitEngineCoverage": dict(Counter(r["engineCoverage"] for r in rankings)),
              "appCoverageAudit": app_audit, "oldVsCorrectedEvidence": engine_comparison,
              "oldFormulaMissingOpponents": {"Infantry": ["halberdier", "skirmisher"],
                                             "Ranged": ["paladin"], "Cavalry": ["skirmisher", "hussar"]},
              "mirrorMatches": mirrors, "costBalanceExamples": price_examples, "opponentSensitivity": sensitivity,
              "remainingIntegration": ["Choose the final scoring weights and whether mobility needs a separate score.",
                                       "Convert consolidated results to the serving battle_scores schema and preserve engine provenance.",
                                       "Replace obsolete five-seed/six-opponent/1:1:1 validation with this campaign's actual policy.",
                                       "Synchronize reference data and line registry: 44 missing variants, 11 replaced entries, one Tarkan duplicate.",
                                       "Update opponent breakdowns, methodology and build/source metadata; keep siege and naval separate.",
                                       "Check API and rendered ranking rows before publication."],
              "newSimulationsPerformed": 0,
              "sources": [fingerprint(path) for path in [DATA / "manifest.json", DATA / "runs.jsonl", DATA / "summary.json",
                          ROOT / "apps/website/services/rankings.py", ROOT / "aoe2x/rank/build_v3_serving_db.py",
                          ROOT / "data/golden/aoe2_reference.db", ROOT / "data/golden/aoe2_reference_simulation.db",
                          ROOT / "data/golden/derived_data_v3.db", ROOT / "data/golden/derived_data_v3.metadata.json"]]}
    OUT.mkdir(parents=True, exist_ok=True)
    write_json("readiness.json", result)
    write_json("rankings-preview.json", rankings)
    write_csv("rankings-preview.csv", rankings)
    write_csv("opponent-breakdown.csv", breakdown)
    leaders = [r for r in rankings if r["lineRank"] == 1]
    write_csv("line-leaders.csv", leaders)
    report = ["# Ranking readiness and provisional standings", "",
              "The completed data supports a ranking preview. It cannot be imported directly into the current web app. No simulations, serving-data edits or deployment were performed for this analysis.", "",
              "The preview gives each agreed opponent equal weight. For each seed, wins receive remaining own HP percentage, losses receive negative remaining opponent HP percentage, and draws receive zero. Average seeds within each opponent, then opponents within each unit. Display score = 50 + half that signed average. Scores are comparable within the same group; 50 is neutral. This is a proposal, not the existing app formula or a finalized scoring decision.", "",
              "- [All 555 ranked variants](rankings-preview.csv)", "- [Per-opponent breakdown](opponent-breakdown.csv)",
              "- [Unit-line leaders](line-leaders.csv)", "- [Readiness evidence, provenance and sensitivity](readiness.json)", "",
              "## Integration gaps", "", *[f"- {item}" for item in result["remainingIntegration"]], "",
              "The current serving snapshot is dated September 4 and tagged build 177723. Its explanation assumes five seeds, six common opponents, 1:1:1 resource weights, normalized role scores, and additional speed/range multipliers. This campaign uses three or ten seeds, different pools per group and weights 1:0.9:1.1. The old infantry composite needs Halberdier and Skirmisher results absent from the approved infantry pool; the old ranged composite needs Paladin results absent from the ranged pool. These missing matchups must not be filled with zero or silently replaced by different opponents. Cavalry has the inputs for its existing final composite, but not the old full breakdown; changing only cavalry's scoring would make the category methods inconsistent.", "",
              "## Interpretation", "",
              "This is a standing-combat benchmark with scripted kiting disabled. Mobility, retreat, raiding, conversion vulnerability and real-game micro are not captured as an overall strategic value. The approved count formula balances population against cost rather than equalizing army resource totals: 13 Persian War Elephants face 27 Spanish Halberdiers, with weighted army costs 3,425.5 versus 1,552.5. Heavy-unit leaders are therefore partly an intended consequence of the allocation policy.", "",
              f"The selected dataset contains {result['runEngineCounts']['original']} original-engine runs and {result['runEngineCounts']['corrected']} corrected-engine runs. Of {len(paired)} directly comparable successful runs, {engine_comparison['changedWinners']} changed winner; median absolute margin change is {engine_comparison['medianAbsoluteMarginChange']:.2f} percentage points. This selected sample is not representative of the full roster. Mixing was explicitly authorized; close rankings should be treated as provisional.", "",
              "Identical-army checks also show sample/side variation: Spanish Champion has a -10.37 signed margin against itself and Spanish Paladin +10.14. Three consistent initial winners do not establish a stable true win probability. This is a reason to avoid claiming tiny rank differences are decisive, not a request to rerun the campaign.", ""]
    for group in GROUPS:
        report.extend([f"## {group}", "", "| Rank | Civilization | Unit | Score |", "|---:|---|---|---:|"])
        report.extend(f"| {r['rank']} | {r['civilization']} | {r['unit']} | {r['score']:.1f} |" for r in rankings if r["group"] == group and r["rank"] <= 20)
        report.append("")
    (OUT / "README.md").write_text("\n".join(report))
    print(json.dumps({"output": str(OUT), "variants": len(rankings), "appCoverageAudit": app_audit,
                      "engineComparison": engine_comparison, "sensitivity": sensitivity,
                      "lineLeaders": [{k: r[k] for k in ["group", "line", "civilization", "unit", "score"]} for r in leaders]}))


if __name__ == "__main__":
    main()
