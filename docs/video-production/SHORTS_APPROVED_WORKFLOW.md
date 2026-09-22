# Approved two-unit Shorts workflow

Approved by the user on **2026-09-22**, using **Grenadier vs Huskarl v15**.
This is the current presentation and operating recipe for turning an existing
two-unit recording into a Short. It supersedes the experimental timing, audio,
camera and bookend choices in [the camera revision history](../../apps/video/SHORTS_CAMERA.md).
Use roles **A = P2/top/left** and **B = P3/bottom/right**; the format is not
specific to Grenadier or Huskarl. Do not redesign it for each new pairing.

For exact source staging, asset/audio preparation, render commands, reuse and
verification steps, use [Raw recording to finalized Short](SHORTS_FROM_RAW.md).
The completed ten-video batch and its final scripts are preserved by that guide.

This approval finalizes the format, not an upload, another capture campaign,
or a rerender of previously completed videos. Work locally from recordings.

## Required inputs

- Existing clean `battle.mp4`, matching `frames.bin`, `recording.json`, and the
  saved matchup `plan.json`. Locate the requested recording in the existing
  local/external archive; preserve it and its recorded outcome.
- Matching unit identities, civilizations, upgrade/mode, recorded army counts,
  and discounted physical-unit costs. Keep the original plan's balance policy;
  do not relabel a geometric-cost capture as equal resources.
- Verified video/HP alignment, `unit-hp-overlay/units.json`, and
  `static-stats-overlay/stats.json`. A bare MP4 is not enough to reconstruct
  trustworthy HP queues, winner statistics, or telemetry framing.
- Native game art, prepared attack animations for these two units, their native
  spoken attack-command variants, and the decoded game victory cue.

Use the existing staging/materialization and alignment helpers. Missing source
evidence is not permission to invent values or silently substitute a matchup.
No new simulation or game capture is needed for a complete archived run.

## 1. Prepare the battle and camera

Use `build_story_batch.prepare_item(..., aftermath_seconds=2)` with a new output
folder. This uses recorded frames, trims to the verified result, and retains
two seconds of real aftermath when available. If the source is too short,
report the available tail; do not manufacture a frozen battle tail.

Use the telemetry camera from `overlay/battle_camera.py`:

- Hold the establishing view until first recorded main-army HP loss.
- Zoom smoothly into the action, with zoom-in only and no backtracking.
- Favor vertical movement; cap horizontal travel at 40 source pixels. Do not
  chase isolated survivors left and right or dwell on unnecessary trees.
- Keep the useful fight centered and unobstructed throughout the zoom. An
  occasional edge unit may clip; stop further zoom where needed rather than
  zooming out. Unusual retreats/monk fights need a targeted visual review.
- Living P4 screen units may affect framing, but never main-army HP queues,
  counts, costs, winner selection, or remaining-HP totals.

The protected battle viewport is **1080 × 1080 at x=0, y=330** on a
1080 × 1920 canvas. Extend the same camera transform over the matching full
recording to expose real surrounding terrain. Black bars are allowed beyond
the recording boundaries. Do not add a blurred/duplicated backdrop, stretch
the canvas to accommodate cards, or enlarge the fight behind the overlays.

## 2. Prepare unit animations and voices

Reuse approved full-color attack PNG caches with their `animation.json` timing
and native per-pose shadows. Keep a stable canvas and registered shadow that
touches the unit; do not position a generic ellipse from transparent padding.
Preserve native alpha and continuous team-color masks. Do not reuse the old
Blackwood cache that darkened its face.

For an uncached pairing, `prepare_story_attacks.py --units <json>` accepts
`[slug, native sprite stub, team color, shadow gamma]` entries. Use the actual
unit's asset identity, A blue and B red. The no-`--units` defaults are a
Blackwood/Huskarl example, **not** generic unit discovery. Reuse the approved
HAT sprite treatment; do not repeatedly enhance already-enhanced sprites.

For each unit/civilization, resolve the installed game's **spoken response to
an attack command** and choose the longest measured native variant. Do not
substitute weapon impacts, throwing sounds, exertion sounds, intro music, or
the prior matchup's civilization voice. `extract_intro_music.py` can extract
and decode a resolved media ID; it does not discover the correct command ID.
Keep event/media IDs, source paths, durations, chosen variant and gains in
`voice-provenance.json`.

**Mounted-unit choice (2026-09-22):** When the actual unit command event is
only a horse response, use the longest spoken attack-command line from the
**same civilization**, as explicitly selected by the user. Keep the original
unit event and the replacement speech event in provenance; label it as an
editorial substitution, not the mounted unit's own spoken response.

