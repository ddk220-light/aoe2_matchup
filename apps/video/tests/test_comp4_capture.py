"""Regression checks for eight-owner validation and converted/replacement armies."""
import copy,unittest
from capture_comp4_spike import owner_units,opening_matches

class Comp4CaptureTests(unittest.TestCase):
    def test_conversion_changes_army_and_replacement_counts(self):
        entities={1:{'__type__':12,1:2554,2:5,12:35,3:4,4:5},
                  2:{'__type__':12,1:1252,2:6,12:40},
                  3:{'__type__':12,1:2554,2:1,12:0},
                  4:{'__type__':9,1:1775,2:1,12:1},
                  5:{'__type__':13,1:999,2:1,12:1}}
        owners=owner_units(entities)
        self.assertEqual(owners[1],[])
        self.assertEqual(owners[5][0]['master'],2554)
        self.assertEqual(owners[6][0]['master'],1252)
        self.assertEqual(sum(map(len,owners.values())),2)

    def test_partial_hp_validation_rejects_full_health_and_wrong_identity(self):
        plan={'subjectMaster':2554,'expectedGrpcOpponentMaster':1802,'subjectHP':{'1':65,'2':80,'3':65,'4':65},
              'pairs':[{'subjectOwner':p,'opponentOwner':p+4,'subjectCount':8,'opponentHP':[50]*5+[30] if p==1 else [50]*7} for p in range(1,5)]}
        owners={p:[{'master':2554,'hp':plan['subjectHP'][str(p)]} for _ in range(8)] for p in range(1,5)}
        owners.update({pair['opponentOwner']:[{'master':1802,'hp':hp} for hp in pair['opponentHP']] for pair in plan['pairs']})
        self.assertTrue(opening_matches(owners,plan))
        wrong=copy.deepcopy(owners);wrong[5][-1]['hp']=50
        self.assertFalse(opening_matches(wrong,plan))
        wrong=copy.deepcopy(owners);wrong[8][0]['master']=1800
        self.assertFalse(opening_matches(wrong,plan))
        wrong=copy.deepcopy(owners);wrong[2][0]['hp']=65
        self.assertFalse(opening_matches(wrong,plan))

if __name__=='__main__':unittest.main()
