# gRPC capture decode — STATUS

Game: match 482498392, munq (Bohemians) vs ddk220 (Incas), Arabia, VER 9.4 /
gameVersion 177723. Same game as `fresh_newpatch.aoe2record`.
Capture: `GAME_munq_vs_ddk220_incas_frames_raw.bin` = 993 MB, 196,143 frames,
42.6 min, length-delimited FrameSequence protobufs.

## ✅ DONE — we can parse the massive file (the simple goal)

### 1. PRODUCTION — 100% verified  (`extract_events.py` -> `events_summary.json`)
The clean, robust source is the **command stream**, NOT the fragile delta patch:
`MultiQueue{playerId, trainId=type, trainCount}` = every unit trained.
Cross-checked vs the .aoe2record DE_QUEUE log: **13/13 unit types match exactly.**

  munq:   Villager 128, Archer 58, Hussite Wagon 25, Knight 6, Militia 4, Treb 4, Monk 2   (227)
  ddk220: Villager 164, Skirmisher 122, Slinger 77, Spearman 27, Archer 10, Champi Scout 7 (407)

Also parsed: `Build` (buildings), first-train timestamp per type, all command +
event type tallies. NO EntityKilled events in this capture (7885 empty events,
58 combatSound, 23 market, 7 chat) -> deaths are NOT in the event stream.

### 2. INITIAL + SURVIVORS  (`build_ground_truth.py` -> `ground_truth.json`)
Decoded the two full-state snapshots (start 0.5 min = `first_patch_seg2.bin`;
end 42.6 min = `end_snapshot.bin`) via the robust entity-band scan (0 resyncs).
Filtered to real unit model-types {9,11,12,14} (drop Missile 13 / Dopple 10 fog
shadows), excluded Flare, collapsed villager task-variants. DEATHS by difference
(produced - alive@end):

  munq:   Villager 128->118 (10 died), Archer 58->16 (42), Hussite 25->7 (18),
          Knight 6->1, Treb 4->0, Militia 4->0.  Defensive: 196/227 survived.
  ddk220: Villager 164->88 (76 died), Skirmisher 122->0 (ALL died), Slinger 77->11,
          Spearman 27->1.  Aggressive, lost the army: 221/407 survived.

Story checks out: Incas all-in skirm/slinger, lost army + got villagers raided;
Bohemians turtled with archers/Hussite Wagons + 4 castles and survived.

## ⚠️ KNOWN GAPS (the "iterations later" work)
- **Per-unit death TIME + HP-over-time**: needs the delta-state decode, which
  PLATEAUS at ~6 min. Cause: model drift (reference_model.rs is 2024; game is
  VER 9.4) makes the scalar/string width guesser misread a field -> per-frame
  desync that corrupts the persistent doc -> World nav fails for all later frames.
  Not a skipped-snapshot issue (only 2 snapshots: start + end, no mid-game one).
- **entity_id -> master_id mapping** (the 99%-classifier ANSWER KEY): same blocker.
  Snapshots give it cleanly at t=0.5min and t=42.6min, but not continuously.
- **Unmapped master_ids in survivors** (id26, id100, id186, id1705, id2556...):
  not in aocref dataset 100 (newer-patch ids or sub-objects). Cosmetic; produced
  units all map cleanly.
- Re-capturing WITH EntityKilled events enabled would give exact deaths directly.

## Artifacts (C:/dev/aoe2/aoe2record/lab/)
- extract_events.py / events_summary.json  — production + buildings (verified)
- build_ground_truth.py / ground_truth.json — produced/alive/died per type, per player
- decode_state_v2.py — flat-doc patch decoder + robust snapshot entity-band seeder
- decode_lifecycle.py — cumulative delta lifecycle (works early game; plateaus mid)
- end_snapshot.bin — extracted end-state (42.6 min) snapshot
- cade_api.proto / *_pb2*.py / certs — gRPC client

## Next iteration (deferred per user: "iterations later")
Fix delta-decode drift -> continuous entity_id->type+hp -> labels.json
{instance_id: true_type} -> score & improve unit_classifier on the .aoe2record
ALONE to >=99% (OVERNIGHT_PLAN.md north star).
