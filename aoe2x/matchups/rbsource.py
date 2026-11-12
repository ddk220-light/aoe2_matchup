"""Read-only access to the 2026 research branch (``RB``) through git.

The research branch ``origin/simulations/civ-forecast-recovery-2026-11-10``
holds ~149k files / 4 GB; it is never checked out. Files are read with
``git show <ref>:<path>``. Every command that needs it skips with a clear
message when the ref is not available (fresh clone without the branch).
"""
from __future__ import annotations

import gzip
import io
import json
import os
import subprocess
from pathlib import Path

from aoe2x.matchups.paths import REPO_ROOT

DEFAULT_REF = "origin/simulations/civ-forecast-recovery-2026-11-10"
RB_TIP = "3344324fa93fd75c212a8e84eccaae566f7efadd"
SIM = "aoe2x/js_simulation"
CAMPAIGNS = f"{SIM}/calibration/campaigns"
FROZEN_DEFINITION = f"{CAMPAIGNS}/unit-rankings-path-recovery-2026-10-29/manifest.json"
ADAPTIVE = f"{CAMPAIGNS}/civ-matchups-campaign-2026-10-31/adaptive"
MISMATCH = f"{CAMPAIGNS}/civ-matchups-mismatch-validation-2026-11-05"
FORECAST = f"{CAMPAIGNS}/civ-matchups-forecast-validation-2026-11-07"
RECOVERY = f"{CAMPAIGNS}/civ-matchups-forecast-recovery-2026-11-10"
FIRST_PASS = f"{SIM}/calibration/reports/civ-matchups-first-pass-provisional-2026-11-02"


class RBUnavailable(RuntimeError):
    pass


class ResearchBranch:
    def __init__(self, ref: str | None = None, repo: Path = REPO_ROOT):
        self.ref = ref or os.environ.get("MATCHUP_RB_REF") or DEFAULT_REF
        self.repo = Path(repo)

    def available(self) -> bool:
        result = subprocess.run(["git", "rev-parse", "--verify", "--quiet", self.ref + "^{commit}"],
                                cwd=self.repo, capture_output=True)
        return result.returncode == 0

    def require(self) -> "ResearchBranch":
        if not self.available():
            raise RBUnavailable(
                f"research branch {self.ref!r} is not available in {self.repo}; "
                f"run `git fetch origin simulations/civ-forecast-recovery-2026-11-10` "
                f"or set MATCHUP_RB_REF")
        return self

    def resolve(self, rev: str) -> str:
        return subprocess.run(["git", "rev-parse", rev + "^{commit}"], cwd=self.repo,
                              capture_output=True, text=True, check=True).stdout.strip()

    def commit(self) -> str:
        return self.resolve(self.ref)

    def show(self, path: str, ref: str | None = None) -> bytes:
        result = subprocess.run(["git", "show", f"{ref or self.ref}:{path}"], cwd=self.repo,
                                capture_output=True)
        if result.returncode:
            raise FileNotFoundError(f"{ref or self.ref}:{path}: {result.stderr.decode().strip()}")
        return result.stdout

    def json(self, path: str):
        return json.loads(self.show(path))

    def jsonl(self, path: str) -> list:
        data = self.show(path)
        if path.endswith(".gz"):
            data = gzip.decompress(data)
        return [json.loads(line) for line in io.StringIO(data.decode("utf-8")) if line.strip()]

    def ls(self, path: str) -> list[str]:
        result = subprocess.run(["git", "ls-tree", "--name-only", f"{self.ref}:{path}"], cwd=self.repo,
                                capture_output=True, text=True, check=True)
        return [line for line in result.stdout.splitlines() if line]
