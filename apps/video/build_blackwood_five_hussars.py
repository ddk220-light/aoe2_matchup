"""Build the local Blackwood revision from new melee and existing ranged footage.

`run` follows the active capture, renders only 43 changed/missing overlays, then
assembles all 73 chapters using the approved intro. No publishing or cleanup.
Individual retained chapter files are preferred over decoding the old full video.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import math
import os
import subprocess
import sys
import time
from pathlib import Path

from aoe2x.lab.io import read_json, write_json, utc_now
from blackwood_five_hussars import ROOT, LAB, REPORT, BASELINE, compare
from finish_pending_production import pause_check
from overlay.battle_end import terminal_row
from overlay.ffutil import find_ffmpeg, find_ffprobe
from verify_recorded_screen import verify

OUT = LAB / "compilations/blackwood-archer-five-hussars/final"
OVERLAYS = REPORT / "overlays"
SOURCES = REPORT / "media-source-status.json"
STATE = REPORT / "production-status.json"


def stage(name, **extra):
    write_json(STATE, {"state": name, "updatedAt": utc_now(), "pid": os.getpid(), **extra})
    print(name, extra, flush=True)


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def assembly_inputs(clips, concat, metadata):
    """Bind a completed decode to these exact inputs before renaming the file."""
    return {"concatSha256": digest(concat), "metadataSha256": digest(metadata),
            "sources": [{"path": c["source"], "sha256": c.get("sourceSha256") or digest(c["source"])}
                        for c in clips]}


def probe(path):
    import json
    return json.loads(subprocess.check_output([find_ffprobe(), "-v", "error", "-show_format",
                                              "-show_streams", "-show_chapters", "-of", "json", str(path)]))


def call_media(args, log):
    pause_check()
    child = subprocess.Popen([find_ffmpeg(), "-hide_banner", "-y", "-v", "warning", *map(str, args)],
                             stdout=log, stderr=log)
    while child.poll() is None:
        time.sleep(2)
        pause_check()
    if child.returncode:
        raise subprocess.CalledProcessError(child.returncode, child.args)


def media_sources():
    baseline = read_json(BASELINE)
    capture_path = REPORT / "status.json"
    capture = read_json(capture_path) if capture_path.exists() else {"state": "RUNNING", "results": []}
    corrected_ids = {e["baselineJobId"] for e in baseline["entries"] if e["mode"] == "reuse" and e["baselineJobId"] != e["originalJobId"]}
    repaired = read_json(LAB / "campaigns/cost-repairs-v2/status.json")
    results = capture["results"] + [r for r in repaired["results"] if r["jobId"] in corrected_ids]
    write_json(SOURCES, {"state": capture["state"], "results": results})
    return capture


def verify_completed(capture):
    for row in capture["results"]:
        if row["status"] != "verified":
            continue
        run = LAB / "runs" / row["jobId"] / "live/run_001"
        proof = run / "screen-verification.json"
        recording = read_json(run / "recording.json")
        if proof.exists():
            cached = read_json(proof)
            if (cached.get("passed") and cached.get("expected") == cached.get("actual") == 5
                    and cached.get("framesSha256") == recording["files"]["frames"]["sha256"]):
                continue
        with contextlib.redirect_stdout(io.StringIO()):
            verify(run, expected=5)


def render_following_capture(workers=3):
    pause_check()
    media_sources()
    stage("CAPTURING_AND_RENDERING", overlayWorkers=workers)
    log_path = REPORT / "overlays-worker.log"
    with log_path.open("a", encoding="utf-8") as log:
        child = subprocess.Popen([sys.executable, "-u", str(ROOT / "apps/video/render_campaign_overlays.py"),
                                  "--manifest", str(ROOT / "aoe2lab.overlays.blackwood-five-hussars.json"),
                                  "--output", str(OVERLAYS), "--workers", str(workers),
                                  "--recording-status", str(SOURCES)], cwd=ROOT, stdout=log, stderr=log)
        previous_count = -1
        while child.poll() is None:
            current = media_sources()
            verify_completed(current)
            count = current.get("completed", 0)
            if count != previous_count:
                compare()
                previous_count = count
            time.sleep(5)
            pause_check()
        if child.returncode:
            raise subprocess.CalledProcessError(child.returncode, child.args)
    current = media_sources()
    verify_completed(current)
    comparison = compare()
    assert current.get("completed") == 40 and not current.get("failed"), "captures need attention"
    assert read_json(OVERLAYS / "status.json")["state"] == "COMPLETE", "overlays need attention"
    assert comparison["state"] == "COMPLETE"


def normalized_clip(source, output, log, *, start=0, duration=None):
    """Accurate seeking/re-encoding only for new trims or missing old chapters."""
    duration = duration or float(probe(source)["format"]["duration"])
    receipt = output.with_suffix(".source.json")
    provenance = {"source": str(source), "sourceBytes": Path(source).stat().st_size,
                  "sourceModifiedNs": Path(source).stat().st_mtime_ns, "start": start, "duration": duration}
    if output.exists() and receipt.exists() and read_json(receipt) == provenance:
        return output
    partial = output.with_name(output.stem + ".partial.mp4")
    # The old concatenation has fractional chapter PTS. Accurate seeking plus
    # the fps filter retained ONE predecessor frame at both recovered cuts,
    # confirmed against the static opponent panel. Remove that boundary frame
    # and the same 1/60 s of audio; fresh battle clips (start=0) are unaffected.
    guard = 1 / 60 if start else 0
    video_filter = ("trim=start_frame=1,setpts=PTS-STARTPTS," if guard else "") + "scale=2560:1440:flags=lanczos,fps=60,format=yuv420p"
    audio_filter = ["-af", f"atrim=start={guard},asetpts=PTS-STARTPTS"] if guard else []
    call_media(["-ss", start, "-i", source, "-t", duration - guard, "-map", "0:v:0", "-map", "0:a:0",
                "-vf", video_filter, *audio_filter, "-c:v", "h264_nvenc",
                "-preset", "p4", "-cq", "18", "-video_track_timescale", "15360",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-movflags", "+faststart", partial], log)
    info = probe(partial)
    assert abs(float(info["format"]["duration"]) - duration) < .12
    partial.replace(output)
    write_json(receipt, provenance)
    if guard:
        write_json(output.with_suffix(".recovery-trim.json"), {"requestedStartSeconds": start,
                   "requestedDurationSeconds": duration, "removedLeadingFrames": 1,
                   "removedAudioSeconds": guard, "outputDurationSeconds": float(info["format"]["duration"])})
    return output


def stamp(value):
    seconds = int(value)
    return f"{seconds // 3600}:{seconds // 60 % 60:02}:{seconds % 60:02}" if seconds >= 3600 else f"{seconds // 60:02}:{seconds % 60:02}"


def assemble():
    baseline = read_json(BASELINE)
    comparison = compare()
    assert comparison["state"] == "COMPLETE", "all 40 captures must be verified before assembly"
    overlays = read_json(OVERLAYS / "status.json")
    assert overlays["state"] == "COMPLETE" and overlays["completed"] == 43
    OUT.mkdir(parents=True, exist_ok=True)
    stage("ASSEMBLING")
    rows_by_id = {r["jobId"]: r for r in comparison["rows"]}
    intro = LAB / "compilations/blackwood-archer-unique-units/final/intro-1440p60.mp4"
    if not intro.exists():
        intro = LAB / "compilations/blackwood-archer-unique-units/intro-v1/blackwood-archer-intro.mp4"
    results = []
    with (OUT / "render.log").open("a", encoding="utf-8") as log:
        if probe(intro)["streams"][0]["width"] != 2560:
            intro = normalized_clip(intro, OUT / "intro-1440p60.mp4", log)
        cursor = float(probe(intro)["format"]["duration"])
        clips = [{"title": "Introduction", "source": str(intro), "startSeconds": 0, "durationSeconds": cursor}]
        for entry in baseline["entries"]:
            row = rows_by_id[entry["jobId"]]
            run = LAB / "runs" / entry["jobId"] / "live/run_001"
            if entry["mode"] == "reuse" and entry["baselineJobId"] == entry["originalJobId"]:
                source = Path(entry["originalChapter"]["source"])
                if not source.exists():
                    source = normalized_clip(Path(baseline["previousFullVideo"]), OUT / (entry["jobId"] + "-reused.mp4"), log,
                                             start=entry["originalChapter"]["startSeconds"], duration=entry["originalChapter"]["durationSeconds"])
            else:
                source = run / "unit-hp-overlay/battle-with-unit-hp.mp4"
                assert source.is_file()
                timeline = read_json(run / "unit-hp-overlay/units.json")
                end = terminal_row(timeline["rows"])
                duration = (math.ceil(end["videoSeconds"] * 60) + 1) / 60
                if float(probe(source)["format"]["duration"]) > duration + .5:
                    source = normalized_clip(source, OUT / (entry["jobId"] + "-battle-end.mp4"), log, duration=duration)
            media = probe(source)
            video = next(s for s in media["streams"] if s["codec_type"] == "video")
            audio = next(s for s in media["streams"] if s["codec_type"] == "audio")
            assert (video["width"], video["height"], video["r_frame_rate"]) == (2560, 1440, "60/1"), source
            assert video["codec_name"] == "h264" and audio["sample_rate"] == "48000", source
            duration = float(media["format"]["duration"])
            result = {**row, "title": entry["civ"] + " - " + entry["unit"], "source": str(source),
                      "sourceSha256": digest(source), "startSeconds": cursor, "durationSeconds": duration, "timestamp": stamp(cursor)}
            clips.append(result)
            results.append(result)
            cursor += duration
        assert len(results) == 73
        concat = OUT / "concat.txt"
        concat.write_text("".join("file '" + Path(c["source"]).as_posix().replace("'", "'\\''") + "'\n" for c in clips), encoding="utf-8")
        metadata = OUT / "chapters.ffmeta"
        content = ";FFMETADATA1\ntitle=Elite Blackwood Archer vs 73 Unique Units - Five Hussars\n"
        for clip in clips:
            content += f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(clip['startSeconds']*1000)}\nEND={round((clip['startSeconds']+clip['durationSeconds'])*1000)}\ntitle={clip['title']}\n"
        metadata.write_text(content, encoding="utf-8")
        video = OUT / "blackwood-archer-five-hussars-complete.mp4"
        partial = OUT / "blackwood-archer-five-hussars-complete.partial.mp4"
        validation_path = OUT / "assembly-validation.json"
        inputs = assembly_inputs(clips, concat, metadata)
        validation = read_json(validation_path) if validation_path.exists() else {}
        # A preview reader can temporarily hold the completed partial on Windows.
        # Preserve the successful decode so retrying that rename need not encode
        # and decode again. Any input or output byte change invalidates this cache.
        validated = (partial.exists() and validation.get("fullDecode") == "passed"
                     and validation.get("inputs") == inputs
                     and validation.get("videoSha256") == digest(partial))
        if not validated:
            call_media(["-f", "concat", "-safe", "0", "-i", concat, "-i", metadata, "-map", "0:v:0", "-map", "0:a:0",
                        "-map_metadata", "1", "-map_chapters", "1", "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-b:a", "192k",
                        "-af", "aresample=async=1", "-movflags", "+faststart", partial], log)
        info = probe(partial)
        assert abs(float(info["format"]["duration"]) - cursor) < 2 and len(info["chapters"]) == 74
        if not validated:
            stage("VALIDATING_FULL_VIDEO", expectedSeconds=cursor)
            call_media(["-xerror", "-threads", "8", "-i", partial, "-f", "null", "-"], log)
            write_json(validation_path, {"fullDecode": "passed", "validatedAt": utc_now(),
                                         "inputs": inputs, "videoSha256": digest(partial)})
        else:
            stage("FINALIZING_VALIDATED_VIDEO", expectedSeconds=cursor)
        partial.replace(video)
        info["format"]["filename"] = str(video)
    description = ("Elite Blackwood Archer vs 73 Unique-Unit Matchups | AoE2 DE\n\n"
                   "Can a smaller front line change the results? Blackwood Archers receive five Spanish Hussars against melee units in this version. "
                   "Ranged-versus-ranged chapters reuse the previous recordings, including cost corrections.\n\n"
                   "Audited Imperial unit costs, equal resources up to 5,000, and a maximum of 27 main units per side. Whole-unit rounding applies. "
                   "Hussars are outside the resource budget. Blackwood Archer cost is per individual archer, accounting for pair production.\n\n"
                   "Try your own matchup: https://aoe2matchup.com/?civ1=Tupi&unit1=elite_blackwood_archer_tupi&age1=Imperial\n\n"
                   "WIN/LOSS is from Blackwood Archer's perspective; HP is the winning main army's remaining HP.\n\n00:00 Introduction\n")
    for row in results:
        result = "WIN" if row["newResult"] == "Blackwood win" else "LOSS" if row["newResult"] == "Blackwood loss" else "DRAW"
        description += f"{row['timestamp']} {row['unit']} | {result} | {row['newWinnerHp']:.0f} HP\n"
    description += "\n#AoE2 #AoE2DE #BlackwoodArcher #Tupi #RTS #BattleSimulation #UnitCounters #StrategyGaming\n"
    assert len(description) <= 5000
    (OUT / "youtube-description-draft.txt").write_text(description, encoding="utf-8")
    write_json(OUT / "manifest.json", {"output": str(video), "generatedAt": utc_now(), "matchups": 73, "chapters": 74,
                                      "newMeleeRecordings": 40, "reusedRangedRecordings": 33, "winnerFlips": comparison["winnerFlips"],
                                      "originalVideoWinnerFlips": comparison["originalVideoWinnerFlips"],
                                      "priorCostCorrectionWinnerFlips": comparison["priorCostCorrectionWinnerFlips"],
                                      "expectedSeconds": cursor, "media": info, "fullDecode": "passed", "videoSha256": digest(video),
                                      "reviewStatus": "Automated checks passed; human visual review pending", "results": results})
    stage("READY_FOR_REVIEW", video=str(video), winnerFlips=comparison["winnerFlips"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "overlays", "assemble"))
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    try:
        if args.command in ("run", "overlays"):
            render_following_capture(args.workers)
        if args.command in ("run", "assemble"):
            assemble()
    except Exception as error:
        stage("NEEDS_ATTENTION", error=repr(error))
        raise
