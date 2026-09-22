# Approved ten Shorts execution plan

> **For agentic workers:** Execute the approved rendering recipe task by task;
> use the existing voice-extraction subtask independently of local composition.

**Goal:** Deliver all ten planned recordings as complete v15-format Shorts.
**Architecture:** Reuse each approved composited battle, including corrected
Teutonic camera and existing Seed outputs. Generate only dynamic intros, two
seconds of recorded aftermath, exit transition, and winner ending. Reuse the
already-approved Grenadier/Huskarl v15 exactly. Keep all prior exports.
**Tech stack:** Existing Python/Pillow/OpenCV render helpers, FFmpeg, local
Compact Real-ESRGAN for new aftermath frames, installed native audio/assets.
**Spec:** `docs/video-production/SHORTS_APPROVED_WORKFLOW.md`.

## Constraints

Use only the ten entries in `data/local/iconic-shorts-v8-20260921/batch.json`.
Do not capture, simulate, upload, push, replace recordings or rerun SeedVR2.
Output into a new `final-v15` subdirectory; keep recorded P2/P3 ordering.
Audio timing derives from the two animations and spoken responses. Hold the
last pose when a response is longer than its attack. Keep the 0.2s handoff,
one-second last-turn-to-battle gap, 2s aftermath, 1.2s exit, full 5s hold,
and 0.7 victory gain. All local code edits use apply_patch.

## Tasks

- [x] Locate the ten previous exports, native attack caches and staged sources;
  all exist, all recordings have at least two seconds of real aftermath.
- [x] Prepare native command voices in `final-v15/voices/catalog.json` using
  unit DAT events and installed Wwise civilization switches, measuring all
  variants and retaining the longest valid line for each unit/civilization.
  User selected same-civilization spoken attack lines for mounted units on
  2026-09-22; selected substitutions retain both event IDs in provenance.
- [x] Add a local `test_final_batch.py` smoke check for real FFmpeg frame
  splicing, fail before the new splice helper exists, then implement it in
  `render_final_batch.py`. Verify that old intro/ending are excluded and the
  original battle frames remain in order between the new segments.
- [x] Build and inspect one complete export, then render the remaining eight
  and retain an exact copy of the approved tenth. Reuse existing BattleCamera,
  BattleOverlay, intro/ending drawing, native shadows and audio-filter helpers.
- [x] Run whole-file media checks plus timing/audio and frame comparisons;
  inspect actual-MP4 contact sheets for all ten. Record hashes and deliver a
  review index with playable links. No publication or phone transfer.

Completed 2026-09-22: all ten exports are indexed at
`data/local/iconic-shorts-v8-20260921/final-v15/REVIEW.md` with per-file media,
timing, voice, hash and visual-review evidence. The Xianbei spoken response's
extra silent tail was removed; the final exported audible handoff is 0.212s.

## Verification commands

From the repository root, using `D:/miniconda3/python.exe` and the existing
`run_batch` environment initializer:

```powershell
& D:/miniconda3/python.exe data/local/iconic-shorts-v8-20260921/test_final_batch.py
& D:/miniconda3/python.exe data/local/iconic-shorts-v8-20260921/render_final_batch.py --numbers 1
& D:/miniconda3/python.exe data/local/iconic-shorts-v8-20260921/render_final_batch.py --numbers 2 3 4 5 6 7 8 9 10
```

The driver writes per-output `story.json`, `voice-provenance.json`, media
verification, actual-video contact sheets and a batch status. Review remains
pending until those images are actually inspected; do not label copied user
approval as approval of the nine new exports.
