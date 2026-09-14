import json

import pytest

from aoe2x.lab.errors import LiveCaptureError
from aoe2x.lab.live import _validate_capture
from aoe2x.lab.retention import validate_retained_statistics


def capture_fixture(tmp_path, terminal_counts=(0, 0), terminal_hp=(0, 0)):
    raw = tmp_path / "raw recordings"
    raw.mkdir()
    for extension, data in (("mov", b"video"), ("frames.bin", b"x" * 1000001),
                            ("meta.json", b"{}"), ("END", b"observed")):
        (raw / f"fight.{extension}").write_bytes(data)
    def row(t, counts, hp):
        return {"game_s": t, "side1": {"count": counts[0], "hp": hp[0]},
                "side2": {"count": counts[1], "hp": hp[1]}}
    # The camel dies first; its pending explosion then kills the final defender.
    payload = {"rows": [row(0, (2, 2), (150, 200)), row(5, (0, 1), (0, 20)),
                        row(6, terminal_counts, terminal_hp), row(7, terminal_counts, terminal_hp)]}
    (raw / "fight.hp.json").write_text(json.dumps(payload))
    plan = {"matchupId": "fight", "side2": {"count": 2, "slug": "flaming_camel_tatars"},
            "side3": {"count": 2, "slug": "paladin"}}
    return plan


def test_mutual_elimination_is_a_draw_at_the_last_armys_death(tmp_path):
    plan = capture_fixture(tmp_path)
    capture = _validate_capture(tmp_path, plan)
    assert capture["outcome"] == "mutual_elimination"
    assert capture["winnerOwner"] is None and capture["winnerSlug"] is None
    assert capture["survivors"] == capture["winnerHp"] == capture["signedRemainingHpPercent"] == 0
    assert capture["eliminationTimeSeconds"] == 6
    resumed = validate_retained_statistics(tmp_path, {"capture": capture}, (2, 2))
    assert resumed == capture


def test_surviving_defender_is_still_the_winner(tmp_path):
    plan = capture_fixture(tmp_path, (0, 1), (0, 20))
    capture = _validate_capture(tmp_path, plan)
    assert capture["winnerOwner"] == 3
    assert capture["signedRemainingHpPercent"] == -10
    assert capture["eliminationTimeSeconds"] == 5


@pytest.mark.parametrize("counts,hp", [((1, 1), (10, 20)), ((0, 0), (0, 20))])
def test_unfinished_or_inconsistent_telemetry_is_not_a_draw(tmp_path, counts, hp):
    plan = capture_fixture(tmp_path, counts, hp)
    with pytest.raises(LiveCaptureError):
        _validate_capture(tmp_path, plan)
    manifest = {"capture": {"startCounts": [2, 2], "artifacts": {"sidecar": "raw recordings/fight.hp.json"}}}
    with pytest.raises(ValueError):
        validate_retained_statistics(tmp_path, manifest, (2, 2))


def test_draw_still_requires_recorded_end_signal(tmp_path):
    plan = capture_fixture(tmp_path)
    (tmp_path / "raw recordings/fight.END").unlink()
    with pytest.raises(LiveCaptureError, match="missing"):
        _validate_capture(tmp_path, plan)
