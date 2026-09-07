"""Frame-aligned battle-only delivery from immutable recorder evidence."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import subprocess
from pathlib import Path

from .errors import LiveCaptureError
from .io import read_json, sha256, write_json
from .recording import probe_video, validate_recording_bundle


CLIP_VERSION = 2


def shifted_sidecar(source: dict, start: float) -> dict:
    result = deepcopy(source)
    result["source_video_game_start_s"] = source["video_game_start_s"]
    result["video_game_start_s"] = source["video_game_start_s"] - start
    if source.get("end_video_s") is not None:
        result["end_video_s"] = source["end_video_s"] - start
    result["clip_start_raw_video_s"] = start
    return result


def prepare_battle_clip(run_directory: Path, plan: dict) -> dict:
    """Trim both tracks at V0; retain every frame thereafter, including the end hold.

    Capture still starts before Test to avoid losing opening frames to encoder
    startup. Presentation starts at the pixel-detected first in-game frame, with
    no patrol lead, OCR delay, fade, or tail trim. Unknown starts fail explicitly.
    """
    from overlay.ffutil import find_ffmpeg
    from overlay.video_extract import find_game_start

    bundle = validate_recording_bundle(run_directory, plan)
    existing = bundle.get("presentation")
    if existing and existing.get("version") == CLIP_VERSION:
        return existing
    source = run_directory / bundle["files"]["video"]["path"]
    media = bundle["media"]
    fps = float(Fraction(media["frameRate"]))
    detected = find_game_start(source, t_from=0.0)
    if detected is None:
        raise LiveCaptureError("cannot identify first in-game frame; raw capture retained for review")
    first_frame = round(detected * fps)
    start = first_frame / fps
    if not 0 <= start < media["durationSeconds"]:
        raise LiveCaptureError("detected game start is outside the recording")
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise LiveCaptureError("ffmpeg is required to trim the recorder output")
    destination = run_directory / "battle.mp4"
    temporary = run_directory / "battle.partial.mp4"
    command = [
        ffmpeg, "-y", "-v", "error", "-i", str(source), "-map", "0:v:0",
        "-vf", f"trim=start_frame={first_frame},setpts=PTS-STARTPTS",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
    ]
    if media["hasAudio"]:
        command += ["-map", "0:a:0", "-af", f"atrim=start={start:.9f},asetpts=PTS-STARTPTS",
                    "-c:a", "aac", "-b:a", "192k"]
    command += ["-movflags", "+faststart", str(temporary)]
    with (run_directory / "battle-trim.log").open("w", encoding="utf-8") as log:
        subprocess.run(command, stdout=log, stderr=log, timeout=600, check=True)
    output_media = probe_video(temporary)
    expected_duration = media["durationSeconds"] - start
    if abs(output_media["durationSeconds"] - expected_duration) > max(2 / fps, 0.05):
        raise LiveCaptureError("battle clip duration does not preserve the original ending")
    if output_media["hasAudio"] != media["hasAudio"]:
        raise LiveCaptureError("battle clip unexpectedly changed audio availability")
    temporary.replace(destination)
    hp_path = run_directory / "battle.hp.json"
    write_json(hp_path, shifted_sidecar(
        read_json(run_directory / bundle["files"]["hp"]["path"]), start,
    ))
    for key, path in (("battleVideo", destination), ("battleHp", hp_path)):
        bundle["files"][key] = {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
    presentation = {
        "version": CLIP_VERSION, "video": destination.name, "sidecar": hp_path.name,
        "startRawFrame": first_frame, "startRawSeconds": start,
        "startDetection": "first_in_game_frame_luma", "endTrimSeconds": 0,
        "audioTrimSeconds": start, "media": output_media,
        "sourceVideoSha256": bundle["files"]["video"]["sha256"],
    }
    bundle["defaultVideo"] = "battleVideo"
    bundle["presentation"] = presentation
    write_json(run_directory / "recording.json", bundle)
    return presentation
