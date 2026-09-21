"""Resume the four standard Champi campaigns without rendering or publishing."""

import json
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from capture_storage_guard import archive_storage_error

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/local/champi-standard-comparison"


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(".tmp.json")
    temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temp.replace(p)


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.work.resolve()
    from aoe2x.lab.recording_campaign import checkpoint

    os.chdir(ROOT)
    manifest = read(OUT / "manifest.json")
    guard_path = OUT / 'archive-guard.json'
    archive_guard = read(guard_path) if guard_path.exists() else None
    allowed_jobs = {row['id'] for row in manifest['matchups']}
    report = OUT / "capture"
    previous = read(report / "status.json") if (report / "status.json").exists() else {}
    verified = {
        r["jobId"]: r for r in previous.get("results", [])
        if r["status"] == "verified" and r['jobId'] in allowed_jobs
    }
    for path in report.glob("pass-*/status.json"):
        for row in read(path).get("results", []):
            if row["status"] == "verified" and row['jobId'] in allowed_jobs:
                verified[row["jobId"]] = row
    pending = [r for r in manifest["matchups"] if r["id"] not in verified]
    if not pending:
        print(f"All {len(manifest['matchups'])} captures are verified", flush=True)
        return
    if (OUT / "PAUSE").exists() or (ROOT / "data/local/thermal/PAUSED.json").exists():
        raise RuntimeError("User or thermal pause must be resolved before starting")
    storage_error = archive_storage_error(archive_guard)
    if storage_error:
        raise RuntimeError(storage_error)
    if shutil.disk_usage(ROOT).free < 8 * 2**30:
        raise RuntimeError("Less than 8 GiB free; archive completed packages first")
    active = report / f"pass-{int(time.time())}"
    save(active / "pending.json", dict(schemaVersion=1, matchups=pending))
    child = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-m",
            "aoe2x.lab.recording_campaign",
            str(active / "pending.json"),
            "--reports",
            str(active),
        ],
        cwd=ROOT,
    )
    save(
        OUT / "worker.json",
        dict(
            pid=os.getpid(),
            childPid=child.pid,
            activeReport=str(active),
            startedAt=time.time(),
            total=len(manifest["matchups"]),
        ),
    )
    last_thermal = 0
    last_maintenance = 0
    while True:
        code = child.poll()
        if time.time() - last_thermal >= 900:
            subprocess.run(
                [sys.executable, str(ROOT / "apps/video/thermal_guard.py")], check=True
            )
            last_thermal = time.time()
        if (
            (OUT / "PAUSE").exists()
            or shutil.disk_usage(ROOT).free < 8 * 2**30
            or (ROOT / "data/local/thermal/PAUSED.json").exists()
            or archive_storage_error(archive_guard)
        ):
            (active / "STOP").touch()
        if (active / "status.json").exists():
            state = read(active / "status.json")
            state["results"] = list(verified.values()) + state.get("results", [])
            state["total"] = len(manifest["matchups"])
            state["manifest"] = str(OUT / "manifest.json")
            checkpoint(report, state, report=code is not None)
            maintenance = {
                "champi-geometric-comparison": ("report_champi_geometric.py", "archive_champi_geometric.py"),
                "paladin-line-comparison": ("archive_paladin_comparison.py",),
                "cavalier-comparison": ("archive_cavalier_comparison.py",),
                "camel-comparison": ("report_camel_comparison.py",),
                "camel-baseline": ("report_camel_baseline.py",),
            }.get(OUT.name, ())
            if maintenance and (
                code is not None or time.time() - last_maintenance >= 60
            ):
                for script in maintenance:
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "apps/video" / script)], cwd=ROOT
                    )
                    if result.returncode:
                        print(
                            f"Maintenance failed: {script}; captures remain recoverable",
                            flush=True,
                        )
                last_maintenance = time.time()
        if code is not None:
            sys.exit(code)
        time.sleep(10)


if __name__ == "__main__":
    main()
