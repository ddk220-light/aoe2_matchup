"""Durable, expanded recording bundles for later offline overlay work."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .errors import LiveCaptureError
from .io import read_json, sha256, utc_now, write_json


def recorder_retention(mode: str, retention: str | None) -> str | None:
    if mode not in {"statistics", "recorder"}:
        raise ValueError("mode must be statistics or recorder")
    if mode == "recorder":
        if retention not in (None, "raw"):
            raise ValueError("recorder mode requires expanded raw retention; omit --retention")
        return "raw"
    return retention


def probe_video(path: Path) -> dict:
    from overlay.ffutil import find_ffprobe

    executable = find_ffprobe()
    if not executable:
        raise LiveCaptureError("ffprobe is required to validate recorder output")
    result = subprocess.run(
        [executable, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    data = json.loads(result.stdout)
    videos = [stream for stream in data["streams"] if stream["codec_type"] == "video"]
    duration = float(data.get("format", {}).get("duration", 0))
    if not videos or duration <= 0 or min(videos[0].get("width", 0), videos[0].get("height", 0)) <= 0:
        raise LiveCaptureError("recorded video has no valid video stream or duration")
    stream = videos[0]
    return {
        "durationSeconds": duration, "width": stream["width"], "height": stream["height"],
        "codec": stream["codec_name"], "frameRate": stream.get("avg_frame_rate"),
        "hasAudio": any(row["codec_type"] == "audio" for row in data["streams"]),
    }


def write_recording_bundle(run_directory: Path, plan: dict, capture: dict) -> dict:
    """Index exact raw inputs; never zip, render, or alter the measured timeline."""
    video = run_directory / capture["artifacts"]["video"]
    prefix = video.with_suffix("")
    paths = {
        "video": video, "frames": Path(f"{prefix}.frames.bin"),
        "metadata": Path(f"{prefix}.meta.json"), "end": Path(f"{prefix}.END"),
        "hp": Path(f"{prefix}.hp.json"),
        "scenario": run_directory / f"{plan['matchupId']}.aoe2scenario",
    }
    files = {}
    for name, path in paths.items():
        if not path.is_file() or path.stat().st_size == 0:
            raise LiveCaptureError(f"recorder bundle is missing {name}: {path}")
        files[name] = {
            "path": path.relative_to(run_directory).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha256(path),
        }
    hp = read_json(paths["hp"])
    if hp.get("clock") != "video":
        raise LiveCaptureError("recorder HP sidecar must use the video clock")
    bundle = {
        "schemaVersion": 1, "kind": "aoe2lab.recording", "createdAt": utc_now(),
        "jobId": plan["jobId"], "planHash": plan["planHash"],
        "mode": "recorder", "retention": "raw", "overlayApplied": False,
        "gameVersion": hp.get("game_version"), "files": files,
        "media": probe_video(video),
        "sides": {
            "side1": {"player": 2, **plan["side2"]},
            "side2": {"player": 3, **plan["side3"]},
        },
        "clock": {
            "rows": "video_seconds", "gameSpeed": hp.get("game_speed"),
            "videoGameStartSeconds": hp.get("video_game_start_s"),
            "recorderStartEpoch": hp.get("recorder_start_epoch"),
            "endVideoSeconds": hp.get("end_video_s"),
            "mapping": "raw_video_s = video_game_start_s + row.game_s",
        },
    }
    write_json(run_directory / "recording.json", bundle)
    return bundle


def validate_recording_bundle(run_directory: Path, plan: dict) -> dict:
    bundle = read_json(run_directory / "recording.json")
    if bundle.get("planHash") != plan["planHash"]:
        raise LiveCaptureError("recorder bundle belongs to a different plan")
    required = {"video", "frames", "metadata", "end", "hp", "scenario"}
    if not required.issubset(bundle.get("files", {})):
        raise LiveCaptureError("recorder bundle file inventory is incomplete")
    for entry in bundle["files"].values():
        path = (run_directory / entry["path"]).resolve()
        if not path.is_relative_to(run_directory.resolve()):
            raise LiveCaptureError("recorder artifact escapes its run directory")
        if not path.is_file() or path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            raise LiveCaptureError(f"recorder artifact missing or changed: {path}")
    return bundle
