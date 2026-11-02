import unittest
import tempfile
import json
from pathlib import Path
from build_civ_first_pass_delivery import validate_exhausted_hash_failure,merge_candidate_batches,project,validate_recovery_review,PATROL_PHYSICS,STATIC_MEMO_PHYSICS,EVENT_STREAM_PHYSICS,TERMINAL_GOAL_PHYSICS
from civ_prediction_first_pass import sha,canonical

class DeliveryTests(unittest.TestCase):
    def fixture(self):
        job={'id':'j','pairKey':'a|b','profileHashes':['b','a'],'counts':[27,20],
             'weightedCosts':[50,90],'scenarioHash':'s','family':'ranged_vs_melee',
             'engineFamily':'kite','policy':'fixed'}
        records=[dict(job,matchupId='j',seed=i,outcome='win') for i in range(3)]
        references=[{'seed':i} for i in range(3)]
        review=dict(job,physicsVersion='collision-repair-v2',outcome='win',
            exactReplay={'seed':0,'passed':True},seedReferences=references,inputHash=sha(canonical(references)))
        row={'pairKey':'a|b','profiles':['a','b'],'outcome':'unresolved','evidenceType':'none','context':{}}
        return job,records,review,row

    def test_repaired_win_is_projected_as_unvalidated_and_orientation_is_kept(self):
        job,records,review,row=self.fixture();validate_recovery_review(review,job,records)
        result=project(row,job,review)
        self.assertEqual(result['outcome'],'b_win')
        self.assertEqual(result['context']['profiles'],['b','a'])
        self.assertEqual(result['evidenceType'],'predicted_unvalidated')
        self.assertFalse(result['verified']);self.assertTrue(result['needsValidation'])
        self.assertEqual(result['recoveryProjection']['measurementPhysicsVersion'],'collision-repair-v2')

    def test_missing_mixed_and_wrong_physics_are_not_valid_measurements(self):
        job,records,review,row=self.fixture()
        with self.assertRaises(AssertionError):validate_recovery_review(review,job,records[:2])
        records[2]['outcome']='loss'
        with self.assertRaises(AssertionError):validate_recovery_review(review,job,records)
        with self.assertRaises(AssertionError):validate_recovery_review(dict(review,physicsVersion='v3'),job,records)
        with self.assertRaises(AssertionError):project(dict(row,outcome='a_win'),job,review)

    def test_recovery_review_must_match_all_recorded_outcomes(self):
        job,records,review,row=self.fixture()
        with self.assertRaises(AssertionError):validate_recovery_review(dict(review,outcome='loss'),job,records)

    def test_patrol_candidate_requires_own_physics_and_preserves_fidelity_warning(self):
        job,records,review,row=self.fixture()
        review.update(physicsVersion=PATROL_PHYSICS,fidelityStatus='not_game_validated')
        with self.assertRaises(AssertionError):validate_recovery_review(review,job,records)
        validate_recovery_review(review,job,records,PATROL_PHYSICS)
        result=project(row,job,review)
        self.assertEqual(result['evidenceType'],'predicted_unvalidated')
        self.assertEqual(result['recoveryProjection']['measurementPhysicsVersion'],PATROL_PHYSICS)
        self.assertEqual(result['recoveryProjection']['fidelityStatus'],'not_game_validated')
        self.assertFalse(result['verified'])

    def test_static_memo_candidate_is_separate_and_requires_complete_seed_review(self):
        job,records,review,row=self.fixture()
        review.update(physicsVersion=STATIC_MEMO_PHYSICS,fidelityStatus='source_engine_fidelity_open')
        with self.assertRaises(AssertionError):validate_recovery_review(review,job,records)
        with self.assertRaises(AssertionError):validate_recovery_review(review,job,records[:2],STATIC_MEMO_PHYSICS)
        validate_recovery_review(review,job,records,STATIC_MEMO_PHYSICS)
        result=project(row,job,review)
        self.assertEqual(result['context']['profiles'],['b','a'])
        self.assertEqual(result['outcome'],'b_win')
        self.assertEqual(result['evidenceType'],'predicted_unvalidated')
        self.assertEqual(result['recoveryProjection']['measurementPhysicsVersion'],STATIC_MEMO_PHYSICS)
        self.assertEqual(result['recoveryProjection']['fidelityStatus'],'source_engine_fidelity_open')
        self.assertFalse(result['verified'])

    def test_event_stream_revision_is_separate_and_incomplete_or_mixed_seeds_do_not_fill_gap(self):
        job,records,review,row=self.fixture()
        review.update(physicsVersion=EVENT_STREAM_PHYSICS,fidelityStatus='source_geometry_fidelity_open')
        with self.assertRaises(AssertionError):validate_recovery_review(review,job,records[:2],EVENT_STREAM_PHYSICS)
        validate_recovery_review(review,job,records,EVENT_STREAM_PHYSICS)
        result=project(row,job,review)
        self.assertEqual(result['evidenceType'],'predicted_unvalidated')
        self.assertEqual(result['recoveryProjection']['measurementPhysicsVersion'],EVENT_STREAM_PHYSICS)
        self.assertEqual(result['sourceContext'],row['context'])
        self.assertFalse(result['verified'])
        records[2]['outcome']='loss'
        with self.assertRaises(AssertionError):validate_recovery_review(review,job,records,EVENT_STREAM_PHYSICS)

    def test_unknown_projection_physics_is_rejected(self):
        job,records,review,row=self.fixture()
        with self.assertRaises(AssertionError):project(row,job,dict(review,physicsVersion='unknown'))
        with self.assertRaises(AssertionError):validate_recovery_review(review,job,records,'unknown')

    def test_separate_campaigns_keep_provenance_and_conflicting_contexts_fail(self):
        job,records,review,row=self.fixture()
        def batch(hash_value, new_review=review, new_job=job):
            return [(new_job,new_review)],[{'physicsVersion':EVENT_STREAM_PHYSICS,'record':{'campaignHash':hash_value,'matchupId':'j','seed':0}}],{'campaignHash':hash_value}
        entries,ledger,metadata=merge_candidate_batches([batch('one'),batch('two')])
        self.assertEqual(len(entries),1)
        self.assertEqual([x['record']['campaignHash'] for x in ledger],['one','two'])
        self.assertEqual(len(metadata),2)
        with self.assertRaises(AssertionError):merge_candidate_batches([batch('one'),batch('one')])
        with self.assertRaises(AssertionError):merge_candidate_batches([batch('one'),batch('two',dict(review,outcome='loss'))])
        with self.assertRaises(AssertionError):merge_candidate_batches([batch('one'),batch('two',new_job=dict(job,profileHashes=['a','b']))])

    def test_terminal_goal_candidate_requires_complete_own_seed_set_and_retains_fidelity_gap(self):
        job,records,review,row=self.fixture()
        review.update(physicsVersion=TERMINAL_GOAL_PHYSICS,fidelityStatus='independent_game_fidelity_open')
        with self.assertRaises(AssertionError):validate_recovery_review(review,job,records[:2],TERMINAL_GOAL_PHYSICS)
        validate_recovery_review(review,job,records,TERMINAL_GOAL_PHYSICS)
        result=project(row,job,review)
        self.assertEqual(result['evidenceType'],'predicted_unvalidated')
        self.assertEqual(result['recoveryProjection']['measurementPhysicsVersion'],TERMINAL_GOAL_PHYSICS)
        self.assertEqual(result['recoveryProjection']['fidelityStatus'],'independent_game_fidelity_open')
        self.assertEqual(result['context']['profiles'],job['profileHashes'])
        self.assertFalse(result['verified'])

    def test_early_recovery_rejects_watchdogs_changed_records_and_unknown_jobs(self):
        record={'matchupId':'j','seed':0,'attempt':4,'watchdog':False,'resultOutcome':None,
                'error':{'name':'RangeError','message':'Invalid string length','stack':'hashCanonicalJson at runFight'}}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'attempts.jsonl'
            text=json.dumps(record).encode();path.write_bytes(text+b'\n')
            reference={'path':str(path),'line':1,'recordSha256':sha(text),'matchupId':'j','seed':0}
            self.assertEqual(validate_exhausted_hash_failure(reference,{'j':{}}),record)
            with self.assertRaises(AssertionError):validate_exhausted_hash_failure(reference,{})
            changed=dict(record,watchdog=True);text=json.dumps(changed).encode();path.write_bytes(text+b'\n')
            with self.assertRaises(AssertionError):validate_exhausted_hash_failure(reference,{'j':{}})
            with self.assertRaises(AssertionError):validate_exhausted_hash_failure(dict(reference,recordSha256=sha(text)),{'j':{}})
            changed=dict(record,attempt=1);text=json.dumps(changed).encode();path.write_bytes(text+b'\n')
            with self.assertRaises(AssertionError):validate_exhausted_hash_failure(dict(reference,recordSha256=sha(text)),{'j':{}})

if __name__=='__main__':unittest.main()
