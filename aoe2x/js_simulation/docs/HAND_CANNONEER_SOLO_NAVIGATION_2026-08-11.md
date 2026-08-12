# Hand Cannoneer solo navigation lab — 2026-08-11

## Outcome

The local JavaScript viewer now has a dedicated movement lab for exactly 21
Bohemian Hand Cannoneers running as engine owner 2 with no enemy roster. The
lab keeps the tape-derived Hand Cannoneer AI-order cadence, but allows three
movement implementations to be viewed side by side:

1. `baseline` — the original translated per-unit move orders;
2. `per-unit-grid` — each unit independently routes its move order over the
   obstruction grid;
3. `cohesive` — one persistent, obstacle-aware formation anchor with stable
   compact slots. This is the default and recommended implementation.

The cohesive implementation completes the 60-second inspection loop without
entering any static Arena obstruction. After its opening regroup, all 21 units
remain in a roughly 1.07-tile-radius ball while the anchor travels 61.79 tiles.

This is deliberately an enemy-free navigation harness. No combat result,
target acquisition, volley, or matchup calibration is changed by selecting a
viewer navigation variant.

## Original failure

The previous Hand Cannoneer movement loop retained the tape-derived clockwise
waypoint orders, but executed each unit's translated destination directly.
That produced three visible defects:

- the initial wide formation stayed wide because every lagging unit inherited
  the same translation;
- units independently selected paths and accumulated on obstacle corners;
- collision stopped overlap at the final solver stage, but there was no
  persistent group route to lead the formation around the central object.

The independent grid-path experiment improved individual obstacle awareness,
but it still had no group-level intent. Units could choose incompatible sides
of the obstruction, stretch the formation, and remain at an unreachable
best-effort approach for most of the loop.

## Cohesive navigation design

The implementation lives in `src/combat/solo-navigation.js` and is activated
only when `scenario.soloMovement === true`.

### Formation anchor

The group has one virtual anchor. It moves at the Hand Cannoneer's ordinary DAT
speed; no speed bonus, teleport, random variation, or result-fitting factor is
applied. The anchor pauses whenever the largest unit-to-slot error exceeds
0.62 tiles, allowing lagging units to catch up at their own normal speed.

### Compact stable slots

The 21 units receive deterministic slots on a compact five-column grid with
0.48-tile spacing. Slot ownership is stable for the whole run. Units may
compress visually at a corner, but they do not continually exchange positions
or cross through the formation to chase a newly assigned slot.

### Formation-inflated central obstruction

The central Arena objects are treated as one compact obstruction envelope for
the group route. The envelope expands the objects by the formation clearance
radius (1.18 tiles plus a 0.07-tile planning margin). Consequently, the anchor
cannot select a route that clears the rock for one unit but drags an outside
slot through it.

The route follows a persistent clockwise perimeter. The current tape-derived
AI waypoint is projected onto that expanded perimeter, and a 0.75-tile
lookahead becomes the anchor's active route waypoint. The projected route never
regresses around the ring when a newer AI order arrives.

### No-progress recovery

If the anchor has not moved for 1.25 seconds, the planner deterministically
reprojects it to the next clockwise perimeter point and increments the replan
counter. The exact verified run needed three such replans. This state and every
destination are published as diagnostics; they do not alter combat hashes
outside the solo harness.

### Final collision authority

The normal world movement and collision solver remains authoritative. The
navigation layer supplies aims; it does not directly mutate final positions.
The verification test independently checks every unit on every snapshot
against the Arena's Chebyshev obstruction geometry, including the Panda Rock's
1.5-tile radius.

## Saved viewer variants

Local links:

- Cohesive: <http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&navigation=cohesive>
- Per-unit grid: <http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&navigation=per-unit-grid>
- Baseline: <http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&navigation=baseline>

Tailnet links:

- Cohesive: <https://dragonstar.tail82a190.ts.net/golden-map/?mode=hand-cannoneer-solo-movement&navigation=cohesive>
- Per-unit grid: <https://dragonstar.tail82a190.ts.net/golden-map/?mode=hand-cannoneer-solo-movement&navigation=per-unit-grid>
- Baseline: <https://dragonstar.tail82a190.ts.net/golden-map/?mode=hand-cannoneer-solo-movement&navigation=baseline>

The Tailnet route is private and requires the viewing device to be connected to
the same tailnet. Viewer handoffs should always include a verified Tailnet URL
as well as localhost.

The endpoint backing these links is:

```text
GET /api/solo-hand-cannoneers?navigation=<variant>
```

Omitting `navigation` selects `cohesive`. Unknown variants or additional
parameters return HTTP 400.

## Viewer diagnostics

The map overlay can be enabled or disabled with **Navigation debug**. It draws:

