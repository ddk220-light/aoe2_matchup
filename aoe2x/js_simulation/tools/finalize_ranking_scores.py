"""Apply the owner's final table groupings without changing scores or the app."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "aoe2x/js_simulation/calibration/reports"
SOURCE = REPORTS / "ranking-readiness-2026-10-29"
OUT = REPORTS / "unit-ranking-scores-final-2026-10-29"
MERGES = {"shock_infantry": "militia", "elephant": "knight", "steppe_lancer": "knight"}
CATEGORIES = [
    ("Infantry", "militia", "Militia line", 91),
    ("Infantry", "spear", "Spear line", 56),
    ("Ranged", "archer", "Archer line", 65),
    ("Ranged", "skirmisher", "Skirmisher line", 57),
    ("Ranged", "cav_archer", "Cavalry archer line", 59),
    ("Ranged", "scorpion", "Scorpion line", 58),
    ("Ranged", "gunpowder", "Gunpowder", 35),
    ("Cavalry", "knight", "Knight line", 70),
    ("Cavalry", "light_cav", "Light cavalry line", 51),
    ("Cavalry", "camel", "Camel line", 13),
]


def read(path):
    return json.loads(path.read_text())


def fingerprint(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def write_json(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + "\n")


def write_csv(name, rows):
    with (OUT / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    previous = read(SOURCE / "rankings-preview.json")
    readiness = read(SOURCE / "readiness.json")
    assert read(SOURCE / "preview-validation.json")["status"] == "passed"
    identity = lambda r: (r["civilization"], r["unitSlug"])
    old_by_key = {identity(r): r for r in previous}
    assert len(previous) == len(old_by_key) == 555
    final, summaries = [], []
    for group, category, label, expected in CATEGORIES:
        members = sorted((r for r in previous if MERGES.get(r["line"], r["line"]) == category),
                         key=lambda r: (-r["score"], r["civilization"], r["unit"]))
        assert len(members) == expected and all(r["group"] == group for r in members)
        for r in members:
            final.append({"group": group, "category": category,
                          "categoryRank": 1 + sum(m["score"] > r["score"] + 1e-10 for m in members),
                          "civilization": r["civilization"], "unit": r["unit"], "unitSlug": r["unitSlug"],
                          "score": r["score"], "groupRank": r["rank"],
                          "sourceLine": r["line"], "sourceLineRank": r["lineRank"],
                          "signedHpMargin": r["signedHpMargin"],
                          "opponentBalancedWinRate": r["opponentBalancedWinRate"],
                          "opponents": r["opponents"], "sampledRuns": r["sampledRuns"],
                          "originalEngineRuns": r["originalEngineRuns"], "correctedEngineRuns": r["correctedEngineRuns"],
                          "engineCoverage": r["engineCoverage"]})
        summaries.append({"group": group, "category": category, "label": label, "variants": len(members),
                          "includedSourceLines": ";".join(sorted({r["line"] for r in members})),
                          "leaderCivilization": members[0]["civilization"], "leaderUnit": members[0]["unit"],
                          "leaderScore": members[0]["score"]})
    assert len(final) == len({identity(r) for r in final}) == 555
    assert {identity(r) for r in final} == set(old_by_key)
    for r in final:
        old = old_by_key[identity(r)]
        for field in ["score", "signedHpMargin", "opponentBalancedWinRate", "opponents", "sampledRuns",
                      "originalEngineRuns", "correctedEngineRuns", "engineCoverage"]:
            assert r[field] == old[field], (identity(r), field)
        if r["sourceLine"] not in MERGES and r["category"] not in MERGES.values():
            assert r["categoryRank"] == old["lineRank"]
    OUT.mkdir(parents=True, exist_ok=True)
    write_json("scores.json", final)
    write_csv("scores.csv", final)
    write_csv("categories.csv", summaries)
    with (OUT / "scores.csv").open(newline="") as handle:
        exported = list(csv.DictReader(handle))
    assert len(exported) == 555
    for row, r in zip(exported, final):
        assert identity(row) == identity(r)
        assert float(row["score"]) == r["score"] and int(row["categoryRank"]) == r["categoryRank"]
    validation = {"status": "passed", "variants": len(final), "categories": len(summaries),
                  "groupCounts": dict(Counter(r["group"] for r in final)),
                  "categoryCounts": dict(Counter(r["category"] for r in final)),
                  "missingVariants": 0, "duplicateVariants": 0, "changedScores": 0,
                  "newSimulations": 0, "unchangedCategoryRanksVerified": True, "csvJsonParity": True}
    write_json("validation.json", validation)
    formula = {**readiness["formula"], "status": "accepted for the finalized score tables; web app implementation is next"}
    manifest = {"schemaVersion": 1, "status": "scores_finalized_web_app_pending",
                "authorization": "Owner accepted the score list and requested shock infantry merged into militia, elephants and steppe lancers merged into knight. Web app changes are a later step.",
                "datasetHash": readiness["datasetHash"], "variants": len(final), "categories": summaries,
                "categoryMerges": MERGES, "formula": formula,
                "sourceEngineVersions": readiness["runEngineCounts"],
                "provenance": "The user-authorized mixture of original and corrected engine results is preserved. Each score retains its source category and engine-run counts; detailed runs are in the consolidated campaign.",
                "scope": "The agreed 555 Imperial land variants; siege/anti-building and naval scores are outside this campaign.",
                "sources": [fingerprint(SOURCE / name) for name in ["rankings-preview.json", "readiness.json", "preview-validation.json"]],
                "generator": fingerprint(Path(__file__).resolve()),
                "outputs": [fingerprint(OUT / name) for name in ["scores.json", "scores.csv", "categories.csv", "validation.json"]]}
    write_json("manifest.json", manifest)
    top = ["# Top 10 by finalized category", "",
           "Scores are unchanged from the accepted preview. Shock infantry is included in Militia; elephants and steppe lancers are included in Knight. Exact ties share a rank and all ties at the top-10 cutoff are included. Scores are shown to one decimal; ranks use unrounded values.", ""]
    for category in summaries:
        top.extend([f"## {category['group']} · {category['label']}", "",
                    "| Rank | Civilization | Unit | Score |", "|---:|---|---|---:|"])
        ties = defaultdict(list)
        for row in final:
            if row["category"] == category["category"] and row["categoryRank"] <= 10:
                ties[(row["categoryRank"], row["unit"], row["score"])].append(row["civilization"])
        for (position, unit, score), civs in ties.items():
            top.append(f"| {position}{'=' if len(civs) > 1 else ''} | {', '.join(civs)} | {unit} | {score:.1f} |")
        top.append("")
    (OUT / "top10-by-category.md").write_text("\n".join(top))
    report = ["# Finalized unit-ranking score tables", "",
              "**555 civilization/unit variants, 10 categories, zero missing or duplicate entries.** All scores are unchanged from the accepted preview. Only category membership and category ranks changed. Web app implementation remains the next step.", "",
              "- [Complete score list — CSV](scores.csv)", "- [Complete score list — JSON](scores.json)",
              "- [Top 10 in every category](top10-by-category.md)", "- [Category counts and leaders](categories.csv)",
              "- [Validation](validation.json)", "- [Methodology and provenance](manifest.json)", "",
              "## Final categories", "", "| Group | Category | Variants |", "|---|---|---:|"]
    report.extend(f"| {r['group']} | {r['label']} | {r['variants']} |" for r in summaries)
    report.extend(["", "Militia includes the former Shock Infantry entries. Knight includes the former Elephant and Steppe Lancer entries. Original categories are retained in `sourceLine` for traceability and the later app migration.", "",
                   "## Scoring", "", "A win contributes remaining own HP percentage; a loss contributes negative remaining opponent HP percentage; a draw contributes zero. Average the required seeds within each opponent matchup, then give each agreed opponent equal weight. Display score = 50 + mean signed HP margin / 2. There is no additional speed, range or cost multiplier. Cost and population balance is already represented by the simulated army counts. Group opponent pools remain unchanged.", "",
                   "The consolidated campaign's mixed engine provenance is preserved as explicitly requested. Finalization means the score list and category decisions are complete; the earlier statistical and simulation limitations still apply. No further simulations, engine changes or web app changes were performed.", "",
                   "Rebuild these tables: `python aoe2x/js_simulation/tools/finalize_ranking_scores.py`", ""])
    (OUT / "README.md").write_text("\n".join(report))
    print(json.dumps(validation))


if __name__ == "__main__":
    main()
