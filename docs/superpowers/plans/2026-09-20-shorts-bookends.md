# Animated matchup Shorts implementation plan

**Goal:** Deliver one Blackwood Archer vs Huskarl Short and Taildrop it to the user's iPhone.

**Architecture:** Keep the approved vertical battle render as the overlay/timing source. Extract clean gameplay from the raw recording using its saved telemetry camera, enhance that viewport with the installed SeedVR2 Sharp model, and replace only the gameplay rectangle. Compose animated opening and closing screens from existing game assets. Never modify the recording or simulation.

**Tech stack:** Python, Pillow, OpenCV, existing game assets, local SeedVR2 CLI, FFmpeg, Tailscale.

**Specification:** The user's three-screen sketch. Three-second opening includes a smooth final 0.6-second upward/downward split. Opening has attack GIFs and names, no HP queues or stat cards. Full battle follows without hidden opening combat. Three-second ending uses the top unit's result and attack animation, preserving bottom stat cards. Blackwood Archer is the top/featured unit. Original battle sound starts with combat; no narration or invented music. 1080x1920 at source 60 fps.

**Constraints:** No push/deployment, no simulation reruns, no source deletion, no model substitution. Use SeedVR2 Sharp with LAB matching, zero added noise, seed 42, 75/25 model/source blend. Stream enhancement in bounded chunks. New media stays under ignored `data/local/`.

## Tasks

1. Add focused failing tests for split direction/reveal, GIF frame duration/looping, top-side result, and retention of footer cards.
2. Implement a separate reusable story-Short compositor and clean camera extraction command. Preserve the existing renderer's defaults.
3. Extract clean 1080-square footage; smoke-test SeedVR2 at true 2x (2160 square), then render the whole battle with temporal context and bounded chunks. A smaller temporal batch is acceptable if needed for full-resolution memory.
4. Compose intro, enhanced battle and ending. Inspect representative frames and check complete decode, duration/frame count and audio. Run only focused tests.
5. Taildrop the finished MP4 to the user's iPhone, report actual transfer outcome. Record exact commands/settings and output manifest.

## Completed 2026-09-21

- Added the opt-in story renderer, reusable bookend helpers and documentation;
  the existing battle renderer's defaults are unchanged.
- Five bookend tests and eight camera tests pass. A failing exact-frame-boundary
  test caught and fixed fractional-second accumulation in 20 fps GIF playback.
- Full SeedVR2 run completed all 1,093 frames in 16 chunks (4,163.12 seconds).
- Finished MP4: 1,453 frames, 1080x1920 at 60 fps, 24.216667 seconds, H.264 and
  stereo AAC. Full video/audio decode passed. Audio correlation against the
  source after the three-second offset was 0.998775.
- Inspected opening, split transition, mid-battle and ending previews.
- Taildrop confirmed the finished file sent to the user's iPhone at 00:03:45
  local time on 2026-09-21. No push, deployment or simulation rerun.
- Media, logs, settings and verification evidence remain under ignored
  `data/local/video-recreate-blackwood-20260920/story-short-seedvr2/`.

## Requested revision, 2026-09-21

Keep the approved battle, camera, Seed frames and three-second ending. Revise
only the bookends and continuous audio. The user confirmed full-width gray
result backing and the simple label `44% HP` (300 / 675 starting army HP).

- [x] Add focused tests for starting-army HP percentage, full-alpha PNG animation
  playback, full-width result backing, and audible bookend audio with combat
  remaining aligned at three seconds.
- [x] Rebuild these two attacks from their native x2 SLDs, using existing
  alpha-aware upscaling helpers and local HAT Sharper weights. Keep aligned
  canvases and original attack cadence; blue Blackwood, red Huskarl. Save lossless
  PNG frames instead of GIF palette/one-bit alpha.
- [x] Refine the existing compositor with textured iron panels, angular corner
  brackets, a shield-shaped VS treatment and subtle animated glints. Keep the
  smooth split reveal. Remove the narrow result backing; put the ornament and
  percentage on one full-width band. Retain the bottom cards.
