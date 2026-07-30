"""Score tape truth cards against 20-seed sim-run distributions.

``score_card(tape_card, sim_cards, sim_durations=None) -> dict`` is the pure,
filesystem-free comparison: given one fight's tape truth card (Task 2's
shape) and a list of that fight's per-seed sim cards (each produced by
calling the SAME ``extract_card`` on a sim run's ``damage``/``missiles``
streams -- never a second metric implementation), it returns one verdict row
per metric x side plus an overall fight verdict and a reroll list.

``score_fight(run_id) -> dict`` is the disk-facing wrapper: it loads
``data/calibration/manifest.json`` (for composition), the tape's truth card
from ``data/calibration/truth/<run_id>.json``, and every
``D:/AI/aoe2_golden/simruns/<run_id>/seed-<n>.json`` file, runs each sim
seed's raw event stream through ``extract_card`` itself, and calls
``score_card``.

CLI:

    python -m aoe2x.calibration.score --all --label baseline
    python -m aoe2x.calibration.score --run-id elite_steppe__vs__arbalester

writes ``data/calibration/runs/<stamp>-<label>.json``.

Verdicts (per the design spec, ``docs/superpowers/specs/2026-07-30-combat-
calibration-design.md`` §3.6):

- **MATCH** -- the tape value lies inside the 20-seed sim distribution's
  [p10, p90] band, OR within the metric's tolerance of the sim median.
- **MISMATCH** -- outside both.
- **INCONCLUSIVE** -- the tape's OWN event count is too small to trust the
  apparent mismatch: fewer than 5 swing gaps for an interval metric, or (for
  a rate metric) a binomial 95% CI wider than the metric's tolerance.
  INCONCLUSIVE only ever *downgrades* an apparent MISMATCH -- a metric that
  already MATCHes is never relabelled.

Tolerances are NOT a single uniform number. Three hard-won, measured facts
from the corpus's two 4-repeat recording families
(``champion__vs__arbalester{,_r2,_r3,_r4}`` and
``champion__vs__heavy_cav_archer{,_r2,_r3,_r4}`` -- the only place the real
game's own run-to-run noise floor is directly observable) drive every
tolerance choice below:

1. **Asymmetric variance by role.** The side that comes out ahead in a given
   recording ("winner": ranked by (survivors, hp_remaining, kills) from the
   TAPE's own outcome) has a stable ``swing_interval_median`` -- repeat
   spread of 0.007s (arbalester family) to 0.031s (heavy-cav-archer family,
   using its 3 repeats where the same side actually won). The OTHER side
   ("loser")'s aggregates swing far more: damage_dealt spread up to 447,
   hp_remaining spread up to 447, survivors spread up to 9, kills spread up
   to 14, duration_s spread ~23.6% in BOTH families. A single uniform
   tolerance would be too tight for the loser's aggregates and (separately)
   too loose to mean anything for the winner's median. So every scalar
   tolerance below is role-conditioned: computed from the TAPE's own outcome
   for that specific fight, not a global family average, so it adapts
   automatically even when the "winner" flips between repeats of the same
   matchup (it does, once, in the heavy-cav-archer family).
2. **Order statistics are noisier than the median even for the stable
   side.** ``swing_interval_fastest`` (a single min() over all gaps) and
   ``churn`` (derived from it) swing by 0.254-0.358s (17.5-20%) on the
   WINNING side across repeats -- far more than the median's 0.007-0.031s.
   Both get their own, wider tolerance from the same winner/loser split.
3. **Rate metrics are comparatively stable.** ``effective_accuracy`` on the
   winning (ranged) side varies by only 0.003-0.044 absolute across repeats.
   A flat 0.05 (5 percentage points) tolerance comfortably covers this with
   headroom, for both roles (no repeat data exists for a losing ranged
   side's accuracy in this corpus, so the same number is used for both,
   flagged here as a documented assumption).

See ``docs/architecture/calibration-rig.md`` for the full worked numbers and
the repeat-family table these were read off of.

Two further hard requirements (from the design's "hard-won facts"):

- ``effective_accuracy`` for a trampling ranged unit can legitimately EXCEED
  1.0 (one projectile can register hits on several victims). It is never
  clamped anywhere in this module -- not in the reported/compared value, and
  not even internally: the binomial-CI helper used only to decide whether a
  rate metric is INCONCLUSIVE clamps its OWN working probability to
  ``[0, 1]`` (a CI is meaningless above 1), but that clamp never touches the
  value that gets scored or reported.
- Repeat recordings are grouped by ``matchup`` but scored (and reported)
  individually by ``run_id`` -- ``score_fight`` takes a ``run_id``, and the
  CLI's per-fight rows each carry both ``run_id`` and ``matchup`` so a reader
  can see repeats of one matchup side by side.

Winner agreement (the campaign's primary KPI, added 2026-07-30)
---------------------------------------------------------------

``verdict`` above is a conjunction over ~40 gated metric rows, so almost
every fight in a 105-fight corpus reads MISMATCH and the number barely
moves between experiments -- useless as a steering signal. Each fight
therefore also carries a ``winner`` block (``winner_match``,
``winner_agreement``; see ``_winner_block``) and the run carries a
``winner_summary`` rollup listing the flipped fights by name.

This is **measurement only**: it does not gate, does not feed ``verdict``,
and no tolerance or gating rule changed when it was added, so scoreboards
written before and after remain directly comparable.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aoe2x.calibration.extract import _composition_for_fight, extract_card
from aoe2x.paths import REPO_ROOT

CALIBRATION_DIR = REPO_ROOT / "data" / "calibration"
MANIFEST_PATH = CALIBRATION_DIR / "manifest.json"
TRUTH_DIR = CALIBRATION_DIR / "truth"
RUNS_DIR = CALIBRATION_DIR / "runs"
SIMRUNS_DIR = Path("D:/AI/aoe2_golden/simruns")

DEFAULT_SEEDS = list(range(1, 21))
Z95 = 1.96  # two-sided 95% normal-approx binomial CI

# ---------------------------------------------------------------------------
# Tolerances -- see the module docstring for the repeat-family evidence each
# number is read off of. `role` is "winner" or "loser", decided per fight
# from the tape's own outcome (see `_roles`).
# ---------------------------------------------------------------------------

# name -> {role: (absolute_floor_seconds, relative_fraction_of_tape_value)}
INTERVAL_TOL: dict[str, dict[str, tuple[float, float]]] = {
    "swing_interval_median": {"winner": (0.05, 0.05), "loser": (0.30, 0.25)},
    "swing_interval_fastest": {"winner": (0.30, 0.20), "loser": (0.50, 0.35)},
    "churn": {"winner": (0.30, 0.20), "loser": (0.50, 0.35)},
}

# Flat tolerances for rate metrics (0-1 nominally; effective_accuracy can
# exceed 1 for trample -- see module docstring).
RATE_TOL: dict[str, float] = {
    "effective_accuracy": 0.05,
    "trample_multi_rate": 0.08,
    "damage_histogram": 0.08,  # per damage-value bucket, as a fraction of hits
}

# name -> absolute floor (in the metric's own units)
COUNT_TOL_FLOOR: dict[str, float] = {
    "hits_landed": 2,
    "damage_dealt": 20.0,
    "kills": 2,
    "survivors": 2,
    "hp_remaining": 20.0,
    "trample_victims_mean": 0.5,
    "trample_victims_max": 1,
    "splash_fraction": 0.05,
}
COUNT_TOL_REL: dict[str, float] = {"winner": 0.15, "loser": 0.60}

GATED_INTERVAL = ["swing_interval_median", "swing_interval_fastest", "churn"]
GATED_RATE = [("effective_accuracy", "projectiles_fired")]
GATED_COUNT = ["hits_landed", "damage_dealt", "kills", "survivors", "hp_remaining"]
TRAMPLE_RATE = [("trample_multi_rate", "swing_count")]
TRAMPLE_COUNT = ["trample_victims_mean", "trample_victims_max", "splash_fraction"]
REPORTED_SIDE = ["first_blood"]

# Movement/geometry metrics the design marks reported-only because the JS
# engine's 30x20 open box deliberately does not model the tape's 16x16,
# ~39%-solid arena (see spec §7 risk 1). `mean_distance_tiles` is listed in
# the design's metric table, but extract_card takes no position stream at
# all (see its own module docstring: "no unit-position stream"), so no truth
# card in this corpus ever carries it -- there is nothing to score, and
# adding a second, position-based metric implementation here would violate
# the one-extractor rule. It is intentionally omitted, not silently dropped.

_VERDICT_RANK = {"MATCH": 0, "INCONCLUSIVE": 1, "MISMATCH": 2}


# ---------------------------------------------------------------------------
# Small stats helpers (stdlib only)
# ---------------------------------------------------------------------------


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolation percentile (numpy's default method), no numpy."""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = q * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def _dist(values: list[Any]) -> dict[str, Any] | None:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    return {
        "median": statistics.median(vals),
        "p10": _percentile(vals, 0.10),
        "p90": _percentile(vals, 0.90),
        "n": len(vals),
    }


