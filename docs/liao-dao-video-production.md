# Elite Liao Dao video production

## Current continuation

The user subsequently requested the same production for Grenadier. Read `docs/grenadier-video-production.md` and continue that authorized recording/render/upload pipeline. Do not pause the shared heartbeat merely because Liao finishes: Grenadier's full video and ten Shorts also need local QA, private upload and processing verification. **Liao is complete:** full video `DTDvglypyjs` and all ten Shorts passed the final API check: eleven verified, eleven processed, zero metadata problems. The production coordinator is COMPLETE; do not restart uploads.

User authorized the full video and ten Shorts, uploaded to YouTube. Use private visibility for review, matching the existing upload workflow; preserve any later visibility changes made by the user. Channel `@aoe2matchup`, ID `UCKYN-pN4AZ3w4LpRxcdSciA`.

## Inputs and process

- Branch `codex/video-recorder-v3`, repository `C:/dev/aoe2/aoe2_matchup`.
- All 73 recordings in `aoe2lab.recorder.liao-dao-all-unique.toml` are complete and verified. Subject: **Elite Liao Dao, Khitans**. Raw MOV and gRPC frames remain untouched.
- Python `apps/video/.venv/Scripts/python.exe`, `PYTHONPATH=apps/video;.` and `PYTHONIOENCODING=utf-8`. Start subprocess helpers hidden on Windows. Inspect current process state before launching anything twice.
- Overlay workers: `apps/video/render_campaign_overlays.py --manifest aoe2lab.recorder.liao-dao-all-unique.toml --output aoe2x/js_simulation/calibration/lab/campaigns/liao-dao-all-unique-overlays --workers 3`. Status and worker logs in that output directory. Resumes successful outputs. Lock prevents duplicate drivers.
- Main pipeline: `apps/video/produce_liao_videos.py`. Status/logs in `aoe2x/js_simulation/calibration/lab/liao-video-production`. It waits for all overlays, selects ten Shorts, renders full compilation plus Shorts in parallel, and prepares eleven upload records. Initial run deliberately stops at `READY_FOR_VISUAL_QA` for agent inspection, not a user permission gate.
- If overlays finish with errors, main pipeline exits `NEEDS_ATTENTION`. Inspect each job's overlay.log and alignment-candidate.json. Never bypass alignment quality thresholds without independent measured evidence. The auto-alignment tool accepts `--sample-rate 6` or `60`, plus optional `--compact-bars` for shorter siege health bars. Retry/resume failed overlay jobs only after resolving timing.
- Rendering runner uses existing `overlay.static_stats`, `overlay.auto_alignment`, and `overlay.unit_hp`. No simulation reruns are needed for this task.

## Intro and thumbnails

`apps/video/intro/liao-dao-cloned.json` contains two untitled campaign pages, original Liao Dao artwork, previously user-authorized campaign narrator voice, and the Chinese theme. The Khitans have no preferred campaign in the installed catalog, so the established Art of War fallback is explicit in the plan.

The original artwork was generated from `apps/website/static/img/units/Elite_Liao_Dao.png` and saved as `apps/video/intro/assets/liao-dao-campaign.png`. Full and Shorts thumbnails: `apps/video/intro/thumbnails/liao-long.jpg` and `liao-shorts.jpg`, using the approved parchment, centered sketch, and name/Matchup title style.

Intro render: `lab/compilations/liao-dao-unique-units/intro-v1/liao-dao-intro.mp4` beneath `aoe2x/js_simulation/calibration/`. The two final page images have been visually reviewed: readable, no overlap or clipping. Narration is generated and cached; do not incur duplicate generation calls. Sources and provenance are in the intro plan. No credentials are stored in the plan.

## Full compilation and Shorts

- `apps/video/build_liao_compilation.py` combines intro plus all 73 overlaid matches in civilization order. Missionary ends at complete conversion. Includes embedded chapters and a description with winners and remaining HP.
- Full output: `lab/compilations/liao-dao-unique-units/final/liao-dao-complete-with-intro.mp4`.
- `apps/video/prepare_liao_shorts.py` selects from actual gRPC outcomes and recorded unit costs: most expensive infantry/cavalry/archer beaten; cheapest losses in those categories; Missionary; Flaming Camel; two other interesting matchups. Absent category outcomes get explicitly documented replacements.
- Shorts selection and outputs: `lab/shorts/liao-selected-10/`. Renderer preserves game music/audio, live HP queues, two stat panels, and Hussars footer for mixed-range battles.
- Full media must pass decoding; Shorts must pass audio, dimensions, duration <=180 seconds, and full decode validation.

## Upload and completion

After local rendering, inspect representative intro, overlay, and Shorts previews including Missionary and Flaming Camel. Record truthful evidence in `lab/liao-video-production/visual-qa.json`, with `status: passed` only when checked. Then run `apps/video/produce_liao_videos.py --upload`; it resumes local render caches and uploads the prepared batch.

Batch manifest/status/index: `lab/youtube-batch-liao/`. Unique upload keys are `liao-full` and `liao-short-01` through `liao-short-10`. Existing YouTube credentials and encrypted resumable states are in ignored `data/local/youtube`; never print their contents. Reuse keys and sessions on retries. Never duplicate earlier Tiger or Xianbei uploads.

Verify with `apps/video/check_youtube_batch.py <absolute path to lab/youtube-batch-liao/manifest.json>`. Check all eleven IDs, processing success, channel, title, description, thumbnails, and privacy. The verification file is a list of per-video results. Provide final links and local index only after the corresponding results are confirmed.

Descriptions use the established exclusions and `Try your own matchup:` with `https://aoe2matchup.com/?civ1=Khitans&unit1=elite_liao_dao_khitans&age1=Imperial`. Full intro uses synthetic-media setting true; gameplay-only Shorts false. No new user approval is required for the authorized private uploads.

## Timing fixes found during production

Houfnice and Grenadier required recovery of colored HP fills where black bar outlines merged into unit sprites; Chakram Thrower required denser samples. All three passed unchanged timing-quality thresholds after repair. The CLI now retries ambiguous default fits with six samples per second and verified colored-fill rectangles. Regression tests reject unbordered colored unit details.

Flaming Camel damage continued one gRPC frame after its last unit disappeared. `overlay/battle_end.py` retains subsequent damage before selecting the terminal frame, but does not extend a fight for idle time or healing. It is shared by new Liao descriptions, outcome selection, and Shorts trimming. Tests cover delayed explosion damage, idle/healing tails, and later wounds. Liao Dao actually defeats Missionary in this capture; the compilation now trims either side's elimination rather than assuming a conversion victory.
