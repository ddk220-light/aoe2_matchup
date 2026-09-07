"""Regression checks for matchup annotations in the static-panel pilot."""
import json
import sqlite3
import unittest

from overlay.static_stats import REPO, bonus_damage, modifiers, upgraded


class StaticStatsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with sqlite3.connect(f'file:{REPO / "data/golden/aoe2_reference.db"}?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            cls.tiger, cls.bowman = [dict(db.execute(
                'SELECT * FROM ref_units WHERE unit_slug=? AND age=?', (slug, 'Imperial')
            ).fetchone()) for slug in ('elite_tiger_cavalry_wei', 'elite_composite_bowman_armenians')]

    def test_pilot_displays_only_outgoing_bonus_damage(self):
        self.assertEqual(modifiers(self.tiger, self.bowman), {'attackBonus': 7})
        self.assertEqual(modifiers(self.bowman, self.tiger), {'attackBonus': 0})

    def test_base_and_technology_stats_do_not_include_matchup_bonus(self):
        self.assertEqual(upgraded(self.tiger, 'attack'), '13+4')
        self.assertEqual(upgraded(self.bowman, 'range'), '4+3')

    def test_bonus_armor_offsets_only_its_matching_class(self):
        target = dict(self.bowman)
        armor = json.loads(target['final_armors_json'])
        armor['15'] = 3
        target['final_armors_json'] = json.dumps(armor)
        self.assertEqual(bonus_damage(self.tiger, target), 4)
        armor['15'] = 10
        target['final_armors_json'] = json.dumps(armor)
        self.assertEqual(bonus_damage(self.tiger, target), 0)


if __name__ == '__main__':
    unittest.main()
