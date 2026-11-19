import json

import run_jarl_stall_retakes as worker


def configure(monkeypatch, tmp_path, state):
    root = tmp_path/'root'
    mounted = root/'mounted'
    work = root/'retakes'
    mounted.mkdir(parents=True)
    work.mkdir()
    (mounted/'status.json').write_text(json.dumps({'state': state}))
    monkeypatch.setattr(worker, 'ROOT', root)
    monkeypatch.setattr(worker, 'MOUNTED', mounted)
    monkeypatch.setattr(worker, 'WORK', work)
    return mounted, work


def test_user_pause_never_acquires_game(monkeypatch, tmp_path):
    mounted, _ = configure(monkeypatch, tmp_path, 'COMPLETE')
    (mounted/'PAUSE').touch()
    monkeypatch.setattr(worker, 'acquire', lambda _: (_ for _ in ()).throw(AssertionError('must not lock')))
    assert worker.wait_for_game() is None


def test_active_capture_is_not_interrupted(monkeypatch, tmp_path):
    mounted, _ = configure(monkeypatch, tmp_path, 'CAPTURING')
    monkeypatch.setattr(worker, 'acquire', lambda _: (_ for _ in ()).throw(AssertionError('must not lock')))
    monkeypatch.setattr(worker.time, 'sleep', lambda _: (mounted/'PAUSE').touch())
    assert worker.wait_for_game() is None


def test_busy_italian_handoff_releases_queue_gate(monkeypatch, tmp_path):
    mounted, _ = configure(monkeypatch, tmp_path, 'COMPLETE')
    closed = []
    class Handle:
        def close(self):
            closed.append(True)
    monkeypatch.setattr(worker, 'acquire', lambda p: Handle() if p.name == 'queue.lock' else None)
    monkeypatch.setattr(worker.time, 'sleep', lambda _: (mounted/'PAUSE').touch())
    assert worker.wait_for_game() is None
    assert closed == [True]


def test_real_windows_lock_contention_is_not_a_read_error(tmp_path):
    from run_italian_mounted_crossbow_after_expansion import acquire
    lock_path = tmp_path/'owner.lock'
    first = acquire(lock_path)
    assert first is not None
    try:
        assert acquire(lock_path) is None
    finally:
        first.close()
    next_owner = acquire(lock_path)
    assert next_owner is not None
    next_owner.close()
