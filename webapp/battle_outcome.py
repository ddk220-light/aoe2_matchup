"""Role: engine — BattleOutcome dataclass and aggregation helpers.

Single source of truth for the rich per-battle data captured by
simulate_real_battle() and persisted by both batch runners.
"""

from dataclasses import dataclass, replace
from collections import Counter


@dataclass
class BattleOutcome:
    winner: int
    end_reason: str
    game_time_s: float
    team1_hp_pct: float
    team2_hp_pct: float
    team1_survivors: int
    team2_survivors: int
    team1_resources_lost: int        # legacy: integer sum of all 3 resources
    team2_resources_lost: int
    team1_start_count: int
    team2_start_count: int

    # Per-resource breakdown — HP-weighted loss
    team1_food_lost: float = 0.0
    team1_wood_lost: float = 0.0
    team1_gold_lost: float = 0.0
    team2_food_lost: float = 0.0
    team2_wood_lost: float = 0.0
    team2_gold_lost: float = 0.0

    # Resources gained from kill-bonus civ effects (e.g. Mapuche +3 gold/kill)
    team1_food_gained: float = 0.0
    team1_wood_gained: float = 0.0
    team1_gold_gained: float = 0.0
    team2_food_gained: float = 0.0
    team2_wood_gained: float = 0.0
    team2_gold_gained: float = 0.0

    # Net value lost = (food + wood + gold lost) - (food + wood + gold gained)
    team1_value_lost: float = 0.0
    team2_value_lost: float = 0.0

    # Per-unit cost (cached so downstream consumers don't need to re-lookup)
    my_cost_food: float = 0.0
    my_cost_wood: float = 0.0
    my_cost_gold: float = 0.0
    opp_cost_food: float = 0.0
    opp_cost_wood: float = 0.0
    opp_cost_gold: float = 0.0


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

    def mean(attr):
        return round(sum(getattr(o, attr) for o in outcomes) / n, 4)

    def imean(attr):
        return int(round(sum(getattr(o, attr) for o in outcomes) / n))

    return replace(
        sample,
        winner=_majority_winner(outcomes),
        end_reason=end_reason,
        game_time_s=round(sum(o.game_time_s for o in outcomes) / n, 3),
        team1_hp_pct=mean("team1_hp_pct"),
        team2_hp_pct=mean("team2_hp_pct"),
        team1_survivors=imean("team1_survivors"),
        team2_survivors=imean("team2_survivors"),
        team1_resources_lost=imean("team1_resources_lost"),
        team2_resources_lost=imean("team2_resources_lost"),
        team1_food_lost=mean("team1_food_lost"),
        team1_wood_lost=mean("team1_wood_lost"),
        team1_gold_lost=mean("team1_gold_lost"),
        team2_food_lost=mean("team2_food_lost"),
        team2_wood_lost=mean("team2_wood_lost"),
        team2_gold_lost=mean("team2_gold_lost"),
        team1_food_gained=mean("team1_food_gained"),
        team1_wood_gained=mean("team1_wood_gained"),
        team1_gold_gained=mean("team1_gold_gained"),
        team2_food_gained=mean("team2_food_gained"),
        team2_wood_gained=mean("team2_wood_gained"),
        team2_gold_gained=mean("team2_gold_gained"),
        team1_value_lost=mean("team1_value_lost"),
        team2_value_lost=mean("team2_value_lost"),
    )
