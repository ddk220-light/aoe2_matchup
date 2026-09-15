# Champi handoff — 2026-09-14

**Update September 15:** The separately authorized 296 geometric-count reruns
are complete and archived. See [CHAMPI_GEOMETRIC.md](CHAMPI_GEOMETRIC.md) and the
approved default [balance policy](BALANCE_POLICY.md). The 296 standard recordings below
remain the immutable baseline. The no-further-capture note below describes the
earlier paused state, superseded only for the new geometric campaign.

## Current state

- All 296 single-arena captures verified: 74 opponents each for Incas, Mapuche,
  Muisca and Tupi Elite Champi Warrior. Zero failed final captures.
- Standard Golden templates, 27-unit cap, 5,000-resource ceiling, effective
  per-unit civilization costs. Standard mixed template retains nine P4 Spanish
  Hussars. P2 is Champi; P1 civilization matches P3 for music.
- Comp4 map/fractional-HP experiment is retired. Never restart it.
- Scheduled monitor `liao-dao-recording-progress` is PAUSED at the owner's request.
- No further capture, overlay batch or upload is requested yet. Discuss the
  Armenian comparison prototype before extending it.

## Archive and cleanup

Canonical captures are flat folders under `D:/AoE2 Renders/champi-standard-incas`,
`champi-standard-mapuche`, `champi-standard-muisca`, `champi-standard-tupi`.
Each contains 74 descriptively named `.mp4` / `.frames.bin` pairs and `run.json`.
Keep the index: it preserves timing, matchup plans, civilization costs and hashes.

All four archive copies passed checksum verification. A restored sample matched
2,544 per-unit timeline rows and timing exactly. The compact adapter is
`apps/video/materialize_compact_recording.py`; original recorder validation still
requires its expanded layout, so use the adapter for offline overlays.

Cleanup completed: 888 duplicate Champi media files removed from PC after
verification, freeing 52.43 GiB. Small metadata and diagnostic files remain.
Fifteen previously uploaded full videos moved and verified, freeing another
48.45 GiB. PC free space was approximately 93 GiB at the last check.
Receipts: `data/local/compact-storage/`; capture status:
`data/local/champi-standard-comparison/capture/status.json`.

Broader legacy disk cleanup is NOT finished. Inventory has missing-video and
ambiguous-campaign exceptions. Some older uploaded raw videos were deleted under
earlier retention rules; preserve their frames and stitched videos. Do not label
overlaid footage as raw. The old `archive_uploaded_champi_storage.ps1` bulk plan
was rejected and must not be run. Preserve unrelated Obuch/Blackwood production.

## Armenian comparison preview — awaiting feedback

Builder: `apps/video/build_champi_four_panel.py`.
Output: `data/local/champi-four-panel-review/Champi_Four_Civilizations_vs_Armenian_Bowmen.mp4`.
Sent successfully by Taildrop to iPhone172 (100.113.26.7).

- 2560x1440, 30 fps, 20.6 seconds; original Incas recording audio retained.
- Four equal portrait panels: Incas, Mapuche, Muisca, Tupi.
- Shared Armenian unit text above; each panel has civilization emblem/name,
  live per-unit HP icons/counts, Champi stats card, and timed result.
- All four lose this sample. Armenian remaining HP: 74.0%, 92.8%, 90.2%, 93.6%.
- Results use timestamped gRPC state with measured video alignment; ending panels
  hold while other battles finish, followed by a three-second final hold.
- The fixed right-hand crop (x=1280..2560) fits the opening armies. Late fighting
  approaches the left crop edge, so review a moving or wider crop before treating
  this as the final layout. This is a prototype, not an approved default.
- The builder restores archived inputs into disposable render-workspace when
  local battle.mp4 files have been pruned; saved alignment is retained locally.

The user's next task is to discuss/refine this overlay. Do not generate all 74
comparison videos or publish this prototype without that next direction.
