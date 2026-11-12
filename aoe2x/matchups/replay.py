"""replay-check: re-run archived 2026 seeds on a pinned engine and compare exactly.

Samples are drawn deterministically from the mismatch-validation and
forecast-validation ``runs.jsonl`` journals on RB, stratified so the check
covers every scenario family (melee/ranged combinations, i.e. unit types),
wins for both sides, draws and fights longer than the old 9,000-tick cap
(which only finish because the worker lifts the cap). Each sampled seed is
rebuilt as the 2026 ``payload(job, seed)`` (RB forecast-validation-lib.mjs):
the job's teamKeys' mechanics from the mechanics bundle, its counts, its
scenario, ``disableAiOrders``/``disableKiting``/``preserveOwnerOrientation``
true and no snapshots. A replay must reproduce every compared field exactly;
nothing is rounded or tolerated.
"""
from __future__ import annotations

import hashlib
import json
import platform
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from aoe2x.matchups.bundle import Scenarios
from aoe2x.matchups.canonical import digest

SAMPLER = "replay-check-strata-v1"
COMPARED = ("outcome", "winnerOwner", "ticks", "unitStartingHp", "opponentStartingHp", "unitRemainingHp",
            "opponentRemainingHp", "unitSurvivors", "opponentSurvivors", "finalStateHash", "eventLogHash")
FAMILIES = ("melee_vs_melee", "melee_vs_ranged", "ranged_vs_melee", "ranged_vs_ranged")


def _rank(campaign: str, row: dict) -> str:
    text = f"{SAMPLER}|{campaign}|{row['matchupId']}|{row['seed']}|{row.get('purpose', '')}"
    return hashlib.sha256(text.encode()).hexdigest()


def select(journals: dict[str, tuple[list[dict], dict]], per_stratum: int = 3,
           max_wall: float = 45.0, long_max_wall: float = 150.0) -> list[dict]:
    """Pick seeds: per campaign, ``per_stratum`` per (win|loss) x family, draws and >9,000-tick fights."""
    chosen = []
    for campaign, (runs, jobs) in journals.items():
        strata = defaultdict(list)
        for row in runs:
            job = jobs[row["matchupId"]]
            if row["ticks"] > 9000 and row["wallSeconds"] <= long_max_wall:
                strata["long"].append(row)
            if row["wallSeconds"] > max_wall:
                continue
            if row["outcome"] == "draw":
                strata["draw"].append(row)
            else:
                strata[f"{row['outcome']}|{job['family']}"].append(row)
        order = [f"{o}|{f}" for o in ("win", "loss") for f in FAMILIES] + ["draw", "long"]
        used = set()
        for name in order:
            picked = 0
            for row in sorted(strata[name], key=lambda r: _rank(campaign, r)):
                if picked == per_stratum:
                    break
                if row["matchupId"] in used:
                    continue
                used.add(row["matchupId"])
                chosen.append({"campaign": campaign, "stratum": name, "row": row, "job": jobs[row["matchupId"]]})
                picked += 1
    return chosen


def payload(job: dict, seed: int, variants: dict, scenarios: Scenarios) -> dict:
    teams = []
    for i, key in enumerate(job["teamKeys"]):
        v = variants[key]
        if v["profileHash"] != job["profileHashes"][i]:
            raise ValueError(f"{job['id']}: {key} does not have profile {job['profileHashes'][i]}")
        teams.append({"mechanics": v["mechanics"], "count": job["counts"][i]})
    scenario_hash, scenario = scenarios.resolve(job["family"], job["engineFamily"])
    if scenario_hash != job["scenarioHash"]:
        raise ValueError(f"{job['id']}: scenario {scenario_hash} is not the job's {job['scenarioHash']}")
    return {"jobId": job["id"], "seed": seed, "teams": teams, "scenario": scenario,
            "disableAiOrders": True, "disableKiting": True, "preserveOwnerOrientation": True,
            "retainSnapshots": False}


def as_record(result: dict) -> dict:
    """``record()`` in RB run-forecast-validation.mjs, restricted to compared fields."""
    rem = result["remainingByOwner"]
    start = result["startingHpByOwner"]
    return {"outcome": "draw" if result["outcome"] == "draw" else ("win" if result["winnerOwner"] == 2 else "loss"),
            "winnerOwner": result["winnerOwner"], "ticks": result["ticks"],
            "unitStartingHp": start["2"], "opponentStartingHp": start["3"],
            "unitRemainingHp": (rem.get("2") or {}).get("hp", 0), "opponentRemainingHp": (rem.get("3") or {}).get("hp", 0),
            "unitSurvivors": (rem.get("2") or {}).get("units", 0), "opponentSurvivors": (rem.get("3") or {}).get("units", 0),
            "finalStateHash": result["finalStateHash"], "eventLogHash": result["eventLogHash"]}


