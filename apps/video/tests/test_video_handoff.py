"""Portable handoff checks: prepare sources without capture, rendering or API use."""
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from create_intro_voice_clone import create
from scaffold_video_episode import ROOT, episode_files
from aoe2x.lab.planner import load_matchup_file


def test_new_episode_has_correct_identities_counts_and_compilable_adapters():
    episode, files = episode_files(ROOT, 'handoff-kamayuk', 'elite_kamayuk_incas')
    manifest = json.loads(files[Path(episode['manifest'])])
    rows = manifest['matchups']
    assert len(rows) == 73
    assert len({r['id'] for r in rows}) == 73
    assert all(r['balance']['mode'] == 'geometric_shared_discount' for r in rows)
    assert 'Equal resources' not in files[Path('apps/video/build_handoff_kamayuk_final.py')]
    assert 'square root of the comparison-cost ratio' in files[Path('apps/video/build_handoff_kamayuk_final.py')]
    assert 'every physical unit as one population' in files[Path('apps/video/build_handoff_kamayuk_final.py')]
    assert all(r['side2'] == 'elite_kamayuk_incas' and r['civ2'] == 'Incas' for r in rows)
    assert all(r['side3'] != r['side2'] for r in rows)
    assert [r['civ3'].casefold() for r in rows] == sorted(r['civ3'].casefold() for r in rows)
    for path, text in files.items():
        if path.suffix == '.py':
            compile(text, str(path), 'exec')
            assert 'elite-monaspa' not in text and 'Georgians' not in text and '#FlemishMilitia' not in text
    assert "result['total']=73" in files[Path('apps/video/run_handoff_kamayuk_capture.py')]
    assert 'handoff-kamayuk-canonical' in files[Path('apps/video/run_handoff_kamayuk_capture.py')]


def test_subject_outside_roster_derives_74_opponents_and_no_source_files_are_written():
    episode, files = episode_files(ROOT, 'handoff-slinger', 'imp_slinger_incas')
    assert episode['matchups'] == 74
    builder = files[Path('apps/video/build_handoff_slinger_final.py')]
    assert 'assert len(results)==74' in builder
    assert "'matchups':74" in builder
    assert 'vs 74 Unique Units' in builder
    assert not (ROOT / episode['manifest']).exists()


def test_scaffold_rejects_path_escape_unknown_unit_and_special_scenarios():
    for key, slug in [('../escape', 'elite_obuch_poles'), ('unknown', 'not_a_unit'),
                      ('camel', 'flaming_camel_tatars'), ('priest', 'missionary_spanish')]:
        with pytest.raises(ValueError):
            episode_files(ROOT, key, slug)


def test_both_manifest_formats_reach_the_postprocess_loader(tmp_path):
    json_file = tmp_path / 'episode.json'
    toml_file = tmp_path / 'episode.toml'
    expected = {'matchups': [{'id': 'test', 'side2': 'a', 'side3': 'b'}]}
    json_file.write_text(json.dumps(expected))
    toml_file.write_text('[[matchups]]\nid="test"\nside2="a"\nside3="b"\n')
    assert load_matchup_file(json_file) == load_matchup_file(toml_file) == expected


def test_retired_clone_is_not_reused_even_when_its_sample_matches(tmp_path):
    sample = tmp_path / 'sample.wav'
    sample.write_bytes(b'not sent to a provider')
    metadata = tmp_path / 'voice.json'
    metadata.write_text(json.dumps({'voice_id': 'retired-voice', 'retired': True,
                                   'sampleSha256': hashlib.sha256(sample.read_bytes()).hexdigest()}))
    with pytest.raises(ValueError, match='retired'):
        create(sample, metadata)


def test_scaffold_write_plans_the_whole_episode_in_isolation_and_refuses_overwrite(tmp_path, monkeypatch):
    import scaffold_video_episode as scaffold
    for relative in ['data/unique-unit-roster.json', 'data/recording-subjects.json',
                     'apps/video/build_elite_monaspa_final.py',
                     'apps/video/prepare_elite_monaspa_final_shorts.py',
                     'apps/video/run_elite_obuch_capture.py']:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    (tmp_path / 'data/video-production-queue.json').write_text(json.dumps({'episodes': []}))
    monkeypatch.setattr(scaffold, 'ROOT', tmp_path)
    monkeypatch.setattr('sys.argv', ['scaffold', '--key', 'integration-kamayuk',
                                   '--slug', 'elite_kamayuk_incas', '--write'])
    # The real Node planner is read-only. All scaffold writes stay in tmp_path.
    scaffold.main()
    report = json.loads((tmp_path / 'data/local/integration-kamayuk-capture-preflight.json').read_text())
    assert report['passed'] and len(report['plans']) == 73
    assert all(p['side2']['count'] <= 27 and p['side3']['count'] <= 27 for p in report['plans'])
    assert all('maxResources' not in p['balance'] for p in report['plans'])
    queue_file = tmp_path / 'data/video-production-queue.json'
    before = queue_file.read_bytes()
    with pytest.raises(SystemExit) as error:
        scaffold.main()
    assert error.value.code == 2
    assert queue_file.read_bytes() == before
