"""The shared truth-card extractor.

``extract_card`` is the single function that turns a stream of combat events
(damage events + missile/projectile events) into a comparable "truth card" of
per-side metrics. **The same function is called on the JS engine's own
emitted events later (Task 3/4)** — so it must consume events by shape alone
and assume nothing about where they came from: no file paths, no tape-only
fields, no special-casing. If tape and sim were ever measured by different
code, every calibration number downstream would be meaningless.

Event shapes (duck-typed, not enforced by a schema — both the tape decoder
and the future sim recorder must produce dicts with at least these keys):

- damage event: ``{t, attacker, victim, damage, victim_hp_after, kill,
  attacker_owner, victim_owner}``. ``attacker``/``victim`` are per-fight
  unique unit-instance ids (NOT owner numbers); ``attacker_owner``/
  ``victim_owner`` are the owner numbers (e.g. 2/3) that key ``composition``.
- missile event: ``{t, id, owner, fired_from, ...}``. ``id`` is a per-
  projectile identity; a real tape's missile stream is a ~60 Hz position
  tracker so the SAME id appears on many rows (one per tick) — the metric
  that matters (``projectiles_fired``) counts **distinct ids**, never raw
  rows. Extra fields (x, y, master, ...) are ignored.
- composition: ``{"side<owner>": {"unit_name": str, "count": int, ...}}``,
  keyed by the real in-game owner number (NOT a structural "side1"/"side2"
  slot — see ``aoe2x/calibration/ingest.py``'s module docstring on this
  distinction). Optional per-side ``"max_hp"`` improves ``hp_remaining``
  accuracy for units that were never hit (see ``_side_card`` docstring);
  everything else (``civ``, ``slug``) is copied through verbatim if present.

Verified metric definitions (validated against the recording's own published
GROUND_TRUTH.md — 7 of 8 values reproduce exactly; the Elite Battle
Elephant's swing_interval_median is a deliberate exception, see
``_swing_interval_stats``):

- **Swing grouping**: group a side's damage events by ``attacker`` (the
  individual unit instance, not owner); consecutive events from the same
  attacker within ``SWING_EPS`` seconds of each other are ONE swing. This is
  what lets a single trampling attack that damages several victims still
  count as one swing.
- **swing_interval_median**: for each attacking unit, take the median gap
  between its own consecutive swings; then take the median of THOSE
  per-unit medians across all of the side's units.
- **swing_interval_fastest**: the minimum gap over ALL units' gaps pooled
  together — NOT the minimum of the per-unit medians.
- **churn**: swing_interval_median - swing_interval_fastest.
- **projectiles_fired**: count of DISTINCT missile ``id`` values for that
  owner (raw row counts in a ~60 Hz position-tracker stream are roughly
  18x too high).
- **effective_accuracy**: hits_landed / projectiles_fired (only meaningful
  for a side that actually fired projectiles).
- **Trample stats**: within the swing groups above, a swing with more than
  one distinct victim is a "multi-hit" swing. ``splash_fraction`` is the
  modal (most common) non-maximal per-hit damage value divided by the modal
  maximal per-hit damage value, computed only over multi-hit swings.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from aoe2x.paths import GOLDEN_DIR, REPO_ROOT

# Consecutive damage events from the SAME attacker within this many seconds
# are one swing. Raised 0.15 -> 0.60 (2026-07-30) because 0.15 was a defect
# in our own rig, not a property of the game: a slow projectile (siege
# onager, heavy scorpion, elite fire lancer) delivers one shot's multi-victim
# damage spread over well more than 0.15s of flight time, so the old value
# shredded ONE shot into several "swings" and manufactured churn that the
# engine was then blamed for. Measured counterfactual over the 105-fight
# corpus: gated MISMATCH 756 -> 726, with all 11 other units' cards
# bit-identical. The Elite Battle Elephant's real trample is unaffected --
# all 402 of its multi-victim swings span <= 0.15s. Applied to tape and sim
# alike (one extractor, one constant) -- see docs/architecture/
# calibration-gap-analysis.md §3.3.
SWING_EPS = 0.60

CALIBRATION_DIR = REPO_ROOT / "data" / "calibration"
MANIFEST_PATH = CALIBRATION_DIR / "manifest.json"
TRUTH_DIR = CALIBRATION_DIR / "truth"

TAPES_DIR = Path("D:/AI/aoe2_golden/tapes")
REFERENCE_DB_PATH = GOLDEN_DIR / "aoe2_reference.db"

_SIDE_KEY_RE = re.compile(r"^side(\d+)$")


def _owner_from_side_key(key: str) -> int:
    m = _SIDE_KEY_RE.match(key)
    if not m:
        raise ValueError(f"extract_card: unexpected composition key (expected 'sideN'): {key!r}")
    return int(m.group(1))


def _fmt_damage_key(value: float) -> str:
    """'8.0' -> '8', '4.5' -> '4.5' — matches the card shape's histogram keys."""
    return f"{value:g}"