- [x] Reuse cached clean gameplay and all Seed frames from the previous output
  through explicit cache arguments. Save a separate revision, never overwrite v1.
  Carry recorded post-battle soundtrack into the opener and retain source audio
  through the full ending; no new music, narration, or paid generation.
- [x] Run focused tests, inspect opening/ending/motion previews, encode and fully
  decode the revised MP4, check HP/timing and audio coverage, and Taildrop it.

Implementation stays in `build_story_short.py` and `overlay/shorts_story.py`,
with one narrow attack-asset preparation script. The comparison renderer only
gains an optional transparent-backing switch; its default output stays unchanged.
No simulation, source recording, production, push, or broad test run.

Revision verification: 19 focused tests passed; full FFmpeg decode passed;
1,453 frames at 60 fps, 24.216667 seconds, stereo AAC covers 24.216 seconds.
Audio correlation after the intro is 0.999408; every one-second audio block is
audible, including the ending. Battle preview frames 0/546/1092 are byte-identical
to v1. The read-only review found no actionable correctness issues. Final v2
media and evidence are in `data/local/video-recreate-blackwood-20260920/story-short-medieval-v2`.
Taildrop confirmed v2 sent to the user's iPhone at 10:21:21 local time on
2026-09-21. Nothing was pushed.

## Game-image revision, 2026-09-21

The user rejected bright neon-like lines and blue/red gradient backgrounds,
and requested existing game images for backgrounds and borders.

- [x] Inspect installed artwork and select the timber/parchment menu background,
  bronze frame image and original ornamental menu header for VS.
- [x] Add a failing corner-preservation/transparency test, implement image frame
  composition using the existing nine-slice helper, and confirm it passes.
- [x] Replace both cinematic backgrounds, synthetic borders, shield and glint
  effects. Keep approved sprites, split opening, audio, HP fraction and battle.
- [x] Encode a separate v3, verify media and unchanged battle previews, and send
  it to the user's iPhone. No source/cache overwrites or pushes.

Only `build_story_short.py`, its small helper/test and workflow documentation
change for this revision. Outputs: `data/local/video-recreate-blackwood-20260920/story-short-gameart-v3`.

V3: 20 focused tests passed; full video/audio decode passed; 1080x1920, 60 fps,
1453 frames, 24.216667 seconds. Decoded audio exactly matches v2 and checked
battle previews 0/546/1092 are byte-identical. Taildrop confirmed sent to the
iPhone at 11:19:03 local time on 2026-09-21. No push.

## Face, circular VS and winner-only revision, 2026-09-21

This supersedes the original top-unit result perspective. Keep the approved
game backgrounds, battle, camera, Seed cache, audio and three-second holds.

- [x] Compare native RGB, team mask, tint and HAT output. Replace binary full-tint
  selection with continuous BC4-mask blending in the story asset preparation
  only. Preserve native skin/paint; lift existing Blackwood shadow detail with
  a hue-preserving gamma 0.6 curve before HAT. Do not invent a face or change
  the shared graphics builder. Rebuild the two lossless attack loops.
- [x] Put VS in the actual bronze medal's circular rim with game parchment inside;
  remove its low-alpha padding before resizing so the circle stays circular.
- [x] Composite the full-width result band at 140/255 opacity; retain background
  texture beneath it and the original game victory ornament above it.
- [x] Feature the actual P2/P3 winner's name, civ, animation, remaining HP fraction
  and victory sign. P4 never contributes. No losing-side "Defeated" ending.
- [x] Add focused regression checks for partial mask colors, hue/alpha retention,
  visible background and both possible winners. 24 story/camera tests pass.
- [x] Inspect and fully verify the separate v4 MP4, unchanged battle/audio and
  final delivery. Taildrop the verified revision to the same iPhone.

Read-only review caught the medal's transparent padding distorting its shape;
the crop and lettering were corrected and the reviewer found no remaining
actionable issues. Media stays under ignored
`data/local/video-recreate-blackwood-20260920/story-short-gameart-v4/`.

