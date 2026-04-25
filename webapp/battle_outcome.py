"""BattleOutcome dataclass and aggregation helpers.

Single source of truth for the rich per-battle data captured by
simulate_real_battle() and persisted by both batch runners.
"""

from dataclasses import dataclass, replace
from collections import Counter


@dataclass
class BattleOutcome:
    winner: int                       # 1, 2, or 0 (draw)
    end_reason: str                   # "eliminated" | "decisive_lead" | "time_cap"
    game_time_s: float
    team1_hp_pct: float               # remaining HP / starting HP, 0..1
    team2_hp_pct: float
    team1_survivors: int
    team2_survivors: int
    team1_resources_lost: int
    team2_resources_lost: int
    team1_start_count: int
    team2_start_count: int


def signed_score(o: BattleOutcome) -> float:
    """Per-matchup signed score in [-100, +100].

    +100 = team1 won with full HP, opponent annihilated.
    -100 = team2 won with full HP.
    0    = draw.
    """
    if o.winner == 0:
        return 0.0
    if o.winner == 1:
        return round(100.0 * (o.team1_hp_pct - o.team2_hp_pct), 4)
    return round(-100.0 * (o.team2_hp_pct - o.team1_hp_pct), 4)


def _majority_winner(outcomes):
    counts = Counter(o.winner for o in outcomes)
    top = counts.most_common(2)
    if len(top) == 1 or top[0][1] > top[1][1]:
        return top[0][0]
    # Tie on votes — pick whichever side has the higher mean HP%.
    avg_t1 = sum(o.team1_hp_pct for o in outcomes) / len(outcomes)
    avg_t2 = sum(o.team2_hp_pct for o in outcomes) / len(outcomes)
    if avg_t1 > avg_t2:
        return 1
    if avg_t2 > avg_t1:
        return 2
    return 0


def average_outcomes(outcomes):
    """Aggregate N outcomes into one. Means for numeric fields, majority for
    winner (HP-tiebreak), most-common for end_reason."""
    if not outcomes:
        raise ValueError("average_outcomes called with empty list")
    n = len(outcomes)
    sample = outcomes[0]
    end_reason = Counter(o.end_reason for o in outcomes).most_common(1)[0][0]
    return replace(
        sample,
        winner=_majority_winner(outcomes),
        end_reason=end_reason,
        game_time_s=round(sum(o.game_time_s for o in outcomes) / n, 3),
        team1_hp_pct=round(sum(o.team1_hp_pct for o in outcomes) / n, 4),
        team2_hp_pct=round(sum(o.team2_hp_pct for o in outcomes) / n, 4),
        team1_survivors=int(round(sum(o.team1_survivors for o in outcomes) / n)),
        team2_survivors=int(round(sum(o.team2_survivors for o in outcomes) / n)),
        team1_resources_lost=int(round(sum(o.team1_resources_lost for o in outcomes) / n)),
        team2_resources_lost=int(round(sum(o.team2_resources_lost for o in outcomes) / n)),
    )