# --------------------------------------------------------------------------
# Swing grouping (the one grouping rule everything else is built on)
# --------------------------------------------------------------------------


def _group_swings_by_attacker(rows: list[dict[str, Any]]) -> dict[Any, list[list[dict[str, Any]]]]:
    """Group `rows` (already filtered to one owner's outgoing attacks) into
    per-attacker lists of swings, where a swing is a list of consecutive
    (by time) damage events from the same attacker no more than SWING_EPS
    apart. Returns {attacker_id: [[event, event, ...], [event, ...], ...]}
    with each inner list's events already time-sorted, and swings within an
    attacker's list also in time order.
    """
    by_attacker: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_attacker[r["attacker"]].append(r)

    result: dict[Any, list[list[dict[str, Any]]]] = {}
    for attacker, events in by_attacker.items():
        events = sorted(events, key=lambda r: r["t"])
        swings: list[list[dict[str, Any]]] = []
        last_t: float | None = None
        for e in events:
            if last_t is None or (e["t"] - last_t) > SWING_EPS:
                swings.append([])
            swings[-1].append(e)
            last_t = e["t"]
        result[attacker] = swings
    return result


def _swing_interval_stats(swings_by_attacker: dict[Any, list[list[dict[str, Any]]]]) -> dict[str, Any]:
    """swing_interval_median (median of per-unit medians), swing_interval_fastest
    (min over ALL pooled gaps — deliberately NOT the min of per-unit medians,
    verified against the recording's own published numbers), churn, and the
    raw gap count that fed them (for n_events diagnostics).
    """
    per_unit_medians: list[float] = []
    all_gaps: list[float] = []
    for swings in swings_by_attacker.values():
        # One representative timestamp per swing: its first event's time.
        swing_times = [swings_group[0]["t"] for swings_group in swings]
        if len(swing_times) < 2:
            continue
        gaps = [swing_times[i + 1] - swing_times[i] for i in range(len(swing_times) - 1)]
        all_gaps.extend(gaps)
        per_unit_medians.append(statistics.median(gaps))

    if not all_gaps:
        return {"median": None, "fastest": None, "churn": None, "n_gaps": 0}

    median = statistics.median(per_unit_medians)
    fastest = min(all_gaps)
    return {
        "median": round(median, 3),
        "fastest": round(fastest, 3),
        "churn": round(median - fastest, 3),
        "n_gaps": len(all_gaps),
    }