Voices keep native speed/pitch and are peak-normalized to -6 dBFS by constant
gain. Each plays once, beginning **with** its unit's attack animation. Animation
speed is **1.5× in the intro only**; the voice is not sped up. Check that the
chosen line fits its turn rather than silently clipping or stretching it.
If the spoken line is longer than the attack, hold the final attack pose until
the line finishes. Measure the 0.2s handoff from the end of both animation and
speech; do not overlap voices or slow the animation to fill the extra time.
Remove excessive leading silence and any trailing silence that would extend a
long voice's turn, retaining a short 12ms boundary pad. Keep trim durations in
provenance; measure the exported audible handoff, not just the WAV duration.

## 3. Compose the dynamic opener

Use existing game parchment/timber background, bronze frame, and **circular VS
medallion**. No neon trim or blue/red gradient backgrounds. Show “Who wins?”,
the two attack sprites, and each civilization emblem immediately before its
name on one line. Remove leading “Elite”/“Heavy” from opening names only.
No HP queues, stats cards, costs or battle description appear in this screen.

Let `dA` and `dB` be each complete attack's summed frame durations in seconds,
divided by the intro playback speed. Derive timings for each pairing:
For a longer voice, use the later of animation end and voice end as that
unit's **turn end** in the handoff/reveal rules below. Otherwise these timings
are unchanged. The final one-second pause begins at the final turn end.

| Event | Time from video start |
| --- | --- |
| A animation and voice start together | `sA = 0.25s` |
| A animation ends | `eA = sA + dA` |
| B animation and voice start together | `sB = eA + 0.20s` |
| B animation ends | `eB = sB + dB` |
| Panels begin opening | `eB + 0.40s` |
| Battle starts, panels fully open | `eB + 1.00s` |

Each unit attacks **once**. It holds its first pose before its turn and its
last pose afterward. No simultaneous loops, voice-after-animation delay, or
fixed five-second opener. The 0.6s upward/downward panel reveal is included
within the final one-second gap, not added after it. The first battle frame
sits beneath the reveal; no actual combat is consumed behind closed panels.

`overlay.shorts_story.sequential_intro_seconds` computes the last animation end
plus one second. The main renderer uses it whenever `intro_attack_starts` is
provided; timings are rounded to the delivery frame grid. Build the intro WAV
to this same duration, and shift battle audio and all exit/victory timestamps
together. Do not carry over a five-second audio pad or old timeline metadata.
The final batch compositor also accounts for longer native spoken lines before
rounding its explicit intro duration; a pose hold does not repeat the attack.

Approved example: A attacks 0.25–1.25s; B attacks 1.45–2.45s; panels open
2.85–3.45s; battle starts at **3.45s**. These are example values, not constants
to copy to units with different animation durations.

## 4. Gameplay, enhancement and floating overlays

Use the fast **Compact Real-ESRGAN `realesr-general-x4v3.pth`** treatment of the
approved v15 sample: enhance gameplay at its delivery viewport, then blend
75% enhanced / 25% source. Compose overlays afterward so text and icons remain
untouched. This is the finalized speed-first format; the earlier SeedVR2-first
experiments are not the default for this recipe. Preserve existing approved
Seed/HAT exports and caches; do not regenerate them merely to change bookends.

- Deliver 1080 × 1920 H.264/yuv420p with AAC stereo 48 kHz. Preserve recording
  cadence (the approved sample is 60 fps); no frame interpolation or gameplay
  speed changes.
- Float the HP queues and cards over surrounding terrain/allowed bars, outside
  the protected fight. Readability fades are neutral and **at most 15% opaque**,
  not solid black panels. They must not obscure the central ongoing action.
- Cards slide in from opposite sides over 0.65s when battle begins.
- Keep full unit names, icons and stats in the cards. Below the divider, show
  applicable special effects as green text. Show discounted food/wood/gold
  costs with game icons, omit zero-cost resources, and never label “per unit.”
- Preserve verified entity HP timing, death ordering, and original combat
  audio. Keep the saved plan's actual comparison and P4 description.

## 5. Aftermath, exit and winner screen

Play **two seconds of real recorded aftermath** after battle completion, then
the **1.2-second exit transition**. Cards slide/fade outward; header/footer
fade; game artwork sweeps top to bottom; the winner ornament, attack sprite,
HP and website message fade in. The final recorded frame may be held under
this transition only. The transition does not steal time from the ending.

Hold the fully revealed winner screen for **five seconds**, or the native
victory cue's duration if shorter. This is independent of attack-loop length.
Use the same full-height game-art background, the actual victorious main army,
and a looping attack at the existing normal ending speed. Show only victory,
never a separate losing/defeat screen. No stats cards, costs, detailed bottom
section, or separate black footer.

