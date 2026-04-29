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


def speed_score(winner: int, game_time_s: float,
                t_max: float = T_MAX_SECONDS,
                lam: float = LAMBDA) -> float:
    """Linear speed score signed by win/loss.

    Spec §"Speed-to-win axis":
      win:  +100 * max(0, 1 - t/T_MAX)
      loss: -lam * 100 * max(0, 1 - t/T_MAX)
      tie:  0
    """
    factor = max(0.0, 1.0 - game_time_s / t_max)
    if winner == 1:
        return 100.0 * factor
    if winner == 2:
        return -lam * 100.0 * factor
    return 0.0


BUILDING_TO_POOL = {
    "Barracks": "infantry",
    "Stable": "stable",
    "Archery Range": "archer",
}


def line_imperial_slugs(unit_lines: dict, line_key: str) -> set[str]:
    """All imperial-age slugs that map to a line, across all civs.

    Used to filter eligible OPPONENTS — who counts as 'in the militia
    line' when computing GC vs militia? Answer: champion + every elite
    unique unit listed under militia['unique_units'] + extra_imperial.
    """
    line = unit_lines[line_key]
    out: set[str] = set()
    if line.get("imperial_slug"):
        out.add(line["imperial_slug"])
    for s in line.get("extra_imperial_slugs") or []:
        out.add(s)
    for civ, val in (line.get("unique_units") or {}).items():
        if val is None:
            continue
        if isinstance(val, list):
            for pair in val:
                if pair and pair[1]:
                    out.add(pair[1])
        else:
            if val[1]:
                out.add(val[1])
    return {s for s in out if s}


def _all_line_slugs_including_castle(unit_lines: dict, line_key: str) -> set[str]:
    """Imperial slugs PLUS castle slugs and castle UU slugs.

    Used for unit_to_pool — a unit that only appears in matchup_db at
    its castle slug (e.g. cataphract_byzantines vs elite_cataphract_byzantines)
    still needs to be classifiable.
    """
    line = unit_lines[line_key]
    out: set[str] = set(line_imperial_slugs(unit_lines, line_key))
    if line.get("castle_slug"):
        out.add(line["castle_slug"])
    for s in line.get("extra_castle_slugs") or []:
        out.add(s)
    for civ, val in (line.get("unique_units") or {}).items():
        if val is None:
            continue
        if isinstance(val, list):
            for pair in val:
                if pair and pair[0]:
                    out.add(pair[0])
        else:
            if val[0]:
                out.add(val[0])
    return {s for s in out if s}


def unit_to_pool(unit_lines: dict, unit_slug: str) -> str | None:
    """Return 'infantry' / 'stable' / 'archer' / None for a unit slug.

    None is returned for siege/naval/monk/etc — units outside the three
    pools we score in this stage. Callers should skip such units.
    """
    for line_key, line in unit_lines.items():
        if unit_slug in _all_line_slugs_including_castle(unit_lines, line_key):
            return BUILDING_TO_POOL.get(line.get("building"))
    return None


def dedup_mean(group_value_pairs) -> float | None:
    """Collapse rows by dedup_group (first wins), return mean of survivors.

    `group_value_pairs` is an iterable of `(dedup_group, value)` tuples.
    Returns `None` if the input is empty.

    First-wins matches the existing fingerprint-dedup convention in
    `run_matchup_battles.py`; rows in the same group are simulator-
    identical so the choice is arbitrary.
    """
    by_group: dict[str, float] = {}
    for group, value in group_value_pairs:
        if group not in by_group:
            by_group[group] = value
    if not by_group:
        return None
    return sum(by_group.values()) / len(by_group)
