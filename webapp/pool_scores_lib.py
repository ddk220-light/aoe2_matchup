"""Pure functions for the pool-scores derivation pipeline.

No I/O: every function takes plain values or in-memory collections and
returns plain values. The orchestrator (derive_pool_scores.py) is
responsible for reading from matchup_db and writing to pool_scores.db.
"""
import datetime
from collections import defaultdict

from unit_lines import UNIT_LINES

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


POOL_ROLES = {
    "infantry": {
        "GC": ["militia", "knight", "archer"],
        "AC": ["knight", "camel", "steppe_lancer", "elephant"],
        "AT": ["spear", "skirmisher", "light_cav"],
    },
    "stable": {
        "GC": ["militia", "knight", "archer"],
        "AC": ["knight", "camel", "steppe_lancer", "elephant", "light_cav"],
    },
    "archer": {
        "GC": ["militia", "knight", "archer"],
        "AA": ["archer", "skirmisher", "cav_archer", "gunpowder"],
    },
}

POOL_WEIGHTS = {
    "infantry": {"GC": 0.70, "AC": 0.15, "AT": 0.15},
    "stable":   {"GC": 0.70, "AC": 0.30},
    "archer":   {"GC": 0.70, "AA": 0.30},
}


def final_score_for_pool(role_means: dict[str, float], pool: str) -> float:
    """Apply pool-specific role weights. Missing roles count as 0."""
    weights = POOL_WEIGHTS[pool]
    return sum(weights[r] * role_means.get(r, 0.0) for r in weights)


def compute_shape(raw_signed_scores) -> dict:
    """Distribution descriptors over RAW signed_scores (not adjusted).

    Win/loss rates are computed from the raw HP-based signed_score so
    they describe the underlying battle outcomes regardless of which
    axis is being scored. Used to drive UI profile labels later.
    """
    values = list(raw_signed_scores)
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": 0.0, "stddev": 0.0,
                "win_rate": 0.0, "decisive_win_rate": 0.0,
                "big_win_rate": 0.0, "catastrophic_loss_rate": 0.0}
    mean_v = sum(values) / n
    var = sum((x - mean_v) ** 2 for x in values) / n
    return {
        "n": n,
        "mean": mean_v,
        "stddev": var ** 0.5,
        "win_rate": 100.0 * sum(1 for x in values if x > 0) / n,
        "decisive_win_rate": 100.0 * sum(1 for x in values if x > 30) / n,
        "big_win_rate": 100.0 * sum(1 for x in values if x > 50) / n,
        "catastrophic_loss_rate": 100.0 * sum(1 for x in values if x < -50) / n,
    }


# ---------------------------------------------------------------------------
# Task 10: derive_unit_scores — integration entry point
# ---------------------------------------------------------------------------

def _opponent_to_lines() -> dict:
    """Map every imperial-age opponent slug to the list of line keys it appears in.

    Cached on first call. Pre-computing avoids O(units × lines) scans
    inside the per-row hot loop.
    """
    out: dict = defaultdict(list)
    for line_key in UNIT_LINES:
        for slug in line_imperial_slugs(UNIT_LINES, line_key):
            out[slug].append(line_key)
    return dict(out)


_OPP_TO_LINES_CACHE: dict | None = None


def _opponent_lines(opp_slug: str) -> list:
    global _OPP_TO_LINES_CACHE
    if _OPP_TO_LINES_CACHE is None:
        _OPP_TO_LINES_CACHE = _opponent_to_lines()
    return _OPP_TO_LINES_CACHE.get(opp_slug, [])


