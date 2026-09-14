"""The evidence gate must reject a default screen or an unusable early snapshot."""
import json
import struct
from types import SimpleNamespace

import pytest

import verify_recorded_screen as screen


@pytest.mark.parametrize("count,early_ms,passed", [(5, 14, True), (9, 14, False), (5, 4000, False)])
def test_recorded_screen_count_and_game_clock_gate(tmp_path, monkeypatch, count, early_ms, passed):
    run = tmp_path / "job/live/run_001"
    run.mkdir(parents=True)
    (run.parent.parent / "plan.json").write_text(json.dumps({"side2": {"count": 2}, "side3": {"count": 3}}))
    (run / "recording.json").write_text(json.dumps({"files": {"frames": {"path": "frames.bin", "sha256": "fixture-hash"}}}))
    (run / "frames.bin").write_bytes(struct.pack("<I", 1) + b"x")
    frames = [SimpleNamespace(patch=b"s" * (screen.SNAP_RESEED + 1), time=0), SimpleNamespace(patch=b"p", time=early_ms)]
    monkeypatch.setattr(screen, "pb", SimpleNamespace(FrameSequence=SimpleNamespace(FromString=lambda data: SimpleNamespace(frame=frames))))

    def seed(path, doc, entities):
        for owner, n, master, hp in ((2, 2, 2581, 25), (3, 3, 1811, 125), (4, count, 448, 95)):
            for i in range(n):
                entities[owner * 100 + i] = {"__type__": 12, 1: master, 2: owner, 12: hp}
        return None, 1

    monkeypatch.setattr(screen, "D", SimpleNamespace(Doc=lambda: None, seed_from_snapshot=seed, apply_patch=lambda *args: None))
    if passed:
        result = screen.verify(run)
        assert result["passed"] and result["actual"] == 5
        assert result["framesSha256"] == "fixture-hash" and result["gameMs"] == 14
        assert json.loads((run / "screen-verification.json").read_text()) == result
    else:
        with pytest.raises(ValueError, match="Expected 5|No early-game"):
            screen.verify(run)
        assert not (run / "screen-verification.json").exists()
