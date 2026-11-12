"""Seed-sampling policies and context classification, ported from the 2026 runners.

RB = ``origin/simulations/civ-forecast-recovery-2026-11-10``; ``CM`` =
``aoe2x/js_simulation/node/civ-matchups`` on RB.

``three-then-ten`` (alias ``distinct-seeds-3-10``)
    ``required()`` in ``CM/forecast-validation-lib.mjs`` (identical rule in
    ``CM/run-adaptive.mjs`` and ``CM/mismatch-validation-lib.mjs``): run the
    initial seeds 0-2; when the three completed results do not all have the same
    ``winnerOwner`` (a draw has ``winnerOwner`` null, so win/loss/draw outcomes
    differing is the same test), add seeds 3-9.

``one-three-ten`` (alias ``distinct-seeds-1-3-10``)
    ``screeningDecision()``/``terminalMargin()`` in
    ``CM/forecast-screening-policy.mjs`` as used by sampling policy v3
    ``distinct-seeds-no-replay-v3`` (``CM/forecast-no-replay-policy.mjs``):
    run seed 0; accept it alone (``single_seed_confirmation``) only when the
    context has prior outcomes, seed 0's physical outcome equals every one of
    them, the loser has 0 survivors and 0 HP, and the winner keeps at least
    ``singleSeedMinimumWinnerHpFraction`` (0.25) of its starting HP; otherwise
    fall through to the three-then-ten rule. Without a prior the shortcut is
    impossible (``first_seed_disagrees``), so new contexts always get >= 3 seeds.
    Dropped from the 2026 code: the amendment-file checks and the three
    grandfathered ``legacyInProgressJobs`` (a 2026 transition artefact).

Classification (``canonicalOutcome()`` in ``CM/forecast-validation-lib.mjs``,
``screeningOutcome()`` in ``CM/forecast-screening-policy.mjs``): when the
completed seed set is final, ``a_win``/``b_win`` if every seed has the same
winning owner (2 or 3), mapped to the ``pairKey`` order through the context's
profile order; otherwise ``close_uncertain`` (mixed winners are never
majority-voted; an all-draw set is ``close_uncertain``). Identity pairs
(``equivalent``) never reach the runner.

Seed rows are journal rows (``record()`` fields): ``seed``, ``winnerOwner``,
``unit*``/``opponent*`` starting/remaining HP and survivors.
"""
from __future__ import annotations

import math

POLICIES = {"three-then-ten": "three-then-ten", "distinct-seeds-3-10": "three-then-ten",
            "one-three-ten": "one-three-ten", "distinct-seeds-1-3-10": "one-three-ten"}
SINGLE = "single_seed_confirmation"
MULTI = "multi_seed_validation"


def policy_name(value: str) -> str:
    try:
        return POLICIES[value]
    except KeyError:
        raise ValueError(f"unknown sampling policy {value!r}; known: {sorted(POLICIES)}") from None


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _check_rows(rows: list[dict], allowed: set[int]) -> None:
    seeds = [r["seed"] for r in rows]
    if len(set(seeds)) != len(seeds):
        raise ValueError("duplicate seed")
    if not all(isinstance(s, int) and s in allowed for s in seeds):
        raise ValueError(f"unknown seed in {sorted(seeds)}")


