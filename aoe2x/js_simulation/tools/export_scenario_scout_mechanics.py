"""Export the post-Imperial Scout master placed for golden Player 4.

The scenario stores master 448, while its post-Imperial technology state
applies the Spanish Hussar-line upgrade statistics to that placed entity. We
therefore combine the Spanish Imperial ``hussar`` reference row (combat
statistics and exact stat chain) with master 448's structural, obstruction,
and animation fields from the local Genie DAT. This is the same two-source
join as every other JS mechanics fixture and does not consult fight outcomes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aoe2x.js_simulation.tools.export_unit_mechanics import export_unit_mechanics


def export_player4_unit(reference_db: Path, dat: Path) -> dict:
    fixture = export_unit_mechanics(reference_db, dat, "hussar", "Spanish", 448)
    fixture["provenance"]["reference_selector"] += (
        "; post-Imperial scenario upgrades apply this line result to placed master 448"
    )
    return fixture


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-db", type=Path, required=True)
    parser.add_argument("--dat", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = export_player4_unit(args.reference_db, args.dat)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
