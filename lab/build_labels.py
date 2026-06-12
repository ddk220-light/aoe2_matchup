"""build_labels.py — Produce trustworthy cumulative ground-truth labels from gRPC capture.

Mission:
  Walk ALL 196k delta frames in a single pass.
  - Op8 CREATE of an Entity (model types 9,11,12,13,14 — EXCLUDE 10 DoppleEntity,
    exclude negative keys): record entity_id -> master_id, owner, first_seen_frame.
  - Op2 ASSIGN on existing entity: update master_id/owner if they change (last-known wins).
  - Op9/Op12 REMOVE (death): mark dead=True but KEEP in cumulative label set.
  - Also seed initial entities from first_patch_seg2.bin snapshot (the ~3146 entities
    present at game start).
  After the walk: map master_id -> unit name (dataset 100), classify as
  villager/military/building/gaia (using name-keyword heuristics), write
  labels.json = {instance_id(str): {master_id, name, class, owner}}.
  Then VERIFY id-link end-to-end: parse fresh_newpatch.aoe2record, collect mgz
  commanded non-building instance_ids, report what % have a label.

Usage:
  python C:/dev/aoe2/aoe2record/lab/build_labels.py [max_sequences]
  max_sequences: 0 = all (196k), default = 0 (all)

Output:
  C:/dev/aoe2/aoe2record/lab/labels.json
"""

import json
import os
import struct
import sys
import types
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
GRPC_DIR   = os.path.dirname(os.path.abspath(__file__))
SNAP_PATH  = os.path.join(GRPC_DIR, "first_patch_seg2.bin")
FRAMES_PATH = os.path.join(GRPC_DIR, "GAME_munq_vs_ddk220_incas_frames_raw.bin")
LABELS_OUT = os.path.join(GRPC_DIR, "labels.json")
MGZ_PATH   = "C:/dev/aoe2/aoc-mgz-67x"
VIS_PATH   = "C:/dev/aoe2/aoe2record/visualizer"
REPLAY_PATH = "C:/dev/_tmp_replay/fresh_newpatch.aoe2record"

# Add grpc dir to path so decode_state_v2 & cade_api_pb2 import
for p in (GRPC_DIR, MGZ_PATH, VIS_PATH):
    if p not in sys.path:
        sys.path.insert(0, p)

import cade_api_pb2 as pb
import decode_state_v2 as dsv2

MAX_SEQ = int(sys.argv[1]) if len(sys.argv) > 1 else 0  # 0 = all

# ---------------------------------------------------------------------------
# Name map: master_id -> name (dataset 100)
# ---------------------------------------------------------------------------
def load_name_map():
    """Load aocref dataset 100 -> {master_id(int): name(str)}."""
    import aocref
    pkg_dir = os.path.dirname(aocref.__file__)
    path = os.path.join(pkg_dir, "data", "datasets", "100.json")
    with open(path) as f:
        ds = json.load(f)
    return {int(k): v for k, v in ds.get("objects", {}).items()}

NAME_MAP = load_name_map()
print(f"[init] Loaded {len(NAME_MAP)} object names from dataset 100.")

# ---------------------------------------------------------------------------
# Classification heuristics (name-based)
# ---------------------------------------------------------------------------
_VIL_KW  = {'villager', 'shepherd', 'lumberjack', 'woodcutter', 'builder',
             'gold miner', 'stone miner', 'forager', 'farmer', 'hunter',
             'fisher', 'fisherman', 'repairer'}
_BLD_KW  = {'wall', 'gate', 'tower', 'castle', 'barracks', 'stable', 'range',
             'camp', 'mill', 'market', 'dock', 'university', 'monastery',
             'house', 'farm', 'wonder', 'center', 'outpost', 'blacksmith',
             'krepost', 'donjon', 'folwark', 'caravanserai', 'feitoria',
             'harbor', 'workshop', 'palisade', 'lumber', 'mining', 'pasture',
             'siege workshop', 'archery range'}
_GAIA_KW = {'sheep', 'deer', 'wolf', 'boar', 'bear', 'turkey', 'lion',
             'crocodile', 'cobra', 'elephant', 'alligator', 'jaguar', 'hawk',
             'fish', 'relic', 'mine', 'cliff', 'shore', 'rock', 'tree', 'hay',
             'gold', 'stone', 'forage', 'berr', 'bush', 'gaia', 'king', 'amazon'}

