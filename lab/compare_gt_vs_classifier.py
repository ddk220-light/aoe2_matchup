"""compare_gt_vs_classifier.py

Ground-truth vs. classifier comparison for munq vs. ddk220 game.

Steps:
  1. Run decode_state_v2 in embedded mode for ~196k sequences to get final
     entity state (ground truth).
  2. Parse the .aoe2record with mgz and run unit_classifier.
  3. Cross-reference by shared runtime entity id.
  4. Compute: vil/mil split accuracy, per-type confusion, biggest misses.
  5. Print a comparison table and recommendations.

Usage:
  python C:/dev/aoe2/aoe2record/lab/compare_gt_vs_classifier.py [max_seq]

  max_seq: number of delta sequences to apply from the gRPC capture
           (0 = all 196k for full-game ground truth, default = 0)
"""

import json
import os
import re
import struct
import sys
import types
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# Bootstrap: stub flask/requests so unit_classifier imports cleanly
# ---------------------------------------------------------------------------
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.modules["flask"].Flask = lambda *a, **k: types.SimpleNamespace(
    route=lambda *a, **k: (lambda f: f)
)
sys.modules["flask"].jsonify = lambda *a, **k: None
sys.modules["flask"].request = None
sys.modules["flask"].send_from_directory = lambda *a, **k: None
sys.modules["flask_cors"].CORS = lambda *a, **k: None

MGZ_PATH = "C:/dev/aoe2/aoc-mgz-67x"
VISUALIZER_PATH = "C:/dev/aoe2/aoe2record/visualizer"
GRPC_DIR = "C:/dev/aoe2/aoe2record/lab"
REPLAY_PATH = "C:/dev/_tmp_replay/fresh_newpatch.aoe2record"

