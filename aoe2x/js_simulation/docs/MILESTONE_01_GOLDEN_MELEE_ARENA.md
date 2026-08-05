# Milestone 01: Golden melee arena locked

**Status:** achieved and locked on 2026-08-04

This milestone establishes the literal map and starting formation used by the
clean-room JavaScript simulator for all melee-versus-melee fights. It replaces
the older generic infantry scenario as the canonical engagement geometry.

## Canonical source

- Scenario: `fixtures/source/golden_meleevsmelee.aoe2scenario`
- Repository source:
  `origin/staging:apps/video/templates/golden_meleevsmelee.aoe2scenario`
- Source commit: `9b9e5374322ce0da2d14dd4ad61e1d4cdb1bf0bc`
- SHA-256:
  `f10508cbe6ec6211d611c35d411ad7e40b38c96b6ef0d6b0d651daa42df645a4`
- Scenario version: `1.58`
- Parser: AoE2ScenarioParser `0.8.2`

The binary hash is an invariant. Replacing this scenario must be an explicit
new milestone with updated fixtures, measurements, tests, and provenance.

## What was locked

- Literal 16 × 16 terrain: 256 source tiles, with no inferred geometry.
- Literal Gaia layer: 101 source objects.
- Center Panda Rock: unchanged at `(9.0, 7.0)`.
- Player 2 formation: 21 exact source positions.
- Player 3 formation: 21 exact source positions.
- Placement validation: 42 occupied source positions, zero blocked or
  duplicate cells.
- Viewer orientation: the approved 90-degree counterclockwise presentation.

The staging scenario and the previous map fixture have identical parsed
terrain and Gaia layers. The only meaningful change is the combat formation.

## Engagement win

The new dedicated melee formation matches the in-game visual engagement far
more closely:

| Measurement | Previous generic infantry fixture | Locked melee fixture |
| --- | ---: | ---: |
| Formation centroid gap | 8.56 tiles | **4.32 tiles** |
| Nearest opposing pair | 3.00 tiles | **2.00 tiles** |

This removes the visibly excessive opening separation without inventing a
placement algorithm or tuning coordinates by hand. Every position comes from
the committed golden scenario.

## Canonical-use rule

All clean-room melee-versus-melee simulations must initialize from
`fixtures/golden_formation_21v21.json`, which is regenerated from the locked
scenario binary. Unit types may be substituted for a matchup, but the initial
21-versus-21 coordinates, map tiles, Gaia objects, and view transform must not
be retuned per unit or matchup.

Do not use `golden_infvsinf.aoe2scenario` as the placement source for new
melee-versus-melee work. Do not hand-edit the derived JSON fixtures. Regenerate
them with the checked-in exporters and require the source hash to match.

## Evidence at lock time

- Python fixture/export tests: 7 passed.
- JavaScript model, renderer, and server tests: 16 passed.
- Tailnet viewer: loaded the canonical filename and hash successfully.
- Browser console: zero errors.
- Visual review: approved as matching the in-game map and starting positions.

## Next mechanics milestone

The next phase starts from this frozen geometry and adds only the minimum
mechanics needed to reproduce a one-versus-one same-unit melee engagement.
Movement, targeting, collision, attack timing, retargeting, and group behavior
must be introduced and validated incrementally without changing this map or
formation baseline.
