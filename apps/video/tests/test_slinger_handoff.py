"""A Slinger handoff cannot overtake outstanding exports or copies."""
from pathlib import Path

import prepare_inca_slinger_standard as handoff
from run_champi_comparison_capture import read, save


def completed_predecessor(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, 'PREDECESSOR', tmp_path)
    campaigns, packages = [], {}
    for slug in handoff.ORDER:
        work = tmp_path / slug
        job = slug + '_trial'
        campaigns.append(dict(slug=slug, workDirectory=str(work), total=1))
        save(work / 'manifest.json', dict(matchups=[dict(id=job)]))
        save(work / 'capture/status.json', dict(state='COMPLETE', completed=1, failed=0,
            pendingExports=0, results=[dict(jobId=job, status='verified')]))
        packages[slug] = dict(state='COMPLETE', verified=1)
    save(tmp_path / 'queue.json', dict(total=6, campaigns=campaigns))
    save(tmp_path / 'status.json', dict(state='COMPLETE', verified=6, failures=[]))
    save(tmp_path / 'delivery/status.json', dict(state='COMPLETE', verified=6, packages=packages))


def test_waits_for_every_export(tmp_path, monkeypatch):
    completed_predecessor(tmp_path, monkeypatch)
    assert handoff.predecessor_complete()
    path = tmp_path / handoff.ORDER[-1] / 'capture/status.json'
    state = read(path)
    state['pendingExports'] = 1
    save(path, state)
    assert not handoff.predecessor_complete()


def test_waits_for_all_copies_and_conditional_decisions(tmp_path, monkeypatch):
    completed_predecessor(tmp_path, monkeypatch)
    path = tmp_path / 'delivery/status.json'
    state = read(path)
    state['packages'][handoff.ORDER[-1]]['state'] = 'COPYING'
    save(path, state)
    assert not handoff.predecessor_complete()
    completed_predecessor(tmp_path, monkeypatch)
    path = tmp_path / 'queue.json'
    queue = read(path)
    queue['campaigns'][-1]['conditionalDonut'] = dict(pending=True)
    save(path, queue)
    assert not handoff.predecessor_complete()
