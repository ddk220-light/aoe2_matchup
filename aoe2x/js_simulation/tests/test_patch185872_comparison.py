import copy
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'tools/prepare_recorded_comparison.py'


class ComparisonPreparationTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(TOOL.exists(), 'comparison preparation tool exists')
        spec = importlib.util.spec_from_file_location('recorded_comparison', TOOL)
        self.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tool)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'reference.db'
        with closing(sqlite3.connect(self.db)) as connection:
            connection.executescript('''
                CREATE TABLE ref_units (id INTEGER PRIMARY KEY, civ_name TEXT, unit_name TEXT,
                    unit_slug TEXT, unit_master INTEGER, age TEXT, final_cost_food REAL,
                    final_cost_wood REAL, final_cost_gold REAL, unit_class INTEGER);
                CREATE TABLE ref_unit_mechanics (ref_unit_id INTEGER, mode TEXT, is_default INTEGER,
                    mechanics_json TEXT, mechanics_hash TEXT, source_build TEXT);
                CREATE TABLE ref_auxiliary_mechanics (actor_slug TEXT, mode TEXT,
                    mechanics_json TEXT, mechanics_hash TEXT, source_build TEXT);
            ''')
            for row, behavior in [
                ((1, 'Saxons', 'Elite Hearth Troop', 'elite_hearth_troop_saxons', 2706, 'Imperial', 0, 80, 35, 6), 'melee'),
                ((2, 'Armenians', 'Elite Composite Bowman', 'elite_composite_bowman_armenians', 1802, 'Imperial', 0, 35, 45, 0), 'mobile_ranged'),
                ((3, 'Bohemians', 'Houfnice', 'bombard_cannon', 1709, 'Imperial', 0, 225, 225, 13), 'siege_ranged'),
            ]:
                connection.execute('INSERT INTO ref_units VALUES (?,?,?,?,?,?,?,?,?,?)', row)
                mechanics = dict(unit_slug=row[3], unit_master=row[4], civilization=row[1], behavior_class=behavior)
                connection.execute('INSERT INTO ref_unit_mechanics VALUES (?,?,?,?,?,?)',
                                   (row[0], 'default', 1, json.dumps(mechanics), 'profile-hash', 'dat-hash'))
            connection.execute('INSERT INTO ref_auxiliary_mechanics VALUES (?,?,?,?,?)',
                               ('scout_cavalry', 'default', json.dumps({'unit_master': 448, 'hp': 95}), 'aux-hash', 'dat-hash'))
            connection.commit()
        self.archive = self.root / 'archive'
        self.archive.mkdir()
        self.match = dict(jobId='capture-1', plan={
            'matchupId': 'hearth_vs_bowman',
            'side2': dict(civ='Saxons', slug='elite_hearth_troop_saxons', label='Elite Hearth Troop', count=26,
                          effectiveCost=dict(food=0, wood=64, gold=28), weightedCost=88.4),
            'side3': dict(civ='Armenians', slug='elite_composite_bowman_armenians', label='Elite Composite Bowman', count=27,
                          effectiveCost=dict(food=0, wood=35, gold=45), weightedCost=81),
            'balance': {'comparisonPolicy': 'geometric_full_discount_weighted_resources_v3'},
            'scenario': {'player4Count': 6, 'family': 'melee_vs_ranged'},
        }, files={'frames.bin': {'path': 'fight.frames.bin'}, 'battle.mp4': {'path': 'fight.mp4'}},
            recording={'clock': {'rows': 'video_seconds', 'gameSpeed': 1.7}},
            capture={'capture': dict(winnerOwner=3, survivors=26, winnerHp=1111, winnerStartingHp=1350,
                                    eliminationTimeSeconds=19.41, gameVersion=185872)})

    def prepare(self, match=None):
        (self.archive / 'run.json').write_text(json.dumps({'matchups': [match or self.match]}))
        return self.tool.prepare_document(self.db, [self.archive / 'run.json'])

    def test_calculated_inputs_ignore_capture_counts_and_costs(self):
        first = self.prepare()
        altered = copy.deepcopy(self.match)
        altered['plan']['side2'].update(count=1, effectiveCost={'food': 999, 'wood': 999, 'gold': 999}, weightedCost=2997)
        altered['plan']['scenario']['player4Count'] = 10
        second = self.prepare(altered)
        self.assertEqual(first['jobs'], second['jobs'])
        job = first['jobs'][0]
        self.assertNotIn('count', job['teams'][0])
        self.assertEqual(job['teams'][0]['effectiveCost'], dict(food=0, wood=64, gold=28))
        self.assertEqual(job['player4Count'], 6)
        self.assertEqual(job['scenario']['auxiliaryArmiesByOwner']['4']['mechanics']['unit_master'], 448)
        expected = second['metadata']['matchups'][0]['expected']
        self.assertEqual(first['metadata']['matchups'][0]['recordingClock']['gameSpeed'], 1.7)
        self.assertEqual(expected['side2']['count'], 1)
        self.assertEqual(expected['player4Count'], 10)
        self.assertEqual(expected['outcome']['winnerHp'], 1111)

    def test_label_resolves_canonical_identity_and_calculates_rounded_ranged_count(self):
        match = copy.deepcopy(self.match)
        match['plan']['side3'].update(civ='Bohemians', slug='houfnice_bohemians', label='Houfnice')
        doc = self.prepare(match)
        self.assertEqual(doc['jobs'][0]['teams'][1]['mechanics']['unit_slug'], 'bombard_cannon')
        self.assertEqual(doc['jobs'][0]['player4Count'], 7)
        self.assertEqual(doc['metadata']['matchups'][0]['calculatedSetup']['counts'], [27, 12])

    def test_missing_mechanics_is_reported_instead_of_substituting_fixture(self):
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute('DELETE FROM ref_unit_mechanics WHERE ref_unit_id=1')
            connection.commit()
        with self.assertRaisesRegex(ValueError, 'mechanics'):
            self.prepare()

    def test_close_recordings_are_not_calibration_targets(self):
        match = copy.deepcopy(self.match)
        match['capture']['capture'].update(winnerHp=270, winnerStartingHp=1350)
        document = self.prepare(match)
        self.assertEqual(document['jobs'], [])
        self.assertEqual(document['metadata']['matchups'], [])

    def test_decisive_threshold_uses_winner_army_starting_hp(self):
        match = copy.deepcopy(self.match)
        match['capture']['capture'].update(winnerHp=809, winnerStartingHp=1350)
        self.assertEqual(len(self.prepare(match)['jobs']), 0)
        match['capture']['capture']['winnerHp'] = 810
        self.assertEqual(len(self.prepare(match)['jobs']), 1)

    def test_blackwood_purchase_divisor_is_physical_units_only(self):
        costs, evidence = self.tool.effective_cost(dict(civ_name='Tupi', unit_master=2581,
            final_cost_food=0, final_cost_wood=60, final_cost_gold=30))
        self.assertEqual(costs, dict(food=0, wood=30, gold=15))
        self.assertEqual(evidence['unitsPerPurchase'], 2)

    def test_saxon_foot_discount_is_not_limited_to_hearth(self):
        row = dict(civ_name='Saxons', unit_master=2704, unit_class=6,
                   final_cost_food=65, final_cost_wood=0, final_cost_gold=45)
        self.assertEqual(self.tool.effective_cost(row)[0], dict(food=52, wood=0, gold=36))
        row.update(unit_master=2701, unit_class=36)
        self.assertEqual(self.tool.effective_cost(row)[0], dict(food=65, wood=0, gold=45))


if __name__ == '__main__':
    unittest.main()
