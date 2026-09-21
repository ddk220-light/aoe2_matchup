"""Editorial tally rules: an advantage means a victory, never a close defeat."""
import unittest

from build_champi_comparison_overlay import update_tally, rank_results


class TallyTests(unittest.TestCase):
    def test_defeat_ranks_minimize_enemy_hp_not_time(self):
        results=[dict(civ=c,winner='3',percent=p,end=t) for c,p,t in
                 [('Incas',97.6,10),('Mapuche',93.8,8),('Muisca',89.5,15),('Tupi',96.3,4)]]
        self.assertEqual(rank_results(results),{'Incas':4,'Mapuche':2,'Muisca':1,'Tupi':3})

    def test_victory_beats_close_defeat_and_ties_share_rank(self):
        results=[dict(civ=c,winner=w,percent=p) for c,w,p in
                 [('Incas','2',1),('Mapuche','3',.1),('Muisca','2',40),('Tupi','2',40)]]
        self.assertEqual(rank_results(results),{'Incas':3,'Mapuche':4,'Muisca':1,'Tupi':1})

    def test_four_defeats_do_not_award_the_least_bad_loss(self):
        results = [dict(civ=c, winner='3', percent=p) for c,p in
                   [('Incas',97.6), ('Mapuche',93.8), ('Muisca',89.5), ('Tupi',96.3)]]
        self.assertEqual(update_tally({}, 'Bowman', results), {})

    def test_only_winner_is_bold_and_previous_chapters_are_preserved(self):
        before = {'Incas': [{'opponent':'Jaguar Warrior', 'bold':False}]}
        result = update_tally(before, 'Ghulam', [
            dict(civ='Mapuche', winner='2', percent=7),
            dict(civ='Incas', winner='3', percent=1)])
        self.assertEqual(result['Mapuche'], [{'opponent':'Ghulam', 'bold':True}])
        self.assertEqual(result['Incas'], before['Incas'])
        self.assertNotIn('Mapuche', before)

    def test_best_victory_uses_unrounded_percent_and_is_not_bold(self):
        result = update_tally({}, 'Monaspa', [
            dict(civ='Mapuche', winner='2', percent=40.041),
            dict(civ='Incas', winner='2', percent=40.049),
            dict(civ='Tupi', winner='3', percent=99)])
        self.assertEqual(result, {'Incas':[{'opponent':'Monaspa', 'bold':False}]})

    def test_equal_winning_percent_credits_both(self):
        result = update_tally({}, 'Paladin', [
            dict(civ='Mapuche', winner='2', percent=40),
            dict(civ='Incas', winner='2', percent=40)])
        self.assertEqual(set(result), {'Incas','Mapuche'})
        self.assertTrue(all(not rows[0]['bold'] for rows in result.values()))


if __name__ == '__main__':
    unittest.main()