def _binomial_ci_halfwidth(p: float, n: float) -> float:
    """95% CI half-width for a proportion, used only to gauge whether the
    tape has enough samples to trust an apparent mismatch. `p` is clamped to
    [0, 1] HERE ONLY (a CI on a proportion above 1 is meaningless) -- this
    clamp never touches the value that gets scored or reported; see
    `effective_accuracy` handling in the module docstring.
    """
    if not n:
        return float("inf")
    p = min(max(p, 0.0), 1.0)
    return Z95 * math.sqrt(p * (1 - p) / n)


def _worst_verdict(verdicts: list[str]) -> str:
    if not verdicts:
        return "MATCH"
    return max(verdicts, key=lambda v: _VERDICT_RANK.get(v, 0))


# ---------------------------------------------------------------------------
# Role (winner/loser) from the tape's own outcome
# ---------------------------------------------------------------------------


def _outcome_rank(side: dict) -> tuple[float, float, float]:
    """The one outcome ordering used everywhere: (survivors, hp_remaining,
    kills). Shared by `_roles` (tolerance selection) and `_winner_side`
    (the winner-agreement KPI) so the two can never drift apart.
    """
    return (side.get("survivors") or 0, side.get("hp_remaining") or 0.0, side.get("kills") or 0)


def _winner_side(sides: dict[str, dict]) -> str | None:
    """The winning side key by `_outcome_rank`, or None when the two sides
    are exactly tied (mutual annihilation) or the fight isn't 2-sided.

    Deliberately derived from the SAME per-side card fields for tape and
    sim, rather than reading the sim runner's own `winner_owner`: the point
    of the KPI is that both outcomes are judged by one rule (the
    one-extractor discipline applied to the outcome, not just the metrics).
    """
    keys = list(sides.keys())
    if len(keys) != 2:
        return None
    a, b = keys
    ra, rb = _outcome_rank(sides[a]), _outcome_rank(sides[b])
    if ra == rb:
        return None
    return a if ra > rb else b


