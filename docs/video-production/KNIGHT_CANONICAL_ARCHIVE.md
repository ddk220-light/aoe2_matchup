# Canonical knight recordings

The canonical collection is `E:/AoE2 Renders/knight-line-canonical` on the original
WD Archives disk (physical serial `WXB1A11Y1348`, volume `F274E9A2`). A drive letter
can change; verify the disk identity. Never format or repartition a disk.

Open `catalog.json` for the exact inventory and completeness flags. Each of the
17 variant folders contains named clean battle MP4s, matching binary frames,
and one `run.json` with the plans, recorded results, timing, checksums and rebuild
metadata. Keep all three: telemetry cannot reconstruct video imagery.

The selected set uses the approved current counts. Isolated count and four-relic
Leitis corrections are already merged into their variant; do not apply the old
separate correction folders again. Source selection is based on approved capture
conditions and availability, never on the winner or remaining HP.

## Known missing raw recordings

The September 21 consolidation identified **1,074 complete pairs out of 1,257
matchup records**. The unavailable originals are:

| Variant | Available raw pairs | Results preserved without raw pairs |
|---|---:|---:|
| Polish Cavalier | 35 | 39 |
| Burmese Cavalier | 2 | 72 |
| Sicilian Cavalier | 2 | 72 |
| Other 14 variants | 1,035 | 0 |

Thirty-three existing verified Polish repeats are retained because their original
raw pairs were unavailable. Their matching results and frames travel with their
videos; the earlier Polish results are preserved as historical metadata, not
silently attached to the newer footage.

`missing-recordings.json` lists the exact 183 missing pairs and their expected
hashes. Their results, original recording metadata and surviving HP samples are
retained in `run.json`, marked `metadataOnly: true` and `mediaAvailable: false`.
These records support result analysis, **not** video reconstruction. Do not claim
the entire collection is replayable and do not recapture these automatically.
Locate the original files first; a missing path is not proof that a rerun is needed.

## Rebuilding an overlay

Use the code on `codex/video-recorder-v3` in `ddk220-light/aoe2_matchup`.
The existing renderer reads a disposable workspace materialized from an index:

```powershell
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe apps/video/materialize_compact_recording.py --index 'E:/AoE2 Renders/knight-line-canonical/paladin-spanish/run.json' --job '<jobId from that index>' --workspace 'C:/dev/aoe2/aoe2_matchup/data/local/knight-render-workspace'
```

Use the exact job ID from the selected `run.json`. Materialization verifies media
checksums and preserves the video/frame relationship. Metadata-only entries stop
with an explicit missing-source error. Renderers must not launch game captures
to work around that error. Remove disposable render copies after their output
has been reviewed; keep the canonical inputs.

`rebuild-data/` contains the reference database and subject-stat snapshots used
by this recording workflow. Keep scripts, unit art, fonts and game UI assets with
the repository/game installation. Do not recalculate recorded counts or replace
these snapshots using a newer game's unit costs during an overlay-only rebuild.

## History and storage receipts

- `source-index-history.json` preserves the old indexes and recorded outcomes,
  including superseded trials, without keeping redundant raw videos.
- `maintenance/copy-receipts.json` records the source and destination SHA-256 checks.
- `maintenance/cleanup-plan.json` enumerates the specific retired files and their
  canonical replacements. Deletion receipts record the completed removals.
- `finished-videos/` retains the previously completed Paladin master. It is kept
  separately from raw battle footage and must not be substituted for a raw pair.

Cleanup is limited to the enumerated knight captures: verified copies, superseded
Paladin trials with complete replacements, and identified failed attempts with
successful replacements. Historical result metadata is retained. No recursive or
wildcard deletion is used, and no missing-source row authorizes deletion.
For an unchanged source, cleanup can reuse this transfer's source/destination
SHA-256 receipt together with the independently saved file size and modification
time. Alternate trials and sources without that proof receive a fresh hash.

The one-time transfer and cleanup status is stored on the PC under
`data/local/knight-storage-consolidation/`. `COPYING_VERIFIED` means copying is
still underway; `COMPLETE_AVAILABLE_RECORDINGS` means the available set has been
verified and redundant media removed. This status does not erase the missing-pair
limitation above. No scheduled capture or analysis task is started by this work.
