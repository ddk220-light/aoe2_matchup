# Rebuildable recording retention

Keep irreplaceable recording sources before any render cache or expanded telemetry.

For every matchup retain a clean battle video, matching binary frame stream, and
the recording metadata describing game/video clock alignment, unit identities,
counts, civilization upgrades, and the balance policy. Compact `run.json` archives
already contain these metadata. Original plan/recording/timing files are retained
for legacy captures. Frames are telemetry and cannot recreate video imagery.

Keep the latest completed full video for each published episode, its intro art,
narration/audio sources, chapter/settings data, and upload identity. Keep scripts,
templates, fonts and referenced assets in the repository. Credentials remain in
their existing protected local storage and must not enter a public archive/index.

If clean footage is missing, preserve any surviving finished/overlaid footage.
Do not call it a clean source and do not delete it based on the existence of frames.
It may still be useful for edits or crops even when a full overlay rebuild is not
possible. Never silently substitute a different cost-policy retake.

Regenerable caches include expanded per-unit HP JSON, render-workspace timelines,
and intermediate comparison videos when all their raw inputs remain available.
An untrimmed MOV may be retired only when the intended clean battle MP4, matching
frames, and alignment metadata remain and their recorded checksums verify.

Transfers use explicit absolute source/destination roots, file-size and SHA-256
verification before removing the source, and durable receipts. Unverified copies,
conflicts, changing source trees, and low-space conditions preserve the source.
Keep at least 4 GiB free on the archive disk. Preserve old logical package paths
with junctions where appropriate; the external disk must be attached to use them.

The September 16 consolidation is described in
`data/local/storage-consolidation-20260916/PLAN.md`; `plan.json` enumerates every
candidate, and execution writes per-package checksum receipts plus `status.json`.
Preparation alone is not evidence that a transfer or deletion happened.

## Canonical knight collection (September 21, 2026)

The current knight collection is on the original WD Archives disk at
`E:/AoE2 Renders/knight-line-canonical`. Read
[KNIGHT_CANONICAL_ARCHIVE.md](KNIGHT_CANONICAL_ARCHIVE.md) for the exact layout,
known missing raw pairs, reconstruction instructions and cleanup receipts.
This consolidation merges the necessary corrections into one index per variant.
The owner authorized retiring its explicitly enumerated redundant knight files
from the PC and both disks after verification. That authorization does not extend
to camel archives, unrelated recordings or personal files.

## SAFEHOUSE transfer (September 20, 2026)

The connected archive is the Buffalo SAFEHOUSE NTFS volume, serial
`00000107000079B6`, currently `D:`. Existing contents must not be deleted or
overwritten. Never format, initialize, repartition, or suggest formatting disks.

New captures use `D:/AoE2 Renders`. The original local archive path
`data/local/AoE2 Renders` is a junction to this directory, so the already-running
knight-expansion supervisor also archives each completed civilization externally.
Its queue configuration uses the external path for subsequent launches. Do not
disconnect this disk during transfers or campaign compaction.

`apps/video/archive_camel_comparison.py --destination "D:/AoE2 Renders"`
compacts all 665 verified camel captures into nine civilization directories.
Each contains named videos, frames, and a `run.json` with reconstruction metadata.
Progress and deletion receipts are in each camel campaign's `archive-status.json`.
Only checksum-verified compact replacements permit local media removal.

Legacy frame dumps and remaining small videos use explicit plans and checksum
receipts in `data/local/storage-audit`; original file paths become symbolic links.
`scripts/move_legacy_recording_frames.ps1` fails closed on destination conflicts
or inability to create a compatibility link. Code, credentials, installed games,
Git history, and operating-system files remain local.

Earlier published archives live on the previously used external disk. A drive
letter is not disk identity: connecting SAFEHOUSE as D: does not make those older
archives available. Do not replace or delete their old junctions.
