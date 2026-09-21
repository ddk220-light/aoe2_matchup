# Champi comparison introduction and closing page

The latest approved 74-matchup comparison is complete in
`data/local/champi-overlay-v3/Champi_Four_Civs_All_Unique_Units.mp4`.
The assembled version is `Champi_Four_Civs_Complete_With_Intro.mp4` beside it.

## Rebuild

Use the video virtual environment with `PYTHONPATH=apps/video;.`:

```powershell
apps/video/.venv/Scripts/python.exe apps/video/build_champi_comparison_intro.py
apps/video/.venv/Scripts/python.exe apps/video/build_champi_comparison_bookends.py --narration-plan apps/video/intro/champi-comparison-opening-cloned.json --page-two-narration-plan apps/video/intro/champi-comparison-observations-cloned.json --series-dir data/local/champi-overlay-v3
```

The first command renders the approved comparison still; consult its `--help`
if changing its output path. The second uses that still and the existing full
matchup video. `--stills-only` previews the first/last pages; `--assemble-only`
reuses rendered bookends using the saved assembly manifest.

Page 1 uses the Pachacuti campaign background, the existing Champi ink drawing,
and the approved generic text from `apps/video/intro/champi-comparison.json`.
Its letters follow the narration's character timestamps. The installed game
font is used. Page 2 begins with only the four emblems and column dividers;
each entire civilization column appears as that civilization's sentence starts.
The observation transcript is spoken only, not written on the page. After the
speech ends, hold the completed comparison for three seconds before battles.
The ending is five seconds with the same campaign background and a sketched
YouTube play emblem, plus “Thank you for watching.” and “Please like and subscribe.”
The Incas theme accompanies all three pages. Existing battle audio is retained.

The saved ElevenLabs key was re-enabled and verified on September 15, restoring
the authorized Pachacuti narrator. To regenerate after a script change:

```powershell
apps/video/.venv/Scripts/python.exe apps/video/generate_intro_narration.py --plan apps/video/intro/champi-comparison-opening.json --output data/local/champi-comparison-intro/narration-opening --voice-id TBChVzmvbo8N8hRVrjOI --voice-kind instant_clone
apps/video/.venv/Scripts/python.exe apps/video/generate_intro_narration.py --plan apps/video/intro/champi-comparison-observations.json --output data/local/champi-comparison-intro/narration-observations --voice-id TBChVzmvbo8N8hRVrjOI --voice-kind instant_clone
```

Supply the key securely through the process environment and verify that the
authorized Pachacuti voice profile is still available before synthesis. Never
commit keys. Page-one text must match `page1` and page-two speech must match
`page2Narration` in `champi-comparison.json`. The observations plan sets a
0.6-second lead and three-second post-speech hold. Page two reveals at 0.600,
6.196, 14.497 and 22.729 seconds in the current generation. Character alignment,
not guessed reading speed, drives those events. Re-synthesis changes timings.

## Preservation and validation

The renderer streams frames through a pipe instead of saving a PNG for each
letter. It encodes only the short bookends using NVENC. Battle video
is copied without re-encoding or crop changes. Joined audio is encoded once
with continuous sample timestamps to remove AAC packet-padding discontinuities.
All segments use H.264 2560×1440 at 30 fps and stereo AAC at 48 kHz.

Do not combine input `-ss` and `-stream_loop` for page-two music: the WAV loop
can reset timestamps and truncate mixed narration. Trim the continuously decoded
music with `atrim` and reset its timestamps before mixing. The renderer checks
that both video and audio cover the full second-page duration. Current pages
last 44.433 and 35.200 seconds; the full compilation lasts 1982.804 seconds.

`data/local/champi-comparison-intro/assembly-manifest.json` records the input
parts, durations, battle start offset, ending start, and narration state.
The source series manifest and raw recordings/frames remain available for
future overlay changes. Do not delete them when cleaning temporary previews.

Verify the page-one/page-two transition, start of battle, and ending by decoding
around the joins and inspecting extracted frames. The original 74 chapters
already passed full decode verification during the series render.

## YouTube package

`prepare_champi_comparison_upload.py --authorize-upload` is used only with an
explicit upload request. It checks all 296 opening count pairs against recording
metadata and the geometric-policy inputs, then generates private-upload settings,
the approved existing parchment thumbnail reference, chapter results, and a
description with the new intro offset. It probes actual encoded chapter lengths
to avoid cumulative frame-rounding drift. Upload with state key
`champi-four-civs-v3`; reuse that key to resume, never create a duplicate.
The package is under `data/local/champi-overlay-v3/youtube`. Its exact preparation
path is approved under the legacy cost-audit upload gate; other pending uploads
remain subject to that gate. No Taildrop is requested for this narrated revision.

## Closing illustration provenance

`apps/video/intro/assets/youtube-campaign-sketch.png` was generated with the
built-in image-generation tool using the Champi art as a linework reference.
Prompt: an isolated recognizable YouTube play-button plaque, dark sepia pen ink,
delicate crosshatching, antique history-book character, no lettering or extra
decoration. A second pass replaced the background and halo with plain white
for multiplication onto the campaign parchment. The saved project asset is
self-contained; it does not depend on the generator's output directory.