def _roles(tape_sides: dict[str, dict]) -> dict[str, str]:
    """'winner'/'loser' per side key, from THIS fight's own tape outcome
    (ranked by (survivors, hp_remaining, kills)). See module docstring point
    1: this is recomputed per fight, not fixed per matchup, because the
    heavy-cav-archer repeat family shows the winner can flip between
    recordings of the very same matchup.
    """
    keys = list(tape_sides.keys())
    if len(keys) != 2:
        return {k: "loser" for k in keys}

    winner = _winner_side(tape_sides)
    if winner is None:
        # No clear winner signal (e.g. mutual annihilation) -- be
        # conservative and give both the wider "loser" tolerance.
        return {k: "loser" for k in keys}
    return {k: ("winner" if k == winner else "loser") for k in keys}


def _winner_block(tape_sides: dict[str, dict], sim_cards: list[dict]) -> dict[str, Any]:
    """The campaign's primary KPI: does the engine pick the same side to win?

    Two numbers, because they answer different questions:

    - ``winner_match`` compares the tape's winner against the winner implied
      by the sim's MEDIAN outcome (per-side median survivors / hp_remaining /
      kills across the seeds). This is the headline yes/no.
    - ``winner_agreement`` is the fraction of individual seeds whose own
      winner equals the tape's. A fight sitting at 0.55 is a coin flip the
      engine happens to be winning, not a fight the engine understands --
      the median-based bool alone would hide that.

    ``winner_match`` is None when either side of the comparison has no
    winner (a tie, or no sim cards at all) -- never silently False.
    """
    tape_winner = _winner_side(tape_sides)

    seed_winners = [_winner_side(c.get("sides") or {}) for c in sim_cards]
    n_seeds = len(seed_winners)

    sim_median_sides: dict[str, dict[str, Any]] = {}
    for side_key in tape_sides:
        present = [c["sides"][side_key] for c in sim_cards if side_key in c.get("sides", {})]
        if not present:
            continue
        sim_median_sides[side_key] = {
            name: statistics.median([s.get(name) or 0 for s in present])
            for name in ("survivors", "hp_remaining", "kills")
        }
    sim_winner = _winner_side(sim_median_sides)

    if tape_winner is None or sim_winner is None:
        match = None
    else:
        match = tape_winner == sim_winner

    agreement = None
    if n_seeds and tape_winner is not None:
        agreement = round(sum(1 for w in seed_winners if w == tape_winner) / n_seeds, 4)

    return {
        "tape_winner": tape_winner,
        "sim_median_winner": sim_winner,
        "winner_match": match,
        "winner_agreement": agreement,
        "n_seeds": n_seeds,
    }