def load_journals(rb) -> dict:
    from aoe2x.matchups.rbsource import FORECAST, MISMATCH
    journals = {}
    for name, base in (("mismatch-validation-2026-11-05", MISMATCH), ("forecast-validation-2026-11-07", FORECAST)):
        jobs = {j["id"]: j for j in rb.jsonl(f"{base}/jobs.jsonl.gz")}
        runs = rb.jsonl(f"{base}/runs.jsonl")
        journals[name] = (runs, jobs)
    return journals


def replay_check(rb, bundle: dict, scenario_set: dict, *, node: str | None, workers: int,
                 per_stratum: int, out_dir: Path, engine_id: str) -> dict:
    from aoe2x.matchups.engine import find_node, node_version, run_battles
    journals = load_journals(rb)
    sample = select(journals, per_stratum=per_stratum)
    variants = {v["key"]: v for v in bundle["variants"]}
    scenarios = Scenarios(scenario_set)
    binary = find_node(node)
    version = node_version(binary)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="replay-check-", dir=out_dir) as tmp:
        jobs_path, results_path = Path(tmp) / "jobs.jsonl", Path(tmp) / "results.jsonl"
        with jobs_path.open("w") as f:
            for i, s in enumerate(sample):
                f.write(json.dumps({"key": str(i), "payload": payload(s["job"], s["row"]["seed"], variants, scenarios)}) + "\n")
        proc = run_battles(jobs_path, results_path, engine_id=engine_id, node=binary, workers=workers,
                           node_policy="warn")
        if proc.returncode:
            raise RuntimeError(f"run-battles failed ({proc.returncode}):\n{proc.stderr[-4000:]}")
        results = {r["key"]: r for r in (json.loads(l) for l in results_path.read_text().splitlines() if l)}
    checks, identical = [], 0
    for i, s in enumerate(sample):
        row, got = s["row"], results.get(str(i))
        entry = {"campaign": s["campaign"], "stratum": s["stratum"], "matchupId": row["matchupId"], "seed": row["seed"],
                 "teamKeys": s["job"]["teamKeys"], "family": s["job"]["family"], "archivedTicks": row["ticks"],
                 "archivedWallSeconds": row["wallSeconds"]}
        if not got or not got.get("ok"):
            entry.update({"identical": False, "error": (got or {}).get("attempts", "missing result")})
        else:
            actual = as_record(got["result"])
            diffs = {k: {"archived": row[k], "replayed": actual[k]} for k in COMPARED if row[k] != actual[k]}
            entry.update({"identical": not diffs, "differences": diffs, "wallSeconds": got["wallSeconds"]})
        identical += entry["identical"]
        checks.append(entry)
    report = {
        "sampler": SAMPLER, "perStratum": per_stratum, "engineId": engine_id,
        "node": {"binary": binary, "version": version},
        "platform": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bundleHash": bundle["bundleHash"], "scenarioSetHash": scenario_set["setHash"],
        "comparedFields": list(COMPARED),
        "sampleDigest": digest([[c["campaign"], c["matchupId"], c["seed"]] for c in checks]),
        "seeds": len(checks), "identical": identical, "allIdentical": identical == len(checks),
        "strata": {k: sum(1 for c in checks if c["stratum"] == k) for k in sorted({c["stratum"] for c in checks})},
        "campaigns": {k: sum(1 for c in checks if c["campaign"] == k) for k in sorted({c["campaign"] for c in checks})},
        "checks": checks,
    }
    (out_dir / f"replay-check-{version}.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def record_evidence(engine_id: str, report: dict) -> dict:
    """Add a passing report to ENGINE.json ``node.verified`` (one entry per Node version)."""
    from aoe2x.matchups.engine import engine_dir
    if not report["allIdentical"]:
        raise ValueError("only a fully identical replay check can be recorded")
    path = engine_dir(engine_id) / "ENGINE.json"
    manifest = json.loads(path.read_text())
    entry = {"version": report["node"]["version"], "checkedAt": report["checkedAt"], "seeds": report["seeds"],
             "identical": report["identical"], "sampler": report["sampler"], "sampleDigest": report["sampleDigest"],
             "comparedFields": report["comparedFields"], "platform": report["platform"],
             "longestArchivedTicks": max(c["archivedTicks"] for c in report["checks"]),
             "evidence": "aoe2x matchups replay-check (archived mismatch + forecast seeds)"}
    verified = [v for v in manifest["node"].get("verified", []) if v["version"] != entry["version"]]
    manifest["node"]["verified"] = sorted(verified + [entry], key=lambda v: v["version"])
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return entry
