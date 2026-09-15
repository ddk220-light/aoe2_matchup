# Compact video storage policy

Owner decision, 2026-09-14: retain the minimum needed to rebuild presentation.
This supersedes older instructions to retain previews, intermediate renders,
multiple overlay videos or duplicate pre-trim recordings indefinitely.

```
AoE2 Renders/<unit-civilization-run-variant>/
  <run-name>_Full_Video.mp4     # completed stitched video, when available
  run.json                     # one small provenance/alignment index
  <civ-unit>_vs_<civ-unit>.mp4  # unoverlaid battle, including game audio
  <civ-unit>_vs_<civ-unit>.frames.bin # matching complete gRPC stream
```

Keep distinct run variants (e.g. corrected costs, five-Hussar buffer) separate.
Never merge different captures merely because their unit names are the same.
The run folder is flat, with no per-matchup subfolders. Matchup pairs use the
same descriptive filename stem; ambiguous duplicate names fail rather than overwrite.

The two media files alone are not sufficient for exact reconstruction:
frames carry game state but not the trimmed video's clock offset. run.json
retains the battle clock mapping, game version, stream metadata, matchup plan,
effective costs, Golden identity, capture checks and file hashes. It does not
retain decoded HP rows, which can be rebuilt from the stream.

The repository retains shared Golden templates, versioned decoder/schema,
unit data and rendering code. Preserve unique approved artwork and narration
in the shared production source library: they cannot be recreated exactly from
battle.mp4 and frames.bin. Preserve publication IDs/settings/descriptions there
as well. Do not delete credentials or repository source files in media cleanup.

## Migration

1. Identify the reconnected external disk; inventory AoE2 Renders and relevant
   PC media. Do not touch unrelated files on the disk.
2. Map every capture and final to its campaign and variant. Validate each
   unoverlaid battle video and its matching complete frames. If a legacy run
   lacks either, report it and preserve its remaining evidence.
3. Copy using apps/video/compact_recording_archive.py. It verifies source hashes,
   capacity and destination SHA-256, refuses conflicts and never deletes sources.
4. Rebuild a representative HP timeline from only the compact files and index;
   verify start/final HP and counts, timing and media audio/duration.
5. Only then prepare a bounded cleanup manifest identifying each obsolete file,
   its verified retained replacement, absolute path, size and hash. Recheck it
   before deletion. Keep verification receipts outside the media folders.
6. Update readers/resume paths before pruning old working layouts. Existing
   recorder validation expects the expanded layout; do not prune active jobs
   or switch that validator without implementing compact-archive support.

For offline overlays, restore a disposable working folder with:
`python apps/video/materialize_compact_recording.py --index "D:/AoE2 Renders/<run>/run.json" --job <job-id> --workspace <scratch-directory>`.
Then pass the returned `live/run_001` directory to existing overlay tools.
This is an offline-render adapter, not a recorder-resume bundle. A real archived
sample reproduced the complete per-unit timeline and timing exactly; only its
source pathname differed. Evidence: data/local/compact-storage/restore-validation.json.

Regenerable overlay videos, Shorts renders, preview images, raw pre-trim MOVs,
duplicate seeds and decoded timelines can be removed after verified migration.
Never delete the sole surviving full video, raw battle or frames stream.

## Current migration status

The external WD drive has been reconnected with 272 GiB free. The previous
122-GiB bulk archive was rejected for capacity; do not run it. The new bounded
master-video migration verifies each copy then removes only the exact original
file. It is scripts/move_verified_full_videos.ps1, with receipts under
data/local/compact-storage. No recursive media cleanup has been performed.
The compact pilot regenerated every HP row and preserved the battle clock offset.
Some legacy battle videos were removed by earlier authorized retention; inventory
these as exceptions and preserve remaining evidence rather than invent raw files.
The current Champi campaign continues locally with its 8-GiB stop safeguard.
