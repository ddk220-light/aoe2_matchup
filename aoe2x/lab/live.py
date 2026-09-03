"""Serial, resumable live-game capture using the canonical AOE2 Lab plan."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from .artifacts import Job
from .config import LabConfig, apply_live_environment
from .errors import LiveCaptureError, PreflightError
from .io import read_json, sha256, utc_now, write_json
from .retention import (
    apply_run_retention,
    normalize_retention,
    validate_retained_statistics,
)


GOLDENS = {
    "melee_vs_melee": (
        "apps/video/templates/lab_goldens/melee_vs_melee.aoe2scenario",
        "31f3bed38ce0512b484124d89d5aa4e97318b3ea55c398bb8dad27242c769f4e",
    ),
    "ranged_vs_ranged": (
        "apps/video/templates/lab_goldens/ranged_vs_ranged.aoe2scenario",
        "f44097ef86e6b123c6dfeb4989842e548af91f0d492e69caf6de87148f040883",
    ),
    "ranged_vs_melee": (
        "apps/video/templates/lab_goldens/ranged_vs_melee.aoe2scenario",
        "13c41485a00943ef525cab848d835d1379259fc8fff38b83d4ec510bc8824783",
    ),
    "melee_vs_ranged": (
        "apps/video/templates/lab_goldens/melee_vs_ranged.aoe2scenario",
        "faf8d616ac9bb4601c4582deccec0984e997617d8c121bc44d698c7963f038a8",
    ),
}


def golden_path(config: LabConfig, family: str) -> Path:
    relative, expected = GOLDENS[family]
    path = config.project_root / relative
    if not path.exists() or sha256(path) != expected:
        raise PreflightError(
            f"golden scenario is missing or changed: {path}",
            hint="restore the committed/current project-local golden before live capture",
        )
    return path


def _load_stack(config: LabConfig):
    apply_live_environment(config)
    import sys

    video_root = config.project_root / "apps" / "video"
    if str(video_root) not in sys.path:
        sys.path.insert(0, str(video_root))
    try:
        from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
        from auto import grpc_capture, platform_io, vision
        from auto.orchestrate_matchup import RUN_DIR, resolve_side, run_matchup
        from build_run import _ai_configuration, build_run, unit_const
    except ImportError as error:
        raise PreflightError(
            f"live-capture dependency is unavailable: {error}",
            hint="create apps/video/.venv and install apps/video/auto/requirements_windows.txt",
        ) from error
    return {
        "AoE2DEScenario": AoE2DEScenario,
        "grpc_capture": grpc_capture,
        "platform_io": platform_io,
        "vision": vision,
        "RUN_DIR": RUN_DIR,
        "resolve_side": resolve_side,
        "run_matchup": run_matchup,
        "ai_configuration": _ai_configuration,
        "build_run": build_run,
        "unit_const": unit_const,
    }


def _source_positions(scenario, player_id: int) -> list[tuple[float, float]]:
    units = list(scenario.unit_manager.get_player_units(player_id))
    if len(units) != 27:
        raise LiveCaptureError(
            f"golden Player {player_id} exposes {len(units)} slots instead of 27"
        )
    return [(round(float(unit.x), 6), round(float(unit.y), 6)) for unit in units]


def _player_runtime_configuration(scenario) -> tuple:
    """Golden player facts that generation is never allowed to rewrite."""
    rows = []
    for player in scenario.player_manager.players:
        player_id = int(player.player_id)
        if player_id not in (1, 2, 3, 4):
            continue
        rows.append((
            player_id,
            int(player.color),
            bool(player.human),
            bool(player.lock_personality),
            tuple(int(value) for value in player.diplomacy),
            bool(player.allied_victory),
            int(player.starting_age),
        ))
    return tuple(rows)


def _trigger_structure(scenario) -> tuple:
    """Compare authored trigger mechanics while allowing intended roster retargets."""
    rows = []
    for trigger in scenario.trigger_manager.triggers:
        conditions = tuple((
            int(condition.condition_type),
            int(condition.source_player),
            int(condition.target_player),
            int(condition.area_x1), int(condition.area_y1),
            int(condition.area_x2), int(condition.area_y2),
            int(condition.timer),
            bool(condition.inverted),
        ) for condition in trigger.conditions)
        effects = tuple((
            int(effect.effect_type),
            int(effect.source_player),
            int(effect.target_player),
            int(effect.diplomacy),
            int(effect.mutual_diplomacy),
            int(effect.area_x1), int(effect.area_y1),
            int(effect.area_x2), int(effect.area_y2),
            int(effect.timer),
        ) for effect in trigger.effects)
        rows.append((
            trigger.name,
            bool(trigger.enabled),
            bool(trigger.looping),
            bool(trigger.execute_on_load),
            conditions,
            effects,
        ))
    return tuple(rows)


def _validate_scenario(config: LabConfig, plan: dict, generated: Path, stack: dict) -> dict:
    family = plan["scenario"]["family"]
    source_path = golden_path(config, family)
    scenario_type = stack["AoE2DEScenario"]
    source = scenario_type.from_file(str(source_path))
    target = scenario_type.from_file(str(generated))
    resolved = [
        stack["resolve_side"](plan["side2"]["civ"], plan["side2"]["slug"]),
        stack["resolve_side"](plan["side3"]["civ"], plan["side3"]["slug"]),
    ]
    masters = [stack["unit_const"](side[1]) for side in resolved]
    counts = [plan["side2"]["count"], plan["side3"]["count"]]
    for player_id, count, master in zip((2, 3), counts, masters):
        expected = _source_positions(source, player_id)[:count]
        actual = [
            (round(float(unit.x), 6), round(float(unit.y), 6))
            for unit in target.unit_manager.get_player_units(player_id)
            if int(unit.unit_const) == master
        ]
        if actual != expected:
            raise LiveCaptureError(
                f"generated Player {player_id} roster/positions differ from first-N golden slots"
            )
    p4 = lambda scenario: [  # noqa: E731
        (round(float(unit.x), 6), round(float(unit.y), 6), int(unit.unit_const))
        for unit in scenario.unit_manager.get_player_units(4)
    ]
    if p4(target) != p4(source):
        raise LiveCaptureError("generated Player 4 roster or positions changed")
    if stack["ai_configuration"](target) != stack["ai_configuration"](source):
        raise LiveCaptureError("generated AI configuration differs from the golden")
    if _player_runtime_configuration(target) != _player_runtime_configuration(source):
        raise LiveCaptureError(
            "generated colors, starting ages, or diplomacy differ from the golden"
        )
    if _trigger_structure(target) != _trigger_structure(source):
        raise LiveCaptureError("generated trigger structure differs from the golden")
    return {
        "sha256": sha256(generated),
        "sourceGolden": str(source_path.relative_to(config.project_root)).replace("\\", "/"),
        "sourceGoldenSha256": plan["scenario"]["goldenSha256"],
        "positionRule": "first_n_units_in_player_order",
        "positionsMatchGolden": True,
        "player4Unchanged": True,
        "aiConfigurationMatchesGolden": True,
        "playerRuntimeConfigurationMatchesGolden": True,
        "triggerStructureMatchesGolden": True,
    }


def _capture_prefix(run_directory: Path, stem: str) -> Path:
    return run_directory / "raw recordings" / stem


def _temporary_grpc_prefix(video: Path) -> Path:
    return Path(tempfile.gettempdir()) / f"grpc_{video.stem}"


def _archive_attempt_diagnostics(
    prefix: Path, run_directory: Path, attempt: int | None
) -> None:
    label = "grpc_logger" if attempt is None else f"failure_attempt_{attempt}.grpc"
    extensions = (".logger.log",) if attempt is None else (
        ".logger.log", ".meta.json", ".END", ".frames.bin",
    )
    for extension in extensions:
        source = Path(f"{prefix}{extension}")
        if not source.exists():
            continue
        suffix = extension if attempt is not None else ".log"
        destination = run_directory / f"{label}{suffix}"
        shutil.copy2(source, destination)


def _clear_temporary_capture(video: Path, prefix: Path) -> None:
    video.unlink(missing_ok=True)
    video.with_suffix(".mp4").unlink(missing_ok=True)
    for extension in (
        ".END", ".meta.json", ".hp_log.jsonl", ".frames.bin",
        ".seed_snap.bin", ".reseed.bin", ".hp.json", ".live_seed.bin",
        ".logger.log",
    ):
        Path(f"{prefix}{extension}").unlink(missing_ok=True)


def _validate_capture(run_directory: Path, plan: dict) -> dict[str, Any]:
    prefix = _capture_prefix(run_directory, plan["matchupId"])
    required = [
        prefix.with_suffix(".mov"),
        Path(f"{prefix}.frames.bin"),
        Path(f"{prefix}.meta.json"),
        Path(f"{prefix}.END"),
        Path(f"{prefix}.hp.json"),
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise LiveCaptureError(f"capture is incomplete; missing: {', '.join(missing)}")
    frames = Path(f"{prefix}.frames.bin")
    if frames.stat().st_size < 1_000_000:
        raise LiveCaptureError("gRPC frame dump is unexpectedly small")
    sidecar = json.loads(Path(f"{prefix}.hp.json").read_text(encoding="utf-8"))
    rows = sidecar.get("rows") or []
    if not rows:
        raise LiveCaptureError("gRPC sidecar has no decoded rows")
    first, final = rows[0], rows[-1]
    expected_counts = (plan["side2"]["count"], plan["side3"]["count"])
    start_counts = (first["side1"]["count"], first["side2"]["count"])
    if start_counts != expected_counts:
        raise LiveCaptureError(
            f"gRPC starting counts are {start_counts}; expected {expected_counts}"
        )
    end_counts = (final["side1"]["count"], final["side2"]["count"])
    if (end_counts[0] == 0) == (end_counts[1] == 0):
        raise LiveCaptureError(f"gRPC did not contain one defeated army: {end_counts}")
    winner_index = 0 if end_counts[0] > 0 else 1
    winner_owner = winner_index + 2
    winner_key = f"side{winner_index + 1}"
    loser_key = "side2" if winner_index == 0 else "side1"
    winner_hp = float(final[winner_key]["hp"])
    starting_hp = float(first[winner_key]["hp"])
    signed = (1 if winner_owner == 2 else -1) * winner_hp / starting_hp * 100
    # Spawn-on-death units can create a temporary zero-count interval.  Report
    # the beginning of the final, stable defeated run rather than that gap.
    final_zero_start = len(rows) - 1
    while (final_zero_start > 0
           and rows[final_zero_start - 1][loser_key]["count"] == 0):
        final_zero_start -= 1
    elimination = rows[final_zero_start]
    return {
        "gameVersion": sidecar.get("game_version"),
        "startCounts": list(start_counts),
        "winnerOwner": winner_owner,
        "winnerSlug": (
            plan["side2"]["slug"] if winner_owner == 2 else plan["side3"]["slug"]
        ),
        "survivors": end_counts[winner_index],
        "winnerHp": winner_hp,
        "winnerStartingHp": starting_hp,
        "winnerRemainingHpPercent": abs(signed),
        "signedRemainingHpPercent": signed,
        "eliminationTimeSeconds": elimination["game_s"],
        "grpcRows": len(rows),
        "framesBytes": frames.stat().st_size,
        "framesSha256": sha256(frames),
        "artifacts": {
            "video": str(required[0].relative_to(run_directory)).replace("\\", "/"),
            "frames": str(frames.relative_to(run_directory)).replace("\\", "/"),
            "sidecar": str(required[4].relative_to(run_directory)).replace("\\", "/"),
        },
    }


def _storage_preflight(
    config: LabConfig, *, repeats: int, retention: str
) -> dict[str, Any]:
    """Require room for the next capture before the game is touched.

    Stats-only capture needs space for one peak recording because it is removed
    after validation. Archive/raw policies accumulate recordings across repeats.
    """
    selected = normalize_retention(retention, config.live_retention)
    recording_count = 1 if selected == "stats" else repeats
    required = (
        config.live_min_free_bytes
        + config.live_estimated_recording_bytes * recording_count
    )
    roots = (config.artifacts_root, Path(tempfile.gettempdir()))
    checked: dict[str, dict[str, Any]] = {}
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
        anchor = root.resolve().anchor.lower() or str(root.resolve())
        if anchor in checked:
            continue
        free = shutil.disk_usage(root).free
        checked[anchor] = {
            "path": str(root.resolve()),
            "freeBytes": free,
            "requiredBytes": required,
        }
        if free < required:
            raise PreflightError(
                f"live capture storage preflight failed on {anchor}: "
                f"{free / 1024 ** 3:.2f} GiB free, "
                f"{required / 1024 ** 3:.2f} GiB required for {selected} retention",
                hint=(
                    "free disk space, choose retention=stats, or lower the configured "
                    "live estimated recording size before starting the game"
                ),
            )
    return {
        "retention": selected,
        "requiredBytes": required,
        "volumes": list(checked.values()),
    }


def preflight_live(
    config: LabConfig,
    plan: dict,
    *,
    check_ui: bool,
    repeats: int = 1,
    retention: str | None = None,
) -> dict:
    stack = _load_stack(config)
    storage = _storage_preflight(
        config,
        repeats=repeats,
        retention=normalize_retention(retention, config.live_retention),
    )
    golden_path(config, plan["scenario"]["family"])
    if config.game_executable and not config.game_executable.exists():
        raise PreflightError(f"configured game executable does not exist: {config.game_executable}")
    try:
        resolved_sides = [
            stack["resolve_side"](plan[key]["civ"], plan[key]["slug"])
            for key in ("side2", "side3")
        ]
        for side in resolved_sides:
            stack["unit_const"](side[1])
    except Exception as error:
        raise PreflightError(
            f"live unit/civilization resolution failed: {error}",
            hint="use a civilization/unit combination supported by the live scenario catalogue",
        ) from error
    if not config.grpc_python.exists() or not config.grpc_logger.exists():
        raise PreflightError("gRPC Python or logger path does not exist")
    if not stack["grpc_capture"].available():
        raise PreflightError("gRPC capture stack reports unavailable")
    scenario_directory = stack["platform_io"].scenario_dir()
    if not scenario_directory.exists():
        raise PreflightError(f"scenario directory does not exist: {scenario_directory}")
    result = {
        "golden": True,
        "grpc": True,
        "scenarioDirectory": str(scenario_directory),
        "resolvedSides": [side[1] for side in resolved_sides],
        "storage": storage,
        "ui": None,
    }
    if check_ui:
        # NoneAI is embedded in each golden. DE extracts it into this scratch
        # directory; Windows cleanup may remove the empty parent between runs.
        (Path(tempfile.gettempdir()) / "AOE2DE_Temp").mkdir(exist_ok=True)
        stack["platform_io"].activate_game()
        time.sleep(1.0)
        state = stack["vision"].detect_state(stack["vision"].grab())
        if state not in ("editor", "load_dialog", "main_menu"):
            raise PreflightError(
                f"AoE2 must be ready in Scenario Editor; detected {state!r}"
            )
        result["ui"] = state
    return result


def _summarize_live(job: Job, repeats: int) -> dict:
    rows = []
    for repeat in range(1, repeats + 1):
        manifest = read_json(job.live_directory / f"run_{repeat:03d}" / "manifest.json")
        rows.append({
            "repeat": repeat,
            **manifest["capture"],
            "retention": manifest.get("retention", {"mode": "raw"}),
        })
    scores = [row["signedRemainingHpPercent"] for row in rows]
    owners = sorted({row["winnerOwner"] for row in rows})
    summary = {
        "schemaVersion": 1,
        "jobId": job.job_id,
        "generatedAt": utc_now(),
        "repeatCount": len(rows),
        "winnerOwners": owners,
        "winnerFlippedAcrossRepeats": len(owners) > 1,
        "retentionModes": sorted({row["retention"]["mode"] for row in rows}),
        "rawRecordingsRetained": any(
            row["retention"].get("recordingsRetained", True) for row in rows
        ),
        "meanSignedRemainingHpPercent": sum(scores) / len(scores),
        "minSignedRemainingHpPercent": min(scores),
        "maxSignedRemainingHpPercent": max(scores),
        "runs": rows,
    }
    write_json(job.live_directory / "summary.json", summary)
    return summary


def run_live(
    config: LabConfig,
    job: Job,
    *,
    repeats: int,
    retries: int = 1,
    retention: str | None = None,
) -> dict:
    if repeats < 1 or retries < 0:
        raise LiveCaptureError("repeats must be positive and retries non-negative")
    selected_retention = normalize_retention(retention, config.live_retention)
    plan = read_json(job.plan_path)
    stack = _load_stack(config)
    preflight = preflight_live(
        config,
        plan,
        check_ui=True,
        repeats=repeats,
        retention=selected_retention,
    )
    job.transition("CAPTURING_LIVE")
    job.update_section(
        "live",
        requestedRepeats=repeats,
        retention=selected_retention,
        storagePreflight=preflight["storage"],
        startedAt=utc_now(),
    )
    complete = []
    for repeat in range(1, repeats + 1):
        run_directory = job.live_directory / f"run_{repeat:03d}"
        manifest_path = run_directory / "manifest.json"
        if manifest_path.exists():
            existing = read_json(manifest_path)
            existing_retention = (existing.get("retention") or {}).get("mode", "raw")
            existing["capture"] = validate_retained_statistics(
                run_directory,
                existing,
                (plan["side2"]["count"], plan["side3"]["count"]),
            )
            if selected_retention == "stats" and existing_retention == "raw":
                existing["retention"] = apply_run_retention(
                    run_directory, selected_retention
                )
                write_json(manifest_path, existing)
            elif selected_retention == "stats" and existing_retention == "archive":
                # An explicitly requested archive is stronger than stats retention;
                # never silently delete it on a later default-policy resume.
                write_json(manifest_path, existing)
            elif selected_retention != existing_retention:
                raise LiveCaptureError(
                    f"repeat {repeat} was retained as {existing_retention}; "
                    f"it cannot be resumed as {selected_retention} without recapture"
                )
            else:
                write_json(manifest_path, existing)
            complete.append(repeat)
            continue
        run_directory.mkdir(parents=True, exist_ok=True)
        error: BaseException | None = None
        for attempt in range(1, retries + 2):
            try:
                log_path = run_directory / f"capture_attempt_{attempt}.log"
                temporary_video = Path(tempfile.gettempdir()) / (
                    f"aoe2lab_{job.job_id}_{repeat:03d}.mov"
                )
                temporary_grpc = _temporary_grpc_prefix(temporary_video)
                stack["run_matchup"](
                    plan["side2"]["civ"],
                    plan["side2"]["slug"],
                    plan["side3"]["civ"],
                    plan["side3"]["slug"],
                    name=f"{plan['matchupId']}.mov",
                    copy_to=run_directory,
                    raw_copy_to=run_directory,
                    cap=config.live_cap_seconds,
                    mode="resources",
                    unit_cap=plan["balance"]["cap"],
                    counts_override=(plan["side2"]["count"], plan["side3"]["count"]),
                    compose=False,
                    out_mov=str(temporary_video),
                    final=str(temporary_video.with_suffix(".mp4")),
                    dismiss_after=True,
                    logfile=str(log_path),
                    template=golden_path(config, plan["scenario"]["family"]),
                    ranged_override=(plan["side2"]["ranged"], plan["side3"]["ranged"]),
                    scenario_validator=lambda generated: _validate_scenario(
                        config, plan, generated, stack
                    ),
                    require_grpc=True,
                )
                resolved2 = stack["resolve_side"](
                    plan["side2"]["civ"], plan["side2"]["slug"]
                )[1]
                resolved3 = stack["resolve_side"](
                    plan["side3"]["civ"], plan["side3"]["slug"]
                )[1]
                generated = stack["RUN_DIR"] / f"{resolved2}_vs_{resolved3}.aoe2scenario"
                scenario_copy = run_directory / f"{plan['matchupId']}.aoe2scenario"
                shutil.copy2(generated, scenario_copy)
                run_manifest = {
                    "schemaVersion": 1,
                    "repeat": repeat,
                    "attempt": attempt,
                    "capturedAt": utc_now(),
                    "scenario": _validate_scenario(config, plan, scenario_copy, stack),
                    "capture": _validate_capture(run_directory, plan),
                }
                write_json(manifest_path, run_manifest)
                try:
                    _archive_attempt_diagnostics(
                        temporary_grpc, run_directory, attempt=None
                    )
                except OSError:
                    pass
                run_manifest["retention"] = apply_run_retention(
                    run_directory, selected_retention
                )
                write_json(manifest_path, run_manifest)
                _clear_temporary_capture(temporary_video, temporary_grpc)
                error = None
                break
            except Exception as current:  # preserve diagnostics before bounded retry
                error = current
                temporary_video = Path(tempfile.gettempdir()) / (
                    f"aoe2lab_{job.job_id}_{repeat:03d}.mov"
                )
                temporary_grpc = _temporary_grpc_prefix(temporary_video)
                try:
                    stack["vision"].grab().save(
                        run_directory / f"failure_attempt_{attempt}.png"
                    )
                except Exception:
                    pass
                write_json(run_directory / f"failure_attempt_{attempt}.json", {
                    "type": type(current).__name__,
                    "message": str(current),
                    "attempt": attempt,
                    "at": utc_now(),
                })
                try:
                    _archive_attempt_diagnostics(
                        temporary_grpc, run_directory, attempt=attempt
                    )
                except OSError:
                    pass
                finally:
                    _clear_temporary_capture(temporary_video, temporary_grpc)
        if error is not None:
            raise LiveCaptureError(
                f"live repeat {repeat} failed after {retries + 1} attempts: {error}"
            ) from error
        complete.append(repeat)
        job.update_section("live", completedRepeats=complete, lastCompletedRepeat=repeat)
    summary = _summarize_live(job, repeats)
    job.update_section(
        "live", completedRepeats=complete, completedAt=utc_now(), summary="live/summary.json"
    )
    job.transition("LIVE_COMPLETE")
    return summary
