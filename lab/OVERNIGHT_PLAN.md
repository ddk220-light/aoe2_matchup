# Overnight loop — make the .aoe2record classifier 99% accurate using gRPC ground truth

## TRUE NORTH STAR (clarified by user)
The end goal is NOT decoding gRPC for its own sake. It is: analyze an .aoe2record
ALONE (no game) and map its units to their true types with **>=99% accuracy**. The
gRPC state decode is the means to get a perfect ANSWER KEY (labels) to measure and
relentlessly improve the inference classifier toward 99%.

## FOUNDATIONAL UNLOCK (verified 2026-06-02)
gRPC entity_id == mgz instance_id (98% overlap on the same game). So decoding the
gRPC state to {entity_id -> master_id(unit type)} gives {instance_id -> true_type}
= direct per-unit labels for the .aoe2record. No positional correlation needed.

## Definition of "done"
- A labeled set {instance_id -> true unit type} extracted from the gRPC capture
  (master_id -> AoE2 unit name).
- unit_classifier (run on the .aoe2record ALONE) matches those true types at
  **>=99%** per-commanded-unit accuracy (and the villager/military split ~100%),
  on this game and any further validation games.
- An automated harness that re-measures accuracy and surfaces every misclassified
  unit, driving the improvement loop.

## Loop (each iteration)
1. DECODE gRPC capture -> {entity_id(=instance_id): master_id}  (fix decode_state_v2).
2. NAME map: master_id -> unit type name (AoE2 ids; same as mgz/aocref).
3. RUN unit_classifier on the .aoe2record alone -> predicted types per instance_id.
4. SCORE: per-unit accuracy vs labels; confusion matrix; list every miss.
5. IMPROVE the classifier (signals/rules/algorithm) against the errors; re-score.
6. Repeat until >=99%. Persist labels (labels.json) + accuracy log.

## Iteration log
- **Iter 1 (wjx6fwc5p, DONE):** CRACKED THE DECODE. decode_state_v2.py uses the
  flat-document + object-id model (World.entities holds object ids, not nested).
  Seeds 3,146 initial entities (snapshot entity band, 0 resyncs) + applies 196,141
  delta frames. master_id=unit type. Same game confirmed (munq Bohemians vs ddk220
  Incas). Also built compare_gt_vs_classifier.py. Caveats: accuracy numbers NOT yet
  trustworthy (GT was end-state vs classifier cumulative; contaminated by DoppleEntity
  fog-shadows model_type 10 + gaia). Snapshot master-entity defs still desync (drift)
  but we route around via the entity band. ~3.3M late-game resyncs (unquantified).
- **Iter 2 (w3l9dy1f6, running):** build CUMULATIVE cleaned labels.json {instance_id:
  true type} -> score baseline accuracy + confusion + misses -> 3 PARALLEL improve
  strategies (refined-rules, data-driven-features, group-first/id-order) each on a
  classifier copy vs labels -> synthesize best + path to 99%. Anti-overfit (1 game).

## Angle/algorithm backlog (cycle through these on each iteration)
1. DOCUMENT+REF model: flat document {doc_id: model}; World.entities holds Refs;
   PushCreate assigns a doc id. (primary hypothesis for the 0-entities bug)
2. DELTA-only extraction from the real stream: track op8 PushCreateAssignKey with
   Entity types 9..14 and the master_id/x/y/hp assigns; ignore the snapshot.
3. PATH A — reconstruct the updated master-entity model for gameVersion 177723
   (RE the new fields/types incl. the String that breaks the guesser) to decode
   first_patch_seg2.bin fully and get the exact INITIAL entity set.
4. ROBUST GUESSER / schema auto-learning: infer unknown field widths from
   consistency across many entity instances (same type -> same layout); learn the
   per-type field map empirically from the stream itself.
5. TRIANGULATION: fuse Create/Make/Queue commands + EntityKilled events + the
   .aoe2record production timeline to pin each entity's type independent of the
   raw patch decode.
6. reversePatch / bidirectional check: use reversePatch to validate forward decode.
7. EXACT VALIDATION harness: continuous cross-check decoded composition vs the
   .aoe2record + commands; surface every mismatch as the next thing to fix.

## Loop mechanism
Each workflow completion re-invokes me. I read results, update this log, pick the
next unaddressed angle(s), and launch the next refined workflow. Persist all
artifacts in C:/dev/aoe2/aoe2record/lab/ so iterations compound. Stop when "done" criteria met.
```
