# Self-Contained Calibration Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the complete standard-unit calibration workflow into `D:/AI/aoe2_matchup/calibration`, rebuild all active tape measurements exclusively from `aoe2_golden_STANDARD_UNITS_FINAL.zip`, and stop active calibration code from reading or writing the historical `D:/AI/aoe2_golden` workspace.

**Architecture:** Keep both simulation engines in their existing production locations. Add a small Python path contract and a matching Node path contract for non-production calibration tools, keep the canonical ZIP and raw run data Git-ignored, and track only the source lock plus compact FINAL-derived fixtures and current reports. Rebuild into staging and publish atomically so stale recordings cannot survive by append.

**Tech Stack:** Python 3, pathlib, dataclasses, hashlib, zipfile, pytest, Node.js ESM, node:test, JSON, Git.

## Global Constraints

- Sole tape authority: `calibration/source/aoe2_golden_STANDARD_UNITS_FINAL.zip`.
- Required SHA-256: `31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9`.
- Required corpus: 339 recordings, 339 truth cards, 91 unordered matchups, 14 standard units.
- The source ZIP, extracted tape streams, raw per-seed runs, and `.scratch/calibration/` are Git-ignored.
- No active calibration code may fall back to Downloads, `D:/AI/aoe2_golden`, or `data/calibration`.
- `D:/AI/aoe2_golden` is not modified or deleted.
- Do not modify `apps/website/static/js/engine/` or `aoe2x/sim/`.
- Do not add, remove, rename, or reinterpret simulation scales. In particular, `tape`, `equal_count`, `30v30`, and `3k` retain their existing meanings.
- Winner, surviving HP percentage, duration, hits, survivors, and medians are regenerated from FINAL; no old tape-derived value is copied forward.
- Preserve unrelated dirty-worktree changes. Every commit stages only files named by its task.
- No deployment, production database write, push to `main`, or other production action is in scope.

## File Structure

### New files

- `aoe2x/calibration/paths.py` — single Python definition of workspace paths, with explicit test override.
- `aoe2x/calibration/source.py` — source-lock parsing and SHA-256/corpus validation.
- `aoe2x/calibration/rebuild.py` — clean staging rebuild and atomic fixture publication.
- `tools/simjs/calibration_paths.mjs` — Node path definitions derived from repository root.
- `tests/test_calibration_paths.py` — Python path and source verification contract.
- `tests/test_calibration_rebuild.py` — clean rebuild, no-append, and provenance contract.
- `tests/js/calibration_paths.test.mjs` — Node path contract.
- `calibration/README.md` — sole active workflow entry point.
- `calibration/source/source_of_truth.json` — tracked source identity.
- `calibration/docs/TAPE_SOURCE_OF_TRUTH.md` — current corpus policy and audit.

### Moved active fixtures

- `data/calibration/manifest.json` → `calibration/fixtures/manifest.json`
- `data/calibration/truth/` → `calibration/fixtures/truth/`
- `data/calibration/spawns.json` → `calibration/fixtures/spawns.json`
- `data/calibration/combat_dicts.json` → `calibration/fixtures/combat_dicts.json`
- `data/calibration/matchups.json` → `calibration/fixtures/matchups.json`
- `data/calibration/fight_sets.json` → `calibration/fixtures/fight_sets.json`

### Removed from the active tree

- `data/calibration/runs/` — mixed historical reports; do not migrate.
- `data/calibration/analysis/` — old tape-derived analysis; do not migrate.
- `docs/calibration/*.md` — old measurement documents; replace only the two current docs named above.
- `data/calibration/` — remove after all active fixtures and consumers move.

### Modified calibration code and tests

- `.gitignore`
- `aoe2x/calibration/ingest.py`
- `aoe2x/calibration/extract.py`
- `aoe2x/calibration/filters.py`
- `aoe2x/calibration/score.py`
- `tools/simjs/calib_runner.mjs`
- `tools/simjs/dump_calib_dicts.py`
- `tools/simjs/dump_calib_spawns.py`
- retained calibration diagnostics listed in Task 7 that currently default to external paths
- `tests/test_calibration_ingest.py`
- `tests/test_calibration_extract.py`
- `tests/test_calibration_filters.py`
- `tests/test_calibration_score.py`
- `tests/test_margin_score.py`
- `tests/test_tape_plan.py`
- `tests/test_tape_rig_js.py`
- `tests/js/calib_runner.test.mjs`
- tape-derived comments in `tests/js/engine/*.test.mjs`
- `AGENTS.md`, `CLAUDE.md`, and `gemini.md`

---

### Task 1: Establish the project-local path contract

