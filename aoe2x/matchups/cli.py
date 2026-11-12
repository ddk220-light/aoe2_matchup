"""``python -m aoe2x.matchups <command>``: the matchup rerun tooling (build steps 1-3).

Commands (names follow RERUN_SYSTEM_PROPOSAL.md section 5 where it defines them):

  verify-engine          check the pinned engine files (and, with RB, the campaign manifest)
  replay-check           re-run archived 2026 seeds and compare exactly            [needs RB + Node]
  import-2026            freeze the 2026 bundle, scenario set, orientation table   [needs RB]
  export-bundle          build a mechanics bundle from any reference DB
  compare-bundles        roster/mechanics differences between two bundles
  validate-config        validate a run config
  freeze                 verify a config's inputs and write <records>/manifest.json
  inventory              config + bundle -> physical battle contexts in <records>/inventory/
  check-inventory-2026   compare a config's inventory with RB adaptive/inventory.jsonl.gz [needs RB]
  import-results         2026 reviewed results -> compact result index             [needs RB]
  run                    run a config's inventory on the pinned engine (resumable)  [needs Node]
  supervise              keep the runner alive; restart after crashes; STOP file / SIGTERM
  status                 progress, rate, ETA, blocked contexts of a run
  unlock                 remove a stale runner lock (refuses while the owner lives)
  export                 deterministic reviewed-results snapshot of a run
  reproduce-2026         sample 2026 contexts into reproduction configs; compare  [needs RB]

Commands marked [needs RB] exit with status 0 and a "skipped" message when the
research branch is not available (exit 3 with --require-rb).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aoe2x.matchups import artifacts
from aoe2x.matchups.paths import CONFIGS_DIR, REPO_ROOT, runs_store

SKIPPED = 0


def _print(value) -> None:
    print(json.dumps(value, indent=2))


def _rb(args):
    from aoe2x.matchups.rbsource import ResearchBranch
    rb = ResearchBranch(getattr(args, "rb_ref", None))
    if not rb.available():
        message = (f"skipped: research branch {rb.ref!r} is not available "
                   "(git fetch origin simulations/civ-forecast-recovery-2026-11-10, or set MATCHUP_RB_REF)")
        print(message, file=sys.stderr)
        raise SystemExit(3 if getattr(args, "require_rb", False) else SKIPPED)
    return rb


def _config_path(value: str) -> Path:
    path = Path(value)
    if not path.exists() and (CONFIGS_DIR / f"{value}.json").exists():
        path = CONFIGS_DIR / f"{value}.json"
    return path


# -------------------------------------------------------------------- inputs

def load_inputs(cfg: dict) -> dict:
    """Bundle, scenario set, orientation table, engine manifest and setup hash for a config."""
    from aoe2x.matchups import bundle as B
    from aoe2x.matchups import config as C
    from aoe2x.matchups import engine as E
    from aoe2x.matchups import inventory as I
    from aoe2x.matchups.canonical import digest
    game = cfg["game"]
    if game.get("bundle"):
        bundle = B.load_bundle(C.resolve_path(game["bundle"], REPO_ROOT), game["bundleHash"])
    else:
        db = C.resolve_path(game["referenceDb"], REPO_ROOT)
        bundle = B.export_from_reference_db(db, rule=cfg.get("roster"), game_build=game["gameBuild"])
        if bundle["game"]["referenceDbSha256"] != game["referenceDbSha256"]:
            raise C.ConfigError(f"{db} has sha256 {bundle['game']['referenceDbSha256']}, "
                                f"config expects {game['referenceDbSha256']}")
    battle = cfg["battle"]
    scenario_set = B.load_scenario_set(C.resolve_path(battle["scenarioSet"], REPO_ROOT))
    if not scenario_set["setHash"].startswith(battle["scenarioSetHash"]):
        raise C.ConfigError(f"scenario set {scenario_set['setHash']} is not {battle['scenarioSetHash']}")
    orientation = None
    if battle["orientation"]["rule"] == "table":
        orientation = I.load_orientation(C.resolve_path(battle["orientation"]["table"], REPO_ROOT),
                                         battle["orientation"]["tableHash"])
    engine_manifest = E.load_engine_manifest(cfg["engine"]["id"])
    setup = C.setup_identity(cfg, engine_manifest, scenario_set["setHash"])
    return {"bundle": bundle, "scenarioSet": scenario_set, "orientation": orientation,
            "engine": engine_manifest, "setup": setup, "setupHash": digest(setup)}


def _header(cfg: dict, inputs: dict) -> dict:
    from aoe2x.matchups.config import config_hash, selection_hash
    return {"runId": cfg["runId"], "configHash": config_hash(cfg), "selectionHash": selection_hash(cfg),
            "bundleHash": inputs["bundle"]["bundleHash"],
            "scenarioSetHash": inputs["scenarioSet"]["setHash"],
            "orientationTableHash": (inputs["orientation"] or {}).get("tableHash"),
            "engineId": inputs["engine"]["engineId"], "engineFilesDigest": inputs["engine"]["filesDigest"],
            "setupHash": inputs["setupHash"]}


# ------------------------------------------------------------------ commands

def cmd_verify_engine(args) -> int:
    from aoe2x.matchups import engine as E
    campaign_files = None
    manifest = E.load_engine_manifest(args.engine)
    if args.against_campaign:
        rb = _rb(args)
        campaign_files = rb.json(manifest["source"]["campaignManifest"])["runtimeFiles"]
    report = E.verify_engine(args.engine, campaign_files)
    report["node"] = manifest["node"]
    _print(report)
    return 0 if report["ok"] else 1


def cmd_replay_check(args) -> int:
    from aoe2x.matchups import bundle as B
    from aoe2x.matchups import replay as R
    rb = _rb(args)
    bundle = B.load_bundle(artifacts.CAMPAIGN_2026_BUNDLE)
    scenarios = B.load_scenario_set(artifacts.FROZEN_SCENARIOS)
    out = Path(args.out) if args.out else runs_store() / "replay-checks"
    report = R.replay_check(rb, bundle, scenarios, node=args.node, workers=args.workers,
                            per_stratum=args.per_stratum, out_dir=out, engine_id=args.engine)
    summary = {k: report[k] for k in ("engineId", "node", "seeds", "identical", "allIdentical", "strata",
                                      "campaigns", "sampleDigest")}
    summary["differences"] = [c for c in report["checks"] if not c["identical"]]
    summary["report"] = str(out / f"replay-check-{report['node']['version']}.json")
    if args.record and report["allIdentical"]:
        summary["recorded"] = R.record_evidence(args.engine, report)
    _print(summary)
    return 0 if report["allIdentical"] else 1


def cmd_import_2026(args) -> int:
    from aoe2x.matchups import bundle as B
    from aoe2x.matchups import inventory as I
    from aoe2x.matchups.rbsource import ADAPTIVE
    rb = _rb(args)
    bundle, scenarios = B.import_campaign_2026(rb)
    adaptive_manifest = rb.json(f"{ADAPTIVE}/manifest.json")
    raw = rb.show(f"{ADAPTIVE}/inventory.jsonl.gz")
    from aoe2x.matchups.canonical import sha256_bytes
    if sha256_bytes(raw) != adaptive_manifest["matchupInventory"]["sha256"]:
        raise SystemExit("adaptive inventory does not match its manifest")
    reference = rb.jsonl(f"{ADAPTIVE}/inventory.jsonl.gz")
    table = I.orientation_table({r["pairKey"]: r["profileHashes"] for r in reference}, {
        "kind": "2026 adaptive inventory physical orientation",
        "path": f"{ADAPTIVE}/inventory.jsonl.gz", "sha256": sha256_bytes(raw),
        "campaignHash": adaptive_manifest["campaignHash"], "branchTip": rb.commit()})
    outputs = {artifacts.CAMPAIGN_2026_BUNDLE: bundle, artifacts.FROZEN_SCENARIOS: scenarios,
               artifacts.ADAPTIVE_ORIENTATION: table}
    import gzip
    report = {}
    status = 0
    for path, value in outputs.items():
        data = gzip.compress(B._json_bytes(value), compresslevel=9, mtime=0)
        same = path.exists() and path.read_bytes() == data
        if args.check:
            status |= 0 if same else 1
        else:
            B.write_json_gz(value, path)
        report[artifacts.rel(path)] = {"bytes": len(data), "identicalToCommitted": same,
                                       "hash": value.get("bundleHash") or value.get("setHash") or value.get("tableHash")}
    report["bundle"] = B.summarize_bundle(bundle)
    report["reversedOrientationPairs"] = len(table["reversed"])
    _print(report)
    return status


def cmd_export_bundle(args) -> int:
    from aoe2x.matchups import bundle as B
    rule = json.loads(args.roster_rule) if args.roster_rule else None
    bundle = B.export_from_reference_db(Path(args.reference_db), rule=rule, game_build=args.game_build,
                                        bundle_id=args.bundle_id, description=args.description or "")
    data = B.write_json_gz(bundle, Path(args.out))
    _print({**B.summarize_bundle(bundle), "out": args.out, "bytes": len(data)})
    return 0


def cmd_compare_bundles(args) -> int:
    from aoe2x.matchups import bundle as B
    a, b = B.load_bundle(Path(args.a)), B.load_bundle(Path(args.b))
    report = B.compare_bundles(a, b)
    report["changedMechanicsCount"] = len(report["changedMechanics"])
    report["a"], report["b"] = B.summarize_bundle(a), B.summarize_bundle(b)
    _print(report)
    return 0


def cmd_validate_config(args) -> int:
    from aoe2x.matchups import config as C
    try:
        cfg = C.load(_config_path(args.config))
    except C.ConfigError as error:
        print(f"invalid: {error}", file=sys.stderr)
        return 1
    _print({"valid": True, "runId": cfg["runId"], "configHash": C.config_hash(cfg),
            "records": str(C.records_dir(cfg))})
    return 0


def cmd_freeze(args) -> int:
    from aoe2x.matchups import config as C
    from aoe2x.matchups import engine as E
    from aoe2x.matchups.bundle import summarize_bundle
    cfg = C.load(_config_path(args.config))
    inputs = load_inputs(cfg)
    check = E.verify_engine(cfg["engine"]["id"])
    if not check["ok"]:
        _print(check)
        return 1
    manifest = {**_header(cfg, inputs), "config": cfg, "setup": inputs["setup"],
                "bundle": summarize_bundle(inputs["bundle"]), "engine": {
                    "engineId": inputs["engine"]["engineId"], "physicsVersion": inputs["engine"]["physicsVersion"],
                    "executionVersion": inputs["engine"]["executionVersion"], "node": inputs["engine"]["node"],
                    "files": check["files"]}}
    out = Path(args.out) if args.out else C.records_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if not cfg["game"].get("bundle"):
        from aoe2x.matchups.bundle import write_json_gz
        write_json_gz(inputs["bundle"], out / "mechanics-bundle.json.gz")
    _print({k: manifest[k] for k in ("runId", "configHash", "bundleHash", "setupHash", "engineId")} | {"out": str(out)})
    return 0


def cmd_inventory(args) -> int:
    from aoe2x.matchups import config as C
    from aoe2x.matchups import inventory as I
    cfg = C.load(_config_path(args.config))
    inputs = load_inputs(cfg)
    result = I.build(cfg, inputs["bundle"], inputs["scenarioSet"], inputs["orientation"], inputs["setupHash"])
    out = Path(args.out) if args.out else C.records_dir(cfg) / "inventory"
    summary = I.write(result, out, _header(cfg, inputs))
    _print({k: v for k, v in summary.items() if k not in ("scenarioHashes",)} | {"out": str(out)})
    return 0


def cmd_check_inventory_2026(args) -> int:
    from aoe2x.matchups import config as C
    from aoe2x.matchups import inventory as I
    from aoe2x.matchups.canonical import sha256_bytes
    from aoe2x.matchups.rbsource import ADAPTIVE
    rb = _rb(args)
    cfg = C.load(_config_path(args.config))
    inputs = load_inputs(cfg)
    result = I.build(cfg, inputs["bundle"], inputs["scenarioSet"], inputs["orientation"], inputs["setupHash"])
    raw = rb.show(f"{ADAPTIVE}/inventory.jsonl.gz")
    reference = rb.jsonl(f"{ADAPTIVE}/inventory.jsonl.gz")
    comparison = I.compare_with_reference(result["jobs"], reference)
    s = result["summary"]
    expected = {"variants": 555, "profiles": 374, "cells": 151223, "civilizationPairs": 1540,
                "profilePairs": 68916, "identityPairs": 45, "identityCells": 820, "contexts": 68871}
    report = {"config": cfg["runId"], "configHash": C.config_hash(cfg),
              "reference": {"path": f"{ADAPTIVE}/inventory.jsonl.gz", "sha256": sha256_bytes(raw),
                            "rows": len(reference), "branchTip": rb.commit()},
              "counts": {k: s[k] for k in expected}, "expectedFromDocs": expected,
              "countsMatchDocs": all(s[k] == v for k, v in expected.items()),
              "scenarioHashes": s["scenarioHashes"], "orientation": s["orientation"],
              "pairKeysDigest": s["pairKeysDigest"], "contextsDigest": s["contextsDigest"],
              "comparison": comparison}
    if args.write_receipt:
        artifacts.INVENTORY_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        artifacts.INVENTORY_RECEIPT.write_text(json.dumps(report, indent=2) + "\n")
    _print(report)
    return 0 if comparison["identical"] and report["countsMatchDocs"] else 1


def cmd_import_results(args) -> int:
    from aoe2x.matchups import config as C
    from aoe2x.matchups import inventory as I
    from aoe2x.matchups import results as RES
    rb = _rb(args)
    cfg = C.load(_config_path(args.config))
    inputs = load_inputs(cfg)
    inv = I.build(cfg, inputs["bundle"], inputs["scenarioSet"], inputs["orientation"], inputs["setupHash"])
    index, report = RES.import_2026(rb, inv, inputs, serving_db=None if args.no_serving_check else
                                    REPO_ROOT / "data/golden/civ_matchups_first_pass.db")
    out = Path(args.out) if args.out else runs_store() / "baselines" / "campaign-2026" / "result-index.jsonl.gz"
    receipt = RES.write_index(index, out, report)
    # The physical orientation of every published measured/inferred result: a run whose
    # inventory uses this table can reuse all reusable 2026 results without reversing any.
    table = I.orientation_table({r["pairKey"]: r["context"]["profiles"] for r in index
                                 if r["context"] is not None and r["evidenceType"] != "identity"},
                                {"kind": "2026 published result orientation (serving DB contexts)",
                                 "resultIndexSha256": receipt["index"]["sha256"], "branchTip": receipt["rb"]["tip"]})
    receipt["publishedOrientation"] = {"tableHash": table["tableHash"], "reversedFromSorted": len(table["reversed"]),
                                       "pairs": table["pairs"]}
    if args.write_receipt:
        from aoe2x.matchups.bundle import write_json_gz
        write_json_gz(table, artifacts.PUBLISHED_ORIENTATION)
        artifacts.RESULT_INDEX_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        artifacts.RESULT_INDEX_RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n")
    _print(receipt | {"out": str(out)})
    return 0 if receipt["mapping"]["unmapped"] == 0 and receipt["mapping"]["ambiguous"] == 0 else 1


def _run_records(args, cfg):
    from aoe2x.matchups import config as C
    return Path(args.records) if getattr(args, "records", None) else C.records_dir(cfg)


def cmd_run(args) -> int:
    from aoe2x.matchups import config as C
    from aoe2x.matchups import runner as RN
    try:
        cfg = C.load(_config_path(args.config))
        run = RN.Run(cfg, records=_run_records(args, cfg), force=args.force)
    except (C.ConfigError, RN.RunError) as error:
        print(f"run error: {error}", file=sys.stderr)
        return RN.EXIT_INTEGRITY
    if args.dry_run:
        _print(run.plan())
        return 0
    return RN.Runner(run, workers=args.workers, node=args.node, retry_blocked=args.retry_blocked).execute()


def cmd_supervise(args) -> int:
    from aoe2x.matchups import config as C
    from aoe2x.matchups.supervisor import Supervisor
    path = _config_path(args.config)
    cfg = C.load(path)
    extra = []
    for flag, value in (("--records", args.records), ("--workers", args.workers), ("--node", args.node)):
        if value:
            extra += [flag, str(value)]
    if args.force:
        extra.append("--force")
    return Supervisor(path.resolve(), _run_records(args, cfg), runner_args=extra, heartbeat=args.heartbeat,
                      max_failures=args.max_failures).run()


def cmd_status(args) -> int:
    from aoe2x.matchups import config as C
    from aoe2x.matchups import status as S
    cfg = C.load(_config_path(args.config))
    report = S.report(_run_records(args, cfg))
    if args.json:
        _print(report)
    else:
        print(S.render(report))
    return 0


def cmd_unlock(args) -> int:
    from aoe2x.matchups import config as C
    from aoe2x.matchups import journal as J
    cfg = C.load(_config_path(args.config))
    lock = J.RunnerLock(_run_records(args, cfg) / ".runner.lock")
    try:
        _print(lock.clear_stale())
    except J.LockBusy as busy:
        print(f"refused: {busy}", file=sys.stderr)
        return 1
    return 0


def cmd_export(args) -> int:
    from aoe2x.matchups import config as C
    from aoe2x.matchups import export as X
    from aoe2x.matchups import runner as RN
    cfg = C.load(_config_path(args.config))
    records = _run_records(args, cfg)
    try:
        run = RN.Run(cfg, records=records)
        out = Path(args.out) if args.out else records / "export"
        manifest = X.write(run, out)
    except RN.RunError as error:
        print(f"export error: {error}", file=sys.stderr)
        return 1
    _print({"out": str(out), "snapshotHash": manifest["snapshotHash"], "complete": manifest["complete"],
            "counts": manifest["counts"], "files": manifest["files"]})
    return 0


def default_index_ref(cfg: dict | None) -> tuple[Path, str | None]:
    """The result index a build/plan uses: the config's ``baselineResults``, else the 2026 index
    in the runs store (checked against the committed receipt)."""
    from aoe2x.matchups import config as C
    ref = (cfg or {}).get("selection", {}).get("baselineResults")
    if ref:
        return C.resolve_path(ref["index"], REPO_ROOT), ref["sha256"]
    receipt = json.loads(artifacts.RESULT_INDEX_RECEIPT.read_text())
    return runs_store() / "baselines" / "campaign-2026" / "result-index.jsonl.gz", receipt["index"]["sha256"]


def cmd_build_db(args) -> int:
    from aoe2x.matchups import config as C
    from aoe2x.matchups import servingdb as S
    cfg = C.load(_config_path(args.config))
    inputs = load_inputs(cfg)
    index_path, index_sha = default_index_ref(cfg)
    if args.index:
        index_path, index_sha = Path(args.index), args.index_sha256
    if not args.no_index and not index_path.exists():
        print(f"build-db: result index {index_path} is missing (python -m aoe2x.matchups import-results)",
              file=sys.stderr)
        return 2
    try:
        index, sha = ([], None) if args.no_index else S.load_index(index_path, index_sha)
        snapshots = [S.load_snapshot(Path(d)) for d in args.snapshot]
        previous = S.read_db(Path(args.previous_db)) if args.previous_db else None
        record = S.build(bundle=inputs["bundle"], scenario_set=inputs["scenarioSet"], battle=cfg["battle"],
                         setup_hash=inputs["setupHash"], engine_files_digest=inputs["engine"]["filesDigest"],
                         index=index, index_sha256=sha, snapshots=snapshots, out=Path(args.out), previous=previous,
                         costs=args.costs, costs_db=Path(args.costs_db), carry_unsimulated=args.carry_unsimulated,
                         max_bytes=int(args.max_mib * 1024 * 1024))
    except S.BuildError as error:
        print(f"build-db error: {error}", file=sys.stderr)
        return 1
    _print({k: record[k] for k in ("out", "bytes", "sha256", "counts", "resultIndex", "snapshots", "previousDb")})
    return 0


def cmd_diff_bundles(args) -> int:
    from aoe2x.matchups import bundle as B
    from aoe2x.matchups import config as C
    from aoe2x.matchups import plan as P
    from aoe2x.matchups import servingdb as S
    old, new = B.load_bundle(Path(args.old)), B.load_bundle(Path(args.new))
    cfg_path = _config_path(args.config)
    raw = json.loads(cfg_path.read_text())
    cfg = C.load(cfg_path)
    scenario_set = B.load_scenario_set(C.resolve_path(cfg["battle"]["scenarioSet"], REPO_ROOT))
    index_path, index_sha = default_index_ref(cfg)
    if args.index:
        index_path, index_sha = Path(args.index), args.index_sha256
    index, sha = S.load_index(index_path, index_sha)
    plan = P.build_plan(old, new, scenario_set, cfg["battle"], index, workers=args.workers,
                        resimulate_kept=args.resimulate_kept)
    if args.out:
        published = {"rule": "table", "table": artifacts.rel(artifacts.PUBLISHED_ORIENTATION),
                     "tableHash": json.loads(json.dumps(B.read_json_any(artifacts.PUBLISHED_ORIENTATION)))["tableHash"]}
        written = P.write_outputs(plan, Path(args.out), old=old, new=new, index=index, with_priors=args.priors,
                                  base_config=raw if args.run_id else None, new_bundle_path=str(Path(args.new).resolve()),
                                  index_ref={"index": str(index_path.resolve()), "sha256": sha}, run_id=args.run_id,
                                  orientation=published)
        plan["written"] = {"dir": str(Path(args.out).resolve()), "files": written}
    if args.json:
        _print({k: v for k, v in plan.items() if k not in ("_pairs", "schedule")} |
               {"scheduleSample": plan["schedule"][:5]})
    else:
        print(P.render(plan))
        if plan.get("written"):
            print(f"written: {plan['written']['dir']} ({', '.join(plan['written']['files'])})")
    return 0


def cmd_archive(args) -> int:
    from aoe2x.matchups import archive as AR
    if args.rb_2026 or args.triage:
        rb = _rb(args)
        if args.triage:
            t = AR.triage_rb(rb.ref)
            if args.json:
                _print(t)
            else:
                print("| Campaign | Kind | Class | Archived | Files | MB |\n|---|---|---|---|---:|---:|")
                for r in t["rows"]:
                    print(f"| {r['campaign']} | {r['kind']} | {r['class']} | {'yes' if r['archived'] else 'no'} | "
                          f"{r['files']:,} | {r['bytes'] / 1e6:,.2f} |")
                print({k: round(v / 1e6, 1) for k, v in t["totals"].items()})
            return 0
        index = None
        if args.with_index:
            index, _ = default_index_ref(None)
        side = AR.archive_rb(rb.ref, rb.commit(), Path(args.out), with_index=index)
        if args.write_receipt:
            receipt = {k: v for k, v in side.items() if k != "files"}
            receipt["files"] = len(side["files"])
            artifacts.RECORDS_ARCHIVE_RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    else:
        if not args.records:
            print("archive: give a records directory or --rb-2026", file=sys.stderr)
            return 2
        side = AR.archive_run(Path(args.records), Path(args.out), Path(args.config) if args.config else None)
    _print({"archive": side["archive"], "totals": side["totals"], "skippedBytes": side.get("skippedBytes")})
    return 0


def cmd_audit_db(args) -> int:
    from aoe2x.matchups import audit as AU
    from aoe2x.matchups import config as C
    from aoe2x.matchups import servingdb as S
    verification = comparison = api = None
    previous = S.read_db(Path(args.previous_db)) if args.previous_db else None
    if args.config:
        cfg = C.load(_config_path(args.config))
        inputs = load_inputs(cfg)
        index_path, index_sha = default_index_ref(cfg)
        if args.index:
            index_path, index_sha = Path(args.index), args.index_sha256
        index, sha = ([], None) if args.no_index else S.load_index(index_path, index_sha)
        snapshots = [S.load_snapshot(Path(d)) for d in args.snapshot]
        verification = AU.verify(Path(args.db), bundle=inputs["bundle"], scenario_set=inputs["scenarioSet"],
                                 battle=cfg["battle"], setup_hash=inputs["setupHash"],
                                 engine_files_digest=inputs["engine"]["filesDigest"], index=index, index_sha256=sha,
                                 snapshots=snapshots, previous=previous)
    compare_with = args.compare or args.previous_db
    if compare_with:
        old = previous if compare_with == args.previous_db else S.read_db(Path(compare_with))
        comparison = AU.compare(old, S.read_db(Path(args.db)))
        if args.api:
            from aoe2x.matchups import apicheck
            api = apicheck.compare(Path(compare_with), Path(args.db))
    if verification is None and comparison is None:
        print("audit-db: give --config (verify against inputs) and/or --previous-db/--compare (compare)",
              file=sys.stderr)
        return 2
    text = AU.summary_markdown(verification, comparison, api)
    if args.md:
        Path(args.md).write_text(text)
    if args.json:
        Path(args.json).write_text(json.dumps({"verification": verification, "comparison": comparison, "api": api},
                                              indent=2) + "\n")
    print(text)
    return 0 if verification is None or verification["ok"] else 1


def cmd_reproduce_2026(args) -> int:
    from aoe2x.matchups import reproduce as RP
    rb = _rb(args)
    if args.compare:
        report = RP.compare(rb, Path(args.dir))
        _print({k: v for k, v in report.items() if k != "problems"} | {"firstProblems": report["problems"][:5]})
        return 0 if report["mismatches"] == 0 and report["missing"] == 0 else 1
    _print(RP.prepare(rb, Path(args.dir), per_stratum=args.per_stratum))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m aoe2x.matchups", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rb-ref", help="research branch ref (default origin/simulations/civ-forecast-recovery-2026-11-10)")
    parser.add_argument("--require-rb", action="store_true", help="fail (exit 3) instead of skipping without RB")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("verify-engine")
    p.add_argument("--engine", default="frozen-civ-matchups-v3")
    p.add_argument("--against-campaign", action="store_true", help="also compare with the campaign manifest on RB")
    p.set_defaults(func=cmd_verify_engine)

    p = sub.add_parser("replay-check")
    p.add_argument("--engine", default="frozen-civ-matchups-v3")
    p.add_argument("--node", help="Node binary (default $MATCHUP_NODE or node on PATH)")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--per-stratum", type=int, default=3, help="seeds per stratum (20 strata -> 60 seeds at 3)")
    p.add_argument("--out", help="report directory (default $MATCHUP_RUNS_STORE/replay-checks)")
    p.add_argument("--record", action="store_true", help="record a fully identical result in ENGINE.json node.verified")
    p.set_defaults(func=cmd_replay_check)

    p = sub.add_parser("import-2026")
    p.add_argument("--check", action="store_true", help="only verify the committed files are byte-identical")
    p.set_defaults(func=cmd_import_2026)

    p = sub.add_parser("export-bundle")
    p.add_argument("--reference-db", required=True)
    p.add_argument("--game-build", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--bundle-id")
    p.add_argument("--description")
    p.add_argument("--roster-rule", help="JSON object overriding ranking-roster-v1 fields")
    p.set_defaults(func=cmd_export_bundle)

    p = sub.add_parser("compare-bundles")
    p.add_argument("a")
    p.add_argument("b")
    p.set_defaults(func=cmd_compare_bundles)

    for name, func in (("validate-config", cmd_validate_config), ("freeze", cmd_freeze), ("inventory", cmd_inventory)):
        p = sub.add_parser(name)
        p.add_argument("config", help="config path or name under aoe2x/matchups/configs/")
        if name != "validate-config":
            p.add_argument("--out", help="output directory (default: the config's output.records)")
        p.set_defaults(func=func)

    p = sub.add_parser("check-inventory-2026")
    p.add_argument("--config", default="full-2026-reproduction")
    p.add_argument("--write-receipt", action="store_true", help=f"write {artifacts.rel(artifacts.INVENTORY_RECEIPT)}")
    p.set_defaults(func=cmd_check_inventory_2026)

    p = sub.add_parser("import-results")
    p.add_argument("--config", default="full-2026-reproduction")
    p.add_argument("--out", help="index path (default $MATCHUP_RUNS_STORE/baselines/campaign-2026/result-index.jsonl.gz)")
    p.add_argument("--no-serving-check", action="store_true", help="skip the cross-check with data/golden/civ_matchups_first_pass.db")
    p.add_argument("--write-receipt", action="store_true", help=f"write {artifacts.rel(artifacts.RESULT_INDEX_RECEIPT)}")
    p.set_defaults(func=cmd_import_results)

    def run_options(p, *, force=True):
        p.add_argument("config", help="config path or name under aoe2x/matchups/configs/")
        p.add_argument("--records", help="records directory (default: the config's output.records)")
        if force:
            p.add_argument("--workers", type=int, help="override execution.workers")
            p.add_argument("--node", help="Node binary (default $MATCHUP_NODE or node on PATH)")
            p.add_argument("--force", action="store_true", help="re-run contexts the baseline index already has")

    p = sub.add_parser("run")
    run_options(p)
    p.add_argument("--retry-blocked", action="store_true", help="give blocked contexts a fresh set of watchdog steps")
    p.add_argument("--dry-run", action="store_true", help="print what would be scheduled (reused vs new); run nothing")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("supervise")
    run_options(p)
    p.add_argument("--heartbeat", type=float, default=30.0, help="seconds between supervisor.json updates")
    p.add_argument("--max-failures", type=int, default=5, help="give up after this many crashes in a row without progress")
    p.set_defaults(func=cmd_supervise)

    p = sub.add_parser("status")
    run_options(p, force=False)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("unlock")
    run_options(p, force=False)
    p.set_defaults(func=cmd_unlock)

    p = sub.add_parser("export")
    run_options(p, force=False)
    p.add_argument("--out", help="snapshot directory (default <records>/export)")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("build-db", help="build the advisor serving DB from a result index + run snapshots")
    p.add_argument("config", help="run config whose bundle (roster) and battle setup the DB is for")
    p.add_argument("--out", required=True, help="output DB path (write a scratch path; copying it to "
                                                "data/golden/ is the release step)")
    p.add_argument("--index", help="result index (default: the config's baselineResults, else the 2026 index)")
    p.add_argument("--index-sha256", help="expected sha256 of --index")
    p.add_argument("--snapshot", action="append", default=[], help="an `export` snapshot dir (repeatable, in order)")
    p.add_argument("--no-index", action="store_true",
                   help="no baseline: every result comes from the snapshots (a full run under new conditions)")
    p.add_argument("--previous-db", help="the currently published DB: keeps unit/evidence ids stable and is "
                                         "the source of kept results for blocked/unsimulated cells")
    p.add_argument("--costs", choices=("reference-db", "bundle"), default="reference-db",
                   help="where units.data.costs come from (2026 builder: the reference DB)")
    p.add_argument("--costs-db", default=str(REPO_ROOT / "data/golden/aoe2_reference_simulation.db"))
    p.add_argument("--carry-unsimulated", action="store_true",
                   help="cells of pairs without any result keep the previous release's result (flag 4) "
                        "instead of failing")
    p.add_argument("--max-mib", type=float, default=95.0, help="refuse to write a DB of this size or more")
    p.set_defaults(func=cmd_build_db)

    p = sub.add_parser("diff-bundles", help="units added/removed/changed between two bundles and the rerun plan")
    p.add_argument("old", help="the bundle the baseline results were simulated with")
    p.add_argument("new", help="the new bundle")
    p.add_argument("--config", default="full-2026-reproduction",
                   help="config giving the battle setup (and default result index); with --run-id also the "
                        "template of the generated run config")
    p.add_argument("--index", help="result index (default: the config's baselineResults, else the 2026 index)")
    p.add_argument("--index-sha256")
    p.add_argument("--workers", type=int, default=4, help="workers for the wall-clock estimate")
    p.add_argument("--resimulate-kept", action="store_true",
                   help="also schedule pairs whose stored result is rule-inferred or from another engine")
    p.add_argument("--out", help="write plan.json, plan.md and contexts.json (selection.contexts) here")
    p.add_argument("--run-id", help="with --out: also write config.json, a ready run config for the schedule")
    p.add_argument("--priors", action="store_true",
                   help="with --out: write priors.jsonl.gz (previous outcomes of the same cells) and use it in "
                        "config.json (one-seed shortcut; owner default is no prior)")
    p.add_argument("--json", action="store_true", help="print JSON instead of the readable plan")
    p.set_defaults(func=cmd_diff_bundles)

    p = sub.add_parser("archive", help="essential run records (or the 2026 campaigns) as one deterministic tarball")
    p.add_argument("records", nargs="?", help="a run's records directory")
    p.add_argument("--out", help="archive path (.tar.gz); a <out>.manifest.json sidecar is written next to it")
    p.add_argument("--config", help="also store this run config in the archive")
    p.add_argument("--rb-2026", action="store_true", help="archive the essential 2026 records from RB  [needs RB]")
    p.add_argument("--with-index", action="store_true", help="with --rb-2026: include the 2026 result index")
    p.add_argument("--triage", action="store_true", help="print the RB records triage table (no archive)  [needs RB]")
    p.add_argument("--write-receipt", action="store_true",
                   help="with --rb-2026: write aoe2x/matchups/baselines/campaign-2026/records-archive.json")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_archive)

    p = sub.add_parser("audit-db", help="verify a built serving DB against its inputs; compare with the published DB")
    p.add_argument("db", help="the built serving DB")
    p.add_argument("--config", help="run config the DB was built for (enables verification against inputs)")
    p.add_argument("--index", help="result index used by build-db (default as build-db)")
    p.add_argument("--index-sha256")
    p.add_argument("--snapshot", action="append", default=[], help="the snapshot dirs given to build-db, in order")
    p.add_argument("--no-index", action="store_true", help="build-db was given --no-index")
    p.add_argument("--previous-db", help="the previous DB given to build-db; also the default --compare target")
    p.add_argument("--compare", help="compare with this DB (default --previous-db)")
    p.add_argument("--api", action="store_true", help="also compare the advisor API responses byte for byte "
                                                     "and the export component version")
    p.add_argument("--md", help="write the markdown release summary here")
    p.add_argument("--json", help="write the full report as JSON here")
    p.set_defaults(func=cmd_audit_db)

    p = sub.add_parser("reproduce-2026")
    p.add_argument("dir", help="working directory for the sample, configs and records (outside the repo)")
    p.add_argument("--per-stratum", type=int, default=3)
    p.add_argument("--compare", action="store_true", help="compare finished runs in DIR with the archived 2026 rows")
    p.set_defaults(func=cmd_reproduce_2026)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
