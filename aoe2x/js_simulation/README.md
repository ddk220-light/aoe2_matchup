# Clean-room JavaScript simulation

This directory is the isolated replacement simulator laboratory: a
deterministic 60-tick/s combat engine (`src/combat/`) rebuilt from scratch
against authorized game recordings, with every constant either dat-sourced
or measured on tape — none fitted. It loads no production engine code.

## Current status

**[Calibration status 2026-08-06](docs/CALIBRATION_STATUS_2026-08-06.md):
28 matchups, 140 tape ratios, 0 wrong winners.** Coverage: melee
(champion/paladin/steppe/elephant), Fire Lancer charge attacks, projectile
combat with ballistics lead, scorpion pass-through bolts, mangonel blast,
projectile accuracy, minimum range, and both sides of the scripted-kiting
AI (arbalester / elite skirmisher / heavy cavalry archer versus champion /
paladin / elite steppe lancer / elite battle elephant / elite fire
lancer). Per-mechanic measurement docs live in `docs/`; start with the
status file and
[the kiting order layer](docs/KITING_AI_ORDER_LAYER_2026-08-06.md).

Calibration circuit metric: signed winner-HP% (winner's remaining HP as a
percent of its own starting pool) with the sim's 25-sampled-order median
scored against the tape's five-repeat band per ratio.

Held-out check on the standard-units archive (101 distinct matchups, 14
units, nothing in it used to set a constant): winner correct in 97/101,
mean winner-HP% delta 14.7 — **[full table per matchup, with the
independently derived purchase and the tape's own numbers, in the standard
units summary](docs/STANDARD_UNITS_SUMMARY_2026-08-07.md)**.

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

The calibrated configuration (`engagement=pursuit`, `orders=1`) is now the
committed default in `src/engine-config.js`; the `AOE2X_EXP_*` environment
variables still override it for experiment sweeps. To get the
pre-calibration baseline engine back, set `AOE2X_EXP_ENGAGEMENT=free` and
`AOE2X_EXP_ORDERS=0` -- in PowerShell, `$env:AOE2X_EXP_ENGAGEMENT = ""`
*deletes* the variable rather than setting it empty, so `free` is the only
way to reach the baseline `engagement=""` arm from this project's documented
shell.

Open `http://127.0.0.1:5011/`.

The local page mirrors the web app's civilization-first Battle Simulation
picker while keeping the clean-room engine isolated from the production
simulator. The full Imperial-age catalogue is visible; units without a
clean-room mechanics profile remain disabled and are labelled **Not yet
calibrated**. The 14 registry-backed civ/unit combinations can be run with
either explicit army counts or an equal-resource budget. The centre stage
uses the isometric Golden Arena renderer and exposes deterministic playback,
damage, map-inspection, hash, and review-export tools.

### Ranged-unit navigation lab

The dedicated enemy-free movement lab runs exactly 21 owner-2 units and can
switch among Hand Cannoneer, Arbalester, Heavy Cavalry Archer, Heavy Scorpion,
and Elite Skirmisher. Its default `cohesive` navigation uses a persistent
formation anchor, collision-aware compact slots, formation-inflated central
obstacle clearance, and deterministic stall recovery. `baseline` and
`per-unit-grid` remain saved for direct visual comparison.

The cohesive run holds the source spawn until the first real AI move order,
forms the group at that order's body-safe destination, and then starts the
shared route. Heavy Scorpion uses the same mechanics-derived clock (first move
at tick 80) and an elastic leash derived from its larger collision body, so it
now completes the kiting loop instead of freezing during an oversized staging
formation.

Local:

`http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&navigation=cohesive`

Tailnet:

`https://dragonstar.tail82a190.ts.net/golden-map/?mode=hand-cannoneer-solo-movement&navigation=cohesive`

Share a selected unit with `unit=<slug>`; for example:

`https://dragonstar.tail82a190.ts.net/golden-map/?mode=hand-cannoneer-solo-movement&unit=heavy_cav_archer&navigation=cohesive`

Recurring kite timing is derived from reload and attack delay on the shared
40-tick AI command grid. The existing tape timing profiles are regression
targets, so new ranged units do not require hand-authored timing rows.

The Tailnet URL requires a device connected to the same tailnet. Always include
a verified Tailnet link when handing off a viewer page.

The selector in the page changes among all three stable deep links. The map can
show the AI waypoint, group anchor, active route waypoint, live centroid, and
every unit's effective destination, alongside cohesion, slot-error, block,
replan, travel, and stall statistics.

See
[Hand Cannoneer solo navigation lab — 2026-08-11](docs/HAND_CANNONEER_SOLO_NAVIGATION_2026-08-11.md)
for the architecture, exact 60-second comparison, deterministic hashes, test
commands, and scope boundaries.

Regenerate the deterministic viewer catalogue after the reference database
changes:

```powershell
python aoe2x/js_simulation/tools/export_viewer_catalogue.py
```

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

### Generated tables

No fixture is read on the `/api/fight` request path. Everything a free-form
fight needs from the tapes is read ONCE by a tool that emits a committed,
generated module; each one prints what it found and refuses to emit if the
archive stops agreeing with it.

```powershell
python aoe2x/js_simulation/tools/derive_placement.py      # -> src/placement-table.js
python aoe2x/js_simulation/tools/derive_kite_profiles.py  # -> src/kite-profiles.js
python aoe2x/js_simulation/tools/export_unit_costs.py     # prints the registry's baseCost column
```

`src/kite-profiles.js` carries `KITE_PROFILE_PROVENANCE`, which names the
source fixture(s) behind every row and flags the one row (Hand Cannoneer)
that is *constructed* from its dat reload because no kiting tape column for
it exists.

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
