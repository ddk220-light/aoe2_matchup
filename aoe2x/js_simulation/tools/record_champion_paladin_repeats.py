"""Record fresh Spanish Champion-vs-Paladin trials from the current melee golden.

This is a thin batch driver around the established video/gRPC automation. It
pins the exact project-local scenario and validates each generated scenario and
gRPC sidecar before advancing to the next repeat.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VIDEO_DIR = ROOT / "apps" / "video"
sys.path.insert(0, str(VIDEO_DIR))

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario  # noqa: E402
from auto import grpc_capture, vision  # noqa: E402
from auto.orchestrate_matchup import RUN_DIR, run_matchup  # noqa: E402
from build_run import _test_const, unit_const  # noqa: E402


GOLDEN = (
    ROOT
    / "aoe2x"
    / "js_simulation"
    / "calibration"
    / "live_observations"
    / "current_melee_golden_2026-08-28"
    / "source"
    / "meleevsmelee.aoe2scenario"
)
GOLDEN_SHA256 = "31f3bed38ce0512b484124d89d5aa4e97318b3ea55c398bb8dad27242c769f4e"
DEFAULT_OUTPUT = (
    ROOT
    / "aoe2x"
    / "js_simulation"
    / "calibration"
    / "live_observations"
    / "spanish_champion_vs_paladin_5x_2026-08-28"
)
STEM = "spanish_champion_vs_paladin"
EXPECTED_COUNTS = (27, 16)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def army_positions(scenario: AoE2DEScenario, player_id: int, master: int):
    return [
        (round(float(unit.x), 6), round(float(unit.y), 6))
        for unit in scenario.unit_manager.get_player_units(player_id)
        if int(unit.unit_const) == master
    ]


def validate_generated_scenario(path: Path) -> dict:
    source = AoE2DEScenario.from_file(str(GOLDEN))
    generated = AoE2DEScenario.from_file(str(path))
    champion = unit_const("champion")
    paladin = unit_const("paladin")
    source_masters = {
        player_id: _test_const(source.unit_manager.get_player_units(player_id))
        for player_id in (2, 3)
    }
    expected_positions = {
        2: army_positions(source, 2, source_masters[2])[: EXPECTED_COUNTS[0]],
        3: army_positions(source, 3, source_masters[3])[: EXPECTED_COUNTS[1]],
    }
    actual_positions = {
        2: army_positions(generated, 2, champion),
        3: army_positions(generated, 3, paladin),
    }
    if tuple(map(len, actual_positions.values())) != EXPECTED_COUNTS:
        raise RuntimeError(
            f"generated roster mismatch: expected {EXPECTED_COUNTS}, "
            f"got {tuple(map(len, actual_positions.values()))}"
        )
    if actual_positions != expected_positions:
        raise RuntimeError("generated positions do not match the golden first-N slots")
    return {
        "sha256": sha256(path),
        "counts": {"player2_champions": 27, "player3_paladins": 16},
        "position_rule": "first_n_units_in_player_order",
        "positions_match_current_melee_golden": True,
    }


def validate_capture(run_dir: Path) -> dict:
    raw = run_dir / "raw recordings"
    prefix = raw / STEM
    required = [
        prefix.with_suffix(".mov"),
        Path(f"{prefix}.frames.bin"),
        Path(f"{prefix}.meta.json"),
        Path(f"{prefix}.END"),
        Path(f"{prefix}.hp.json"),
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"capture is incomplete: missing {missing}")
    if Path(f"{prefix}.frames.bin").stat().st_size < 1_000_000:
        raise RuntimeError("gRPC frame dump is unexpectedly small")
    sidecar = json.loads(Path(f"{prefix}.hp.json").read_text(encoding="utf-8"))
    rows = sidecar.get("rows") or []
    if not rows:
        raise RuntimeError("gRPC HP sidecar has no rows")
    first, final = rows[0], rows[-1]
    start = (first["side1"]["count"], first["side2"]["count"])
    end = (final["side1"]["count"], final["side2"]["count"])
    if start != EXPECTED_COUNTS:
        raise RuntimeError(f"gRPC starting roster mismatch: expected {EXPECTED_COUNTS}, got {start}")
    if (end[0] == 0) == (end[1] == 0):
        raise RuntimeError(f"unexpected final gRPC roster: {end}")
    winner_side = "champion" if end[0] > 0 else "paladin"
    winner_index = 0 if end[0] > 0 else 1
    eliminated_key = "side2" if winner_index == 0 else "side1"
    elimination = next(row for row in rows if row[eliminated_key]["count"] == 0)
    return {
        "game_version": sidecar.get("game_version"),
        "start_counts": list(start),
        "winner": winner_side,
        "survivors": end[winner_index],
        "winner_hp": final[f"side{winner_index + 1}"]["hp"],
        "elimination_time_s": elimination["game_s"],
        "grpc_rows": len(rows),
        "frames_bytes": Path(f"{prefix}.frames.bin").stat().st_size,
        "frames_sha256": sha256(Path(f"{prefix}.frames.bin")),
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cap", type=int, default=180)
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be positive")
    if not GOLDEN.exists() or sha256(GOLDEN) != GOLDEN_SHA256:
        raise SystemExit("current melee golden is missing or its SHA-256 changed")
    if not grpc_capture.available():
        raise SystemExit("gRPC capture stack is unavailable")
    state = vision.detect_state(vision.grab())
    if state != "editor":
        raise SystemExit(f"AoE2 must be in the Scenario Editor; detected {state!r}")

    args.output.mkdir(parents=True, exist_ok=False)
    batch = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "golden": {"path": str(GOLDEN.relative_to(ROOT)), "sha256": GOLDEN_SHA256},
        "matchup": {
            "player2": {"civ": "Spanish", "unit": "Champion", "count": 27},
            "player3": {"civ": "Spanish", "unit": "Paladin", "count": 16},
            "purchase_rule": "equal total unweighted resources; cheaper side capped at 27",
            "resource_totals": {"player2": 2160, "player3": 2160},
        },
        "runs": [],
    }

    for repeat in range(1, args.repeats + 1):
        run_dir = args.output / f"run_{repeat:03d}"
        run_dir.mkdir()
        log_path = run_dir / "record.log"
        log_path.write_text("", encoding="utf-8")
        print(f"===== GAME REPEAT {repeat}/{args.repeats} =====", flush=True)
        raw_path = run_matchup(
            "Spanish",
            "champion",
            "Spanish",
            "paladin",
            name=f"{STEM}.mov",
            copy_to=run_dir,
            raw_copy_to=run_dir,
            cap=args.cap,
            mode="resources",
            unit_cap=27,
            counts_override=EXPECTED_COUNTS,
            compose=False,
            out_mov=str(Path(tempfile.gettempdir()) / f"aoe2_champion_paladin_{repeat:03d}.mov"),
            final=str(Path(tempfile.gettempdir()) / f"aoe2_champion_paladin_{repeat:03d}.mp4"),
            dismiss_after=True,
            logfile=str(log_path),
            template=GOLDEN,
        )
        generated = RUN_DIR / "champion_vs_paladin.aoe2scenario"
        scenario_copy = run_dir / f"{STEM}.aoe2scenario"
        shutil.copy2(generated, scenario_copy)
        run_manifest = {
            "repeat": repeat,
            "raw_video": str(Path(raw_path).relative_to(args.output)),
            "scenario": validate_generated_scenario(scenario_copy),
            "capture": validate_capture(run_dir),
        }
        (run_dir / "capture_manifest.json").write_text(
            json.dumps(run_manifest, indent=2) + "\n", encoding="utf-8"
        )
        batch["runs"].append(run_manifest)
        (args.output / "capture_manifest.json").write_text(
            json.dumps(batch, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(run_manifest["capture"], sort_keys=True), flush=True)

    print(f"DONE {args.repeats} validated captures -> {args.output}", flush=True)


if __name__ == "__main__":
    main()
