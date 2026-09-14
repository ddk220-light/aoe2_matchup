# Flemish Militia video production

Current status: the earlier voice-slot issue below was resolved and all eleven Flemish videos completed upload/processing. Its Burgundian cloud voice was subsequently retired after preserving narration and videos. The owner now permits replacing completed campaign clones under the [standing voice policy](../apps/video/intro/voice-profile-policy.json). The dated progress notes below describe the earlier production stage, not an outstanding approval requirement.

The user authorized uploading the Flemish Militia package on 2026-09-13, following the established full-video and ten-Shorts workflow. All 73 captures are complete and validated, with no failures. The subject is Burgundian Flemish Militia, at the audited purchase cost of 30 food and 25 gold per physical unit. The approved roster excludes the subject itself; equal-resource armies have a 27-unit cap and the existing Hussar screen for melee versus ranged fights.

Raw captures, frame streams and generated media are retained under `D:/AoE2 Renders/flemish-militia`, with workspace junctions preserving the existing lab paths. The capture completion receipt is `data/local/flemish-militia-capture-completion.json`.

## Media assets

- Background: installed Burgundian Dukes campaign `wecam2`, `textures/campaign/wecam2/dukes_background.dds`; the campaign catalog maps this from the first scenario's playable civilization.
- Narrator source: `PLAY_BRG1_INTRO`, event 1095348081, action 615056596, sound 900227526, media 61744571, bank 1057199168, English `DLC1.pck`. Extracted full reference is 168 seconds; `.tools/intro-voice/burgundians/reference90.wav` is the compact 90-second voice sample.
- Music: installed `wwise/Base.pck`, media 487359100, Burgundian civilization theme, 53.844 seconds. Saved under `apps/video/intro/assets/burgundians-theme.wav`.
- Script: `apps/video/intro/flemish-militia.json`, two untitled slides, based on installed English help strings 26542 and 28343.
- Art: `apps/video/intro/assets/flemish-militia-campaign.png`, generated from the game sprite, with a clean white background for multiply compositing. The rejected intermediate checkerboard image is not used.
- Long and vertical thumbnails use `apps/video/intro/thumbnails/flemish-militia-*`. Both campaign renderers now respect real alpha channels as well as opaque artwork.

## Narration dependency

ElevenLabs rejected creating the Burgundian voice with `voice_limit_reached` (10 of 10 custom voice slots). No voice was deleted. An asynchronous question asks whether the user authorizes replacing the old Wei profile, retaining all existing audio/videos, or will increase the voice limit. Do not delete any profile without the answer. Once resolved, use `create_intro_voice_clone.py` with the reference above and `generate_intro_narration.py`; secrets belong only in the process environment.

## Resumable production

`apps/video/finish_flemish_production.py` uses the established publisher for one full video and ten Shorts, retaining private upload defaults and owner changes in Studio. It adopts the separate eight-worker overlay pass. While narration is blocked, it can assemble and validate `flemish-militia-battles-only.mp4` and render the ten Shorts. The final builder reuses completed, duration-checked battle trims after narration is ready.

Status and logs: `data/local/flemish-production-status.json`, `flemish-production.stdout.log`, `flemish-production.stderr.log`; overlays: `aoe2x/js_simulation/calibration/lab/campaigns/flemish-militia-final-overlays/status.json`. The supervisor retains the existing 15-minute thermal checks. The paused scheduled task has not been reactivated.

Before upload, inspect actual compiled-video and all ten Shorts frames, then write the final `visual-qa.json`. Do not create a passing QA receipt in advance. Verify all eleven uploads and YouTube processing before marking the package complete.

## Upload progress

All ten Shorts passed representative-frame visual review and full decode/audio validation, uploaded privately to aoe2matchup, and returned YouTube processingStatus=succeeded. Receipts: `lab/shorts/flemish-militia-selected-10/upload-completion.json`; links: `data/local/flemish-militia-upload-report.md`. The full 73-battle compilation passed decoding and representative-frame review; the intro and final upload remain blocked by the voice-slot choice. The final full-video QA gate has deliberately not been marked passed.

## Narration capacity resolved

The user approved replacing the old Wei profile. Its exact remote ID was verified before deletion; local metadata is marked retired and all saved Wei audio/video remains intact. Burgundian clone rbfHpuNWhxKqk7yqXiX5 was created successfully. Both narration pages and alignments were generated; the resulting intro is 46.1 seconds. Elite Monaspa is queued after the full Flemish upload, with 73 cost-validated matchups.
