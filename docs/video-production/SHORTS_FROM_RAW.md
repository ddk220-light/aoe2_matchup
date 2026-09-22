# Raw recording to finalized two-unit Short

Finalized on **2026-09-22**, after the ten-video review batch. This is the
operator procedure; [SHORTS_APPROVED_WORKFLOW.md](SHORTS_APPROVED_WORKFLOW.md)
is the visual/audio specification. Follow that specification, not earlier
experiments in `SHORTS_CAMERA.md`.

This is an **offline render**. Do not launch AoE2, run another simulation,
recapture a battle, publish, or Taildrop as part of it. A raw MP4 alone is not
sufficient: the matching recording metadata, telemetry and saved plan are
required for honest HP, costs, framing and results.

## 1. Locate and preserve the source

Find the requested pairing in the existing local, F: or E: archive. Select by
actual units, civilizations, upgrades, costs and recorded conditions, not just
folder names. A newer policy label does not justify re-recording valid footage.

The two supported source layouts are:

- Full recording: `<job>/plan.json` and `<job>/live/run_001/recording.json`.
  The latter identifies the original video and frames files and their hashes.
- Compact archive: an archive `run.json` plus its exact `sourceJob` identifier;
  `materialize_compact_recording.materialize` restores the source locally.

Use one entry with **number 1** for a new standalone Short:

```json
{
  "root": "D:/AI/aoe2_matchup/data/local/my-new-short",
  "victoryAudio": "D:/AI/aoe2_matchup/data/local/my-new-short/audio/victory.wav",
  "items": [{
    "number": 1,
    "key": "unit-a-vs-unit-b",
    "title": "Unit A vs Unit B",
    "sourceRun": "F:/AoE2 Renders/campaign/captures/exact-job/live/run_001"
  }]
}
```

For a compact archive, replace `sourceRun` with `sourceIndex` and `sourceJob`.
Save this as the new local folder's `batch.json`, replacing the reference
manifest's ten entries. Keep the actual **P2/top/left, P3/bottom/right** order,
even if the display title lists the matchup in reverse. Never modify the
archived source to change its winner, costs, relics or P4 screen.

## 2. Set up the offline workspace

Use the established video Python environment. It needs NumPy, Pillow, OpenCV,
the existing telemetry/Scenario Parser dependencies, `genieutils`, and the
existing CUDA PyTorch/Spandrel stack. See [workstation setup](SETUP_AND_DATA.md).
For this workflow, no live client credentials, upload credentials or narration
service are needed.

The tested workstation uses:

| Input | Tested location / treatment |
| --- | --- |
| Python | `D:/miniconda3/python.exe` |
| Game | `D:/SteamLibrary/steamapps/common/AoE2DE` |
| FFmpeg/FFprobe | `D:/AI/environments/comfy-env/.pixi/envs/geometrypack-nodes/Library/bin` |
| Gameplay model | `data/local/video-recreate-blackwood-20260920/realesr-general-x4v3.pth` |
| Sprite model | Existing HAT Sharper weights used by `prepare_story_attacks.py` |
| Audio decoder | Existing local `vgmstream-cli.exe` |

No model download or upgrade is necessary on this workstation. Preserve good
existing enhanced footage, sprites and camera paths instead of enhancing twice.

The exact final assembly and voice scripts are preserved as a
[source reference bundle](reference/shorts-v15/README.md). Restore those files
into the **new** `data/local/<batch-name>/` folder, retaining their relative
paths. Do not execute them inside `docs/`: their path calculations deliberately
refer to the original local working layout. `run_batch.py` is imported only as
the tested environment initializer; running it directly launches an older batch.

```powershell
# Run from the repository root. Use a NEW local output folder.
$ShortPython = 'D:/miniconda3/python.exe'
$ShortRoot = Join-Path (Get-Location).Path 'data/local/my-new-short'
$ShortReference = 'docs/video-production/reference/shorts-v15'
New-Item -ItemType Directory -Path $ShortRoot
Copy-Item -Path "$ShortReference/*" -Destination $ShortRoot -Recurse
Rename-Item -LiteralPath "$ShortRoot/test_final_batch.py.txt" -NewName 'test_final_batch.py'
$env:SHORTS_ROOT = $ShortRoot
```

Replace the copied `batch.json` with the intended source entry before running
anything. On another workstation, adjust `run_batch.py`'s game/FFmpeg paths,
the voice catalog's decoder path, model path and manifest source paths. Its
`google.__path__` addition is a workaround for this workstation's split Python
environment, not a requirement to install another copy of Python everywhere.

## 3. Stage, align, trim and plan the camera

Run this Python block through the configured environment (PowerShell syntax
below). It copies/materializes the archived source locally, verifies copied
hashes, reuses or computes HP/video alignment, resolves stats read-only, and
plans the telemetry-guided camera. It does **not** render or capture yet.

