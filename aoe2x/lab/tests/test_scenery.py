"""A recording may use reviewed scenery, but must never silently swap maps."""
import dataclasses

import pytest

from aoe2x.lab.config import load_config
from aoe2x.lab.errors import PreflightError
from aoe2x.lab.io import sha256, write_json
from aoe2x.lab.live import capture_template_path


def test_frozen_scenery_rejects_changed_file_or_wrong_golden(tmp_path, monkeypatch):
    config = dataclasses.replace(load_config(), project_root=tmp_path)
    golden = tmp_path/'golden'
    golden.write_bytes(b'original')
    monkeypatch.setattr('aoe2x.lab.live.golden_path', lambda *_: golden)
    template = tmp_path/'winter'
    template.write_bytes(b'reviewed derivative')
    audit = tmp_path/'audit.json'
    metadata = dict(state='PASSED', family='melee_vs_melee',
                    goldenSha256=sha256(golden), templateSha256=sha256(template))
    write_json(audit, metadata)
    scenery = dict(path='winter', sha256=sha256(template),
                   auditPath='audit.json', auditSha256=sha256(audit))
    plan = {'scenario': {'family': 'melee_vs_melee', 'scenery': scenery}}
    assert capture_template_path(config, plan) == template
    template.write_bytes(b'changed')
    with pytest.raises(PreflightError, match='missing or changed'):
        capture_template_path(config, plan)
    template.write_bytes(b'reviewed derivative')
    metadata['family'] = 'ranged_vs_ranged'
    write_json(audit, metadata)
    scenery['auditSha256'] = sha256(audit)
    with pytest.raises(PreflightError, match='does not match'):
        capture_template_path(config, plan)
    scenery['path'] = '../outside-project'
    with pytest.raises(PreflightError, match='inside the project'):
        capture_template_path(config, plan)
    assert capture_template_path(config, {'scenario': {'family': 'melee_vs_melee'}}) == golden


def test_donut_binds_template_and_rejects_wrong_ownership(tmp_path, monkeypatch):
    config = dataclasses.replace(load_config(), project_root=tmp_path)
    golden = tmp_path / 'golden'
    golden.write_bytes(b'arena')
    monkeypatch.setattr('aoe2x.lab.live.golden_path', lambda *_: golden)
    template = tmp_path / 'donut'
    template.write_bytes(b'reviewed donut')
    audit = tmp_path / 'audit.json'
    write_json(audit, dict(state='PASSED', layout='Donut', templateSha256=sha256(template),
                          slotsPerSide=27, bufferUnits=0, terrainFlat=True, quietAi=True))
    descriptor = dict(path='donut', sha256=sha256(template),
                      auditPath='audit.json', auditSha256=sha256(audit))
    plan = dict(side2={'ranged': True}, side3={'ranged': False},
                scenario=dict(family='ranged_vs_ranged', layout='Donut', player4Buffer='none', donut=descriptor))
    assert capture_template_path(config, plan) == template
    plan['side3']['ranged'] = True
    with pytest.raises(PreflightError, match='ranged P2'):
        capture_template_path(config, plan)
    plan['scenario'].update(donutExperiment='arbalester_kites_jarl_v1', subjectOwner=3)
    plan['side2']['slug'] = 'arbalester_saracens'
    plan['side3']['slug'] = 'elite_jarl_varangians'
    assert capture_template_path(config, plan) == template
    plan['scenario']['subjectOwner'] = 2
    with pytest.raises(PreflightError, match='Invalid Arbalester'):
        capture_template_path(config, plan)
    plan['scenario'].pop('donutExperiment')
    plan['side3']['ranged'] = False
    template.write_bytes(b'changed scenery')
    with pytest.raises(PreflightError, match='missing or changed'):
        capture_template_path(config, plan)
