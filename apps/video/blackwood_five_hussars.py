"""Isolated Blackwood screen experiment: 40 new melee fights, 33 reused ranged fights.

Commands: prepare (no game), capture --pilot, capture, compare. Media assembly is
in build_blackwood_five_hussars.py. Never rewrites the original episode or Goldens.
The baseline uses completed cost-repair recordings wherever army counts changed.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
import time
from pathlib import Path

from aoe2x.lab.cli import _load_batch, _normalize_batch_row, load_matchup_file
from aoe2x.lab.config import load_config
from aoe2x.lab.io import read_json, write_json, utc_now
from aoe2x.lab.live import _load_stack, _validate_scenario, golden_path
from aoe2x.lab.planner import plan_matchup

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "aoe2x/js_simulation/calibration/lab"
KEY = "blackwood-five-hussars"
REPORT = LAB / "campaigns" / KEY
MANIFEST = ROOT / "aoe2lab.recorder.blackwood-five-hussars.json"
BASELINE = REPORT / "baseline.json"


def prepare():
    original = load_matchup_file(ROOT / "aoe2lab.recorder.blackwood-archer-all-unique.toml")
    repairs = read_json(LAB / "campaigns/cost-repairs-v2/replacement-map.json")["jobs"]
    replacements = {r["originalJobId"]: r["replacementJobId"] for r in repairs}
    verified = set()
    for name in ("blackwood-archer-all-unique", "cost-repairs-v2"):
        verified.update(r["jobId"] for r in read_json(LAB / "campaigns" / name / "status.json")["results"]
                        if r["status"] == "verified")
    full = read_json(LAB / "compilations/blackwood-archer-unique-units/final/manifest.json")
    chapters = {r["jobId"]: r for r in full["results"]}
    config, entries, capture, overlays, validations = load_config(), [], [], [], []
    stack = _load_stack(config)
    for old in original["matchups"]:
        original_id = old["id"]
        baseline_id = replacements.get(original_id, original_id)
        assert baseline_id in verified, (baseline_id, "unverified baseline")
        run = LAB / "runs" / baseline_id / "live/run_001"
        previous = read_json(run.parent.parent / "plan.json")
        row = {**old, "balance": {"mode": "equal_resources", "cap": 27, "maxResources": 5000}}
        plan = plan_matchup(config, _normalize_batch_row(row, {}))
        # Earlier plans predate catalog provenance. A corrected price that leaves
        # both rounded counts unchanged does not alter the recorded fight. Preserve
        # the old plan and retain the fresh audited plan separately as evidence.
        for side in ("side2", "side3"):
            assert plan[side]["count"] == previous[side]["count"], (baseline_id, side, "baseline count drift")
        assert plan["scenario"]["family"] == previous["scenario"]["family"]
        assert plan["scenario"]["goldenSha256"] == previous["scenario"]["goldenSha256"]
        recorded = read_json(run / "manifest.json")["capture"]
        assert recorded["startCounts"] == [plan[s]["count"] for s in ("side2", "side3")]
        frames = run / recorded["artifacts"]["frames"]
        assert frames.is_file() and frames.stat().st_size == recorded["framesBytes"], frames
        melee = plan["scenario"]["family"] == "ranged_vs_melee"
        target_id = original_id.replace("blackwood_archer_unique_", "blackwood_archer_five_hussars_") if melee else baseline_id
        if melee:
            row.update(id=target_id, scenario={"player4Count": 5})
            target = plan_matchup(config, _normalize_batch_row(row, {}))
            assert target["side2"] == plan["side2"] and target["side3"] == plan["side3"]
            generated = REPORT / "scenario-preflight" / f"{target_id}.aoe2scenario"
            with contextlib.redirect_stdout(io.StringIO()):
                stack["build_run"](
                    *(stack["resolve_side"](target[s]["civ"], target[s]["slug"]) for s in ("side2", "side3")),
                    generated, counts=(target["side2"]["count"], target["side3"]["count"]),
                    template=golden_path(config, target["scenario"]["family"]), player4_count=5)
                validation = _validate_scenario(config, target, generated, stack)
                old_scenario = stack["AoE2DEScenario"].from_file(str(run / f"{previous['matchupId']}.aoe2scenario"))
            assert len(old_scenario.unit_manager.get_player_units(4)) == 9
            validations.append({"jobId": target_id, "plan": target, "validation": validation})
            capture.append(row)
            overlays.append(row)
        else:
            assert plan["scenario"]["family"] == "ranged_vs_ranged"
            if baseline_id != original_id:
                assert (run / "battle.mp4").is_file(), "corrected ranged source missing"
                overlays.append({**row, "id": baseline_id})
            else:
                # Prefer already trimmed chapter files; if cleaned, recover the
                # exact frame interval from the retained complete episode.
                assert Path(chapters[original_id]["source"]).is_file() or Path(full["output"]).is_file()
        entries.append({"originalJobId": original_id, "baselineJobId": baseline_id, "jobId": target_id,
                        "unit": plan["side3"]["label"], "civ": plan["side3"]["civ"],
                        "family": plan["scenario"]["family"], "mode": "recapture" if melee else "reuse",
                        "mainCounts": recorded["startCounts"], "oldHussars": 9 if melee else 0,
                        "newHussars": 5 if melee else 0, "baselineCapture": recorded,
                        "originalChapter": chapters[original_id], "auditedPlan": plan})
    assert len(entries) == 73 and len(capture) == 40 and len(overlays) == 43
    write_json(MANIFEST, {"schemaVersion": 1, "matchups": capture})
    write_json(ROOT / "aoe2lab.overlays.blackwood-five-hussars.json", {"schemaVersion": 1, "matchups": overlays})
    write_json(BASELINE, {"preparedAt": utc_now(), "subject": "Elite Blackwood Archer", "previousFullVideo": full["output"],
                         "costPolicy": "Audited effective Imperial purchase cost per physical unit; Blackwood pair cost divided by two.",
                         "captureCount": 40, "reuseCount": 33, "correctedRangedChapters": 3, "entries": entries})
    write_json(REPORT / "preflight.json", {"passed": True, "updatedAt": utc_now(), "validations": validations})
    print("Prepared 40 five-Hussar captures and 33 reused ranged chapters (3 cost-corrected).", flush=True)


def capture(pilot=False):
    from finish_pending_production import pause_check
    assert read_json(REPORT / "preflight.json")["passed"]
    manifest, directory = MANIFEST, REPORT
    if pilot:
        manifest = REPORT / "pilot.json"
        write_json(manifest, {"schemaVersion": 1, "matchups": read_json(MANIFEST)["matchups"][:1]})
        directory = REPORT / "pilot"
    pause_check()
    child = subprocess.Popen([sys.executable, "-u", "-m", "aoe2x.lab.recording_campaign", str(manifest),
                              "--reports", str(directory)], cwd=ROOT)
    while child.poll() is None:
        time.sleep(5)
        pause_check()
    if child.returncode:
        raise subprocess.CalledProcessError(child.returncode, child.args)


def terminal_hp_outcome(capture, timeline):
    """Include damage captured after the recorder's coarser winner summary."""
    from overlay.battle_end import terminal_row
    assert timeline["sourceSha256"] == capture["framesSha256"], "timeline belongs to different frames"
    row = terminal_row(timeline["rows"])
    hp = {o: sum(u["hp"] for u in row["sides"][o]) for o in ("2", "3")}
    living = [int(o) for o in hp if hp[o] > 0]
    winner = living[0] if len(living) == 1 else None
    assert winner == capture.get("winnerOwner"), "terminal winner differs; review the recorded battle"
    if winner is None:
        return capture
    remaining = hp[str(winner)]
    percent = remaining / capture["winnerStartingHp"] * 100
    return {**capture, "winnerHp": remaining, "winnerRemainingHpPercent": percent,
            "signedRemainingHpPercent": percent if winner == 2 else -percent,
            "hpSource": "terminal per-unit gRPC state", "terminalVideoSeconds": row["videoSeconds"]}


