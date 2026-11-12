"""Compare independently measured game balances with modeled activity vectors.

Measurements are evidence only. This module never changes a model parameter.
"""
import hashlib
import json
import math
from pathlib import Path

RESOURCES = ("food", "wood", "gold", "stone")


def model_key(activity):
    value = {k: activity[k] for k in ("scenarioSignature", "outputs")}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_observations(civilizations, manifest, source_hash, calibration_root, *, require_measurements=True):
    """Require matched source/layout and traceable captures for every vector.

    resourceDeltas include banked + carried resources and subtract recurring
    inputs. villagerSeconds is measured active worker count integrated over the
    same window, including walking and drop-off time. Multiple windows sum.
    """
    required = {}
    for civ, economy in civilizations.items():
        for activity in economy["activities"]:
            key = model_key(activity)
            record = required.setdefault(key, {"modelKey": key, "scenarioSignature": activity["scenarioSignature"],
                                                "outputs": activity["outputs"], "civilizations": []})
            record["civilizations"].append(civ)
    report = {"targetRelativeError": .01, "requiredForRelease": require_measurements,
              "required": list(required.values()), "comparisons": [], "blockers": []}
    if manifest is None:
        report["status"] = "pending" if require_measurements else "deferred_by_user"
        if require_measurements:
            report["blockers"].append({"code": "controlled_observations_missing",
                "detail": f"Matched controlled captures are required for {len(required)} distinct gathering activity vectors; target error <1%."})
        return report
    doc = json.loads(Path(manifest).read_text())
    if doc.get("sourceSha256") != source_hash:
        raise ValueError("observation manifest must use the same DAT source hash")
    root = Path(calibration_root).resolve()
    totals = {}
    for window in doc.get("windows", []):
        key = window["modelKey"]
        if key not in required:
            raise ValueError(f"unknown gathering model key: {key}")
        capture = (root / window["capturePath"]).resolve()
        if not capture.is_relative_to(root) or not capture.is_file() or capture.name != "frames.bin":
            raise ValueError("controlled observation must reference frames.bin within calibration")
        if not capture.stat().st_size:
            raise ValueError("empty game capture")
        digest = hashlib.sha256(capture.read_bytes()).hexdigest()
        if digest != window["captureSha256"]:
            raise ValueError("controlled game capture hash mismatch")
        seconds = window["villagerSeconds"]
        start, end = window["startGameSecond"], window["endGameSecond"]
        if not all(isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)
                   for v in (seconds, start, end)) or seconds <= 0 or start < 0 or end <= start:
            raise ValueError("invalid observation measurement window")
        value = totals.setdefault(key, {"villagerSeconds": 0, "resources": dict.fromkeys(RESOURCES, 0), "captures": [], "windows": []})
        # A capture window cannot be counted twice, including overlapping ones.
        if any(old[0] == str(capture) and max(old[1], start) < min(old[2], end) for old in value["windows"]):
            raise ValueError("overlapping observation windows")
        value["windows"].append((str(capture), start, end))
        value["villagerSeconds"] += seconds
        for resource in RESOURCES:
            delta = window["resourceDeltas"].get(resource, 0)
            if not isinstance(delta, (float, int)) or isinstance(delta, bool) or not math.isfinite(delta):
                raise ValueError("resource deltas must be finite")
            value["resources"][resource] += delta
        value["captures"].append({"path": str(capture.relative_to(root)), "sha256": digest,
                                  "runNumber": window["runNumber"], "startGameSecond": start, "endGameSecond": end})
    for key, expected in required.items():
        measured = totals.get(key)
        if measured is None:
            report["blockers"].append({"code": "gathering_observation_missing", "modelKey": key,
                                      "detail": ", ".join(expected["civilizations"])})
            continue
        actual = {r: measured["resources"][r] / measured["villagerSeconds"] for r in RESOURCES}
        errors = {r: abs(actual[r] - expected["outputs"].get(r, 0)) / abs(expected["outputs"][r])
                  if abs(expected["outputs"].get(r, 0)) > 1e-10 else (0 if abs(actual[r]) < 1e-10 else None)
                  for r in RESOURCES}
        passed = all(e is not None and e < .01 for e in errors.values())
        report["comparisons"].append({"modelKey": key, "observedOutputs": actual, "relativeErrors": errors,
                                       "passed": passed, "captures": measured["captures"]})
        if not passed:
            report["blockers"].append({"code": "gathering_measurement_mismatch", "modelKey": key,
                                      "detail": "Measured output differs by at least 1%; resolve mechanics, do not fit the output."})
    report["status"] = "validated" if not report["blockers"] else "incomplete_or_failed"
    return report
