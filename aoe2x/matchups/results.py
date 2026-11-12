"""Result index: the archived 2026 per-context results, keyed for reuse.

The serving DB ``data/golden/civ_matchups_first_pass.db`` was built in layers
(HOW_THE_2026_CAMPAIGNS_RAN.md section 7.1):

1. first-pass profile table   RB <reports>/civ-matchups-first-pass-provisional-2026-11-02/profile-table.jsonl.gz
                              (``scripts/build_advisor_first_pass.py``): observed (adaptive, pilot and
                              ranking-era corrected-engine seed sets), rule-inferred, identity and
                              forecast rows;
2. mismatch reviews           RB <mismatch>/correction-snapshots/review-ready-2026-11-07
                              (= data/validation/civ-matchups-legacy-mismatch-2026-11-05/consolidated-2026-11-07,
                              ``scripts/apply_advisor_matchup_corrections.py``);
3. forecast reviews           RB <forecast>/correction-snapshots/070
                              (= data/validation/civ-matchups-forecast-validation-2026-11-07/2026-11-10,
                              ``scripts/apply_advisor_forecast_corrections.py``);
4. recovery reviews           RB <recovery>/correction-snapshots/002
                              (= data/validation/civ-matchups-forecast-recovery-2026-11-10/2026-11-11,
                              ``scripts/apply_advisor_recovery_results.py``).

A later layer replaces an earlier one for the same ``pairKey``. The index
holds one row per profile pair (68,916) with the final outcome, its evidence
and per-seed records, and maps each row onto the inventory built from the
run config: ``same`` orientation, or ``reversed`` (the stored physical context
has the two armies the other way round; the 2026 forecast contexts kept the
orientation they were forecast in, ``contextPolicy:
preserve-approved-forecast-context-v1``). A result is never transferred into
the other orientation: a reversed row can be reused only by a run whose
inventory uses that orientation for the pair.

Seed records are lists in ``SEED_FIELDS`` order to keep the index compact.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from aoe2x.matchups.battle import ContextBuilder
from aoe2x.matchups.bundle import Scenarios
from aoe2x.matchups.canonical import digest, sha256_bytes

INDEX_SCHEMA = "aoe2-matchup-result-index/v1"
SEED_FIELDS = ["seed", "winnerOwner", "ticks", "unitRemainingHp", "opponentRemainingHp", "unitSurvivors",
               "opponentSurvivors", "unitStartingHp", "opponentStartingHp", "finalStateHash", "eventLogHash",
               "physicsVersion"]
CONTEXT_FIELDS = ("profiles", "counts", "scenarioHash", "family", "engineFamily", "weightedCosts", "policy")
FROZEN_PHYSICS = "frozen-civ-matchups-v3"
# Adaptive and pilot seeds ran on the corrected engine of RB commit 85ac79df5; it differs from
# frozen-civ-matchups-v3 only in the three lossless-event-stream files, and the mismatch campaign
# replayed 2,379 adaptive seed sets exactly on frozen-civ-matchups-v3.
ADAPTIVE_PHYSICS = "frozen-civ-matchups-v3:adaptive-2026-10-31"
RANKING_PHYSICS = "ranking-corrected-engine-2026-10-29"
REUSABLE_PHYSICS = {FROZEN_PHYSICS, ADAPTIVE_PHYSICS}


def _seed(row: dict, physics: str) -> list:
    rec = {**row, "physicsVersion": row.get("physicsVersion") or physics}
    return [rec.get(f) for f in SEED_FIELDS]


def _verified_snapshot(rb, base: str, files: list[str]) -> tuple[dict, dict]:
    manifest_raw = rb.show(f"{base}/manifest.json")
    manifest = json.loads(manifest_raw)
    data = {}
    for name in files:
        raw = rb.show(f"{base}/{name}")
        expected = manifest.get("files", {}).get(name)
        if expected and sha256_bytes(raw) != expected:
            raise ValueError(f"{base}/{name} does not match its snapshot manifest")
        data[name] = raw
    return manifest, {"path": base, "manifestSha256": sha256_bytes(manifest_raw),
                      "files": {k: sha256_bytes(v) for k, v in data.items()}, "_data": data}


def _gzlines(raw: bytes) -> list:
    return [json.loads(line) for line in gzip.decompress(raw).decode().splitlines() if line.strip()]


class RunLines:
    """``path:line`` run references of the first-pass table, read lazily from RB."""

    def __init__(self, rb):
        from aoe2x.matchups.rbsource import CAMPAIGNS
        self.rb, self.cache = rb, {}
        self.aliases = {"runs.jsonl": f"{CAMPAIGNS}/unit-rankings-consolidated-2026-10-29/runs.jsonl",
                        "additional-recorded-runs.jsonl":
                            f"{CAMPAIGNS}/unit-rankings-consolidated-2026-10-29/additional-recorded-runs.jsonl"}

    def get(self, ref: str) -> tuple[dict, str]:
        path, line = ref.rsplit(":", 1)
        path = self.aliases.get(path, path)
        if path not in self.cache:
            self.cache[path] = self.rb.show(path).decode().split("\n")
        if "/adaptive/" in path or "/pilot/" in path:
            physics = ADAPTIVE_PHYSICS
        else:
            physics = RANKING_PHYSICS
        return json.loads(self.cache[path][int(line) - 1]), physics


def import_2026(rb, inventory: dict, inputs: dict, serving_db: Path | None = None) -> tuple[list, dict]:
    from aoe2x.matchups import rbsource as S
    sources = {}
    # 1. first pass
    fp_manifest_raw = rb.show(f"{S.FIRST_PASS}/manifest.json")
    fp_raw = rb.show(f"{S.FIRST_PASS}/profile-table.jsonl.gz")
    first_pass = _gzlines(fp_raw)
    sources["firstPass"] = {"path": f"{S.FIRST_PASS}/profile-table.jsonl.gz", "sha256": sha256_bytes(fp_raw),
                            "manifestSha256": sha256_bytes(fp_manifest_raw), "rows": len(first_pass)}
    # 2-3. mismatch and forecast reviewed-only snapshots
    snapshots = {}
    for name, base in (("mismatch", f"{S.MISMATCH}/correction-snapshots/review-ready-2026-11-07"),
                       ("forecast", f"{S.FORECAST}/correction-snapshots/070")):
        manifest, info = _verified_snapshot(rb, base, ["reviewed-contexts.jsonl.gz"])
        rows = _gzlines(info.pop("_data")["reviewed-contexts.jsonl.gz"])
        if len(rows) != manifest["reviewedContexts"]:
            raise ValueError(f"{name} snapshot row count")
        snapshots[name] = rows
        sources[name] = {**info, "rows": len(rows), "campaignHash": manifest["campaignHash"],
                         "version": manifest["version"]}
    # 4. recovery snapshot (contexts come from the forecast jobs)
    rec_base = f"{S.RECOVERY}/correction-snapshots/002"
    rec_raw = rb.show(f"{rec_base}/matchup-reviews.json")
    recovery = json.loads(rec_raw)
    rec_runs_raw = rb.show(f"{rec_base}/runs.jsonl.gz")
    rec_runs = defaultdict(list)
    for x in _gzlines(rec_runs_raw):
        rec_runs[x["recoveryContextId"]].append(x)
    # all-forecast-contexts holds the 39,124 runnable jobs plus the 24 held contexts.
    fv_raw = rb.show(f"{S.FORECAST}/all-forecast-contexts.jsonl.gz")
    fv_jobs = {j["id"]: j for j in _gzlines(fv_raw)}
    sources["recovery"] = {"path": rec_base, "matchupReviewsSha256": sha256_bytes(rec_raw), "rows": len(recovery),
                           "runsSha256": sha256_bytes(rec_runs_raw),
                           "contextsFrom": f"{S.FORECAST}/all-forecast-contexts.jsonl.gz",
                           "contextsSha256": sha256_bytes(fv_raw)}

    final: dict[str, dict] = {}
    layer_counts = Counter()
    runs = RunLines(rb)
    for r in first_pass:
        et = r["evidenceType"]
        row = {"pairKey": r["pairKey"], "outcome": r["outcome"], "evidenceType": et, "source": None,
               "context": r.get("context"), "seeds": []}
        if et == "identity":
            row.update(source="identity", context=None)
        elif et == "inferred":
            row.update(source="first-pass-inference", ruleId=r.get("ruleId"), ruleVersion=r.get("ruleVersion"))
        elif et == "observed":
            seeds = []
            for ref in r["sourceRunIds"]:
                rec, physics = runs.get(ref)
                seeds.append(_seed(rec, physics))
            row.update(source="first-pass-observed", jobId=r["sourceMatchups"][0], seeds=sorted(seeds))
        elif et == "predicted_unvalidated":
            row.update(source="first-pass-forecast", predictionTier=r.get("predictionTier"))
        else:
            raise ValueError(f"unknown first-pass evidence type {et}")
        final[r["pairKey"]] = row
        layer_counts["firstPass"] += 1
    replaced = Counter()
    for name in ("mismatch", "forecast"):
        seen = set()
        for r in snapshots[name]:
            if r["pairKey"] in seen:
                raise ValueError(f"{name}: pair reviewed twice {r['pairKey']}")
            seen.add(r["pairKey"])
            if digest(r["context"]) != r["contextHash"]:
                raise ValueError(f"{name}: contextHash mismatch {r['jobId']}")
            replaced[f"{name}<-{final[r['pairKey']]['source']}"] += 1
            physics = r["physicsVersion"]
            seeds = sorted(_seed(m, physics) for m in r["measuredRecords"])
            if [s[0] for s in seeds] != sorted(x["seed"] for x in r["seedResults"]):
                raise ValueError(f"{name}: seed set mismatch {r['jobId']}")
            a, b = r["pairKey"].split("|")
            if a == b:
                # A mirror battle of one profile stays an identity pair ("equivalent" even if a
                # seeded mirror had a winner: reviewJob() in RB run-mismatch-validation.mjs).
                if r["outcome"] != "equivalent":
                    raise ValueError(f"{name}: identity pair {r['jobId']} reviewed as {r['outcome']}")
                final[r["pairKey"]].update(mirrorValidation={"jobId": r["jobId"], "context": r["context"],
                                                             "contextHash": r["contextHash"], "seeds": seeds})
                layer_counts[f"{name}IdentityMirrors"] += 1
                continue
            final[r["pairKey"]] = {"pairKey": r["pairKey"], "outcome": r["outcome"], "evidenceType": "observed",
                                   "source": f"{name}-validation", "jobId": r["jobId"], "context": r["context"],
                                   "contextHash": r["contextHash"], "validationMode": r["validationMode"],
                                   "evidenceLevel": r.get("evidenceLevel"), "seeds": seeds}
            layer_counts[name] += 1
    for r in recovery:
        job = fv_jobs[r["jobId"]]
        context = job["context"]
        if digest(context) != job["contextHash"]:
            raise ValueError("recovery context hash")
        seeds = sorted(_seed(x["record"], x["sourceReference"]["physicsVersion"])
                       for x in rec_runs[r["jobId"]])
        if [x[0] for x in seeds] != sorted(x["seed"] for x in r["seeds"]):
            raise ValueError(f"recovery: seed set mismatch {r['jobId']}")
        replaced[f"recovery<-{final[job['pairKey']]['source']}"] += 1
        final[job["pairKey"]] = {"pairKey": job["pairKey"], "outcome": r["outcome"], "evidenceType": "observed",
                                 "source": "forecast-recovery", "jobId": r["jobId"], "context": context,
                                 "contextHash": job["contextHash"], "evidenceLevel": r["evidenceLevel"],
                                 "physicsVersions": r["physicsVersions"], "seeds": seeds}
        layer_counts["recovery"] += 1

    # map onto the inventory
    jobs = {j["pairKey"]: j for j in inventory["jobs"]}
    identity = {r["pairKey"] for r in inventory["identity"]}
    mechanics = {}
    for v in inputs["bundle"]["variants"]:
        mechanics.setdefault(v["profileHash"], v["mechanics"])
    build_context = ContextBuilder(mechanics, Scenarios(inputs["scenarioSet"]), inputs_battle(inputs))
    mapping = Counter()
    by_source = defaultdict(Counter)
    index = []
    for pk in sorted(final):
        row = final[pk]
        if row["context"] is not None and "contextHash" not in row:
            row["contextHash"] = digest(row["context"])
        if row["source"] == "identity":
            status = "identity" if pk in identity else "outside-selection"
        elif pk not in jobs:
            # Not a context of this run (selection-limited config, or the pair is identity here).
            status = "unmapped" if pk in identity else "outside-selection"
        else:
            job = jobs[pk]
            ctx = {f: row["context"].get(f) for f in CONTEXT_FIELDS}
            ours = {f: job[f if f != "profiles" else "profileHashes"] for f in CONTEXT_FIELDS}
            if ctx == ours:
                status = "same"
            else:
                mirror = build_context(*reversed(job["profileHashes"]))
                status = "reversed" if ctx == {f: mirror[f] for f in CONTEXT_FIELDS} else "unmapped"
            row["inventoryId"] = job["id"]
        row["orientation"] = status
        physics = {s[-1] for s in row["seeds"]}
        row["reusable"] = (row["evidenceType"] == "observed" and status in ("same", "reversed")
                           and bool(physics) and physics <= REUSABLE_PHYSICS)
        if row["reusable"]:
            row["resultKey"] = digest({"contextHash": row["contextHash"], "setupHash": inputs["setupHash"]})
        mapping[status] += 1
        by_source[row["source"]][status] += 1
        index.append(row)
    covered = set(final)
    report = {
        "schema": INDEX_SCHEMA, "seedFields": SEED_FIELDS, "sources": sources, "rb": {"ref": rb.ref, "tip": rb.commit()},
        "layers": dict(layer_counts), "replaced": dict(sorted(replaced.items())),
        "rows": len(index),
        "evidenceTypes": dict(sorted(Counter(r["evidenceType"] for r in index).items())),
        "finalSources": dict(sorted(Counter(r["source"] for r in index).items())),
        "outcomes": dict(sorted(Counter(r["outcome"] for r in index).items())),
        "seedRecords": sum(len(r["seeds"]) for r in index),
        "physicsVersions": dict(sorted(Counter(s[-1] for r in index for s in r["seeds"]).items())),
        "reusable": sum(r["reusable"] for r in index),
        "mapping": {"same": mapping["same"], "reversed": mapping["reversed"], "identity": mapping["identity"],
                    "unmapped": mapping["unmapped"], "ambiguous": 0,
                    "outsideSelection": mapping["outside-selection"],
                    "inventoryPairsWithoutResult": len((set(jobs) | identity) - covered),
                    "bySource": {k: dict(v) for k, v in sorted(by_source.items())}},
        "remainingForecasts": sum(r["evidenceType"] == "predicted_unvalidated" for r in index),
        "setupHash": inputs["setupHash"], "bundleHash": inputs["bundle"]["bundleHash"],
    }
    if serving_db is not None and Path(serving_db).exists():
        report["servingDbCheck"] = check_serving_db(Path(serving_db), {r["pairKey"]: r for r in index})
    return index, report


def inputs_battle(inputs: dict) -> dict:
    s = inputs["setup"]
    return {k: s[k] for k in ("armyCap", "resourceWeights", "disableAiOrders", "disableKiting",
                               "preserveOwnerOrientation")}


def check_serving_db(path: Path, index: dict) -> dict:
    """Compare final outcome/evidence type/context per pair with the serving DB evidence table."""
    import sqlite3
    import zlib
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
        counts = Counter()
        examples = {}
        for (blob,) in db.execute("SELECT data FROM evidence"):
            row = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
            ours = index.get(row["pairKey"])
            if ours is None:
                counts["missing"] += 1
                continue
            counts["rows"] += 1
            for field, a, b in (("outcome", ours["outcome"], row["outcome"]),
                                ("evidenceType", ours["evidenceType"], row["evidenceType"]),
                                ("context", ours["context"], row.get("context") if ours["context"] is not None else None)):
                if a == b:
                    counts[f"{field}Equal"] += 1
                else:
                    examples.setdefault(field, row["pairKey"])
    finally:
        db.close()
    from aoe2x.matchups.paths import REPO_ROOT
    try:
        shown = path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        shown = str(path)
    return {"path": shown, "sha256": sha256_bytes(path.read_bytes()), **dict(counts), "firstDifference": examples}


def write_index(index: list, path: Path, report: dict) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = gzip.compress("".join(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n" for r in index).encode(),
                        compresslevel=9, mtime=0)
    path.write_bytes(data)
    receipt = {**report, "index": {"file": path.name, "sha256": sha256_bytes(data), "bytes": len(data),
                                   "rows": len(index)}}
    path.with_name(path.name.replace(".jsonl.gz", "") + ".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
