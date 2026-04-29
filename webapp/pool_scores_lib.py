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
