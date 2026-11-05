import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np

from civ_prediction_witnesses import build_witnesses, observed_roots, effect_signature


class WitnessTests(unittest.TestCase):
    def test_guesses_inferences_and_close_results_are_not_decisive_roots(self):
        rows = [{'evidenceType':e, 'outcome':o} for e,o in [
            ('observed','a_win'),('observed','close_uncertain'),
            ('inferred','b_win'),('predicted_unvalidated','a_win')]]
        self.assertEqual(observed_roots(rows),rows[:1])

    def test_effect_values_and_charge_cannot_silently_share_neighbors(self):
        base = {'effects':{'bonus':1}, 'mode':'default','charge':None}
        self.assertNotEqual(effect_signature(base),effect_signature(dict(base,effects={'bonus':2})))
        self.assertNotEqual(effect_signature(base),effect_signature(dict(base,charge={'damage':10})))

    def test_target_result_is_not_its_own_neighbor_and_counts_are_checked(self):
        hashes = ['a','b','c']
        mechanics = {'hp':100, 'speed_tiles_per_second':1,'reload_seconds':2,
            'attack_range_tiles':0,'unit_class':12,'mode':'default',
            'effects':{},'collision_size_tiles':{'x':.25}}
        definition = {'profiles':{h:{'mechanics':mechanics} for h in hashes}}
        variants = [{'key':h,'profileHash':h,'line':'knight'} for h in hashes]
        def row(a,b,counts):
            return {'pairKey':a+'|'+b,'profiles':[a,b],'outcome':'a_win','evidenceType':'observed',
                'sourceRunIds':['saved-seed'], 'context':{'profiles':[a,b], 'counts':counts,'scenarioHash':'s'}}
        target=row('a','b',[27,26]);neighbor=row('b','c',[26,27])
        damage={'hashes':hashes,'damage':[[10]*3 for _ in hashes],'exceptions':0}
        with patch('civ_prediction_witnesses.make_margin_edges',return_value=(np.full((3,3),np.nan),2)):
            witnesses,_=build_witnesses([target],[target,neighbor],variants,definition,damage,Path('unused'))
            self.assertEqual(witnesses['a|b']['neighbors'],[])
            neighbor['context'].update(profiles=['c','b'],counts=[27,26])
            witnesses,_=build_witnesses([target],[target,neighbor],variants,definition,damage,Path('unused'))
            self.assertEqual([r['anchorPairKey'] for r in witnesses['a|b']['neighbors']],['b|c'])
            neighbor['context']['counts']=[27,25]
            witnesses,_=build_witnesses([target],[target,neighbor],variants,definition,damage,Path('unused'))
            self.assertEqual(witnesses['a|b']['neighbors'],[])


if __name__ == '__main__':
    unittest.main()