# ---------------------------------------------------------------------------
# Per-metric scoring
# ---------------------------------------------------------------------------


def _score_scalar(tape_value: float, sim_values: list[Any], tolerance: float) -> dict[str, Any]:
    """Core MATCH/MISMATCH decision (the INCONCLUSIVE downgrade, which needs
    metric-specific context -- n_gaps or a rate denominator -- is applied by
    the caller).
    """
    dist = _dist(sim_values)
    if dist is None:
        return {
            "sim_median": None, "sim_p10": None, "sim_p90": None, "sim_n": 0,
            "delta": None, "tolerance": round(tolerance, 4), "verdict": "MISMATCH",
            "tol_z": None, "degenerate_band": None,
            "note": "sim produced no value for this metric across any seed",
        }
    inside = dist["p10"] <= tape_value <= dist["p90"]
    within_tol = abs(tape_value - dist["median"]) <= tolerance
    verdict = "MATCH" if (inside or within_tol) else "MISMATCH"
    return {
        "sim_median": round(dist["median"], 4), "sim_p10": round(dist["p10"], 4),
        "sim_p90": round(dist["p90"], 4), "sim_n": dist["n"],
        "delta": round(tape_value - dist["median"], 4), "tolerance": round(tolerance, 4),
        "verdict": verdict,
        # --- diagnostics (measurement only — neither field feeds the verdict) ---
        # tol_z: how many tolerances away from the sim median the tape sits.
        # <=1 is "would pass on tolerance alone"; 8.0 and 1.05 are both bare
        # "MISMATCH" without it, and only one of them is worth chasing.
        "tol_z": (round(abs(tape_value - dist["median"]) / tolerance, 3) if tolerance else None),
        # degenerate_band: the 20-seed [p10, p90] band collapsed to a single
        # point, so the "inside the band" arm of the verdict is doing no work
        # and the whole call rests on the tolerance arm. Common for integer
        # counts (survivors, kills) in lopsided fights; worth seeing, because
        # a zero-width band means the sim is deterministic on that metric and
        # ANY tape value off that point mismatches.
        "degenerate_band": (dist["p90"] - dist["p10"]) == 0,
    }


def _interval_tolerance(name: str, tape_value: float, role: str) -> float:
    abs_floor, rel = INTERVAL_TOL[name][role]
    return max(abs_floor, rel * abs(tape_value))