**Files:**
- Create: `aoe2x/calibration/paths.py`
- Create: `tests/test_calibration_paths.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `CalibrationPaths` frozen dataclass.
- Produces: `workspace_paths(root: Path | None = None) -> CalibrationPaths`.
- Produces fields: `root`, `source_dir`, `source_zip`, `source_lock`, `tapes_dir`, `fixtures_dir`, `manifest`, `truth_dir`, `spawns`, `combat_dicts`, `matchups`, `fight_sets`, `runs_dir`, `reports_dir`, `docs_dir`, `scratch_dir`.
- Default root: `<repo>/calibration`; tests pass an explicit root and never mutate global environment variables.

- [ ] **Step 1: Record the production-engine file-hash baseline**

Create `.scratch/calibration/production-engine-baseline.json` from every file under `apps/website/static/js/engine/` and `aoe2x/sim/`. Store repository-relative path plus SHA-256, sorted by path. This ignored baseline is the comparison authority because the worktree was dirty before the migration.

```powershell
$repo = (Resolve-Path '.').Path
$roots = @('apps\website\static\js\engine', 'aoe2x\sim')
$rows = foreach ($root in $roots) {
    Get-ChildItem -LiteralPath (Join-Path $repo $root) -File -Recurse |
        Sort-Object FullName |
        ForEach-Object {
            [pscustomobject]@{
                path = $_.FullName.Substring($repo.Length + 1).Replace('\', '/')
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
            }
        }
}
New-Item -ItemType Directory -Path '.scratch\calibration' -Force | Out-Null
$rows | ConvertTo-Json | Set-Content -LiteralPath '.scratch\calibration\production-engine-baseline.json' -Encoding UTF8
```

- [ ] **Step 2: Write the failing path tests**

```python
from pathlib import Path

from aoe2x.calibration.paths import workspace_paths


def test_default_workspace_is_inside_repo():
    p = workspace_paths()
    assert p.root == Path(__file__).resolve().parents[1] / "calibration"
    assert p.source_zip == p.root / "source" / "aoe2_golden_STANDARD_UNITS_FINAL.zip"
    assert p.manifest == p.root / "fixtures" / "manifest.json"
    assert p.runs_dir == p.root / "runs"
    assert p.scratch_dir == Path(__file__).resolve().parents[1] / ".scratch" / "calibration"


def test_explicit_workspace_override_is_closed_over_one_root(tmp_path):
    p = workspace_paths(tmp_path / "workspace")
    assert p.root == (tmp_path / "workspace").resolve()
    for child in (
        p.source_dir, p.tapes_dir, p.fixtures_dir, p.truth_dir,
        p.runs_dir, p.reports_dir, p.docs_dir, p.scratch_dir,
    ):
        assert child.is_relative_to(p.root)
```

- [ ] **Step 3: Run the tests and verify import failure**

Run:

```powershell
python -m pytest tests/test_calibration_paths.py -q -p no:cacheprovider
```

Expected: FAIL because `aoe2x.calibration.paths` does not exist.

- [ ] **Step 4: Implement the immutable path object**

```python
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ZIP_NAME = "aoe2_golden_STANDARD_UNITS_FINAL.zip"


@dataclass(frozen=True)
class CalibrationPaths:
    root: Path
    source_dir: Path
    source_zip: Path
    source_lock: Path
    tapes_dir: Path
    fixtures_dir: Path
    manifest: Path
    truth_dir: Path
    spawns: Path
    combat_dicts: Path
    matchups: Path
    fight_sets: Path
    runs_dir: Path
    reports_dir: Path
    docs_dir: Path
    scratch_dir: Path


def workspace_paths(root: Path | None = None) -> CalibrationPaths:
    base = (root or REPO_ROOT / "calibration").resolve()
    source = base / "source"
    fixtures = base / "fixtures"
    scratch = base / ".scratch" if root is not None else REPO_ROOT / ".scratch" / "calibration"
    return CalibrationPaths(
        root=base,
        source_dir=source,
        source_zip=source / SOURCE_ZIP_NAME,
        source_lock=source / "source_of_truth.json",
        tapes_dir=base / "tapes",
        fixtures_dir=fixtures,
        manifest=fixtures / "manifest.json",
        truth_dir=fixtures / "truth",
        spawns=fixtures / "spawns.json",
        combat_dicts=fixtures / "combat_dicts.json",
        matchups=fixtures / "matchups.json",
        fight_sets=fixtures / "fight_sets.json",
        runs_dir=base / "runs",
        reports_dir=base / "reports",
        docs_dir=base / "docs",
        scratch_dir=scratch,
    )
```

- [ ] **Step 5: Add precise ignore rules**

Append exactly:

```gitignore
# Local standard-unit calibration inputs and generated outcomes.
/calibration/source/*.zip
/calibration/tapes/
/calibration/runs/
/.scratch/calibration/
```

Do not ignore `calibration/source/source_of_truth.json`, fixtures, reports, or docs.

- [ ] **Step 6: Run path tests and Git-ignore checks**

```powershell
python -m pytest tests/test_calibration_paths.py -q -p no:cacheprovider
git check-ignore calibration/source/example.zip calibration/tapes/example calibration/runs/example .scratch/calibration/example
```

Expected: 2 tests pass; all four sample paths are reported ignored.

- [ ] **Step 7: Commit only Task 1 files**

```powershell
git add -- .gitignore aoe2x/calibration/paths.py tests/test_calibration_paths.py
git commit -m "calibration: define project-local workspace paths"
```

### Task 2: Lock and verify the sole FINAL archive

**Files:**
- Create: `aoe2x/calibration/source.py`
- Create: `calibration/source/source_of_truth.json`
- Modify: `tests/test_calibration_paths.py`

**Interfaces:**
- Consumes: `CalibrationPaths`, `workspace_paths()` from Task 1.
- Produces: `CalibrationSourceError(RuntimeError)`.
- Produces: `load_source_lock(paths: CalibrationPaths) -> dict[str, object]`.
- Produces: `verify_source_archive(paths: CalibrationPaths) -> dict[str, object]`.
- Produces: `main(argv: Sequence[str] | None = None) -> int`, supporting `--workspace-root PATH` and printing normalized filename, hash, and counts.
- Verification checks filename, SHA-256, `recordings == 339`, `unordered_matchups == 91`, and `standard_units == 14`.

- [ ] **Step 1: Write failing source-lock tests**

```python
import hashlib
import json
from zipfile import ZipFile

import pytest

from aoe2x.calibration.paths import workspace_paths
import aoe2x.calibration.source as source_mod
from aoe2x.calibration.source import CalibrationSourceError, verify_source_archive


def _write_lock(paths, sha256):
    paths.source_dir.mkdir(parents=True)
    paths.source_lock.write_text(json.dumps({
        "archive": paths.source_zip.name,
        "sha256": sha256,
        "recordings": 339,
        "unordered_matchups": 91,
        "standard_units": 14,
    }), encoding="utf-8")


def test_verify_source_archive_accepts_exact_locked_zip(tmp_path, monkeypatch):
    paths = workspace_paths(tmp_path / "calibration")
    paths.source_dir.mkdir(parents=True)
    with ZipFile(paths.source_zip, "w") as zf:
        zf.writestr("standard_units/decoded/f.meta.json", "{}")
    digest = hashlib.sha256(paths.source_zip.read_bytes()).hexdigest().upper()
    monkeypatch.setattr(source_mod, "FINAL_SHA256", digest)
    _write_lock(paths, digest)
    assert verify_source_archive(paths)["sha256"] == digest


@pytest.mark.parametrize("condition", ["missing", "wrong_hash", "wrong_name", "wrong_counts"])
def test_verify_source_archive_fails_closed(tmp_path, condition):
    paths = workspace_paths(tmp_path / "calibration")
    paths.source_dir.mkdir(parents=True)
    if condition != "missing":
        paths.source_zip.write_bytes(b"not-the-locked-archive")
    _write_lock(paths, "0" * 64)
    if condition == "wrong_name":
        data = json.loads(paths.source_lock.read_text())
        data["archive"] = "old.zip"
        paths.source_lock.write_text(json.dumps(data))
    if condition == "wrong_counts":
        data = json.loads(paths.source_lock.read_text())
        data["recordings"] = 338
        paths.source_lock.write_text(json.dumps(data))
    with pytest.raises(CalibrationSourceError):
        verify_source_archive(paths)


def make_locked_test_archive(tmp_path):
    paths = workspace_paths(tmp_path / "calibration")
    paths.source_dir.mkdir(parents=True)
    with ZipFile(paths.source_zip, "w") as zf:
        zf.writestr("standard_units/decoded/f.meta.json", "{}")
    digest = hashlib.sha256(paths.source_zip.read_bytes()).hexdigest().upper()
    _write_lock(paths, digest)
    return paths


def test_source_cli_reports_verified_contract(tmp_path, capsys, monkeypatch):
    paths = make_locked_test_archive(tmp_path)
    digest = hashlib.sha256(paths.source_zip.read_bytes()).hexdigest().upper()
    monkeypatch.setattr(source_mod, "FINAL_SHA256", digest)
    assert source_mod.main(["--workspace-root", str(paths.root)]) == 0
    out = capsys.readouterr().out
    assert paths.source_zip.name in out
    assert "recordings=339" in out
```

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
python -m pytest tests/test_calibration_paths.py -q -p no:cacheprovider
```

Expected: FAIL because `aoe2x.calibration.source` does not exist.

- [ ] **Step 3: Implement fail-closed validation**

Implementation requirements:

```python
FINAL_SHA256 = "31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9"
EXPECTED_COUNTS = {
    "recordings": 339,
    "unordered_matchups": 91,
    "standard_units": 14,
}
```

Read the archive in 1 MiB chunks with `hashlib.sha256()`. Reject malformed JSON, missing fields, unexpected fields for the checked contract, a non-FINAL filename, count mismatch, absent ZIP, hash mismatch, or `ZipFile.testzip()` returning a corrupt member. Return a normalized lock dictionary only after every check passes.

- [ ] **Step 4: Write the tracked source lock**

```json
{
  "archive": "aoe2_golden_STANDARD_UNITS_FINAL.zip",
  "sha256": "31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9",
  "recordings": 339,
  "unordered_matchups": 91,
  "standard_units": 14
}
```

- [ ] **Step 5: Run focused tests**

```powershell
python -m pytest tests/test_calibration_paths.py -q -p no:cacheprovider
```

Expected: all source and path tests pass.

- [ ] **Step 6: Commit only source-lock files**

```powershell
git add -- aoe2x/calibration/source.py tests/test_calibration_paths.py calibration/source/source_of_truth.json
git commit -m "calibration: lock the final standard-unit archive"
```

### Task 3: Refactor ingestion and extraction for clean project-local rebuilds

**Files:**
- Create: `aoe2x/calibration/rebuild.py`
- Create: `tests/test_calibration_rebuild.py`
- Modify: `aoe2x/calibration/ingest.py`
- Modify: `aoe2x/calibration/extract.py`
- Modify: `tests/test_calibration_ingest.py`
- Modify: `tests/test_calibration_extract.py`

**Interfaces:**
- Consumes: `CalibrationPaths`, `workspace_paths()`, `verify_source_archive()`.
- Modify: `ingest_zip(zip_path: Path, *, paths: CalibrationPaths = workspace_paths()) -> list[str]`.
- Modify: `build_truth_card(run_id: str, *, paths: CalibrationPaths = workspace_paths()) -> dict`.
- Produces: `rebuild_final(paths: CalibrationPaths = workspace_paths()) -> dict[str, int]`.
- Produces private publication seam: `_publish_staged_workspace(staged: CalibrationPaths, target: CalibrationPaths) -> None`.
- CLI: `python -m aoe2x.calibration.rebuild` with optional `--workspace-root PATH` for tests only.

- [ ] **Step 1: Add failing dependency-injection tests**

Add tests proving that explicit temporary paths receive all writes and that the repository default paths remain untouched. Patch no module globals. Each test constructs `paths = workspace_paths(tmp_path / "calibration")` and passes it to the public function.

- [ ] **Step 2: Add failing clean-publication tests**

```python
def test_publish_staged_workspace_replaces_instead_of_appending(tmp_path):
    target = workspace_paths(tmp_path / "target")
    staged = workspace_paths(tmp_path / "staged")
    target.truth_dir.mkdir(parents=True)
    staged.truth_dir.mkdir(parents=True)
    target.tapes_dir.mkdir(parents=True)
    staged.tapes_dir.mkdir(parents=True)
    (target.truth_dir / "stale_old_tape.json").write_text("{}")
    (staged.truth_dir / "final.json").write_text("{}")
    (staged.tapes_dir / "final.stream").write_text("final")

    _publish_staged_workspace(staged, target)

    assert not (target.truth_dir / "stale_old_tape.json").exists()
    assert (target.truth_dir / "final.json").exists()
    assert (target.tapes_dir / "final.stream").read_text() == "final"


def test_rebuild_verifies_source_before_mutating(tmp_path):
    paths = workspace_paths(tmp_path / "calibration")
    paths.fixtures_dir.mkdir(parents=True)
    marker = paths.fixtures_dir / "must-survive.txt"
    marker.write_text("unchanged")

    with pytest.raises(CalibrationSourceError):
        rebuild_final(paths)

    assert marker.read_text() == "unchanged"
```

The full 339-recording rebuild is the Task 4 integration gate. Task 3 unit tests exercise path injection, source-first failure, replacement, and rollback without weakening production corpus constants.

- [ ] **Step 3: Run the focused tests and confirm path/global failures**

```powershell
python -m pytest tests/test_calibration_ingest.py tests/test_calibration_extract.py tests/test_calibration_rebuild.py -q -p no:cacheprovider
```

Expected: FAIL because current modules write through global `data/calibration` and `D:/AI/aoe2_golden` constants.

- [ ] **Step 4: Inject `CalibrationPaths` through ingestion and extraction**

Replace module path constants with reads from the passed `paths`. Do not retain deprecated aliases. Update docstrings to the project-local paths. Ensure extraction reads `paths.tapes_dir / run_id` and writes `paths.truth_dir / f"{run_id}.json"`.

Change each manifest entry from absolute `"drop": "D:/..."` provenance to `"source_archive": paths.source_zip.name`. Keep `zip_sha256`, normalized to uppercase. No absolute source path is stored in generated fixtures.

- [ ] **Step 5: Implement clean staging and atomic publication**

`rebuild_final()` must:

1. call `verify_source_archive(paths)` before creating or deleting anything;
2. create a unique staging root under `paths.scratch_dir`;
3. derive staging paths with `workspace_paths(staging_root)`;
4. ingest and extract all recordings into staging;
5. assert 339 manifest entries, 339 truth cards, and 91 unordered matchups;
6. assert every manifest row has `zip_sha256 == FINAL_SHA256`;
7. replace `paths.tapes_dir` and `paths.fixtures_dir` only after validation;
8. remove staging in `finally` after resolving and confirming it is under `.scratch/calibration`;
9. return the exact summary dictionary.

Publication uses same-volume rename operations. Before replacing existing project-local directories, move them to a sibling backup; restore the backup on any publication failure; remove the backup only after both new directories are in place.

- [ ] **Step 6: Run focused tests**

```powershell
python -m pytest tests/test_calibration_ingest.py tests/test_calibration_extract.py tests/test_calibration_rebuild.py -q -p no:cacheprovider
```

Expected: all tests pass, including stale-file removal and rollback.

- [ ] **Step 7: Commit only ingestion/rebuild files**

```powershell
git add -- aoe2x/calibration/ingest.py aoe2x/calibration/extract.py aoe2x/calibration/rebuild.py tests/test_calibration_ingest.py tests/test_calibration_extract.py tests/test_calibration_rebuild.py
git commit -m "calibration: rebuild final tapes without stale carryover"
```

### Task 4: Install the ignored FINAL archive inside the project

**Files:**
- Create ignored local file: `calibration/source/aoe2_golden_STANDARD_UNITS_FINAL.zip`

**Interfaces:**
- Consumes: ignore rules and source verifier from Tasks 1–2.
- Produces: a verified local source archive available to later rebuild tasks but absent from Git status.

- [ ] **Step 1: Verify source and destination before copying**

```powershell
Get-FileHash -LiteralPath 'C:\Users\ddk22\Downloads\aoe2_golden_STANDARD_UNITS_FINAL.zip' -Algorithm SHA256
Test-Path -LiteralPath 'D:\AI\aoe2_matchup\calibration\source\aoe2_golden_STANDARD_UNITS_FINAL.zip'
```

Expected source hash: `31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9` and destination absent before first copy.

- [ ] **Step 2: Copy the ignored binary and prove it cannot be staged**

```powershell
Copy-Item -LiteralPath 'C:\Users\ddk22\Downloads\aoe2_golden_STANDARD_UNITS_FINAL.zip' -Destination 'D:\AI\aoe2_matchup\calibration\source\aoe2_golden_STANDARD_UNITS_FINAL.zip'
git check-ignore calibration/source/aoe2_golden_STANDARD_UNITS_FINAL.zip
```

Expected: Git reports the ZIP as ignored.

- [ ] **Step 3: Verify the copied archive through the project API**

```powershell
python -m aoe2x.calibration.source
```

Expected: filename, SHA-256, 339 recordings, 91 matchups, and 14 units are printed; exit 0.

- [ ] **Step 4: Verify ignored boundary and source immutability**

```powershell
git status --short -- calibration/source
Get-FileHash -LiteralPath 'D:\AI\aoe2_matchup\calibration\source\aoe2_golden_STANDARD_UNITS_FINAL.zip' -Algorithm SHA256
```

Expected: the ZIP is absent from Git status and retains the locked hash. This task creates no commit because its only output is intentionally ignored.

### Task 5: Redirect Python scoring, filters, and fixture generators

**Files:**
- Modify: `aoe2x/calibration/filters.py`
- Modify: `aoe2x/calibration/score.py`
- Modify: `tools/simjs/dump_calib_dicts.py`
- Modify: `tools/simjs/dump_calib_spawns.py`
- Modify: `tests/test_calibration_filters.py`
- Modify: `tests/test_calibration_score.py`

**Interfaces:**
- Consumes: `workspace_paths()` from Task 1.
- Modify: `slug_set(name: str, *, paths: CalibrationPaths = workspace_paths()) -> frozenset[str]`.
- Scorer defaults: `paths.runs_dir` for raw inputs and `paths.reports_dir` for summaries.
- Dump tools read/write only `paths.fixtures_dir` and `paths.tapes_dir`.

- [ ] **Step 1: Write failing temporary-workspace tests**

Tests create a complete minimal `fixtures/fight_sets.json`, manifest, truth card, and run file under `tmp_path`; they call APIs with explicit paths and assert no `data/calibration` file is opened. Use monkeypatch on `Path.open` only to reject forbidden path prefixes, not to provide data.

- [ ] **Step 2: Run focused tests and confirm old-path failure**

```powershell
python -m pytest tests/test_calibration_filters.py tests/test_calibration_score.py -q -p no:cacheprovider
```

- [ ] **Step 3: Replace old constants with the path contract**

Update imports, defaults, CLI help, and docstrings. Keep report mathematics and all scale behavior byte-for-byte unchanged. The only functional differences are path resolution and fail-closed source provenance.

- [ ] **Step 4: Add source verification at command entry points**

Before a CLI scores or regenerates fixtures, call `verify_source_archive(paths)`. Pure unit-level math functions remain source-independent.

- [ ] **Step 5: Run focused tests**

```powershell
python -m pytest tests/test_calibration_filters.py tests/test_calibration_score.py -q -p no:cacheprovider
```

Expected: all tests pass with temporary project-local workspaces.

- [ ] **Step 6: Commit Task 5 files**

```powershell
git add -- aoe2x/calibration/filters.py aoe2x/calibration/score.py tools/simjs/dump_calib_dicts.py tools/simjs/dump_calib_spawns.py tests/test_calibration_filters.py tests/test_calibration_score.py
git commit -m "calibration: redirect Python tools to local workspace"
```

### Task 6: Redirect Node calibration runners without touching the JS engine

**Files:**
- Create: `tools/simjs/calibration_paths.mjs`
- Create: `tests/js/calibration_paths.test.mjs`
- Modify: `tools/simjs/calib_runner.mjs`
- Modify: `tests/js/calib_runner.test.mjs`

**Interfaces:**
- Produces: `calibrationPaths(repoRoot)` returning URL-safe absolute strings for `root`, `fixtures`, `manifest`, `combatDicts`, `spawns`, `fightSets`, and `runs`.
- `calib_runner.mjs` defaults `--out-dir` to `<repo>/calibration/runs` and reads all fixtures from `<repo>/calibration/fixtures`.
- Existing imports from `apps/website/static/js/engine/` remain unchanged.

- [ ] **Step 1: Write the failing Node path test**

```javascript
import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { calibrationPaths } from "../../tools/simjs/calibration_paths.mjs";

test("calibration paths stay under the supplied repository", () => {
    const repo = path.resolve("C:/tmp/repo");
    const p = calibrationPaths(repo);
    assert.equal(p.root, path.join(repo, "calibration"));
    assert.equal(p.manifest, path.join(repo, "calibration/fixtures/manifest.json"));
    assert.equal(p.runs, path.join(repo, "calibration/runs"));
});
```

- [ ] **Step 2: Run Node tests and verify module-not-found**

```powershell
node --test tests/js/calibration_paths.test.mjs tests/js/calib_runner.test.mjs
```

- [ ] **Step 3: Implement Node paths and update the runner**

Use `path.resolve()` and `path.join()` only. Do not accept an environment fallback to external storage. Preserve runner exports, seed behavior, scale flags, arena choices, and engine imports.

- [ ] **Step 4: Add a no-production-diff assertion**

```powershell
$repo = (Resolve-Path '.').Path
$before = Get-Content -LiteralPath '.scratch\calibration\production-engine-baseline.json' -Raw | ConvertFrom-Json
$roots = @('apps\website\static\js\engine', 'aoe2x\sim')
$after = foreach ($root in $roots) {
    Get-ChildItem -LiteralPath (Join-Path $repo $root) -File -Recurse |
        Sort-Object FullName |
        ForEach-Object {
            [pscustomobject]@{
                path = $_.FullName.Substring($repo.Length + 1).Replace('\', '/')
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
            }
        }
}
if (($before | ConvertTo-Json -Compress) -ne ($after | ConvertTo-Json -Compress)) {
    throw 'production engine files changed during calibration migration'
}
```

Expected: no output. The comparison uses the pre-migration file hashes and does not assume repository HEAD was clean.

- [ ] **Step 5: Run Node tests**

```powershell
node --test tests/js/calibration_paths.test.mjs tests/js/calib_runner.test.mjs tests/js/tape_runner.test.mjs
```

- [ ] **Step 6: Commit only Node calibration files**

```powershell
git add -- tools/simjs/calibration_paths.mjs tools/simjs/calib_runner.mjs tests/js/calibration_paths.test.mjs tests/js/calib_runner.test.mjs
git commit -m "calibration: redirect JS runner to local workspace"
```

### Task 7: Remove the legacy tape-measurement pipeline and external diagnostic defaults

**Files:**
- Remove: `aoe2x/validation/__init__.py`
- Remove: `aoe2x/validation/extract_tapes.py`
- Remove: `aoe2x/validation/margin_score.py`
- Remove: `aoe2x/validation/report.py`
- Remove: `aoe2x/validation/tape_rig.py`
- Remove: `aoe2x/validation/tape_rig_js.py`
- Remove: `tools/simjs/dump_tape_dicts.py`
- Remove: `tools/simjs/tape_runner.mjs`
- Remove: `data/validation/tape_runs.db`
- Remove: `tests/test_margin_score.py`
- Remove: `tests/test_report_engine_column.py`
- Remove: `tests/test_tape_plan.py`
- Remove: `tests/test_tape_rig_js.py`
- Remove: `tests/js/tape_runner.test.mjs`
- Modify: `tools/simjs/c1_chase_probe.mjs`
- Modify: `tools/simjs/c1_chaser_cadence.py`
- Modify: `tools/simjs/d1_dat_audit.py`
- Modify: `tools/simjs/d1_siege_forensics.py`
- Modify: `tools/simjs/dump_sim_units.mjs`
- Modify: `tools/simjs/e14_identity.mjs`
- Modify: `tools/simjs/melee_bout_forensics.py`
- Modify: `tools/simjs/melee_engagement_probe.mjs`
- Modify: `tools/simjs/melee_target_forensics.py`
- Modify: `tools/simjs/ranged_depth_forensics.py`
- Modify: `tools/simjs/ranged_fire_forensics.py`
- Modify: `tools/simjs/ranged_shot_dump.mjs`
- Modify: `tools/simjs/r5c_targeting_forensics.py`
- Modify: `tools/simjs/r5e_pick_forensics.py`
- Modify: `tools/simjs/v2_family_board.py`
- Modify comments only: `tests/js/engine/blast_falloff.test.mjs`
- Modify comments only: `tests/js/engine/c3_post_swing_plant.test.mjs`
- Modify comments only: `tests/js/engine/charge_volley.test.mjs`
- Modify comments only: `tests/js/engine/d2_siege.test.mjs`
- Modify comments only: `tests/js/engine/e1_orbit_kite.test.mjs`
- Modify comments only: `tests/js/engine/melee_swing_recovery.test.mjs`
- Modify comments only: `tests/js/engine/trample.test.mjs`
- Modify comments only: `tests/js/engine/w1_scrum_walk.test.mjs`
- Modify: `tests/test_calibration_ingest.py`
- Modify: `tests/test_calibration_paths.py`

**Interfaces:**
- Consumes: Python `workspace_paths()` or Node `calibrationPaths()`.
- Every retained diagnostic either defaults inside `calibration/runs/<tool-name>` or requires an explicit path.
- No retained diagnostic reads a historical run merely because the user omitted an argument.
- The obsolete `aoe2x.validation`/`data/validation` tape rig has no compatibility shim; current work uses `aoe2x.calibration` only.

- [ ] **Step 1: Add a failing forbidden-path source audit**

```python
def test_active_calibration_sources_have_no_legacy_storage_paths():
    roots = [REPO / "aoe2x/calibration", REPO / "tools/simjs", REPO / "tests"]
    forbidden = (
        "D:" + "/AI/aoe2_golden",
        "D:" + "\\AI\\aoe2_golden",
        "data/" + "calibration",
    )
    offenders = []
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".mjs", ".js"}:
                continue
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in forbidden):
                offenders.append(path.relative_to(REPO).as_posix())
    assert offenders == []
```

- [ ] **Step 2: Run the audit and confirm the planned offender list**

```powershell
python -m pytest tests/test_calibration_paths.py::test_active_calibration_sources_have_no_legacy_storage_paths -q -p no:cacheprovider
```

Expected: FAIL listing the retained diagnostic and comment files named above. Any additional offender is added explicitly to this task before editing.

- [ ] **Step 3: Remove the superseded validation pipeline**

Delete the six `aoe2x/validation` modules, two legacy JS/Python tape tools, the validation database, and their five Python/one Node test files listed above. Confirm `rg -n 'aoe2x\.validation|dump_tape_dicts|tape_runner' aoe2x tools tests` returns no active references.

- [ ] **Step 4: Redirect every retained diagnostic**

For each retained diagnostic listed under Files, import the applicable path contract. Tape readers use `workspace_paths().tapes_dir`; generated output defaults use a tool-specific child of `workspace_paths().runs_dir` or `calibrationPaths(REPO).runs`; report readers requiring an existing run keep `--sim-runs-dir` mandatory. Update examples to `calibration/runs/...`. Do not copy any old numerical result into comments.

- [ ] **Step 5: Remove old tape claims from retained tests**

Delete the skipped obsolete-real-tape blocks and helpers from `tests/test_calibration_ingest.py`. In the eight engine test files listed above, remove only citations to old tape paths/reports and statements claiming old measured values as truth; preserve executable assertions and production engine imports unchanged.

- [ ] **Step 6: Run the audit and retained calibration tests**

```powershell
python -m pytest tests/test_calibration_paths.py tests/test_calibration_ingest.py -q -p no:cacheprovider
node --test tests/js/calibration_paths.test.mjs tests/js/calib_runner.test.mjs
```

Expected: audit clean; retained tests pass without external data.

- [ ] **Step 7: Commit the exact legacy-pipeline and offender cleanup**

```powershell
git add -A -- aoe2x/validation data/validation aoe2x/calibration tools/simjs tests/test_calibration_ingest.py tests/test_calibration_paths.py tests/test_margin_score.py tests/test_report_engine_column.py tests/test_tape_plan.py tests/test_tape_rig_js.py tests/js
git commit -m "calibration: remove superseded tape measurement pipeline"
```

Before committing, inspect `git diff --cached --name-only` and unstage any production engine or unrelated test file.

### Task 8: Replace active calibration documentation with FINAL-only material

**Files:**
- Create: `calibration/README.md`
- Create: `calibration/docs/TAPE_SOURCE_OF_TRUTH.md`
- Remove: `docs/calibration/*.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `gemini.md`
- Test: `tests/test_calibration_paths.py`

**Interfaces:**
- `calibration/README.md` documents one command sequence: verify → rebuild → regenerate combat dictionaries → regenerate spawns → run → score/report.
- `TAPE_SOURCE_OF_TRUTH.md` contains only FINAL path, hash, 339/91/14 counts, data flow, and prohibition on old data.

- [ ] **Step 1: Add a failing documentation audit**

Add this test to `tests/test_calibration_paths.py`:

```python
def test_active_calibration_docs_contain_only_final_authority():
    docs = list((REPO / "calibration").rglob("*.md"))
    docs += [REPO / "AGENTS.md", REPO / "CLAUDE.md", REPO / "gemini.md"]
    forbidden = (
        "STANDARD_UNITS_2026-08-02",
        "phase2_COMPLETE",
        "batch91_partial",
        "aoe2_golden_spike",
        "C:" + "/Users/ddk22/Downloads",
        "D:" + "/AI/aoe2_golden",
        "data/" + "calibration",
        "123 fights",
        "155 fights",
        "222 tapes",
    )
    offenders = {
        path.relative_to(REPO).as_posix(): [token for token in forbidden if token in path.read_text(encoding="utf-8")]
        for path in docs
        if path.exists() and any(token in path.read_text(encoding="utf-8") for token in forbidden)
    }
    assert offenders == {}
```

- [ ] **Step 2: Remove old measurement documents from the active tree**

Delete every file currently under `docs/calibration/`. Do not copy historical winner margins, HP values, durations, hit counts, or conclusions into the new docs. Git history remains the only archive.

- [ ] **Step 3: Write the new workflow README**

Include exact commands:

```powershell
python -m aoe2x.calibration.source
python -m aoe2x.calibration.rebuild
python tools/simjs/dump_calib_dicts.py
python tools/simjs/dump_calib_spawns.py
node tools/simjs/calib_runner.mjs --seeds 20
python -m aoe2x.calibration.score
```

Document which outputs are ignored and which compact reports/fixtures are tracked. State that scale behavior is not part of this migration.

- [ ] **Step 4: Write the FINAL-only source document and update agent memory**

Use exactly the locked name, hash, 339 recordings, 91 unordered matchups, and 14 units. Point all agents to `calibration/source/source_of_truth.json`. Remove old active paths and any instruction to consult the 2026-08-02 handoff.

- [ ] **Step 5: Run documentation and path audits**

```powershell
python -m pytest tests/test_calibration_paths.py -q -p no:cacheprovider
rg -n 'STANDARD_UNITS_2026-08-02|phase2_COMPLETE|D:/AI/aoe2_golden|data/calibration' calibration AGENTS.md CLAUDE.md gemini.md
```

Expected: pytest passes and `rg` returns no matches. Refer to the external location only as “the historical external workspace,” without embedding a usable path.

- [ ] **Step 6: Commit docs and memory only**

```powershell
git add -A -- calibration/README.md calibration/docs docs/calibration AGENTS.md CLAUDE.md gemini.md tests/test_calibration_paths.py
git commit -m "docs: make final tapes the only calibration authority"
```

### Task 9: Publish the regenerated FINAL-only fixture set

**Files:**
- Create: `calibration/fixtures/manifest.json`
- Create: `calibration/fixtures/truth/*.json`
- Create: `calibration/fixtures/spawns.json`
- Create: `calibration/fixtures/combat_dicts.json`
- Create: `calibration/fixtures/matchups.json`
- Create: `calibration/fixtures/fight_sets.json`
- Remove: `data/calibration/runs/`
- Remove: `data/calibration/analysis/`
- Remove remaining: `data/calibration/`

**Interfaces:**
- Consumes: source verifier, rebuild command, Python dump tools, and project-local path contracts from Tasks 1–8.
- Produces: the only active compact fixture set, fully regenerated or copied only when the file is configuration rather than a tape measurement.

- [ ] **Step 1: Snapshot the existing fight-set configuration**

`fight_sets.json` defines unit grouping rather than a measured tape outcome. Copy it into staging before the old directory is removed, then verify its standard-unit union contains exactly 14 slugs. Do not copy manifest, truth, spawns, runs, or analysis.

- [ ] **Step 2: Rebuild manifest, matchups, truth, and extracted tapes from FINAL**

```powershell
python -m aoe2x.calibration.rebuild
```

Expected summary: `recordings=339 truth_cards=339 unordered_matchups=91`.

- [ ] **Step 3: Regenerate current combat dictionaries and spawns**

```powershell
python tools/simjs/dump_calib_dicts.py
python tools/simjs/dump_calib_spawns.py
```

Expected: 14 combat dictionaries and 339 spawn entries under `calibration/fixtures/`.

- [ ] **Step 4: Run the exact provenance assertion**

```python
paths = workspace_paths()
manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))["fights"]
assert len(manifest) == 339
assert len(list(paths.truth_dir.glob("*.json"))) == 339
assert {row["zip_sha256"].upper() for row in manifest} == {FINAL_SHA256}
assert {row["source_archive"] for row in manifest} == {paths.source_zip.name}
assert len({row["matchup"] for row in manifest}) == 91
assert len({side["slug"] for row in manifest for side in (row["side1"], row["side2"])}) == 14
assert len(json.loads(paths.spawns.read_text(encoding="utf-8"))) == 339
assert len(json.loads(paths.combat_dicts.read_text(encoding="utf-8"))) == 14
```

- [ ] **Step 5: Remove mixed historical outputs and old fixture locations**

Delete `data/calibration/runs/` and `data/calibration/analysis/` without migrating their contents. Remove the old manifest, truth, spawns, combat dictionaries, matchups, fight sets, source lock, and then the empty `data/calibration/` directory. Resolve each removal target and confirm it is under `D:/AI/aoe2_matchup/data/calibration` before deletion.

- [ ] **Step 6: Verify ignored/generated/tracked boundaries**

```powershell
git status --short -- calibration data/calibration
```

Expected: ZIP, tapes, and raw runs are absent; compact fixtures and removal of old paths are visible.

- [ ] **Step 7: Commit only the published fixture set and old-path removal**

```powershell
git add -A -- calibration/fixtures data/calibration
git diff --cached --name-only
git commit -m "calibration: publish final-only fixtures in workspace"
```

### Task 10: End-to-end provenance and regression verification

**Files:**
- No planned file changes. A failing gate reopens the task that owns the failing file; the gate is rerun after that task's focused test passes.

**Interfaces:**
- Produces no new feature interface.
- Produces evidence that the migrated workspace is self-contained and production engines are unchanged.

- [ ] **Step 1: Verify binary and active corpus provenance**

Run a read-only verification script that reports and asserts:

```text
source ZIP SHA-256 = 31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9
manifest rows = 339
truth cards = 339
unordered matchups = 91
active manifest hashes = {FINAL SHA-256 only}
```

- [ ] **Step 2: Run focused Python tests**

```powershell
python -m pytest tests/test_calibration_paths.py tests/test_calibration_rebuild.py tests/test_calibration_ingest.py tests/test_calibration_extract.py tests/test_calibration_filters.py tests/test_calibration_score.py -q -p no:cacheprovider
```

Expected: all retained tests pass; no test reads legacy tape data.

- [ ] **Step 3: Run focused Node tests**

```powershell
node --test tests/js/calibration_paths.test.mjs tests/js/calib_runner.test.mjs
```

Expected: all tests pass.

- [ ] **Step 4: Run forbidden-path and stale-measurement audits**

```powershell
rg -n 'STANDARD_UNITS_2026-08-02|phase2_COMPLETE|data/calibration|C:/Users/ddk22/Downloads/aoe2_golden|D:/AI/aoe2_golden' aoe2x/calibration tools/simjs calibration tests AGENTS.md CLAUDE.md gemini.md
```

Expected: no active-source matches. Current docs call it only “the historical external workspace.”

- [ ] **Step 5: Prove production engine immutability**

```powershell
$repo = (Resolve-Path '.').Path
$before = Get-Content -LiteralPath '.scratch\calibration\production-engine-baseline.json' -Raw | ConvertFrom-Json
$roots = @('apps\website\static\js\engine', 'aoe2x\sim')
$after = foreach ($root in $roots) {
    Get-ChildItem -LiteralPath (Join-Path $repo $root) -File -Recurse |
        Sort-Object FullName |
        ForEach-Object {
            [pscustomobject]@{
                path = $_.FullName.Substring($repo.Length + 1).Replace('\', '/')
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
            }
        }
}
$delta = Compare-Object ($before | ConvertTo-Json -Compress) ($after | ConvertTo-Json -Compress)
if ($delta) { $delta; throw 'production engine files changed during calibration migration' }
```

Expected: no delta. Do not use `git diff HEAD` as the sole proof because the worktree was dirty before migration.

- [ ] **Step 6: Run the full repository suite**

```powershell
python -m pytest -q -p no:cacheprovider
node --test tests/js/engine tests/js/calibration_paths.test.mjs tests/js/calib_runner.test.mjs
```

Record pre-existing failures separately. Any new failure in a calibration path, fixture, or documentation test blocks completion.

- [ ] **Step 7: Check whitespace and scope**

```powershell
git diff --check
git status --short
```

Confirm no ignored ZIP, tape stream, or raw run is staged; confirm unrelated graphics, lab, website, and production simulation changes remain untouched.

- [ ] **Step 8: Commit verification corrections only when Step 1–7 exposed a defect**

If no fixes were required, do not create an empty commit. If fixes were required, stage only their named calibration files and use:

```powershell
git commit -m "test: verify self-contained final calibration workspace"
```

## Completion Evidence

The implementation report must include:

- source ZIP path and verified SHA-256;
- manifest, truth-card, matchup, and unit counts;
- focused Python and Node test results;
- full-suite result with any pre-existing unrelated failures named;
- forbidden-path audit result;
- proof that `apps/website/static/js/engine/` and `aoe2x/sim/` did not change;
- confirmation that `D:/AI/aoe2_golden` was neither read for evidence nor modified;
- commit hashes created by the migration;
- explicit statement that no production action occurred.