- the current tape-derived AI waypoint;
- the persistent formation anchor;
- the active route waypoint;
- the live group centroid;
- all 21 effective unit destinations;
- a line from each unit to its assigned destination.

The live statistics panel reports:

- cohesion radius;
- maximum slot error;
- units blocked on the current tick;
- deterministic route replans;
- cumulative anchor travel;
- current anchor-stall duration.

The navigation selector reloads the same page with a stable deep link, making
visual comparisons repeatable and easy to share on desktop or mobile.

## Exact 60-second comparison

All rows use the same 21 units, starting formation, Arena map, AI order clock,
and 3,601 snapshots (tick 0 through tick 3,600). `Obstacle overlaps` counts
unit/snapshot/obstacle penetrations under the collision solver's Chebyshev
geometry; it is a diagnostic incidence count, not a count of unique units.
The cohesion columns use snapshots from tick 900 onward so the deliberately
wide recorded starting formation does not masquerade as steady-state spread.

| Variant | Mean cohesion radius after regroup | Maximum after regroup | Compact snapshots (≤2.25) | Obstacle overlaps | Minimum obstacle clearance | Longest stationary run | Anchor travel | Replans |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline` | 5.602 | 6.979 | 0% | 35,801 | -0.498 tiles | 5.05 s | 0 | 0 |
| `per-unit-grid` | 4.671 | 5.062 | 0% | 8,600 | -0.212 tiles | 49.85 s | 0 | 0 |
| `cohesive` | **1.073** | **1.073** | **100%** | **0** | **+0.046 tiles** | **3.58 s** | **61.787 tiles** | **3** |

Deterministic final-state hashes for this comparison:

- `baseline`: `1c9d9fbb67e083b346ea78fff41442d70e7ba4369ec6f57b962986188aa230c7`
- `per-unit-grid`: `4c850597a2e6695fdc955d98d110250d713c4f624c66e0d6a94697e9a87ab622`
- `cohesive`: `f659c8af83290134a7e44c3f10c5c3bf255bc0f1e602924a956fa09babfb634a`

## Verification

Focused syntax validation:

```powershell
node --check src/combat/solo-navigation.js
node --check src/combat/world.js
node --check src/fight.js
node --check viewer/battle-state.js
node --check viewer/app.js
node --check viewer/map-renderer.js
node --check server.mjs
```

Focused automated suite:

```powershell
node --test `
  tests/battle-state.test.mjs `
  tests/map-renderer.test.mjs `
  tests/kite-orders.test.mjs `
  tests/chase-path.test.mjs

node --test `
  --test-name-pattern "solo movement endpoint|cohesive solo navigation|viewer page exposes|phone layout" `
  tests/server.test.mjs

python -m pytest ../../tests/test_viewer_catalogue_export.py -q -p no:cacheprovider
```

The first JavaScript command passes 25/25 tests. The focused server command
passes its five selected tests, including the exact obstacle-clearance check,
and skips ten tests outside its name filter. The catalogue export passes 2/2
tests. The full JavaScript suite in the broader current checkout reports
245/275 passing and 30 failures. Those failures are in the broader checkout's
Champion outcome/comparison, target-state, and world-tick expectations (for
example the Champion 2v3 winner expectation and the unsupported Champion
playback guard), not in the solo-navigation slice. They are recorded here so a
focused green suite is not misrepresented as a globally green checkout.

Browser verification loaded the cohesive Tailnet-equivalent page on the local
server, observed live cohesion `1.07 tiles`, slot error `0.00 tiles`, blocked
count `0`, and replan count `3`, with no browser console errors.

## Main files

- `src/combat/solo-navigation.js` — variants, formation route, slots, pacing,
  replanning, and diagnostics.
- `src/combat/world.js` — solo-only navigation hook and snapshot publication.
- `src/fight.js` — fixed 21-unit run, variant validation, summaries, and wire
  snapshots.
- `server.mjs` — strict movement endpoint.
- `viewer/battle-state.js` — stable deep-link parsing.
- `viewer/app.js` — selector, stats, and diagnostic snapshot plumbing.
- `viewer/map-renderer.js` — route, anchor, centroid, and slot overlays.
- `tests/server.test.mjs` — endpoint, cohesion, and exact obstacle-clearance
  regression coverage.

## Non-goals and next review

This work does not claim that the cohesive route is a tape-derived replacement
for all kiting formations. It is the physics/navigation candidate for visual
review in this exact enemy-free Hand Cannoneer harness. The saved baseline and
per-unit variants remain available so reviewer feedback can distinguish group
motion, slot behavior, cornering, and obstacle clearance before any decision
to generalize the mechanism into combat matchups.
