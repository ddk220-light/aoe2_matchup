"""Result grouping must distinguish loss of the Inca advantage from all-civ flips."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report_champi_geometric import CIVS, group_pattern


class PatternTests(unittest.TestCase):
    def rows(self, old, new):
        return [
            dict(civ=c, oldResult=a, newResult=b, opponent="test", opponentLabel="Test")
            for c, a, b in zip(CIVS, old, new)
        ]

    def test_all_win_to_all_loss(self):
        g = group_pattern(self.rows(["win"] * 4, ["loss"] * 4))
        self.assertTrue(g["allWinsToAllLosses"])
        self.assertFalse(g["incaSoleWinLost"])

    def test_inca_only_advantage_lost(self):
        g = group_pattern(self.rows(["win", "loss", "loss", "loss"], ["loss"] * 4))
        self.assertTrue(g["incaSoleWinLost"])
        self.assertFalse(g["allWinsToAllLosses"])
        self.assertTrue(all(r["incaOnlyWinLost"] for r in g["contrasts"]))

    def test_pending_is_not_a_loss(self):
        g = group_pattern(self.rows(["win"] * 4, ["loss", None, None, None]))
        self.assertFalse(g["complete"])
        self.assertIsNone(g["newWinningCivs"])
        self.assertIsNone(g["patternChanged"])


if __name__ == "__main__":
    unittest.main()
