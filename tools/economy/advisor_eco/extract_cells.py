"""Per-cell table: seed HP of the battle winner + both armies' 60-s investment.

For every advisor cell (a, b) with simulated evidence (``evidence_type`` =
``observed``) it writes one row to ``$ADVISOR_ECO_OUT/cells.csv.gz``:
per-seed winners, the cell winner's remaining-HP fraction (mean / mean over the
seeds it won / min / max), both sides' army-economics headline in weighted
villager-minutes for the cell's counts, both full research packages, and the
proposed label. ``inferred`` and ``identity`` cells are counted, not labelled.

Seed sources inside an evidence blob (orientation: owner 2 = context.profiles[0],
owner 3 = context.profiles[1]):
  forecastValidation.seedResults / mismatchValidation.seedResults
      -> winnerOwner + winnerHpFraction (= winner remaining HP / its starting HP)
  recoveryValidation.measuredRecords -> unit/opponent starting + remaining HP
  sourceRunIds (first-pass campaign, 9,315 contexts) -> run records read from git
      (``--runs-ref``, branch simulations/civ-matchups-campaign-2026-10-31), which
      carry unit/opponent starting + remaining HP.

Usage: python tools/economy/advisor_eco/extract_cells.py [--jobs 4] [--runs-ref REF]
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import multiprocessing
import statistics
import subprocess
import sys
import time

from common import (CELLS_CSV, ECO_SAVING, HP_LIMIT, OUT, REPO, advisor_units, connect, economics_map,
                    evidence_decoder)

RUNS_REF = "207c31283c70db1f6ebea4ae93535c98dfe86777"  # tip of origin/simulations/civ-matchups-campaign-2026-10-31

_DATA = None


def _init():
    global _DATA
    from aoe2x.economy.matchup import RuntimeData
    _DATA = RuntimeData()


def _evaluate(job):
    from aoe2x.economy.matchup import evaluate_matchup
    left, right = job
    try:
        result = evaluate_matchup(_DATA, left, right)
    except Exception as error:  # noqa: BLE001 - reported per cell
        return job, None, repr(error)
    teams = result["teams"]
    out = []
    for team in teams:
        labor = team["investment"]["labor"]
        out.append({"vm": None if labor is None else labor["villagerMinutes"],
                    "status": team["investment"]["status"],
                    "full": team["researchSummary"]["full"]["villagerMinutes"],
                    "common": team["researchSummary"]["common"]["villagerMinutes"],
                    "army": team["investment"]["standaloneLabor"]["army"],
                    "buildings": team["investment"]["standaloneLabor"]["buildings"]})
    return job, out, None


def run_lines(ref, references):
    """{"path:line": record} for the referenced first-pass campaign runs."""
    by_file = collections.defaultdict(set)
    for reference in references:
        path, line = reference.rsplit(":", 1)
        by_file[path].add(int(line))
    records = {}
    for path, lines in sorted(by_file.items()):
        shown = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{path}"], capture_output=True, text=True)
        if shown.returncode:
            continue  # e.g. bare "runs.jsonl:<n>" references (294, ~98 contexts): file not in git history
        text = shown.stdout.split("\n")
        for line in lines:
            records[f"{path}:{line}"] = json.loads(text[line - 1])
    return records


def seeds_of(evidence, runs):
    """List of per-seed dicts {seed, winner (0/1/None), frac: [f0, f1] or None, winnerFrac, source}.

    Index 0/1 = context.profiles order. ``frac`` holds both sides' remaining HP
    fractions when the record has them; otherwise only ``winnerFrac`` is known
    (the loser of a seed is eliminated, see check in main)."""
    profiles = evidence["context"]["profiles"]
    seeds = []
    for block in ("forecastValidation", "mismatchValidation"):
        for result in evidence.get(block, {}).get("seedResults", []) or []:
            owner = result.get("winnerOwner")
            seeds.append({"seed": result.get("seed"), "winner": {2: 0, 3: 1}.get(owner), "frac": None,
                          "winnerFrac": result.get("winnerHpFraction"), "source": block})
    for measured in evidence.get("recoveryValidation", {}).get("measuredRecords", []) or []:
        record = measured["record"]
        seeds.append(_record_seed(record, profiles, "recoveryValidation"))
    if not seeds:
        for reference in evidence.get("sourceRunIds", []) or []:
            if reference in runs:
                seeds.append(_record_seed(runs[reference], profiles, "campaignRun", evidence["context"]["counts"]))
    return seeds


def _record_seed(record, profiles, source, counts=None):
    if "profileHashes" in record:
        unit_side = profiles.index(record["profileHashes"][0])
    else:  # 00-pilot records (40) carry no hashes: orient by army counts, else context order
        unit_side = 1 if counts and [record["opponentCount"], record["unitCount"]] == counts != counts[::-1] else 0
    own = record["unitRemainingHp"] / record["unitStartingHp"]
    opp = record["opponentRemainingHp"] / record["opponentStartingHp"]
    frac = [own, opp] if unit_side == 0 else [opp, own]
    start = [record["unitStartingHp"], record["opponentStartingHp"]]
    if unit_side == 1:
        start.reverse()
    winner = {2: 0, 3: 1}.get(record.get("winnerOwner"))
    if winner is not None and unit_side == 1:
        winner = 1 - winner  # winnerOwner 2 is the record's unit side
    return {"seed": record.get("seed"), "winner": winner, "frac": frac, "start": start,
            "winnerFrac": None if winner is None else frac[winner], "source": source}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--runs-ref", default=RUNS_REF)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.time()
    db = connect()
    decode = evidence_decoder(db)
    units = advisor_units(db)

    from aoe2x.economy.matchup import RuntimeData
    data = RuntimeData()
    mapping, problems = economics_map(data, units)

    cells = db.execute("SELECT a, b, outcome, evidence_type, count_a, count_b, evidence_id FROM cells ORDER BY a, b").fetchall()
    counts = collections.Counter(c[3] for c in cells)
    needed = sorted({c[6] for c in cells if c[3] == "observed"})
    evidence = {}
    for eid in needed:
        evidence[eid] = decode(db.execute("SELECT data FROM evidence WHERE id=?", (eid,)).fetchone()[0])
    references = {r for e in evidence.values() if not any(k in e for k in ("forecastValidation", "mismatchValidation", "recoveryValidation"))
                  for r in e.get("sourceRunIds", [])}
    runs = run_lines(args.runs_ref, references)
    print(f"evidence {len(evidence)}, campaign run records {len(runs)} ({time.time() - started:.0f}s)", file=sys.stderr)

    checks = collections.Counter()
    # Orientation and HP-ratio checks on records that carry both sides.
    for e in evidence.values():
        for block in ("forecastValidation", "mismatchValidation"):
            replay = (e.get(block, {}).get("exactReplay") or {}).get("result")
            if not replay:
                continue
            side = {2: replay["side2"], 3: replay["side3"]}
            checks["exactReplay results"] += 1
            if replay["winnerOwner"] in (2, 3):
                w = replay["winnerOwner"]
                if abs(replay["winnerHp"] / replay["startingHpByOwner"][str(w)] -
                       next((s["winnerHpFraction"] for s in e[block]["seedResults"] if s["seed"] == replay["seed"]), -1)) < 1e-9:
                    checks["exactReplay winnerHp/startingHp == seedResults fraction"] += 1
                loser = 5 - w
                if replay["remainingByOwner"][str(loser)]["hp"] == 0:
                    checks["exactReplay loser eliminated"] += 1
            counts_ctx = e["context"]["counts"]
            if [side[2]["count"], side[3]["count"]] == counts_ctx:
                checks["exactReplay side2/side3 counts == context.counts order"] += 1
    for record in runs.values():
        checks["campaign run records"] += 1
        if record["winnerOwner"] in (2, 3):
            loser_hp = record["opponentRemainingHp"] if record["winnerOwner"] == 2 else record["unitRemainingHp"]
            checks["campaign runs loser eliminated"] += loser_hp == 0

    profile_of = {uid: u["profileHash"] for uid, u in units.items()}
    rows, jobs = [], set()
    for a, b, outcome, etype, ca, cb, eid in cells:
        if etype != "observed":
            continue
        e = evidence[eid]
        profiles = e["context"]["profiles"]
        ia, ib = profiles.index(profile_of[a]), profiles.index(profile_of[b])
        if [e["context"]["counts"][ia], e["context"]["counts"][ib]] != [ca, cb]:
            checks["counts mismatch cell vs context"] += 1
        seeds = seeds_of(e, runs)
        won_a = sum(1 for s in seeds if s["winner"] == ia)
        won_b = sum(1 for s in seeds if s["winner"] == ib)
        draws = len(seeds) - won_a - won_b
        majority = "a_win" if won_a > won_b else "b_win" if won_b > won_a else "tie" if seeds else "no_seed_data"
        checks[f"outcome {outcome} / seed majority {majority}"] += 1
        winner = {"a_win": ia, "b_win": ib}.get(outcome)
        if winner is None:  # close_uncertain: report the majority side for information only
            winner = ia if won_a >= won_b else ib
        winner_fracs = [(s["winnerFrac"] if s["winner"] == winner else 0.0) for s in seeds]
        won_fracs = [s["winnerFrac"] for s in seeds if s["winner"] == winner]
        jobs.add(((*mapping[a], ca), (*mapping[b], cb)))
        rows.append({"a": a, "b": b, "civ_a": units[a]["civilization"], "civ_b": units[b]["civilization"],
                     "name_a": units[a]["name"], "name_b": units[b]["name"], "outcome": outcome,
                     "count_a": ca, "count_b": cb, "evidence_id": eid, "seeds": len(seeds),
                     "seeds_won_a": won_a, "seeds_won_b": won_b, "draws": draws,
                     "seed_sources": "+".join(sorted({s["source"] for s in seeds})),
                     "hp_avg": statistics.fmean(winner_fracs) if seeds else None,
                     "hp_avg_won": statistics.fmean(won_fracs) if won_fracs else None,
                     "hp_min": min(winner_fracs) if seeds else None, "hp_max": max(winner_fracs) if seeds else None,
                     "wcost_a": e["context"]["weightedCosts"][ia], "wcost_b": e["context"]["weightedCosts"][ib],
                     "gold_a": int(units[a]["costs"]["gold"] > 0), "gold_b": int(units[b]["costs"]["gold"] > 0),
                     "group_a": units[a]["group"], "group_b": units[b]["group"],
                     "_job": ((*mapping[a], ca), (*mapping[b], cb))})

    print(f"cells {len(rows)}, economics jobs {len(jobs)} ({time.time() - started:.0f}s)", file=sys.stderr)
    with multiprocessing.Pool(args.jobs, initializer=_init) as pool:
        results = {}
        for job, out, error in pool.imap_unordered(_evaluate, sorted(jobs), chunksize=200):
            results[job] = (out, error)
    print(f"economics done ({time.time() - started:.0f}s)", file=sys.stderr)

    labels = collections.Counter()
    fields = ["a", "b", "civ_a", "civ_b", "name_a", "name_b", "outcome", "count_a", "count_b", "evidence_id",
              "seeds", "seeds_won_a", "seeds_won_b", "draws", "seed_sources", "hp_avg", "hp_avg_won", "hp_min", "hp_max",
              "wcost_a", "wcost_b", "gold_a", "gold_b", "group_a", "group_b", "vm_a", "vm_b", "army_vm_a", "army_vm_b",
              "common_vm_a", "common_vm_b", "full_vm_a", "full_vm_b", "eco_status", "saving", "label"]
    with gzip.open(CELLS_CSV, "wt", newline="", compresslevel=6) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out, error = results[row.pop("_job")]
            if out is None:
                row["eco_status"] = "error:" + error
            else:
                ta, tb = out
                row.update(vm_a=ta["vm"], vm_b=tb["vm"], full_vm_a=ta["full"], full_vm_b=tb["full"],
                           army_vm_a=(ta["army"] or {}).get("villagerMinutes"), army_vm_b=(tb["army"] or {}).get("villagerMinutes"),
                           common_vm_a=ta["common"], common_vm_b=tb["common"],
                           eco_status="available" if ta["vm"] is not None and tb["vm"] is not None else f"{ta['status']}/{tb['status']}")
            label = ""
            if row["seeds"] and row["outcome"] in ("a_win", "b_win") and row.get("vm_a") is not None and row.get("vm_b") is not None:
                winner_vm, loser_vm = (row["vm_a"], row["vm_b"]) if row["outcome"] == "a_win" else (row["vm_b"], row["vm_a"])
                row["saving"] = 1 - loser_vm / winner_vm
                if row["hp_avg"] < HP_LIMIT and row["saving"] >= ECO_SAVING:
                    label = "narrow_loss_cheaper_rebuild"
            row["label"] = label
            labels[label or "none"] += 1
            for key in ("hp_avg", "hp_avg_won", "hp_min", "hp_max", "vm_a", "vm_b", "full_vm_a", "full_vm_b",
                        "army_vm_a", "army_vm_b", "common_vm_a", "common_vm_b", "saving"):
                if isinstance(row.get(key), float):
                    row[key] = f"{row[key]:.6f}"
            writer.writerow(row)

    summary = {"cellsByEvidenceType": dict(counts), "observedCells": len(rows),
               "observedContexts": len(evidence), "economicsJobs": len(jobs),
               "mappingProblems": problems, "mappedUnits": len(mapping), "advisorUnits": len(units),
               "checks": dict(sorted(checks.items())), "labels": dict(labels),
               "economicsErrors": sum(1 for v in results.values() if v[0] is None),
               "runsRef": args.runs_ref, "seconds": round(time.time() - started)}
    (OUT / "extract_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
