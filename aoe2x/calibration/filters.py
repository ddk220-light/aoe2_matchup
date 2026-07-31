"""Corpus subset filters shared by the scorer and the melee HP report.

An experiment that only touches melee has no business waiting on (or being
scored against) the 124 fights it cannot affect. Both the JS sim runner
(``tools/simjs/calib_runner.mjs``) and the Python scorer
(``python -m aoe2x.calibration.score``) therefore accept the SAME three
filters, and this module is the Python half of that pair:

- ``--tags a,b,c``   -- exact match on a fight's ``tag``
- ``--match <re>``   -- ``re.search`` against a fight's ``run_id``
- ``--melee-only``   -- both sides' slugs in the ``melee`` set
- ``--ranged-only``  -- both sides' slugs in the ``ranged`` set

The named sets live in ``data/calibration/fight_sets.json``, which the JS
runner reads too, so the two languages cannot drift. They are defined by unit
SLUG, never by a frozen list of fight tags -- membership is recomputed from
each manifest fight's own ``side1``/``side2``, so a new recording of a melee
matchup joins the set the moment it is ingested.

Filters COMBINE with AND. Passing none selects everything.

``describe_filter`` returns the short human label every subset scoreboard is
stamped with, so a 31-fight board can never be mistaken for a 155-fight one.
"""
from __future__ import annotations

import argparse
import json
import re
from functools import lru_cache
from typing import Any, Iterable, Sequence

from aoe2x.paths import REPO_ROOT

FIGHT_SETS_PATH = REPO_ROOT / "data" / "calibration" / "fight_sets.json"


@lru_cache(maxsize=1)
def _fight_sets() -> dict[str, frozenset[str]]:
    raw = json.loads(FIGHT_SETS_PATH.read_text(encoding="utf-8"))
    return {k: frozenset(v) for k, v in raw.items() if not k.startswith("_")}


def slug_set(name: str) -> frozenset[str]:
    """One named slug set out of ``data/calibration/fight_sets.json``."""
    sets = _fight_sets()
    try:
        return sets[name]
    except KeyError:
        raise KeyError(
            f"no fight set {name!r} in {FIGHT_SETS_PATH} "
            f"(have: {', '.join(sorted(sets))})"
        ) from None


#: Both-sides-melee slug set -- the Round-4 pure-melee gate's definition.
MELEE_SLUGS = slug_set("melee")
#: The five vanilla trash/knight-line units; a subset of ``MELEE_SLUGS``.
BASIC_MELEE_SLUGS = slug_set("basic_melee")
#: Both-sides-ranged slug set -- the Round-5 ranged-vs-ranged gate's definition.
RANGED_SLUGS = slug_set("ranged")


def both_sides_in(fight: dict[str, Any], slugs: Iterable[str]) -> bool:
    """True when BOTH of a manifest fight's armies are in ``slugs``."""
    want = set(slugs)
    return fight["side1"]["slug"] in want and fight["side2"]["slug"] in want


def filter_fights(
    fights: Sequence[dict[str, Any]],
    *,
    tags: Sequence[str] | None = None,
    match: str | None = None,
    melee_only: bool = False,
    ranged_only: bool = False,
) -> list[dict[str, Any]]:
    """Apply the shared subset filters (AND-combined) in manifest order.

    Mirrors ``filterFights`` in ``tools/simjs/calib_runner.mjs`` exactly --
    same three filters, same AND, same order-preserving output -- so
    ``calib_runner --melee-only`` and ``score --melee-only`` always agree on
    which fights they are talking about.
    """
    out = list(fights)
    if tags:
        wanted = set(tags)
        unknown = wanted - {f["tag"] for f in fights}
        if unknown:
            # Loud, not silent: a typo'd tag would otherwise just shrink the
            # board and look like a legitimately small subset.
            raise KeyError(f"--tags: no manifest fight with tag(s): {', '.join(sorted(unknown))}")
        out = [f for f in out if f["tag"] in wanted]
    if match:
        rx = re.compile(match)
        out = [f for f in out if rx.search(f["run_id"])]
    if melee_only:
        out = [f for f in out if both_sides_in(f, MELEE_SLUGS)]
    if ranged_only:
        out = [f for f in out if both_sides_in(f, RANGED_SLUGS)]
    return out


def describe_filter(
    *,
    tags: Sequence[str] | None = None,
    match: str | None = None,
    melee_only: bool = False,
    ranged_only: bool = False,
) -> str | None:
    """Short label for a subset run, or None when nothing was filtered."""
    parts: list[str] = []
    if melee_only:
        parts.append("melee-only")
    if ranged_only:
        parts.append("ranged-only")
    if tags:
        parts.append("tags=" + ",".join(tags))
    if match:
        parts.append(f"match={match}")
    return "+".join(parts) if parts else None


def add_filter_args(ap: argparse.ArgumentParser) -> None:
    """Register the three shared filter flags on an ArgumentParser."""
    g = ap.add_argument_group("corpus subset filters (AND-combined)")
    g.add_argument(
        "--tags", default=None,
        help="Comma-separated manifest tags to keep (exact match).",
    )
    g.add_argument(
        "--match", default=None,
        help="Regex kept if it re.search()es a fight's run_id.",
    )
    g.add_argument(
        "--melee-only", action="store_true",
        help=(
            "Keep only fights where BOTH sides' slugs are in the 'melee' set "
            f"of {FIGHT_SETS_PATH.name} ({', '.join(sorted(MELEE_SLUGS))})."
        ),
    )
    g.add_argument(
        "--ranged-only", action="store_true",
        help=(
            "Keep only fights where BOTH sides' slugs are in the 'ranged' set "
            f"of {FIGHT_SETS_PATH.name} ({', '.join(sorted(RANGED_SLUGS))})."
        ),
    )


def filter_kwargs_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Turn parsed ``add_filter_args`` flags into ``filter_fights`` kwargs."""
    return {
        "tags": [t for t in args.tags.split(",") if t] if args.tags else None,
        "match": args.match,
        "melee_only": bool(args.melee_only),
        "ranged_only": bool(getattr(args, "ranged_only", False)),
    }
