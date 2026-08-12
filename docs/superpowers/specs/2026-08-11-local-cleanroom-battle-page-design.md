# Local Clean-Room Battle Page Design

**Date:** 2026-08-11

## Goal

Upgrade the existing local clean-room viewer at `aoe2x/js_simulation/viewer/`
into a working Battle Simulation page that matches the current website's
selection and playback experience while running only the clean-room JavaScript
engine and its generated Golden Arena placements.

This is a local calibration and product-preview surface. It does not replace,
modify, deploy, or route traffic away from the current website simulator.

## Product Decisions

- The existing clean-room viewer is upgraded in place and remains available at
  `http://127.0.0.1:5011/` through `aoe2x/js_simulation/server.mjs`.
- The page mirrors the website's Battle Simulation structure: page header,
  options menu, two civilization-first picker rails, center arena, start and
  playback controls, live team summaries, and damage diagnostics.
- The center arena uses the existing isometric Golden Arena and circle-based
  unit renderer. Production sprites are not required for simulated bodies.
- All website civilizations and Imperial unit choices remain visible. Only the
  exact civilization/unit combinations present in `UNIT_REGISTRY` are enabled.
- Unsupported units remain visible, are labelled `Not yet calibrated`, and
  cannot be selected through the grid, search, URL state, or the HTTP API.
- Engine execution remains deterministic. The page does not introduce a seed,
  random acquisition order, or cosmetic simulation variation.

## Architecture

The page has four boundaries:

1. **Reference catalogue**: a deterministic, display-only JSON export from
   `data/golden/aoe2_reference.db`. It contains the Imperial civilization/unit
   rows required to reproduce the website picker. It is not mechanics input.
2. **Availability manifest**: `/api/units`, sourced from `UNIT_REGISTRY`, is the
   sole authority for which exact civilization/unit combinations can run.
3. **Battle adapter**: browser state maps Team 1/Team 2 selections and options
   to the existing `/api/fight` contract. Engine-side validation remains final.
4. **Playback**: the existing map renderer consumes the returned snapshots,
   unit index, events, winner, and deterministic hashes.

The local Node server serves only an explicit allowlist of shared website CSS,
images, and frontend constants. It does not expose or import the old website
simulation engine or `simulate.js`. Viewer-specific CSS layers disabled-state
and isometric-arena rules over the shared presentation.

## Catalogue and Availability

A new exporter reads the committed reference database with Python's standard
`sqlite3` library and writes a stable JSON fixture under
`aoe2x/js_simulation/fixtures/`. The JSON records source filename, SHA-256, and
ordered civilization/unit data.

Enabled entries are joined explicitly by `(civ, display name)` to an engine
slug. The join must resolve exactly once for every `UNIT_REGISTRY` row; missing
or ambiguous matches fail tests and regeneration. The HTTP server returns both
the full display catalogue and availability metadata, but `/api/fight` accepts
only engine slugs from the registry.

All civilization cards are browsable, including civilizations with no enabled
unit. Inside a civilization, units retain the website's building-group layout.
Disabled unit cards use a visible lock/status treatment and have no selectable
action. Search returns the same catalogue and uses the same disabled treatment.

## Battle Options

### Equal Numbers

The user supplies both army counts. Inputs are validated against the actual
per-side placement capacity of the selected matchup family. No silent spawn
overlap or count truncation is allowed. When a newly selected pairing lowers a
capacity, the UI moves the count to the largest legal value and explains the
limit beside the input.

### Equal Resources

The default budget is 3,000 and is editable. The server derives counts from the
clean-room purchase rule using `Food + Wood + 1.5 * Gold`, the 21-unit purchase
cap, and the selected matchup's placement capacities. The response is the
source of truth for the displayed counts.

The website's `5,000 incl. Upgrades` option remains visible but disabled with a
`Not calibrated` explanation. The clean-room registry does not carry an
authorized upgrade-cost purchase model.

## Interaction and Playback

The pick phase matches the website:

- civilization grid -> civilization badge -> unit grid -> unit badge;
- rail search can jump to a civilization or exact unit;
- Start is enabled only after both sides have supported selections;
- starting a battle collapses selection content into live team summaries;
- Pause/Resume, New Battle, speed, and timer controls use the existing snapshot
  playback cursor without changing engine state;
- New Battle returns to the picker; Reset Playback replays the exact result.

The center map retains pan, zoom, top-down, grid, object, footprint, and label
controls. Unit circles show owner color, HP, facing, range/body overlays, and
target/attack relationships.

## Diagnostics

The normal battle page remains the primary surface. Existing laboratory tools
move into a collapsible `Calibration tools` section beneath it:

- winner and remaining HP;
- final-state and event-log hashes;
- per-unit telemetry and event timeline;
- local flag and review note;
- downloadable review JSON with selected units, counts, mode, budget, result,
  hashes, and note.

The damage-breakdown button presents event-derived hit, damage, kill, and
survivor totals. It must not display the old engine's formula calculations.

## Errors and Safety

- Rejected fights keep the last valid playback and picker usable.
- Unsupported URL selections render as unavailable and never start a fight.
- Counts and budgets receive clear inline validation.
- Raw archives, extracted tapes, mechanics fixtures, and calibration reports
  remain inaccessible from the local HTTP server.
- No production route, template, JavaScript engine, database, or deployment
  configuration is modified.

## Verification

- Exporter tests prove deterministic catalogue output and exact registry joins.
- Server tests cover the catalogue endpoint, asset allowlist, unsupported
  requests, configurable resource budgets, and calibration-source denial.
- Browser-state unit tests cover availability, picker transitions, search,
  option validation, and request construction.
- Existing server/viewer integration tests cover map playback and review export.
- Visual verification covers desktop and mobile layouts against the current
  website treatment.
- Focused engine invariance tests verify that adding the page and budget input
  does not change the default 3,000-resource result or hashes.