def _trample_stats(swings_by_attacker: dict[Any, list[list[dict[str, Any]]]]) -> dict[str, Any]:
    """Multi-victim ("trample") swing stats plus splash_fraction, computed
    only over swings with more than one distinct victim.
    """
    all_swings: list[list[dict[str, Any]]] = [
        swing for swings in swings_by_attacker.values() for swing in swings
    ]
    total = len(all_swings)
    multi = [s for s in all_swings if len({e["victim"] for e in s}) > 1]

    if total == 0:
        multi_rate = 0.0
    else:
        multi_rate = len(multi) / total

    if not multi:
        return {
            "trample_multi_rate": multi_rate,
            "trample_victims_mean": 0.0,
            "trample_victims_max": 0,
            "splash_fraction": None,
        }

    victim_counts = [len({e["victim"] for e in s}) for s in multi]
    max_vals: list[float] = []
    nonmax_vals: list[float] = []
    for s in multi:
        dmgs = [e["damage"] for e in s]
        mx = max(dmgs)
        max_vals.append(mx)
        nonmax_vals.extend(d for d in dmgs if d != mx)

    mode_max = Counter(max_vals).most_common(1)[0][0]
    splash_fraction = None
    if nonmax_vals:
        mode_nonmax = Counter(nonmax_vals).most_common(1)[0][0]
        splash_fraction = round(mode_nonmax / mode_max, 4) if mode_max else None

    return {
        "trample_multi_rate": round(multi_rate, 4),
        "trample_victims_mean": round(sum(victim_counts) / len(victim_counts), 3),
        "trample_victims_max": max(victim_counts),
        "splash_fraction": splash_fraction,
    }


# --------------------------------------------------------------------------
# Per-side derivation (kills/survivors/hp_remaining) — damage events only,
# no unit-position stream (extract_card doesn't receive one).
# --------------------------------------------------------------------------


def _kills_by(rows: list[dict[str, Any]]) -> int:
    return sum(1 for r in rows if r.get("kill"))


