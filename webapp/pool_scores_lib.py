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