```powershell
@'
import os, sys
from pathlib import Path
root = Path(os.environ['SHORTS_ROOT'])
sys.path.insert(0, str(root))
import run_batch
from build_story_batch import read, prepare_item
from render_final_batch import previous_folder
item = read(root/'batch.json')['items'][0]
output = previous_folder(item)
battle = prepare_item(item, root, output, cache_gameplay=False, aftermath_seconds=0)
print(battle)
'@ | & $ShortPython -
```

For this **two-pass recipe**, the intermediate battle contains combat only;
the final compositor adds the two seconds of real aftermath from the raw file.
Do not include aftermath in both passes. For a separate direct-render route,
`prepare_item(..., aftermath_seconds=2)` includes it up front instead.

Required prepared files include `battle/camera.json`, `battle/manifest.json`,
`unit-hp-overlay/units.json`, accepted `alignment.json`, and
`static-stats-overlay/stats.json`. Check that the recording contains at least
two seconds after the selected terminal frame. If not, report the available
tail rather than inventing it or silently cutting the requested hold.

The camera holds until main-army contact, zooms in smoothly without reversing,
favors vertical movement, and caps horizontal travel at 40 source pixels.
The protected fight is 1080-square at y=330. P4 can guide framing but cannot
enter the main-army counts, costs or winner/HP calculation.

## 4. Prepare the two attack animations

Reuse the approved PNG caches where available. Otherwise create a local
`attack-units.json`: an array of `[slug, native_sprite_stub, team_color,
shadow_gamma]`. For example, the original asset mapping was:

```json
[
  ["elite_blackwood_archer", "u_arc_blackwood_archer_elite", "blue", 0.6],
  ["elite_huskarl", "u_inf_huskarl_elite", "red", 1]
]
```

Use the **actual** units' asset stubs, not these example identities. Output
folder names must match `unit.lower().replace(' ', '_')` from prepared stats.
The corresponding `_attackA_x2.sld` files must already be extracted under
`graphics/game_raw_files/`.

```powershell
# Set $ShortHatWeights to the existing HAT Sharper weights file.
$env:PYTHONPATH = "apps/video;."
& $ShortPython apps/video/prepare_story_attacks.py `
  --units "$ShortRoot/attack-units.json" --output "$ShortRoot/attacks" `
  --weights $ShortHatWeights
```

Inspect both units once: intact faces, continuous team-color masks, stable
canvas and native pose-matched shadows touching the unit. Do not use old
paletted Blackwood frames or a detached generic shadow ellipse.

## 5. Resolve the spoken command lines and victory cue

Follow `DAT unit -> attack command event -> Play action -> civilization switch
or unit-specific speech action -> random variants -> sound/media IDs`.
Decode every relevant variant and keep the longest spoken one. The preserved
`final-v15/voices/build_catalog.py` implements the installed bank-v154 layout;
its fixture aliases document the identities used in the ten-video batch.
For a new identity, verify its real fixture/unit ID and civilization mapping
before extending that mapping. A familiar-looking filename is not evidence.

Generate the catalog's bank-object input from the installed game using the
existing parser (the assertion also prevents silently using a different bank):

```powershell
@'
import os, sys
from pathlib import Path
root = Path(os.environ['SHORTS_ROOT'])
sys.path.insert(0, str(root))
import run_batch
from extract_intro_reference import banks, objects
from overlay.static_stats import GAME
from build_story_batch import save
bank_id, raw = next((i, raw) for i, raw in banks(GAME/'wwise/Base.pck') if i == 232745270)
save(root/'command-voice-preview/Base-232745270-objects.json',
     {str(i): {'kind': kind, 'data': data.hex()} for i, (kind, data) in objects(raw).items()})
'@ | & $ShortPython -
& $ShortPython "$ShortRoot/final-v15/voices/build_catalog.py"
& $ShortPython "$ShortRoot/final-v15/voices/build_editorial_candidates.py"
```

Known routing in the completed batch:

- Human spoken attack event: `3761709415`, civilization switch `329664771`.
- Mounted event `3139909899` is horse audio, not speech. The user approved
  **same-civilization human attack speech** instead; retain both event IDs.
- Xianbei event `13823237` has three actions. Spoken action `915835144`
  targets container `835767286`; exclude the weapon/exertion and mounted-effect
  actions. `inspect_xianbei_actions.py` records that evidence when needed.

Keep `catalog.json`, `editorial-candidates.json`, decoded WAVs and provenance
local. The compositor selects approved spoken candidates automatically when
the DAT response is marked `spoken:false`. Do not use weapon impacts or intro
music in place of the requested spoken orders.

Reuse the original full-volume victory WAV and `victory-source.json`. The
verified installed mapping was `Play_Victory`, event `2453267296`, bank
`232745270`, media `149728724` in `Base.pck` (embedded DIDX/DATA), decoded by
vgmstream into 5.5 seconds at 48 kHz stereo. If the source is missing, verify
the installed mapping before using `extract_intro_music.py --media-id 149728724
--package <game>/wwise/Base.pck --decoder <vgmstream> --output <local>/victory.wem`.
Do not use `extract_intro_reference.py`'s campaign-voice default for this cue.

