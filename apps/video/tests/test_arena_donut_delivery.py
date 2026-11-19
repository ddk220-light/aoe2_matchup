"""Protect existing archive rows/media when publishing a Donut extension."""
import copy
from pathlib import Path

import pytest

import copy_arena_donut_to_share as delivery
from compact_recording_archive import digest, read
from run_champi_comparison_capture import save


def fixture(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    root.mkdir()
    work = root / 'work'
    campaign_dir = work / 'subject'
    destination = tmp_path / 'existing-archive'
    destination.mkdir()
    baseline = dict(state='COMPLETE', title='Existing run', matchups=[dict(
        jobId='old', files={'battle.mp4': {'path': 'old.mp4'}})], finalVideo=None)
    save(destination / 'run.json', baseline)
    (destination / 'old.mp4').write_bytes(b'old recording must survive')
    original_media = (destination / 'old.mp4').read_bytes()
    job = 'new'
    runs = root / 'runs'
    source = runs / job / 'live/run_001'
    source.mkdir(parents=True)
    files = {}
    for key, name in [('battle.mp4', 'video.mp4'), ('frames.bin', 'frames.bin')]:
        path = source / name
        path.write_bytes(('new ' + key).encode())
        files[key] = dict(source=str(path), bytes=path.stat().st_size, sha256=digest(path))
    prepared = dict(jobId=job, files=files, plan=dict(
        side2={'civ': 'Saracens', 'label': 'Arbalester'}, side3={'civ': 'Danes', 'label': 'Jomsviking'},
        scenario={}))
    item = dict(id=job, subjectOwner=3, subjectSlug='subject', opponentSlug='arb',
                opponentIndex=2, iteration=1, layout='Donut', selectionReason='Arena loss')
    save(campaign_dir / 'manifest.json', {'matchups': [item]})
    save(campaign_dir / 'capture/status.json', dict(results=[dict(jobId=job, status='verified', runDirectory=str(source))]))
    for name in ['pilot-validation.json', 'subject-stats.json', 'preflight.json']:
        save(campaign_dir / name, {})
    save(work / 'queue.json', {})
    save(work / 'eligibility.json', {})
    doc = root / 'docs/video-production/ARENA_DONUT_CAPTURE.md'
    doc.parent.mkdir(parents=True)
    doc.write_text('test reconstruction guide')
    campaign = dict(slug='subject', total=1, destination=str(destination),
        workDirectory=str(campaign_dir), originalIndexSha256=digest(destination / 'run.json'))
    monkeypatch.setattr(delivery, 'ROOT', root)
    monkeypatch.setattr(delivery, 'RUNS', runs)
    monkeypatch.setattr(delivery, 'prepare', lambda _: copy.deepcopy(prepared))
    return work, campaign, destination, baseline, original_media


def test_append_preserves_baseline_and_resumes_publication(tmp_path, monkeypatch):
    work, campaign, target, baseline, old_media = fixture(tmp_path, monkeypatch)
    state = {'packages': {}}
    delivery.deliver(work, campaign, state)
    index = read(target / 'run.json')
    assert index['matchups'][0] == baseline['matchups'][0]
    assert len(index['matchups']) == 2
    added = index['matchups'][1]
    assert added['subjectOwner'] == 3
    assert added['name'].startswith('Danes_Jomsviking_vs_Saracens_Arbalester')
    assert added['files']['battle.mp4']['path'].endswith(' - Donut.mp4')
    assert (target / 'old.mp4').read_bytes() == old_media
    delivery.deliver(work, campaign, state)
    assert len(read(target / 'run.json')['matchups']) == 2


def test_changed_baseline_is_not_overwritten(tmp_path, monkeypatch):
    work, campaign, target, _, _ = fixture(tmp_path, monkeypatch)
    save(target / 'run.json', {'someoneElseUpdated': True})
    with pytest.raises(RuntimeError, match='changed after preparation'):
        delivery.deliver(work, campaign, {'packages': {}})
    assert read(target / 'run.json') == {'someoneElseUpdated': True}


def test_color_sixth_iteration_appends_named_pair_without_replacing_history(tmp_path, monkeypatch):
    work, campaign, target, baseline, old_media = fixture(tmp_path, monkeypatch)
    manifest_path = Path(campaign['workDirectory']) / 'manifest.json'
    manifest = read(manifest_path)
    manifest['matchups'][0].update(iteration=6, colorCorrected=True)
    save(manifest_path, manifest)
    campaign.update(metadataDirectory='_donut_color_r06_metadata',
                    extensionKind='donut-color-corrected-sixth-iteration')
    state = {'packages': {}}
    delivery.deliver(work, campaign, state)
    result = read(target / 'run.json')
    assert result['matchups'][0] == baseline['matchups'][0]
    added = result['matchups'][-1]
    assert added['colorCorrected'] and added['iteration'] == 6
    assert added['name'].endswith('_r06 - Donut - Color Corrected')
    for key, info in added['files'].items():
        assert (target / info['path']).is_file()
        assert info['path'] == added['name'] + ('.mp4' if key == 'battle.mp4' else '.frames.bin')
    assert (target / 'old.mp4').read_bytes() == old_media


def test_follow_on_extension_preserves_previous_metadata_and_media(tmp_path, monkeypatch):
    work, campaign, target, baseline, old_media = fixture(tmp_path, monkeypatch)
    delivery.deliver(work, campaign, {'packages': {}})
    previous = read(target / 'run.json')
    old_metadata = {p.relative_to(target): digest(p)
                    for p in (target / '_arena_donut_metadata').rglob('*') if p.is_file()}
    root = work.parent
    next_work = root / 'slinger-work'
    directory = next_work / 'subject'
    source = delivery.RUNS / 'slinger' / 'live/run_001'
    source.mkdir(parents=True)
    prepared = copy.deepcopy(delivery.prepare(source))
    prepared.update(jobId='slinger')
    prepared['plan']['side3']['label'] = 'Slinger'
    for key, info in prepared['files'].items():
        path = source / key
        path.write_bytes(('Slinger ' + key).encode())
        info.update(source=str(path), bytes=path.stat().st_size, sha256=digest(path))
    monkeypatch.setattr(delivery, 'prepare', lambda _: copy.deepcopy(prepared))
    item = dict(id='slinger', subjectOwner=3, subjectSlug='subject', opponentSlug='slinger',
        opponentIndex=17, iteration=1, layout='Arena', selectionReason='New standard opponent')
    save(directory / 'manifest.json', {'matchups': [item]})
    save(directory / 'capture/status.json', dict(results=[dict(
        jobId='slinger', status='verified', runDirectory=str(source))]))
    for name in ('pilot-validation.json', 'subject-stats.json', 'preflight.json'):
        save(directory / name, {})
    save(next_work / 'queue.json', {})
    save(next_work / 'eligibility.json', {})
    next_campaign = {**campaign, 'workDirectory': str(directory),
        'originalIndexSha256': digest(target / 'run.json'),
        'metadataDirectory': '_inca_slinger_metadata', 'extensionKind': 'inca-slinger'}
    state = {'packages': {}}
    delivery.deliver(next_work, next_campaign, state)
    extended = read(target / 'run.json')
    assert extended['matchups'][:-1] == previous['matchups']
    assert extended['extensions'][-1]['kind'] == 'inca-slinger'
    assert (target / '_inca_slinger_metadata').is_dir()
    assert {p: digest(target / p) for p in old_metadata} == old_metadata
    assert (target / 'old.mp4').read_bytes() == old_media
    delivery.deliver(next_work, next_campaign, state)
    assert len(read(target / 'run.json')['matchups']) == 3
