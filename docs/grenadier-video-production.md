# Grenadier video production

## Current completion and upload state

**Production COMPLETE and reported.** Full video: **s2Y0Dq7iXS4** (`https://youtu.be/s2Y0Dq7iXS4`). The final live API checks returned eleven verified, eleven processed and zero metadata problems for Grenadier, and the same for Liao. The production coordinator is COMPLETE. All local videos, raw recordings and gRPC frames are retained. Do not restart any recording, rendering or upload worker.

Completion details are in `lab/grenadier-video-production/completion.json`; the full video and ten Shorts are linked in `lab/youtube-batch-grenadier/index.html`. The app confirmed heartbeat `liao-dao-recording-progress` is **PAUSED**. If a stale heartbeat arrives, do not repeat the completion notification or launch work.

All 73 raw recordings and 73 overlays are COMPLETE, with zero failures. The full video is built: **22:07.364**, 2560x1440/60fps, 2,451,372,882 bytes, intro plus 73 matchups and 74 chapters. Full decoding passed. Recorded results are 58 wins and 15 losses; no infantry losses occurred, so the ten-Shorts selection documents an extra interesting matchup instead of inventing an infantry loss.

All ten Shorts are rendered, fully decoded, visually reviewed, uploaded privately and processed. `check_youtube_batch.py .../youtube-batch-grenadier/shorts-manifest.json` returned ten verified, ten processed, zero metadata problems. Do not upload them again with new keys. Their selection is Temple Guard, Centurion, War Elephant, War Wagon, Blackwood Archer, Missionary, Flaming Camel, Tiger Cavalry, Teutonic Knight and Cataphract.

Final visual QA is **passed** in `lab/grenadier-video-production/visual-qa.json`, including all ten Shorts, both intro pages and thumbnails, compiled-video samples at 20 and 51 seconds and ending reviews. Full description is 3468 characters and respects all exclusions. Upload logs are `lab/grenadier-video-production/upload.stdout.log` and `upload.stderr.log`. The coordinator reused the ten existing Short IDs and uploaded the full video with key **grenadier-full**. All transfers and processing verification are finished. Liao is also complete and reported.

The user requested the same end-to-end production as Liao Dao: all unique-unit matchups, a narrated campaign intro, full compilation, ten Shorts, thumbnails and private YouTube uploads to `@aoe2matchup` (`UCKYN-pN4AZ3w4LpRxcdSciA`). These uploads are authorized. Preserve any later visibility changes made by the user. No new approval is needed; local visual QA is performed by the agent.

## Capture and overlays

- Subject: **Grenadier, Jurchens**, `grenadier_jurchens`, master 1911. Player 2 always has Grenadiers; Player 3 is the opponent, Player 1 matches Player 3's civilization for music.
- Manifest: `aoe2lab.recorder.grenadier-all-unique.toml`. All 73 plans passed before capture. It is generated from the approved 74-entry `data/unique-unit-roster.json`, excluding Grenadier and including Liao Dao. Equal resources, cap 27, fully upgraded units and unchanged Golden Hussar screen for mixed ranged/melee.
- Python: `apps/video/.venv/Scripts/python.exe`; `PYTHONPATH=apps/video;.` and `PYTHONIOENCODING=utf-8`.
- Recorder: `python -u -m aoe2x.lab.recording_campaign aoe2lab.recorder.grenadier-all-unique.toml --reports aoe2x/js_simulation/calibration/lab/campaigns/grenadier-all-unique`. Initial launcher PID 31668, child 24120. Verify live process state before restarting. Parent/child Python processes are one worker, not duplicate campaigns.
- Reports, logs, preflight and status: `aoe2x/js_simulation/calibration/lab/campaigns/grenadier-all-unique/`. Every ten verified captures produces a durable milestone. Preserve raw MOV, `frames.bin`, recording metadata and `battle.mp4` under `lab/runs/grenadier_unique_*/live/run_001`.
- Overlay workers: `apps/video/render_campaign_overlays.py --manifest aoe2lab.recorder.grenadier-all-unique.toml --output aoe2x/js_simulation/calibration/lab/campaigns/grenadier-all-unique-overlays --workers 2 --recording-status aoe2x/js_simulation/calibration/lab/campaigns/grenadier-all-unique/status.json`. The optional recording-status argument gates scheduling on verified raw bundles, so overlays run alongside captures without touching incomplete files. Initial launcher PID 10336. The output lock prevents duplicates. Retry failed jobs only; preserve passed alignment and video caches.
- Do not play audio or manually manipulate the game during capture. No new simulation runs are part of this video-production request.

## Intro and thumbnail assets

Plan: `apps/video/intro/grenadier.json`; narrated plan: `grenadier-cloned.json`. Two untitled pages with character-by-character reveal, existing user-authorized campaign voice clone and Chinese-theme music. Jurchens have no mapped campaign background in the installed catalog, so use the established Art of War fallback.

