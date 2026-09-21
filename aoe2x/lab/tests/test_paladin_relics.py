import contextlib
import io

import pytest

from aoe2x.lab.config import load_config
from aoe2x.lab.errors import LiveCaptureError, PlanError
from aoe2x.lab.live import _load_stack, _validate_scenario, golden_path
from aoe2x.lab.planner import make_request, plan_matchup


def test_four_relic_attack_targets_only_lithuanian_paladins_and_is_part_of_plan(tmp_path):
    cfg = load_config()
    request = make_request(side2='paladin_lithuanians_four_relics', side3='elite_composite_bowman_armenians')
    ordinary = plan_matchup(cfg, request)
    request['scenario'] = {'lithuanianRelics': 4}
    plan = plan_matchup(cfg, request)
    assert ordinary['planHash'] != plan['planHash']
    stack = _load_stack(cfg)
    target = tmp_path / 'relics.aoe2scenario'
    with contextlib.redirect_stdout(io.StringIO()):
        stack['build_run'](*(stack['resolve_side'](plan[s]['civ'], plan[s]['slug']) for s in ('side2', 'side3')),
            target, counts=tuple(plan[s]['count'] for s in ('side2', 'side3')),
            template=golden_path(cfg, plan['scenario']['family']), lithuanian_relics=4)
        _validate_scenario(cfg, plan, target, stack)
        scenario = stack['AoE2DEScenario'].from_file(str(target))
        effect = scenario.trigger_manager.triggers[-1].effects[0]
        assert effect.armour_attack_class == 4 and effect.armour_attack_quantity == 4
        assert effect.object_list_unit_id == 569 and effect.source_player == 2
        assert not scenario.trigger_manager.triggers[-1].looping
        effect.armour_attack_quantity = 3
        tampered = tmp_path / 'wrong.aoe2scenario'
        scenario.write_to_file(str(tampered))
        with pytest.raises(LiveCaptureError, match='relic condition'):
            _validate_scenario(cfg, plan, tampered, stack)


def test_relic_condition_cannot_be_given_to_other_civilizations():
    request = make_request(side2='paladin_franks', side3='elite_composite_bowman_armenians')
    request['scenario'] = {'lithuanianRelics': 4}
    with pytest.raises(PlanError, match='Lithuanian'):
        plan_matchup(load_config(), request)


@pytest.mark.parametrize('both_sides', [False, True])
def test_leitis_relics_target_opponent_and_preserve_paladin_modifier(tmp_path, both_sides):
    cfg = load_config()
    request = make_request(side2='paladin_lithuanians_four_relics' if both_sides else 'cavalier_bulgarians',
                           side3='elite_leitis_lithuanians')
    request['scenario'] = {'lithuanianRelics': 4} if both_sides else {}
    previous = plan_matchup(cfg, request)
    request['scenario']['opponentLithuanianRelics'] = 4
    plan = plan_matchup(cfg, request)
    assert plan['planHash'] != previous['planHash']
    assert [plan[s]['count'] for s in ('side2', 'side3')] == [previous[s]['count'] for s in ('side2', 'side3')]
    stack = _load_stack(cfg)
    target = tmp_path / 'leitis.aoe2scenario'
    with contextlib.redirect_stdout(io.StringIO()):
        stack['build_run'](*(stack['resolve_side'](plan[s]['civ'], plan[s]['slug']) for s in ('side2', 'side3')),
            target, counts=tuple(plan[s]['count'] for s in ('side2', 'side3')),
            template=golden_path(cfg, plan['scenario']['family']),
            lithuanian_relics=4 if both_sides else None, opponent_lithuanian_relics=4)
        _validate_scenario(cfg, plan, target, stack)
        scenario = stack['AoE2DEScenario'].from_file(str(target))
        triggers = scenario.trigger_manager.triggers[-(2 if both_sides else 1):]
        assert [(t.effects[0].source_player, t.effects[0].object_list_unit_id) for t in triggers] == (
            [(2, 569), (3, 1236)] if both_sides else [(3, 1236)])
        assert all(t.effects[0].armour_attack_quantity == 4 and not t.looping for t in triggers)
        # Both modifiers must be validated independently, including the P2 effect
        # that is no longer the final trigger when P3 also gets four relics.
        triggers[0].effects[0].armour_attack_quantity = 8
        tampered = tmp_path / 'double-bonus.aoe2scenario'
        scenario.write_to_file(str(tampered))
        with pytest.raises(LiveCaptureError, match='relic condition'):
            _validate_scenario(cfg, plan, tampered, stack)


@pytest.mark.parametrize('slug,civ', [('elite_leitis_lithuanians', 'Franks'),
                                     ('elite_composite_bowman_armenians', 'Armenians')])
def test_opponent_relics_reject_wrong_owner_identity(slug, civ):
    request = make_request(side2='paladin_franks', side3=slug, civ3=civ)
    request['scenario'] = {'opponentLithuanianRelics': 4}
    with pytest.raises(PlanError):
        plan_matchup(load_config(), request)
