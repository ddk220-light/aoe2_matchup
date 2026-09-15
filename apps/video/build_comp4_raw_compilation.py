"""Join verified Comp4 gameplay for review, preserving every canonical capture.

Reads status.json so accepted retakes replace rejected takes. Only the verified
loading/editor lead-in is trimmed. No overlay, intro, or extra music is added.
Temporary MOVs use PCM audio to avoid a second lossy audio generation at joins.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import time
from pathlib import Path

from overlay.ffutil import find_ffmpeg, find_ffprobe


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root, out = args.campaign.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    segments = out / "segments"
    segments.mkdir(exist_ok=True)
    ff, probe = find_ffmpeg(), find_ffprobe()
    if not ff or not probe:
        raise RuntimeError("FFmpeg and FFprobe are required")
    manifest, status = read(root / "manifest.json"), read(root / "status.json")
    if status["state"] != "COMPLETE" or status.get("failed"):
        raise RuntimeError("Campaign must be complete with no unresolved failures")
    if len(status["completed"]) != len(manifest["jobs"]):
        raise RuntimeError("Completed captures do not match the roster")

    def inspect(path):
        return json.loads(subprocess.check_output([
            probe, "-v", "error", "-show_format", "-show_streams",
            "-show_chapters", "-of", "json", str(path)], text=True))

    def progress(state, **values):
        data = {"state": state, "updatedAt": time.time(), **values}
        write(out / "status.json", data)
        print(json.dumps(data), flush=True)

    def run(arguments, log_name):
        with (out / log_name).open("w", encoding="utf-8") as log:
            subprocess.run([ff, "-hide_banner", "-y", "-v", "warning",
                            *map(str, arguments)], stdout=log, stderr=log, check=True)

    clips, total_frames = [], 0
    for index, job in enumerate(manifest["jobs"], 1):
        capture = Path(status["completed"][job["id"]]["capture"])
        proof = read(capture / "validation.json")
        source = capture / "raw.mp4"
        if proof["state"] != "VERIFIED":
            raise RuntimeError(f"Unverified capture: {capture}")
        source_hash = digest(source)
        if source_hash != proof["files"]["raw.mp4"]["sha256"]:
            raise RuntimeError(f"Source hash changed: {source}")
        media = inspect(source)
        video = next(s for s in media["streams"] if s["codec_type"] == "video")
        audio = next(s for s in media["streams"] if s["codec_type"] == "audio")
        if (video["width"], video["height"], video["r_frame_rate"]) != (2560, 1440, "60/1"):
            raise RuntimeError(f"Unexpected video format: {source}")
        if audio["sample_rate"] != "48000" or audio["channels"] != 2:
            raise RuntimeError(f"Unexpected audio format: {source}")
        # First complete video frame at/after the verified gameplay start.
        start_frame = math.ceil(proof["videoStartSeconds"] * 60 - 1e-6)
        frame_count = int(video["nb_frames"]) - start_frame
        if frame_count <= 0:
            raise RuntimeError(f"Invalid trim: {source}")
        target = segments / f"{index:02d}.mov"
        receipt = target.with_suffix(".json")
        signature = {"sourceSha256": source_hash, "startFrame": start_frame,
                     "frames": frame_count, "encode": "nvenc-p4-cq21-max20m-pcm-v1"}
        cached = read(receipt) if receipt.exists() else {}
        valid_cache = (target.exists() and cached.get("inputs") == signature
                       and cached.get("sha256") == digest(target))
        if not valid_cache:
            if shutil.disk_usage(out).free < 4 * 2**30:
                raise RuntimeError("Less than 4 GiB free; stopping before source files are at risk")
            progress("TRIMMING", clip=index, total=len(manifest["jobs"]), matchup=job["id"])
            samples = frame_count * 800  # 48000 samples / 60 frames.
            run(["-threads", "2", "-ss", f"{start_frame / 60:.9f}", "-i", source,
                 "-map", "0:v:0", "-map", "0:a:0", "-map_metadata", "-1",
                 "-vf", "setpts=PTS-STARTPTS", "-af",
                 f"asetpts=PTS-STARTPTS,apad=whole_len={samples},atrim=end_sample={samples}",
                 "-frames:v", frame_count, "-t", f"{frame_count / 60:.9f}",
                 "-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "21",
                 "-b:v", "0", "-maxrate", "20M", "-bufsize", "40M", "-pix_fmt", "yuv420p",
                 "-r", "60", "-video_track_timescale", "15360",
                 "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", target],
                f"encode-{index:02d}.log")
            segment_video = next(s for s in inspect(target)["streams"] if s["codec_type"] == "video")
            if int(segment_video["nb_frames"]) != frame_count:
                raise RuntimeError(f"Trim frame count mismatch: {target}")
            write(receipt, {"inputs": signature, "sha256": digest(target)})
        clips.append({"id": job["id"], "title": f"{job['opponent']['civ']} - {job['opponent']['label']}",
                      "source": str(source), "sourceSha256": source_hash,
                      "startFrameInSource": start_frame, "startFrame": total_frames,
                      "frames": frame_count, "segment": str(target)})
        total_frames += frame_count

    write(out / "clips.json", {"campaign": str(root), "fps": 60, "frames": total_frames, "clips": clips})
    concat = out / "concat.txt"
    concat.write_text("".join("file '" + Path(c["segment"]).as_posix().replace("'", "'\\''")
                              + f"'\nduration {c['frames'] / 60:.9f}\n" for c in clips), encoding="utf-8")
    metadata = out / "chapters.ffmeta"
    chapter_lines = [";FFMETADATA1", "title=Champi Four Civilizations - All 74 Raw Matchups"]
    text_chapters = []
    for c in clips:
        title = c["title"].replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#")
        chapter_lines.extend(["[CHAPTER]", "TIMEBASE=1/60", f"START={c['startFrame']}",
                              f"END={c['startFrame'] + c['frames']}", f"title={title}"])
        seconds = c["startFrame"] // 60
        text_chapters.append(f"{seconds // 60:02d}:{seconds % 60:02d} {c['title']}")
    metadata.write_text("\n".join(chapter_lines) + "\n", encoding="utf-8")
    (out / "chapters.txt").write_text("\n".join(text_chapters) + "\n", encoding="utf-8")
    partial = out / "Champi_Four_Civilizations_All_74_Raw_Matchups.partial.mp4"
    final = out / "Champi_Four_Civilizations_All_74_Raw_Matchups.mp4"
    segment_bytes = sum(Path(c["segment"]).stat().st_size for c in clips)
    if shutil.disk_usage(out).free < segment_bytes + 2 * 2**30:
        raise RuntimeError("Insufficient disk space to safely assemble the final")
    progress("ASSEMBLING", clips=len(clips), duration=total_frames / 60)
    run(["-f", "concat", "-safe", "0", "-i", concat, "-i", metadata,
         "-map", "0:v:0", "-map", "0:a:0", "-map_metadata", "1", "-map_chapters", "1",
         "-c:v", "copy", "-video_track_timescale", "15360", "-c:a", "aac",
         "-ar", "48000", "-ac", "2", "-b:a", "192k", "-af", "aresample=async=1:first_pts=0",
         "-movflags", "+faststart", partial], "assemble.log")
    progress("VERIFYING", clips=len(clips), duration=total_frames / 60)
    final_media = inspect(partial)
    final_video = next(s for s in final_media["streams"] if s["codec_type"] == "video")
    if int(final_video["nb_frames"]) != total_frames:
        raise RuntimeError("Final frame count does not equal all trimmed sources")
    if len(final_media["chapters"]) != len(clips):
        raise RuntimeError("Missing final chapters")
    if abs(float(final_media["format"]["duration"]) - total_frames / 60) > 0.1:
        raise RuntimeError("Final duration mismatch")
    run(["-v", "error", "-xerror", "-threads", "4", "-i", partial,
         "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"], "decode-qa.log")
    # Windows readers can briefly hold the finished mux while visual QA extracts
    # a frame. Retry only the rename; never re-encode a video that already passed.
    for attempt in range(31):
        try:
            partial.replace(final)
            break
        except PermissionError as error:
            if getattr(error, "winerror", None) != 32 or attempt == 30:
                raise
            time.sleep(1)
    final_media["format"]["filename"] = str(final)
    write(out / "validation.json", {"state": "VERIFIED", "file": str(final),
          "sha256": digest(final), "bytes": final.stat().st_size,
          "durationSeconds": float(final_media["format"]["duration"]),
          "clips": len(clips), "frames": total_frames, "fullDecodePassed": True,
          "sourceHashesVerified": True, "rawsAndFramesPreserved": True,
          "media": final_media})
    progress("COMPLETE", file=str(final), clips=len(clips), duration=total_frames / 60)


if __name__ == "__main__":
    main()