The overview uses the official Jurchens civilization page and the installed DAT-derived Grenadier fixture. It describes Jurchen history, area-damage grenades, Thunderclap Bombs' later blasts and death explosion without stat tables.

Artwork: `apps/video/intro/assets/grenadier-campaign.png`. Built-in image generation, using `apps/website/static/img/units/Grenadier.png` for unit identity and the approved monochrome Liao illustration for style. Prompt: full-body Jurchen Grenadier with conical helmet, studded armored coat and spiked grenade, fine historical ink crosshatching on pure white for parchment compositing. The full and Shorts thumbnails use the approved campaign parchment composition with the new Grenadier sketch and exactly `Grenadier` / `Matchup` below it. Files: `apps/video/intro/thumbnails/grenadier-long.jpg` (1280x720) and `grenadier-shorts.jpg` (1080x1920), with PNG originals. Both generated images were visually reviewed for identity, framing and title accuracy.

Intro output: `lab/compilations/grenadier-unique-units/intro-v1/grenadier-intro.mp4` beneath `aoe2x/js_simulation/calibration/`. Narration is generated and cached: page 1 is 24.0 seconds, page 2 is 24.833 seconds. Never print credentials or regenerate identical paid requests. Initial intro launcher PID 14244. Review both slide PNGs and validate the rendered audio/video before final QA.

## Full video and Shorts

- Coordinator: `apps/video/produce_grenadier_videos.py`; status and logs in `lab/grenadier-video-production/`. It waits for all 73 overlays, selects ten Shorts from actual recorded outcomes and costs, renders full plus Shorts concurrently and writes upload preparations. Run without arguments initially; it stops at `READY_FOR_VISUAL_QA` for agent review.
- Full builder: `apps/video/build_grenadier_compilation.py`, output `lab/compilations/grenadier-unique-units/final/grenadier-complete-with-intro.mp4`. Intro plus 73 battles in civilization order; embedded chapters, winner/remaining HP, full FFmpeg decode check. Missionary clips end at elimination/conversion with later damage preserved by `overlay.battle_end.terminal_row`.
- Selection: `apps/video/prepare_grenadier_shorts.py`, output `lab/shorts/grenadier-selected-10/selection.json`. Highest-cost win and lowest-cost loss for infantry, melee cavalry and archers; Missionary and Flaming Camel; two interesting matchups, with documented replacements for categories without an eligible outcome. Use actual gRPC outcomes; do not manufacture six categories if wins/losses are absent.
- Shorts use the established crop, live HP icon queues, two stat panels, conditional Hussars footer, original game audio and 1080x1920/60fps output. Decode and audio validation is required.
- Review representative rendered frames including both intro pages, ranged/ranged and ranged/melee overlays, a mobile opponent, Missionary and Flaming Camel. Record truthful evidence in `lab/grenadier-video-production/visual-qa.json`, with `status: passed` only after inspection. No user permission gate is required.

## Upload and monitoring

After visual QA run `apps/video/produce_grenadier_videos.py --upload`. It resumes cached work, uses encrypted existing credentials, uploads eleven videos privately and verifies processing, channel, title, description and thumbnail. Unique keys: `grenadier-full` and `grenadier-short-01` through `grenadier-short-10`. Batch files/index/verification: `lab/youtube-batch-grenadier/`. Reuse these keys and resumable sessions; never duplicate uploads. A saved video ID alone does not mean processing succeeded.

Website link: `https://aoe2matchup.com/?civ1=Jurchens&unit1=grenadier_jurchens&age1=Imperial`. Keep the user's description exclusions: no AI-narration paragraph, no one-trial disclaimer, no preselected-unit phrase. Full intro synthetic-media setting is true; gameplay-only Shorts false. Privacy is private initially, Gaming category, not made for kids.

The existing heartbeat `liao-dao-recording-progress` should monitor this production. **Liao is now complete:** full ID `DTDvglypyjs`; the final batch check returned eleven verified, eleven processed, no metadata problems, and its coordinator is COMPLETE. Do not restart its uploader. Notify Grenadier milestones every ten verified captures, actionable failures and final video links; stay quiet on unchanged state. Pause the heartbeat only after Grenadier's eleven uploads are processed, verified and reported.

Grenadier's intro is now complete and passed full decode, audio and 48.833-second duration checks; both pages were visually reviewed. See its `intro-v1/validation.json`. Preliminary overlay reviews and last reported capture milestone are in `lab/grenadier-video-production/review-progress.json`; these are not final Shorts/compilation approval. Initial production coordinator launcher PID 28100, child 32352. It will stop at READY_FOR_VISUAL_QA, at which point the monitoring agent must inspect final artifacts, record truthful visual QA and resume with `--upload`.
