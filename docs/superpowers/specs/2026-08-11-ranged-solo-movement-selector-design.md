# Ranged Solo Movement Selector Design

**Date:** 2026-08-11

## Goal

Extend the existing enemy-free 21-unit movement lab so the viewer can switch
between Hand Cannoneer, Arbalester, Heavy Cavalry Archer, Heavy Scorpion, and
Elite Skirmisher without leaving the page. The lab remains a navigation and
kiting-order inspection surface; it does not change combat matchup outcomes.

## Product Contract

- The existing `mode=hand-cannoneer-solo-movement` link remains valid and
  defaults to the Bohemian Hand Cannoneer.
- A `unit=<engine slug>` query parameter selects one of:
  `hand_cannoneer`, `arbalester`, `heavy_cav_archer`, `heavy_scorpion`, or
  `imp_elite_skirm`.
- The page displays a ranged-unit selector next to the saved navigation
  selector. Changing either selector reloads a stable, shareable deep link.
- Every run contains exactly 21 owner-2 units, no enemy roster, the existing
  Golden Arena map, and the selected `baseline`, `per-unit-grid`, or
  `cohesive` navigation implementation.
- Labels, civilization, HP, speed, collision size, range, and renderer master
  ID come from the selected clean-room registry/mechanics fixture.
- Unknown, melee, or otherwise unsupported unit slugs receive HTTP 400.

## Engine Design

The hard-coded Hand Cannoneer runner becomes a generic solo-ranged runner. It
uses the same 21 kite-family spawn cells for every selected unit so visual
comparisons begin from identical positions.

The engine derives each ranged unit's recurring firing/movement cycle from its
mechanics fixture. Reload time is rounded upward to the shared 40-tick AI
decision grid; attack delay determines the first safe movement phase after a
shot; the shared 80-tick movement-order interval supplies any later movement
phases before the next attack cycle. Movement speed does not alter attack
cadence: it determines how much distance the unit can actually cover during
the derived reload window.

The existing tape-derived `KITE_PROFILES` values remain regression oracles,
not runtime timing inputs. The mechanics rule must reproduce the currently
accepted recurring values for Arbalester, Heavy Cavalry Archer, Hand
Cannoneer, and Elite Skirmisher. A newly registered ranged unit therefore gets
a valid recurring timing profile without adding a calibrated timing row.

Opening behavior and formation behavior remain explicit AI policy. They are
not unit mechanics: for example, an HCA's opening fire/top-up sequence and a
Hand Cannoneer's translated formation cannot be inferred from reload or
movement speed. Those policies may choose the initial attack phase or
formation style, but may not override the mechanics-derived recurring reload
cycle.

Heavy Scorpion uses the same mechanics derivation: its 3.6-second reload and
0.16-second attack delay produce its recurring shoot/move opportunity window
without a Scorpion-only timer. In combat its decision to retreat still depends
on an enemy entering minimum range. The enemy-free viewer exercises its real
speed, 0.5-tile collision radius, and obstacle routing, so the UI identifies
that run as a navigation loop rather than evidence of combat retreat triggers.

The cohesive planner uses the engine's shared 0.48-tile formation lattice for
every unit because two allied formation movers are allowed to compress through
one another. Static-obstacle envelope clearance and the elastic group leash do
derive from real collision radius. This keeps Heavy Scorpion's larger body
outside obstructions without creating a five-tile-wide square that cannot fit
through the Arena corridor. Final world collision remains authoritative.

The cohesive startup has no invented staging point. Units hold their recorded
spawn until the first actual mechanics-clock move order, then travel to stable
slots centered on the nearest body-safe projection of that visible AI order.
The shared route anchor advances only after the formation reaches that first
destination.

## HTTP and Browser State

`GET /api/solo-hand-cannoneers` remains the endpoint for backward compatibility
and accepts only `unit` and `navigation`. Omitting `unit` selects
`hand_cannoneer`; omitting `navigation` selects `cohesive`.

The `/api/units` response exposes the ordered solo-movement slug allowlist so
the viewer builds the picker from the same registry rows that the server uses.
The browser parser accepts the legacy URL, validates supported slugs and
navigation variants, and creates a canonical query containing both fields.

## Verification

- Browser-state tests cover the legacy default, all five unit deep links,
  navigation variants, and rejection of extra/unsupported parameters.
- Server tests prove each selectable slug produces 21 owner-2 instances of
  the selected mechanics row and that unknown or melee slugs are rejected.
- Cohesive regression tests check all five units remain outside every Arena
  obstruction using each unit's actual collision radius.
- Viewer-shell tests cover the ranged-unit selector and query-preserving
  navigation/unit changes.
- Manual desktop and mobile verification uses the Tailnet deep link and checks
  that unit changes update the title, rail, map bodies, and URL.

## Non-Goals

- No enemies, attacks, damage, target acquisition, or matchup result changes.
- No new tape-derived timing profile is required for a selectable ranged unit.
- No production deployment or production route change.