V4 verification: 24 focused tests pass; full video/audio decode passes. Output
is 1080x1920, 60 fps, 1,453 frames, 24.216667 seconds. Decoded audio is identical
to v3, and battle previews 0/546/1092 are byte-identical. Inspected four corrected
attack poses, opening, circular badge and translucent ending. Taildrop confirmed
the MP4 sent to the iPhone at 12:33:22 local time on 2026-09-21. No push.

## Floating battle overlay revision (v5), 2026-09-21

**Goal:** Same Short, with sliding stat cards, translucent top/bottom fades,
special effects and effective resource costs, and a plain victory footer.

**Architecture:** Keep the exact enhanced square and smooth camera in the center.
Extend the same frame as a blurred full-height backdrop behind transparent HUD
layers. A new `overlay/shorts_battle.py` owns the transparent queues, neutral
scrims, card entrance and footer. `static_stats.panel` gets opt-in card details;
other renderers retain their defaults. The story compositor uses those layers
and the existing v4 attack/audio caches. No new simulation or model runs.

### Task 1: Rich stat cards

Files: `overlay/static_stats.py`, `tests/test_shorts_battle.py`.

- [x] Add and observe failing checks: `effective_cost(side)` must return the
  recorded `effectiveCost`, never base price; Blackwood 0/17.5/22.5, Huskarl
  53/0/25. `special_effects(unit)` includes `Poison damage` for its recorded
  positive bleed effect and retains existing effect notes.
- [x] Add opt-in `panel(..., details={...})`: green effects below the horizontal
  line, then a cost row using installed food/wood/gold stat icons. Per the user's
  follow-up, show only nonzero resources and no "Per unit" label. Use a 390px
  source card so two notes and costs fit; 510px-wide delivery fits the footer.
- [x] Run focused tests and inspect both cards at delivery size.

### Task 2: Floating overlay and integration

Files: new `overlay/shorts_battle.py`, `build_story_short.py`,
`tests/test_shorts_battle.py`, `SHORTS_CAMERA.md`.

- [x] Write failing checks for transparent scrim centers/15%-opacity ends, retained
  central gameplay pixels, and cards offscreen at t=0 / settled at t=0.65 with
  monotonic opposing slides. A small red/blue card fixture verifies the actual
  compositing result, not just a position calculation.
- [x] Build `battlefield_canvas`, `readability_scrim`, `slide_cards`, and
  `BattleOverlay`. Reuse the verified HP timeline and original identity packing;
  rebuild these on a transparent layer instead of keying black out of video.
- [x] Integrate the overlay with cached Seed frames. First battle frame has
  offscreen cards; the first 0.65 seconds brings them in smoothly. Preserve
  three-second bookends and audio. Victory uses settled updated cards over plain
  warm parchment rather than a black footer.
- [x] Run the story, camera and new overlay tests only. Render v5 to a new local
  folder and inspect entrance/card previews. The user's correction below
  superseded this draft before delivery; final media checks and Taildrop move
  to v6 rather than sending the rejected blurred-backdrop treatment.

No push, deployment, shared graphics regeneration, source/cache deletion,
production database changes or broad hardening. Inline implementation continues
in the existing feature checkout with its uncommitted v4 work preserved.

### User crop correction and opening labels (v6)

The v5 draft was rendered but not delivered. The user rejected a blurred video
extension: the overlay must float on actual battlefield footage. Keep all card,
cost and 15%-opacity refinements, but replace the background composition.

- [x] Replace the blurred extension with a single aspect-preserving portrait crop
  from the existing 2160-square enhanced frames, before any final downsample.
  Preview at 1080x1680 with plain 120px top/bottom bars; also expose bar-height 0
  for edge-to-edge framing. The user was offered the two framing choices; the
  small-bar option is the stated preview assumption while awaiting preference.
- [x] Remove Elite/Heavy from opener names only, replace the separate civ label
  with the actual civilization emblem immediately before the name, and fit each
  complete label on one centered line. Keep all other game-art bookends.
