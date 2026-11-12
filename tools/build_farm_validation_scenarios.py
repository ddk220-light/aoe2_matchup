#!/usr/bin/env python3
"""Create controlled DE capture inputs. Requires AoE2ScenarioParser==0.9.9.

Generated scenarios are structurally checked, not claimed to have run in DE.
Native construction initializes farms after the selected technology effects.
"""
import hashlib
import json
from pathlib import Path

from AoE2ScenarioParser import settings
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.datasets.object_support import Civilization, StartingAge
from AoE2ScenarioParser.datasets.trigger_lists import Operation
from AoE2ScenarioParser.datasets.effects import EffectId

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'aoe2x/js_simulation/calibration/economy/farms-repeated-reference-2026-11-09/de-capture'
PREVIOUS = ROOT / 'aoe2x/js_simulation/calibration/economy/farms-refinement-2026-11-09'
settings.PRINT_STATUS_UPDATES = False


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    for name, profile, techs, building_id, origins in [
        ('tc-none', 'none', [], 109, [(4, 0), (7, 0)]),
        ('tc-wheelbarrow', 'wheelbarrow', [14, 213], 109, [(4, 0), (7, 0)]),
        ('tc-handcart', 'full', [14, 213, 13, 249], 109, [(4, 0), (7, 0)]),
        ('mill-postimperial', 'full', [14, 213, 13, 249, 12], 68, None),
    ]:
        fixture = json.loads((PREVIOUS / f'fixture-{profile}.json').read_text())
        if origins is None:
            origins = [(f['x0'], f['y0']) for f in fixture['farms']]
        scenario = AoE2DEScenario.from_default('1.58')
        scenario.map_manager.map_size = 80
        scenario.player_manager.active_players = 2
        for tile in scenario.map_manager.terrain:
            tile.terrain_id = 0
            tile.elevation = 0
        for player in scenario.player_manager.players[1:]:
            player.human = True
            player.civilization = Civilization.BYZANTINES
            player.starting_age = StartingAge.DARK_AGE
            player.food = player.gold = player.stone = 0
            player.wood = 1000 if player.player_id == 1 else 0
            player.allied_victory = False
        scenario.option_manager.victory_condition = 4  # Custom; no victory trigger.
        scenario.option_manager.victory_custom_conditions_required = True
        um, tm = scenario.unit_manager, scenario.trigger_manager
        um.add_unit(player=2, unit_const=109, x=70, y=70)
        half = 2 if building_id == 109 else 1
        building = um.add_unit(player=1, unit_const=building_id, x=30+half, y=30+half)
        setup = tm.add_trigger('Selected upgrades only', enabled=True)
        setup.new_effect.change_diplomacy(source_player=1, target_player=2, diplomacy=0, mutual_diplomacy=True)
        setup.new_effect.change_view(source_player=1, location_x=34, location_y=31)
        for tech in techs:
            setup.new_effect.research_technology(source_player=1, technology=tech, force_research_technology=1)
        start = tm.add_trigger('Native farm construction at 10 seconds', enabled=True)
        start.new_condition.timer(timer=10)
        workers = []
        for index, (x, y) in enumerate(origins):
            cx, cy = x + 31.5, y + 31.5
            worker = um.add_unit(player=1, unit_const=83, x=cx, y=cy)
            workers.append(dict(index=index,reference_id=worker.reference_id,x=cx,y=cy,
                                farm_origin=[x+30,y+30]))
            start.new_effect.place_foundation(source_player=1, object_list_unit_id=50,
                                               location_x=int(cx), location_y=int(cy))
        for worker in workers:
            start.new_effect.task_object(source_player=1, selected_object_ids=[worker['reference_id']],
                                         location_x=int(worker['x']), location_y=int(worker['y']))
        # Prevent subsequent reseeding without changing worker or farm attributes.
        no_reseed = tm.add_trigger('Remove spare wood after initial construction', enabled=True)
        no_reseed.new_condition.timer(timer=60)
        no_reseed.new_effect.modify_resource(source_player=1, tribute_list=1, operation=Operation.SET, quantity=0)
        filename = OUT / f'{name}.aoe2scenario'
        scenario.write_to_file(str(filename))
        restored = AoE2DEScenario.from_file(str(filename))
        assert restored.scenario_version == '1.58'
        restored_units = restored.unit_manager.get_player_units(1)
        assert len([u for u in restored_units if u.unit_const == 83]) == len(origins)
        assert len([u for u in restored_units if u.unit_const == building_id]) == 1
        for worker in workers:
            actual = next(u for u in restored_units if u.reference_id == worker['reference_id'])
            assert (actual.x, actual.y) == (worker['x'], worker['y'])
        effects = [e for t in restored.trigger_manager.triggers for e in t.effects]
        # Effect enums are checked by their serialized names, not assumed numbers.
        names = [EffectId(e.effect_type).name for e in effects]
        assert names.count('RESEARCH_TECHNOLOGY') == len(techs)
        assert [e.technology for e in effects if EffectId(e.effect_type).name == 'RESEARCH_TECHNOLOGY'] == techs
        assert names.count('PLACE_FOUNDATION') == len(origins)
        assert names.count('TASK_OBJECT') == len(origins)
        assert restored.player_manager.active_players == 2
        assert restored.player_manager.players[1].civilization == Civilization.BYZANTINES
        expected_food = 175 + (75 if 14 in techs else 0) + (125 if 13 in techs else 0) + (175 if 12 in techs else 0)
        cases.append(dict(name=name,file=filename.name,sha256=hashlib.sha256(filename.read_bytes()).hexdigest(),
                          technology_ids=techs,expected_food_per_farm=expected_food,
                          expected_worker=fixture['worker'],workers=workers,building_reference_id=building.reference_id,
                          validation='Parser round-trip and scenario structure passed; actual DE execution pending.'))
    result = dict(parser_version='0.9.9',scenario_format='1.58',civilization='Byzantines',cases=cases,
                  state='awaiting_real_game_capture',
                  protocol=[
                      'Load a scenario in current DE. Use the standard data set, no mods, no cheats, and fixed 1.7x game speed. Record the exact executable build.',
                      'Use Player 1; do not assign an AI or issue worker orders. Farms begin native construction at game time 10 seconds after selected upgrades are applied.',
                      'Record the whole test to at least 22 game-minutes for the two-farm cases, and 25 for the ten-farm post-Imperial case. Keep the game clock visible; save the replay if available.',
                      'Verify initial farm food, worker carry and speed against the case manifest. Stop comparison if these differ, or if foundation snapping changes the layout.',
                      'Measure each farm from its actual construction-completion time to depletion. Also capture the first work-spot position, each change of work spot, carried food, drop-off positions and final deposit.',
                      'Use harvested food (banked plus carried) for fixed-time comparisons. Do not mix this with banked-only food or depletion with final-deposit time.',
                      'The ten-farm setup is a no-reseeding diagnostic: wood becomes zero at 60 seconds. Compare before depletion, or match this setting in the model.',
                      'Repeat each two-farm case at least 10 times for an initial distribution. Increase repetitions if the uncertainty of the mean remains above 1%; do not select favorable individual runs.',
                      'Actual farm-creation, task and gather timestamps must be observed. Trigger scheduling and native construction are not presumed instantaneous or exactly 15 seconds in a live run.'
                  ])
    (OUT / 'capture-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    (OUT / 'README.md').write_text('# Controlled DE farming capture inputs\n\n'
        'Four generated scenarios are ready for an in-game check. They were parsed back and structurally verified, but have not been run in DE. This Linux workspace has no DE executable.\n\n'
        'The selected economy technologies are forced in Dark Age to isolate their effects; this is a laboratory test of the post-Imperial economy parameters, not a normal match. All workers are generic Byzantines.\n\n'
        + '\n'.join(f'{i+1}. {step}' for i,step in enumerate(result['protocol'])) + '\n\n'
        'The exact unit references, coordinates, expected values and file hashes are in `capture-manifest.json`. Native construction deliberately avoids guessing how preplaced farms inherit food-capacity upgrades.\n')
    print(json.dumps([{'name':c['name'],'workers':len(c['workers']),'validation':c['validation']} for c in cases],indent=2))


if __name__ == '__main__':
    main()
