import unittest
from overlay.battle_end import terminal_row

def row(t,a,b):return {'videoSeconds':t,'sides':{'2':[{'hp':a}],'3':[{'hp':b}]}}

class RecordedBattleEnd(unittest.TestCase):
    def test_posthumous_explosion_damage_is_retained(self):
        rows=[row(0,85,75),row(4.159,60,0),row(4.167,40,0),row(7,40,0)]
        self.assertIs(terminal_row(rows),rows[2])
    def test_idle_tail_and_healing_do_not_extend_battle(self):
        rows=[row(0,85,50),row(10,40,0),row(11,41,0),row(12,41,0)]
        self.assertIs(terminal_row(rows),rows[1])
    def test_later_wounds_can_change_winner_to_draw(self):
        rows=[row(0,10,10),row(1,0,3),row(2,0,0)]
        self.assertIs(terminal_row(rows),rows[-1])

if __name__=='__main__':unittest.main()