def _side_outcome(
    damage_events: list[dict[str, Any]],
    owner: int,
    start_count: int,
    max_hp: float | None,
) -> dict[str, Any]:
    """survivors/hp_remaining for the side owned by `owner`.

    Deaths are counted directly from kill=True events where victim_owner ==
    owner (each unit fires its kill flag exactly once, on its terminal hit).
    hp_remaining sums the LAST recorded hp_after for every distinct victim
    id on this side that didn't die (best-effort: a unit never hit at all
    never appears as a victim, so its remaining hp is unknowable from
    damage events alone — if `max_hp` is supplied via composition, such
    untouched survivors are assumed to be at full health; otherwise they
    contribute 0, which UNDERCOUNTS hp_remaining when they exist).
    """
    victim_rows = [r for r in damage_events if r.get("victim_owner") == owner]
    deaths = sum(1 for r in victim_rows if r.get("kill"))
    survivors = max(start_count - deaths, 0)

    by_victim: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in victim_rows:
        by_victim[r["victim"]].append(r)

    hp_seen = 0.0
    n_seen_survivors = 0
    for victim_id, events in by_victim.items():
        # NOTE: multiple attackers can land hits on the same victim at the
        # exact same recorded timestamp (rounded ties are common in this
        # tape format). max(..., key=t) breaks ties by keeping the FIRST
        # equal-max item, which can silently pick a non-killing tied event
        # over the true final (killing) one. A stable sort + take-the-last
        # element preserves original event order on ties, giving the
        # correct chronologically-last event.
        last = sorted(events, key=lambda r: r["t"])[-1]
        if not last.get("kill"):
            hp_seen += last.get("victim_hp_after", 0.0) or 0.0
            n_seen_survivors += 1

    n_unseen_survivors = max(survivors - n_seen_survivors, 0)
    if max_hp is not None:
        hp_remaining = hp_seen + n_unseen_survivors * max_hp
    else:
        hp_remaining = hp_seen

    return {"survivors": survivors, "hp_remaining": round(hp_remaining, 3)}


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def _side_card(
    damage_events: list[dict[str, Any]],
    missile_events: list[dict[str, Any]],
    owner: int,
    side_meta: dict[str, Any],
) -> dict[str, Any]:
    outgoing = [r for r in damage_events if r.get("attacker_owner") == owner]
    start_count = side_meta.get("count", 0)

    swings_by_attacker = _group_swings_by_attacker(outgoing)
    landed_swing_count = sum(len(v) for v in swings_by_attacker.values())
    interval = _swing_interval_stats(swings_by_attacker)
    trample = _trample_stats(swings_by_attacker)

    projectiles_fired = len({m["id"] for m in missile_events if m.get("owner") == owner})
    # swing_count is the side's total attack-attempt count (hit or miss). A
    # ranged side's misses never produce a damage event, so grouping damage
    # events alone would UNDERCOUNT attempts — projectiles_fired (every shot
    # fired, landed or not) is the true attempt count when the side fired
    # any projectiles. A melee side has no missile stream at all, so its
    # only available attempt signal is the SWING_EPS-grouped damage-event
    # count (misses are invisible for melee; this is what
    # test_trample_multi_victim_detection exercises directly).
    swing_count = projectiles_fired if projectiles_fired else landed_swing_count
    hits_landed = len(outgoing)
    damage_dealt = sum(r.get("damage", 0.0) for r in outgoing)
    kills = _kills_by(outgoing)

    effective_accuracy = round(hits_landed / projectiles_fired, 4) if projectiles_fired else None

    damage_histogram: dict[str, int] = {}
    for value, count in Counter(r["damage"] for r in outgoing).most_common():
        damage_histogram[_fmt_damage_key(value)] = count

    first_blood = round(min(r["t"] for r in outgoing), 3) if outgoing else None

    outcome = _side_outcome(damage_events, owner, start_count, side_meta.get("max_hp"))

    card: dict[str, Any] = {
        "unit_name": side_meta.get("unit_name"),
        "civ": side_meta.get("civ"),
        "slug": side_meta.get("slug"),
        "start_count": start_count,
        "survivors": outcome["survivors"],
        "hp_remaining": outcome["hp_remaining"],
        "hits_landed": hits_landed,
        "damage_dealt": damage_dealt,
        "kills": kills,
        "swing_interval_median": interval["median"],
        "swing_interval_fastest": interval["fastest"],
        "churn": interval["churn"],
        "swing_count": swing_count,
        "projectiles_fired": projectiles_fired,
        "effective_accuracy": effective_accuracy,
        "damage_histogram": damage_histogram,
        "trample_multi_rate": trample["trample_multi_rate"],
        "trample_victims_mean": trample["trample_victims_mean"],
        "trample_victims_max": trample["trample_victims_max"],
        "splash_fraction": trample["splash_fraction"],
        "first_blood": first_blood,
        "n_events": {
            "swings": swing_count,
            "gaps": interval["n_gaps"],
            "projectiles": projectiles_fired,
        },
    }
    return card


