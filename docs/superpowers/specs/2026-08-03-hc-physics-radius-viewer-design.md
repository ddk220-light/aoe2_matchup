# HC physics-radius viewer design

## Goal

Make the calibration-only HC Field Lab display each unit at its actual simulation
collision radius so the visible packing can be compared directly with AoE2
behavior. Keep production simulation and rendering code unchanged.

## Visualization

- The HC viewer will draw a filled team-colored disc centered on each living or
  dead unit using `unit.radius` exactly.
- The boundary stroke will be drawn inside the disc so no decorative pixels
  extend beyond the represented collision body.
- HP bars will remain readable but will not be presented as unit geometry.
- A labeled one-tile ruler will be drawn on the battlefield. One tile is the
  engine's `TILE_SIZE`, currently 30 logical canvas pixels.
- Target-line overlays and all simulation behavior remain unchanged.
- The physics view is the only view in this diagnostic viewer; there is no
  visual-radius toggle or enlarged sprite layer.

## Isolation and data flow

The shared production `SimRenderer` remains untouched. The viewer will load a
calibration-specific renderer module that follows the same public renderer
interface (`render`, `setLabels`, canvas context and render scales) but overrides
unit presentation with physics-scale discs. Base, Recovery, H1, H2, and H3 will
all use the same diagnostic renderer, ensuring visual differences come only from
their engine mechanics.

The viewer continues to build scenarios exclusively from fixtures derived from
`calibration/source/aoe2_golden_STANDARD_UNITS_FINAL.zip` with locked SHA-256
`31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9`.

## Tests and verification

- Add a failing viewer test that requires the calibration-specific physics
  renderer and verifies that its unit-disc geometry reads `unit.radius`, not
  `unit.drawRadius`.
- Verify that the test fails before implementation and passes afterward.
- Run all HC viewer tests, JavaScript syntax checks, and the variant smoke run.
- Fetch the local and Tailnet pages and confirm that the new renderer is served.
- Inspect the live viewer at the HC-versus-Paladin H1 scenario and confirm the
  one-tile ruler and physics-scale bodies are visible.

## Collision research follow-up

After the viewer change, inspect the installed Genie `.dat` extraction path and
technical references for per-unit collision, overlap/minimum-size multiplier,
obstruction, formation, patrol, and activity-dependent behavior. Validate any
mechanical interpretation against only the locked FINAL tape trajectories. The
research will distinguish raw data fields from inferred engine behavior and
record confidence and unresolved questions.