# Pre-build master_id -> class cache
_CLS_CACHE = {}

def classify_master_id(mid, owner):
    """Return class string: 'villager'|'military'|'building'|'gaia'."""
    if owner == 0:
        return 'gaia'
    if mid in _CLS_CACHE:
        return _CLS_CACHE[mid]
    nm = NAME_MAP.get(mid, '').lower()
    if any(k in nm for k in _VIL_KW):
        cls = 'villager'
    elif any(k in nm for k in _BLD_KW):
        cls = 'building'
    elif any(k in nm for k in _GAIA_KW):
        cls = 'gaia'
    else:
        cls = 'military'
    _CLS_CACHE[mid] = cls
    return cls


# ---------------------------------------------------------------------------
# PHASE 1: Seed from snapshot (initial entities at game start)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("PHASE 1: Seed initial entities from snapshot")
print("=" * 70)

doc = dsv2.Doc()
entity_store = {}  # live {entity_id -> {__type__, field_idx -> value}}
_, world_id = dsv2.seed_from_snapshot(SNAP_PATH, doc, entity_store)
print(f"  Entities seeded from snapshot: {len(entity_store)}")

# Sync snapshot entities into doc's World model so deltas can PushKey on them
world_model = doc.models[world_id]
world_ents_in_doc = world_model.setdefault(1, {})
for ekey, e in entity_store.items():
    if ekey not in world_ents_in_doc:
        cid = doc.register(e.get("__type__", 9))
        world_ents_in_doc[ekey] = cid
        dm = doc.models[cid]
        for fk, fv in e.items():
            dm[fk] = fv

# ---------------------------------------------------------------------------
# Cumulative label dict (persists through deaths)
# ---------------------------------------------------------------------------
# {entity_id(int) -> {'master_id': int, 'owner': int, 'name': str, 'class': str,
#                      'dead': bool, 'first_frame': int, 'model_type': int}}
cumulative = {}

def _record(eid, model_type, master_id, owner, frame_no):
    """Add or update a cumulative record. master_id=None if not yet known."""
    if eid in cumulative:
        rec = cumulative[eid]
        if master_id is not None:
            rec['master_id'] = master_id
            rec['name'] = NAME_MAP.get(master_id, f'id{master_id}')
        if owner is not None:
            rec['owner'] = owner
        rec['class'] = classify_master_id(rec.get('master_id'), rec.get('owner', 0))
    else:
        name = NAME_MAP.get(master_id, f'id{master_id}') if master_id is not None else None
        cumulative[eid] = {
            'master_id': master_id,
            'owner': owner,
            'name': name,
            'class': classify_master_id(master_id, owner) if master_id is not None else 'unknown',
            'dead': False,
            'first_frame': frame_no,
            'model_type': model_type,
        }


# Seed cumulative from snapshot (frame 0)
snap_dopple = 0
snap_neg = 0
for eid, e in entity_store.items():
    mt = e.get("__type__", 9)
    if eid < 0:
        snap_neg += 1
        continue
    if mt == 10:  # DoppleEntity fog-shadow — exclude
        snap_dopple += 1
        continue
    master_id = e.get(1)
    owner = e.get(2, 0)
    _record(eid, mt, master_id, owner, 0)

print(f"  Cumulative after snapshot: {len(cumulative)}"
      f"  (excluded neg={snap_neg}, dopple={snap_dopple})")

# ---------------------------------------------------------------------------
# PHASE 2: Walk all delta frames — cumulative entity tracking
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("PHASE 2: Walk delta frames (cumulative creates + updates)")
print(f"         max_sequences = {'all' if not MAX_SEQ else MAX_SEQ}")
print("=" * 70)

# We need a CUSTOM patch walker that intercepts creates/updates/deletes
# without relying on apply_patch's entity_store (which only tracks live entities).
# Strategy: use apply_patch (which updates entity_store for live entities), AND
# separately re-scan the patch bytes for op8 CREATE, op2 ASSIGN-while-in-entity,
# op9/op12 DELETE to maintain cumulative.
#
# Actually: apply_patch already handles op8 (adds to entity_store) and op9/op12
# (removes from entity_store). We track the DELTA between before/after for creates
# and deletions, plus we mirror field[1] (master_id) and field[2] (owner) updates
# into cumulative from entity_store updates.
#
# The cleanest approach: after each apply_patch call, diff entity_store against
# cumulative to find new creates, then separately scan for deaths.

