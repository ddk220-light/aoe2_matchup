"""A stale completion summary must never activate a new cost catalog mid-run."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_mounted_crossbow_capture import guards_complete


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def completed_queue(root):
    campaigns = []
    for civ in ('byzantines', 'danes', 'saxons', 'varangians', 'vikings'):
        rows = [{'id': f'{civ}_{i}'} for i in range(77)]
        write(root / civ / 'manifest.json', {'matchups': rows})
        write(root / civ / 'capture/status.json', dict(state='COMPLETE', completed=77,
            failed=0, pendingExports=0,
            results=[dict(jobId=r['id'], status='verified') for r in rows]))
        campaigns.append({'key': civ})
    write(root / 'queue.json', {'total': 385, 'campaigns': campaigns})
    write(root / 'status.json', {'state': 'COMPLETE', 'verified': 385})


def test_all_receipts_required(tmp_path):
    completed_queue(tmp_path)
    assert guards_complete(tmp_path)
    path = tmp_path / 'vikings/capture/status.json'
    state = json.loads(path.read_text()); state['pendingExports'] = 1
    write(path, state)
    assert not guards_complete(tmp_path)


def test_duplicate_cannot_hide_missing_matchup(tmp_path):
    completed_queue(tmp_path)
    path = tmp_path / 'danes/capture/status.json'
    state = json.loads(path.read_text()); state['results'][-1] = state['results'][0]
    write(path, state)
    assert not guards_complete(tmp_path)


def test_live_queue_never_activates(tmp_path):
    completed_queue(tmp_path)
    write(tmp_path / 'status.json', {'state': 'CAPTURING', 'verified': 385})
    assert not guards_complete(tmp_path)


def test_append_rejects_active_queue_before_catalog_changes(tmp_path, monkeypatch):
    import pytest
    import prepare_mounted_crossbow_capture as preparation
    completed_queue(tmp_path)
    write(tmp_path / 'status.json', {'state': 'CAPTURING', 'verified': 385})
    original = (tmp_path / 'queue.json').read_bytes()
    monkeypatch.setattr(preparation, 'WORK', tmp_path)
    monkeypatch.setattr(preparation, 'guards_complete', lambda: True)
    with pytest.raises(RuntimeError, match='Finish the existing queue'):
        preparation.activate({'subjects': []}, None, append=True)
    assert (tmp_path / 'queue.json').read_bytes() == original
    assert not (tmp_path / 'provenance').exists()
