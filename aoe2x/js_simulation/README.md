# Clean-room JavaScript simulation

This directory is the isolated replacement simulator laboratory. Stage 1 adds
the exact scenario-derived 21-versus-21 infantry placement to the map inspector.
It still loads no production engine code and contains no clock, movement,
targeting, collision physics, or combat behavior.

## Locked milestone

[Milestone 01: Golden melee arena locked](docs/MILESTONE_01_GOLDEN_MELEE_ARENA.md)
defines the canonical map and 21-versus-21 starting positions for every
melee-versus-melee clean-room simulation.

## Authoritative map fixture

The checked-in source is:

`fixtures/source/golden_meleevsmelee.aoe2scenario`

SHA-256:

`f10508cbe6ec6211d611c35d411ad7e40b38c96b6ef0d6b0d651daa42df645a4`

Repository source:

`origin/staging:apps/video/templates/golden_meleevsmelee.aoe2scenario`

The fight-specific staging scenarios, including `golden_meleevsmelee`, were
parsed with AoE2ScenarioParser 0.8.2 before selection. The dedicated melee
scenario preserves the same terrain hash
`b26cb070467b57e64d6b28450d9a64bbc95121499f3053f7b9a97698ce7d9c4d`
and Gaia-object hash
`4cfd18f4aae0466863ec32bf02a62bdff9866d24bc71bcba008b0fa5a8301254`.

`golden_meleevsmelee` is used because it is the current dedicated golden
melee-versus-melee engagement template on staging.

## Run the viewer

From the repository root:

```powershell
node aoe2x/js_simulation/server.mjs --host 127.0.0.1 --port 5011
```

Open `http://127.0.0.1:5011/`.

The default bind is local-only. Use an explicit host only when exposing it
through the local Tailnet configuration.

## Regenerate the derived JSON

Requires Python and AoE2ScenarioParser 0.8.2:

```powershell
python aoe2x/js_simulation/tools/export_golden_map.py `
  --scenario aoe2x/js_simulation/fixtures/source/golden_meleevsmelee.aoe2scenario `
  --output aoe2x/js_simulation/fixtures/golden_map.json
```

The exporter preserves all 256 terrain tiles and all 101 Gaia objects. Unknown
terrain or object IDs are retained with an `UNKNOWN_<id>` name rather than
being discarded.

## Tests

```powershell
python -m pytest tests/test_cleanroom_map_export.py -q -p no:cacheprovider
node --test aoe2x/js_simulation/tests
```

The map fixture is read-only. Viewer controls affect only presentation.

## Formation fixture

`fixtures/golden_formation_21v21.json` contains the exact first 21 Player 2
records and first 21 Player 3 records retained by the golden scenario builder:

- Player 2 references 1628–1648: Elite Jaguar Warrior, unit constant 726.
- Player 3 references 1699–1719: Militia, unit constant 74.

All coordinates and rotations are copied from the source scenario. The initial
42 positions have no Gaia-cell, forest-terrain, or duplicate-cell conflicts.
Markers in the viewer communicate placement and facing only; their drawn size
is not a calibrated collision radius.

## View orientation and centre

The viewer rotates the scenario coordinate plane 90 degrees counterclockwise
around the geometric map centre `(8, 8)`. This is a presentation transform;
terrain and object coordinates in `golden_map.json` remain unchanged. Render
depth and pointer picking use the same forward/inverse transform.

For the 16-by-16 source map, tile boundaries span `0..16`, so `(8, 8)` is the
exact centre. The dirt arena centroid is `(7.949, 8.051)`. The Panda Rock is
literally stored at `(9, 7)`, so the small visual offset of the central obstacle
is source-authored and must not be removed by recentering the camera.
