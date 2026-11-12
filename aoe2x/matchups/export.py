"""``export``: a compact, deterministic "reviewed results" snapshot of a run.

The snapshot is the small artefact build step 4 (serving DB) consumes and the
one meant to be committed (proposal section 8, ``matchups/runs/<runId>/``):

    manifest.json        hashes of config, bundle, scenario set, setup, engine,
                         inventory, result index, journals and every file below
    results.jsonl.gz     one row per reviewed context, in result-index row shape
                         (``results.INDEX_SCHEMA``: pairKey, outcome, evidenceType,
                         source, context, contextHash, resultKey, seeds as
                         ``SEED_FIELDS`` lists, ...) so a run's rows replace index
                         rows by ``pairKey``
    reused.jsonl.gz      contexts taken from the baseline index (jobId, pairKey, resultKey)
    blocked.jsonl.gz     contexts that exhausted the watchdog steps (never results)

Like RB ``CM/export-forecast-reviews.mjs`` every review is re-verified against
the seed journal before it is exported (seed set, record hashes, sampling
decision and outcome recomputed from the journal rows). Nothing that depends
on timing (timestamps, wall seconds, attempt numbers) is exported, rows are
sorted, JSON keys are sorted and gzip has mtime 0, so the same journals give a
byte-identical snapshot, also when the run was interrupted and resumed.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

from aoe2x.matchups import journal as J
from aoe2x.matchups.canonical import digest, sha256_bytes
from aoe2x.matchups.results import INDEX_SCHEMA, SEED_FIELDS
from aoe2x.matchups.runner import Run, RunError, content

SNAPSHOT_SCHEMA = "aoe2-matchup-run-snapshot/v1"


def _gz(rows: list) -> bytes:
    text = "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows)
    return gzip.compress(text.encode(), compresslevel=9, mtime=0)


def _file_hash(path: Path) -> str | None:
    return sha256_bytes(path.read_bytes()) if path.exists() else None


def build(run: Run) -> tuple[dict, dict[str, bytes]]:
    run.prepare(build=False)
    R = run.records
    runs = J.read_journal(R / "runs.jsonl")
    attempts = J.read_journal(R / "attempts.jsonl")
    rows: dict[str, list] = {}
    for r in runs:
        if r["campaignHash"] != run.run_hash:
            raise RunError("runs.jsonl belongs to another run")
        rows.setdefault(r["matchupId"], []).append(r)
    reviews = {}
    for path in sorted((R / "pair-reviews").glob("*.json")):
        review = json.loads(path.read_text())
        reviews[review["jobId"]] = review
    results, problems = [], []
    for jid, review in sorted(reviews.items()):
        job = run.by_id.get(jid)
        body = {k: v for k, v in review.items() if k != "reviewHash"}
        seeds = sorted(rows.get(jid, []), key=lambda r: r["seed"])
        prior, _ = run.prior(job) if job else (None, None)
        if job is None or digest(body) != review["reviewHash"] or review["campaignHash"] != run.run_hash:
            problems.append(f"{jid}: review hash/run")
            continue
        if [s["seed"] for s in seeds] != [s["seed"] for s in review["seedResults"]] or \
                [digest(s) for s in seeds] != [s["recordHash"] for s in review["seedResults"]]:
            problems.append(f"{jid}: review seeds differ from the journal")
            continue
        decision = run.policy.decision(job, seeds, prior)
        if decision != review["samplingDecision"] or decision["requiredSeeds"] or \
                run.policy.outcome(job, seeds, prior) != review["outcome"]:
            problems.append(f"{jid}: sampling decision or outcome does not follow from the journal")
            continue
        results.append({
            "pairKey": job["pairKey"], "outcome": review["outcome"], "evidenceType": "observed",
            "source": f"run:{run.cfg['runId']}", "runHash": run.run_hash, "jobId": jid,
            "context": review["context"], "contextHash": job["contextHash"], "resultKey": job["resultKey"],
            "validationMode": review["validationMode"], "evidenceLevel": review["evidenceLevel"],
            "samplingPolicy": review["samplingPolicy"], "samplingDecision": decision,
            "priorOutcomes": review["priorOutcomes"], "changed": review["changed"],
            "seeds": [[s.get(f) for f in SEED_FIELDS] for s in seeds],
            "orientation": "same", "reusable": True,
        })
    if problems:
        raise RunError(f"{len(problems)} review(s) failed verification, e.g. {problems[0]}")
    results.sort(key=lambda r: r["pairKey"])
    reuse = J.read_json(R / "reuse.json", {}) or {}
    reused = sorted(([c[0], run.by_id[c[0]]["pairKey"], c[1], c[2]] for c in reuse.get("contexts", [])
                     if c[0] not in reviews), key=lambda r: r[1])
    blocked_state: dict[str, dict] = {}
    for a in attempts:
        jid = a["matchupId"]
        if a.get("unblocked"):
            blocked_state.pop(jid, None)
            continue
        b = blocked_state.setdefault(jid, {"attempts": 0, "exhausted": False})
        b["attempts"] += 1
        if a.get("exhausted"):
            b.update(exhausted=True, seed=a["seed"], error=(a.get("error") or {}).get("name"),
                     watchdog=a.get("watchdog"), limitSeconds=a.get("limitSeconds"))
    blocked = sorted(({"jobId": jid, "pairKey": run.by_id[jid]["pairKey"], "contextHash": run.by_id[jid]["contextHash"],
                       "resultKey": run.by_id[jid]["resultKey"], "seed": b["seed"], "failedAttempts": b["attempts"],
                       "lastError": b["error"], "watchdog": b["watchdog"], "lastLimitSeconds": b["limitSeconds"],
                       "seedsCompleted": sorted(r["seed"] for r in rows.get(jid, []))}
                      for jid, b in blocked_state.items() if b["exhausted"] and jid not in reviews),
                     key=lambda r: r["pairKey"])
    files = {"results.jsonl.gz": _gz(results), "reused.jsonl.gz": _gz(reused), "blocked.jsonl.gz": _gz(blocked)}
    total = len(run.jobs)
    engine = run.engine
    manifest = {
        "schema": SNAPSHOT_SCHEMA, "resultRowSchema": INDEX_SCHEMA, "seedFields": SEED_FIELDS,
        "runId": run.cfg["runId"], "runHash": run.run_hash, "configHash": run.config_hash, "config": run.cfg,
        "bundleHash": run.inputs["bundle"]["bundleHash"], "scenarioSetHash": run.inputs["scenarioSet"]["setHash"],
        "setupHash": run.inputs["setupHash"], "setup": run.inputs["setup"],
        "engine": {"engineId": engine["engineId"], "filesDigest": engine["filesDigest"],
                   "physicsVersion": engine["physicsVersion"], "executionVersion": engine["executionVersion"],
                   "nodeVersions": sorted({r.get("nodeVersion") for r in runs if r.get("nodeVersion")})},
        "inventory": {"sha256": run.inventory_sha256, "contexts": total},
        "resultIndexSha256": run.index_sha256, "forcedRerun": bool(reuse.get("forced")),
        "journal": {"runsSha256": _file_hash(R / "runs.jsonl"), "runsLines": len(runs),
                    "runsContentDigest": digest(sorted((content(r) for r in runs),
                                                       key=lambda r: (r["matchupId"], r["seed"]))),
                    "attemptsSha256": _file_hash(R / "attempts.jsonl"), "attemptsLines": len(attempts)},
        "counts": {"contexts": total, "reviewed": len(results), "reused": len(reused), "blocked": len(blocked),
                   "remaining": total - len(results) - len(reused) - len(blocked), "seeds": len(runs),
                   "outcomes": dict(sorted(Counter(r["outcome"] for r in results).items())),
                   "evidenceLevels": dict(sorted(Counter(r["evidenceLevel"] for r in results).items())),
                   "seedCounts": dict(sorted(Counter(str(len(r["seeds"])) for r in results).items()))},
        "files": {name: {"sha256": sha256_bytes(data), "bytes": len(data)} for name, data in files.items()},
    }
    manifest["complete"] = manifest["counts"]["remaining"] == 0
    manifest["snapshotHash"] = digest(manifest)
    return manifest, files


def write(run: Run, out: Path) -> dict:
    manifest, files = build(run)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        J.write_bytes_atomic(out / name, data)
    J.write_bytes_atomic(out / "manifest.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    return manifest
