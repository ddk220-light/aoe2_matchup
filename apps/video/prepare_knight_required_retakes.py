"""Replace the blanket knight rerun with only verified necessary corrections.

Compare the original manifests' actual frozen counts with the approved v2 plans.
Reuse completed corrections and the eight previously recorded four-relic Leitis
fixes. Freeze a separate subset queue; never edit old plans, delete media, or
touch a connected archive. Run only after the blanket recorder has stopped.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil

from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "data/local/knight-v2-recapture"
WORK = ROOT / "data/local/knight-required-retakes"
COUNT_OPPONENTS = {"elite_karambit_warrior", "elite_blackwood_archer_tupi"}


def different_counts(before, after):
    """A policy-name difference alone is not a reason to recapture a battle."""
    return [before[s]["count"] for s in ("side2", "side3")] != [
        after[s]["count"] for s in ("side2", "side3")]


def main():
    if (WORK / "queue.json").exists():
        raise FileExistsError("Required-retakes queue exists; resume without replanning")
    if not (OLD / "PAUSE").exists():
        raise RuntimeError("Stop the blanket queue at a safe boundary first")
    source_queue = read(OLD / "queue.json")
    originals = {}
    for directory in ("paladin-line-comparison", "cavalier-comparison"):
        base = ROOT / "data/local" / directory
        for request in read(base / "manifest.json")["matchups"]:
            path = base / "plans" / (request["id"] + ".json")
            plan = read(path)
            key = (plan["side2"]["civ"], plan["side3"]["slug"])
            if key in originals:
                raise ValueError(f"Duplicate original matchup: {key}")
            originals[key] = (plan, path)

    queue, audit = [], []

    def freeze_subset(campaign, requests, archive_prefix=None):
        source = Path(campaign["workDirectory"])
        destination = WORK / campaign["key"]
        if destination.exists():
            raise FileExistsError(destination)
        destination.mkdir(parents=True)
        for name in ("subject-stats.json", "archive-guard.json"):
            shutil.copyfile(source / name, destination / name)
        shutil.copytree(source / "frozen-catalogs", destination / "frozen-catalogs")
        (destination / "plans").mkdir()
        fingerprints = {}
        for request in requests:
            name = request["id"] + ".json"
            data = (source / "plans" / name).read_bytes()
            (destination / "plans" / name).write_bytes(data)
            fingerprints[request["id"]] = hashlib.sha256(data).hexdigest()
        save(destination / "manifest.json", dict(schemaVersion=1, matchups=requests))
        save(destination / "pilot.json", dict(schemaVersion=1, matchups=requests[:1]))
        save(destination / "pilot-phase/archive-guard.json", read(source / "archive-guard.json"))
        save(destination / "preflight.json", dict(
            state="PASSED", total=len(requests), frozenPlanSha256=fingerprints,
            sourceCampaign=str(source), selection="Only missing necessary corrections"))
        selected = copy.deepcopy(campaign)
        selected.update(workDirectory=str(destination), total=len(requests))
        if archive_prefix:
            selected["archivePrefix"] = archive_prefix
        queue.append(selected)

    changed_total, unchanged_total, already_done = 0, 0, 0
    for campaign in source_queue["campaigns"][:8]:
        source = Path(campaign["workDirectory"])
        state = read(source / "capture/status.json") if (source / "capture/status.json").exists() else {}
        if state.get("currentJob") or state.get("pendingExports"):
            raise RuntimeError(f"Recording/export still active: {source}")
        verified = {r["jobId"]: r for r in state.get("results", []) if r["status"] == "verified"}
        requests = []
        for request in read(source / "manifest.json")["matchups"]:
            plan = read(source / "plans" / (request["id"] + ".json"))
            key = (plan["side2"]["civ"], plan["side3"]["slug"])
            before, original_path = originals[key]
            changed = different_counts(before, plan)
            record = dict(civilization=key[0], opponent=key[1],
                          oldPlan=str(original_path), newJobId=plan["jobId"],
                          oldCounts=[before[s]["count"] for s in ("side2", "side3")],
                          newCounts=[plan[s]["count"] for s in ("side2", "side3")],
                          countsChanged=changed)
            if not changed:
                unchanged_total += 1
                record["action"] = "reuse_existing"
            else:
                changed_total += 1
                if key[1] not in COUNT_OPPONENTS:
                    raise ValueError(f"Unexpected count correction: {key}")
                if request["id"] in verified:
                    # Verify the completed replacement's actual archived counts
                    # and both media files before excluding it from new work.
                    index_path = Path(source_queue["archiveRoot"]) / (
                        campaign["archivePrefix"] + "-" + key[0].lower()) / "run.json"
                    row = next(r for r in read(index_path)["matchups"] if r["jobId"] == request["id"])
                    if row["capture"]["capture"]["startCounts"] != record["newCounts"]:
                        raise ValueError(f"Archived count mismatch: {request['id']}")
                    for media in ("battle.mp4", "frames.bin"):
                        entry = row["files"][media]
                        path = index_path.parent / entry["path"]
                        if not path.is_file() or path.stat().st_size != entry["bytes"]:
                            raise ValueError(f"Missing completed correction: {path}")
                    already_done += 1
                    record["action"] = "reuse_completed_correction"
                else:
                    requests.append(request)
                    record["action"] = "capture_required"
            audit.append(record)
        if requests:
            freeze_subset(campaign, requests, "knight-count-fix-cavalier")

    # The original eight already have verified +4 Leitis correction receipts.
    # They must not be confused with the nine newer expansion variants.
    reused_leitis = []
    for directory in ("paladin-leitis-four-relics", "cavalier-leitis-four-relics"):
        base = ROOT / "data/local" / directory
        state = read(base / "capture/status.json")
        receipts = read(base / "archive-status.json")["completed"]
        for result in state["results"]:
            if result["status"] != "verified" or receipts[result["jobId"]]["phase"] != "complete":
                raise ValueError("Existing Leitis correction has not passed capture/archive verification")
            plan = read(base / "plans" / (result["jobId"] + ".json"))
            if plan["scenario"].get("opponentLithuanianRelics") != 4:
                raise ValueError("Existing Leitis correction does not have four relics")
            reused_leitis.append(dict(jobId=result["jobId"], archive=receipts[result["jobId"]]["index"]))

    corrections = source_queue["campaigns"][8]
    source = Path(corrections["workDirectory"])
    rows = read(source / "manifest.json")["matchups"]
    if len(rows) != 9 or any((Path(source_queue["archiveRoot"]) / (
            corrections["archivePrefix"] + "-" + r["civ2"].lower()) / "run.json").exists() for r in rows):
        raise ValueError("Leitis correction availability changed; audit before recapturing")
    freeze_subset(corrections, rows)
    if (changed_total, unchanged_total, already_done, len(reused_leitis)) != (16, 575, 10, 8):
        raise ValueError("Audit differs from the reviewed minimal-retake scope")
    total = sum(c["total"] for c in queue)
    if total != 15:
        raise ValueError("Only the six remaining count fixes and nine Leitis fixes are authorized here")
    save(WORK / "audit.json", dict(
        countChanges=changed_total, countsUnchanged=unchanged_total,
        completedCountCorrections=already_done, remainingCountCorrections=6,
        expansionLeitisCorrections=9, totalRemaining=total,
        reusedOriginalLeitis=reused_leitis, comparisons=audit,
        originalArchiveAvailability="Older external disk required for final source-file verification; do not replace inaccessible originals with new captures"))
    save(WORK / "queue.json", dict(
        state="READY", total=total, captureOnly=True, campaigns=queue,
        archiveRoot=source_queue["archiveRoot"], archiveGuard=source_queue["archiveGuard"],
        authorization="User stopped blanket reruns and authorized only verified necessary retakes",
        supersedes=str(OLD), preserveOriginals=True))
    save(OLD / "SUPERSEDED.json", dict(
        replacement=str(WORK), reason="575 of 591 original army counts are unchanged; do not resume blanket reruns"))
    print(json.dumps(dict(countChanges=16, unchanged=575, alreadyCorrected=10,
                          remaining=15, queue=str(WORK / "queue.json")), indent=2))


if __name__ == "__main__":
    main()
