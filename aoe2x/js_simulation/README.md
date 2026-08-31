# Live-capture JavaScript simulation

This directory is the replacement simulator laboratory: a deterministic
60-tick/s combat engine (`src/combat/`) rebuilt from scratch against the newest
relevant project-local live game recordings, with every constant either
dat-sourced or measured on tape — none fitted. It loads no production engine
code.

## Current status

The registry currently contains 34 generated unit-mechanics fixtures. The
historical dedicated corpus contains 19 matchup archives, 95 ratio rows, and
475 exact tape repeats. The most recent historical acceptance slice covers
Hand Cannoneer versus Champion and Paladin: 50/50
resolved simulations, no wrong winners, no row above 25 points, and 3.67-point
mean absolute row delta.

The newest live current-golden matrix adds 14 ranged matchups and 70 freshly
recorded game runs. The engine now agrees with all 14 winner directions and has
a 12.06-point mean absolute normalized winner-HP delta after reproducing the
Player-4 diplomacy gate, ranged-AI target spread, and Spanish gunpowder reload.

The older 2026-08-06 calibration and 17-archive 2026-08-14 full-suite reports
remain historical evidence. They predate the current native-siege,
minimum-range-retreat, exclusive allied-overlap, and Hand Cannoneer corpus
changes and must not be presented as a current full-portfolio result.

## Documentation map

- [Current engine and mechanics](docs/CURRENT_ENGINE_2026-08-15.md) — the
  authoritative description of the active tick loop, targeting, attacks,
  projectiles, kiting, navigation, collision, crowding, and limitations.
- [Golden tape comparison workflow](docs/GOLDEN_TAPE_COMPARISON_WORKFLOW.md) —
  the legacy archive workflow, retained only for interpreting historical
  reports. New work uses the latest relevant live `frames.bin` directly.
- [Recoverable benchmark runner](docs/RECOVERABLE_DEDICATED_BENCHMARKS.md) —
  operational details for full and selective runs.
- [Hand Cannoneer current-engine result](calibration/reports/hand_cannoneer_current_engine_2026-08-15/README.md) —
  the newest 10-row/50-run comparison.
- [Current ranged golden matrix](docs/RANGED_MATRIX_LIVE_OBSERVATIONS_2026-08-29.md) —
  70 live runs across 14 RvR/RvM matchups, observed targeting and diplomacy
  behavior, mechanics changes, full result table, and remaining residuals.
- [Historical 17-archive report](docs/DEDICATED_GOLDEN_RANGED_MELEE_2026-08-14.md) —
  the last full portfolio before the current changes.
- [Kiting AI order layer](docs/KITING_AI_ORDER_LAYER_2026-08-06.md) and
  [Hand Cannoneer navigation lab](docs/HAND_CANNONEER_SOLO_NAVIGATION_2026-08-11.md) —
  detailed derivations behind two major subsystems.

Calibration circuit metric: signed winner-HP% (winner's remaining HP as a
percent of its own starting pool) with the sim's 25-sampled-order median
scored against the tape's five-repeat band per ratio.

Historical held-out check on the standard-units archive (101 distinct matchups,
14 units, nothing in it used to set a constant): winner correct in 97/101,
mean winner-HP% delta 14.7 — **[full table per matchup, with the
independently derived purchase and the tape's own numbers, in the standard
units summary](docs/STANDARD_UNITS_SUMMARY_2026-08-07.md)**.

## Locked milestone

[Milestone 01: Golden melee arena locked](docs/MILESTONE_01_GOLDEN_MELEE_ARENA.md)
records the earlier milestone. The active viewer now uses the current
27-versus-27 melee golden map and ordered starting slots captured on 2026-08-28.

## Authoritative map fixture

The checked-in source is:

`calibration/live_observations/current_melee_golden_2026-08-28/source/meleevsmelee.aoe2scenario`

The latest project-local live scenario source is used directly. No archive,
manifest, or hash prerequisite applies to the active workflow.

The source was parsed with AoE2ScenarioParser 0.8.3. The literal export contains
256 terrain tiles and 152 Gaia objects; no inferred map geometry is written to
the viewer fixture.

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

The fight endpoint automatically loads measured opening profiles
for the exact observed `23 Champion vs 27 Halberdier`,
`27 Champion vs 16 Paladin`, and
`27 Spanish Paladin vs 21 Burmese Elite Battle Elephant` rosters. For the last
one, open the viewer with
`?mode=battle&side2=paladin&n2=27&side3=elite_elephant&n3=21`; other counts use
the general engine rather than silently stretching a matchup-specific profile.

It also recognizes the exact 14 current ranged-golden rosters documented in
`docs/RANGED_MATRIX_LIVE_OBSERVATIONS_2026-08-29.md`. Those requests use the
literal current RvR/RvM first-N slots and patrols; RvM also uses its measured
Player-4 release tick. For example:

`?mode=battle&side2=arbalester&n2=27&side3=heavy_cav_archer&n3=18`

