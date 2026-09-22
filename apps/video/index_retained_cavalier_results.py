"""Recover recorded results without recapturing or claiming missing media exists.

The retained source jobs contain the original plans and capture manifests even
when their compact MP4/frame archives are on another disk. Build local, explicitly
metadata-only indexes for ranking. This never writes to the source disk or changes
outcomes, count policies, or the recorded four-relic Leitis selection.
"""
import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CIVILIZATIONS = ("poles", "burmese", "sicilians")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def retained_row(job, civ):
    live = job / "live/run_001"
    paths = {"plan": job / "plan.json", "capture": live / "manifest.json",
             "recording": live / "recording.json"}
    data = {key: read(path) for key, path in paths.items()}
    plan, capture, recording = (data[key] for key in paths)
    if plan["jobId"] != job.name or recording["jobId"] != job.name:
        raise ValueError(f"Cross-job metadata: {job}")
    if plan["side2"]["civ"].lower() != civ:
        raise ValueError(f"Unexpected civilization: {job}")
    if capture["capture"]["startCounts"] != [plan[s]["count"] for s in ("side2", "side3")]:
        raise ValueError(f"Captured counts differ from the saved plan: {job}")
    if plan["side3"]["slug"] == "elite_leitis_lithuanians":
        if plan["scenario"].get("opponentLithuanianRelics") != 4:
            raise ValueError(f"Use the existing four-relic Leitis correction: {job}")
    expected = {}
    for key in ("battleVideo", "frames"):
        entry = recording["files"][key]
        path = live / entry["path"]
        expected[key] = dict(entry, sourcePath=str(path),
                             presentWithExpectedSize=path.is_file() and path.stat().st_size == entry["bytes"])
    return dict(jobId=job.name, plan=plan, capture=capture,
                sourceKind="retained_capture_metadata", metadataOnly=True,
                expectedMedia=expected, sourceMetadata={key: dict(
                    path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                    for key, path in paths.items()})


def build(source, output):
    # Refuse overwrite: an existing index may be evidence for a published report.
    destinations = [output / f"knight-reused-cavalier-{civ}" / "run.json" for civ in CIVILIZATIONS]
    if any(path.exists() for path in destinations):
        raise FileExistsError("Result indexes already exist; choose a new local output directory")
    indexes = []
    for civ, destination in zip(CIVILIZATIONS, destinations):
        jobs = sorted(p for p in source.glob(f"cavalier_{civ}_unique_*") if p.is_dir())
        rows = [retained_row(job, civ) for job in jobs]
        if len(rows) != 74 or len({r["plan"]["side3"]["slug"] for r in rows}) != 74:
            raise ValueError(f"Expected exactly 74 distinct retained opponents for {civ}")
        indexes.append((destination, dict(schemaVersion=1,
            kind="aoe2lab.retained-result-index", metadataOnly=True,
            sourceRoot=str(source.resolve()),
            limitation="Recorded result metadata is available; this index does not establish that compact battle videos or frames are available for replay.",
            matchups=rows)))
    for destination, index in indexes:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(dict(index=str(destination), results=len(index["matchups"]), metadataOnly=True)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Read-only retained-source-versions directory")
    parser.add_argument("--output", type=Path, default=REPO / "data/local/knight-reused-indexes")
    args = parser.parse_args()
    build(args.source, args.output)