seq_count = 0
frame_count = 0
delta_count = 0
total_resyncs = 0
creates_from_deltas = 0
deaths_tracked = 0
updates_tracked = 0
last_time_ms = 520

# Set of IDs currently alive (subset of cumulative)
alive = set(cumulative.keys())

for raw_seq in dsv2.read_frame_sequences(FRAMES_PATH):
    if MAX_SEQ and seq_count >= MAX_SEQ:
        break
    seq_count += 1

    try:
        sq = pb.FrameSequence()
        sq.ParseFromString(raw_seq)
    except Exception:
        continue

    for fr in sq.frame:
        frame_count += 1
        t = fr.time or last_time_ms

        if fr.patch:
            plen = len(fr.patch)
            if plen > 500_000:
                # Full-state snapshot (drift zone) — skip
                continue

            # Snapshot of entity_store BEFORE applying patch
            before_ids = set(entity_store.keys())

            rs = dsv2.apply_patch(doc, fr.patch, entity_store, world_id)
            total_resyncs += rs
            delta_count += 1

            after_ids = set(entity_store.keys())

            # New creates: in after but not before
            new_ids = after_ids - before_ids
            for eid in new_ids:
                e = entity_store[eid]
                mt = e.get("__type__", 9)
                # Exclude DoppleEntity (model_type==10) and negative keys
                if eid < 0 or mt == 10:
                    continue
                master_id = e.get(1)
                owner = e.get(2, 0)
                _record(eid, mt, master_id, owner, frame_count)
                alive.add(eid)
                creates_from_deltas += 1

            # Field updates for existing entities (master_id / owner may change)
            # After apply_patch, entity_store has the latest field values.
            # We check all live entities' field[1] and field[2] against cumulative.
            for eid in after_ids:
                e = entity_store[eid]
                mid = e.get(1)
                own = e.get(2)
                if mid is None and own is None:
                    continue
                if eid in cumulative:
                    rec = cumulative[eid]
                    changed = False
                    if mid is not None and rec.get('master_id') != mid:
                        rec['master_id'] = mid
                        rec['name'] = NAME_MAP.get(mid, f'id{mid}')
                        changed = True
                    if own is not None and rec.get('owner') != own:
                        rec['owner'] = own
                        changed = True
                    if changed:
                        rec['class'] = classify_master_id(rec['master_id'], rec['owner'])
                        updates_tracked += 1

            # Deaths: in before but not after (removed by op9/op12)
            died_ids = before_ids - after_ids
            for eid in died_ids:
                if eid in cumulative:
                    cumulative[eid]['dead'] = True
                    alive.discard(eid)
                    deaths_tracked += 1

        # EntityKilled events (another death signal)
        for ev in fr.event:
            which = ev.WhichOneof("event")
            if which == "entityKilled":
                eid = ev.entityKilled.id
                entity_store.pop(eid, None)
                if eid in cumulative:
                    cumulative[eid]['dead'] = True
                    alive.discard(eid)
                    deaths_tracked += 1

        if t:
            last_time_ms = t

    if seq_count % 10_000 == 0:
        print(f"  ... {seq_count} seqs, {frame_count} frames, "
              f"cumulative={len(cumulative)}, alive={len(alive)}")

print(f"\n  Done: {seq_count} seqs, {frame_count} frames")
print(f"  Delta count: {delta_count}, resyncs: {total_resyncs}")
print(f"  New creates from deltas: {creates_from_deltas}")
print(f"  Deaths tracked: {deaths_tracked}")
print(f"  Field updates: {updates_tracked}")
print(f"  TOTAL cumulative entities: {len(cumulative)}")
print(f"  Final game time: {last_time_ms/1000:.1f}s ({last_time_ms/60000:.1f} min)")

# ---------------------------------------------------------------------------
# PHASE 3: Clean and finalize cumulative labels
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("PHASE 3: Clean and analyze cumulative label set")
print("=" * 70)

# Filter: exclude negative keys and model_type==10 (already done at insert time)
# Exclude entities with no master_id (unknown type — they won't be useful as labels)
clean = {}
excluded_no_master = 0
excluded_dopple = 0
excluded_neg = 0

for eid, rec in cumulative.items():
    if eid < 0:
        excluded_neg += 1
        continue
    if rec.get('model_type') == 10:
        excluded_dopple += 1
        continue
    if rec.get('master_id') is None:
        excluded_no_master += 1
        continue
    clean[eid] = rec

