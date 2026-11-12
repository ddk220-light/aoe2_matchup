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


def cmd_reproduce_2026(args) -> int:
    from aoe2x.matchups import reproduce as RP
    rb = _rb(args)
    if args.compare:
        report = RP.compare(rb, Path(args.dir))
        _print({k: v for k, v in report.items() if k != "contexts"})
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

    p = sub.add_parser("reproduce-2026")
    p.add_argument("dir", help="working directory for the sample, configs and records (outside the repo)")
    p.add_argument("--per-stratum", type=int, default=3)
    p.add_argument("--compare", action="store_true", help="compare finished runs in DIR with the archived 2026 rows")
    p.set_defaults(func=cmd_reproduce_2026)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
