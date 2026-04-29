"""Pure functions for the pool-scores derivation pipeline.

No I/O: every function takes plain values or in-memory collections and
returns plain values. The orchestrator (derive_pool_scores.py) is
responsible for reading from matchup_db and writing to pool_scores.db.
"""

LAMBDA = 2.0
T_MAX_SECONDS = 120.0


def apply_loss_aversion(x: float, lam: float = LAMBDA) -> float:
    """Multiply negative values by `lam`; leave non-negative values unchanged.

    Locked-in design (see spec §"Loss aversion"). Asymmetric: widens the
    gap between losses and wins of the same magnitude, but preserves
    linearity on each side of zero so weighted aggregation works.
    """
    return x if x >= 0 else lam * x


def hp_score(team1_hp_pct: float, team2_hp_pct: float, winner: int) -> float:
    """Raw signed_score for a battle, signed from team1's perspective.

    +100 = team1 won at full HP with opp dead.
    -100 = team1 dead, opp at full HP.
       0 = tie / no decision.
    """
    if winner == 0:
        return 0.0
    if winner == 1:
        return 100.0 * (team1_hp_pct - team2_hp_pct)
    if winner == 2:
        return -100.0 * (team2_hp_pct - team1_hp_pct)
    raise ValueError(f"unexpected winner value: {winner!r}")


def weighted_cost(food: float | None, wood: float | None, gold: float | None) -> float:
    """Resource cost with gold weighted higher.

    Mirrors `_calc_weighted_cost` in webapp/best_units.py:904 — same
    coefficients used by the existing 3k cost-matched scenarios.
    """
    return 0.8 * (wood or 0) + (food or 0) + 1.5 * (gold or 0)


def cost_score(t1_hp: float, t2_hp: float, winner: int,
               my_total_cost: float, opp_total_cost: float,
               lam: float = LAMBDA) -> float:
    """Per-battle resource cost from team1's perspective. Higher = worse.

    Cost framing per spec §"Resource cost axis":
      win:  cost = my_spent
      loss: cost = lam * (my_spent + opp_remaining)
      tie:  cost = my_spent + opp_remaining   (no lambda)
    """
    my_spent = my_total_cost * (1.0 - t1_hp)
    opp_remaining = opp_total_cost * t2_hp
    if winner == 1:
        return my_spent
    if winner == 2:
        return lam * (my_spent + opp_remaining)
    return my_spent + opp_remaining
