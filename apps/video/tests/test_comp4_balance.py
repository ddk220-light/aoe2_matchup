"""The approved fractional-HP examples and important rounding boundaries."""
import unittest
import tempfile
from pathlib import Path
from build_comp4_scenario import hp_roster


class Comp4BalanceTests(unittest.TestCase):
    def test_approved_champi_reference_and_inca_discount(self):
        reference = hp_roster(75, 75, 80, 50)
        inca = hp_roster(75, 60, 80, 50)
        self.assertEqual(reference['subjectCount'], 8)
        self.assertEqual(reference['opponentHP'], [50] * 7)
        self.assertEqual(inca['opponentHP'], [50] * 5 + [30])
        self.assertEqual(inca['opponentTotalHP'] / reference['opponentTotalHP'], .8)

    def test_integer_discount_has_no_extra_zero_hp_unit(self):
        self.assertEqual(hp_roster(80, 60, 80, 50)['opponentHP'], [50] * 6)

    def test_reference_subject_more_expensive(self):
        result = hp_roster(100, 75, 50, 60)
        self.assertEqual(result['subjectCount'], 4)
        self.assertEqual(result['opponentHP'], [60] * 6)

    def test_invalid_or_unrepresentable_costs_fail(self):
        for args in [(0, 0, 80, 50), (75, 90, 80, 50), (75, 60, 10000, 50)]:
            with self.assertRaises(ValueError):
                hp_roster(*args)

    def test_generated_scenario_preserves_golden_contract(self):
        from build_comp4_scenario import GOLDEN, ROOT, generate
        if not (ROOT/'data/local/cost-audit-extracted').exists():
            self.skipTest('Requires the audited installed-DAT extraction')
        from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
        from AoE2ScenarioParser.datasets.effects import attributes
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'test.aoe2scenario'
            manifest = generate(path)
            original = AoE2DEScenario.from_file(str(GOLDEN))
            generated = AoE2DEScenario.from_file(str(path))
            def effect_row(e):
                return {k:getattr(e,k) for k in ['effect_type', *attributes[e.effect_type]]}
            self.assertEqual([effect_row(e) for e in original.trigger_manager.triggers[0].effects],
                             [effect_row(e) for e in generated.trigger_manager.triggers[0].effects[1:]])
            damage = generated.trigger_manager.triggers[0].effects[0]
            self.assertEqual((damage.effect_type, damage.source_player, damage.quantity), (24,5,20))
            partial = manifest['pairs'][0]['slots'][-1]
            self.assertEqual(damage.selected_object_ids, [partial['referenceId']])
            self.assertEqual(len(generated.trigger_manager.triggers),1)
            for owner in range(1,9):
                a,b = original.player_manager.players[owner], generated.player_manager.players[owner]
                for attr in set(a._object_attributes + a._object_attributes_non_gaia):
                    self.assertEqual(getattr(a,attr), getattr(b,attr), (owner,attr))
            for attr in ['ai_names','ai_type','ai_files']:
                a = original.sections['PlayerDataTwo'].retriever_map[attr].data
                b = generated.sections['PlayerDataTwo'].retriever_map[attr].data
                if attr == 'ai_files':
                    a = [r.retriever_map['ai_per_file_text'].data for r in a]
                    b = [r.retriever_map['ai_per_file_text'].data for r in b]
                self.assertEqual(a,b,attr)
            terrain = lambda s:[(t.x,t.y,t.terrain_id,t.elevation,t.layer) for t in s.map_manager.terrain]
            self.assertEqual(terrain(original),terrain(generated))
            self.assertEqual(original.sections['Options'].retriever_map['all_techs'].data,
                             generated.sections['Options'].retriever_map['all_techs'].data)


if __name__ == '__main__':
    unittest.main()