print(f"  Excluded negative keys:   {excluded_neg}")
print(f"  Excluded DoppleEntity:    {excluded_dopple}")
print(f"  Excluded no master_id:    {excluded_no_master}")
print(f"  CLEAN cumulative labels:  {len(clean)}")

# Analysis by class and owner
by_cls   = Counter(r['class'] for r in clean.values())
by_owner = Counter(r['owner'] for r in clean.values())
dead_ct  = sum(1 for r in clean.values() if r.get('dead', False))

print(f"\n  By class:   {dict(by_cls)}")
print(f"  By owner:   {dict(by_owner)}")
print(f"  Dead (ever-existed but died): {dead_ct}")
print(f"  Alive at game end: {len(clean) - dead_ct}")

# Per-owner breakdown
owner_names = {0: 'Gaia', 1: 'P1(munq/Bohemians)', 2: 'P2(ddk220/Incas)'}
for owner in sorted(by_owner.keys()):
    ents = [(eid, r) for eid, r in clean.items() if r['owner'] == owner]
    cls_ct = Counter(r['class'] for _, r in ents)
    name_ct = Counter(r['name'] for _, r in ents)
    print(f"\n  {owner_names.get(owner, f'owner{owner}')}: "
          f"total={len(ents)}  {dict(cls_ct)}")
    print(f"  Top types:")
    for nm, cnt in name_ct.most_common(15):
        cls_tag = next(r['class'] for _, r in ents if r['name'] == nm)
        print(f"    {nm:35s}  x{cnt:3d}  [{cls_tag}]")

# ---------------------------------------------------------------------------
# PHASE 4: Write labels.json
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("PHASE 4: Write labels.json")
print("=" * 70)

# Output format: {instance_id(str): {master_id, name, class, owner}}
# Include ALL entities (gaia + players, dead + alive) for maximum coverage.
# Callers can filter by owner != 0 for player-only.
labels_out = {}
for eid, rec in clean.items():
    labels_out[str(eid)] = {
        "master_id": rec['master_id'],
        "name": rec['name'],
        "class": rec['class'],
        "owner": rec['owner'],
    }

with open(LABELS_OUT, "w") as f:
    json.dump(labels_out, f, separators=(',', ':'))

size_kb = os.path.getsize(LABELS_OUT) / 1024
print(f"  Written: {LABELS_OUT}")
print(f"  Entries: {len(labels_out)}  ({size_kb:.1f} KB)")

# ---------------------------------------------------------------------------
# PHASE 5: Verify id-link vs mgz classifier instance_ids
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("PHASE 5: Verify id-link (gRPC labels vs mgz commanded instance_ids)")
print("=" * 70)

# Stub flask/requests so unit_classifier imports cleanly
for mod_name in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(mod_name, types.ModuleType(mod_name))
sys.modules["flask"].Flask = lambda *a, **k: types.SimpleNamespace(
    route=lambda *a, **k: (lambda f: f)
)
sys.modules["flask"].jsonify = lambda *a, **k: None
sys.modules["flask"].request = None
sys.modules["flask"].send_from_directory = lambda *a, **k: None
sys.modules["flask_cors"].CORS = lambda *a, **k: None

