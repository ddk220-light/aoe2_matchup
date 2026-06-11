"""config.py — machine-specific defaults, each overridable via an environment variable.

The ONE place personal paths live; everything else imports from here. Defaults are
derived from the user profile so a new machine works without edits — set the env
vars only when your layout differs.
"""
from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str, default) -> Path:
    v = os.environ.get(name)
    return Path(v) if v else Path(default)


# Where finished matchup videos (and their "raw recordings/" archive) land.
VIDEOS_DIR = _env_path("AOE2_VIDEOS_DIR", Path.home() / "Videos" / "aoe2_matchups")
DEFAULT_COPY_TO = _env_path("AOE2_COPY_TO", VIDEOS_DIR)
GUECHA_OUT = _env_path("GUECHA_OUT", VIDEOS_DIR / "guecha_sweep")

# The gRPC stream recorder + offline redecoder live IN THE REPO now
# (scenario_builder/grpc/ — recorder, redecoder, decoder, schema, protobuf stubs and
# the CadeRemote mTLS certs), and the scenario_builder venv carries grpcio+protobuf,
# so the pipeline is self-sufficient. Env overrides remain for external checkouts
# (e.g. the research copy at C:\dev\aoe2\aoe2grpc).
_SB = Path(__file__).resolve().parents[1]
GRPC_PYTHON = os.environ.get(
    "AOE2_GRPC_PYTHON", str(_SB / ".venv" / "Scripts" / "python.exe"))
GRPC_LOGGER = os.environ.get("AOE2_GRPC_LOGGER", str(_SB / "grpc" / "grpc_hp_log.py"))
GRPC_REDECODE = os.environ.get(
    "AOE2_GRPC_REDECODE", str(Path(GRPC_LOGGER).parent / "redecode_hp.py"))

# The gRPC stream's frame timestamps are GAME-SIM seconds, which run faster than
# wall/video time by the game-speed setting (AoE2:DE "normal" = 1.7x — measured on
# footage: a fight the readout saw end at video 16.5s ends at stream 28s; 28/1.7=16.47).
# Sidecars divide by this so their game_s is in video seconds.
GAME_SPEED = float(os.environ.get("AOE2_GAME_SPEED", "1.7"))
