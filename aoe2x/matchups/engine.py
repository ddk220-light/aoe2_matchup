"""Pinned matchup engines: ENGINE.json, file verification, Node discovery.

An engine lives in ``aoe2x/matchups/engines/<engineId>/`` as a byte-for-byte
copy of the runtime files a campaign manifest lists (``runtimeFiles``), kept
under their original ``aoe2x/js_simulation/...`` relative paths so the
engine's own relative imports and fixture reads keep working. It is
deliberately *outside* ``aoe2x/js_simulation/src``: the live site hashes that
directory into its engine version.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from aoe2x.matchups.canonical import digest, sha256_bytes
from aoe2x.matchups.paths import ENGINES_DIR, NODE_DIR

ENGINE_SCHEMA = "aoe2-matchup-engine/v1"
DEFAULT_ENGINE = "frozen-civ-matchups-v3"
NODE_POLICIES = ("exact", "verified", "warn")

# The tick-cap lifting hook of RB:aoe2x/js_simulation/node/mismatch-validation-worker.mjs,
# recorded per engine so a later engine whose source text differs can declare its own.
CAMPAIGN_HOOKS = {
    "fight": {"module": "/aoe2x/js_simulation/src/fight.js",
              "target": "maxTicks: MAX_TICKS,",
              "replacement": "maxTicks: globalThis.__collisionValidationMaxTicks ?? MAX_TICKS,"},
    "world": {"module": "/aoe2x/js_simulation/src/combat/world.js",
              "capTarget": "const MAX_WORLD_TICKS = 9000;",
              "capReplacement": "const MAX_WORLD_TICKS = Number.MAX_SAFE_INTEGER;",
              "progressTarget": "  const publish = (current) => {"},
}


def engine_dir(engine_id: str = DEFAULT_ENGINE) -> Path:
    return ENGINES_DIR / engine_id


def load_engine_manifest(engine_id: str = DEFAULT_ENGINE) -> dict:
    path = engine_dir(engine_id) / "ENGINE.json"
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != ENGINE_SCHEMA:
        raise ValueError(f"{path}: unknown schema {manifest.get('schema')!r}")
    return manifest


def files_digest(files: list[dict]) -> str:
    return digest([{"path": f["path"], "sha256": f["sha256"]} for f in files])


def verify_engine(engine_id: str = DEFAULT_ENGINE, campaign_runtime_files: list[dict] | None = None) -> dict:
    """Check every pinned file against ENGINE.json (and optionally a campaign manifest).

    Returns a report; ``report["ok"]`` is False on any difference.
    """
    root = engine_dir(engine_id)
    manifest = load_engine_manifest(engine_id)
    problems = []
    listed = {f["path"] for f in manifest["files"]}
    for f in manifest["files"]:
        path = root / f["path"]
        if not path.is_file():
            problems.append(f"missing {f['path']}")
            continue
        data = path.read_bytes()
        if sha256_bytes(data) != f["sha256"]:
            problems.append(f"sha256 differs {f['path']}")
        if len(data) != f["bytes"]:
            problems.append(f"size differs {f['path']}")
    on_disk = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} - {"ENGINE.json"}
    for extra in sorted(on_disk - listed):
        if "__pycache__" not in extra:
            problems.append(f"unlisted file {extra}")
    if files_digest(manifest["files"]) != manifest["filesDigest"]:
        problems.append("filesDigest does not match the file list")
    campaign = None
    if campaign_runtime_files is not None:
        want = {f["path"]: f["sha256"] for f in campaign_runtime_files}
        have = {f["path"]: f["sha256"] for f in manifest["files"]}
        campaign = {"files": len(want), "matching": sum(have.get(p) == h for p, h in want.items()),
                    "missing": sorted(set(want) - set(have)), "extra": sorted(set(have) - set(want)),
                    "different": sorted(p for p, h in want.items() if p in have and have[p] != h)}
        if campaign["missing"] or campaign["extra"] or campaign["different"]:
            problems.append("engine differs from the campaign manifest runtimeFiles")
    return {"engineId": manifest["engineId"], "files": len(manifest["files"]),
            "bytes": sum(f["bytes"] for f in manifest["files"]), "ok": not problems,
            "problems": problems, "campaign": campaign}


def pin_engine(engine_id: str, rb, source_commit: str, campaign_manifest_path: str, *,
               physics_version: str, execution_version: str, description: str,
               engine_config: dict | None = None, write: bool = True) -> dict:
    """Copy a campaign's ``runtimeFiles`` from ``source_commit`` and write ENGINE.json.

    Every byte comes from git; each file must hash to the campaign manifest's value.
    Used once for ``frozen-civ-matchups-v3``; later engines (e.g. the 2026
    recovery variants) can be pinned beside it the same way.
    """
    raw = rb.show(campaign_manifest_path)
    campaign = json.loads(raw)
    root = engine_dir(engine_id)
    files = []
    for entry in sorted(campaign["runtimeFiles"], key=lambda f: f["path"]):
        data = rb.show(entry["path"], ref=source_commit)
        if sha256_bytes(data) != entry["sha256"]:
            raise ValueError(f"{source_commit}:{entry['path']} does not match the campaign manifest")
        files.append({"path": entry["path"], "sha256": entry["sha256"], "bytes": len(data)})
        if write:
            target = root / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    manifest = {
        "schema": ENGINE_SCHEMA,
        "engineId": engine_id,
        "description": description,
        "physicsVersion": physics_version,
        "executionVersion": execution_version,
        "source": {
            "branch": rb.ref.removeprefix("origin/"),
            "branchTip": rb.commit(),
            "commit": rb.resolve(source_commit),
            "campaignManifest": campaign_manifest_path,
            "campaignManifestSha256": sha256_bytes(raw),
            "campaignHash": campaign.get("campaignHash"),
            "campaignSourceCommit": campaign.get("sourceCommit"),
        },
        "engineConfig": engine_config,
        "simulationEnvironment": campaign.get("simulationEnvironment", {}),
        "node": {"pinned": campaign["nodeVersion"], "verified": []},
        "entry": "aoe2x/js_simulation/node/run-job.mjs",
        "hooks": CAMPAIGN_HOOKS,
        "maxSimulationTicks": campaign.get("policy", {}).get("maxSimulationTicks"),
        "files": files,
        "filesDigest": files_digest(files),
    }
    if write:
        (root / "ENGINE.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def find_node(explicit: str | None = None) -> str:
    """The Node binary: ``explicit``, else ``$MATCHUP_NODE``, else ``node`` on PATH."""
    candidate = explicit or os.environ.get("MATCHUP_NODE") or shutil.which("node")
    if not candidate:
        raise FileNotFoundError("no Node binary: pass --node or set MATCHUP_NODE")
    return candidate


def node_version(binary: str) -> str:
    return subprocess.run([binary, "--version"], capture_output=True, text=True, check=True).stdout.strip()


def run_battles(jobs_path: Path, results_path: Path, *, engine_id: str = DEFAULT_ENGINE,
                node: str | None = None, workers: int = 4, timeout_steps=(180, 600, 1800, 3600),
                node_policy: str = "verified", environment: dict | None = None,
                max_old_space_mb: int | None = 3072, progress_dir: Path | None = None) -> subprocess.CompletedProcess:
    """Run ``node aoe2x/matchups/node/run-battles.mjs`` on a jobs file (one JSON job per line)."""
    binary = find_node(node)
    command = [binary]
    if max_old_space_mb:
        command.append(f"--max-old-space-size={max_old_space_mb}")
    command += [str(NODE_DIR / "run-battles.mjs"), "--engine", str(engine_dir(engine_id)),
                "--jobs", str(jobs_path), "--out", str(results_path), "--workers", str(workers),
                "--timeout-steps", ",".join(str(s) for s in timeout_steps),
                "--node-policy", node_policy, "--environment", json.dumps(environment or {})]
    if progress_dir:
        command += ["--progress-dir", str(progress_dir)]
    return subprocess.run(command, text=True, capture_output=True)
