import unittest

from overlay.unit_timeline import ordered_units, sample_at


class UnitTimelineTests(unittest.TestCase):
    def test_damage_is_not_shown_before_its_timestamp(self):
        rows = [{'hp': 50}, {'hp': 29}, {'hp': 0}]
        times = [0, 1.25, 2.5]
        self.assertEqual(sample_at(rows, times, 1.249)['hp'], 50)
        self.assertEqual(sample_at(rows, times, 1.25)['hp'], 29)
        self.assertEqual(sample_at(rows, times, 2.499)['hp'], 29)
        self.assertEqual(sample_at(rows, times, 2.5)['hp'], 0)

    def test_survivors_compact_without_reassigning_health(self):
        units = [{'id': 12, 'hp': 29}, {'id': 10, 'hp': 50}, {'id': 11, 'hp': 0}]
        self.assertEqual([(u['id'], u['hp']) for u in ordered_units(units)], [(10, 50), (12, 29), (11, 0)])
        units[1]['hp'] = 0
        self.assertEqual([(u['id'], u['hp']) for u in ordered_units(units)], [(12, 29), (10, 0), (11, 0)])

    def test_hold_after_last_sample_and_allow_observed_healing(self):
        rows = [{'hp': 80, 'maxHp': 145}, {'hp': 90, 'maxHp': 155}]
        self.assertEqual(sample_at(rows, [0, 1], 10), rows[-1])
        self.assertEqual(sample_at(rows, [0, 1], -.5), rows[0])


if __name__ == '__main__':
    unittest.main()
