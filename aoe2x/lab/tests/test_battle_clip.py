from __future__ import annotations

import json
import subprocess
import sys
import wave

import pytest

from aoe2x.lab.battle_clip import prepare_battle_clip, shifted_sidecar
from aoe2x.lab.config import load_config
from aoe2x.lab.recording import write_recording_bundle


def test_clip_sidecar_shifts_video_offsets_without_changing_measured_rows():
    source = {"video_game_start_s": 6.215, "end_video_s": 53.403,
              "clock": "video", "rows": [{"game_s": 20, "hp": 50}]}
    result = shifted_sidecar(source, 8.9)
    assert result["video_game_start_s"] == pytest.approx(-2.685)
    assert result["end_video_s"] == pytest.approx(44.503)
    assert result["rows"] == source["rows"]
    assert source["video_game_start_s"] == 6.215


def test_actual_clip_starts_on_first_game_frame_trims_audio_and_keeps_end(tmp_path, monkeypatch):
    import cv2
    import numpy as np

    sys.path.insert(0, str(load_config().project_root / "apps/video"))
    from overlay.ffutil import find_ffmpeg
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        pytest.skip("ffmpeg unavailable")
    # One second of dark menu + two seconds of bright, individually identifiable frames.
    source = tmp_path / "fixture.avi"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"MJPG"), 30, (64, 64))
    assert writer.isOpened()
    for frame in range(90):
        writer.write(np.full((64, 64, 3), 20 if frame < 30 else 120 + frame, dtype=np.uint8))
    writer.release()
    # The first second has silence; the battle has a tone. A silent clip start
    # exposes forgetting to trim audio even if the video and duration look correct.
    samples = np.zeros(48000 * 3, dtype=np.int16)
    samples[48000:] = (6000 * np.sin(2 * np.pi * 440 * np.arange(96000) / 48000)).astype(np.int16)
    wav = tmp_path / "fixture.wav"
    with wave.open(str(wav), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(48000)
        output.writeframes(samples.tobytes())
    raw = tmp_path / "raw recordings"
    raw.mkdir()
    video = raw / "fight.mov"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(source), "-i", str(wav),
                    "-c:v", "copy", "-c:a", "pcm_s16le", str(video)], check=True)
    for suffix in (".frames.bin", ".meta.json", ".END"):
        (raw / f"fight{suffix}").write_bytes(b"fixture")
    (raw / "fight.hp.json").write_text(json.dumps({"clock": "video", "video_game_start_s": 1, "end_video_s": 2.8, "rows": []}))
    (tmp_path / "fight.aoe2scenario").write_bytes(b"scenario")
    plan = {"matchupId": "fight", "jobId": "job", "planHash": "hash", "side2": {}, "side3": {}}
    write_recording_bundle(tmp_path, plan, {"artifacts": {"video": "raw recordings/fight.mov"}})
    result = prepare_battle_clip(tmp_path, plan)
    assert result["startRawFrame"] == 30
    assert result["audioTrimSeconds"] == 1
    assert result["media"]["durationSeconds"] == pytest.approx(2, abs=0.05)
    cap = cv2.VideoCapture(str(tmp_path / result["video"]))
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 60
    ok, first = cap.read()
    assert ok and float(first.mean()) == pytest.approx(150, abs=3)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 59)
    ok, last = cap.read()
    assert ok and float(last.mean()) == pytest.approx(209, abs=3)
    cap.release()
    audio = subprocess.check_output([ffmpeg, "-v", "error", "-i", str(tmp_path / result["video"]),
                                     "-t", "0.2", "-f", "s16le", "-ac", "1", "-"])
    assert np.abs(np.frombuffer(audio, dtype=np.int16).astype(float)).mean() > 1000
    # Fully reusable without re-encoding, probing, or touching the game.
    monkeypatch.setattr("aoe2x.lab.battle_clip.subprocess.run", lambda *a, **k: pytest.fail("unexpected re-encode"))
    assert prepare_battle_clip(tmp_path, plan) == result
