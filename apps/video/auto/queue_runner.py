# apps/video/auto/queue_runner.py
"""Run a queue of matchup recordings with resume-skip, per-clip failure
isolation, and a metadata manifest (out_dir/manifest.json) that stitching,
chapters, and recompose read INSTEAD of parsing filenames.

Spec dict: {civ1, slug1, civ2, slug2, name, label, category, why, ...} —
extra keys are preserved into the manifest untouched.
"""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from auto.pure import log

MANIFEST = "manifest.json"


@dataclass
class QueueResult:
    done: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    failed: list = field(default_factory=list)


def _load_manifest(out_dir):
    p = Path(out_dir) / MANIFEST
    if p.exists():
        return json.loads(p.read_text())
    return {"clips": []}


def _save_manifest(out_dir, manifest):
    (Path(out_dir) / MANIFEST).write_text(json.dumps(manifest, indent=1))


def run_matchup_queue(specs, out_dir, *, run_one, on_recover=None):
    """run_one(spec, out_dir) -> Path of finished clip (or raises).
    on_recover() is called after a failure (e.g. return_to_editor)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(out_dir)
    by_name = {c["name"]: c for c in manifest["clips"]}
    result = QueueResult()

    for s in specs:
        entry = by_name.get(s["name"])
        clip_path = out_dir / f"{s['name']}.mp4"
        if entry and entry.get("status") == "done" and clip_path.exists():
            log(f"skip (done): {s['name']}")
            result.skipped.append(s)
            continue
        entry = dict(s)
        try:
            path = run_one(s, out_dir)
            entry.update(status="done", path=str(path), ts=time.time())
            result.done.append(s)
        except Exception as e:                          # noqa: BLE001
            log(f"FAILED {s['name']}: {e}")
            entry.update(status="failed", error=str(e), ts=time.time())
            result.failed.append(s)
            if on_recover:
                try:
                    on_recover()
                except Exception as re:                 # noqa: BLE001
                    log(f"recovery also failed: {re}")
        by_name[s["name"]] = entry
        # rebuild in spec order, keeping clips from older runs (unknown names) first
        known = {s2["name"] for s2 in specs}
        manifest["clips"] = ([c for c in manifest["clips"]
                              if c.get("name") not in known]
                             + [by_name[s2["name"]] for s2 in specs
                                if s2["name"] in by_name])
        _save_manifest(out_dir, manifest)
    return result