def _count_tolerance(name: str, tape_value: float, role: str) -> float:
    return max(COUNT_TOL_FLOOR[name], COUNT_TOL_REL[role] * abs(tape_value))


def _score_histogram(tape_side: dict, sim_sides: list[dict]) -> list[dict[str, Any]]:
    """One row per damage-value bucket (as a fraction of that side's own
    hits_landed, so buckets are comparable across different total hit
    counts), scored as a rate metric with the same INCONCLUSIVE-via-CI rule
    as any other rate metric.
    """
    tape_hist: dict[str, int] = tape_side.get("damage_histogram") or {}
    tape_total = tape_side.get("hits_landed") or 0
    keys = set(tape_hist.keys())
    for s in sim_sides:
        keys |= set((s.get("damage_histogram") or {}).keys())

    rows = []
    for key in sorted(keys, key=float):
        tape_count = tape_hist.get(key, 0)
        tape_frac = (tape_count / tape_total) if tape_total else 0.0
        sim_fracs = []
        for s in sim_sides:
            total = s.get("hits_landed") or 0
            cnt = (s.get("damage_histogram") or {}).get(key, 0)
            sim_fracs.append((cnt / total) if total else 0.0)

        row = _score_scalar(tape_frac, sim_fracs, RATE_TOL["damage_histogram"])
        if row["verdict"] == "MISMATCH":
            halfwidth = _binomial_ci_halfwidth(tape_frac, tape_total)
            if halfwidth > RATE_TOL["damage_histogram"]:
                row["verdict"] = "INCONCLUSIVE"
                row["note"] = f"tape has only {tape_total} hits backing damage_histogram[{key}]"
        row.update(name=f"damage_histogram[{key}]", tape=round(tape_frac, 4),
                   n=tape_total, gated=True)
        rows.append(row)
    return rows


