"""Incremental verified archive for this campaign only; prune redundant local media.

Only new champi_geometric_* jobs listed as verified may be moved. Canonical old
archives and all small capture evidence are retained. Every deletion is a single
resolved path under that job, after the compact replacement passes its checksum.
"""

import shutil
from pathlib import Path
from compact_recording_archive import prepare, digest
from report_champi_geometric import ROOT, OUT, read, save

DEST = Path("D:/AoE2 Renders")
RUNS = (ROOT / "aoe2x/js_simulation/calibration/lab/runs").resolve()
JOB_PREFIX = "champi_geometric_"
ARCHIVE_PREFIX = "champi-geometric"
CIVS = ("incas", "mapuche", "muisca", "tupi")
TITLE_PREFIX = "Champi Geometric"
PRESERVE_BASELINE = True


def main():
    import msvcrt

    # A manual maintenance call and the capture worker must not update one
    # archive index concurrently. Windows releases this lock if the process dies.
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "archive.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            archive_verified()
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def archive_verified():
    if not DEST.is_dir():
        raise RuntimeError("External archive disconnected; sources retained")
    status = read(OUT / "capture/status.json")
    receipt_path = OUT / "archive-status.json"
    state = (
        read(receipt_path)
        if receipt_path.exists()
        else dict(completed={}, deletedBytes=0)
    )
    allowed = {r["id"] for r in read(OUT / "manifest.json")["matchups"]}
    for result in status["results"]:
        job = result["jobId"]
        if (
            result["status"] != "verified"
            or state["completed"].get(job, {}).get("phase") == "complete"
        ):
            continue
        if job not in allowed or not job.startswith(JOB_PREFIX):
            raise ValueError("Foreign archive job")
        source = Path(result["runDirectory"]).resolve()
        expected = (RUNS / job / "live/run_001").resolve()
        if source != expected or not source.is_relative_to(RUNS):
            raise ValueError("Escaped capture source")
        pending = state["completed"].get(job)
        if pending:
            recovery_index = Path(pending["index"]).resolve()
            if recovery_index not in {
                (DEST / f"{ARCHIVE_PREFIX}-{civ}" / "run.json").resolve()
                for civ in CIVS
            }:
                raise ValueError("Escaped archive recovery index")
            saved_index = read(recovery_index)
            row = next(r for r in saved_index["matchups"] if r["jobId"] == job)
        else:
            row = prepare(source)
        if row["jobId"] != job:
            raise ValueError("Bundle job mismatch")
        civ = row["plan"]["side2"]["civ"].lower()
        if civ not in CIVS:
            raise ValueError("Unexpected civilization")
        destination = (DEST / f"{ARCHIVE_PREFIX}-{civ}").resolve()
        if destination.parent != DEST.resolve():
            raise ValueError("Escaped archive destination")
        destination.mkdir(parents=True, exist_ok=True)
        index_path = destination / "run.json"
        index = (
            read(index_path)
            if index_path.exists()
            else dict(
                schemaVersion=1,
                kind="aoe2lab.compact-archive",
                title=f"{TITLE_PREFIX} {civ.title()}",
                matchups=[],
                finalVideo=None,
            )
        )
        if index["title"] != f"{TITLE_PREFIX} {civ.title()}":
            raise ValueError("Archive variant conflict")
        if any(
            r["jobId"] != job and r["name"].casefold() == row["name"].casefold()
            for r in index["matchups"]
        ):
            raise ValueError("Another job already owns this archive filename")
        need = sum(f["bytes"] for f in row["files"].values())
        if shutil.disk_usage(destination).free < need + 2 * 2**30:
            raise RuntimeError("Archive reserve reached; sources retained")
        for f in row["files"].values():
            if not Path(f["source"]).resolve().is_relative_to(source):
                raise ValueError("Escaped archive input")
            target = (destination / f["path"]).resolve()
            if target.parent != destination:
                raise ValueError("Escaped archive file")
            if not target.exists():
                partial = target.with_suffix(target.suffix + ".partial")
                shutil.copyfile(f["source"], partial)
                if (
                    partial.stat().st_size != f["bytes"]
                    or digest(partial) != f["sha256"]
                ):
                    raise ValueError("Copy checksum failure")
                partial.replace(target)
            if target.stat().st_size != f["bytes"] or digest(target) != f["sha256"]:
                raise ValueError("Archive conflict")
        prior = next((r for r in index["matchups"] if r["jobId"] == job), None)
        if prior and prior != row:
            raise ValueError("Existing job provenance differs")
        if not prior:
            index["matchups"].append(row)
        save(index_path, index)
        # Preserve the frozen baseline beside each new campaign for comparison.
        baseline_target = destination / "baseline.json"
        if PRESERVE_BASELINE and not baseline_target.exists():
            baseline_partial = destination / "baseline.partial.json"
            shutil.copyfile(OUT / "baseline.json", baseline_partial)
            if digest(baseline_partial) != digest(OUT / "baseline.json"):
                raise ValueError("Baseline copy checksum failure")
            baseline_partial.replace(baseline_target)
        if PRESERVE_BASELINE and digest(baseline_target) != digest(OUT / "baseline.json"):
            raise ValueError("Baseline archive conflict")
        # Verify all disposable inputs before deleting any; no recursive removal.
        disposable = {}
        for entry in row["files"].values():
            disposable[entry["source"]] = entry
        original = row["recording"]["files"]["video"]
        original_path = (source / original["path"]).resolve()
        disposable[str(original_path)] = {**original, "source": str(original_path)}
        for text, entry in disposable.items():
            path = Path(text).resolve()
            if not path.is_relative_to(source) or path.suffix not in (
                ".mp4",
                ".mov",
                ".bin",
            ):
                raise ValueError("Unsafe disposable input")
            if path.exists() and (
                path.stat().st_size != entry["bytes"] or digest(path) != entry["sha256"]
            ):
                raise ValueError("Source changed; retain media")
        save(
            source / "archived.json",
            dict(
                jobId=job,
                index=str(index_path),
                adapter="apps/video/materialize_compact_recording.py",
            ),
        )
        state["completed"][job] = dict(index=str(index_path), phase="copied_verified")
        save(receipt_path, state)
        deleted = 0
        for text in disposable:
            path = Path(text).resolve()
            if path.exists():
                deleted += path.stat().st_size
                path.unlink()
        state["completed"][job] = dict(
            index=str(index_path), phase="complete", deletedBytes=deleted
        )
        state["deletedBytes"] += deleted
        save(receipt_path, state)
    print(f"Archived {len(state['completed'])} new captures", flush=True)


if __name__ == "__main__":
    main()
