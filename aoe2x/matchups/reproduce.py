"""``reproduce-2026``: re-run a deterministic sample of 2026 contexts and compare exactly.

``prepare`` samples reviewed contexts from the two 2026 campaigns whose
reviews are final in the published table (RB mismatch snapshot
``review-ready-2026-11-07`` and forecast snapshot ``070``; contexts later
replaced by the recovery campaign are left out), stratified by the sampling
rule 2026 used, seed count, scenario family, outcome and (one-three-ten)
decision reason, plus ten-seed sets that contain a draw. Two runs are
written, one per rule:

* ``three-then-ten``: mismatch ``fresh_seed_set`` reviews and forecast reviews
  made before sampling amendment v2 (both ran seeds 0-2, then 3-9 on mixed winners);
* ``one-three-ten``: forecast reviews under ``distinct-seeds-no-replay-v3``
  (and v2, same decision rule) with the 2026 forecast outcomes of each context
  as its priors file; the three ``legacyInProgressJobs`` are excluded.

Every expected seed is the archived ``runs.jsonl`` line on RB (checked to be
byte-for-byte the review's ``measuredRecords`` entry). Sampled contexts must
appear in the run's inventory with the archived ``contextHash`` (published
orientation table), so nothing is mapped or reversed.

``compare`` checks every seed's outcome, winner, ticks, starting/remaining HP,
survivors, ``finalStateHash`` and ``eventLogHash``, the seed set, the
classification and (one-three-ten) the sampling decision.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from aoe2x.matchups import config as C
from aoe2x.matchups.canonical import digest, sha256_bytes
from aoe2x.matchups.paths import CONFIGS_DIR

SAMPLER = "reproduce-2026-strata-v1"
COMPARED = ("outcome", "winnerOwner", "ticks", "unitStartingHp", "opponentStartingHp", "unitRemainingHp",
            "opponentRemainingHp", "unitSurvivors", "opponentSurvivors", "finalStateHash", "eventLogHash")
V2, V3 = "0760c8fd", "4404ca50"
# Keep the sample affordable: total archived wall seconds per context by seed count.
MAX_WALL = {1: 20.0, 3: 45.0, 10: 150.0}
GROUPS = ("three-then-ten", "one-three-ten")


def _rank(job_id: str) -> str:
    return hashlib.sha256(f"{SAMPLER}|{job_id}".encode()).hexdigest()


def _gz(rows) -> bytes:
    return gzip.compress("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows).encode(),
                         compresslevel=9, mtime=0)


def _load(rb):
    from aoe2x.matchups.rbsource import FORECAST, MISMATCH, RECOVERY
    snaps = {"mismatch": rb.jsonl(f"{MISMATCH}/correction-snapshots/review-ready-2026-11-07/reviewed-contexts.jsonl.gz"),
             "forecast": rb.jsonl(f"{FORECAST}/correction-snapshots/070/reviewed-contexts.jsonl.gz")}
    recovered = {r["jobId"] for r in rb.json(f"{RECOVERY}/correction-snapshots/002/matchup-reviews.json")}
    legacy = set(rb.json(f"{FORECAST}/sampling-policy-v3.json")["legacyInProgressJobs"])
    runs = {}
    for name, base in (("mismatch", MISMATCH), ("forecast", FORECAST)):
        for line in rb.show(f"{base}/runs.jsonl").decode().splitlines():
            if line.strip():
                row = json.loads(line)
                runs[(row["matchupId"], row["seed"], row.get("purpose"))] = line
    return snaps, recovered, legacy, runs


def candidates(snaps, recovered, legacy) -> dict[str, list]:
    forecast_pairs = {r["pairKey"] for r in snaps["forecast"]}
    out = {g: [] for g in GROUPS}
    for name, rows in snaps.items():
        for r in rows:
            if r["outcome"] == "equivalent" or r["validationMode"] == "exact_replay_of_measured_seed_set":
                continue
            if name == "mismatch" and r["pairKey"] in forecast_pairs:
                continue  # superseded by a later layer
            if r["jobId"] in recovered or r["jobId"] in legacy:
                continue
            policy = (r.get("samplingPolicyHash") or "")[:8]
            group = "one-three-ten" if policy in (V2, V3) else "three-then-ten"
            seeds = r["seedCount"]
            wall = sum(m["wallSeconds"] for m in r["measuredRecords"])
            if wall > MAX_WALL[seeds]:
                continue
            draw = any(m["outcome"] == "draw" for m in r["measuredRecords"])
            reason = (r.get("samplingDecision") or {}).get("reason", "") if group == "one-three-ten" and seeds > 1 else ""
            stratum = f"{seeds}|{r['context']['family']}|{r['outcome']}|{reason}"
            out[group].append((stratum, draw, name, r))
    return out


def prepare(rb, directory: Path, per_stratum: int = 3) -> dict:
    directory = Path(directory).resolve()
    snaps, recovered, legacy, runs = _load(rb)
    picked = {}
    for group, rows in candidates(snaps, recovered, legacy).items():
        strata = defaultdict(list)
        for stratum, draw, campaign, r in rows:
            strata[stratum].append((campaign, r))
            if draw:
                strata[f"draw|{stratum}"].append((campaign, r))
        chosen, used = [], set()
        for name in sorted(strata):
            n = 0
            for campaign, r in sorted(strata[name], key=lambda x: _rank(x[1]["jobId"])):
                if n == per_stratum:
                    break
                if r["pairKey"] in used:
                    continue
                used.add(r["pairKey"])
                chosen.append((name, campaign, r))
                n += 1
        picked[group] = chosen
    base = json.loads((CONFIGS_DIR / "full-2026-reproduction.json").read_text())
    single = json.loads((CONFIGS_DIR / "single-civ-example.json").read_text())
    report = {"sampler": SAMPLER, "perStratum": per_stratum, "maxWallSecondsBySeedCount": MAX_WALL, "groups": {}}
    expected = []
    for group, chosen in picked.items():
        gdir = directory / group
        gdir.mkdir(parents=True, exist_ok=True)
        keys = sorted(r["pairKey"] for _, _, r in chosen)
        ctx_bytes = (json.dumps(keys, indent=0) + "\n").encode()
        (gdir / "contexts.json").write_bytes(ctx_bytes)
        cfg = copy.deepcopy(base)
        cfg["runId"] = f"repro-2026-{group}"
        cfg["description"] = (f"Reproduction sample of 2026 {group} contexts ({SAMPLER}); compare with "
                              "`reproduce-2026 --compare`.")
        cfg["selection"] = {"mode": "full", "civilizations": None, "units": None, "against": "*",
                            "contexts": {"file": str(gdir / "contexts.json"), "sha256": sha256_bytes(ctx_bytes)}}
        cfg["battle"]["orientation"] = single["battle"]["orientation"]  # published 2026 orientation
        cfg["sampling"]["policy"] = group
        if group == "one-three-ten":
            priors = [{"contextHash": r["contextHash"], "outcomes": [o["outcome"] for o in r["originalOutcomes"]],
                       "source": f"2026 forecast original evidence {r['originalEvidenceIds']}"}
                      for _, _, r in sorted(chosen, key=lambda x: x[2]["contextHash"])]
            data = _gz(priors)
            (gdir / "priors.jsonl.gz").write_bytes(data)
            cfg["sampling"].update(forecastSource="priors-file",
                                   priors={"file": str(gdir / "priors.jsonl.gz"), "sha256": sha256_bytes(data)})
        else:
            cfg["sampling"]["forecastSource"] = "none"
        cfg["output"] = {"records": str(gdir / "records")}
        (gdir / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
        C.load(gdir / "config.json")
        mismatched_lines = 0
        for stratum, campaign, r in chosen:
            seeds = []
            for m in sorted(r["measuredRecords"], key=lambda m: m["seed"]):
                line = runs.get((m["matchupId"], m["seed"], m.get("purpose")))
                if line is None or json.loads(line) != m:
                    mismatched_lines += 1
                seeds.append({k: m[k] for k in ("seed",) + COMPARED} | {"archivedWallSeconds": m["wallSeconds"]})
            expected.append({"group": group, "stratum": stratum, "campaign": campaign, "jobId2026": r["jobId"],
                             "pairKey": r["pairKey"], "contextHash": r["contextHash"], "context": r["context"],
                             "outcome": r["outcome"], "evidenceLevel": r.get("evidenceLevel"),
                             "samplingDecision": r.get("samplingDecision"), "seeds": seeds})
        if mismatched_lines:
            raise ValueError(f"{mismatched_lines} measured records differ from the archived runs.jsonl lines")
        report["groups"][group] = {
            "config": str(gdir / "config.json"), "contexts": len(chosen),
            "seeds": sum(len(r["measuredRecords"]) for _, _, r in chosen),
            "archivedWallSeconds": round(sum(m["wallSeconds"] for _, _, r in chosen for m in r["measuredRecords"]), 1),
            "bySeedCount": _count(r["seedCount"] for _, _, r in chosen),
            "byFamily": _count(r["context"]["family"] for _, _, r in chosen),
            "byOutcome": _count(r["outcome"] for _, _, r in chosen),
            "byCampaign": _count(c for _, c, _ in chosen),
            "withDraw": sum(any(m["outcome"] == "draw" for m in r["measuredRecords"]) for _, _, r in chosen),
            "byReason": _count((r.get("samplingDecision") or {}).get("reason", "-") for _, _, r in chosen),
        }
    (directory / "expected.jsonl.gz").write_bytes(_gz(expected))
    report["expected"] = str(directory / "expected.jsonl.gz")
    report["checks"] = _check_inventory(directory, expected)
    (directory / "sample.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def _count(values) -> dict:
    out = defaultdict(int)
    for v in values:
        out[str(v)] += 1
    return dict(sorted(out.items()))


def _check_inventory(directory: Path, expected: list) -> dict:
    """Every sampled context must be an inventory context of its config with the archived contextHash."""
    from aoe2x.matchups import inventory as I
    from aoe2x.matchups.cli import load_inputs
    out = {}
    for group in GROUPS:
        cfg = C.load(directory / group / "config.json")
        inputs = load_inputs(cfg)
        inv = I.build(cfg, inputs["bundle"], inputs["scenarioSet"], inputs["orientation"], inputs["setupHash"])
        by_pair = {j["pairKey"]: j for j in inv["jobs"]}
        rows = [e for e in expected if e["group"] == group]
        same = sum(by_pair.get(e["pairKey"], {}).get("contextHash") == e["contextHash"] for e in rows)
        if same != len(rows) or len(by_pair) != len(rows):
            raise ValueError(f"{group}: {len(rows) - same} sampled contexts are not inventory contexts with the "
                             "archived contextHash")
        out[group] = {"inventoryContexts": len(by_pair), "sameContextHash": same}
    return out


def compare(rb, directory: Path) -> dict:
    directory = Path(directory)
    expected = [json.loads(l) for l in gzip.decompress((directory / "expected.jsonl.gz").read_bytes()).decode().splitlines()]
    totals = {"contexts": 0, "seeds": 0, "mismatches": 0, "missing": 0, "classificationMismatches": 0,
              "decisionMismatches": 0, "seedSetMismatches": 0, "seedFieldMismatches": 0}
    groups, details = {}, []
    for group in GROUPS:
        records = directory / group / "records"
        runs = defaultdict(dict)
        for line in (records / "runs.jsonl").read_text().splitlines() if (records / "runs.jsonl").exists() else []:
            r = json.loads(line)
            runs[r["contextHash"]][r["seed"]] = r
        reviews = {}
        for path in (records / "pair-reviews").glob("*.json"):
            rv = json.loads(path.read_text())
            reviews[rv["contextHash"]] = rv
        g = {"contexts": 0, "seeds": 0, "mismatches": 0, "missing": 0, "walls": []}
        for e in (x for x in expected if x["group"] == group):
            g["contexts"] += 1
            review = reviews.get(e["contextHash"])
            entry = {"group": group, "jobId2026": e["jobId2026"], "contextHash": e["contextHash"], "problems": []}
            if review is None:
                entry["problems"].append("not reviewed")
                g["missing"] += 1
                details.append(entry)
                continue
            ours = runs[e["contextHash"]]
            if sorted(ours) != [s["seed"] for s in e["seeds"]]:
                entry["problems"].append({"seedSet": {"archived": [s["seed"] for s in e["seeds"]], "ours": sorted(ours)}})
                totals["seedSetMismatches"] += 1
            for s in e["seeds"]:
                g["seeds"] += 1
                row = ours.get(s["seed"])
                if row is None:
                    continue
                g["walls"].append((s["archivedWallSeconds"], row["wallSeconds"]))
                diff = {k: [s[k], row[k]] for k in COMPARED if s[k] != row[k]}
                if diff:
                    entry["problems"].append({"seed": s["seed"], "differences": diff})
                    totals["seedFieldMismatches"] += 1
            if review["outcome"] != e["outcome"]:
                entry["problems"].append({"outcome": [e["outcome"], review["outcome"]]})
                totals["classificationMismatches"] += 1
            if group == "one-three-ten" and review["samplingDecision"] != e["samplingDecision"]:
                entry["problems"].append({"samplingDecision": [e["samplingDecision"], review["samplingDecision"]]})
                totals["decisionMismatches"] += 1
            if entry["problems"]:
                g["mismatches"] += 1
                details.append(entry)
        walls = g.pop("walls")
        g["archivedWallSeconds"] = round(sum(a for a, _ in walls), 1)
        g["ourWallSeconds"] = round(sum(b for _, b in walls), 1)
        groups[group] = g
        for k in ("contexts", "seeds", "mismatches", "missing"):
            totals[k] += g[k]
    report = {**totals, "groups": groups, "problems": details, "comparedFields": list(COMPARED),
              "expectedSha256": sha256_bytes((directory / "expected.jsonl.gz").read_bytes()), "rbTip": rb.commit()}
    (directory / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


__all__ = ["prepare", "compare", "digest"]