def derive_unit_scores(*, civ: str, unit_slug: str, scale: str,
                       rows: list,
                       sim_version=None) -> list:
    """Derive 3 output rows (one per axis) for one (civ, unit, scale).

    `rows` is the list of matchup_battles rows for this unit at this
    scale. Each row must have the keys used by `_row()` in the tests.
    Returns an empty list if the unit's pool can't be determined
    (e.g. siege/naval/monk, out of scope for this stage).

    Each opponent's line is bucketed into ALL matching roles — a line may
    appear in more than one role (e.g. knight counts in both GC and AC for
    the infantry pool, producing the ~0.27 effective weight described in
    the spec).
    """
    pool = unit_to_pool(UNIT_LINES, unit_slug)
    if pool is None:
        return []

    role_def = POOL_ROLES[pool]
    # Bucket: (line_key, role) -> axis -> {dedup_group: value}
    line_axis_values: dict = defaultdict(lambda: {"hp": {}, "cost": {}, "speed": {}})
    # Raw HP signed scores (unadjusted) keyed by dedup_group — for shape descriptors.
    # All three axes share the same underlying battle outcomes.
    raw_hp_by_dedup: dict = {}

    for r in rows:
        opp_slug = r["opp_unit_slug"]
        opp_line_keys = _opponent_lines(opp_slug)
        if not opp_line_keys:
            continue

        my_total = r["my_count"] * weighted_cost(
            r["my_cost_food"], r["my_cost_wood"], r["my_cost_gold"])
        opp_total = r["opp_count"] * weighted_cost(
            r["opp_cost_food"], r["opp_cost_wood"], r["opp_cost_gold"])
        raw_hp = hp_score(r["team1_hp_pct"], r["team2_hp_pct"], r["winner"])
        adj_hp = apply_loss_aversion(raw_hp)
        cost = cost_score(r["team1_hp_pct"], r["team2_hp_pct"], r["winner"],
                          my_total, opp_total)
        speed = speed_score(r["winner"], r["game_time_s"])

        dedup = r["dedup_group"]

        # Track raw HP for shape (first dedup_group entry wins).
        raw_hp_by_dedup.setdefault(dedup, raw_hp)

        # Bucket per-axis adjusted values; a line may appear in multiple roles
        # (e.g. knight is in both GC and AC for infantry — intentional per spec).
        for line_key in opp_line_keys:
            for role, lines in role_def.items():
                if line_key in lines:
                    line_axis_values[(line_key, role)]["hp"].setdefault(dedup, adj_hp)
                    line_axis_values[(line_key, role)]["cost"].setdefault(dedup, cost)
                    line_axis_values[(line_key, role)]["speed"].setdefault(dedup, speed)

    # Compute shape from raw HP signed scores (shared across all axes).
    shape = compute_shape(raw_hp_by_dedup.values())

    # Build one output row per axis.
    derived_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    out_rows = []
    for axis in ("hp", "cost", "speed"):
        # Per-line mean → per-role mean across lines that had data.
        role_means: dict = {}
        for role, lines in role_def.items():
            line_vals = []
            for line in lines:
                vals = line_axis_values.get((line, role), {}).get(axis, {})
                if vals:
                    line_vals.append(sum(vals.values()) / len(vals))
            if line_vals:
                role_means[role] = sum(line_vals) / len(line_vals)
            else:
                role_means[role] = 0.0

        final = final_score_for_pool(role_means, pool)
        weights = POOL_WEIGHTS[pool]

        out_rows.append({
            "civ_name": civ, "unit_slug": unit_slug,
            "pool": pool, "scale": scale, "axis": axis,
            "final_score": final,
            "gc": role_means.get("GC", 0.0) if "GC" in weights else None,
            "ac": role_means.get("AC", 0.0) if "AC" in weights else None,
            "at": role_means.get("AT", 0.0) if "AT" in weights else None,
            "aa": role_means.get("AA", 0.0) if "AA" in weights else None,
            "n": shape["n"], "mean": shape["mean"], "stddev": shape["stddev"],
            "win_rate": shape["win_rate"],
            "decisive_win_rate": shape["decisive_win_rate"],
            "big_win_rate": shape["big_win_rate"],
            "catastrophic_loss_rate": shape["catastrophic_loss_rate"],
            "sim_version": sim_version, "derived_at": derived_at,
        })
    return out_rows
