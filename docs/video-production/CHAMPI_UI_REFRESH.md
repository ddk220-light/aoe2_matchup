# Champi comparison overlay revision

Approved changes, September 15, 2026:

- Each panel shows its actual opening army sizes below the civilization header:
  featured Champi first, opponent second, e.g. `27 vs 24`. These stay fixed for
  the chapter. They do not count the P4 Hussar buffer or replace the final HP result.
- Tally sprites are approximately 10% larger (66-pixel cells instead of 60).
- Sole victories use a soft amber halo behind the sprite, with no solid outline.
  The serialized `bold` flag retains its existing sole-winner meaning.
- Tally icons must have actual transparency. Opaque portrait fallback is forbidden.
- The opponent title, portrait frame, HP bar and HP text share x=192, safely inside
  the widest civilization border. Stats remain inside the fixed x=650 divider.

`apps/video/build_champi_comparison_overlay.py` implements these defaults for
future rendering. `apps/video/refresh_champi_comparison_ui.py` applies them to the
previously verified 74-chapter compilation, retaining its exact crop and result
timing. It replaces the whole footer, adds the new count labels, copies chapter
audio, uses NVENC hardware encoding with automatic CPU thread allocation for
offline rendering, checks chapter decoding, and reassembles
the existing intro/end around the updated matchups. No game recapture is needed.

```powershell
$env:PYTHONPATH='apps/video;.'
apps/video/.venv/Scripts/python.exe apps/video/refresh_champi_comparison_ui.py --preview-only
apps/video/.venv/Scripts/python.exe apps/video/refresh_champi_comparison_ui.py
```

Outputs and resumable checkpoints are under `data/local/champi-overlay-v3`.
The original master and chapter files under `champi-comparison-full` are retained.
`icon-audit.json` records the 74 resolved sprite paths and alpha-channel ranges.

The two War Chariot modes now resolve to the existing transparent
`war_chariot_3k.png`. Missing Missionary and Flaming Camel sprites were decoded
from the installed game's `u_monk_missionary_idleA_x2.sld` and
`u_cam_flaming_camel_idleA_x2.sld`, using direction 6 and the existing red-team
sprite decoder. Their PNGs live alongside the other website unit sprites.
Extraction source hashes are recorded in `data/local/champi-icon-extraction.json`.
No invented unit artwork or generated replacement was necessary.

The current complete video includes restored Pachacuti narration on both intro
pages. Page one reveals its written text; page two reveals whole civilization
columns at their spoken paragraph starts and holds for three seconds after the
voiceover. Its commentary is not printed on screen. See
[bookend instructions](CHAMPI_COMPARISON_BOOKENDS.md) for the current rebuild.
