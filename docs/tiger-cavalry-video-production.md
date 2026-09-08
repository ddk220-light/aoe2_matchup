# Tiger Cavalry video: production workflow and approval record

Recorded September 8, 2026, on `codex/video-recorder-v3`.

## Delivered and approved

The delivered video combines the approved Wei campaign-style introduction with 59 validated matchup overlay videos. The user reviewed the overlay videos and intro through local previews and iPhone Taildrop transfers, approved the final cloned-voice intro, requested assembly, and then accepted the completed compilation and requested this documentation and commit.

| Item | Final delivery |
| --- | --- |
| Subject | Wei — Elite Tiger Cavalry |
| Opponents | 59 recorded unique-unit matchups in the approved compilation |
| Duration | 2071.174 seconds — 34:31 |
| Picture | 2560 × 1440, H.264; intro normalized to 60 fps, existing battle video packets preserved |
| Audio | Stereo AAC, 48 kHz |
| Chapters | 60: introduction plus 59 matchups |
| File size | 3,645,803,644 bytes |
| SHA-256 | `954c4cb24f751082c8a3f45be9e381bd5dc7f465a60056f2558a99c1500cbe7d` |
| Tiger results | 23 wins, 36 losses in these recordings |
| Description | 4,399 characters, including conditions, results, HP, survivors, website link and hashtags |

Local delivery directory, relative to the repository root:

`aoe2x/js_simulation/calibration/lab/compilations/tiger-unique-units/final/`

- `tiger-cavalry-complete-with-intro.mp4`: final master.
- `youtube-description.txt` and `youtube-title.txt`: upload copy.
- `chapter-results.json`: detailed result evidence for each included matchup.
- `chapters.ffmeta`: embedded chapter metadata.
- `manifest.json`, `validation.json`, `encode.log`, and `qa/`: assembly and verification records.

The master is stored locally. No YouTube upload or publication was performed. The website chapter timestamps become navigable YouTube chapters when the description accompanies this master; a hosted video URL was not invented.

### Capture completion is different from publication readiness

The raw recorder campaign completed **73 of 73 captures with zero failed captures**. Its postprocessing snapshot contains **59 complete overlays and 14 failed/held overlays**. Only the 59 validated overlays entered the reviewed compilation. The other 14 remain omitted; this document does not claim that every captured matchup is publication-ready.

The repository snapshot [tiger-cavalry-approved-release.json](tiger-cavalry-approved-release.json) records the included matchup results and omitted job IDs. The ready-to-paste description is also preserved as [tiger-cavalry-youtube-description.txt](tiger-cavalry-youtube-description.txt).

## 1. Define the subject, opponent roster and scenario rules

1. Select the subject unit and civilization: Elite Tiger Cavalry, Wei.
2. Use the approved reusable roster in `data/unique-unit-roster.json`. It includes highest-tier unique land units and relevant unique upgrades/alternate attack modes. Exclude the subject itself, ships, heroes, Camel Scout, Winged Hussars and ordinary regional lines. Sort by civilization name; the executed manifest is authoritative for ties and included modes.
3. Keep the subject on Player 2 and the opponent on Player 3. Set spectator Player 1 to Player 3's civilization so the game music follows the opponent.
4. Preserve the chosen Golden scenario, including its center-camera trigger. The user's corrected Default 1 scenario established the camera intent.
5. Match main armies by resource cost, with up to 27 units per side and whole-unit rounding. A ranged army facing melee receives the Golden scenario's free screen. The archived footage uses **nine Spanish cavalry**, not ten Huskarls. Throwing Axemen, Gbeto and Mamelukes are treated as ranged opponents for this purpose.

The user withdrew a proposed change to the screen count and asked to keep the Golden setup. Describe the actual recorded setup, not the earlier recalled unit/count.

## 2. Record through AoE2 Lab and monitor completion

The recorder mode loads each generated matchup into the installed game, runs it, and saves raw gameplay and timestamped gRPC frames in a structured local folder. It does not package these into a ZIP or depend on a one-off manual recording.

Relevant implementation entry points:

- `aoe2x/lab/live.py`, `recording_campaign.py`, `recording.py`, and `battle_clip.py`.
- `apps/video/auto/orchestrate_matchup.py` and `record_until_end.py`.
- Executed manifest: `aoe2lab.recorder.all-unique.toml`.
- Campaign evidence: `aoe2x/js_simulation/calibration/lab/campaigns/tiger-all-unique/`.

The initial small batch was reviewed before the full roster proceeded. The campaign persisted status, verified capture bundles, resumed remaining jobs, and produced reports every ten matches. Completion was based on validated artifacts, not just a launched process or a passed click.

The live game driver remains serial because it controls one game instance. Offline finalization and later processing can overlap it. Navigation was tightened around observed UI states and gRPC battle-end detection to reduce idle time. Failures remained visible in the status reports.