try:
    import mgz.model
    import unit_classifier as uc

    print(f"\n  Parsing replay: {REPLAY_PATH}")
    with open(REPLAY_PATH, "rb") as f:
        match = mgz.model.parse_match(f)

    print(f"  Dataset: {match.dataset_id}  Players: {[(p.name, str(p.civilization)) for p in match.players]}")

    # Run classifier to get all commanded instance_ids
    ctx = uc._run(match)
    guesses = ctx.guesses

    # Collect all non-building instance_ids that the classifier considered
    mgz_non_bld = set(cid for cid in guesses if cid not in ctx.building_ids)
    mgz_all = set(guesses.keys())
    mgz_bld = ctx.building_ids

    print(f"\n  mgz total guesses:          {len(mgz_all)}")
    print(f"  mgz building ids:           {len(mgz_bld)}")
    print(f"  mgz non-building ids:       {len(mgz_non_bld)}")

    # Check label coverage
    label_ids = set(int(k) for k in labels_out.keys())
    player_label_ids = set(int(k) for k, v in labels_out.items() if v['owner'] != 0)

    direct_overlap_all   = mgz_non_bld & label_ids
    direct_overlap_player = mgz_non_bld & player_label_ids

    pct_all    = 100 * len(direct_overlap_all) / max(1, len(mgz_non_bld))
    pct_player = 100 * len(direct_overlap_player) / max(1, len(mgz_non_bld))

    print(f"\n  Label ids total (incl. gaia): {len(label_ids)}")
    print(f"  Label ids player-only:         {len(player_label_ids)}")
    print(f"  Direct overlap (non-bld mgz vs all labels):    {len(direct_overlap_all)} / {len(mgz_non_bld)} ({pct_all:.1f}%)")
    print(f"  Direct overlap (non-bld mgz vs player labels): {len(direct_overlap_player)} / {len(mgz_non_bld)} ({pct_player:.1f}%)")

    n_military = len(direct_overlap_player) - sum(1 for k in direct_overlap_player if labels_out[str(k)]['class'] == 'villager')
    n_villager = sum(1 for k in direct_overlap_player if labels_out[str(k)]['class'] == 'villager')

    # Unmatched mgz ids
    unmatched = mgz_non_bld - label_ids
    print(f"\n  Unmatched mgz non-bld ids: {len(unmatched)}")
    if unmatched:
        print(f"  Unmatched sample: {sorted(unmatched)[:20]}")
        # Check classifier output for unmatched
        unmatched_cls = Counter(guesses[cid].cls for cid in unmatched if cid in guesses)
        print(f"  Unmatched by classifier class: {dict(unmatched_cls)}")
        unmatched_type = Counter(guesses[cid].type for cid in unmatched if cid in guesses)
        print(f"  Unmatched by classifier type (top 10): {unmatched_type.most_common(10)}")

    # Also check: how many mgz ids are in labels but as 'gaia' (wrong owner)
    gaia_overlap = mgz_non_bld & (label_ids - player_label_ids)
    print(f"\n  mgz non-bld ids labeled as GAIA (potential issue): {len(gaia_overlap)}")
    if gaia_overlap:
        for gid in sorted(gaia_overlap)[:10]:
            rec = labels_out.get(str(gid), {})
            print(f"    id={gid}: name={rec.get('name','?')}, class={rec.get('class','?')}, owner={rec.get('owner','?')}")

    # Per-player breakdown of matched ids
    print("\n  Per-player id-link coverage:")
    for p in match.players:
        pname = p.name
        pnum  = p.number
        # mgz ids for this player
        p_mgz_ids = set(cid for cid in mgz_non_bld
                        if guesses[cid].player == pname)
        # labels for this player
        p_label_ids = set(int(k) for k, v in labels_out.items() if v['owner'] == pnum)
        p_overlap = p_mgz_ids & p_label_ids
        p_pct = 100 * len(p_overlap) / max(1, len(p_mgz_ids))
        print(f"  {pname} (P{pnum}): mgz={len(p_mgz_ids)}, labels={len(p_label_ids)}, "
              f"overlap={len(p_overlap)} ({p_pct:.1f}%)")

    # Summary stats for StructuredOutput
    final_n_labels = len(labels_out)
    final_n_vil    = sum(1 for v in labels_out.values() if v['class'] == 'villager')
    final_n_mil    = sum(1 for v in labels_out.values() if v['class'] == 'military')
    final_id_pct   = f"{pct_player:.1f}%"

    print(f"\n  === SUMMARY FOR STRUCTURED OUTPUT ===")
    print(f"  labels_path:        {LABELS_OUT}")
    print(f"  n_labels:           {final_n_labels}")
    print(f"  n_villager:         {final_n_vil}")
    print(f"  n_military:         {final_n_mil}")
    print(f"  id_link_pct:        {final_id_pct}  (non-bld mgz ids that have a player label)")
    print(f"  owner_base:         0=Gaia, 1=P1(munq/Bohemians), 2=P2(ddk220/Incas)")
    print(f"  name_map_source:    aocref dataset 100")

except Exception as ex:
    import traceback
    print(f"  WARNING: mgz parsing failed: {ex}")
    traceback.print_exc()
    final_n_labels = len(labels_out)
    final_n_vil    = sum(1 for v in labels_out.values() if v['class'] == 'villager')
    final_n_mil    = sum(1 for v in labels_out.values() if v['class'] == 'military')
    final_id_pct   = "N/A"

print("\nDone.")