class Policy:
    def __init__(self, sampling: dict):
        self.name = policy_name(sampling["policy"])
        self.initial = list(sampling["initialSeeds"])
        self.extra = list(sampling["extraSeedsOnMixedWinners"])
        self.min_fraction = sampling.get("singleSeedMinimumWinnerHpFraction", 0.25)
        self.allowed = set(self.initial) | set(self.extra)

    # ------------------------------------------------------------- three/ten
    def full_required(self, rows: list[dict]) -> list[int]:
        seeds = {r["seed"]: r for r in rows}
        initial = [s for s in self.initial if s not in seeds]
        if initial:
            return initial
        if len({seeds[s]["winnerOwner"] for s in self.initial}) > 1:
            return [s for s in self.extra if s not in seeds]
        return []

    # --------------------------------------------------------------- decision
    def decision(self, job: dict, rows: list[dict], prior: list[str] | None) -> dict:
        """The sampling decision for a context's completed rows; ``requiredSeeds`` = what still has to run."""
        _check_rows(rows, self.allowed)
        if self.name == "three-then-ten":
            return {"evidenceLevel": MULTI, "reason": "three_then_ten", "requiredSeeds": self.full_required(rows)}
        prior = list(prior or [])
        first_seed = self.initial[0]
        first = next((r for r in rows if r["seed"] == first_seed), None)
        if first is None:
            return {"evidenceLevel": MULTI, "reason": "first_seed_required", "requiredSeeds": [first_seed]}
        margin = terminal_margin(first)
        outcome = physical_outcome(job, first["winnerOwner"])
        agrees = len(prior) > 0 and all(x == outcome for x in prior) and outcome != "close_uncertain"
        decisive = margin is not None and margin >= self.min_fraction
        if len(rows) > 1:
            reason = "additional_seed_evidence"
        elif not agrees:
            reason = "first_seed_disagrees"
        elif not decisive:
            reason = "first_seed_close_or_not_decisive"
        else:
            reason = "decisive_forecast_agreement"
        single = len(rows) == 1 and agrees and decisive
        return {"evidenceLevel": SINGLE if single else MULTI, "reason": reason,
                "firstSeedOutcome": outcome, "firstSeedAgrees": agrees, "firstSeedWinnerHpFraction": margin,
                "minimumWinnerHpFraction": self.min_fraction,
                "requiredSeeds": [] if single else self.full_required(rows)}

    def dispatchable(self, job: dict, rows: list[dict], prior: list[str] | None) -> list[int]:
        """Seeds that may start now. Equal to ``requiredSeeds`` except that a one-three-ten
        context without any prior cannot take the single-seed shortcut, so its whole initial
        set may start at once (same final seed set, more parallelism)."""
        required = self.decision(job, rows, prior)["requiredSeeds"]
        if self.name == "one-three-ten" and not prior and not rows:
            return list(self.initial)
        return required

    def complete(self, job: dict, rows: list[dict], prior: list[str] | None) -> bool:
        return not self.decision(job, rows, prior)["requiredSeeds"]

    def outcome(self, job: dict, rows: list[dict], prior: list[str] | None) -> str:
        if not self.complete(job, rows, prior):
            raise ValueError("incomplete seed set")
        return classify(job, rows)


def physical_outcome(job: dict, owner) -> str:
    """``physicalOutcome()``: owner 2/3 -> a_win/b_win in pairKey order; anything else close."""
    if owner not in (2, 3):
        return "close_uncertain"
    return "a_win" if job["profileHashes"][owner - 2] == job["pairKey"].split("|")[0] else "b_win"


def classify(job: dict, rows: list[dict]) -> str:
    """``canonicalOutcome()``/``screeningOutcome()`` for a final seed set."""
    if not rows:
        raise ValueError("no seeds")
    winners = {r["winnerOwner"] for r in rows}
    return physical_outcome(job, next(iter(winners))) if len(winners) == 1 else "close_uncertain"


def terminal_margin(row: dict):
    """``terminalMargin()``: winner's remaining HP fraction when the loser is wiped out, else None."""
    if row.get("winnerOwner") not in (2, 3):
        return None
    win, lose = ("unit", "opponent") if row["winnerOwner"] == 2 else ("opponent", "unit")
    start, remaining = row.get(win + "StartingHp"), row.get(win + "RemainingHp")
    if not _finite(start) or not _finite(remaining) or start <= 0 or remaining <= 0 or remaining > start:
        return None
    survivors = row.get(win + "Survivors")
    if not (_finite(survivors) and survivors > 0) or row.get(lose + "Survivors") != 0 or row.get(lose + "RemainingHp") != 0:
        return None
    return remaining / start


def winner_hp_fraction(row: dict) -> float:
    """``winnerHpFraction`` of a 2026 pair-review seed result."""
    return max(row["unitRemainingHp"] / row["unitStartingHp"], row["opponentRemainingHp"] / row["opponentStartingHp"])