Per-job evidence is under:

`aoe2x/js_simulation/calibration/lab/runs/<jobId>/live/run_001/`

Keep the scenario, recording metadata, raw recordings and original gRPC capture together. Derived artifacts include `battle.mp4`, `battle.hp.json`, and `unit-hp-overlay/`. The original captures remain available for overlay correction and independent simulation comparison.

### Start/end behavior

- The published battle clip begins when the game actually starts, after the editor's Test interaction. Computer-use narration such as “test button” must not be audible in the recording.
- Preserve a sharp ending after the result is established.
- Conversions are ownership changes: a side can lose when it owns no living combatants even though the converted entities remain alive for the winner.
- The Missionary clip required a special correction: cut after the final conversion rather than waiting through the long original recording. The retained cut is 19.883333 seconds, exclusive frame 1193 at 60 fps. `missionary-trim.json` documents the source event. Raw footage and frames were retained.

## 3. Build the approved overlay and validate timing

The overlay is produced offline from the recorded video and per-unit gRPC HP timeline; recording does not need to be repeated when those samples already exist.

Approved presentation:

- Bottom-left subject stats and bottom-right opponent stats, labeled by unit name rather than player number.
- Installed game font/icon assets and civilization-specific panel borders.
- Civilization emblem centered on the unit portrait's bottom-right corner, overlapping the corner like a subscript badge.
- Adequate title margins; no “Starting Stats” label.
- Special abilities below the stats; Tiger Cavalry's per-kill increase and maximum are included.
- Matchup bonus damage shown separately in green brackets. Do not subtract it from the opposing unit's displayed armor or disguise it as ordinary attack upgrades.
- Vertical portrait queues, up to three columns by nine rows, with live HP and survivor counts. Living units compact upward as casualties occur; dead units are visibly distinguished.

Relevant modules: `apps/video/overlay/static_stats.py`, `civ_theme.py`, `unit_hp.py`, and `unit_timeline.py`.

Each `unit-hp-overlay/units.json` preserves entity identities, HP samples and the mapping from game time to video time. Verify that mapping against visible HP/death transitions. Wall-clock timing or a guessed game speed alone is insufficient. Ambiguous timing is a reason to hold an overlay, not to label it complete.

The user reviewed sample overlays, requested typography/bonus-label changes and the corner-centered emblem, and approved that design as the standard going forward. Existing branch commits `604d72e4` and `52d9cf68` record those overlay milestones.

## 4. Keep simulation comparison separate from recorded results

The user also requested five V3 simulation runs per completed matchup, fixture coverage fixes, and comparison of winners and HP deltas. Those are diagnostic outputs, not the source of the video's winner labels.

The parallel processing evidence is in `campaigns/tiger-all-unique-postprocess/`. Fixture preflight and actual game-data mechanics were used for the simulation work. Ghulam/Flaming Camel investigations and the unresolved Shotel discrepancy are separate from approval of the video. Do not imply that the user approved the engine as accurate for every matchup.

The final video's results come from the recorded per-unit timeline at the last visible sample of each chapter, excluding the screen. Missionary totals include converted Tigers under their new owner. This avoids reporting later healing from a portion of the capture that was trimmed away.

## 5. Assemble and review the battle-only compilation

Select overlay jobs explicitly marked complete. Preserve civilization order and each validated HP overlay. Substitute the trimmed Missionary clip. Record each clip's source, duration, cumulative start and job ID in the compilation manifest.

The intermediate battle-only master is:

`aoe2x/js_simulation/calibration/lab/compilations/tiger-unique-units/tiger-cavalry-all-completed-overlays.mp4`

It contains the 59 reviewed battle videos and lasts 2027.840333 seconds. The local helper used for that assembly was `.tools/build-tiger-compilation.py`; its `manifest.json`, `concat.txt`, and `chapters.ffmeta` preserve the actual assembly inputs. The user said the overlays looked good, identified Missionary as the only requested timing correction, and requested the full combination.

## 6. Create and review the campaign-style introduction

### Art and civilization mapping

Search installed campaign JSON, DDS backgrounds, artwork and font atlases. Map campaigns to civilizations using the first embedded scenario's Player 1 civilization where supported, with explicit curated exceptions rather than guessed certainty. Parse archives in isolated processes because the scenario parser uses process-global schema state.

The resulting catalog has 43 preferred civilization mappings. Wei deliberately uses the **Art of War** parchment/background, as requested. A Tiger Cavalry campaign sketch was generated from the existing unit portrait, using original sepia line art composited onto the parchment. The background and fonts are read from the local game installation.

Relevant files: `apps/video/build_campaign_catalog.py`, `build_campaign_intro.py`, and `apps/video/intro/`.

### Editorial review sequence

