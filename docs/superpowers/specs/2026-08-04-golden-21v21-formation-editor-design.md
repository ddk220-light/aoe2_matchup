# Golden 21v21 Formation Editor Design

Date: 2026-08-04

## Objective

Extend the clean-room Stage 0 map viewer into a Stage 1 placement editor that
shows the exact 21-versus-21 infantry formations produced by the current golden
scenario workflow. The editor lets the user correct placement visually and
download both a machine-readable layout and a corrected AoE2 scenario.

This stage contains no clock, movement, targeting, collision physics, attacks,
damage, or combat resolution.

## Source authority

The immutable source scenario is:

`aoe2x/js_simulation/fixtures/source/golden_infvsinf.aoe2scenario`

Required SHA-256:

`a8d11848399a56a13cbf05b4812e5e95939f790b768285c67600c4e24c651113`

The source template stores 36 Player 2 Elite Jaguar Warriors (unit constant
726) and 40 Player 3 Militia (unit constant 74). The current golden builder
creates a 21-versus-21 scenario by retaining the first 21 units returned for
each player and removing the surplus. Stage 1 must reproduce that behavior,
not invent or geometrically generate a formation.

Retained source reference IDs:

- Player 2: 1628 through 1648 inclusive.
- Player 3: 1699 through 1719 inclusive.

The initial coordinates and rotations come directly from these 42 source
records. The checked-in source binary and derived golden map fixture remain
read-only.

## Editor interaction

The existing 90-degree-counterclockwise presentation transform remains in
place. It affects only rendering and pointer conversion; exported coordinates
remain in the original scenario coordinate plane.

Each retained unit is shown as a team-colored placement marker with a facing
indicator derived from its scenario rotation. The marker is explicitly a
placement control, not a calibrated collision radius.

The user can:

- Select and drag one unit at a time.
- Snap a dragged unit to the center of a map tile (`n + 0.5`).
- Nudge all units on one side by one tile in the four cardinal directions. A
  side nudge is atomic and is rejected entirely if any destination is invalid.
- Undo and redo placement changes.
- Reset the full layout to the golden source positions.
- Inspect player, source reference ID, unit constant/name, original position,
  current position, and rotation for the selected unit.
- Toggle unit identifiers and obstruction cells for diagnosis.

The status area always displays the current unit counts and whether the layout
is exportable. Invalid drag targets are drawn in red and are not committed on
drop.

## Placement validation

One shared, deterministic validator is used by the browser model and mirrored
independently by the server export boundary. A layout is valid only when:

1. It contains exactly 21 Player 2 units and 21 Player 3 units.
2. Every retained source reference ID appears exactly once.
3. Every coordinate is finite and at a tile center.
4. Every coordinate lies within the 16-by-16 map.
5. No unit occupies a forest-terrain cell. The source forest terrain IDs are
   10, 56, and 128.
6. No unit occupies the cell of any Gaia object, including trees, bushes, and
   the Panda Rock.
7. No two retained units occupy the same tile cell.
8. The request identifies the required source scenario SHA-256.

The unedited first-21 formations satisfy every rule: they contain no Gaia-cell,
forest-terrain, or duplicate-cell conflicts.

These are placement-editor constraints, not claims about the live game's
continuous collision system. Finer sub-tile positioning and unit-radius
collision belong to later mechanics stages.

## JSON export

The browser downloads:

`golden_infvsinf_21v21_layout.json`

The JSON contains:

- Schema version and export timestamp.
- Source filename and SHA-256.
- Map size and view-orientation metadata.
- Validation result and conflict list.
- Both sides' unit records with reference ID, player ID, unit constant/name,
  rotation, original coordinates, and edited coordinates.

JSON generation is client-side after a final local validation. The download
uses a Blob URL and revokes it after initiating the download.

## AoE2 scenario export

The browser posts the same layout document to a same-origin export endpoint.
The server:

1. Enforces a small request-size limit and parses JSON.
2. Verifies the source hash and all placement invariants independently.
3. Creates a unique temporary directory.
4. Invokes a fixed Python exporter command without a shell and without placing
   user-controlled values in command-line syntax.
5. Loads the immutable golden scenario with AoE2ScenarioParser.
6. Matches retained units by player and reference ID.
7. Removes all surplus Player 2 and Player 3 army units.
8. Changes only the retained units' `x` and `y` coordinates.
9. Writes and reads back the output scenario.
10. Revalidates map dimensions, terrain, Gaia objects, retained units, AI data,
    triggers, player configuration, and source-preserved rotations.
11. Returns the binary as
    `golden_infvsinf_21v21_edited.aoe2scenario` with attachment headers.
12. Removes the temporary directory in success and error paths.

No endpoint accepts a filesystem path, executable name, scenario filename, or
arbitrary unit constant from the browser.

## Error handling

Client validation failures disable both export buttons and list each conflicting
unit and cell. Server validation failures return structured JSON with a stable
error code and human-readable details; the editor displays them without losing
the current layout. Parser or round-trip failures return no partial scenario.

The original source scenario is never overwritten. Export artifacts are sent
to the browser only and are not added to the repository automatically.

## Component boundaries

- `tools/export_golden_formation.py`: extracts the exact retained formation and
  produces the derived placement fixture.
- `fixtures/golden_formation_21v21.json`: immutable derived positions and unit
  provenance used by the viewer.
- `src/formation-model.js`: pure selection, movement, snapping, validation,
  undo/redo, and export-document logic.
- `viewer/map-renderer.js`: presentation and pointer mapping only.
- `viewer/app.js`: controls, inspection, downloads, and server error display.
- `tools/write_edited_scenario.py`: fixed, validated scenario rewrite and
  read-back verification.
- `server.mjs`: narrow fixture and scenario-export HTTP routes.

## Verification strategy

Python tests verify exact extraction of the first 21 reference IDs per side,
the source hash, initial conflict freedom, surplus removal, coordinate-only
editing, and scenario read-back preservation.

JavaScript tests verify snapping, bounds, forest/Gaia/duplicate conflicts,
side nudging as an atomic operation, undo/redo, reset, forward/inverse rotated
pointer mapping, JSON shape, request limits, invalid-export rejection, and
download response headers.

Browser verification covers desktop and phone layouts, individual dragging,
invalid-drop rejection, undo/reset, retained coordinate inspection, both
downloads, and a clean console on the Tailnet URL with and without its trailing
slash.

## Acceptance criteria

- The initial view contains the exact retained 21 Player 2 and 21 Player 3
  source units at their source positions and rotations.
- The initial layout reports zero placement conflicts.
- Invalid moves cannot be committed or exported.
- Valid corrections survive JSON export and scenario round-trip.
- The scenario export contains exactly the edited 42 army units and preserves
  all non-placement source structures checked above.
- The existing Stage 0 map provenance and source fixtures remain unchanged.
- No simulation mechanics are introduced.