def capture_with_terminal_hp(job_id, capture):
    path = LAB / "runs" / job_id / "live/run_001/unit-hp-overlay/units.json"
    if not path.exists():
        return {**capture, "hpSource": "recorder summary; overlay timeline not yet available"}
    stat = path.stat()
    fingerprint = {"framesSha256": capture["framesSha256"], "timelineBytes": stat.st_size,
                   "timelineModifiedNs": stat.st_mtime_ns}
    cache_path = REPORT / "terminal-hp" / (job_id + ".json")
    cached = read_json(cache_path) if cache_path.exists() else {}
    if cached.get("fingerprint") == fingerprint:
        return {**capture, **cached["terminal"]}
    result = terminal_hp_outcome(capture, read_json(path))
    terminal = {key: result[key] for key in ("winnerHp", "winnerRemainingHpPercent", "signedRemainingHpPercent", "hpSource", "terminalVideoSeconds") if key in result}
    write_json(cache_path, {"fingerprint": fingerprint, "terminal": terminal,
                            "recorderSummaryWinnerHp": capture.get("winnerHp")})
    return result


def compare():
    baseline = read_json(BASELINE)
    status_path = REPORT / "status.json"
    status = read_json(status_path) if status_path.exists() else {"results": []}
    verified = {r["jobId"] for r in status["results"] if r["status"] == "verified"}
    rows = []
    for entry in baseline["entries"]:
        if entry["mode"] == "recapture" and entry["jobId"] not in verified:
            continue
        new = capture_with_terminal_hp(entry["jobId"], read_json(LAB / "runs" / entry["jobId"] / "live/run_001/manifest.json")["capture"])
        old = capture_with_terminal_hp(entry["baselineJobId"], entry["baselineCapture"])
        original = read_json(LAB / "runs" / entry["originalJobId"] / "live/run_001/manifest.json")["capture"] if entry["originalJobId"] != entry["baselineJobId"] else old
        assert new["startCounts"] == old["startCounts"]
        assert new["gameVersion"] == old["gameVersion"], "game version differs; comparison needs review"
        label = lambda c: "Blackwood win" if c.get("winnerOwner") == 2 else "Blackwood loss" if c.get("winnerOwner") == 3 else c.get("outcome", "unknown")
        rows.append({k: entry[k] for k in ("unit", "civ", "mode", "family", "mainCounts", "oldHussars", "newHussars", "originalJobId", "baselineJobId", "jobId")} |
                    {"oldResult": label(old), "newResult": label(new), "winnerChanged": old.get("winnerOwner") != new.get("winnerOwner"),
                     "oldWinnerHp": old.get("winnerHp"), "newWinnerHp": new.get("winnerHp"),
                     "oldWinnerHpPercent": old.get("winnerRemainingHpPercent"), "newWinnerHpPercent": new.get("winnerRemainingHpPercent"),
                     "oldHpSource": old.get("hpSource"), "newHpSource": new.get("hpSource"),
                     "oldSignedHpPercent": old.get("signedRemainingHpPercent"), "newSignedHpPercent": new.get("signedRemainingHpPercent"),
                     "oldFramesSha256": old["framesSha256"], "newFramesSha256": new["framesSha256"],
                     "originalVideoResult": label(original), "originalVideoCounts": original["startCounts"],
                     "originalVideoWinnerHpPercent": original.get("winnerRemainingHpPercent"),
                     "originalVideoWinnerChanged": original.get("winnerOwner") != new.get("winnerOwner"),
                     "priorCostCorrectionChangedWinner": original.get("winnerOwner") != old.get("winnerOwner")})
    flips = [r for r in rows if r["winnerChanged"]]
    original_flips = [r for r in rows if r["originalVideoWinnerChanged"]]
    result = {"state": "COMPLETE" if len(rows) == 73 else "IN_PROGRESS", "updatedAt": utc_now(),
              "completedRetakes": sum(r["mode"] == "recapture" for r in rows), "totalRetakes": 40,
              "reusedRanged": 33, "winnerFlips": len(flips), "originalVideoWinnerFlips": len(original_flips),
              "priorCostCorrectionWinnerFlips": sum(r["priorCostCorrectionChangedWinner"] for r in rows), "rows": rows}
    write_json(REPORT / "winner-comparison.json", result)
    lines = ["# Elite Blackwood Archer: five-Hussar experiment", "",
             f"{result['completedRetakes']}/40 new melee recordings; 33 ranged recordings reused. {len(flips)} observed winner flips.", "",
             "The baseline has nine Spanish Hussars. This version has five. Main army costs/counts and Golden runtime are unchanged. "
             "Cost-corrected captures replace six original chapters before comparison. These are single recorded battles per condition; "
             "combat variation can contribute to outcome changes. HP excludes the Hussar screen. "
             "Where available, terminal per-unit gRPC HP includes the last pending damage ticks beyond the recorder summary.", "",
             "## Five-Hussar winner flips with matching main counts", "", "| Civilization | Opponent | Main counts | Nine-Hussar baseline | Five-Hussar result | New winner HP |",
             "|---|---|---|---|---|---:|"]
    lines.extend(f"| {r['civ']} | {r['unit']} | {r['mainCounts'][0]} vs {r['mainCounts'][1]} | {r['oldResult']} | {r['newResult']} | {r['newWinnerHp']:.0f} ({r['newWinnerHpPercent']:.1f}%) |" for r in flips)
    if not flips:
        lines.append("| No observed flips among completed captures | | | | | |")
    lines += ["", "## Changes versus the originally compiled video", "",
              f"{len(original_flips)} chapters have a different winner from the original full video. "
              "The ranged Chakram Thrower, War Wagon, and Plumed Archer changes already occurred in the earlier cost-correction captures; "
              "they are reused here and must not be attributed to reducing the Hussars.", "",
              "| Civilization | Opponent | Original video | Corrected nine-Hussar baseline | This version | Why included |",
              "|---|---|---|---|---|---|"]
    for r in original_flips:
        reason = "Earlier cost correction; ranged recording reused" if r["mode"] == "reuse" else "New five-Hussar capture"
        lines.append(f"| {r['civ']} | {r['unit']} | {r['originalVideoResult']} | {r['oldResult']} | {r['newResult']} | {reason} |")
    lines += ["", "## All chapters", "", "| Civilization | Opponent | Source | Corrected baseline | Current | Baseline HP % | Current HP % |", "|---|---|---|---|---|---:|---:|"]
    lines.extend(f"| {r['civ']} | {r['unit']} | {r['mode']} | {r['oldResult']} | {r['newResult']} | {r['oldWinnerHpPercent']:.1f} | {r['newWinnerHpPercent']:.1f} |" for r in rows)
    (REPORT / "winner-comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "capture", "compare"))
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "capture":
        capture(args.pilot)
    else:
        compare()