The final compositor makes a separate **0.7-gain** victory WAV. Give the manifest
the original full-volume file, not a file already reduced to 70%.

## 6. Render one pilot, then the selected batch

For a **new raw pairing**, build the intermediate enhanced combat once and
immediately wrap it in the finalized bookends. This uses the copied reference
driver's real functions, including long-voice holds and silent-tail trimming:

```powershell
@'
import os, sys
from pathlib import Path
root = Path(os.environ['SHORTS_ROOT'])
sys.path.insert(0, str(root))
import run_batch
import render_final_batch as final
from build_story_batch import read, previews
from build_story_short import render
from overlay.video_enhance import LocalUpscaler
batch = read(root/'batch.json')
item = batch['items'][0]  # new standalone recipe uses number 1
previous = final.previous_folder(item)
battle = previous/'battle'
previews(battle, previous, root/'attacks', recording_top=160)
model = LocalUpscaler(final.MODEL)
render(battle, previous, victory_audio=Path(batch['victoryAudio']),
       attack_frames=root/'attacks', upscaler=model)
final.compose(item, model)
'@ | & $ShortPython -
```

Review the preflight before rendering if unit assets or camera framing are
unfamiliar: run the block only through `previews(...)`, inspect its sheet, then
continue the render calls. If a valid intermediate combat export already
exists, skip `render(...)` and reuse it with `final.compose(...)`.

The intermediate opener/ending are discarded. Final assembly reuses only its
combat frames, adds two raw-recorded aftermath seconds, and regenerates the
opening, exit and victory screen. This keeps expensive enhancement out of
audio-only revisions. Do not run SeedVR2 again to change an intro.

Final timing, using attack duration divided by 1.5 and native-speed speech:

```text
A starts = 0.25
A turn ends = A starts + max(A attack duration, A trimmed speech duration)
B starts = A turn ends + 0.20
B turn ends = B starts + max(B attack duration, B trimmed speech duration)
Panels open = B turn ends + 0.40
Battle starts = B turn ends + 1.00  (rounded to the video frame grid)
Real aftermath = 2.00
Exit transition = 1.20
Fully revealed winner screen = 5.00
```

One attack each; hold the final pose during longer speech. Voices are normalized
to -6 dBFS at native pitch/speed. Remove excess silence with a 12ms boundary pad
so file padding does not create another long handoff. Opening is not fixed at
five seconds. Victory music starts 0.8s into the exit and runs through the full
ending at 70% of the original cue, with an 80ms fade.

**Existing completed ten-video batch only:** restore/use its original local
layout and run the following if regeneration is actually needed:

```powershell
& $ShortPython "$ShortRoot/test_final_batch.py"
& $ShortPython "$ShortRoot/render_final_batch.py" --numbers 1 2 3 4 5 6 7 8 9 10
```

The batch driver resumes by skipping outputs with an existing timing audit.
Those flags are not a forced rerender. For a deliberately revised clip, use
`compose(item, model)` explicitly after checking the target; it replaces that
generated final export, never the archived recording. Preserve an approved
export under a new revision directory before intentionally replacing it.

Number 3 reuses the corrected Teutonic camera/Seed export, number 4 the existing
Samurai/Obuch enhanced export, and number 10 retains the approved Grenadier/
Huskarl v15 byte-for-byte. These are **batch-specific reuse choices**, not
automatic asset discovery for arbitrary matchups. The reference tests and
`finish_final_batch.py` also target that exact ten-item dataset.

## 7. Check and hand off the actual exports

Each final folder contains the MP4, `story.json`, `voice-provenance.json`,
`verification.json`, `timing-audit.json`, camera/trim metadata and
`review-sheet.jpg`. Verify full-file decode, 1080x1920 H.264/AAC at 48 kHz,
recorded frame cadence, audio duration, intro onset and handoff, real aftermath,
full ending and measured victory gain. The compositor performs these checks.

Inspect the **actual exported** intro, reveal, contact, middle/late fight,
aftermath, exit and ending. Confirm readable nonzero discounted costs and green
effects, unobstructed action, correct units/civs, attached shadows, winner-only
result, proportional whole-army HP and the website message. A passing encoder
or a reused template is not visual approval.

After inspecting all ten original-batch review sheets, run
`finish_final_batch.py` to create `REVIEW.md` and `completion.json`. Do not run
that script before inspection: it records the operator's review as performed.
For a single/new batch, record only the clips actually checked; do not claim
the reference finisher validated a different roster.

Keep raw media, extracted audio/art, weights and output videos in ignored local
storage. Commit the reusable renderer, tests, this procedure and reference
scripts. Deliver local links for review. Git push, Taildrop, YouTube upload and
public release are separate actions requiring their own requested scope.

The completed batch is indexed locally at
`data/local/iconic-shorts-v8-20260921/final-v15/REVIEW.md`; its ten media hashes,
durations and evidence are in `completion.json`. No raw footage was recaptured
or modified, and no videos were published as part of that render.