`?mode=battle&side2=hand_cannoneer&n2=27&side3=elite_steppe&n3=23`

The local page mirrors the web app's civilization-first Battle Simulation
picker while keeping the replacement engine isolated from the production
simulator. The full Imperial-age catalogue is visible; units without a
mechanics profile remain disabled and are labelled **Not yet
calibrated**. The 14 registry-backed civ/unit combinations can be run with
either explicit army counts or an equal-resource budget. The centre stage
uses the isometric Golden Arena renderer and exposes deterministic playback,
damage, map-inspection, hash, and review-export tools.

### Ranged-unit navigation lab

The dedicated enemy-free movement lab runs exactly 21 owner-2 units and can
switch among Hand Cannoneer, Arbalester, Heavy Cavalry Archer, Heavy Scorpion,
Elite Skirmisher, and Siege Onager. Its default `cohesive` navigation uses a persistent
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

### Ranged-versus-melee kiting viewer

The generalized combat viewer exposes the registry-backed ranged and melee
units for visual experimentation: Hand Cannoneer, Elite Skirmisher, Heavy
Cavalry Archer, Arbalester, Heavy Scorpion, and Siege Onager against Champion,
Halberdier, Hussar, Heavy Camel Rider, Paladin, Elite Battle Elephant, Elite
Steppe Lancer, or Elite Fire Lancer. Manual `n2`/`n3` values remain available.
Viewer availability is not evidence that a matchup has a current live capture;
new comparisons use the newest relevant project-local `frames.bin`.

Local:

`http://127.0.0.1:5011/?mode=ranged-vs-melee-kiting&ranged=heavy_cav_archer&melee=champion&navigation=cohesive`

Tailnet:

`https://dragonstar.tail82a190.ts.net/golden-map/?mode=ranged-vs-melee-kiting&ranged=heavy_cav_archer&melee=champion&navigation=cohesive`

The current exact-repeat corpus uses only 19 separately named,
SHA-256-manifested dedicated golden archives. See the
[golden tape comparison workflow](docs/GOLDEN_TAPE_COMPARISON_WORKFLOW.md),
the [recoverable benchmark runner](docs/RECOVERABLE_DEDICATED_BENCHMARKS.md),
and the historical
[2026-08-14 dedicated benchmark](docs/DEDICATED_GOLDEN_RANGED_MELEE_2026-08-14.md).

Heavy Scorpion deliberately does not use the cohesive mobile-ranged kite
controller. In combat observation and dedicated scenarios it uses native siege
targeting, pass-through bolts, and individual minimum-range retreat. The melee
opponent still uses preventive crowd steering and exclusive overlap
reservations so it can surround the siege line without collapsing into an
unbounded stack.

One-range melee chasers now use the generic reach-wedge collision policy. Any
melee unit whose sourced `attack_range_tiles` is at least one may form one
exclusive two-deep allied transit pair near its legal engagement envelope.
The rule is target-independent and does not name Elite Steppe Lancer. It does
not shrink collision bodies, admit a third overlapping ally, permit compact
four-unit cliques, or alter zero-range melee units. The current dedicated
corpus contains one eligible unit, Elite Steppe Lancer, so all 15 Steppe ratio
rows were rerun for the active
[one-range melee report](calibration/reports/experiment_one_range_melee_wedge_2026-08-14/README.md).

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

The exporter preserves all 256 terrain tiles and all 152 Gaia objects. Unknown
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
source fixture(s) behind every row. The Hand Cannoneer recurring clock is
mechanics-derived from its sourced reload and attack delay; its formation and
opening policy came from the authorized Standard Units streams and is now also
checked end-to-end by the two dedicated Hand Cannoneer golden archives.

## Tests

```powershell
python -m pytest tests/test_cleanroom_map_export.py -q -p no:cacheprovider
node --test aoe2x/js_simulation/tests
```

The map fixture is read-only. Viewer controls affect only presentation.

## Formation fixture

`fixtures/golden_formation_27v27.json` contains the exact first 27 Player 2
records and first 27 Player 3 records in source order:

- Player 2: Militia placeholders, unit constant 74.
- Player 3: Woad Raider placeholders, unit constant 232.

All coordinates and rotations are copied from the source scenario. The initial
54 positions have no Gaia-cell, forest-terrain, or duplicate-cell conflicts.
Markers in the viewer communicate placement and facing only; their drawn size
is not a calibrated collision radius.

## View orientation and centre

The viewer rotates the scenario coordinate plane 90 degrees counterclockwise
around the geometric map centre `(8, 8)`. This is a presentation transform;
terrain and object coordinates in `golden_map.json` remain unchanged. Render
depth and pointer picking use the same forward/inverse transform.

For the 16-by-16 source map, tile boundaries span `0..16`, so `(8, 8)` is the
exact centre. Camera rotation does not recenter, transpose, or otherwise alter
the source-authored terrain, trees, or unit slots.
