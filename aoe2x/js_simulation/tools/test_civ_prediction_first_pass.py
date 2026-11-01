import gzip
import json
from pathlib import Path
import tempfile
import unittest

from civ_prediction_first_pass import (VERSION, canonical, choose, compare, plan,
    read_rows, select_probes, sha, write_json, write_rows)


class PredictionPolicyTests(unittest.TestCase):
    def model(self, a=.82, b=.08, other_a=.8, other_b=.1):
        return {'histGradientBoostingProbabilities': {'aWin': a, 'bWin': b, 'close': 1-a-b},
                'extraTreesProbabilities': {'aWin': other_a, 'bWin': other_b, 'close': 1-other_a-other_b}}

    def test_agreement_is_a_prediction_not_a_probability(self):
        selected = choose(self.model(), None)
        self.assertEqual(selected['predictedOutcome'], 'a_win')
        self.assertEqual(selected['tier'], 'broader_agreement')

    def test_model_disagreement_and_close_risk_abstain(self):
        self.assertIsNone(choose(self.model(other_a=.1, other_b=.8), None))
        self.assertIsNone(choose(self.model(a=.8, b=.01), None))

    def test_cavalry_contradiction_removes_only_benchmark_method(self):
        prior = {'supportingMethods': {'two_benchmark_rule': {'predictedOutcome': 'b_win'},
                                      'extra_trees': {'predictedOutcome': 'a_win'}}}
        result = choose(self.model(), prior, cavalry_guard=False)
        self.assertEqual(result['predictedOutcome'], 'a_win')
        self.assertNotIn('two_benchmark_rule', result['supportingMethods'])

    def test_no_inferred_labels_or_retroactive_prospective_credit(self):
        context = {'counts': [27, 25]}
        predictions = {'p': {'ruleHash': 'r', 'family': 'test', 'predictedOutcome': 'a_win',
            'supportingMethods': {}, 'rankingCommonC': [], 'contextHash': sha(canonical(context))}}
        row = {'context': context, 'evidenceType': 'inferred', 'outcome': 'a_win',
               'sourceRunIds': ['campaign/adaptive/runs/027.jsonl:1']}
        self.assertEqual(compare(predictions, {'p': row}, 27), ([], []))
        row['evidenceType'] = 'observed'
        self.assertFalse(compare(predictions, {'p': row}, 27)[0][0]['independent'])
        row.update(outcome='close_uncertain', sourceRunIds=['campaign/adaptive/runs/028.jsonl:1'])
        tests, failures = compare(predictions, {'p': row}, 27)
        self.assertTrue(tests[0]['independent'])
        self.assertEqual(len(failures), 1)

    def test_samples_are_bounded_unique_and_deterministic(self):
        candidates = [{'pairKey': str(i), 'ruleHash': str(i%4), 'family': 'test',
            'aliases': 10, 'estimatedSeconds': 20, 'profiles': [str(i), str(i+1)],
            'modelScores': {'hgb': {'aWin': .8, 'bWin': .1}}, 'predictedOutcome': 'a_win'}
            for i in range(70)]
        a = select_probes(candidates, [], 32)
        self.assertEqual(len(a), 32)
        self.assertEqual(len({r['pairKey'] for r in a}), 32)
        self.assertEqual(a, select_probes(list(reversed(candidates)), [], 32))
        self.assertEqual({r['purpose'] for r in a}, {'representative_sample', 'boundary_and_new_profiles'})

    def test_table_preserves_observed_blocked_and_display_orientation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); campaign = root/'campaign'; policy = root/'policy'; output=root/'output'
            context = {'profiles': ['a','b'], 'counts': [27,25], 'scenarioHash': 'scenario'}
            rows = [{'pairKey': key, 'profiles': ['a','b'], 'context': context, 'aliases': 1,
                'outcome': 'a_win' if key=='observed' else 'unresolved',
                'evidenceType': 'observed' if key=='observed' else 'none',
                'sourceRunIds': ['campaign/adaptive/runs/026.jsonl:1'] if key=='observed' else []}
                for key in ['observed','blocked','prediction']]
            variants = [{'key':'CivA|unit','profileHash':'a'}, {'key':'CivB|unit','profileHash':'b'}]
            cells = [{'pairKey':r['pairKey'],'civA':'CivB','unitA':'unit','civB':'CivA','unitB':'unit',
                      'outcome':r['outcome'],'evidenceType':r['evidenceType']} for r in rows]
            inf = campaign/'latest-inference'
            write_rows(inf/'profile-matchups.jsonl.gz', rows)
            write_rows(inf/'civ-matchups.jsonl.gz', cells)
            write_json(inf/'variant-profiles.json', variants)
            names = ['profile-matchups.jsonl.gz','civ-matchups.jsonl.gz','variant-profiles.json']
            source_hashes = {name:sha((inf/name).read_bytes()) for name in names}
            write_json(inf/'manifest.json', {'buildHash':'build','outputs':[
                {'file':name,'rows':len(rows),'sha256':source_hashes[name]} for name in names]})
            write_json(campaign/'adaptive/state.json', {'completedPhases':['026'],'blockedPairs':['blocked']})
            write_json(campaign/'adaptive/phases/026.json', {'pairKeys':['observed','blocked']})
            write_json(campaign/'adaptive/phases/026-review.json', {'status':'complete_with_blocked',
                'pairs':2,'blockedPairs':['blocked'],'missingSeeds':1,'inferenceHash':'build'})
            (campaign/'adaptive/runs').mkdir()
            predictions = [{'pairKey':r['pairKey'],'profiles':['a','b'],'contextHash':sha(canonical(context)),
                'ruleHash':'rule','family':'test','predictedOutcome':'a_win','tier':'broader_agreement',
                'supportingMethods':{},'rankingCommonC':[],
                'modelScores':{'hgb':{'aWin':.8,'bWin':.1}}} for r in rows]
            write_rows(policy/'predictions.jsonl.gz', predictions)
            write_json(policy/'manifest.json', {'policyVersion':VERSION,'predictionCount':3,
                'introducedAfterPhase':27,'validationSamplePerPhase':32,
                'predictionsSha256':sha((policy/'predictions.jsonl.gz').read_bytes())})
            result = plan(campaign, policy, 26, output)
            generated = {r['pairKey']:r for r in read_rows(output/'profile-table.jsonl.gz')}
            self.assertEqual(generated['observed']['evidenceType'],'observed')
            self.assertEqual(generated['blocked']['outcome'],'unresolved')
            self.assertEqual(generated['prediction']['evidenceType'],'predicted_unvalidated')
            self.assertFalse(generated['prediction']['verified'])
            cell = next(r for r in read_rows(output/'civilization-table.jsonl.gz') if r['pairKey']=='prediction')
            self.assertEqual(cell['outcome'],'b_win')
            self.assertEqual(cell['sourceOutcome'],'unresolved')
            self.assertEqual(result['summary']['predictedPairs'],1)
            self.assertEqual(source_hashes,{name:sha((inf/name).read_bytes()) for name in names})


if __name__ == '__main__':
    unittest.main()
