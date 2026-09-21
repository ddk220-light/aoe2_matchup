# Four-civilization comparison overlay prototype

Review target: Incas, Mapuche, Muisca and Tupi Elite Champi Warriors against
Armenian Elite Composite Bowmen. This uses the **geometric** recordings, not the
older equal-resource or four-arena scenario captures. It does not publish videos
or interact with the running game.

## Inputs and reproduction

Renderer: `apps/video/build_champi_comparison_overlay.py`.
Output workspace: `data/local/champi-comparison-overlay-v2`.
Archive indexes: `D:/AoE2 Renders/champi-geometric-{civ}/run.json`.

Use the video Python environment, installed game assets and FFmpeg. From the
repository root, set `PYTHONPATH=apps/video;.`. Prepare each of `incas`, `mapuche`,
`muisca`, `tupi` using this Python pattern:

```python
import json
from pathlib import Path
from materialize_compact_recording import materialize
from overlay.auto_alignment import align
from overlay.unit_timeline import decode

out = Path('data/local/champi-comparison-overlay-v2').resolve()
for civ in ('incas', 'mapuche', 'muisca', 'tupi'):
    job = f'champi_geometric_{civ}_01_elite_composite_bowman_armenians'
    run = out / 'render-workspace' / job / 'live/run_001'
    if not (run / 'battle.mp4').exists():
        run = materialize(
            Path(f'D:/AoE2 Renders/champi-geometric-{civ}/run.json'),
            job, out / 'render-workspace')
    align(run)  # Do not bypass a failed/ambiguous visual HP alignment.
    (run / 'timeline.json').write_text(json.dumps(decode(run)))
```

Then run:

```powershell
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe apps/video/build_champi_comparison_overlay.py --stills-only
apps/video/.venv/Scripts/python.exe apps/video/build_champi_comparison_overlay.py
apps/video/.venv/Scripts/python.exe -m unittest apps/video/test_champi_comparison_tally.py
```

The materializer verifies archived file sizes and SHA-256 hashes before creating
disposable render inputs. Keep the archive `run.json`: the recording clock,
plans and source identities are needed alongside the two large media files.

## Layout and timing

- 2560 × 1440, 30 fps; four 640 × 960 views above one continuous civ-themed
  parchment and border. A vertical divider separates opponent stats and tally.
- The footer and civilization labels use the same installed font atlas as the
  unit stats. The only tally heading is “Tally of best winners”.
- The stats divider is fixed at x=650. Text fits within its reserved column;
  long bonus annotations move below the stat rows rather than crossing it.
- Approved reminders beneath the civilization names:
  Incas: “Cheaper food; +1 melee/+1 pierce armor”; Mapuche: “+15 HP; moves slower”;
  Muisca: “Moves faster; +3 melee armor; -2 attack”; Tupi: “Attacks faster; -2 attack”.
  Stat differences use a fully upgraded Champi without civilization bonuses as baseline.
- Source crop is locked at 960 × 1440 at x=890, scaled uniformly by 2/3.
  The user explicitly approved occasional units being cut off at the edges;
  do not widen, pan, pad or otherwise change the crop for the comparison videos.
- Remove only the first 0.4 seconds of camera settling. All four featured and
  opponent armies still have their full opening HP at this time.
- Civilization name and emblem are placed over the top of the footage.
- No live HP grids. Each panel freezes and displays its result at its verified
  final damage event; retain all results for three seconds after the last end.
- The original game Trajan Pro fonts and victory/defeat ornaments are reused.
  A semi-transparent grey backing follows the user's latest reference.
- Original audio comes from the longest battle (Mapuche); other feeds are silent.
  It fades out during the final hold.

## Result and tally meaning

HP is surviving **winner** HP divided by that side's opening HP. Buffer Hussars
are excluded. A defeated Champi panel labels this explicitly as opponent HP.

The tally credits only victorious Champi civilizations, selecting the highest
unrounded surviving HP percentage. Exact ties share credit. Entries use transparent
unit sprites; an outline indicates the only civilization that won (the serialized
`bold` field is retained for compatibility). All four lose this Armenian matchup, so its tally
stays empty; do not credit Muisca just for the least severe defeat.

Result medals rank all four outcomes independently of the tally. Victories rank
above defeats; more own HP is better for victories, less enemy HP is better for
defeats. Battle duration has no effect. Ties share a rank. Use installed gold,
silver and bronze medals for ranks 1–3; rank 4 has no medal. No numeric labels.
Defeat medals are slightly dimmer, preserving distinct metal colors.
For this matchup the ranks are Muisca 1, Mapuche 2, Tupi 3, Incas 4.

`update_tally` accepts prior completed entries without modifying them. The review
renderer starts with an empty tally. `build_champi_comparison_series.py` prepares
the first five archived opponents, verifies all 20 timelines, renders chapters
sequentially with a cumulative tally, and concatenates the completed chapters.

```powershell
$env:PYTHONPATH='apps/video;.'
$env:OPENCV_FFMPEG_THREADS='2'
apps/video/.venv/Scripts/python.exe apps/video/build_champi_comparison_series.py --count 5
```

Output: `data/local/champi-comparison-first-five/Champi_Four_Civs_First_Five_Matchups.mp4`.
The input and series manifests record source runs, result times, ranks, tally
state and output metadata. `--prepare-only` stops after materializing/alignment;
`--stills-only` renders review frames without encoding video.

Inspect `comparison-manifest.json`, opening/combat/result stills and the encoded
MP4 before sharing. Source archives and active capture processes are untouched.

## Full comparison render

The approved full comparison uses all 74 archived opponents, with Incas, Mapuche,
Muisca and Tupi shown together. Keep the approved crop and layout unchanged.

```powershell
$env:PYTHONPATH='apps/video;.'
$env:PYTHONIOENCODING='utf-8'
$env:OPENCV_FFMPEG_THREADS='2'
apps/video/.venv/Scripts/python.exe apps/video/build_champi_comparison_series.py --all --output data/local/champi-comparison-full
```

Preparation and encoding proceed chapter by chapter. Two bounded workers align
the four sources, then one encoder renders the chapter. The existing temperature
guard runs every 15 minutes; a thermal pause or less than 8 GiB free blocks further
work. `status.json`, `worker.log` (when launched with redirected output), and
`render-progress.json` show progress. Alignment failures stop the sequence rather
than silently omitting a matchup or corrupting the cumulative tally.

Each chapter is decoded before its checkpoint is accepted. Restart the same
command after resolving a failure: matching renderer/input/tally checkpoints reuse
completed chapter videos. The final output is
`Champi_Four_Civs_All_Unique_Units.mp4`. `series-manifest.json` contains the ordered
chapter results and final tally. No upload is performed by this command.

For future overlay edits retain the four `D:/AoE2 Renders/champi-geometric-*`
archives (named raw MP4 and frames pairs plus `run.json`), the alignment/timeline
JSON, source indexes, series manifests and renderer source. The `rebuild` folder
in this run holds small source/index snapshots. Game artwork/fonts and reference
stats remain in their existing installations/repository. Render-workspace media
are disposable copies of hash-verified archive inputs; they are not the originals.
Only prune those copies or intermediate rendered chapters after the final file
passes review and the original archive pairs are still verified. Preserve timing
metadata so a later overlay revision need not repeat alignment.
