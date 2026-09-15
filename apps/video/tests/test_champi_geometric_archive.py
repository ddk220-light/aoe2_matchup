"""Exercise archive conflict and interrupted-prune recovery with disposable files."""

from pathlib import Path

import pytest

import archive_champi_geometric as archive


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    out, runs, destination = (tmp_path / p for p in ("work", "runs", "archive"))
    destination.mkdir()
    monkeypatch.setattr(archive, "OUT", out)
    monkeypatch.setattr(archive, "RUNS", runs.resolve())
    monkeypatch.setattr(archive, "DEST", destination)
    job = "champi_geometric_test"
    source = runs / job / "live/run_001"
    source.mkdir(parents=True)
    files = {}
    for kind, filename in (("video", "battle.mp4"), ("frames", "frames.bin")):
        path = source / filename
        path.write_bytes(filename.encode())
        files[kind] = dict(
            source=str(path),
            path=filename,
            bytes=path.stat().st_size,
            sha256=archive.digest(path),
        )
    (source / "keep.json").write_text("{}")
    row = dict(
        jobId=job,
        name="test",
        plan={"side2": {"civ": "Incas"}},
        files=files,
        recording={"files": {"video": files["video"]}},
    )
    monkeypatch.setattr(archive, "prepare", lambda p: row)
    archive.save(out / "manifest.json", {"matchups": [{"id": job}]})
    archive.save(out / "baseline.json", {"original": True})
    archive.save(
        out / "capture/status.json",
        {
            "results": [
                {"jobId": job, "status": "verified", "runDirectory": str(source)}
            ]
        },
    )
    return out, source, destination / "champi-geometric-incas", job


def test_verified_copy_prunes_only_media_and_is_idempotent(bundle):
    out, source, destination, job = bundle
    archive.archive_verified()
    assert (source / "keep.json").exists()
    assert not (source / "battle.mp4").exists()
    assert not (source / "frames.bin").exists()
    assert (destination / "battle.mp4").read_bytes() == b"battle.mp4"
    assert (destination / "frames.bin").read_bytes() == b"frames.bin"
    first = archive.read(out / "archive-status.json")
    assert first["completed"][job]["phase"] == "complete"
    archive.archive_verified()
    assert archive.read(out / "archive-status.json") == first


def test_conflicting_archive_preserves_sources(bundle):
    _, source, destination, _ = bundle
    destination.mkdir()
    (destination / "battle.mp4").write_bytes(b"different video")
    with pytest.raises(ValueError, match="Archive conflict"):
        archive.archive_verified()
    assert (source / "battle.mp4").exists()
    assert (source / "frames.bin").exists()


def test_interrupted_prune_resumes_using_verified_index(bundle, monkeypatch):
    out, source, destination, job = bundle
    original_unlink = Path.unlink

    def interrupted(path, *args, **kwargs):
        if path == source / "frames.bin":
            raise OSError("simulated interruption")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", interrupted)
    with pytest.raises(OSError, match="simulated interruption"):
        archive.archive_verified()
    assert (
        archive.read(out / "archive-status.json")["completed"][job]["phase"]
        == "copied_verified"
    )
    assert not (source / "battle.mp4").exists()
    monkeypatch.setattr(Path, "unlink", original_unlink)

    def cannot_prepare(_):
        raise AssertionError("Must recover from archive index, not pruned source")

    monkeypatch.setattr(archive, "prepare", cannot_prepare)
    archive.archive_verified()
    assert not (source / "frames.bin").exists()
    assert (destination / "battle.mp4").exists()
    assert (
        archive.read(out / "archive-status.json")["completed"][job]["phase"]
        == "complete"
    )
