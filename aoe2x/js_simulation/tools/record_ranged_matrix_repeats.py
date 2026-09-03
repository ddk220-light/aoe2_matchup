"""Record the current ranged matrix or the mechanics-expansion roster.

The driver uses only the verified project-local ranged goldens, preserves their
literal first-N slot order, and validates every generated scenario and raw gRPC
capture. Completed runs are skipped on restart, making the long batch resumable.

The ``expanded`` matrix adds five requested units against the eight-unit current
golden roster, plus every unique pairing among the five additions.  It selects
the melee/ranged scenario family from the ordered unit roles and keeps the old
14-row matrix as the default so historical capture commands remain stable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VIDEO_DIR = ROOT / "apps" / "video"
sys.path.insert(0, str(VIDEO_DIR))

from AoE2ScenarioParser import settings  # noqa: E402
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario  # noqa: E402
from auto import grpc_capture, vision  # noqa: E402
from auto.orchestrate_matchup import RUN_DIR, resolve_side, run_matchup  # noqa: E402
from build_run import unit_const  # noqa: E402


settings.PRINT_STATUS_UPDATES = False
SOURCE_ROOT = (
    ROOT / "aoe2x" / "js_simulation" / "calibration" / "live_observations"
    / "current_ranged_goldens_2026-08-29" / "source"
)
GOLDENS = {
    "melee_vs_melee": {
        "path": (
            ROOT / "aoe2x" / "js_simulation" / "calibration"
            / "live_observations" / "current_melee_golden_2026-08-28"
            / "source" / "meleevsmelee.aoe2scenario"
        ),
        "sha256": "31f3bed38ce0512b484124d89d5aa4e97318b3ea55c398bb8dad27242c769f4e",
    },
    "ranged_vs_ranged": {
        "path": SOURCE_ROOT / "rangedvsranged.aoe2scenario",
        "sha256": "f44097ef86e6b123c6dfeb4989842e548af91f0d492e69caf6de87148f040883",
    },
    "ranged_vs_melee": {
        "path": SOURCE_ROOT / "rangedvsmelee.aoe2scenario",
        "sha256": "13c41485a00943ef525cab848d835d1379259fc8fff38b83d4ec510bc8824783",
    },
    "melee_vs_ranged": {
        "path": SOURCE_ROOT / "meleevsranged.aoe2scenario",
        "sha256": "faf8d616ac9bb4601c4582deccec0984e997617d8c121bc44d698c7963f038a8",
    },
}
DEFAULT_OUTPUT = (
    ROOT / "aoe2x" / "js_simulation" / "calibration" / "live_observations"
    / "ranged_matrix_5x_2026-08-29"
)
EXPANDED_DEFAULT_OUTPUT = (
    ROOT / "aoe2x" / "js_simulation" / "calibration" / "live_observations"
    / "expanded_roster_5x_2026-08-31"
)
REQUESTED_DEFAULT_OUTPUT = (
    ROOT / "aoe2x" / "js_simulation" / "calibration" / "live_observations"
    / "requested_roster_vs_arb_paladin_1x_2026-08-31"
)


@dataclass(frozen=True)
class Side:
    civ: str
    slug: str
    label: str
    cost: int
    role: str = "melee"


@dataclass(frozen=True)
class Matchup:
    family: str
    side1: Side
    side2: Side

    @property
    def key(self) -> str:
        return f"{self.side1.slug}_vs_{self.side2.slug}"

    @property
    def counts(self) -> tuple[int, int]:
        if self.side1.cost <= self.side2.cost:
            return 27, max(1, (27 * self.side1.cost) // self.side2.cost)
        return max(1, (27 * self.side2.cost) // self.side1.cost), 27


ARB = Side("Chinese", "arbalester", "Arbalester", 70, "ranged")
HC = Side("Spanish", "hand_cannoneer", "Hand Cannoneer", 95, "ranged")
HCA = Side("Saracens", "heavy_cav_archer", "Heavy Cavalry Archer", 100, "ranged")
PAL = Side("Spanish", "paladin", "Paladin", 135)
STEPPE = Side("Cumans", "elite_steppe", "Elite Steppe Lancer", 110)
HUSSAR = Side("Spanish", "hussar", "Hussar", 80)
CHAMP = Side("Chinese", "champion", "Champion", 70)
HALB = Side("Bulgarians", "halberdier", "Halberdier", 60)

ELEPHANT = Side("Burmese", "elite_elephant", "Elite Battle Elephant", 170)
SCORPION = Side("Chinese", "heavy_scorpion", "Heavy Scorpion", 150, "ranged")
ONAGER = Side("Aztecs", "siege_onager", "Siege Onager", 295, "ranged")
SKIRMISHER = Side("Chinese", "imp_elite_skirm", "Elite Skirmisher", 60, "ranged")
CAMEL = Side("Turks", "heavy_camel", "Heavy Camel Rider", 115)

# Fully-upgraded Imperial forms requested on 2026-08-31. Units without an
# elite upgrade retain their one in-game form; every other row names the elite
# scenario unit explicitly. Costs are unweighted per-unit food+wood+gold from
# the current reference DB (Blackwood Archer's two-unit train batch is already
# divided to 40 resources per placed unit).
REQUESTED_ROSTER = (
    Side("Wu", "jian_swordsman_wu", "Jian Swordsman", 95),
    Side("Wei", "xianbei_raider_wei", "Xianbei Raider", 90, "ranged"),
    Side("Khitans", "mounted_trebuchet_khitans", "Mounted Trebuchet", 350, "ranged"),
    Side("Jurchens", "grenadier_jurchens", "Grenadier", 100, "ranged"),
    Side("Shu", "war_chariot_shu", "War Chariot", 155, "ranged"),
    Side("Shu", "elite_white_feather_guard_shu", "Elite White Feather Guard", 75),
    Side("Wei", "elite_tiger_cavalry_wei", "Elite Tiger Cavalry", 140),
    Side("Tupi", "elite_blackwood_archer_tupi", "Elite Blackwood Archer", 40, "ranged"),
    Side("Tupi", "elite_ibirapema_warrior_tupi", "Elite Ibirapema Warrior", 90),
    Side("Muisca", "elite_temple_guard_muisca", "Elite Temple Guard", 115),
    Side("Muisca", "elite_guecha_warrior_muisca", "Elite Guecha Warrior", 110, "ranged"),
    Side("Mapuche", "elite_bolas_rider_mapuche", "Elite Bolas Rider", 95, "ranged"),
    Side("Mapuche", "elite_kona_mapuche", "Elite Kona", 105),
    Side("Bohemians", "elite_hussite_wagon_bohemians", "Elite Hussite Wagon", 180, "ranged"),
    Side("Japanese", "elite_samurai_japanese", "Elite Samurai", 75),
    Side("Chinese", "elite_chu_ko_nu_chinese", "Elite Chu Ko Nu", 75, "ranged"),
    Side("Cumans", "elite_kipchak_cumans", "Elite Kipchak", 95, "ranged"),
    Side("Burgundians", "elite_coustillier_burgundians", "Elite Coustillier", 110),
    Side("Poles", "elite_obuch_poles", "Elite Obuch", 75),
)


def family_for(side1: Side, side2: Side) -> str:
    if side1.role == "melee" and side2.role == "melee":
        return "melee_vs_melee"
    if side1.role == "ranged" and side2.role == "ranged":
        return "ranged_vs_ranged"
    if side1.role == "ranged":
        return "ranged_vs_melee"
    return "melee_vs_ranged"

MATCHUPS = (
    Matchup("ranged_vs_ranged", ARB, HC),
    Matchup("ranged_vs_ranged", ARB, HCA),
    *(Matchup("ranged_vs_melee", ranged, melee)
      for ranged in (ARB, HCA, HC)
      for melee in (PAL, STEPPE, HUSSAR, CHAMP)),
)

EXISTING_ROSTER = (CHAMP, HALB, PAL, STEPPE, HUSSAR, ARB, HC, HCA)
ADDED_ROSTER = (ELEPHANT, SCORPION, ONAGER, SKIRMISHER, CAMEL)
EXPANDED_MATCHUPS = (
    *(Matchup(family_for(added, existing), added, existing)
      for added in ADDED_ROSTER for existing in EXISTING_ROSTER),
    *(Matchup(family_for(left, right), left, right)
      for index, left in enumerate(ADDED_ROSTER)
      for right in ADDED_ROSTER[index + 1:]),
)
REQUESTED_MATCHUPS = tuple(
    Matchup(family_for(unit, reference), unit, reference)
    for unit in REQUESTED_ROSTER
    for reference in (ARB, PAL)
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def army_positions(
    scenario: AoE2DEScenario,
    player_id: int,
    master: int,
) -> list[tuple[float, float]]:
    return [
        (round(float(unit.x), 6), round(float(unit.y), 6))
        for unit in scenario.unit_manager.get_player_units(player_id)
        if int(unit.unit_const) == master
    ]


def source_slot_positions(
    scenario: AoE2DEScenario,
    player_id: int,
) -> list[tuple[float, float]]:
    units = list(scenario.unit_manager.get_player_units(player_id))
    if len(units) != 27:
        raise RuntimeError(
            f"golden player {player_id} must expose 27 slots; found {len(units)}"
        )
    return [(round(float(unit.x), 6), round(float(unit.y), 6)) for unit in units]


def validate_generated_scenario(path: Path, matchup: Matchup) -> dict:
    golden = GOLDENS[matchup.family]["path"]
    source = AoE2DEScenario.from_file(str(golden))
    generated = AoE2DEScenario.from_file(str(path))
    counts = matchup.counts
    masters = tuple(unit_const(resolve_side(side.civ, side.slug)[1]) for side in (
        matchup.side1,
        matchup.side2,
    ))
    expected = {
        player_id: source_slot_positions(source, player_id)[:count]
        for player_id, count in zip((2, 3), counts)
    }
    actual = {
        player_id: army_positions(generated, player_id, master)
        for player_id, master in zip((2, 3), masters)
    }
    if tuple(map(len, actual.values())) != counts:
        raise RuntimeError(
            f"generated roster mismatch for {matchup.key}: expected {counts}, "
            f"got {tuple(map(len, actual.values()))}"
        )
    if actual != expected:
        raise RuntimeError(f"generated positions do not match {matchup.family} first-N slots")
    p4_source = [
        (round(float(unit.x), 6), round(float(unit.y), 6), int(unit.unit_const))
        for unit in source.unit_manager.get_player_units(4)
    ]
    p4_generated = [
        (round(float(unit.x), 6), round(float(unit.y), 6), int(unit.unit_const))
        for unit in generated.unit_manager.get_player_units(4)
    ]
    if p4_generated != p4_source:
        raise RuntimeError("Player-4 diplomacy roster or positions changed")
    return {
        "sha256": sha256(path),
        "counts": {"player2": counts[0], "player3": counts[1]},
        "position_rule": "first_n_units_in_player_order",
        "positions_match_family_golden": True,
        "player4_unchanged": True,
    }


def capture_prefix(run_dir: Path, stem: str) -> Path:
    return run_dir / "raw recordings" / stem


def validate_capture(run_dir: Path, matchup: Matchup) -> dict:
    prefix = capture_prefix(run_dir, matchup.key)
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
    frames = Path(f"{prefix}.frames.bin")
    if frames.stat().st_size < 1_000_000:
        raise RuntimeError("gRPC frame dump is unexpectedly small")
    sidecar = json.loads(Path(f"{prefix}.hp.json").read_text(encoding="utf-8"))
    rows = sidecar.get("rows") or []
    if not rows:
        raise RuntimeError("gRPC HP sidecar has no rows")
    first, final = rows[0], rows[-1]
    start = (first["side1"]["count"], first["side2"]["count"])
    if start != matchup.counts:
        raise RuntimeError(
            f"gRPC starting roster mismatch for {matchup.key}: "
            f"expected {matchup.counts}, got {start}"
        )
    end = (final["side1"]["count"], final["side2"]["count"])
    if (end[0] == 0) == (end[1] == 0):
        raise RuntimeError(f"unexpected final gRPC roster for {matchup.key}: {end}")
    winner_index = 0 if end[0] > 0 else 1
    winner_side = matchup.side1 if winner_index == 0 else matchup.side2
    eliminated_key = "side2" if winner_index == 0 else "side1"
    elimination = next(row for row in rows if row[eliminated_key]["count"] == 0)
    return {
        "game_version": sidecar.get("game_version"),
        "start_counts": list(start),
        "winner": winner_side.slug,
        "survivors": end[winner_index],
        "winner_hp": final[f"side{winner_index + 1}"]["hp"],
        "elimination_time_s": elimination["game_s"],
        "grpc_rows": len(rows),
        "frames_bytes": frames.stat().st_size,
        "frames_sha256": sha256(frames),
    }


def matchup_manifest(matchup: Matchup) -> dict:
    n1, n2 = matchup.counts
    golden = GOLDENS[matchup.family]
    return {
        "family": matchup.family,
        "golden": {
            "path": str(golden["path"].relative_to(ROOT)),
            "sha256": golden["sha256"],
        },
        "side1": {
            **asdict(matchup.side1),
            "count": n1,
            "resources": n1 * matchup.side1.cost,
        },
        "side2": {
            **asdict(matchup.side2),
            "count": n2,
            "resources": n2 * matchup.side2.cost,
        },
        "purchase_rule": (
            "unweighted resources; cheaper side capped at 27 and pricier side floored"
        ),
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--matrix",
        choices=("current", "expanded", "requested"),
        default="current",
        help=(
            "capture the historical 14 rows, five-unit expansion matrix, or the "
            "requested fully-upgraded roster versus Arbalester and Paladin"
        ),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cap", type=int, default=210)
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="run only these matchup keys",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="skip these matchup keys (also when resuming a larger manifest)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the selected matchup plan without touching the game",
    )
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be positive")
    candidates = (
        MATCHUPS if args.matrix == "current"
        else EXPANDED_MATCHUPS if args.matrix == "expanded"
        else REQUESTED_MATCHUPS
    )
    if args.output is None:
        args.output = (
            DEFAULT_OUTPUT if args.matrix == "current"
            else EXPANDED_DEFAULT_OUTPUT if args.matrix == "expanded"
            else REQUESTED_DEFAULT_OUTPUT
        )
    selected = [
        matchup for matchup in candidates
        if (not args.only or matchup.key in args.only)
        and matchup.key not in args.exclude
    ]
    requested_keys = set(args.only) | set(args.exclude)
    unknown = sorted(requested_keys - {matchup.key for matchup in candidates})
    if unknown:
        raise SystemExit(f"unknown matchup keys: {unknown}")
    if not selected:
        raise SystemExit("no matchups selected")
    if args.list:
        for matchup in selected:
            print(
                f"{matchup.key}\t{matchup.family}\t"
                f"{matchup.counts[0]}v{matchup.counts[1]}\t"
                f"{matchup.side1.civ} {matchup.side1.label}\t"
                f"{matchup.side2.civ} {matchup.side2.label}"
            )
        print(f"TOTAL\t{len(selected)}")
        return
    for golden in GOLDENS.values():
        if not golden["path"].exists() or sha256(golden["path"]) != golden["sha256"]:
            raise SystemExit(f"golden is missing or changed: {golden['path']}")
    if not grpc_capture.available():
        raise SystemExit("gRPC capture stack is unavailable")
    state = vision.detect_state(vision.grab())
    if state not in ("editor", "load_dialog"):
        raise SystemExit(
            "AoE2 must be in the Scenario Editor or its Load Scenario dialog; "
            f"detected {state!r}"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    batch_path = args.output / "capture_manifest.json"
    if batch_path.exists():
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        expected_keys = [matchup.key for matchup in selected]
        manifest_keys = set(batch.get("matchup_keys", []))
        if (
            batch.get("repeats") != args.repeats
            or not set(expected_keys).issubset(manifest_keys)
        ):
            raise SystemExit("existing batch manifest does not match requested matrix")
    else:
        batch = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "repeats": args.repeats,
            "matchup_keys": [matchup.key for matchup in selected],
            "matchups": {matchup.key: matchup_manifest(matchup) for matchup in selected},
            "runs": {},
        }
        write_json(batch_path, batch)

    total = len(selected) * args.repeats
    manifest_total = len(batch["matchup_keys"]) * args.repeats

    def manifest_completed_runs() -> int:
        return sum(
            len({row.get("repeat") for row in batch["runs"].get(key, [])})
            for key in batch["matchup_keys"]
        )

    complete = 0
    for matchup_index, matchup in enumerate(selected, 1):
        matchup_dir = args.output / matchup.key
        matchup_dir.mkdir(exist_ok=True)
        batch["runs"].setdefault(matchup.key, [])
        for repeat in range(1, args.repeats + 1):
            run_dir = matchup_dir / f"run_{repeat:03d}"
            run_manifest_path = run_dir / "capture_manifest.json"
            if run_manifest_path.exists():
                existing = json.loads(run_manifest_path.read_text(encoding="utf-8"))
                validate_capture(run_dir, matchup)
                complete += 1
                print(
                    f"SKIP validated {complete}/{total} {matchup.key} run {repeat}",
                    flush=True,
                )
                if not any(
                    row.get("repeat") == repeat
                    for row in batch["runs"][matchup.key]
                ):
                    batch["runs"][matchup.key].append(existing)
                    batch["completed_runs"] = manifest_completed_runs()
                    batch["updated_at"] = datetime.now(timezone.utc).isoformat()
                    write_json(batch_path, batch)
                continue
            run_dir.mkdir(exist_ok=True)
            log_path = run_dir / "record.log"
            print(
                f"===== {complete + 1}/{total} {matchup.key} "
                f"({matchup_index}/{len(selected)}) REPEAT {repeat}/{args.repeats} =====",
                flush=True,
            )
            raw_path = run_matchup(
                matchup.side1.civ,
                matchup.side1.slug,
                matchup.side2.civ,
                matchup.side2.slug,
                name=f"{matchup.key}.mov",
                copy_to=run_dir,
                raw_copy_to=run_dir,
                cap=args.cap,
                mode="resources",
                unit_cap=27,
                counts_override=matchup.counts,
                compose=False,
                out_mov=str(
                    Path(tempfile.gettempdir())
                    / f"aoe2_{matchup.key}_{repeat:03d}.mov"
                ),
                final=str(
                    Path(tempfile.gettempdir())
                    / f"aoe2_{matchup.key}_{repeat:03d}.mp4"
                ),
                dismiss_after=True,
                logfile=str(log_path),
                template=GOLDENS[matchup.family]["path"],
            )
            generated = RUN_DIR / (
                f"{resolve_side(matchup.side1.civ, matchup.side1.slug)[1]}_vs_"
                f"{resolve_side(matchup.side2.civ, matchup.side2.slug)[1]}.aoe2scenario"
            )
            scenario_copy = run_dir / f"{matchup.key}.aoe2scenario"
            shutil.copy2(generated, scenario_copy)
            run_manifest = {
                "repeat": repeat,
                "raw_video": str(Path(raw_path).relative_to(args.output)),
                "scenario": validate_generated_scenario(scenario_copy, matchup),
                "capture": validate_capture(run_dir, matchup),
            }
            write_json(run_manifest_path, run_manifest)
            batch["runs"][matchup.key] = [
                row
                for row in batch["runs"][matchup.key]
                if row.get("repeat") != repeat
            ] + [run_manifest]
            batch["runs"][matchup.key].sort(key=lambda row: row["repeat"])
            complete += 1
            batch["completed_runs"] = manifest_completed_runs()
            batch["updated_at"] = datetime.now(timezone.utc).isoformat()
            write_json(batch_path, batch)
            print(json.dumps(run_manifest["capture"], sort_keys=True), flush=True)

    batch["completed_runs"] = manifest_completed_runs()
    batch["updated_at"] = datetime.now(timezone.utc).isoformat()
    if batch["completed_runs"] == manifest_total:
        batch["completed_at"] = datetime.now(timezone.utc).isoformat()
    else:
        batch.pop("completed_at", None)
    write_json(batch_path, batch)
    print(
        f"DONE {total} selected captures; batch has "
        f"{batch['completed_runs']}/{manifest_total} -> {args.output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
