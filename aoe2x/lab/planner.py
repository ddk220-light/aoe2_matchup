"""Canonical matchup request parsing and Node-backed engine planning."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .config import LabConfig
from .errors import PlanError
from .io import safe_slug


def make_request(
    *,
    side2: str,
    side3: str,
    civ2: str | None = None,
    civ3: str | None = None,
    balance: str = "equal_resources",
    count: int = 27,
    n2: int | None = None,
    n3: int | None = None,
    cap: int = 27,
    food_weight: float = 1.0,
    wood_weight: float = 1.0,
    gold_weight: float = 1.0,
    job_id: str | None = None,
) -> dict[str, Any]:
    if balance == "explicit" and (n2 is None or n3 is None):
        raise PlanError("explicit balance requires both --n2 and --n3")
    if balance != "explicit" and (n2 is not None or n3 is not None):
        raise PlanError("--n2 and --n3 are only valid with --balance explicit")
    request: dict[str, Any] = {
        "schemaVersion": 1,
        "side2": {"slug": side2, **({"civ": civ2} if civ2 else {})},
        "side3": {"slug": side3, **({"civ": civ3} if civ3 else {})},
        "balance": {
            "mode": balance,
            "cap": cap,
            "count": count,
            "weights": {
                "food": food_weight,
                "wood": wood_weight,
                "gold": gold_weight,
            },
            **({"n2": n2, "n3": n3} if balance == "explicit" else {}),
        },
    }
    if job_id:
        request["jobId"] = safe_slug(job_id)
    return request


def load_matchup_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix == ".toml":
        try:
            import tomllib
        except ModuleNotFoundError as error:  # pragma: no cover
            raise PlanError("TOML matchup files require Python 3.11+") from error
        with path.open("rb") as source:
            return tomllib.load(source)
    raise PlanError("matchup files must be JSON or TOML")


def plan_matchup(config: LabConfig, request: dict[str, Any]) -> dict[str, Any]:
    worker = (
        config.project_root
        / "aoe2x" / "js_simulation" / "tools" / "aoe2lab_worker.mjs"
    )
    command = [config.node, str(worker), "plan"]
    completed = subprocess.run(
        command,
        input=json.dumps(request),
        capture_output=True,
        text=True,
        cwd=config.project_root,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise PlanError(
            f"engine rejected the matchup plan: {detail}",
            hint="run 'aoe2lab doctor' and verify both unit slugs are registered",
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise PlanError("engine planner returned invalid JSON") from error
