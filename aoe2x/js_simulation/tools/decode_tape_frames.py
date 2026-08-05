"""Decode a golden-basics `.frames.bin` into a full-rate per-frame per-unit
state trace (position, HP, entity state, action type/state/target/target_xy/
timer).

The 10 Hz `decoded/*.units.jsonl.gz` in the same archive throws away exactly
the fields that matter for calibration: what each unit was DOING, who it was
targeting, and where it was steering. The raw gRPC dump keeps all of it at the
render cadence (~59.7 Hz).

Read-only against the authorized archive; writes only into the output dir.

    python decode_tape_frames.py --archive <zip> --unit-master 567 1v1 2v1
"""
import argparse
import json
import os
import struct
import sys
import zipfile

GRPC_DIR = r"D:\AI\aoe2_matchup\aoe2x\grpc"
sys.path.insert(0, GRPC_DIR)

# Local protobuf runtime is 6.33.4, the checked-in gencode says 6.33.5. The
# generated descriptor itself is unchanged by that patch bump; skip the guard.
from google.protobuf import runtime_version as _rtv  # noqa: E402
_rtv.ValidateProtobufRuntimeVersion = lambda *a, **k: None
import decode_state_v2 as D  # noqa: E402
import cade_api_pb2 as pb    # noqa: E402

SNAP_RESEED = 400_000

F_ID, F_MASTER, F_OWNER, F_X, F_Y = 0, 1, 2, 3, 4
F_STATE, F_TYPE, F_HP, F_UNDER_ATTACK, F_FACET = 8, 11, 12, 13, 16
F_CUR_ACTION = 20            # ActionEntity.current_action -> Ref(Action)
A_TYPE, A_STATE, A_TARGET, A_TARGET2 = 0, 1, 2, 3
A_TX, A_TY, A_TIMER = 4, 5, 12
ARMY_MT = {9, 11, 12}


def archive_layout(archive):
    """Locate the `raw recordings/` prefix and the per-fight tag stem."""
    with zipfile.ZipFile(archive) as z:
        raw = [n for n in z.namelist() if n.endswith(".frames.bin")]
    if not raw:
        raise SystemExit(f"{archive} contains no .frames.bin")
    head, _, _ = raw[0].rpartition("/")
    stems = sorted(
        os.path.basename(n)[: -len(".frames.bin")] for n in raw
    )
    # Every fight in a basics archive shares one `<pair>__` stem prefix.
    prefix = os.path.commonprefix(stems)
    return f"{head}/", prefix


def frames_path(archive, base, prefix, tag, out_dir):
    dest = os.path.join(out_dir, f"{tag}.frames.bin")
    if not os.path.exists(dest):
        with zipfile.ZipFile(archive) as z, open(dest, "wb") as out:
            out.write(z.read(f"{base}{prefix}{tag}.frames.bin"))
    return dest


def action_of(doc, entity):
    ref = entity.get(F_CUR_ACTION)
    if not isinstance(ref, int):
        return None
    model = doc.models.get(ref)
    if not model:
        return None
    return {
        "action_model_type": model.get("__type__"),
        "action_type": model.get(A_TYPE),
        "action_state": model.get(A_STATE),
        "target_id": model.get(A_TARGET),
        "target_2_id": model.get(A_TARGET2),
        "target_x": model.get(A_TX),
        "target_y": model.get(A_TY),
        "timer": model.get(A_TIMER),
    }


def decode(archive, base, prefix, tag, masters, out_dir):
    path = frames_path(archive, base, prefix, tag, out_dir)
    doc = es = world_id = None
    rows = []
    kills = []
    seen_masters = set()
    seed_path = os.path.join(out_dir, f"{tag}.reseed.bin")
    frame_count = 0

    with open(path, "rb") as f:
        while True:
            hdr = f.read(4)
            if len(hdr) < 4:
                break
            (ln,) = struct.unpack("<I", hdr)
            buf = f.read(ln)
            if len(buf) < ln:
                break
            sq = pb.FrameSequence()
            sq.ParseFromString(buf)
            for fr in sq.frame:
                patch = fr.patch
                if patch and len(patch) > SNAP_RESEED:
                    with open(seed_path, "wb") as s:
                        s.write(patch)
                    doc = D.Doc()
                    es = {}
                    _, world_id = D.seed_from_snapshot(seed_path, doc, es)
                    continue
                if es is None:
                    continue
                if patch:
                    D.apply_patch(doc, patch, es, world_id)
                for ev in fr.event:
                    if ev.HasField("entityKilled"):
                        kills.append({
                            "t_ms": fr.time,
                            "id": ev.entityKilled.id,
                            "killer_id": ev.entityKilled.killerId,
                        })
                frame_count += 1
                # entity_store only mirrors scalar assigns (op 2); model-ref
                # fields such as current_action live in the Doc itself.
                world_entities = doc.models.get(world_id, {}).get(1, {})
                for key, ent in es.items():
                    if ent.get("__type__") not in ARMY_MT:
                        continue
                    master = ent.get(F_MASTER)
                    if ent.get(F_OWNER) not in (2, 3):
                        continue
                    seen_masters.add(master)
                    if masters and master not in masters:
                        continue
                    doc_id = world_entities.get(key)
                    if isinstance(doc_id, int) and doc_id in doc.models:
                        ent = {**doc.models[doc_id], **ent}
                    row = {
                        "t_ms": fr.time,
                        "key": key,
                        "id": ent.get(F_ID),
                        "master": master,
                        "owner": ent.get(F_OWNER),
                        "x": ent.get(F_X),
                        "y": ent.get(F_Y),
                        "hp": ent.get(F_HP),
                        "state": ent.get(F_STATE),
                        "under_attack": ent.get(F_UNDER_ATTACK),
                        "facet": ent.get(F_FACET),
                    }
                    act = action_of(doc, ent)
                    if act:
                        row.update(act)
                    rows.append(row)

    out_path = os.path.join(out_dir, f"{tag}.tape_trace.jsonl")
    with open(out_path, "w", encoding="utf8") as out:
        for row in rows:
            out.write(json.dumps(row) + "\n")
    meta = {
        "tag": tag,
        "frames": frame_count,
        "rows": len(rows),
        "masters_seen": sorted(m for m in seen_masters if m is not None),
        "kills": kills,
        "t_ms_min": min((r["t_ms"] for r in rows), default=None),
        "t_ms_max": max((r["t_ms"] for r in rows), default=None),
    }
    with open(os.path.join(out_dir, f"{tag}.tape_trace.meta.json"), "w") as out:
        json.dump(meta, out, indent=1)
    return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True,
                        help="golden-basics .zip holding `raw recordings/`")
    parser.add_argument("--unit-master", type=int, action="append", default=[],
                        help="keep only these unit masters (repeatable)")
    parser.add_argument("--out-dir", default=os.path.dirname(
        os.path.abspath(__file__)))
    parser.add_argument("tags", nargs="+", help="fight tags, e.g. 1v1 1v1_r2")
    args = parser.parse_args()

    base, prefix = archive_layout(args.archive)
    os.makedirs(args.out_dir, exist_ok=True)
    for tag in args.tags:
        meta = decode(args.archive, base, prefix, tag,
                      set(args.unit_master), args.out_dir)
        print(json.dumps({k: v for k, v in meta.items() if k != "kills"}))


if __name__ == "__main__":
    main()
