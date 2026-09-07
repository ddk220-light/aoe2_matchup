"""Read-only portability and dependency checks."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .config import LabConfig
from .io import sha256
from .live import GOLDENS


def run_doctor(config: LabConfig, *, live: bool = False, ui: bool = False) -> dict:
    checks = []

    def check(name: str, passed: bool, detail: str, *, required: bool = True) -> None:
        checks.append({
            "name": name,
            "passed": bool(passed),
            "required": required,
            "detail": detail,
        })

    try:
        node = subprocess.run(
            [config.node, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
        check("Node.js", node.returncode == 0, (node.stdout or node.stderr).strip())
    except OSError as error:
        check("Node.js", False, str(error))
    worker = config.project_root / "aoe2x/js_simulation/tools/aoe2lab_worker.mjs"
    server = config.project_root / "aoe2x/js_simulation/server.mjs"
    check("Simulation worker", worker.exists(), str(worker))
    check("Viewer server", server.exists(), str(server))
    try:
        config.artifacts_root.mkdir(parents=True, exist_ok=True)
        probe = config.artifacts_root / ".doctor-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        check("Artifact storage", True, str(config.artifacts_root))
    except OSError as error:
        check("Artifact storage", False, str(error))
    for family, (relative, expected) in GOLDENS.items():
        path = config.project_root / relative
        actual = sha256(path) if path.exists() else None
        check(f"Golden {family}", actual == expected, str(path))
    fixtures = [
        config.project_root / "aoe2x/js_simulation/fixtures/golden_map.json",
        config.project_root / "aoe2x/js_simulation/fixtures/golden_formation_27v27.json",
        config.project_root / "aoe2x/js_simulation/fixtures/current_ranged_golden_formations.json",
    ]
    check("Simulation fixtures", all(path.exists() for path in fixtures), ", ".join(map(str, fixtures)))
    lab_python_ok = False
    lab_python_detail = str(config.python)
    if config.python.exists():
        probe = (
            "import aoe2x, AoE2ScenarioParser, grpc, cv2, numpy, PIL, "
            "pydirectinput, pygetwindow; print('AOE2 Lab runtime OK')"
        )
        try:
            completed = subprocess.run(
                [str(config.python), "-c", probe],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
                cwd=config.project_root,
            )
            lab_python_ok = completed.returncode == 0
            detail = (completed.stdout or completed.stderr).strip()
            lab_python_detail = f"{config.python} ({detail or 'no probe output'})"
        except OSError as error:
            lab_python_detail = f"{config.python} ({error})"
    check("AOE2 Lab Python", lab_python_ok, lab_python_detail, required=live)
    current_python = Path(sys.executable).resolve()
    configured_python = config.python.resolve() if config.python.exists() else config.python
    check(
        "Active lab interpreter",
        not live or current_python == configured_python,
        f"active={current_python}; configured={configured_python}",
        required=live,
    )
    grpc_python_ok = False
    grpc_python_detail = str(config.grpc_python)
    if config.grpc_python.exists():
        try:
            completed = subprocess.run(
                [str(config.grpc_python), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            grpc_python_ok = completed.returncode == 0
            version = (completed.stdout or completed.stderr).strip()
            grpc_python_detail = f"{config.grpc_python} ({version or 'no version output'})"
        except OSError as error:
            grpc_python_detail = f"{config.grpc_python} ({error})"
    check("gRPC Python", grpc_python_ok, grpc_python_detail, required=live)
    check(
        "gRPC logger", config.grpc_logger.exists(), str(config.grpc_logger), required=live
    )
    check(
        "gRPC redecoder", config.grpc_redecoder.exists(), str(config.grpc_redecoder), required=live
    )
    if config.scenario_directory:
        check(
            "Scenario directory",
            config.scenario_directory.exists(),
            str(config.scenario_directory),
            required=live,
        )
    else:
        check("Scenario directory", True, "auto-detect at live-run import", required=live)
    if config.game_executable:
        check(
            "Game executable", config.game_executable.exists(), str(config.game_executable), required=live
        )
    if live:
        from .planner import make_request, plan_matchup
        from .live import preflight_live

        try:
            plan = plan_matchup(config, make_request(side2="champion", side3="halberdier"))
            detail = preflight_live(config, plan, check_ui=ui)
            check("Live automation", True, str(detail))
        except Exception as error:
            check("Live automation", False, str(error))
    required_failures = [row for row in checks if row["required"] and not row["passed"]]
    return {
        "ok": not required_failures,
        "projectRoot": str(config.project_root),
        "config": str(config.config_path) if config.config_path else "defaults",
        "cpuCount": os.cpu_count() or 1,
        "checks": checks,
    }
