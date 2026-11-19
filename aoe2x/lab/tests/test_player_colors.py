"""Color follows the subject; formations, diplomacy and frozen templates do not change."""
import contextlib
import io

import pytest

from aoe2x.lab.cli import _normalize_batch_row
from aoe2x.lab.config import load_config
from aoe2x.lab.errors import LabError, LiveCaptureError
from aoe2x.lab.io import sha256
from aoe2x.lab.live import (
    _load_stack, _validate_scenario, golden_path, planned_player_colors,
)
from aoe2x.lab.planner import make_request, plan_matchup


@pytest.mark.parametrize('owner', [2, 3])
@pytest.mark.parametrize('source_colors', [(0, 1), (1, 4)])
def test_subject_colors_override_arena_or_donut_colors_only(owner, source_colors, tmp_path, monkeypatch):
    config = load_config()
    plan = plan_matchup(config, make_request(side2='arbalester', civ2='Chinese',
        side3='paladin', civ3='Spanish', subject_owner=owner,
        balance='explicit', n2=17, n3=27))
    stack = _load_stack(config)
    golden = golden_path(config, plan['scenario']['family'])
    golden_hash = sha256(golden)
    with contextlib.redirect_stdout(io.StringIO()):
        source = stack['AoE2DEScenario'].from_file(str(golden))
        players = {int(p.player_id): p for p in source.player_manager.players}
        for pid, color in zip((2, 3), source_colors):
            players[pid].color = color
        template = tmp_path / 'template.aoe2scenario'
        source.write_to_file(str(template))
        template_hash = sha256(template)
        monkeypatch.setattr('aoe2x.lab.live.capture_template_path', lambda *_: template)
        target = tmp_path / 'generated.aoe2scenario'
        sides = [stack['resolve_side'](plan[k]['civ'], plan[k]['slug']) for k in ('side2', 'side3')]
        stack['build_run'](*sides, target,
            counts=tuple(plan[k]['count'] for k in ('side2', 'side3')),
            template=template, remove_player4_buffer=True, subject_owner=owner)
        report = _validate_scenario(config, plan, target, stack)
        generated = stack['AoE2DEScenario'].from_file(str(target))
        players = {int(p.player_id): p for p in generated.player_manager.players}
        assert int(players[owner].color) == 0
        assert int(players[5-owner].color) == 1
        assert report['playerColorsMatchPlan']
        assert report['playerRuntimeConfigurationMatchesPlan']
        assert report['playerRuntimeConfigurationMatchesGolden'] == (
            tuple(planned_player_colors(plan)[p] for p in (2, 3)) == source_colors)
        assert all(report[k] for k in ('positionsMatchGolden', 'aiConfigurationMatchesGolden',
            'cameraMatchesGolden', 'triggerStructureMatchesGolden'))
        players[owner].color = 4
        wrong_color = tmp_path / 'wrong-color.aoe2scenario'
        generated.write_to_file(str(wrong_color))
        with pytest.raises(LiveCaptureError, match='colors'):
            _validate_scenario(config, plan, wrong_color, stack)
        players[owner].color = 0
        players[owner].starting_age = int(players[owner].starting_age) - 1
        wrong_age = tmp_path / 'wrong-age.aoe2scenario'
        generated.write_to_file(str(wrong_age))
        with pytest.raises(LiveCaptureError, match='starting ages'):
            _validate_scenario(config, plan, wrong_age, stack)
    assert sha256(golden) == golden_hash
    assert sha256(template) == template_hash


def test_legacy_batch_metadata_does_not_rewrite_frozen_requests():
    row = dict(id='old-trial', subjectOwner=3, side2='arbalester', side3='paladin',
               scenario={'player4Buffer': 'none'})
    normalized = _normalize_batch_row(row, {})
    assert 'subjectOwner' not in normalized['scenario']
    assert planned_player_colors({'scenario': normalized['scenario']}) is None
    row['scenario']['subjectOwner'] = 2
    with pytest.raises(LabError, match='disagrees'):
        _normalize_batch_row(row, {})
    row['scenario']['subjectOwner'] = 3
    assert _normalize_batch_row(row, {})['scenario']['subjectOwner'] == 3


def test_reject_inconsistent_color_contract():
    with pytest.raises(LiveCaptureError, match='requires explicit'):
        planned_player_colors({'scenario': {'playerColors': {'2': 0, '3': 1}}})
    with pytest.raises(LiveCaptureError, match='blue for the subject'):
        planned_player_colors({'scenario': {'subjectOwner': 3,
            'colorPolicy': 'subject_blue_opponent_red_v1', 'playerColors': {'2': 0, '3': 1}}})