def _score_side(side_key: str, tape_side: dict, sim_sides: list[dict], role: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for name in GATED_INTERVAL:
        tv = tape_side.get(name)
        if tv is None:
            continue
        sim_vals = [s.get(name) for s in sim_sides]
        tol = _interval_tolerance(name, tv, role)
        row = _score_scalar(tv, sim_vals, tol)
        n_gaps = (tape_side.get("n_events") or {}).get("gaps", 0)
        if row["verdict"] == "MISMATCH" and n_gaps < 5:
            row["verdict"] = "INCONCLUSIVE"
            row["note"] = f"tape has only {n_gaps} swing gaps (<5) for this side"
        row.update(name=name, side=side_key, tape=tv, n=n_gaps, gated=True, role=role)
        rows.append(row)

    for name, denom_field in GATED_RATE:
        tv = tape_side.get(name)
        if tv is None:
            continue
        sim_vals = [s.get(name) for s in sim_sides]
        tol = RATE_TOL[name]
        row = _score_scalar(tv, sim_vals, tol)
        n = tape_side.get(denom_field) or 0
        if row["verdict"] == "MISMATCH":
            halfwidth = _binomial_ci_halfwidth(tv, n)
            if halfwidth > tol:
                row["verdict"] = "INCONCLUSIVE"
                row["note"] = f"tape n={n} ({denom_field}) gives a CI wider than tolerance"
        row.update(name=name, side=side_key, tape=tv, n=n, gated=True, role=role)
        rows.append(row)

    for name in GATED_COUNT:
        tv = tape_side.get(name)
        if tv is None:
            continue
        sim_vals = [s.get(name) for s in sim_sides]
        tol = _count_tolerance(name, tv, role)
        row = _score_scalar(tv, sim_vals, tol)
        row.update(name=name, side=side_key, tape=tv, n=None, gated=True, role=role)
        rows.append(row)

    # Trample stats are gated only when the unit demonstrably tramples --
    # in the tape, or in at least one sim seed (so a sim that fails to
    # trigger trample at all still surfaces as a real mismatch rather than
    # being silently skipped).
    has_trample = (tape_side.get("trample_multi_rate") or 0) > 0 or any(
        (s.get("trample_multi_rate") or 0) > 0 for s in sim_sides
    )
    if has_trample:
        for name, denom_field in TRAMPLE_RATE:
            tv = tape_side.get(name)
            if tv is None:
                continue
            sim_vals = [s.get(name) for s in sim_sides]
            tol = RATE_TOL[name]
            row = _score_scalar(tv, sim_vals, tol)
            n = tape_side.get(denom_field) or 0
            if row["verdict"] == "MISMATCH":
                halfwidth = _binomial_ci_halfwidth(tv, n)
                if halfwidth > tol:
                    row["verdict"] = "INCONCLUSIVE"
                    row["note"] = f"tape n={n} ({denom_field}) gives a CI wider than tolerance"
            row.update(name=name, side=side_key, tape=tv, n=n, gated=True, role=role)
            rows.append(row)

        for name in TRAMPLE_COUNT:
            tv = tape_side.get(name)
            if tv is None:
                continue
            sim_vals = [s.get(name) for s in sim_sides]
            tol = _count_tolerance(name, tv, role)
            row = _score_scalar(tv, sim_vals, tol)
            row.update(name=name, side=side_key, tape=tv, n=None, gated=True, role=role)
            rows.append(row)

    hist_rows = _score_histogram(tape_side, sim_sides)
    for r in hist_rows:
        r.update(side=side_key, role=role)
    rows.extend(hist_rows)
    if hist_rows:
        rows.append({
            "name": "damage_histogram", "side": side_key, "role": role, "tape": None,
            "sim_median": None, "sim_p10": None, "sim_p90": None, "sim_n": None,
            "delta": None, "tolerance": None, "n": tape_side.get("hits_landed"),
            "gated": True, "verdict": _worst_verdict([r["verdict"] for r in hist_rows]),
            "note": f"rollup of {len(hist_rows)} damage-value buckets",
        })

    for name in REPORTED_SIDE:
        tv = tape_side.get(name)
        if tv is None:
            continue
        sim_vals = [s.get(name) for s in sim_sides]
        row = _score_scalar(tv, sim_vals, 0.5)
        row.update(name=name, side=side_key, tape=tv, n=None, gated=False, role=role)
        rows.append(row)

    return rows


def score_card(tape_card: dict, sim_cards: list[dict], sim_durations: list[float] | None = None) -> dict:
    """Compare one fight's tape truth card against its 20-seed sim-card
    distribution. `sim_cards` are extract_card's OWN output shape
    (`{"sides": {...}}`) -- callers must have already run each sim seed's
    raw damage/missile streams through extract_card themselves (see
    `score_fight` below), never a second metric implementation.
    """
    tape_sides = tape_card["sides"]
    roles = _roles(tape_sides)

    all_rows: list[dict[str, Any]] = []
    for side_key, tape_side in tape_sides.items():
        sim_sides = [c["sides"][side_key] for c in sim_cards if side_key in c.get("sides", {})]
        all_rows.extend(_score_side(side_key, tape_side, sim_sides, roles[side_key]))

    if sim_durations is not None:
        tv = tape_card.get("duration_s")
        if tv is not None:
            # Reported only (design spec §3.1/§7): the JS engine's open 30x20
            # box vs. the tape's 16x16, ~39%-solid arena makes fight length
            # geometry-confounded. Tolerance (25%) matches the ~23.6%
            # duration spread measured across BOTH repeat-run families --
            # i.e. this is the real game's own noise floor for duration, not
            # a guess.
            tol = max(5.0, 0.25 * tv)
            row = _score_scalar(tv, sim_durations, tol)
            row.update(name="duration_s", side=None, tape=tv, n=None, gated=False, role=None)
            all_rows.append(row)

    gated_verdicts = [r["verdict"] for r in all_rows if r.get("gated")]
    worst = _worst_verdict(gated_verdicts) if gated_verdicts else "MATCH"
    overall = {"MATCH": "PASS", "MISMATCH": "MISMATCH", "INCONCLUSIVE": "INCONCLUSIVE"}[worst]

    rerolls = [
        {"name": r["name"], "side": r["side"], "note": r.get("note")}
        for r in all_rows if r.get("gated") and r["verdict"] == "INCONCLUSIVE"
    ]

    winner = _winner_block(tape_sides, sim_cards)

    return {
        "tag": tape_card.get("tag"),
        "run_id": tape_card.get("run_id"),
        "matchup": tape_card.get("matchup"),
        "metrics": all_rows,
        "verdict": overall,
        # Primary KPI, NOT gated: `verdict` above deliberately stays exactly
        # what it was so this run stays comparable to earlier scoreboards.
        # See `_winner_block`.
        "winner": winner,
        "winner_match": winner["winner_match"],
        "winner_agreement": winner["winner_agreement"],
        "rerolls": rerolls,
    }


# ---------------------------------------------------------------------------
# Disk-facing glue
# ---------------------------------------------------------------------------


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_manifest_fight(run_id: str) -> dict[str, Any]:
    for f in _load_manifest()["fights"]:
        if f["run_id"] == run_id:
            return f
    raise KeyError(f"no manifest entry for run_id={run_id!r}")


def _load_sim_cards(
    fight: dict[str, Any], seeds: list[int] = DEFAULT_SEEDS, sim_runs_dir: Path = SIMRUNS_DIR,
) -> tuple[list[dict], list[float]]:
    """Run every available seed file's raw damage/missile streams through
    extract_card (the SAME function the tape went through) and return the
    resulting sim cards plus each seed's own (raw, sim-native) duration_s.
    """
    composition = _composition_for_fight(fight)
    run_dir = sim_runs_dir / fight["run_id"]
    cards, durations = [], []
    for seed in seeds:
        p = run_dir / f"seed-{seed}.json"
        if not p.exists():
            continue
        raw = json.loads(p.read_text(encoding="utf-8"))
        cards.append(extract_card(raw["damage"], raw["missiles"], composition))
        durations.append(raw.get("duration_s"))
    if not cards:
        raise FileNotFoundError(f"no sim run files found under {run_dir}")
    return cards, durations


def score_fight(run_id: str, *, seeds: list[int] = DEFAULT_SEEDS, sim_runs_dir: Path = SIMRUNS_DIR) -> dict:
    fight = _load_manifest_fight(run_id)
    tape_card = json.loads((TRUTH_DIR / f"{run_id}.json").read_text(encoding="utf-8"))
    sim_cards, sim_durations = _load_sim_cards(fight, seeds, sim_runs_dir)
    return score_card(tape_card, sim_cards, sim_durations)


def score_all(
    *, seeds: list[int] = DEFAULT_SEEDS, sim_runs_dir: Path = SIMRUNS_DIR,
) -> tuple[list[dict], list[dict]]:
    """Score every fight in the manifest. Per-fight isolation (matching
    ingest.py's own convention): one fight's failure is recorded and
    skipped, never aborts the whole batch.
    """
    results, failures = [], []
    for fight in _load_manifest()["fights"]:
        run_id = fight["run_id"]
        try:
            results.append(score_fight(run_id, seeds=seeds, sim_runs_dir=sim_runs_dir))
        except Exception as exc:  # noqa: BLE001 - deliberately broad, isolated per fight
            failures.append({"run_id": run_id, "error": str(exc)})
    return results, failures


def _winner_summary(results: list[dict]) -> dict[str, Any]:
    """Roll the per-fight winner block up into the run's headline KPI.

    `n_comparable` excludes fights where either side of the comparison had
    no winner at all (a tie) — those are listed separately under
    `undecidable` rather than being counted as agreements or flips.
    """
    comparable = [r for r in results if r.get("winner", {}).get("winner_match") is not None]
    flipped = [r for r in comparable if r["winner"]["winner_match"] is False]
    undecidable = [
        r["run_id"] for r in results if r.get("winner", {}).get("winner_match") is None
    ]
    agreements = [
        r["winner"]["winner_agreement"] for r in results
        if r.get("winner", {}).get("winner_agreement") is not None
    ]
    return {
        "n_comparable": len(comparable),
        "n_winner_match": len(comparable) - len(flipped),
        "n_winner_flipped": len(flipped),
        "winner_match_rate": round((len(comparable) - len(flipped)) / len(comparable), 4) if comparable else None,
        "mean_seed_agreement": round(statistics.mean(agreements), 4) if agreements else None,
        "flipped": [
            {
                "run_id": r["run_id"],
                "matchup": r.get("matchup"),
                "tape_winner": r["winner"]["tape_winner"],
                "sim_median_winner": r["winner"]["sim_median_winner"],
                "winner_agreement": r["winner"]["winner_agreement"],
            }
            for r in flipped
        ],
        "undecidable": undecidable,
    }


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="Score every fight in the manifest.")
    ap.add_argument("--run-id", action="append", dest="run_ids", help="Score a single run_id (repeatable).")
    ap.add_argument("--label", default="baseline", help="Label embedded in the output filename.")
    ap.add_argument("--seeds", type=int, default=20, help="Number of seeds to read (1..N).")
    ap.add_argument(
        "--sim-runs-dir", type=Path, default=SIMRUNS_DIR,
        help=(
            "Directory holding <run_id>/seed-<n>.json sim runs "
            f"(default: {SIMRUNS_DIR}). Point this at an experiment's "
            "--out-dir to score that run without clobbering the default."
        ),
    )
    args = ap.parse_args()

    if not args.all and not args.run_ids:
        ap.error("nothing to do: pass --all or one or more --run-id")

    seeds = list(range(1, args.seeds + 1))

    if args.all:
        results, failures = score_all(seeds=seeds, sim_runs_dir=args.sim_runs_dir)
    else:
        results, failures = [], []
        for run_id in args.run_ids:
            try:
                results.append(score_fight(run_id, seeds=seeds, sim_runs_dir=args.sim_runs_dir))
            except Exception as exc:  # noqa: BLE001
                failures.append({"run_id": run_id, "error": str(exc)})

    verdict_counts = Counter(r["verdict"] for r in results)

    mismatch_ranking: Counter[str] = Counter()
    for r in results:
        for m in r["metrics"]:
            if m.get("gated") and m["verdict"] == "MISMATCH":
                mismatch_ranking[m["name"]] += 1

    winner_summary = _winner_summary(results)

    stamp = _stamp()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RUNS_DIR / f"{stamp}-{args.label}.json"
    payload = {
        "label": args.label,
        "generated_utc": stamp,
        "sim_runs_dir": str(args.sim_runs_dir),
        "n_fights": len(results),
        "n_failures": len(failures),
        "verdict_counts": dict(verdict_counts),
        "winner_summary": winner_summary,
        "mismatch_ranking": mismatch_ranking.most_common(),
        "failures": failures,
        "fights": results,
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"scored {len(results)} fights ({len(failures)} load/score failures)")
    print(f"verdicts: {dict(verdict_counts)}")
    print(
        f"winner agreement: {winner_summary['n_winner_match']}/{winner_summary['n_comparable']} "
        f"fights pick the same winner as the tape "
        f"(mean per-seed agreement {winner_summary['mean_seed_agreement']})"
    )
    if winner_summary["flipped"]:
        print(f"flipped fights ({len(winner_summary['flipped'])}) — sim picks the OTHER side:")
        for f in winner_summary["flipped"]:
            print(
                f"  {f['run_id']:44s} tape={f['tape_winner']} sim={f['sim_median_winner']} "
                f"seed_agreement={f['winner_agreement']}"
            )
    if winner_summary["undecidable"]:
        print(
            f"winner undecidable (tie on one side) for {len(winner_summary['undecidable'])}: "
            + ", ".join(winner_summary["undecidable"])
        )
    if mismatch_ranking:
        print("top mismatched gated metrics (fight count):")
        for name, cnt in mismatch_ranking.most_common(15):
            print(f"  {name:28s} {cnt}")
    if failures:
        print("failures:")
        for f in failures:
            print(f"  {f['run_id']}: {f['error']}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
