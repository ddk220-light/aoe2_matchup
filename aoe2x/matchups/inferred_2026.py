"""Selection + priors for re-simulating the 2026 rule-inferred matchup contexts.

Run config: ``configs/inferred-2026-resim.json``; operator note: ``RUN_INFERRED_2026.md``.

``build``  reads the 2026 result index (``import-results`` output), keeps the
           rows with ``evidenceType == "inferred"`` (10,193) and writes, outside git:
           ``contexts.jsonl.gz`` (``selection.contexts``: pairKey + contextHash) and
           ``priors.jsonl.gz`` (``sampling.priors``: contextHash, pairKey,
           ``outcomes = [inferred outcome]`` in pairKey order, source = the rule).
           Both are gzip mtime 0, sorted, so the same index gives the same bytes.
``verify`` builds the run's inventory in memory from the config and checks, for every
           inferred row: exactly one job with its pairKey, the same ``contextHash``
           (i.e. the same physical orientation and context as the stored, published
           result), and exactly one serving-DB ``evidence`` row with that pairKey,
           ``evidenceType`` inferred, the same context and outcome; displayed cells of
           those evidence rows = the jobs' ``displayedCells``.

    python -m aoe2x.matchups.inferred_2026 build  --index I --out DIR
    python -m aoe2x.matchups.inferred_2026 verify <config> [--serving-db data/golden/civ_matchups_first_pass.db]
"""
from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import sys
import zlib
from collections import Counter
from pathlib import Path

from aoe2x.matchups.canonical import digest, sha256_bytes
from aoe2x.matchups.paths import REPO_ROOT


def _gz(rows: list[dict]) -> bytes:
    return gzip.compress("".join(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n" for r in rows).encode(),
                         compresslevel=9, mtime=0)


def _index(path: Path) -> list[dict]:
    return [json.loads(line) for line in gzip.open(path, "rt") if line.strip()]


def build(index_path: Path, out: Path) -> dict:
    raw = index_path.read_bytes()
    rows = [json.loads(line) for line in gzip.decompress(raw).decode().splitlines() if line.strip()]
    inferred = sorted((r for r in rows if r["evidenceType"] == "inferred"), key=lambda r: r["pairKey"])
    for r in inferred:
        if digest(r["context"]) != r["contextHash"]:
            raise ValueError(f"{r['pairKey']}: contextHash does not match its context")
        if r["outcome"] not in ("a_win", "b_win"):
            raise ValueError(f"{r['pairKey']}: unexpected inferred outcome {r['outcome']}")
    contexts = [{"pairKey": r["pairKey"], "contextHash": r["contextHash"]} for r in inferred]
    priors = [{"contextHash": r["contextHash"], "pairKey": r["pairKey"], "outcomes": [r["outcome"]],
               "source": f"first-pass-inference:{r.get('ruleId')}:{r.get('ruleVersion')}"} for r in inferred]
    out.mkdir(parents=True, exist_ok=True)
    report = {"index": {"path": str(index_path), "sha256": sha256_bytes(raw), "rows": len(rows)},
              "inferred": len(inferred), "outcomes": dict(Counter(r["outcome"] for r in inferred)),
              "rules": dict(Counter(r.get("ruleId") for r in inferred)),
              "indexOrientationVsAdaptive": dict(Counter(r["orientation"] for r in inferred)), "files": {}}
    for name, data in (("contexts.jsonl.gz", _gz(contexts)), ("priors.jsonl.gz", _gz(priors))):
        (out / name).write_bytes(data)
        report["files"][name] = {"path": str(out / name), "sha256": sha256_bytes(data), "bytes": len(data)}
    (out / "selection-receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def verify(config: str, serving_db: Path, index_path: Path | None) -> dict:
    from aoe2x.matchups import config as C
    from aoe2x.matchups import runner as RN
    from aoe2x.matchups.cli import _config_path
    cfg = C.load(_config_path(config))
    run = RN.Run(cfg).prepare(build="memory")
    jobs = {j["pairKey"]: j for j in run.jobs}
    ctx_ref = cfg["selection"]["contexts"]
    selection = [json.loads(line) for line in gzip.open(C.resolve_path(ctx_ref["file"], REPO_ROOT), "rt") if line.strip()]
    index = {r["pairKey"]: r for r in _index(index_path)} if index_path else {}
    problems = Counter()
    examples = {}

    def bad(kind, pk):
        problems[kind] += 1
        examples.setdefault(kind, pk)

    for s in selection:
        j = jobs.get(s["pairKey"])
        if j is None:
            bad("noJob", s["pairKey"])
        elif j["contextHash"] != s["contextHash"]:
            bad("contextHashDiffers", s["pairKey"])
        prior, _ = run.prior(j) if j else (None, None)
        if not prior:
            bad("noPrior", s["pairKey"])
        if index and index[s["pairKey"]]["evidenceType"] != "inferred":
            bad("notInferredInIndex", s["pairKey"])
    # serving DB: evidence rows by pairKey, and the cells pointing at them
    db = sqlite3.connect(f"file:{serving_db}?mode=ro", uri=True)
    dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
    ev_by_pair: dict[str, list] = {}
    for eid, blob in db.execute("SELECT id, data FROM evidence"):
        row = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
        ev_by_pair.setdefault(row["pairKey"], []).append((eid, row))
    cells_by_ev = Counter(e for (e,) in db.execute("SELECT evidence_id FROM cells"))
    inferred_cells_db = db.execute("SELECT count(*) FROM cells WHERE evidence_type='inferred'").fetchone()[0]
    db.close()
    mapped, cells = 0, 0
    for s in selection:
        hits = ev_by_pair.get(s["pairKey"], [])
        if len(hits) != 1:
            bad(f"servingEvidenceRows={len(hits)}", s["pairKey"])
            continue
        eid, row = hits[0]
        j = jobs.get(s["pairKey"])
        if row.get("evidenceType") != "inferred":
            bad("servingNotInferred", s["pairKey"])
        if row.get("context") is None or digest(row["context"]) != s["contextHash"]:
            bad("servingContextDiffers", s["pairKey"])
        if j and run.prior(j)[0] != [row["outcome"]]:
            bad("servingOutcomeDiffersFromPrior", s["pairKey"])
        if j and cells_by_ev[eid] != j["displayedCells"]:
            bad("displayedCellsDiffer", s["pairKey"])
        mapped += 1
        cells += cells_by_ev[eid]
    return {"config": cfg["runId"], "runHash": C.run_hash(cfg), "selection": len(selection), "jobs": len(run.jobs),
            "jobOrientation": dict(Counter(j["orientation"] for j in run.jobs)),
            "mappedToServingEvidence": mapped, "servingCells": cells, "servingInferredCells": inferred_cells_db,
            "servingDb": {"path": str(serving_db), "sha256": sha256_bytes(Path(serving_db).read_bytes())},
            "problems": dict(problems), "examples": examples, "ok": not problems and mapped == len(selection) == len(run.jobs)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m aoe2x.matchups.inferred_2026")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--index", required=True)
    b.add_argument("--out", required=True)
    v = sub.add_parser("verify")
    v.add_argument("config")
    v.add_argument("--serving-db", default=str(REPO_ROOT / "data/golden/civ_matchups_first_pass.db"))
    v.add_argument("--index")
    a = p.parse_args(argv)
    if a.cmd == "build":
        report = build(Path(a.index), Path(a.out))
    else:
        report = verify(a.config, Path(a.serving_db), Path(a.index) if a.index else None)
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
