"""Extract same-civilization spoken-event candidates for mounted units."""

import importlib.util
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("voice_catalog", HERE / "build_catalog.py")
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)
current = catalog.read_json(HERE / "catalog.json")
entries = catalog.read_json(catalog.OBJECTS_PATH)
records = []
for source in current["selected"]:
    if source["eventId"] != 3139909899:
        continue
    event_id = 3761709415
    action_id, target_id, switch_container_id, variants = catalog.sound_variants(
        entries, event_id, source["civilization"]
    )
    candidates = []
    for variant, (container_id, sound_id, media_id) in enumerate(variants):
        stem = (
            f"candidate-{source['matchupNumber']:02d}-{source['side']}-"
            f"{source['civilization'].lower()}-spoken-v{variant}"
        )
        wem = HERE / f"{stem}.wem"
        wav = HERE / f"{stem}.wav"
        if not wav.exists():
            catalog.extract(catalog.PACKAGE, media_id, wem)
            subprocess.run(
                [str(catalog.DECODER), "-i", "-o", str(wav), str(wem)],
                check=True,
                capture_output=True,
            )
        candidates.append(
            {
                **{key: source[key] for key in ("matchupNumber", "matchupKey", "side", "unit", "civilization", "unitId")},
                "candidateOnly": True,
                "editorialSubstitution": "same-civilization human spoken attack event; not the mounted unit's DAT event",
                "sourceDatEventId": source["eventId"],
                "eventId": event_id,
                "actionId": action_id,
                "switchGroup": "Civilization",
                "switchId": catalog.fnv1(source["civilization"]),
                "switchContainerId": switch_container_id,
                "eventTargetId": target_id,
                "containerId": container_id,
                "soundId": sound_id,
                "mediaId": media_id,
                "variant": variant,
                "variantCount": len(variants),
                "wav": str(wav.resolve()),
                "rawWav": str(wav.resolve()),
                "wem": str(wem.resolve()),
                "bankId": catalog.BANK_ID,
                "bankObjects": str(catalog.OBJECTS_PATH.resolve()),
                "bankPackage": str(catalog.PACKAGE.resolve()),
                "mediaPackage": str(catalog.PACKAGE.resolve()),
                **catalog.measure_wav(wav),
            }
        )
    records.append(max(candidates, key=lambda record: record["durationSeconds"]))
(HERE / "editorial-candidates.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
for record in records:
    print(record["matchupNumber"], record["unit"], record["civilization"], record["durationSeconds"])
