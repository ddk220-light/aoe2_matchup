# Video pipeline owner's guide

Written 2026-11-18 by Claude after a code-level read of the whole pipeline
(main checkout `C:\dev\aoe2\aoe2_matchup`, branch `codex/video-recorder-v3`
**plus its uncommitted working tree**). Every rule below was checked against
code, not just other docs. Where the existing docs disagree with code, the
[drift register](#7-doc-drift-register) says which one wins.

Use this as the map. The [production runbook](../VIDEO_PRODUCTION_RUNBOOK.md)
and the per-topic guides in this folder are still the step-by-step procedures;
read them for exact commands, but trust this file's corrections where they
conflict.

---

## 0. Read this first: repository state

| Fact | Consequence |
|---|---|
| **The golden branch is `video-recorder-v3`** (owner decision, 2026-11-18). It is `codex/video-recorder-v3` (including the 6 Sept 22–24 asset/doc commits) plus the previously uncommitted Sept 22 – Oct 8 pipeline work, the map/AI inputs, and this guide. Do new video work there. | `codex/video-recorder-v3` is historical. `origin/main` has ~480 later website commits and has never been merged with the video work; expect conflicts when it is. |
| **The branch holds logic, not run history** (owner rule, 2026-11-18): code, catalogs, databases, Goldens and map/AI inputs, and instructions. Past runs (plans, queues, status, result indexes, rankings output, logs, media) live on the recording share. | Never commit campaign folders from `data/local`. Only the exact allowlist in `.gitignore` is tracked; see [data/local/README.md](../../data/local/README.md). |
| A fresh clone needs game-derived data regenerated: `python -m aoe2x.extract.run` (→ `data/inputs/extracted_data/`), `python scripts/audit_installed_dat.py`, `python scripts/cache_installed_dat.py`. | See [§9](#9-redo-a-run-on-a-fresh-machine). Without the extraction, 2 more cost tests fail. |
| The older Claude-era pipeline (`ddkMatchupAI`, `apps/video/sim_v2`, `build_civ_copies.py`) lives on branch `aoe2_ai_for_simulation`. | It is not an ancestor of the Codex branch. The current Goldens use `NoneAi`; don't mix the two systems. |
| Machine-local, never in Git: the game, `apps/video/.venv`, gRPC mTLS certs (`aoe2x/grpc/*.pem,*.key`), YouTube tokens (`data/local/youtube/tokens.dpapi`), the ElevenLabs key (`data/local/elevenlabs.dpapi` or `ELEVENLABS_API_KEY`), all recordings. | A fresh clone cannot capture, narrate, or upload. See [Setup and data](SETUP_AND_DATA.md). |

Lab root (runs, campaigns, compilations, Shorts):
`aoe2x/js_simulation/calibration/lab/`. Completed-run archive (since Oct 1):
`\\100.123.128.35\AoE2-Incoming\<subject>\...` (Dragonstar share).

---

## 1. What the pipeline produces

There are three product types. They share capture and overlay code, but they
differ in planning and editing.

| Product | What it is | Example | Main builders |
|---|---|---|---|
| **Unit episode** | One subject unit vs the whole unique-unit roster (76 opponents today). Full video (~25 min, chaptered) plus 10 Shorts. | Elite Monaspa (73 chapters, 26:49) | `scaffold_video_episode.py` → `build_<key>_final.py`, `prepare_<key>_final_shorts.py`, `finish_<key>_production.py` |
| **Civ comparison series** | One unit family across 4+ civs vs a shared opponent set. Four-column chapters, a ranking, and top-N highlight lists. | Champi, Knight/Cavalier/Paladin, Camel | `build_champi_comparison_overlay.py`, `build_knight_comparison_series.py`, `report_knight_line_rankings.py`, `prepare_*_comparison_upload.py` |
| **Shorts** | 1080×1920 single matchups chosen by recorded outcome. | 10 per episode | `build_vertical_short.py`, `render_selected_shorts.py` |

Status at writing (`data/video-production-queue.json`): 14 episodes complete,
`elite-obuch` has captures complete but no media. The newest work is the
**standard-unit 5-repeat Arena/Donut campaign** (Jomsviking, Hearth Troop, Jarl,
Varangian/Viking Guard, Danish Heavy Mounted Crossbowman, Chinese Halberdier
and Elite Fire Lancer as opponents). It is capture-only so far: no overlays or
uploads.

---

## 2. End-to-end flow

```
 roster + subjects + cost catalogs ──► PLAN (Node worker, hashed) ──► scenario from Golden
        data/*.json                     aoe2x/lab/planner.py            apps/video/build_run.py
                                        aoe2lab_worker.mjs plan         + live._validate_scenario
                                                                              │
 ┌────────────────────────────────────────────────────────────────────────────┘
 ▼
 CAPTURE (one game, one driver, mutexed)        EVIDENCE
 orchestrate_matchup: load → Test → ffmpeg  ──► gRPC Frames stream → .frames.bin
 ddagrab+NVENC, END file or WINS banner         redecode → hp.json; live.py validates counts/winner
                                                 recording.json (sha256 inventory) → campaign "verified"
                                                              │
       ┌─────────────────────────┬────────────────────────────┼───────────────────────────┐
       ▼                         ▼                            ▼                           ▼
 optional V3 sim lane     OVERLAY per battle           RANKING (comparison series)   archive to share
 5 seeds, MATCH report    static panels + HP align     report_knight_line_rankings   copy_*_to_share
 (diagnostic only)        + live HP queue render       → RANKING/HIGHLIGHTS
                                 │
       ┌─────────────────────────┼──────────────────────────┐
       ▼                         ▼                          ▼
 INTRO + COVERS            FULL COMPILATION             SHORTS (10)
 campaign backdrop,        concat, chapters, trim,      outcome-based selection,
 ElevenLabs clone, music   full decode check            vertical render
       └─────────────────────────┴──────────────────────────┘
                                 ▼
                 QA contact sheets → human review → visual-qa.json
                                 ▼
                 YouTube: OAuth → resumable upload → thumbnail → processing poll
                                 ▼
                 upload-completion.json, release report, archive
```

---

## 3. Stage by stage

### 3.1 Plan: subject, roster, costs, counts

**Rosters.**
- [`data/unique-unit-roster.json`](../../data/unique-unit-roster.json) holds 77 opponents (42 melee, 28 mobile_ranged, 7 siege_ranged), sorted by (civ, label). The Viking Sagas units (Jomsviking 2712, Hearth Troop 2706, Jarl 2709) are in the uncommitted diff.
- [`data/recording-subjects.json`](../../data/recording-subjects.json) holds 69 subjects that are not opponents: standard, regional and naval units.
- **Opponent set** = roster minus the subject's slug, sorted by casefolded (civ, label) ([`scaffold_video_episode.py:33-53`](../../apps/video/scaffold_video_episode.py)). Naval units, Flaming Camel, Mounted Trebuchet and Missionary are rejected as subjects.

**Costs.**
- [`data/recording-costs.json`](../../data/recording-costs.json): 161 `civ|slug` entries, `costBasis: fully_upgraded_imperial_v1`. Each entry has base, purchase, unitsPerPurchase and effectiveCost per physical unit, an effect trace, and a `releaseAudit` block (DAT sha).
- Lookup fails closed: there is no fallback to base cost ([`recording-costs.js:10-17`](../../aoe2x/js_simulation/src/recording-costs.js)).
- Special cases:
  - Blackwood Archer is trained in pairs, so the purchase is divided by 2.
  - Karambit is 1 per purchase, even though its population is 0.5.
  - Saxon masters 2703–2706 get ×0.8 at the maximum of 4 TCs/Castles ([`aoe2x/dbgen/conditional_costs.py`](../../aoe2x/dbgen/conditional_costs.py), uncommitted). Owner policy (Sept 22) is to always assume the maximum conditional discount.
- ⚠ The regeneration script the docs point to, `scripts/audit_recording_costs.py`, **lacks the civ tech-tree stage and the Saxon discount, and rewrites the whole catalog, dropping `releaseAudit`**. The newer path is `scripts/audit_installed_dat.py` plus the `prepare_*` helpers. Don't regenerate costs with the old script.

**Army sizes: current default `geometric_full_discount_weighted_resources_v3`**
([`recording-balance.js:48-95`](../../aoe2x/js_simulation/src/recording-balance.js),
[`balance.py:3-5`](../../aoe2x/lab/balance.py)):

```text
cost      = food + 0.9·wood + 1.1·gold      per physical unit, all discounts in full
cheaper   = 27
expensive = max(1, floor(27·sqrt(cheapCost/expensiveCost) + 0.5))
```

`27·√r` is the **geometric mean of equal-count (27) and equal-resources (27·r)**.
Population is fixed at 1 per physical unit; the game's population value is
recorded but not used. There is no resource ceiling unless a request sets
`maxResources`. Water maps cap at 15.

History, kept so that old plans re-validate:

| Policy | Score | Notes |
|---|---|---|
| v1 `geometric_shared_discount_v1` (Sep 15) | cost × game population | shared units' food/wood discounts at 50% |
| v2 `..._unit_count_v2` (Sep 20) | cost, population 1 | same 50% rule, weights 1/1/1 |
| **v3 (uncommitted, Sep 22+)** | cost, population 1 | weights 1/0.9/1.1, full discounts |
| `equal_resources`, `equal_count`, `explicit` | — | still selectable; all 31 root `aoe2lab.recorder.*` manifests are legacy `equal_resources` |

Worked check: Blackwood 42.75 vs Spanish Paladin 142.5 gives 27 vs 15.
(`BALANCE_POLICY.md:97` says 40.5 → 14; that is the 1/1/1 number and is stale.)

**Plan and hash** ([`aoe2lab_worker.mjs:204-273`](../../aoe2x/js_simulation/tools/aoe2lab_worker.mjs)):
- `planHash` = sha256 of canonical JSON of the sides, balance and scenario blocks.
- It includes both catalog SHAs, the weights, family/goldenSha256, player4Buffer, scenery/donut SHAs, subjectOwner, colorPolicy and playerColors.
- `jobId` is not hashed; it defaults to `matchupId_<hash8>`. [`artifacts.py:50-78`](../../aoe2x/lab/artifacts.py) refuses to reuse a jobId with a different hash.
- Consequence: **any catalog or policy edit makes a new plan**. Old captures stay bound to their frozen plan, which is intentional.

CLI ([`aoe2x/lab/cli.py`](../../aoe2x/lab/cli.py)):
- `plan` prints a plan and writes nothing.
- Other commands: `simulate`, `live`/`record`, `run`, `batch <manifest> --phase …`, `compare`, `status`, `doctor`, `serve`.
- Campaign runner: `python -m aoe2x.lab.recording_campaign <manifest> --reports <dir>`.

### 3.2 Scenario: Goldens, maps, families, kiting

**Golden templates** ([`apps/video/templates/lab_goldens/`](../../apps/video/templates/lab_goldens/)):
- All are 16×16, hash-pinned in [`live.py:26-58`](../../aoe2x/lab/live.py).
- P1 is the human spectator; it inherits P3's civ so the opponent's music plays.
- P2–P4 use `NoneAi` (a `(disable-self)` script).
- Camera trigger: P1 to (8,7). Template colors: P2 blue, P3 red.

| Golden | Use |
|---|---|
| `melee_vs_melee` | 27 slots per side; Starting trigger patrols P2→(2,13), P3→(13,2) |
| `ranged_vs_ranged` | same layout; **also used for every no-buffer fight with any ranged side** |
| `ranged_vs_melee` / `melee_vs_ranged` | adds the P4 "front line" (9 Scout→Hussar slots) and the `DefeatFrontLine` gate. Only used when a buffer is opted in. |
| `water_map` | 15 per side, no P4, not simulatable |

**Family rule.**
- "Ranged" means class `mobile_ranged` or `siege_ranged` ([`lab-scenario.js:23-34`](../../aoe2x/js_simulation/src/lab-scenario.js)). Throwing Axeman, Gbeto and Mameluke are ranged; Fire Lancer and Flaming Camel are melee.
- `player4Buffer` **defaults to `none`**, which gives `ranged_vs_ranged` if either side is ranged, otherwise `melee_vs_melee` ([`aoe2lab_worker.mjs:142-148`](../../aoe2x/js_simulation/tools/aoe2lab_worker.mjs)).
- `golden` (9 Hussars) and `scaled` (`round(clamp(5+(T−1000)/1800, 5, 10))`, T = fielded ranged army cost) are historical opt-ins.

**Maps used for current captures** (owner policy, Oct 3, [AGENTS.md](../../AGENTS.md)):
- **Arena** is not a separate template. It is a Golden plus a frozen winter scenery derivative ("Winter Campaign Study – Detailed Battlefield" terrain and Gaia, with the combat band x+y∈[10,21] flattened, plus a wildlife-freeze trigger). Builder: `prepare_norse_standard_capture.py:67-143`; output: `data/local/detailed-standard-norse/winter-templates/`.
- **Donut** is a flat winter map with a central rock, used for kiting retests: `data/local/arena-donut-standard/donut-template/Winter Donut.aoe2scenario` ([`prepare_arena_donut_capture.py:68-119`](../../apps/video/prepare_arena_donut_capture.py), untracked).
  - P2 is always the ranged army, running `ddkDonutQuietAI`. P3 is melee on NoneAi with engine aggression.
  - It has no buffer and no patrol trigger.
  - A melee subject therefore sits on **P3** (`subjectOwner: 3`).
  - **Never ranged vs ranged on Donut.** The single exception is `arbalester_kites_jarl_v1`.

**When Donut is used** ([`prepare_arena_donut_capture.py:190-204`](../../apps/video/prepare_arena_donut_capture.py), [`conditional_donut.py`](../../apps/video/conditional_donut.py)):
- A melee subject gets Donut against Arbalester / Heavy Cavalry Archer / Elite Elephant Archer **only if the ranged army lost ≥3 of 5 Arena trials** (`--trigger any-loss` means ≥1, and must be chosen before freezing).
- Jarl gets Donut against every melee opponent.
- Danish Heavy Mounted Crossbowmen get Donut against melee opponents that beat them in ≥3 of 5.
- The decision uses in-game winners, not the ranking's <10% draw rule.

**How the kiting AI works.**
- `ddkDonutQuietAI.per` is the Immortal cavalry-archer pipeline with chat removed. It kites only when it out-ranges the enemy; otherwise it volleys.
- Kite dwell = clamp(reload−1400, 400, 2200). Fire window = attack delay + 60 ms, from a per-type table plus a class fallback.
- Discovery explicitly includes gbeto, throwing axeman, mameluke, ballista elephant and Jarl (2709 is DAT class Cavalry).
- **Rules 0–77 must keep their numbers** because `.per` jumps are absolute ([`donut_ai_timing.py:29-38`](../../apps/video/donut_ai_timing.py)).
- The AI is **embedded in the scenario in three places**: `PlayerDataTwo.ai_names`, the per-slot `ai_per_file_text`, and the `Files` section. If they disagree, the scenario crash-loads silently.
- ⚠ The current `prepare_arena_donut_capture.py` adds `protect_slinger_volley`, but the three frozen `.per` copies (sha `6d635a0d…`) predate it. Regenerating changes the AI hash.

**Materialization** ([`build_run.py:281-367`](../../apps/video/build_run.py)):
1. Set the civs and copy P3's civ to P1.
2. Apply subject-blue / opponent-red when `subject_owner` is set.
3. Fill the first N template slots in record order and remove camp props.
4. Retarget count/wipe/banner/TASK/PATROL triggers to the actual unit types. Fixed object references don't survive army replacement.
5. Trim or extend P4 per `player4Count`.

[`live._validate_scenario`](../../aoe2x/lab/live.py) then re-checks:
- P1 civ = P3 civ, the planned civs, and camera exactly (8,7).
- First-N positions and the exact P4 roster.
- AI identical to the template, and only the planned color change.
- Identical trigger structure; a scenery derivative may add only its trailing Gaia trigger.

### 3.3 Capture

The game must already be open, in the **Scenario Editor**, fullscreen and frontmost. No code launches Steam or the game. Preflight: `.\scripts\aoe2lab.ps1 doctor --live --ui`.

Per battle ([`apps/video/auto/orchestrate_matchup.py`](../../apps/video/auto/orchestrate_matchup.py)):
1. Copy the scenario to the profile as `Matchup Run.aoe2scenario`. The Load dialog's search box must be preset to "Matchup Run".
2. Menu → Load (OCR picks the row) → Menu.
3. Start the gRPC logger, then ffmpeg, then click **Test**.
4. Detect game start by luma. gRPC frames must arrive within 12 s.
5. Recorder: `ddagrab → h264_nvenc` (p1/ull/cq19), with gdigrab+x264 as the fallback. Audio comes from dshow `virtual-audio-capturer`. OBS is not used.
6. End: the gRPC tailer writes `.END` after one army has been at 0 for 4 s of stream time. The WINS banner is the fallback (5 s grace).
7. Exit: F10 → Quit → Yes, back to the editor.

Controls:
- Campaign: one driver (Windows mutex `recorder-campaign.lock`) and one background finalizer.
- Three consecutive failures give `STOPPED_AFTER_ERRORS`.
- Stopping:
  - A queue `PAUSE` file or `thermal/PAUSED.json` stops at the campaign boundary.
  - A campaign `PAUSE` file, <8 GiB free, or an archive-guard failure stops at the next battle boundary.
- Thermal limits: CPU 90 / GPU 85 °C; resume below 80 / 75.

**Repeats.** `r01..r05` are separate jobs and separate games with one shared plan hash. They are *not* simulation seeds.

### 3.4 Evidence and verification (gRPC)

**Logger** ([`aoe2x/grpc/grpc_hp_log.py`](../../aoe2x/grpc/grpc_hp_log.py)):
- Connects over mTLS to `ipv6:[::1]:4341`, target-name override `ca-game-api`.
- Calls `SetFogOfWar(false)`, then streams `Frames(disableParticles)`.
- Writes length-prefixed `FrameSequence` records to `.frames.bin`, plus `.meta.json` and `.END`.
- Env: `AOE2_GRPC`, `AOE2_GRPC_PYTHON`, `AOE2_GAME_SPEED` (default 1.7).

**Army and conversions.**
- Army = owners 2/3, model types 9/11/12, excluding the scout 448. P4 is never counted.
- Conversions: an ID that changes owner leaves its old queue and joins the new owner ([`redecode_hp.py:278-291`](../../aoe2x/grpc/redecode_hp.py)). A converter's remaining HP can therefore exceed 100%.

**Validation** ([`live.py:398-474`](../../aoe2x/lab/live.py)):
- The mov, frames, meta, END and hp files must all exist; frames must be ≥1 MB.
- Starting counts must equal the plan.
- Exactly one side must be at 0. Mutual elimination is recovered from (0,0) for ≥3 observations plus an end-screen check.
- Result: winner owner, survivors, winner HP / own starting HP.

**Bundle.** `recording.json` is a sha256 inventory plus media, sides and the clock mapping ([`recording.py:46-102`](../../aoe2x/lab/recording.py)). The campaign row goes `finalizing` → `verified`, and "verified" explicitly does *not* mean the simulation agrees.

**Clocks.**
- Stream time is game time. Sidecars are divided by game speed and stamped `clock:"video"`; don't divide again.
- `battle.mp4` = raw video trimmed at the first in-game frame (luma); the tail is not trimmed.
- The final mapping is `videoSeconds = gameMs/1000/speed + offset`, taken from `alignment.json`.

**Optional V3 sim lane** (`postprocess_campaign --simulation-only`):
- Runs 5 seeds per verified job.
- MATCH = 5/5 winner agreement and |Δ mean signed HP| ≤10 pp. Anything with a wrong seed or >20 pp is listed in `failures-over20.md`.
- Refuses scenery/Donut, relics, water, and any P4 count other than 9. **This means today's Arena/Donut captures are outside the sim lane.**
- Diagnostic only; it never supplies results.

### 3.5 Rankings (comparison series)

Source: [`report_knight_line_rankings.py`](../../apps/video/report_knight_line_rankings.py). The full specification is in [CIVILIZATION_COMPARISON_GUIDE.md](CIVILIZATION_COMPARISON_GUIDE.md).

- **One recorded battle per cell.** The ranking does not average repeats.
- **P** = surviving main-army HP % of that army's own start. It is a draw if there is no winner or P < 10 (exactly 10 is a win).
- **Points:** win = 2 + h + otherLosses/(N−1); loss = −h; draw = 0.5. Score = 100·Σ/(4M).
- **Highlights:** upward surprises, downward surprises and rare wins (gap >10 pp), each kept to 25; top-10 is just the first 10.
- ⚠ The reporter accepts only v1/v2 policies and `--line camel|knight`. **v3 captures are rejected** until a loader is added (guide §5 lists the steps).

### 3.6 Overlays

The production path is `render_campaign_overlays.py` → `postprocess_campaign`. For each run it runs:
- `overlay.static_stats --panels-only`
- `overlay.auto_alignment`
- `overlay.unit_hp`

It then checks that frame count and size match `battle.mp4`. Requirements: 2560×1440, source fps, libx264 CRF18.

**Static panels** ([`static_stats.py`](../../apps/video/overlay/static_stats.py)):
- 590×344 per side, at y=1078.
- Text uses the game's MSDF font atlas; stat icons come from `widgetui/.../staticons`.
- Portraits come from `apps/website/static/img/units/`; stats from `aoe2_reference.db` plus `supplemental-stats.json`.
- Bonus damage is drawn as a green bracket on the attack row.
- Effect notes are hard-coded per slug.

**Live HP queue** ([`unit_hp.py`](../../apps/video/overlay/unit_hp.py), [`unit_timeline.py`](../../apps/video/overlay/unit_timeline.py)):
- A 256×800 strip per side with 72 px tiles, filled column-first.
- Survivors first, then the dead (gray, 0.35 brightness).
- More than 27 alive adds columns, and **surplus dead tiles are silently dropped**.
- HP holds the last observed value, with no interpolation.

**Alignment** ([`auto_alignment.py`](../../apps/video/overlay/auto_alignment.py)):
- Detects in-game HP bars (blue fill = P2, red = P3), samples at 3 Hz, and grid-fits speed ∈ {1.7, 2.0} and offset −4…+2 s.
- Gates: ≥30 *bar detections*, RMS ≤0.045, alternative-error ratio ≥1.4.
- Recovery options: `--sample-rate 15 --color-components`, hash-bound `--anchors`, or [`event_alignment.py`](../../apps/video/overlay/event_alignment.py) with reviewed death events.
- **Do not relax the gates.**

**Battle end** ([`battle_end.py`](../../apps/video/overlay/battle_end.py)): the first elimination, extended while any side's HP keeps dropping (pending projectiles).

**Shorts** ([`build_vertical_short.py`](../../apps/video/build_vertical_short.py)):
- Layout: queues in y 0–320 (filled row-first), the game view at y=330, the two stat cards at y=1435, and a caption.
- The game view is a **fixed 1440×1440 crop at x=640**; there is no tracking, only `--crop-x`.
- 10 picks: for each of Infantry / melee Cavalry / Archer, the most expensive opponent beaten and the cheapest one lost to; then Missionary and Flaming Camel; then interesting fills (closest finishes). See [`prepare_flemish_militia_final_shorts.py`](../../apps/video/prepare_flemish_militia_final_shorts.py).

**Comparison chapters** ([`build_champi_comparison_overlay.py`](../../apps/video/build_champi_comparison_overlay.py)):
- 2560×1440 at 30 fps: four 640×960 views with no live HP.
- The game's victory/defeat art, Trajan Pro, medals, and a footer with the opponent card and a tally.
- The Knight profile mode uses `encode_comparison_fast.py` (FFmpeg plus NVENC).

### 3.7 Intro, narration, covers

**Backdrop** ([`build_campaign_catalog.py`](../../apps/video/build_campaign_catalog.py)):
- Scans `resources/_common/campaign/*.json` for `SlideBackgroundImage`, plus each campaign's first-scenario P1 civ.
- Applies curated overrides from `intro/campaign_overrides.json`; Wei uses Art of War.
- Renderers read the game's `.dds` directly; nothing is copied into Git.

**Pages** ([`build_campaign_intro.py`](../../apps/video/build_campaign_intro.py)):
- Two untitled parchment pages, 1920×1080 at 30 fps.
- Unit art is multiplied onto the parchment. Text uses the game font, x=875, width=550, both adjustable per plan.
- Letters reveal per character from ElevenLabs timestamps.
- Mix: voice −17 LUFS, music −31, limiter.

**Narration** ([`generate_intro_narration.py`](../../apps/video/generate_intro_narration.py)):
- Narrator reference audio comes from Wwise packs via `extract_intro_reference.py`.
- Cloning: `POST /v1/voices/add`. TTS: `/with-timestamps`, `eleven_multilingual_v2`.
- Voice IDs are in `intro/*-voice-clone.json`. Five are **retired**, Pachacuti among them, even though `CHAMPI_COMPARISON_BOOKENDS.md` says otherwise. **Never reuse a retired ID.**
- Narration audio is irreplaceable once a clone is deleted, so archive it.

**Unit art** comes from built-in image generation using the unit icon as reference, with provenance saved next to the asset.

**Covers** ([`build_campaign_thumbnail.py`](../../apps/video/build_campaign_thumbnail.py)): `-long.jpg` 1280×720 and `-shorts.jpg` 1080×1920, under 2 MiB. Older covers (Tiger, Xianbei, Liao, Grenadier) were AI-edited instead.

### 3.8 Compile, QA, upload

**Full video** (the scaffold copies [`build_elite_monaspa_final.py`](../../apps/video/build_elite_monaspa_final.py)):
- The intro is NVENC re-encoded to 2560×1440 at 60 fps.
- Each chapter is trimmed at `terminal_row` + 1 frame.
- Concat uses ffconcat with `-c:v copy` and FFMETADATA chapters, with audio as AAC 48 kHz.
- Checks: duration within 2 s, the chapter count, and a `-xerror` full decode.
- `manifest.json` is written last; the description is ≤5000 chars.

**QA** ([`production_qa_sheet.py`](../../apps/video/production_qa_sheet.py)):
- Builds contact sheets; Shorts must be ≤180 s.
- A human then writes `final-cost-v2/visual-qa.json`.
- ⚠ There are two schemas: `finish_pending_production` asserts `passed: true`, while `produce_*` and `serial_media_queue` check `status == "passed"`.
- **Never write a passing receipt to unblock a supervisor before the review has happened.**

**YouTube** ([`authorize_youtube.py`](../../apps/video/authorize_youtube.py), [`upload_youtube.py`](../../apps/video/upload_youtube.py)):
- OAuth uses a Desktop client with loopback and PKCE. Scopes: `youtube.upload` and `youtube.readonly`. Tokens are DPAPI-encrypted.
- Channel `@aoe2matchup`, `UCKYN-pN4AZ3w4LpRxcdSciA`. The uploader refuses any other channel.
- Upload: resumable `videos.insert` in 16 MiB chunks, with the encrypted session saved for resume, then `thumbnails.set`, then polling `videos.list` until `processingStatus == succeeded`.
- Videos always start private: category 20, `en`, not made for kids, synthetic-media True for the narrated full video and False for Shorts.
- Retry with the same state key. **Never start a second insert because Studio shows 0%.**
- Endpoints used: token, `channels.list`, `videos.insert`, `thumbnails.set`, `videos.list`. **Nothing else.**

---

## 4. Current rules: quick reference

| Topic | Rule (code-verified) |
|---|---|
| Counts | v3 geometric: cheaper side 27; other = round½↑(27·√(cheap/exp)); cost = F + 0.9W + 1.1G, full discounts; population 1 |
| Map | Arena (winter scenery Golden) by default; Donut only for selected ranged-vs-melee kiting retests |
| Buffer | None for new captures. Hussar footage is historical only. |
| Owners | Arena: subject usually P2. Donut: ranged = P2, melee = P3, so a melee subject is on **P3**. Record `subjectOwner` and never infer the subject from P2. |
| Colors | New plans: subject blue, opponent red (`subject_blue_opponent_red_v1`), hashed into the plan. Historical plans keep their template colors. |
| Repeats | 5 separate games per condition (r01–r05) |
| Results | Always from the real game. The simulation is diagnostic only. |
| Copy | Describe the saved plan's policy. Never write "equal resources" for geometric captures. |
| Owner instructions | Reuse valid work; push back on unnecessary reruns; never format disks; no recording until the owner asks (standing since Oct 3) |

---

## 5. Known bugs and risks (verified)

| # | Issue | Where | Impact |
|---|---|---|---|
| 1 | Firecrawl API key committed in plain text (in public history since `4bb1a4b0`) | `.claude/skills/aoe2onlinereference/SKILL.md` | Redacted on 2026-11-18, but it remains in history. **Rotate the key.** |
| 2 | **Color policy vs HP alignment.** `auto_alignment` hard-codes blue = owner 2 and red = owner 3. With subject-blue and a melee subject on Donut P3, P3 is blue, so the owner labels swap. | `auto_alignment.py:24-27`, `live.py:176-190`, `build_run.py:318-323` | The overlay is fit against the wrong army: it either fails its gates or, worse, passes with a swapped fit. Fix this before the first overlay of a new-policy Donut capture (none exist yet). |
| 3 | Rankings reject v3 | `report_knight_line_rankings.py:31` | Arena/Donut standard-unit results can't be ranked until a loader is added. |
| 4 | Sim lane assumes the subject is P2; the reporter does too | `postprocess_campaign.py:200,237` | Donut P3 subjects get mirrored comparisons. |
| 5 | `audit_recording_costs.py` regresses the catalog | `scripts/` | Wipes Saxon/tech-tree costs and `releaseAudit`. |
| 6 | The scaffold writes `player4Buffer: 'golden'` metadata, but its rows produce no-buffer plans with no `subjectOwner` (so no color policy) | `scaffold_video_episode.py:121` | The queue entry misdescribes the capture, and the plan hash differs from a CLI `plan`. |
| 7 | `meta.json` counters are stale (the logger is killed with `terminate()`); `end_game_s` is always null | `grpc_capture.py:106,162` | Don't trust those fields. `frames.bin` can end in a partial record, which the reader tolerates. |
| 8 | Two `visual-qa.json` schemas | §3.8 | A receipt valid for one supervisor fails the other. |
| 9 | Comparison-series finishers have no QA gate; `upload_youtube_batch` ignores the cost-audit allowlist | `finish_knight_comparison.py`, `upload_youtube_batch.py:23` | Inconsistent safety gates. |
| 10 | The HP queue silently drops dead tiles beyond capacity | `unit_hp.py:55-57` | Large armies lose visible casualties. |
| 11 | No guard keeps Missionary out of the sim lane, although the docs call it unsupported | `postprocess_campaign.py` | It could get a misleading MATCH/MISMATCH. |
| 12 | Full compilation copies video without asserting the codec, fps or resolution match | `build_*_final.py` | A mismatched chapter corrupts the concat silently until the decode check. |

### Offline test status (2026-11-18, main-checkout working tree)

`node --test` balance and worker tests: 23/23 pass.
`pytest aoe2x/lab/tests apps/video/tests`: **270 passed, 7 failed, 3 skipped**.

| Failure | Cause | Kind |
|---|---|---|
| 3 × `test_video_handoff.py` | Expects 73/74 opponents; the roster is now 77 | Stale test expectation |
| `test_pure::test_cost_weights_match_the_website` | Reads the removed `apps/webapp/simulation_real.py` | Stale path |
| `test_recorder_navigation::test_cached_row_is_revalidated_and_relocated` | The test double lacks the new `exact=` kwarg of `find()` | Stale test double |
| `test_mutual_elimination::test_draw_still_requires_recorded_end_signal` | The error-message regex no longer matches | Probably stale; check the message |
| `test_workflow::test_mixed_live_build_preserves_p4_diplomacy_ai_and_trigger_structure` | `generated Player 2 roster/positions differ from first-N golden slots` | **Possible real regression** in mixed (buffered) builds. It matters when resuming historical Hussar plans. Investigate before relying on them. |

Run them with:
`PYTHONPATH='apps/video;.' apps/video/.venv/Scripts/python.exe -m pytest aoe2x/lab/tests apps/video/tests -q -p no:cacheprovider`

---

## 6. Improvement roadmap

### 6.1 Maps and civ themes
- **Drafts already exist.** `data/local/arena-theme-review/` (untracked) has 10 civ themes (Japanese, Chinese, Vikings, Celts, Byzantines, Saracens, Ethiopians, Incas, Mayans, Persians) and 20 biome A/B variants. The builders are `build_biome_variants.py` and `build_extra_variants.py`, with notes in `REVIEW.md`. None is wired into a plan; only Winter is in production.
- **To promote a theme, follow `winter_templates()`.** Derive terrain and Gaia only, keep the combat band flat and passable, and freeze the derivative with an audit (`state PASSED`, goldenSha256, templateSha256). Then pass it as `scenario.scenery`; the validator enforces everything else.
- **Selection rule to add:** subject civ → theme. This changes the plan hash, so it starts a new policy version. It does not justify re-recording.
- **Gate:** run one pilot per theme and check pathing, camera framing, HP-bar detection (snow vs sand contrast affects `auto_alignment`) and alignment gates before using it in a campaign.

### 6.2 Overlays
- **Easy wins:**
  - Derive a per-civ accent color (today only the parchment and emblem vary).
  - Show a running "resources lost" counter (cost × dead, from the timeline).
  - Add kill-feed / casualty ticks.
  - Add a final result card on single-matchup chapters (the comparison overlay already has the art).
- **Shorts:** track the battle centroid from gRPC x/y instead of the fixed crop. Add a 1–2 s hook card ("27 Arbalesters vs 15 Paladins: who wins?") before the fight.
- **Hard-coded today:** all geometry, colors, effect notes and the 2560×1440 requirement. Move them to a style JSON per product before adding themes.

### 6.3 YouTube engagement
Researched 2026-11-18 from developers.google.com and support.google.com. Re-check quotas before building.

| Lever | API? | Notes |
|---|---|---|
| Series playlists (per unit, per civ, Shorts) | ✅ `playlists.insert`, `playlistItems.insert` (50 units each) | Needs the `youtube` or `youtube.force-ssl` scope, so re-consent is required (today we only have upload + readonly) |
| Scheduled publishing | ✅ `status.publishAt` on private, never-published videos | Explicitly set `privacyStatus` (the default behavior changed Nov 2026) |
| Captions / multi-language metadata | ✅ `captions.insert` (400 units), `localizations` via `videos.update` | Narration text and timestamps already exist, so captions are nearly free |
| Pinned "predict the winner" comment | ⚠ Posting works (`commentThreads.insert`); **pinning is not possible via the API** | Pin it manually in Studio |
| Polls / quizzes / community posts | ❌ The posts API is a partner-only pilot with no polls | Studio only; quizzes are the natural fit for "who wins?" |
| End screens, cards, Shorts→long "related video" | ❌ | Studio only; add to the release checklist |
| Thumbnail/title A/B (Test & Compare) | ❌ | Studio, long-form only; it picks by watch-time share |
| Analytics | ✅ Analytics API (retention by `elapsedVideoTimeRatio`, traffic source, `creatorContentType`); **impressions/CTR only via the Reporting API** (`channel_reach_basic_a1`) | Create the Reporting jobs early (they backfill only 30 days) |

**Policy risk: YouTube's inauthentic-content rule.** It bars "content that looks like it's made with a template" and judges the whole channel. Treat varied, matchup-specific analysis (why a unit wins, cost-efficiency, the counter explanation) as a requirement, not polish. Ten interchangeable Shorts per episode is the highest-risk pattern. Separately, YouTube says plain gameplay footage doesn't need a synthetic-media disclosure. Revisit whether `containsSyntheticMedia=True` is required for cloned-narrator intros; that is the owner's decision.

**Suggested first step:** a `publish_extras.py` that runs after `upload-completion.json`. It adds the video to its playlists, uploads captions from the narration alignment, sets `publishAt`, and posts a "predict the winner" comment for manual pinning. All of that is within the API; it needs re-consent with the `youtube.force-ssl` scope.

---

## 7. Doc drift register

Code wins in every row below.

| Doc says | Code says |
|---|---|
| Runbook §2: resource weights 1/1/1, half-strength food/wood rule for shared units | v3: 1/0.9/1.1, full discounts (`balance.py:5`) |
| Runbook §1, all-unique doc, scaffold comment: 74-unit roster | 77 (76 opponents for a roster subject) |
| Runbook §2, `aoe2-lab.md`: 9-Hussar P4 screen is the default for mixed fights | default `player4Buffer: none` (`aoe2lab_worker.mjs:142`) |
| Runbook: "P2 is always the featured unit" | Donut puts melee subjects on P3 (`subjectOwner`) |
| `BALANCE_POLICY.md:97`: Blackwood 40.5 → 14 Paladins | 42.75 → 15 |
| `aoe2-lab.md:179`: counts default to equal resources | geometric v3 |
| `CHAMPI_COMPARISON_BOOKENDS.md`: Pachacuti voice restored | `pachacuti-voice-clone.json` is `retired` |
| `NARRATION-OPTIONS.md`: Wei clone current | retired |
| `per-unit-hp-overlay.md`: fixed 3×9 grid, rejects >27 | grows columns, drops surplus dead |
| `static-stats-overlay.md`: pilot pair only, blast-radius row | any plan; no such row |
| `selected-matchup-shorts.md`: 20 Shorts at 60 fps | 10 per subject; fps inherited |
| `apps/video/RUNBOOK.md`, `build_run.py` docstring | describe the legacy `scenario_builder` / `default3` flow |
| `platform_io.py:20`: gdigrab | ddagrab + NVENC by default |
| gRPC README: `record_games.py` consumer | file does not exist |
| `MEDIA_AND_PUBLICATION.md`: `data/local/youtube/client.json` | not present; token stores the client path |

---

## 8. Starting a new idea: checklist

1. **Decide the product type** (§1) and whether existing verified captures already answer it. Reuse first ([AGENTS.md](../../AGENTS.md), [minimal retake audit](KNIGHT_MINIMAL_RETAKE_AUDIT.md)).
2. **Resolve unit identity** (master ID, civ, mode) in the roster or subjects. Add cost evidence with `audit_installed_dat.py`, not the old audit script.
3. **Preview plans** (`aoe2x.lab.cli plan`, or the scaffold without `--write`). Inspect counts, family, map, `subjectOwner` and colors. Spot-check the cheapest and most expensive opponents.
4. **Get the owner's go-ahead to record** (standing instruction). Pilot 3–5 jobs using the same job IDs as the full run.
5. **Capture** with the wrapper; monitor the active pass `status.json`, thermals and disk.
6. **Overlays, intro, compile, Shorts.** One subject at a time.
7. **Real visual and audio review** → `visual-qa.json` → authorized upload → `upload-completion.json`.
8. **Archive** to the share with sha256 receipts; only then remove authorized local copies.
9. **Update this guide's** §4–§7 when a rule changes.

---

## 9. Redo a run on a fresh machine

Everything needed is in Git except the game, credentials, and data derived from the installed game.

1. **Install.** Install AoE2:DE (same build; check the DAT sha against a run's `source.json`/`run.json` on the share). Set up `apps/video/.venv` per [SETUP_AND_DATA.md](SETUP_AND_DATA.md), with `genieutils-py` available. Copy the gRPC mTLS certs to `aoe2x/grpc/`. Create `aoe2lab.toml` from `aoe2lab.example.toml`.
2. **Regenerate game-derived data:**
   - `python -m aoe2x.extract.run` writes `data/inputs/extracted_data/`.
   - `python scripts/audit_installed_dat.py` writes `data/local/dat-release-audit/`.
   - `python scripts/cache_installed_dat.py` writes the pickled DAT the winter prepare scripts load.
   - Regenerate the databases only if the game build changed (CLAUDE.md "Build Pipeline").
3. **Know what defines a run.** All of these are tracked:
   - catalogs: `data/unique-unit-roster.json`, `recording-subjects.json`, `recording-costs.json`, `recording-balance.json`;
   - Goldens: `apps/video/templates/lab_goldens/`;
   - Arena/Donut templates and kiting AI: `data/local/...` allowlist;
   - the planner/worker code.
   A plan is a pure function of those plus the request, so the same request on the same catalogs gives the same `planHash`.
4. **Pick the request:**
   - **A new unit episode:** scaffold it (`apps/video/scaffold_video_episode.py --key … --slug …`), then run `python -m aoe2x.lab.recording_campaign <manifest> --reports <dir>`. The root `aoe2lab.recorder.<key>-all-unique.json` files are the historical episodes' requests. They use legacy `equal_resources` rows, and the cost guard rejects re-planning them against today's catalogs.
   - **A new Arena / Donut / themed-map run:** use the generic `apps/video/prepare_spike_matchups.py`. It takes subjects × opponents × layouts, freezes a recorder manifest from the tracked templates (a themed Arena is built and audited on the spot), and reads no earlier run records. Register any unit missing from the catalogs first, with `apps/video/register_recording_unit.py`. Then run `python -m aoe2x.lab.recording_campaign <work>/manifest.json --reports <dir>`.
   - **Historical delta scripts need the share.** These scripts topped up specific past campaigns and read those campaigns' own queue, manifest or status files plus share `run.json` indexes:
     - `prepare_arena_donut_capture`, `prepare_jarl_kiting_followup`, `prepare_slinger_timing_probe`;
     - `prepare_mounted_donut_opening_fixes`, `prepare_donut_color_*`;
     - `prepare_detailed_cavalier_retakes`, `prepare_saxon_guard_cost_retakes`, `fix_jarl_opening_patrol`.

     They don't run on a fresh clone without those records. Keep them as a record of how those campaigns were derived, not as the way to start new work.
   - **Older extraction folders:** `prepare_jomsviking_capture` reads `data/local/viking-sagas-research/extracted`, and the cost-audit tools read `data/local/cost-audit-extracted`. Both are `aoe2x.extract` outputs. Regenerate them by running the extractor with its output directory pointed there (`scripts/audit_installed_dat.py` shows the pattern).
5. **Run the rest:** overlays, intro, compile, Shorts, QA and upload, per §3.6–3.8 and the [runbook](../VIDEO_PRODUCTION_RUNBOOK.md).

To reproduce an **exact past plan hash**, use the catalog versions saved with that run on the share (`_arena_donut_metadata`, `frozen-catalogs/`, `run.json`). Current catalogs produce current plans.
