"""Extract every calibration tape's FIRST-FRAME unit positions -> data/calibration/spawns.json.

Why this exists
---------------
Through E11 the calibration scenario placed the two armies as single-file
COLUMNS on opposite ends of a 30x20-tile field -- 28 tiles apart.  The
recordings it is scored against do nothing of the kind: both armies are 2-D
BLOCKS about 5 tiles apart inside a walled ~13.6-tile box.  Every constant
fitted against the column scenario was therefore fitted against the wrong
initial condition (E11's radius work made this impossible to ignore: with true
collision radii the engine's chasers converge into a single ball and envelop a
ranged side the tapes show holding a 2.1-tile standoff).

This tool removes the guesswork.  For each of the 155 tapes it takes the FIRST
observed position of every unit and writes them out verbatim, in tile
coordinates, keyed by the recording's own owner number::

    { "<tag>": { "2": [[x, y], ...], "3": [[x, y], ...] } }

`tools/simjs/calib_runner.mjs` feeds those straight into the engine's spawner
("tapebox" mode), so a scored fight starts exactly where the recording started.

Discipline
----------
* Positions are copied, never synthesised: no jitter, no rounding, no
  re-centring.  The engine does the tile -> pixel mapping (one shared constant,
  TILE_SIZE), so this file stays a pure transcription of the tape.
* Counts are checked against `data/calibration/manifest.json` -- against
  `side1`/`side2`'s own `owner` field, NOT against side ORDER, because the
  side labels do not follow the tag's word order (a tag reading
  ``a__vs__b`` may well have `side1` = b).  A tag whose per-owner count
  disagrees with the manifest is reported and SKIPPED rather than written,
  so a bad row can never silently become a scored spawn.
* A unit's first frame is its first appearance in the stream, which is time
  ordered.  Deaths, later spawns and respawns are irrelevant here and are
  never read: the scan stops as soon as it has seen every id the manifest
  expects (with a `--settle` grace window in case a tape's first sample is
  short).
* Within an owner, units are emitted in ascending id order -- deterministic,
  and (since every unit on a side is identical) the order only ever decides
  which body stands where.

Usage::

    python tools/simjs/dump_calib_spawns.py           # write spawns.json
    python tools/simjs/dump_calib_spawns.py --check    # validate only, no write
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TAPES_DIR = Path("D:/AI/aoe2_golden/tapes")
MANIFEST_PATH = ROOT / "data" / "calibration" / "manifest.json"
OUT_PATH = ROOT / "data" / "calibration" / "spawns.json"

# How much tape time past the first sample we are willing to keep scanning for
# a unit the manifest says exists but the first frame did not carry. One second
# is far longer than any observed gap (every tape in the corpus delivers its
# whole roster in the first sample) and still far shorter than any real
# reinforcement would be.
SETTLE_S = 1.0


def first_frame_positions(tape_path: Path, expected: dict[int, int], settle_s: float = SETTLE_S):
    """First observed (x, y) per unit id, grouped by owner.

    `expected` maps owner -> unit count. Scanning stops as soon as every
    expected unit has been seen (or `settle_s` of tape time has elapsed),
    so this never reads more than the opening moment of a recording.
    """
    seen: dict[int, tuple[int, float, float]] = {}
    t0 = None
    with gzip.open(tape_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            t = row["t"]
            if t0 is None:
                t0 = t
            uid = row["id"]
            if uid not in seen:
                seen[uid] = (row["owner"], row["x"], row["y"])
            n_owner: dict[int, int] = defaultdict(int)
            for owner, _x, _y in seen.values():
                n_owner[owner] += 1
            if all(n_owner.get(o, 0) >= c for o, c in expected.items()):
                break
            if t - t0 > settle_s:
                break

    by_owner: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    for uid, (owner, x, y) in seen.items():
        by_owner[owner].append((uid, x, y))
    return {owner: sorted(rows) for owner, rows in by_owner.items()}


def build(manifest_path: Path = MANIFEST_PATH, tapes_dir: Path = TAPES_DIR):
    fights = json.loads(manifest_path.read_text(encoding="utf-8"))["fights"]
    spawns: dict[str, dict[str, list[list[float]]]] = {}
    problems: list[str] = []
    bounds = [float("inf"), float("inf"), float("-inf"), float("-inf")]

    for fight in fights:
        tag = fight["tag"]
        expected = {
            int(fight["side1"]["owner"]): int(fight["side1"]["count"]),
            int(fight["side2"]["owner"]): int(fight["side2"]["count"]),
        }
        tape = tapes_dir / tag / f"{tag}.units.jsonl.gz"
        if not tape.exists():
            problems.append(f"{tag}: no tape at {tape}")
            continue

        by_owner = first_frame_positions(tape, expected)
        got = {o: len(rows) for o, rows in by_owner.items()}
        if got != expected:
            problems.append(f"{tag}: first-frame counts {got} != manifest {expected}")
            continue

        entry: dict[str, list[list[float]]] = {}
        for owner in sorted(expected):
            pts = [[x, y] for _uid, x, y in by_owner[owner]]
            entry[str(owner)] = pts
            for x, y in pts:
                bounds[0] = min(bounds[0], x)
                bounds[1] = min(bounds[1], y)
                bounds[2] = max(bounds[2], x)
                bounds[3] = max(bounds[3], y)
        spawns[tag] = entry

    return spawns, problems, bounds


def _stats(spawns: dict[str, dict[str, list[list[float]]]]) -> None:
    """Print the geometry the tapebox scenario is built to reproduce."""
    seps, nearest = [], []
    for tag, sides in spawns.items():
        keys = sorted(sides)
        if len(keys) != 2:
            continue
        cs = []
        for k in keys:
            pts = sides[k]
            cs.append((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)))
        seps.append(((cs[0][0] - cs[1][0]) ** 2 + (cs[0][1] - cs[1][1]) ** 2) ** 0.5)
        best = min(
            ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            for a in sides[keys[0]]
            for b in sides[keys[1]]
        )
        nearest.append(best)
    if seps:
        seps.sort()
        nearest.sort()
        mid = len(seps) // 2
        print(
            f"centroid separation (tiles): min {seps[0]:.2f} median {seps[mid]:.2f} "
            f"max {seps[-1]:.2f}"
        )
        print(
            f"nearest cross-army pair (tiles): min {nearest[0]:.2f} "
            f"median {nearest[len(nearest) // 2]:.2f} max {nearest[-1]:.2f}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="validate only; write nothing")
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args()

    spawns, problems, bounds = build()
    print(f"extracted spawns for {len(spawns)} tapes")
    print(
        f"first-frame tile bounds: x [{bounds[0]}, {bounds[2]}]  y [{bounds[1]}, {bounds[3]}]"
    )
    _stats(spawns)
    if problems:
        print(f"{len(problems)} problem tag(s) -- NOT written:")
        for p in problems:
            print(f"  {p}")

    if args.check:
        return
    args.out.write_text(json.dumps(spawns, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