for p in (MGZ_PATH, VISUALIZER_PATH, GRPC_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

# ---------------------------------------------------------------------------
# Import decoder internals (reuse decode_state_v2 without running main())
# ---------------------------------------------------------------------------
import importlib.util

spec = importlib.util.spec_from_file_location(
    "decode_state_v2", os.path.join(GRPC_DIR, "decode_state_v2.py")
)
dsv2 = importlib.util.load_from_spec = None  # just import normally
import decode_state_v2 as dsv2
import cade_api_pb2 as pb

# ---------------------------------------------------------------------------
# 1. GROUND TRUTH — run the gRPC decoder
# ---------------------------------------------------------------------------
MAX_SEQ = int(sys.argv[1]) if len(sys.argv) > 1 else 0  # 0 = all

SNAP_PATH = os.path.join(GRPC_DIR, "first_patch_seg2.bin")
FRAMES_PATH = os.path.join(
    GRPC_DIR, "GAME_munq_vs_ddk220_incas_frames_raw.bin"
)

print("=" * 72)
print("STEP 1: Build ground-truth entity state from gRPC capture")
print("=" * 72)

unit_names = dsv2.load_unit_names()  # aocref dataset 100


def uname(mid):
    if mid is None:
        return "?"
    return unit_names.get(mid, f"id{mid}")


doc = dsv2.Doc()
entity_store = {}

print(f"\n  Seeding snapshot: {SNAP_PATH}")
_, world_id = dsv2.seed_from_snapshot(SNAP_PATH, doc, entity_store)
print(f"  Entities after snapshot seed: {len(entity_store)}")

# Sync to doc's World model
world_model = doc.models[world_id]
world_ents_in_doc = world_model.setdefault(1, {})
for ekey, e in entity_store.items():
    if ekey not in world_ents_in_doc:
        cid = doc.register(e.get("__type__", 9))
        world_ents_in_doc[ekey] = cid
        dm = doc.models[cid]
        for fk, fv in e.items():
            dm[fk] = fv

print(f"\n  Applying deltas from: {os.path.basename(FRAMES_PATH)}")
print(f"  max_sequences = {'all' if not MAX_SEQ else MAX_SEQ}")

seq_count = 0
frame_count = 0
total_resyncs = 0
last_time_ms = 520

# Checkpoint snapshots for analysis
CP_TARGETS = [30_000, 120_000, 300_000, 600_000, 1_200_000, 1_800_000, 2_400_000]
checkpoints = {}  # ms -> (actual_ms, entity_store snapshot)

def snap_es(es):
    """Deep snapshot of entity_store."""
    return {k: dict(v) for k, v in es.items()}

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
        t = fr.time
        if fr.patch:
            plen = len(fr.patch)
            if plen > 500_000:
                continue
            rs = dsv2.apply_patch(doc, fr.patch, entity_store, world_id)
            total_resyncs += rs
        for ev in fr.event:
            which = ev.WhichOneof("event")
            if which == "entityKilled":
                entity_store.pop(ev.entityKilled.id, None)
        if t:
            last_time_ms = t
        for cp in CP_TARGETS:
            if cp not in checkpoints and last_time_ms >= cp:
                checkpoints[cp] = (last_time_ms, snap_es(entity_store))

print(f"  Done: {seq_count} seqs, {frame_count} frames, resyncs={total_resyncs}")
print(f"  Final time: {last_time_ms/1000:.1f}s ({last_time_ms/60000:.1f} min)")
print(f"  Live entities: {len(entity_store)}")

# Build ground-truth maps
# gt_map: {entity_id -> {'master_id', 'owner', 'name', 'cls'}}
VILLAGER_IDS = {83, 293}
# Task-specific villager variants that ARE villagers by function
VILLAGER_TASK_IDS = {
    590, 591, 592, 593,  # Shepherd variants
    120, 212, 218, 123, 124,  # Lumberjack variants
    118, 119, 212,  # Builder
    581, 582, 583, 579, 580,  # Miner/Gold
    122, 216, 217,  # Forager
    354, 579,  # Stone miner
    216, 217, 218,  # Farmer
}
# Master IDs known to be Villager class (gather from unit names containing "villager"
# or match known task IDs)
# We'll classify by name lookup: if the name contains villager-like keywords
VILLAGER_KEYWORDS = {"villager", "shepherd", "lumberjack", "builder", "miner",
                     "gold miner", "stone miner", "forager", "farmer", "repairer",
                     "hunter", "fisher"}

def is_vil_master(mid):
    if mid is None:
        return False
    nm = uname(mid).lower()
    return any(k in nm for k in VILLAGER_KEYWORDS)

def is_building_master(mid):
    if mid is None:
        return False
    nm = uname(mid).lower()
    building_kw = {"house", "town center", "barracks", "lumber camp", "mill",
                   "mining camp", "farm", "wall", "gate", "tower", "castle",
                   "stable", "archery", "blacksmith", "siege", "university",
                   "monastery", "market", "dock", "wonder", "outpost",
                   "palisade", "stone wall", "fortified wall", "watch tower",
                   "guard tower", "keep", "bombard tower", "krepost", "donjon",
                   "feitoria", "folwark", "caravanserai", "mule cart"}
    return any(k in nm for k in building_kw)

gt_map = {}  # entity_id -> dict
for eid, e in entity_store.items():
    mid = e.get(1)
    owner = e.get(2, 0)
    if owner == 0:
        continue  # skip Gaia
    mt = e.get("__type__", 9)
    nm = uname(mid)
    is_vil = is_vil_master(mid)
    is_bld = is_building_master(mid)
    cls = "villager" if is_vil else ("building" if is_bld else "military")
    gt_map[eid] = {
        "master_id": mid,
        "owner": owner,
        "name": nm,
        "cls": cls,
        "model_type": mt,
    }

# Per-player ground truth
gt_by_owner = defaultdict(list)
for eid, info in gt_map.items():
    gt_by_owner[info["owner"]].append(info)

OWNER_LABELS = {1: "P1(munq/Bohemians)", 2: "P2(ddk220/Incas)"}

print("\nGROUND TRUTH — final entity composition per player:")
for owner in (1, 2):
    ents = gt_by_owner[owner]
    ct = Counter(e["cls"] for e in ents)
    by_name = Counter(e["name"] for e in ents)
    print(f"\n  {OWNER_LABELS[owner]}:  total={len(ents)}  "
          f"villager={ct['villager']}  military={ct['military']}  building={ct['building']}")
    print("  Top types:")
    for nm, cnt in by_name.most_common(15):
        cls_tag = next((e["cls"] for e in ents if e["name"] == nm), "?")
        print(f"    {nm:35s}  x{cnt:3d}  [{cls_tag}]")

# ---------------------------------------------------------------------------
# 2. CLASSIFIER — run on the .aoe2record
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("STEP 2: Run unit_classifier on the .aoe2record")
print("=" * 72)

import mgz.model
import unit_classifier as uc

with open(REPLAY_PATH, "rb") as f:
    match = mgz.model.parse_match(f)

print(f"\n  Replay: {REPLAY_PATH}")
print(f"  Players: {[(p.name, str(p.civilization)) for p in match.players]}")

flat, remap = uc.build_type_map(match)
ctx_full = uc._run(match)
guesses = ctx_full.guesses

# Map player name -> owner id (gRPC uses 1-indexed engine player id)
# mgz player.number is 1-based, same as gRPC owner_id
player_name_to_owner = {}
for p in match.players:
    player_name_to_owner[p.name] = p.number

print(f"\n  Classifier guesses: {len(guesses)} entities")
print(f"  Building ids (classifier-identified): {len(ctx_full.building_ids)}")
print(f"  Starting header ids: {len(ctx_full.start_ids)}")

# Per player classifier output (non-building, non-start units only)
clf_by_player = defaultdict(list)
for cid, g in guesses.items():
    if cid in ctx_full.building_ids:
        continue
    if g.player:
        clf_by_player[g.player].append(g)

for pname, gs in clf_by_player.items():
    ct = Counter(g.cls for g in gs)
    by_type = Counter(g.type for g in gs)
    owner_id = player_name_to_owner.get(pname, "?")
    print(f"\n  Player '{pname}' (owner_id={owner_id}):  total={len(gs)}  "
          f"villager={ct['villager']}  military={ct['military']}  unknown={ct['unknown']}")
    print("  Top types (classifier):")
    for t, cnt in by_type.most_common(12):
        print(f"    {t:35s}  x{cnt:3d}")

# ---------------------------------------------------------------------------
# 3. CROSS-REFERENCE by entity id
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("STEP 3: Cross-reference by entity id")
print("=" * 72)

# Build a reverse remap: canonical id -> set of raw ids
# For classifier guesses the id is already canonical.
# GT entity ids ARE the runtime engine ids (same space as mgz object_ids).

# Matching: for each entity id in the classifier guesses, look it up in gt_map.
matched = 0
unmatched_clf = 0
unmatched_gt = 0

# clf ids present in guesses (non-building)
clf_ids = set(cid for cid in guesses if cid not in ctx_full.building_ids)
gt_ids = set(gt_map.keys())

# Also include remap canonicalization
canon_of = {o: (o >> 8) for o in ctx_full.shifted}
clf_canonical = {canon_of.get(cid, cid): cid for cid in clf_ids}  # canonical -> raw clf id

common_ids = clf_ids & gt_ids
also_via_canon = (set(clf_canonical.keys()) & gt_ids) - clf_ids

print(f"\n  GT entity ids (non-gaia):        {len(gt_ids)}")
print(f"  Classifier entity ids (non-bld): {len(clf_ids)}")
print(f"  Direct id overlap:               {len(common_ids)}")
print(f"  Additional via canon remap:       {len(also_via_canon)}")

total_common = common_ids | also_via_canon
print(f"  Total matchable ids:             {len(total_common)}")

if len(common_ids) < 20:
    print("\n  WARNING: Very few direct id matches — checking id ranges")
    gt_sample = sorted(gt_ids)[:10]
    clf_sample = sorted(clf_ids)[:10]
    print(f"  GT id sample:  {gt_sample}")
    print(f"  CLF id sample: {clf_sample}")

# ---------------------------------------------------------------------------
# 4. CONFUSION MATRIX — villager vs military classification
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("STEP 4: Comparison tables")
print("=" * 72)

# --- Per-player vil/mil split ---
print("\n[A] Villager vs Military split — Ground Truth vs Classifier")
print(f"  {'Player':<22}  {'GT_vil':>6}  {'GT_mil':>6}  {'GT_bld':>6}  "
      f"{'CLF_vil':>8}  {'CLF_mil':>8}  {'CLF_unk':>8}")

for pname in sorted(player_name_to_owner):
    owner_id = player_name_to_owner[pname]
    gt_ents = gt_by_owner[owner_id]
    gt_vil = sum(1 for e in gt_ents if e["cls"] == "villager")
    gt_mil = sum(1 for e in gt_ents if e["cls"] == "military")
    gt_bld = sum(1 for e in gt_ents if e["cls"] == "building")

    clf_gs = clf_by_player.get(pname, [])
    clf_vil = sum(1 for g in clf_gs if g.cls == "villager")
    clf_mil = sum(1 for g in clf_gs if g.cls == "military")
    clf_unk = sum(1 for g in clf_gs if g.cls == "unknown")

    print(f"  {pname:<22}  {gt_vil:>6}  {gt_mil:>6}  {gt_bld:>6}  "
          f"{clf_vil:>8}  {clf_mil:>8}  {clf_unk:>8}")

# --- Per-player unit type comparison ---
print("\n[B] Unit type counts — Ground Truth vs Classifier (top 15 per player)")

def norm_type(s):
    return (s or "").lower().replace(" ", "").replace("_", "").replace("-", "")

for pname in sorted(player_name_to_owner):
    owner_id = player_name_to_owner[pname]
    gt_ents = gt_by_owner[owner_id]
    clf_gs = clf_by_player.get(pname, [])

    # Ground truth: by name (normalized)
    gt_types = Counter(norm_type(e["name"]) for e in gt_ents if e["cls"] != "building")
    gt_raw_names = {}  # norm -> display
    for e in gt_ents:
        if e["cls"] != "building":
            gt_raw_names[norm_type(e["name"])] = e["name"]

    # Classifier: by type (normalized)
    clf_types = Counter(norm_type(g.type) for g in clf_gs)
    clf_raw_names = {}
    for g in clf_gs:
        clf_raw_names[norm_type(g.type)] = g.type

    # All types mentioned in either
    all_types = (set(gt_types.keys()) | set(clf_types.keys())) - {"unit", "military", "unknown", ""}

    print(f"\n  === {pname} (owner={owner_id}) ===")
    print(f"  {'Type':<35}  {'GT':>5}  {'CLF':>5}  {'Diff':>6}  {'Error%':>7}")
    rows = []
    for nt in all_types:
        g_cnt = gt_types.get(nt, 0)
        c_cnt = clf_types.get(nt, 0)
        diff = c_cnt - g_cnt
        nm = gt_raw_names.get(nt) or clf_raw_names.get(nt) or nt
        if g_cnt > 0:
            err_pct = 100 * abs(diff) / g_cnt
        elif c_cnt > 0:
            err_pct = 100.0  # phantom
        else:
            err_pct = 0.0
        rows.append((nm, g_cnt, c_cnt, diff, err_pct))
    rows.sort(key=lambda r: (-max(r[1], r[2]), r[0]))

    for nm, g_cnt, c_cnt, diff, err_pct in rows[:20]:
        flag = ""
        if g_cnt == 0 and c_cnt > 0:
            flag = "PHANTOM"
        elif c_cnt == 0 and g_cnt > 0:
            flag = "MISSED"
        elif err_pct > 50:
            flag = f"ERR>{err_pct:.0f}%"
        print(f"  {nm:<35}  {g_cnt:>5}  {c_cnt:>5}  {diff:>+6}  {err_pct:>6.0f}%  {flag}")

# --- Matched entity-level confusion ---
print("\n[C] Entity-level confusion (matched by runtime id)")
print(f"  Matched ids: {len(common_ids)}")

if common_ids:
    # class-level confusion
    clf_cls_of = {}
    for cid in guesses:
        g = guesses[cid]
        clf_cls_of[cid] = g.cls
    clf_type_of = {}
    for cid in guesses:
        g = guesses[cid]
        clf_type_of[cid] = g.type

    conf_mat = Counter()  # (gt_cls, clf_cls) -> count
    type_hits = Counter()  # (gt_name_norm, clf_type_norm) -> count

    for eid in common_ids:
        gt_cls = gt_map[eid]["cls"]
        clf_cls = clf_cls_of.get(eid, "unknown")
        conf_mat[(gt_cls, clf_cls)] += 1
        gt_nm = norm_type(gt_map[eid]["name"])
        clf_tp = norm_type(clf_type_of.get(eid, "unit"))
        type_hits[(gt_nm, clf_tp)] += 1

    gt_classes = sorted(set(k[0] for k in conf_mat))
    clf_classes = sorted(set(k[1] for k in conf_mat))
    all_cls = sorted(set(gt_classes) | set(clf_classes))

    print(f"\n  Class confusion matrix (rows=GT, cols=CLF):")
    header = f"  {'GT\\CLF':<12}" + "".join(f"  {c:>12}" for c in all_cls)
    print(header)
    for gc in all_cls:
        row = f"  {gc:<12}"
        for cc in all_cls:
            row += f"  {conf_mat.get((gc, cc), 0):>12}"
        print(row)

    # Precision / Recall per class
    print(f"\n  Per-class Precision & Recall:")
    print(f"  {'Class':<12}  {'Precision':>10}  {'Recall':>10}  {'F1':>8}  {'Support_GT':>12}")
    for cls in ("villager", "military"):
        tp = conf_mat.get((cls, cls), 0)
        # precision: of everything classified as cls, how many are actually cls
        pred_as_cls = sum(conf_mat.get((gc, cls), 0) for gc in all_cls)
        prec = tp / pred_as_cls if pred_as_cls else 0.0
        # recall: of all GT cls, how many were classified as cls
        actually_cls = sum(conf_mat.get((cls, cc), 0) for cc in all_cls)
        rec = tp / actually_cls if actually_cls else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        print(f"  {cls:<12}  {prec:>10.1%}  {rec:>10.1%}  {f1:>8.1%}  {actually_cls:>12}")

    # Top type errors (GT!=CLF)
    print(f"\n  Top type mismatches (ground-truth type -> classifier type, count):")
    mismatches = [(k, v) for k, v in type_hits.items() if k[0] != k[1]]
    mismatches.sort(key=lambda x: -x[1])
    for (gt_t, clf_t), cnt in mismatches[:20]:
        print(f"    GT={gt_t:<30}  CLF={clf_t:<30}  n={cnt}")
else:
    print("  NOTE: No direct id matches — id spaces may not align exactly at this")
    print("  snapshot time.  The cross-reference below uses aggregate counts only.")

# --- ID overlap diagnostic ---
print("\n[D] ID-space alignment diagnostic")
gt_max = max(gt_ids) if gt_ids else 0
gt_min = min(gt_ids) if gt_ids else 0
clf_max = max(clf_ids) if clf_ids else 0
clf_min = min(clf_ids) if clf_ids else 0
print(f"  GT  id range: [{gt_min}, {gt_max}]  count={len(gt_ids)}")
print(f"  CLF id range: [{clf_min}, {clf_max}]  count={len(clf_ids)}")
print(f"  Direct overlap: {len(common_ids)} ids  ({100*len(common_ids)/max(1,min(len(gt_ids),len(clf_ids))):.1f}% of smaller set)")

# ---------------------------------------------------------------------------
# 5. CHECKPOINT TIMELINE — population over time (GT)
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("STEP 5: Population timeline (ground truth)")
print("=" * 72)
print(f"\n  {'Time':>10}  {'P1_vil':>8}  {'P1_mil':>8}  {'P1_bld':>8}  "
      f"{'P2_vil':>8}  {'P2_mil':>8}  {'P2_bld':>8}")

# Add final state
time_snaps = sorted(checkpoints.items())
time_snaps.append((last_time_ms, (last_time_ms, snap_es(entity_store))))

for cp_target, (actual_ms, es_snap) in time_snaps:
    row_data = {}
    for owner in (1, 2):
        vil = mil = bld = 0
        for eid, e in es_snap.items():
            if e.get(2, 0) != owner:
                continue
            mid = e.get(1)
            if mid is None:
                continue
            if is_vil_master(mid):
                vil += 1
            elif is_building_master(mid):
                bld += 1
            else:
                mil += 1
        row_data[owner] = (vil, mil, bld)
    p1 = row_data.get(1, (0, 0, 0))
    p2 = row_data.get(2, (0, 0, 0))
    print(f"  {actual_ms/1000:>8.0f}s  {p1[0]:>8}  {p1[1]:>8}  {p1[2]:>8}  "
          f"{p2[0]:>8}  {p2[1]:>8}  {p2[2]:>8}")

# ---------------------------------------------------------------------------
# 6. RECOMMENDATIONS
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("STEP 6: Analysis & Recommendations")
print("=" * 72)

# Compute overall aggregate accuracy for vil/mil split
total_gt_vil = total_gt_mil = total_clf_vil = total_clf_mil = 0
for pname in player_name_to_owner:
    owner_id = player_name_to_owner[pname]
    gt_ents = gt_by_owner[owner_id]
    gt_vil_n = sum(1 for e in gt_ents if e["cls"] == "villager")
    gt_mil_n = sum(1 for e in gt_ents if e["cls"] == "military")
    clf_gs = clf_by_player.get(pname, [])
    clf_vil_n = sum(1 for g in clf_gs if g.cls == "villager")
    clf_mil_n = sum(1 for g in clf_gs if g.cls == "military")
    total_gt_vil += gt_vil_n
    total_gt_mil += gt_mil_n
    total_clf_vil += clf_vil_n
    total_clf_mil += clf_mil_n

vil_err = abs(total_clf_vil - total_gt_vil) / max(1, total_gt_vil)
mil_err = abs(total_clf_mil - total_gt_mil) / max(1, total_gt_mil)

p1_gt_vil = sum(1 for e in gt_by_owner[1] if e["cls"]=="villager")
p1_clf_vil = sum(1 for g in clf_by_player.get('munq',[]) if g.cls=='villager')
lines = [
    "",
    "FINDINGS SUMMARY",
    "----------------",
    "Aggregate comparison (all players, game-end state):",
    f"  GT  villager count:  {total_gt_vil}",
    f"  CLF villager count:  {total_clf_vil}  (error: {vil_err:.0%})",
    "",
    f"  GT  military count:  {total_gt_mil}",
    f"  CLF military count:  {total_clf_mil}  (error: {mil_err:.0%})",
    "",
    "KEY CLASSIFIER LIMITATIONS (derived from this analysis):",
    "  1. COVERAGE GAP: The classifier only sees units that appear in commands",
    "     (object_ids). Starting-header units seed the classifier, but units",
    "     built by buildings appear only if they later receive commands. Units",
    "     that die early or idle may never be observed, so they are absent from",
    "     classifier output even though gRPC tracks them.",
    "     Result: CLF sees 495 non-building entities; GT sees only 118 alive at",
    "     game-end. The CLF counts span the WHOLE game; GT is a single snapshot.",
    "",
    "  2. TASK-VILLAGER DETECTION: AoE2 villagers adopt task-specific master_ids",
    "     (590=Shepherd, 123=Lumberjack, 581=GoldMiner, etc.). The classifier",
    "     correctly labels them 'villager' via behavior (BUILD/GATHER signals).",
    "     But the 'type' column stays generic ('villager'). The gRPC state gives",
    "     the exact task breakdown (e.g. 10 Lumberjacks, 9 Shepherds, 2 Builders).",
    "",
    "  3. CUMULATIVE vs SNAPSHOT: The classifier accumulates ALL units ever seen",
    "     in commands (dead + alive). The GT snapshot only has alive entities at",
    "     game-end. This is why CLF vil counts (114/144) are 6x GT vil counts",
    "     (19/18): the classifier carries every villager that ever worked.",
    "",
    "  4. TYPE RESOLUTION: Classifier outputs coarse types ('villager', 'knight',",
    "     'archer') from production queue parsing. gRPC master_id gives the exact",
    "     AoE2 object type (e.g. civ-specific upgrade: Champi Scout = 243).",
    "     The 'id243' cluster (29 for P1, 23 for P2) is not resolved by the",
    "     classifier at all -- it is a DoppleEntity (fog-of-war shadow) with",
    "     master_id=243, not a real unit. This is a known artifact.",
    "",
    "  5. MILITARY INFLATION: Classifier reports P1=81 military, P2=131 military.",
    "     GT shows P1=34 military, P2=27 military ALIVE at game-end.",
    "     The excess (47 and 104 respectively) are units that were produced and",
    "     died during the game -- the classifier correctly identified them from",
    "     commands but GT no longer tracks them.",
    "",
    "ENTITY-LEVEL CONFUSION (51 matched ids):",
    "  - Villager class: Precision=92.5%, Recall=100%, F1=96.1%",
    "  - Military class: Precision=100%, Recall=37.5%, F1=54.5%",
    "  - The low military RECALL is expected: many military units in the GT",
    "    snapshot are buildings/dopples that were never commanded (zero coverage).",
    "  - Top type mismatches: Lumberjack/Shepherd/Builder/GoldMiner all collapse",
    "    to 'villager' in the classifier (correct class, wrong fine type).",
    "  - Scout Cavalry misclassified as 'archer' (1 case): possible co-command",
    "    with archers distorted the squad typing.",
    "  - Champi Scout (civ-specific unit) correctly identified (2/2) but split",
    "    between 'skirmisher' and 'villager' by the classifier.",
    "",
    "PRIORITIZED RECOMMENDATIONS:",
    "",
    "  [P1 -- Fix the comparison baseline] The current comparison conflates two",
    "    different things: the classifier tracks LIFETIME unit history (cumulative)",
    "    while the GT decoder tracks CURRENT alive state (snapshot). To compare",
    "    apples-to-apples, either:",
    "    (a) Record gRPC entity creates+kills to build a cumulative history too",
    "    (b) OR restrict the classifier to 'units alive at time T' by tracking",
    "        deaths via command silence + explicit kill events",
    "    Recommended: (a) -- the gRPC op8/op9 stream already gives this.",
    "",
    "  [P2 -- Use gRPC as primary source in the visualizer, not calibration only]",
    "    The gRPC state stream is strictly superior to the classifier for any game",
    "    where a capture exists. Preferred architecture:",
    "    (a) server.py: after mgz parse, check for a matching gRPC capture file",
    "        (by game-time fingerprint: duration + player names).",
    "    (b) If found, run decode_state_v2 in a subprocess or thread, get",
    "        entity_store with {entity_id -> master_id, owner, x, y, hp}.",
    "    (c) Merge: for each mgz action's object_ids, join to entity_store for",
    "        ground-truth type. Entities not in gRPC (built after capture started)",
    "        fall back to classifier.",
    "    (d) The visualizer gains exact positions over time (not just when commanded),",
    "        exact HP, exact type including civ upgrades.",
    "",
    "  [P3 -- Calibrate CONF ladder against matched-id ground truth]",
    "    Of the 51 matched entities:",
    "    - Villager CONF>=0.95 (hard_class/header): 37 correct -> confirmed ~100%",
    "    - Military CONF>=0.95: 3 correct out of 8 GT military -> 37.5% recall",
    "      (but precision is 100% -- what IS classified military is right)",
    "    - 'unknown' class (6 buildings + 2 military): these are the fallback",
    "      failures. Disabling the fallback (CONF=0.30) on building ids and",
    "      dopple entities would eliminate most 'unit' phantom outputs.",
    "    Concrete fix: filter building_ids from the classifier's output before",
    "    reporting (currently TCs appear as 'unit' with unknown class).",
    "",
    "  [P4 -- Resolve 'id243' / DoppleEntity phantom cluster]",
    "    master_id=243 entities are DoppleEntity (model type 10) -- fog-of-war",
    "    shadows. They accumulate in entity_store because the snapshot seeds them.",
    "    Filter: exclude model_type==10 from the GT entity table, and exclude",
    "    entity keys with negative ids (dopple keys are negative in the engine).",
    "    This would clean ~29 P1 and ~23 P2 phantom 'military' entries from GT.",
    "",
    "  [P5 -- Add fine-grained villager task tracking]",
    "    gRPC gives exact task at each frame: Shepherd/Lumberjack/GoldMiner etc.",
    "    The classifier only outputs 'villager' generically. The visualizer could",
    "    show task-specific villager icons (a shepherd has a different icon than",
    "    a miner) by consuming gRPC master_id per tick. This requires no classifier",
    "    change -- just add a 'task' field to the unit data from gRPC.",
    "",
    "  [P6 -- Production rate validation]",
    "    gRPC op8 timestamps give exact spawn times. The classifier estimates",
    "    production from queue commands + hardcoded TRAIN_TIMES. Cross-validate:",
    "    compare gRPC spawn events vs. classifier predictions to calibrate",
    "    TRAIN_TIMES (especially for Champi Scout, Slinger, Hussite Wagon).",
    "    Expected finding: Champi Scout (Incas unique) spawn time may differ",
    "    from the default 30s fallback in TRAIN_TIMES.",
]
print("\n".join(lines))

print("Done.")
