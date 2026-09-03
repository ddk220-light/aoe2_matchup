"""Portable machine configuration for AOE2 Lab."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None

from .errors import ConfigurationError
from .io import repo_root


@dataclass(frozen=True)
class LabConfig:
    project_root: Path
    config_path: Path | None
    artifacts_root: Path
    node: str
    python: str
    game_executable: Path | None
    scenario_directory: Path | None
    game_window_title: str
    grpc_python: Path
    grpc_logger: Path
    grpc_redecoder: Path
    simulation_workers: int
    simulation_seeds: int
    live_cap_seconds: int
    live_retention: str
    live_min_free_bytes: int
    live_estimated_recording_bytes: int
    viewer_host: str
    viewer_port: int
    viewer_route: str
    tailscale: str


def _path(root: Path, value: str | None, default: Path | None) -> Path | None:
    if value is None or value == "":
        return default
    selected = Path(os.path.expandvars(os.path.expanduser(value)))
    return selected if selected.is_absolute() else (root / selected).resolve()


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"[{name}] must be a TOML table")
    return value


def load_config(path: str | Path | None = None) -> LabConfig:
    root = repo_root()
    explicit = Path(path).resolve() if path else None
    env_path = os.environ.get("AOE2LAB_CONFIG")
    candidate = explicit or (Path(env_path).resolve() if env_path else root / "aoe2lab.toml")
    data: dict[str, Any] = {}
    config_path: Path | None = None
    if candidate.exists():
        if tomllib is None:
            raise ConfigurationError("TOML configuration requires Python 3.11 or newer")
        with candidate.open("rb") as source:
            data = tomllib.load(source)
        config_path = candidate
    elif explicit or env_path:
        raise ConfigurationError(f"configuration file does not exist: {candidate}")

    paths = _section(data, "paths")
    game = _section(data, "game")
    grpc = _section(data, "grpc")
    simulation = _section(data, "simulation")
    live = _section(data, "live")
    viewer = _section(data, "viewer")
    video_root = root / "apps" / "video"
    grpc_root = root / "aoe2x" / "grpc"
    artifacts = _path(
        root,
        paths.get("artifacts"),
        root / "aoe2x" / "js_simulation" / "calibration" / "lab",
    )
    scenario_value = game.get("scenario_directory") or os.environ.get("AOE2_SCENARIO_DIR")
    game_executable = _path(root, game.get("executable"), None)
    grpc_python = _path(
        root,
        grpc.get("python") or os.environ.get("AOE2_GRPC_PYTHON"),
        video_root / ".venv" / "Scripts" / "python.exe",
    )
    grpc_logger = _path(
        root,
        grpc.get("logger") or os.environ.get("AOE2_GRPC_LOGGER"),
        grpc_root / "grpc_hp_log.py",
    )
    grpc_redecoder = _path(
        root,
        grpc.get("redecoder") or os.environ.get("AOE2_GRPC_REDECODE"),
        grpc_root / "redecode_hp.py",
    )
    node = str(paths.get("node") or shutil.which("node") or "node")
    workers = int(simulation.get("workers", 0))
    seeds = int(simulation.get("seeds", 5))
    port = int(viewer.get("port", 5012))
    cap = int(live.get("cap_seconds", 210))
    retention = str(live.get("retention", "stats")).strip().lower()
    min_free_gb = float(live.get("min_free_gb", 2.0))
    estimated_recording_gb = float(live.get("estimated_recording_gb", 1.0))
    if retention not in {"stats", "archive", "raw"}:
        raise ConfigurationError("live.retention must be stats, archive, or raw")
    if min_free_gb < 0 or estimated_recording_gb <= 0:
        raise ConfigurationError(
            "live.min_free_gb must be non-negative and estimated_recording_gb positive"
        )
    if workers < 0 or seeds < 1 or cap < 10 or not 1 <= port <= 65535:
        raise ConfigurationError("workers, seeds, cap_seconds, or viewer port is invalid")
    route = str(viewer.get("tailnet_route", "/golden-map"))
    if not route.startswith("/"):
        raise ConfigurationError("viewer.tailnet_route must begin with '/'")
    return LabConfig(
        project_root=root,
        config_path=config_path,
        artifacts_root=artifacts,
        node=node,
        python=str(paths.get("python") or sys.executable),
        game_executable=game_executable,
        scenario_directory=_path(root, scenario_value, None),
        game_window_title=str(game.get(
            "window_title", "Age of Empires II: Definitive Edition"
        )),
        grpc_python=grpc_python,
        grpc_logger=grpc_logger,
        grpc_redecoder=grpc_redecoder,
        simulation_workers=workers,
        simulation_seeds=seeds,
        live_cap_seconds=cap,
        live_retention=retention,
        live_min_free_bytes=int(min_free_gb * 1024 ** 3),
        live_estimated_recording_bytes=int(estimated_recording_gb * 1024 ** 3),
        viewer_host=str(viewer.get("host", "127.0.0.1")),
        viewer_port=port,
        viewer_route=route.rstrip("/") or "/",
        tailscale=str(viewer.get("tailscale") or shutil.which("tailscale") or "tailscale"),
    )


def apply_live_environment(config: LabConfig) -> None:
    """Apply config before importing the legacy live automation modules."""
    if config.scenario_directory:
        os.environ["AOE2_SCENARIO_DIR"] = str(config.scenario_directory)
    os.environ["AOE2_WIN_TITLE"] = config.game_window_title
    os.environ["AOE2_GRPC_PYTHON"] = str(config.grpc_python)
    os.environ["AOE2_GRPC_LOGGER"] = str(config.grpc_logger)
    os.environ["AOE2_GRPC_REDECODE"] = str(config.grpc_redecoder)