| Version | Review and resulting decision |
| --- | --- |
| Intro v1 | Five pages covering introduction, history, abilities, rules and chapters; supplied for review and Taildropped. |
| Intro v2 | User retained only the history and abilities pages, removed titles/page numbers, moved the other material to the description, and requested letter-by-letter text plus music. |
| Intro v3 | Narration used a licensed voice returned by similarity search. User clarified that this was not the desired result and requested actual voice cloning. This version was superseded. |
| Intro v4 | User confirmed permission to clone the narrator. Generated an actual Wei campaign voice clone, synchronized text to speech, mixed music, delivered locally and via iPhone Taildrop. User said it was perfect and requested final assembly. |

### Approved narration and timing

The extracted Wei event `PLAY_WEI1S1` resolves through the installed English DLC7 bank to media 513736269 (78 seconds). Art of War `PLAY_CM_01` was also extracted as a fallback, but Wei existed and was used. `extract_intro_reference.py` records the direct Wwise event/action/sound mapping.

After the user confirmed permission, ElevenLabs Instant Voice Cloning created the narrator from the Wei recording. `create_intro_voice_clone.py` and `generate_intro_narration.py` record the reusable workflow. Store credentials only in the process environment; never put API keys in documentation, source, commands in a runbook, or committed outputs.

The final intro uses newly synthesized narration, not copied campaign dialogue. The two pages cover unit background/history and special abilities. Provider character timestamps drive the letter reveal; each page has a 0.4-second lead and approximately two seconds of final hold. The intro lasts 43.333333 seconds.

The Chinese civilization music fallback was extracted from installed media 784299781 and decoded with vgmstream. It is mixed quietly beneath speech, with fades. This is not claimed to be a verified Wei-specific theme. `tiger-cavalry-cloned.json` is the approved intro plan; `intro-v4/` retains speech, alignment, provenance and validation.

## 7. Combine the approved intro and battles

`apps/video/finalize_tiger_compilation.py` joins the approved v4 intro and battle-only compilation. It normalizes only the intro to 1440p/60 fps and the battle stream's time base, then copies the battle H.264 packets. Audio is re-encoded continuously. The existing battle visuals are not recompressed.

The final assembly:

1. Prepends the 43.333333-second approved intro.
2. Shifts all 59 battle chapters by the intro duration.
3. Embeds the introduction and matchup chapters in the MP4.
4. Reads the final visible per-unit HP sample for each chapter.
5. Writes winner, loser, remaining HP and survivor count to the result record.
6. Produces the upload title and description with full unit names, conditions and clearly defined WIN/LOSS labels from Tiger Cavalry's perspective.
7. Links to `https://aoe2matchup.com/?civ1=Wei&unit1=elite_tiger_cavalry_wei&age1=Imperial`. Browser verification confirmed automatic Wei/Elite Tiger Cavalry selection; the shorter slug without `_wei` did not select the unit.
8. Adds relevant AoE2, RTS, battle-simulation, counter-unit and defense-strategy hashtags.

Chapter labels use the winner's total remaining main-army HP, rounded, plus living unit count. They are not average individual-unit health or V3 estimates. WIN means Tiger wins; LOSS means the named opponent wins. The other main army is the loser. The description calls out the Missionary ownership exception.

## 8. Verify, deliver and record approval

Final verification checked:

- Expected combined duration, video resolution and audio format.
- All 60 embedded chapters, ordered and within the master duration.
- A decoded frame at every chapter and at the end: 61 checks.
- Eight seconds of audio/video spanning the intro-to-battle join, with no decoder errors.
- Visual inspection of the first battle after the join.
- 59 distinct included job IDs, all with a resolved recorded winner.
- The description's length and the website preselection behavior.
- The final master checksum listed above.

Earlier review of the individual overlays remains part of the acceptance evidence; the final assembly checks do not claim an additional minute-by-minute subjective review or an independent listening test of voice similarity.

The user approved the completed master and description and requested that this workflow be recorded and committed. This commit preserves the runbook, a compact release/result snapshot and the exact final description. Large videos, raw captures, gRPC streams, installed-game audio and temporary render frames stay in local artifact storage.

## Reuse for another unit

Follow the same sequence: choose subject and roster → validate Golden/scenario inputs → run a small recording spike → review → complete/resume captures with reports → validate overlays and hold failures → review the battle compilation → select/generate campaign art and authorized narration → review the intro → combine only approved inputs → regenerate results/chapters/description → validate and deliver.

The current intro layout is validated for the Art of War parchment. Other campaign layouts may need different text/art rectangles. The finalizer currently targets this Tiger release; adapt its subject/input paths for another unit. A fresh environment also needs the local captures, installed game assets, Python dependencies, FFmpeg, decoder and narration credentials/artifacts. The documentation is an execution record, not a claim that large local media is included in Git.
