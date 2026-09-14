# Inca Slinger video production

User requested the next full episode versus all approved unique units, with the new civilization reflected in background, narration, intro and overlay. Complete the full video and ten Shorts locally. Automatic approval review initially required fresh upload approval. The user subsequently explicitly instructed finishing publication of Inca Slinger and then producing/publishing seven further episodes in order. That new authorization is recorded in upload-approval.json. Complete media and agent QA, then upload using established private settings; no repeat approval question is needed.

## Inputs and identity

- Subject: Incas Slinger, master 185, recording slug `imp_slinger_incas`, scenario key `imp_slinger`. Website slug remains `imp_slinger`.
- New `data/recording-subjects.json` keeps this regional subject separate from the approved unique opponent roster and the existing Mapuche simulator fixture. No calibrated Inca simulation support is implied.
- Opponents: all 74 rows of `data/unique-unit-roster.json`; Slinger is not an opponent row, so there is no self-match to exclude.
- Same Lab base-cost resource convention: food + wood + gold, cap 27, cheaper army capped, expensive army floored. Slinger base cost 50 food +25 wood from reference DB row 748. Inca food discounts are not silently substituted into this existing base-cost convention. All game upgrades remain active.
- Player 2 Incas/Slinger, Player 3 opponent, Player 1 matches Player 3. Golden Hussar screening unchanged for mixed melee/ranged matches.
- Installed capture version 180059. Prefer installed data over older web patch numbers.

## Paths and commands

All paths relative to repository `C:/dev/aoe2/aoe2_matchup`.
Python: `apps/video/.venv/Scripts/python.exe`; set `PYTHONPATH=apps/video;.` and `PYTHONIOENCODING=utf-8`. Elevated environment is needed for installed FFmpeg discovery/game automation. Launch background helpers with `Start-Process -WindowStyle Hidden`, redirect separate logs. Never duplicate recorder or Shorts workers.

- Manifest: `aoe2lab.recorder.inca-slinger-all-unique.toml` (all 74 plans preflighted).
- Capture: `python -u -m aoe2x.lab.recording_campaign aoe2lab.recorder.inca-slinger-all-unique.toml --reports aoe2x/js_simulation/calibration/lab/campaigns/inca-slinger-all-unique`
- Overlay: `python -u apps/video/render_campaign_overlays.py --manifest aoe2lab.recorder.inca-slinger-all-unique.toml --output aoe2x/js_simulation/calibration/lab/campaigns/inca-slinger-all-unique-overlays --workers 2 --recording-status aoe2x/js_simulation/calibration/lab/campaigns/inca-slinger-all-unique/status.json`
- Intro plan: `apps/video/intro/inca-slinger.json`; generated voice-aligned plan `inca-slinger-cloned.json`.
- Intro render: `python apps/video/build_campaign_intro.py --plan apps/video/intro/inca-slinger-cloned.json --output aoe2x/js_simulation/calibration/lab/compilations/inca-slinger-unique-units/intro-v1`
- Resumable production: `python -u apps/video/produce_inca_slinger_videos.py` (waits for overlays; selects ten Shorts, renders full + Shorts, stops READY_FOR_VISUAL_QA).
- Selection: `apps/video/prepare_inca_slinger_shorts.py`; same six cost-based categories where outcomes exist, Missionary + Flaming Camel mandatory, extra interesting matches fill absent categories.
- Compilation: `apps/video/build_inca_slinger_compilation.py`: 74 fights + introduction =75 chapters, full decode validation, Missionary trimmed at conversion victory.
- Full output: `aoe2x/js_simulation/calibration/lab/compilations/inca-slinger-unique-units/final/inca-slinger-complete-with-intro.mp4`.
- Shorts: `aoe2x/js_simulation/calibration/lab/shorts/inca-slinger-selected-10`.
- Production status: `aoe2x/js_simulation/calibration/lab/inca-slinger-video-production/status.json`.

## Inca assets

- Campaign fcam5/Pachacuti is mapped to INCAS by parsed first-scenario Player 1 civilization.
- Installed background: `widgetui/textures/campaign/fcam5/pachacuti_background.dds`.
- Narrator: PLAY_PAC1S1 -> action 66612840 -> sound 103353070 -> media 216907757, English Base.pck bank and Base.1.pck media. Extracted WAV `.tools/intro-voice/PLAY_PAC1S1.wav` (104 seconds). User previously confirmed permission and asked to change narrator for this civ.
- Clone metadata: `apps/video/intro/pachacuti-voice-clone.json`; ElevenLabs instant clone. Reuse cached voice and synthesis; do not create duplicates. API key only in process environment, never committed or printed.
- Music: installed Base.pck WEM1032387344, exported `apps/video/intro/assets/incas-theme.wav`. Civilization identity uses community media-ID mapping at https://www.reddit.com/r/aoe2/comments/x50996/ (the WEM itself has no readable title).
- Art: `apps/video/intro/assets/inca-slinger-campaign.png`, original generated ink drawing using installed Slinger portrait as costume reference.
- Thumbnails: `apps/video/intro/thumbnails/inca-slinger-long.jpg` and `inca-slinger-shorts.jpg`, approved campaign-parchment design. Use same background/art as intro.
- Overlay theme is resolved from Incas, not Mapuche. View first finished panels and confirm Inca emblem, HP and identity.
- Intro text discusses slings in the Andes, no-gold training, bonus damage to infantry/monks/siege, and Inca upgrades without numeric claims from obsolete patches. Official rework context: https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-169123/ . Installed costs supersede that older article.

## QA and uploads

Before uploads, inspect both intro pages, encoded intro frames, first Inca overlay and representative Shorts (including Missionary/conversion and Flaming Camel), plus all render validation. Only after actual review write `aoe2x/js_simulation/calibration/lab/inca-slinger-video-production/visual-qa.json` with status passed and evidence. This is agent review, not a user-approval gate.

Fresh explicit user approval is now recorded in `upload-approval.json` with `authorized: true` in the production directory. After actual media QA, run `python -u apps/video/produce_inca_slinger_videos.py --upload`. Target @aoe2matchup / UCKYN-pN4AZ3w4LpRxcdSciA. Upload keys `inca-slinger-full`, `inca-slinger-short-01`..10; preserve prior upload IDs/state and user visibility changes. DPAPI YouTube token under ignored `data/local/youtube`. Descriptions omit the three permanently rejected disclaimers, include rules, chapter outcomes/remaining HP, relevant hashtags and Incas+imp_slinger website link. Default private.

Batch: `aoe2x/js_simulation/calibration/lab/youtube-batch-inca-slinger/manifest.json`. Verify all eleven API processing states and metadata with `apps/video/check_youtube_batch.py`; report links only when actually uploaded, distinguish processing.

## Monitoring

Use existing heartbeat `liao-dao-recording-progress` for this episode (do not create a duplicate). Notify every ten newly verified captures, meaningful completion or actionable errors; stay quiet unchanged. Preserve raw MOVs until full video and Shorts uploads are verified; afterward follow the authorized individual-video cleanup policy in docs/ordered-video-production.md. Preserve every gRPC frame file and completed full video permanently. Check disk before resuming. If recorder stops, inspect logs and reason first; existing completed jobs are cached. After all eleven Inca uploads are processed and verified, advance through data/video-production-queue.json in its exact order. See docs/ordered-video-production.md. Honor the existing fresh approval and thermal pause.

Thermal safety: before any start or resume, inspect data/local/thermal/PAUSED.json. If present, do not start/resume workers. Follow docs/thermal-monitor.md; only the user may authorize resuming after cooling.
