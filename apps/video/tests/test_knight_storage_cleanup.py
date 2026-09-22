import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest
import finish_knight_consolidation as cleanup


def test_changed_source_is_preserved(tmp_path, monkeypatch):
    lab=tmp_path/'lab'; lab.mkdir()
    source=lab/'battle.mp4'; source.write_bytes(b'changed')
    monkeypatch.setattr(cleanup,'RUNS',lab)
    monkeypatch.setattr(cleanup,'DEST',tmp_path/'archive')
    candidate=dict(source=str(source),sourceRoot=str(lab),bytes=7,
                   sha256=hashlib.sha256(b'correct').hexdigest())
    with pytest.raises(ValueError,match='Changed source'):
        cleanup.validated_source(candidate)
    assert source.read_bytes()==b'changed'


def test_path_escape_cannot_be_retired(tmp_path,monkeypatch):
    lab=tmp_path/'lab'; lab.mkdir(); source=tmp_path/'outside.mp4'; source.write_bytes(b'keep')
    monkeypatch.setattr(cleanup,'RUNS',lab)
    monkeypatch.setattr(cleanup,'DEST',tmp_path/'archive')
    candidate=dict(source=str(source),sourceRoot=str(tmp_path),bytes=4,
                   sha256=hashlib.sha256(b'keep').hexdigest())
    with pytest.raises(ValueError,match='restricted'):
        cleanup.validated_source(candidate)
    assert source.exists()


def test_missing_frame_copy_blocks_cleanup_even_with_video_receipt(tmp_path,monkeypatch):
    archive=tmp_path/'archive'; archive.mkdir(); video=archive/'battle.mp4'; video.write_bytes(b'video')
    monkeypatch.setattr(cleanup,'DEST',archive)
    sha=hashlib.sha256(b'video').hexdigest()
    candidate=dict(replacement=[dict(path=str(video),bytes=5,sha256=sha),
                                dict(path=str(archive/'frames.bin'),bytes=8,sha256='missing')])
    receipts={str(video):dict(bytes=5,sha256=sha)}
    with pytest.raises(ValueError,match='missing'):
        cleanup.check_replacement(candidate,receipts)


def test_copy_receipt_cannot_hide_a_source_changed_after_inventory(tmp_path, monkeypatch):
    lab=tmp_path/'lab'; lab.mkdir(); source=lab/'battle.mp4'; source.write_bytes(b'original')
    original_time=source.stat().st_mtime_ns
    sha=hashlib.sha256(b'original').hexdigest()
    monkeypatch.setattr(cleanup,'RUNS',lab)
    monkeypatch.setattr(cleanup,'DEST',tmp_path/'archive')
    candidate=dict(source=str(source),sourceRoot=str(lab),bytes=8,sha256=sha)
    key=str(source.resolve()).casefold()
    receipts={key:dict(bytes=8,sha256=sha,verifiedAt=datetime.now(timezone.utc).isoformat())}
    source.write_bytes(b'modified')
    import os
    os.utime(source,ns=(original_time+1000000000,original_time+1000000000))
    with pytest.raises(ValueError,match='Changed source'):
        cleanup.validated_source(candidate,receipts,{key:original_time})
    assert source.read_bytes()==b'modified'