Show `44% HP`-style whole percentages and a matching proportional bar, computed
from the **winner's entire initial main-army HP**. The result's translucent
backing spans the full width (approved alpha 140/255, distinct from the battle
HUD's 15% readability fades). The footer message is:
**“Visit aoe2matchup.com for more simulations.”**

Use the game's actual victory music at **0.70 linear gain relative to the
original decoded cue**, not 70% of an already-reduced file. Do not reduce
voices or combat along with it. Music continues through the full ending and
has the final 80ms fade. The renderer starts it during the content reveal when
the cue has sufficient length: for the approved 5.5s source and 1.2s exit, it
starts 0.8s into the exit and plays 5.4s through the five-second hold.

## Applying the recipe with the existing tools

1. Stage the requested archived run and prepare its telemetry battle with
   `build_story_batch.prepare_item(..., cache_gameplay=False, aftermath_seconds=2)`.
   Prepare the matching stats, animation folders, command voices and camera.
2. Calculate the two starts and intro length above. Produce a stereo 48 kHz
   intro WAV with each voice delayed to its animation start. Prepare a separate
   victory WAV at gain 0.7 from the original cue, recording that gain once.
3. Render with the existing explicit options (variables below are the prepared
   paths and calculated values, not new CLI features):

   ```powershell
   & $Py apps/video/build_story_short.py render `
       --battle $Battle --output $NewOutput `
       --enhance-model $CompactWeights --attack-frames $AttackRoot `
       --intro-audio $IntroWav --intro-attack-speed 1.5 `
       --intro-attack-starts $FirstStart $SecondStart `
       --exit-seconds 1.2 --victory-audio $VictoryAt70PercentWav
   ```

   Configure the existing video Python environment, game-assets path and
   FFmpeg/FFprobe as described in the main runbook. Record the original victory
   source and 0.7 gain alongside the renderer's story metadata; the current
   renderer does not apply a victory-gain flag itself.
4. For an intro/audio-only revision, reuse the existing enhanced battle/exit/
   ending as the v15 local driver does. Trim at the **source** intro boundary;
   concatenate the new opener; recalculate every downstream timestamp and
   total frame count. Do not rerun GPU enhancement or overwrite the old export.
5. Verify the final MP4 and save its evidence below. Publication and phone
   transfer are separate actions, only when requested.

**Current tooling boundary:** `build_story_short.py` supports dynamic one-shot
timing, but its bare defaults and `build_story_batch.py`'s older `main()` do
not assemble this complete preset automatically. The latter omits the new
voices, aftermath and exit settings. Use the explicit preparation/render
recipe above. The local `build_sequential_intro_sample.py` is a reproducible
Grenadier/Huskarl reference, not a generic command to run blindly for another
pairing. Do not claim that unprepared unit assets or voice mappings exist.

## Per-output acceptance record

Keep the final MP4, `story.json`, voice provenance, source/plan references,
camera and stats, representative frame previews, and `verification.json`
under ignored `data/local/`. Keep reusable code and this recipe in the repo.

- Full-file decode succeeds; dimensions/codecs, frame count and audio duration
  match the story. Check the exported media, not just an encoder exit code.
- Animation/voice starts align (the reference's audible onsets are within one
  60-fps frame), inter-unit gap is 0.2s, and battle starts one second after
  the final turn (animation plus any required spoken-line pose hold). Check
  the reveal and audible handoff, not only the cue metadata.
- Sample opening, contact, mid/late battle, aftermath, exit and full ending.
  Verify visible action, smooth crop, attached shadows, readable floating HUD,
  true winner/HP, intact ending duration and quieter victory audio.
- Save exact output hash, timing and review evidence. A different pairing has
  not been visually approved merely because it uses this approved template.

### Approved reference

Local folder (relative to repo):
`data/local/iconic-shorts-v8-20260921/command-voice-preview/10-grenadier-vs-huskarl-v15/`.

- File: `Grenadier-vs-Huskarl-Short-v15-Dynamic-Intro.mp4`.
- 1080 × 1920, 60 fps, 1,205 frames, 20.083333s; battle begins at 3.45s.
- SHA-256: `d355fc50cdea6246572d76f9c84f78dbf3fbba227f19ee18b0b6c7f1291b1f82`.
- User approved this output/process on 2026-09-22. Earlier v9–v14 exports
  remain revision evidence, not the final timing specification.

For source preparation and supporting commands, see the
[video production runbook](../VIDEO_PRODUCTION_RUNBOOK.md). For implementation
details and historical decisions, see [SHORTS_CAMERA.md](../../apps/video/SHORTS_CAMERA.md).