- [x] Verify focused crop tests (one sharp image, no stretching/blurred extension)
  and title shortening; inspect first/mid-battle and opener drafts. 38 focused
  checks pass before the final media verification.
- [x] Render v6 and inspect previews. User rejected the resulting army occlusion;
  withhold delivery and supersede this draft with the protected framing below.

### Protect the approved battle viewport (v7)

Root cause: aspect-fill into a taller viewport enlarged the whole square by
1680/1080, putting the starting Huskarl formation behind the unchanged cards.
The user wants the original battle framing kept clear while cards cover scenery.

- [x] Keep the approved enhanced square at x0/y330/1080x1080, unchanged in scale,
  content or camera motion. Apply that same camera transform to the synchronized
  full recording to reveal only genuine adjacent terrain. Use black outside
  recording bounds; no blurred or repeated extension and no extra aspect-fill.
- [x] Keep header, cards and even the 15%-opacity fades entirely outside the
  protected battle rectangle. Test its pixels remain untouched during entrance,
  settled cards and late battle; test actual source pixels at multiple zooms.
- [x] Inspect actual frames 0/39/546/1092 before encoding: protected region is
  pixel-identical to the original enhanced square. Audit all 183 telemetry
  observations: living-unit centers span y352.69..1374.62, with zero intersections
  with header<320 or cards>=1435. 39 focused tests pass.
- [x] Render v7; verify final media, opening, card entrance, unobstructed battle,
  ending and unchanged audio. Taildrop this corrected version only.

V7 final verification: 39 focused tests passed; full video/audio decode passed.
1080x1920, 60 fps, 1,453 frames, 24.216667 seconds. Decoded audio is byte-identical
to v4. Protected battle interiors at frames 0/546/1092 match v4 exactly; full
pre-encode protected squares at 0/39/546/1092 also match the enhanced input.
Reviewed final intro, slide midpoint, first/middle/late battle and updated ending.
Read-only review found no actionable issues. Taildrop confirmed sent to iphone172
at 14:10:44 local time on 2026-09-21. Nothing was pushed or deployed.

## Full-background victory ending (v8), 2026-09-21

The user requests only an ending revision. Keep all approved opener and battle
pixels, animation, camera, framing, cards and audio timing unchanged.

- [x] Test the five-second/shorter-cue duration, full-height game-art ending without
  cards or bottom details, website message, and exact victory-audio start.
- [x] Extend the existing game background and border to 1080x1920. Keep the actual
  winner's animation/sign/HP and replace the old footer with "Visit
  aoe2matchup.com for more simulations." No stat cards on this screen.
- [x] Use the installed game's `Play_Victory` cue: Base.pck bank 232745270,
  event 2453267296 -> action 730600277 -> container 476172815 -> sound 31516768 ->
  embedded Vorbis media 149728724. Decoded length is 5.5 seconds; use five seconds
  with a brief final fade. Start it at the first ending frame, replacing combat.
- [x] Render a separate v8 using all existing caches. Check focused tests, media
  decode, duration, unchanged opener/battle, ending layout and audio, then Taildrop.

Use the existing extraction helpers and a portable official vgmstream decoder;
local media/tools stay in ignored `data/local/`. No game or model run, push,
deployment, source/cache deletion or unrelated code changes.

V8 verification: 40 focused tests pass; complete video/audio decode passes.
1080x1920 at 60 fps, 1,573 frames / 26.216667 seconds. Ending starts at 21.216667
seconds and holds 300 frames / five seconds. Both intro previews and battle
previews 0/20/39/546/1092 are byte-identical to V7. Decoded intro/battle audio is
byte-identical through 21.116667 seconds; the ending's decoded victory cue has
0.999862 correlation against the extracted original. Inspected the full ending
layout and the encoded frame at 22 seconds. Read-only review found no actionable
issues. Taildrop confirmed V8 sent to iphone172 at 14:40:00 local on 2026-09-21.
Evidence is in `data/local/video-recreate-blackwood-20260920/story-short-gameart-v8/`.
Nothing was pushed or deployed.
