"""grpc_capture.py — bridge the matchup automation to the gRPC stream recorder.

The recorder (aoe2grpc/grpc_hp_log.py) dumps the raw CadeRemote Frames() stream during
the fight; the EXACT per-second timeline is then decoded OFFLINE (redecode_hp.py, full
hindsight — frame-accurate deaths, true HP, no carry-forward lag) when the sidecar is
built. Both need grpcio + the cade_api stubs, which live in the SYSTEM Python, not the
scenario_builder venv — so they run as separate processes.

Config (env, machine-specific defaults in auto/config.py):
  AOE2_GRPC           '0' to disable (default on)
  AOE2_GRPC_PYTHON    system python with grpcio (has the cade_api stubs)
  AOE2_GRPC_LOGGER    path to grpc_hp_log.py (the stream recorder)
  AOE2_GRPC_REDECODE  path to redecode_hp.py (the offline decoder)
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from auto.record_until_end import log
from auto.config import GRPC_PYTHON, GRPC_LOGGER, GRPC_REDECODE, GAME_SPEED

GRPC_ENABLED = os.environ.get("AOE2_GRPC", "1").lower() not in ("0", "", "false", "no")


def available() -> bool:
    return GRPC_ENABLED and Path(GRPC_PYTHON).exists() and Path(GRPC_LOGGER).exists()


def start_logger(prefix, dur=270, logfile=None):
    """Spawn the stream recorder (system python) writing to <prefix>.* . Its stdout goes
    to <prefix>.logger.log so a silent failure is diagnosable. Returns the Popen or None."""
    if not available():
        log("[grpc] recorder unavailable — overlay will use the OCR readout "
            "(set AOE2_GRPC_PYTHON / AOE2_GRPC_LOGGER)", logfile)
        return None
    for ext in (".END", ".meta.json", ".hp_log.jsonl", ".frames.bin",
                ".seed_snap.bin", ".reseed.bin", ".hp.json"):  # clear stale artifacts
        try:
            os.remove(prefix + ext)
        except OSError:
            pass
    lf = open(prefix + ".logger.log", "w")
    proc = subprocess.Popen([GRPC_PYTHON, GRPC_LOGGER, prefix, str(int(dur))],
                            stdout=lf, stderr=subprocess.STDOUT)
    lf.close()                                  # the child keeps its own handle
    log(f"[grpc] stream recorder started (pid {proc.pid}) -> {prefix}.*", logfile)
    return proc


def redecode(prefix, logfile=None, timeout=240) -> bool:
    """Run the OFFLINE redecode of <prefix>.frames.bin -> <prefix>.hp_log.jsonl (the
    exact timeline). Returns True if rows were produced."""
    frames = prefix + ".frames.bin"
    if not (os.path.exists(frames) and os.path.getsize(frames) > 1_000_000):
        return False
    if not Path(GRPC_REDECODE).exists():
        log(f"[grpc] redecoder missing: {GRPC_REDECODE}", logfile)
        return False
    try:
        p = subprocess.run([GRPC_PYTHON, GRPC_REDECODE, prefix],
                           capture_output=True, text=True, timeout=timeout)
        tail = (p.stdout or "").strip().splitlines()
        if tail:
            log(f"[grpc] redecode: {tail[-1] if p.returncode == 0 else tail[-3:]}", logfile)
        return p.returncode == 0
    except Exception as e:
        log(f"[grpc] redecode failed: {type(e).__name__}: {e}", logfile)
        return False


def stop_logger(proc, timeout=8, logfile=None):
    if proc is None:
        return
    try:
        proc.terminate(); proc.wait(timeout=timeout)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    log("[grpc] HP logger stopped", logfile)


def read_meta(prefix) -> dict:
    try:
        with open(prefix + ".meta.json") as f:
            return json.load(f)
    except Exception:
        return {}


def read_rows(prefix) -> list:
    rows = []
    try:
        with open(prefix + ".hp_log.jsonl") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    except Exception:
        pass
    return rows


def write_sidecar(prefix, t_rec, logfile=None):
    """Build the HP sidecar (timeline + video-sync offset) and write it to <prefix>.hp.json.
    Called BEFORE compose so the overlay can consume it. The timeline comes from the
    OFFLINE redecode of the recorded stream (exact counts + true HP); composers re-anchor
    the clock on the pixel-detected V0, the stored wall-clock offset is only a fallback.

    video_game_start_s = wall0_epoch - t_rec  ≈ seconds into the RAW recording where the
    gRPC game clock began, so overlay row game_s=G maps to raw-video time
    (video_game_start_s + G). Returns the sidecar path or None."""
    redecode(prefix, logfile=logfile)
    meta = read_meta(prefix)
    rows = read_rows(prefix)
    if not meta.get("wall0_epoch"):
        # archive rebuilds: .meta.json isn't archived, but the prior sidecar kept it
        try:
            with open(prefix + ".hp.json") as f:
                meta.setdefault("wall0_epoch", json.load(f)["wall0_epoch"])
        except Exception:
            pass
    if not rows or not meta.get("wall0_epoch"):
        log("[grpc] no HP timeline to save", logfile)
        return None
    # hp_log rows are in GAME-SIM seconds (the stream clock runs at game speed);
    # the sidecar contract is VIDEO seconds since game start.
    for r in rows:
        r["game_s"] = round(r["game_s"] / GAME_SPEED, 2)
    end_s = meta.get("end_game_s")
    sidecar = {
        "video_game_start_s": round(meta["wall0_epoch"] - t_rec, 3),
        "wall0_epoch": meta["wall0_epoch"], "recorder_start_epoch": t_rec,
        "game_version": meta.get("game_version"),
        "end_game_s": round(end_s / GAME_SPEED, 2) if end_s else None,
        "clock": "video", "game_speed": GAME_SPEED,
        "rows": rows,
    }
    out = prefix + ".hp.json"
    with open(out, "w") as f:
        json.dump(sidecar, f)
    log(f"[grpc] HP sidecar -> {out}  (game-start at video +{sidecar['video_game_start_s']:.1f}s, "
        f"{len(rows)} rows)", logfile)
    return out


def copy_sidecar(sidecar_path, dest_video, logfile=None):
    """Copy the sidecar next to the finished video (<video-stem>.hp.json)."""
    if not sidecar_path:
        return None
    import shutil
    out = str(Path(dest_video).with_suffix("")) + ".hp.json"
    try:
        shutil.copy2(sidecar_path, out)
        log(f"[grpc] HP sidecar copied -> {out}", logfile)
        return out
    except Exception as e:
        log(f"[grpc] sidecar copy failed: {e}", logfile)
        return None
