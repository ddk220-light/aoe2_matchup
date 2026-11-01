import unittest
from build_civ_first_pass_delivery import project,validate_recovery_review,PATROL_PHYSICS
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

    def test_unknown_projection_physics_is_rejected(self):
        job,records,review,row=self.fixture()
        with self.assertRaises(AssertionError):project(row,job,dict(review,physicsVersion='unknown'))
        with self.assertRaises(AssertionError):validate_recovery_review(review,job,records,'unknown')

if __name__=='__main__':unittest.main()
