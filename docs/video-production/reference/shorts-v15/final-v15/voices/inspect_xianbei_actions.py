"""Decode every component of Xianbei Raider's multi-action command event."""

import importlib.util
import json
import struct
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("voice_catalog", HERE / "build_catalog.py")
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)
entries = catalog.read_json(catalog.OBJECTS_PATH)
event_id = 13823237
event = bytes.fromhex(entries[str(event_id)]["data"])
action_ids = struct.unpack_from(f"<{event[0]}I", event, 1)
records = []
for action_index, action_id in enumerate(action_ids):
    action = bytes.fromhex(entries[str(action_id)]["data"])
    target_id = struct.unpack_from("<I", action, 2)[0]
    sound_ids = catalog.random_sounds(entries, target_id)
    for variant, sound_id in enumerate(sound_ids):
        sound = bytes.fromhex(entries[str(sound_id)]["data"])
        media_id = struct.unpack_from("<I", sound, 5)[0]
        stem = f"xianbei-action{action_index}-v{variant}"
        wem = HERE / f"{stem}.wem"
        wav = HERE / f"{stem}.wav"
        if not wav.exists():
            catalog.extract(catalog.PACKAGE, media_id, wem)
            subprocess.run(
                [str(catalog.DECODER), "-i", "-o", str(wav), str(wem)],
                check=True,
                capture_output=True,
            )
        records.append(
            {
                "eventId": event_id,
                "actionIndex": action_index,
                "actionId": action_id,
                "containerId": target_id,
                "soundId": sound_id,
                "mediaId": media_id,
                "variant": variant,
                "variantCount": len(sound_ids),
                "wav": str(wav.resolve()),
                **catalog.measure_wav(wav),
            }
        )
(HERE / "xianbei-actions.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
for record in records:
    print(
        record["actionIndex"], record["variant"], record["durationSeconds"],
        record["audibleOnsetSeconds"], record["soundId"], record["mediaId"],
    )
