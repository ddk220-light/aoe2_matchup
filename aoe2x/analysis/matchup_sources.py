"""S-measurement backends behind one interface: the Windows batch baseline DB
(matchup_means, scale '3k') or fresh local position-engine sims.

Both expose:
  .score(subject, opponent)  -> S in [-100, 100]  (or None if unavailable)
  .detail(subject, opponent) -> dict with S plus sd/n/hp/counts (or None)

S is subject-positive: > 0 means the subject wins. For the DB source S is the
multi-seed `mean` from matchup_means; hp-left / counts come from the
representative matchup_battles row (team1 = subject). Missing pair -> skip with
a warning (return None), never abort (locked decision 2026-07-05).
"""
import sqlite3
import statistics
import sys

BUDGET = 3000
SCALE = "3k"


class MatchupDbSource:
    """Reads matchup_means (S = mean, subject-positive) plus sd/n, and the
    representative matchup_battles row for hp-left / start counts."""

    def __init__(self, db_path):
        self.db_path = str(db_path)
        self.db = sqlite3.connect(self.db_path)

    def detail(self, subject, opponent):
        m = self.db.execute(
            "SELECT mean, sd, n, verdict FROM matchup_means"
            " WHERE my_civ=? AND my_slug=? AND opp_civ=? AND opp_slug=?"
            " AND scale=?",
            (subject["civ"], subject["slug"], opponent["civ"], opponent["slug"],
             SCALE)).fetchone()
        if m is None:
            print(f"[matchup-db] WARNING missing means row: "
                  f"{subject['civ']}/{subject['slug']} vs "
                  f"{opponent['civ']}/{opponent['slug']} @{SCALE} — skipping",
                  file=sys.stderr)
            return None
        b = self.db.execute(
            "SELECT team1_hp_pct, team2_hp_pct, my_count, opp_count,"
            " team1_start_count, team2_start_count FROM matchup_battles"
            " WHERE my_civ=? AND my_unit_slug=? AND opp_civ=? AND opp_unit_slug=?"
            " AND scale=?",
            (subject["civ"], subject["slug"], opponent["civ"], opponent["slug"],
             SCALE)).fetchone()
        hp1 = b[0] if b else 0.0
        hp2 = b[1] if b else 0.0
        return {
            "S": m[0], "sd": m[1], "n": m[2], "verdict": m[3],
            "hp1": hp1, "hp2": hp2,
            "counts": (b[4], b[5]) if b else (None, None),
        }

    def score(self, subject, opponent):
        d = self.detail(subject, opponent)
        return None if d is None else d["S"]


class LocalSimSource:
    """Fresh simulation_real battles, mean margin over seeds (1..8 by default).

    Requires the pool/subject to be packed with combat dicts (with_combat=True),
    which pulls in aoe2x.sim / numpy — imported lazily here.
    """

    def __init__(self, seeds=(1, 2, 3, 4, 5, 6, 7, 8), budget=BUDGET):
        self.seeds = tuple(seeds)
        self.budget = budget

    def _margins(self, subject, opponent):
        from aoe2x.sim.simulation_real import simulate_real_battle
        margins, last = [], None
        for seed in self.seeds:
            winner, r1, r2, hp1, hp2 = simulate_real_battle(
                subject["combat"], opponent["combat"], self.budget,
                seed=seed, return_hp=True, _legacy_tuple=True)
            margins.append((hp1 - hp2) * 100.0)
            last = (hp1, hp2)
        return margins, last

    def score(self, subject, opponent):
        margins, _ = self._margins(subject, opponent)
        return statistics.fmean(margins)

    def detail(self, subject, opponent):
        margins, last = self._margins(subject, opponent)
        hp1, hp2 = last
        return {
            "S": statistics.fmean(margins),
            "sd": statistics.pstdev(margins) if len(margins) > 1 else 0.0,
            "n": len(margins), "verdict": None,
            "hp1": hp1, "hp2": hp2, "counts": (None, None),
        }