def extract_card(
    damage_events: list[dict[str, Any]],
    missile_events: list[dict[str, Any]],
    composition: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Turn a stream of combat events into a truth card of per-side metrics.

    Consumes events BY SHAPE ALONE (see module docstring for the expected
    dict keys) — this function is called on both real-tape events and the
    JS engine's own emitted events, so it must never import or assume
    anything tape-specific (no file paths, no tape-only fields).

    `composition` is keyed by the real in-game owner number as
    ``"side<owner>"`` (e.g. ``"side2"``, ``"side3"``) — NOT a structural
    "first side / second side" slot. Returns ``{"sides": {"side2": {...},
    "side3": {...}}}``; callers that also want top-level ``tag``/``run_id``/
    ``matchup``/``duration_s`` (the full card shape from the brief) add
    those themselves, since this function has no notion of a run identity or
    an authoritative fight duration — see ``build_truth_card`` below.
    """
    sides: dict[str, Any] = {}
    for side_key, side_meta in composition.items():
        owner = _owner_from_side_key(side_key)
        sides[side_key] = _side_card(damage_events, missile_events, owner, side_meta)
    return {"sides": sides}


# --------------------------------------------------------------------------
# CLI: read the manifest + tape streams, write data/calibration/truth/<run_id>.json
# --------------------------------------------------------------------------


def _read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _fetch_max_hp(civ: str | None, slug: str | None) -> float | None:
    if not civ or not slug or not REFERENCE_DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(REFERENCE_DB_PATH))
    try:
        cur = conn.execute(
            "SELECT final_hp FROM ref_units WHERE civ_name = ? AND unit_slug = ? AND age = 'Imperial'",
            (civ, slug),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _composition_for_fight(fight: dict[str, Any]) -> dict[str, dict[str, Any]]:
    composition: dict[str, dict[str, Any]] = {}
    for side in (fight["side1"], fight["side2"]):
        owner = side["owner"]
        composition[f"side{owner}"] = {
            "unit_name": side.get("unit_name"),
            "civ": side.get("civ"),
            "slug": side.get("slug"),
            "count": side.get("count"),
            "max_hp": _fetch_max_hp(side.get("civ"), side.get("slug")),
        }
    return composition


def build_truth_card(fight: dict[str, Any]) -> dict[str, Any]:
    """Build the full on-disk card shape (tag/run_id/matchup/duration_s +
    extract_card's per-side "sides") for one manifest fight entry, reading
    its tape streams from D:/AI/aoe2_golden/tapes/<run_id>/.
    """
    run_id = fight["run_id"]
    run_dir = TAPES_DIR / run_id
    damage_path = run_dir / f"{run_id}.damage.jsonl.gz"
    missiles_path = run_dir / f"{run_id}.missiles.jsonl.gz"

    if not damage_path.exists():
        # NEVER substitute [] here. A missing damage stream produces a
        # perfectly plausible-looking all-zero card (0 hits, 0 swings, empty
        # histogram, everyone survives at full hp) that silently poisons
        # every scoreboard downstream. This exact silent failure shipped
        # once, for hand_cannoneer__vs__elite_elephant_r2, whose tape files
        # had been staged under the raw recorded tag instead of the
        # reassigned run_id (fixed in ingest._process_fight).
        staged = sorted(p.name for p in run_dir.glob("*")) if run_dir.exists() else []
        raise FileNotFoundError(
            f"build_truth_card({run_id!r}): no damage tape at {damage_path} — "
            f"refusing to emit an all-zero card. Files present in {run_dir}: "
            f"{staged or '<dir does not exist>'}"
        )

    damage_events = _read_jsonl_gz(damage_path)
    # The missile stream is legitimately absent for an all-melee fight, so
    # (unlike damage) an empty substitution here is correct, not a silent
    # data loss: extract_card reads it only for projectiles_fired.
    missile_events = _read_jsonl_gz(missiles_path) if missiles_path.exists() else []
    composition = _composition_for_fight(fight)

    card = extract_card(damage_events, missile_events, composition)
    return {
        "tag": run_id,
        "run_id": run_id,
        "matchup": fight.get("matchup", run_id),
        "duration_s": fight.get("duration_s"),
        **card,
    }


def write_truth_cards(run_ids: list[str] | None = None) -> list[str]:
    """Build and write truth cards for the given run_ids (or every fight in
    the manifest if None) to data/calibration/truth/<run_id>.json. Returns
    the list of run_ids written.
    """
    manifest = _load_manifest()
    fights = manifest["fights"]
    if run_ids is not None:
        wanted = set(run_ids)
        fights = [f for f in fights if f["run_id"] in wanted]

    TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for fight in fights:
        card = build_truth_card(fight)
        out_path = TRUTH_DIR / f"{fight['run_id']}.json"
        out_path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        written.append(fight["run_id"])
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Extract truth cards for every fight in the manifest.")
    parser.add_argument("--run-id", action="append", dest="run_ids", help="Extract a single run_id (repeatable).")
    args = parser.parse_args()

    if not args.all and not args.run_ids:
        parser.error("nothing to do: pass --all or one or more --run-id")

    run_ids = None if args.all else args.run_ids
    written = write_truth_cards(run_ids)
    print(f"Wrote {len(written)} truth card(s) to {TRUTH_DIR}")


if __name__ == "__main__":
    main()
