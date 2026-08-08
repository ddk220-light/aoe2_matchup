"""Derive the per-kiter script cycle from the tapes and emit src/kite-profiles.js.

Every kiting truth fixture records the scenario's `kiteOwner` and, where the
cycle differs from the engine default, an explicit `kiteProfile`. The kiting
unit itself is named by `sides[kiteOwner]`, which is the mechanics fixture the
unit registry already keys on -- so the profiles can be re-keyed from the
scenario onto the KITER, which is what a free-selection fight needs.

Fixtures that carry `kiteOwner` but no `kiteProfile` ran on the engine default
(ai-orders.js DEFAULT_KITE_PROFILE, the arbalester cycle). They are recorded in
the provenance as `defaultedFixtures` and are NOT used to derive a value; every
kiter that appears only in such fixtures would be indistinguishable from the
default, and the script fails loudly if that ever happens for a slug that has no
explicit column at all.

    python aoe2x/js_simulation/tools/derive_kite_profiles.py
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "calibration" / "fixtures"
REGISTRY = ROOT / "src" / "unit-registry.js"
UNIT_STATS = ROOT / "fixtures" / "unit_stats"
OUTPUT = ROOT / "src" / "kite-profiles.js"

TICKS_PER_SECOND = 60

# The order clock every recorded kiting archive runs on: 0.667 s between
# consecutive script commands (ai-orders.js, "Every recorded archive runs the
# same 0.667 s order clock"). 40 ticks at 60 Hz.
ORDER_CLOCK_TICKS = 40

PROFILE_KEYS = (
    "beatTicks",
    "firstBeatTick",
    "moveOffsetTicks",
    "topupOffsetTicks",
    "preMoveTicks",
)

# Hand Cannoneer has no kiting tape column. Its beat is CONSTRUCTED, and the
# construction is recorded in the provenance rather than passed off as measured.
CONSTRUCTED_SLUGS = ("hand_cannoneer",)


def registry_rows() -> list[dict]:
    """slug / class / mechanics fixture for every registered unit.

    Parsed out of src/unit-registry.js rather than duplicated here, so this
    tool and the engine can never disagree about which slug a fixture is.
    """
    text = REGISTRY.read_text(encoding="utf8")
    rows = []
    for match in re.finditer(
        r'\{\s*slug:\s*"(?P<slug>[a-z0-9_]+)".*?'
        r'fixture:\s*"(?P<fixture>[a-z0-9_.]+)",\s*class:\s*"(?P<cls>[a-z_]+)"',
        text,
        re.S,
    ):
        rows.append({
            "slug": match["slug"],
            "fixture": match["fixture"],
            "class": match["cls"],
        })
    if not rows:
        raise SystemExit("could not parse any rows out of src/unit-registry.js")
    return rows


def normalise(profile: dict) -> dict:
    """The five profile fields, with the optional lists defaulted to empty."""
    missing = [key for key in ("beatTicks", "firstBeatTick", "moveOffsetTicks")
               if key not in profile]
    if missing:
        raise SystemExit(f"kiteProfile is missing {missing}: {profile}")
    return {
        "beatTicks": profile["beatTicks"],
        "firstBeatTick": profile["firstBeatTick"],
        "moveOffsetTicks": list(profile["moveOffsetTicks"]),
        "topupOffsetTicks": list(profile.get("topupOffsetTicks", [])),
        "preMoveTicks": list(profile.get("preMoveTicks", [])),
    }


def constructed_beat_ticks(reload_seconds: float) -> int:
    """Snap a dat reload up to the next whole order-clock step.

    This is the standard-units sweep's own rule, transcribed from
    `profile_for` in that sweep's `std_build_run_input.py`:

        slots = math.ceil(reload_s / (2 / 3) - 1e-9)
        beat = slots * 40

    Not fitted: the order clock is measured (0.667 s), the reload is dat, and
    the rule reproduces all three MEASURED beats exactly --
    arbalester 1.7 s -> 2.00 s, elite skirmisher 3.0 s -> 3.33 s,
    heavy cav archer 1.8 s -> 2.00 s. main() re-checks that on every run and
    refuses to emit if it ever stops holding.
    """
    steps = math.ceil(reload_seconds * TICKS_PER_SECOND / ORDER_CLOCK_TICKS - 1e-9)
    return steps * ORDER_CLOCK_TICKS


def constructed_offsets(beat_ticks: int) -> tuple[list[int], list[int]]:
    """Move offsets and pre-fight moves for a constructed cycle.

    Also the sweep's rule, verbatim ("fill rule moves 40+80k, preMoves 80+80k
    for others"):

        moves = [t for t in range(40, beat, 80)]
        pre   = [t for t in range(80, beat, 80)]

    It reproduces the arbalester and elite-skirmisher columns exactly. It does
    NOT reproduce the heavy cav archer, whose cycle is a different shape
    entirely (it opens firing: firstBeatTick 40, and it top-ups) -- which is
    precisely why a constructed row is marked constructed.
    """
    moves = list(range(ORDER_CLOCK_TICKS, beat_ticks, 2 * ORDER_CLOCK_TICKS))
    pre = list(range(2 * ORDER_CLOCK_TICKS, beat_ticks, 2 * ORDER_CLOCK_TICKS))
    return moves, pre


def main() -> None:
    rows = registry_rows()
    slug_by_stem = {row["fixture"].removesuffix(".json"): row["slug"] for row in rows}
    class_by_slug = {row["slug"]: row["class"] for row in rows}

    explicit: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    defaulted: dict[str, list[str]] = defaultdict(list)
    scanned = 0
    kiting = 0
    for path in sorted(FIXTURES.glob("*.json")):
        scanned += 1
        truth = json.loads(path.read_text(encoding="utf8"))
        if not isinstance(truth, dict):
            continue
        owner = truth.get("kiteOwner")
        if not isinstance(owner, int):
            continue
        kiting += 1
        stem = (truth.get("sides") or {}).get(str(owner))
        slug = slug_by_stem.get(stem)
        if slug is None:
            raise SystemExit(
                f"{path.name}: kiting side {owner} is {stem!r}, which no registry row claims")
        profile = truth.get("kiteProfile")
        if profile is None:
            defaulted[slug].append(path.name)
        else:
            explicit[slug].append((path.name, normalise(profile)))

    table: dict[str, dict] = {}
    measured_provenance: dict[str, dict] = {}
    for slug, entries in sorted(explicit.items()):
        first_name, first = entries[0]
        for name, other in entries[1:]:
            if other != first:
                raise SystemExit(
                    f"{slug}: {name} disagrees with {first_name}\n  {other}\n  {first}")
        table[slug] = first
        measured_provenance[slug] = {
            "source": "tape",
            "fixtures": sorted(name for name, _ in entries),
            "defaultedFixtures": sorted(defaulted.get(slug, [])),
        }

    print(f"fixtures scanned {scanned}  kiting {kiting}  measured kiters {len(table)}")
    for slug, profile in sorted(table.items()):
        seconds = profile["beatTicks"] / TICKS_PER_SECOND
        print(f"  {slug}: beat {profile['beatTicks']} ({seconds:.2f} s) "
              f"first {profile['firstBeatTick']} moves {profile['moveOffsetTicks']} "
              f"topups {profile['topupOffsetTicks']} pre {profile['preMoveTicks']} "
              f"<- {len(explicit[slug])} fixture(s)"
              + (f", {len(defaulted.get(slug, []))} defaulted" if defaulted.get(slug) else ""))
    for slug, names in sorted(defaulted.items()):
        if slug not in table:
            raise SystemExit(
                f"{slug} kites in {names} but no fixture records its profile; it would be "
                "indistinguishable from the engine default and cannot be derived")

    # Re-check the constructed-beat rule against every MEASURED beat before it
    # is used to construct anything.
    checks = []
    for slug, profile in sorted(table.items()):
        stats = json.loads(
            (UNIT_STATS / f"{[r for r in rows if r['slug'] == slug][0]['fixture']}")
            .read_text(encoding="utf8"))
        reload_seconds = stats["reload_seconds"]
        predicted = constructed_beat_ticks(reload_seconds)
        moves, pre = constructed_offsets(predicted)
        checks.append({
            "slug": slug,
            "reloadSeconds": reload_seconds,
            "measuredBeatTicks": profile["beatTicks"],
            "predictedBeatTicks": predicted,
            "agrees": predicted == profile["beatTicks"],
            "shapeAgrees": (
                profile["firstBeatTick"] == profile["beatTicks"]
                and profile["moveOffsetTicks"] == moves
                and profile["preMoveTicks"] == pre
                and profile["topupOffsetTicks"] == []),
        })
    print("constructed rule vs the measured columns:")
    for check in checks:
        print(f"  {check['slug']}: reload {check['reloadSeconds']} s -> "
              f"{check['predictedBeatTicks']} ticks, measured {check['measuredBeatTicks']} "
              f"(beat {'agrees' if check['agrees'] else 'DISAGREES'}, "
              f"shape {'agrees' if check['shapeAgrees'] else 'differs'})")
    if not all(check["agrees"] for check in checks):
        raise SystemExit(
            "the constructed-beat rule no longer reproduces the measured beats; "
            "do not emit a constructed row against a rule that does not hold")

    constructed_provenance: dict[str, dict] = {}
    for slug in CONSTRUCTED_SLUGS:
        if slug in table:
            continue
        if class_by_slug.get(slug) != "mobile_ranged":
            raise SystemExit(f"{slug} is not mobile_ranged; it never kites")
        fixture = [row for row in rows if row["slug"] == slug][0]["fixture"]
        stats = json.loads((UNIT_STATS / fixture).read_text(encoding="utf8"))
        reload_seconds = stats["reload_seconds"]
        beat = constructed_beat_ticks(reload_seconds)
        moves, pre = constructed_offsets(beat)
        table[slug] = {
            "beatTicks": beat,
            "firstBeatTick": beat,
            "moveOffsetTicks": moves,
            "topupOffsetTicks": [],
            "preMoveTicks": pre,
        }
        constructed_provenance[slug] = {
            "source": "constructed",
            "reason": "no kiting tape column exists for this unit",
            "reloadSeconds": reload_seconds,
            "beatRule": (
                "ceil(reload / 0.667 s order clock) * 0.667 s -- reproduces all three "
                "measured beats exactly (arbalester 1.7->2.00 s, elite skirmisher "
                "3.0->3.33 s, heavy cav archer 1.8->2.00 s)"),
            "shapeRule": (
                "firstBeatTick = beatTicks; moves at 40+80k and pre-fight moves at "
                "80+80k, both up to the beat; no top-ups. Reproduces the arbalester "
                "and elite-skirmisher columns; does NOT reproduce the heavy cav "
                "archer, whose cycle is a different shape (opens firing, top-ups)."),
            "transcribedFrom": (
                "profile_for() in the standard-units sweep's std_build_run_input.py. "
                "That sweep ran from a session scratchpad and is NOT in the repo; this "
                "tool is where the rule now lives. The values it emits for "
                "hand_cannoneer match the sweep's own std_run_input.json exactly."),
            "warning": (
                "CONSTRUCTED, NOT MEASURED. The standard-units sweep names this as the "
                "likely cause of the four large hand-cannoneer kite deltas."),
        }
        print(f"  {slug}: CONSTRUCTED beat {beat} ({beat / TICKS_PER_SECOND:.2f} s) "
              f"from reload {reload_seconds} s, moves {moves}, pre {pre}")

    kiters = sorted(slug for slug, cls in class_by_slug.items() if cls == "mobile_ranged")
    uncovered = [slug for slug in kiters if slug not in table]
    if uncovered:
        raise SystemExit(f"mobile_ranged units with no profile at all: {uncovered}")

    provenance = {
        "sourceDirectory": "aoe2x/js_simulation/calibration/fixtures",
        "registry": "aoe2x/js_simulation/src/unit-registry.js",
        "ticksPerSecond": TICKS_PER_SECOND,
        "orderClockTicks": ORDER_CLOCK_TICKS,
        "fixturesScanned": scanned,
        "kitingFixtures": kiting,
        "beatRuleChecks": checks,
        "profiles": {**measured_provenance, **constructed_provenance},
    }

    body = json.dumps(table, indent=2, sort_keys=True)
    prov = json.dumps(provenance, indent=2, sort_keys=True)
    OUTPUT.write_text(
        "// GENERATED by tools/derive_kite_profiles.py -- do not edit by hand.\n"
        "//\n"
        "// The script cycle each kiting unit runs, keyed by unit slug. Re-keyed from\n"
        "// the recorded scenarios (where the profile is a property of the tape) onto\n"
        "// the KITER, which is what a free-selection fight needs: the same arbalester\n"
        "// runs the same cycle whichever melee unit it is pointed at.\n"
        "//\n"
        "// KITE_PROFILE_PROVENANCE names the source fixture(s) behind every row and\n"
        "// flags the one row that is CONSTRUCTED rather than measured.\n"
        f"export const KITE_PROFILES = Object.freeze({body});\n"
        "\n"
        f"export const KITE_PROFILE_PROVENANCE = Object.freeze({prov});\n",
        encoding="utf8",
    )
    print(f"wrote {OUTPUT.relative_to(ROOT.parents[1])}")


if __name__ == "__main__":
    main()
