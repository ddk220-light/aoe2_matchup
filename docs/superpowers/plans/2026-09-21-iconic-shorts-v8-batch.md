# Ten iconic V8 Shorts implementation plan

> **For agentic workers:** Continue the approved video workflow inline; use focused
> parallel read-only source recovery and code review. The user requested production
> of the ten selected Shorts, not a new design approval or a Git integration.

**Goal:** Render the ten selected matchups in the approved V8 format, verify the
actual results, and deliver the finished videos locally and to the user's iPhone.

**Architecture:** A fixed ten-entry batch manifest identifies exact archived
recordings. Stage disposable local inputs, decode the existing telemetry/alignment,
derive the existing monotonic camera, run the approved local SeedVR2 Sharp 2x
preset, and compose the existing V8 layers. Retain source and intermediate files.

**Tech Stack:** Existing Python/Pillow/OpenCV/SLD decoder, HAT sprite upscale,
SeedVR2 standalone CLI, FFmpeg, and Taildrop.

**Spec:** User-approved V8 in `apps/video/SHORTS_CAMERA.md`, plus the ten-matchup
shortlist immediately approved in the conversation on 2026-09-21.

## Global constraints

- Three-second split opener; civilization emblem and short unit name in one line.
- Protected 1080-square battle at y330, smooth one-direction pan and zoom-in only.
- Floating 15%-maximum-opacity readability fades; opposing 0.65s card entrance.
- Correct discounted nonzero resource prices, green special effects, no cost label.
- Winner-only full-background ending, no cards/footer; website CTA and actual
  `Play_Victory` audio, five seconds or shorter if cue shorter.
- SeedVR2 7B Sharp, 1080->2160, 75/25 enhanced/source blend, LAB matching, seed42,
  no added noise, original 60fps and game audio. No silent model substitution.
- Preserve each capture's balance/P4/relic setup and disclose it. No production
  writes, uploads to YouTube, pushes, source deletion, or broad test suites.

## Task 1: Exact input inventory

- [ ] Locate and verify unoverlaid source video, frames, plan, and timing for all ten.
  Never call an old overlaid compilation raw footage. Record missing-source entries.
- [ ] Stage available captures under `data/local/iconic-shorts-v8-20260921/sources`.
  Use `materialize_compact_recording.materialize` for compact archives; copy only
  required input files and verified alignment for expanded captures.
- [ ] Decode HP/positions with `overlay.unit_timeline.decode`, verify terminal
  winner, and build camera and exact frame manifest using existing helpers.

## Task 2: Reuse V8 for multiple units

Files: `apps/video/build_story_short.py`, `apps/video/prepare_story_attacks.py`,
`apps/video/tests/test_shorts_story.py`, and a narrow batch entry point.

- [ ] Add a failing test that two non-Blackwood unit names produce the corresponding
  output filename, not the single-demo hardcoded name. Implement that naming only.
- [ ] Expose explicit sprite source/color entries to the existing native-mask/HAT
  asset preparation function. Keep its approved default Blackwood/Huskarl behavior.
- [ ] Add only the selected units' missing special-effect notes and show the explicit
  four-relic Leitis setup. Test the notes and effect/price card contract.
- [ ] Run the focused story, card and camera checks; inspect new bookend/card previews.

## Task 3: Generate and verify

- [ ] Prepare clean crops with `build_story_short.prepare` for each available entry.
- [ ] Run the established SeedVR2 CLI preset serially on the GPU; reuse completed
  outputs when resuming this fixed batch. Preserve per-entry logs and status.
- [ ] Compose with `build_story_short.render` and the existing decoded victory WAV.
- [ ] Check media dimensions/frame count/audio/full decode, beginning/middle/end
  previews, winner/HP/costs/effects, and camera clearance before delivery.
- [ ] Taildrop verified finished files and record successful transfer receipts.

Missing source footage is a separate input issue, not permission to fabricate a
battle, substitute opponents or reprocess old opaque overlays into the new format.

## Progress — 2026-09-21

- Six sources verified, staged, HP-aligned, camera-prepared and visually preflighted.
- Four raw videos not found in either archive copy. User declined re-capture;
  existing recordings only. Direct E: recheck confirmed telemetry folders and
  older overlaid exports, but not the missing originals. Keep those four on hold.
- Generic names, native/HAT attack selection, selected effect notes and four-relic
  disclosure implemented. 43 focused checks pass; read-only review found no
  Critical/Important issue for the six prepared sources.
- Obuch/Teutonic Knight enhancement is active. The remaining five have a hidden
  serial queue that starts only after the first export's automated media checks.
- Final enhanced video checks, visual/motion review and Taildrop remain pending.
  This batch has not been marked complete, published or delivered.
