import unittest
import copy
import json
import subprocess
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.dbgen.unit_analyzer import UnitAnalyzer, UnitStats
from aoe2x.dbgen.config import ATTR_FOOD_COST, ATTR_GOLD_COST, ATTR_WOOD_COST

class CostEffectsTest(unittest.TestCase):
    def test_absolute_cost_replacement_then_discount(self):
        analyzer=UnitAnalyzer.__new__(UnitAnalyzer)
        stats=UnitStats(cost_food=35,cost_gold=45,cost_wood=20)
        # Corvinian Army's installed effect sets food to 80 and gold to zero.
        analyzer._set_attribute(stats,ATTR_FOOD_COST,80)
        analyzer._set_attribute(stats,ATTR_GOLD_COST,0)
        analyzer._set_attribute(stats,ATTR_WOOD_COST,100)
        analyzer._multiply_attribute(stats,ATTR_WOOD_COST,.5)
        self.assertEqual((stats.cost_food,stats.cost_gold,stats.cost_wood),(80,0,50))

    def test_capture_gate_rejects_legacy_and_tampered_counts(self):
        code="import {createLabPlan} from './aoe2x/js_simulation/tools/aoe2lab_worker.mjs'; console.log(JSON.stringify(createLabPlan({schemaVersion:1,side2:{slug:'elite_champi_warrior_incas'},side3:{slug:'elite_huskarl'},balance:{mode:'equal_resources',cap:27}})));"
        plan=json.loads(subprocess.check_output(['node','--input-type=module','-e',code]))
        self.assertTrue(validate_plan_costs(plan)['verified'])
        legacy=copy.deepcopy(plan);legacy['balance'].pop('costBasis')
        with self.assertRaisesRegex(ValueError,'Legacy or stale'):validate_plan_costs(legacy)
        bad=copy.deepcopy(plan);bad['side3']['count']=18;bad['side3']['armyWeightedResources']=18*78
        with self.assertRaisesRegex(ValueError,'Army counts'):validate_plan_costs(bad)

if __name__=='__main__':unittest.main()
