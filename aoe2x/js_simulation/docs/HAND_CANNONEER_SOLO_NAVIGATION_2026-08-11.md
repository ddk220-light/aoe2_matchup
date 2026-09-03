# Hand Cannoneer solo navigation lab — 2026-08-11

## Outcome

The local JavaScript viewer now has a dedicated movement lab for exactly 21
owner-2 ranged units with no enemy roster. The picker switches among Bohemian
Hand Cannoneer, Chinese Arbalester, Saracen Heavy Cavalry Archer, Japanese
Heavy Scorpion, and Chinese Elite Skirmisher. Every run uses the selected
unit's clean-room mechanics and allows three movement implementations to be
viewed side by side:

1. `baseline` — the original translated per-unit move orders;
2. `per-unit-grid` — each unit independently routes its move order over the
   obstruction grid;
3. `cohesive` — one persistent, obstacle-aware formation anchor with stable
   compact slots. This is the default and recommended implementation.

The cohesive implementation completes the 60-second inspection loop without
entering any static Arena obstruction. Its startup now holds the recorded
spawn through the opening window, forms at the first actual AI move order, and
only then advances the shared kiting route. It no longer compacts at a hidden
pre-order staging point.

This is deliberately an enemy-free navigation harness. No combat result,
target acquisition, volley, or matchup calibration is changed by selecting a
viewer navigation variant.

## Mechanics-derived kiting timing

The recurring kiting schedule is derived automatically from unit mechanics,
not loaded from a per-unit timing table. Reload time is rounded upward to the
shared 40-tick AI decision grid. Attack delay identifies the first safe
movement-command slot after projectile release, and later movement phases
repeat every 80 ticks before the next attack cycle.

Movement speed does not alter firing cadence. It determines how far a unit can
actually travel during the derived reload window. Range, minimum range, enemy
position, and relative speed decide whether combat should move or shoot; those
conditions are deliberately absent from this enemy-free navigation loop.

The existing tape profiles remain regression oracles. The general rule
reproduces every accepted recurring profile:

| Unit | Reload | Attack delay | Derived cycle | Accepted cycle | Movement offsets |
|---|---:|---:|---:|---:|---:|
| Arbalester | 1.70 s | 0.342 s | 120 ticks | 120 | 40 |
| Heavy Cavalry Archer | 1.80 s | 0.897 s | 120 ticks | 120 | 80 |
| Elite Skirmisher | 3.00 s | 0.507 s | 200 ticks | 200 | 40, 120 |
| Hand Cannoneer | 3.45 s | 0.350 s | 240 ticks | 240 | 68, 148, 228 after the tick-12 opening |
| Heavy Scorpion | 3.60 s | 0.160 s | 240 ticks | no timing row required | 40, 120, 200 |

Opening and formation choices remain explicit AI policy because mechanics
cannot infer them. HCA's tick-40 opening/top-up and Hand Cannoneer's tick-12
opening plus translated formation are preserved, but neither overrides the
mechanics-derived recurring cycle. A new ranged unit now receives a valid
default timing cycle from its mechanics fixture.

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
applied. The ordinary ranged leash is 0.62 tiles; for larger bodies it derives
upward to one unit diameter so a single displaced siege slot cannot freeze the
whole formation at an obstacle corner.

### First-order formation

The cohesive navigator begins in `awaiting-first-order`. Every destination is
the unit's own spawn, so there is no motion before the kiting AI issues its
first right-click. At that tick, the visible AI order is projected only as far
as necessary onto the body-aware safe envelope; that point becomes the first
formation centre. All 21 stable slots travel there immediately. The anchor
does not advance around the obstacle until the group enters its derived leash.

For Hand Cannoneer and Heavy Scorpion, the mechanics clock issues that first
move at tick 80. In the verified Scorpion run the formation begins moving at
tick 80, changes from forming to routing at tick 613, and its anchor travels
32.37 tiles during the 60-second loop.

### Compact stable slots

The 21 units receive deterministic slots on a compact five-column grid with
0.48-tile spacing. Slot ownership is stable for the whole run. This spacing is
shared by Scorpions: the engine's measured formation-movement rule allows
allied formation bodies to overlap, while full body radius remains mandatory
against map edges and static obstructions. Expanding Scorpion slots to their
full one-tile diameter made the formation wider than the Arena corridor and
was the reason the old viewer appeared not to move.

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
against the Arena's circular static-obstacle geometry, including the Panda
Rock's 1.5-tile radius.

## Saved viewer variants

Use `unit=<slug>` with `hand_cannoneer`, `arbalester`,
`heavy_cav_archer`, `heavy_scorpion`, or `imp_elite_skirm`. Omitting it keeps
the original Hand Cannoneer default. The visible **Ranged unit** selector
updates this parameter while preserving the navigation selection.

Local links:

- Cohesive: <http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&navigation=cohesive>
- Per-unit grid: <http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&navigation=per-unit-grid>
- Baseline: <http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&navigation=baseline>

Example selected-unit links:

- Arbalester: <http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&unit=arbalester&navigation=cohesive>
- Heavy Cavalry Archer: <http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&unit=heavy_cav_archer&navigation=cohesive>
- Heavy Scorpion: <http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&unit=heavy_scorpion&navigation=cohesive>
- Elite Skirmisher: <http://127.0.0.1:5011/?mode=hand-cannoneer-solo-movement&unit=imp_elite_skirm&navigation=cohesive>

Tailnet links:

- Cohesive: <https://dragonstar.tail82a190.ts.net/golden-map/?mode=hand-cannoneer-solo-movement&navigation=cohesive>
- Per-unit grid: <https://dragonstar.tail82a190.ts.net/golden-map/?mode=hand-cannoneer-solo-movement&navigation=per-unit-grid>
- Baseline: <https://dragonstar.tail82a190.ts.net/golden-map/?mode=hand-cannoneer-solo-movement&navigation=baseline>

Selected-unit Tailnet example:

<https://dragonstar.tail82a190.ts.net/golden-map/?mode=hand-cannoneer-solo-movement&unit=heavy_scorpion&navigation=cohesive>

The Tailnet route is private and requires the viewing device to be connected to
the same tailnet. Viewer handoffs should always include a verified Tailnet URL
as well as localhost.

The endpoint backing these links is:

```text
GET /api/solo-hand-cannoneers?unit=<slug>&navigation=<variant>
```

Omitting `unit` selects `hand_cannoneer`; omitting `navigation` selects
`cohesive`. Unknown or melee units, unknown variants, duplicate values, and
additional parameters return HTTP 400.

## Viewer diagnostics

The map overlay can be enabled or disabled with **Navigation debug**. It draws:

- the current tape-derived AI waypoint;
- the persistent formation anchor;
- the active route waypoint;
- the live group centroid;
- all 21 effective unit destinations;
- a line from each unit to its assigned destination.
- the first-formation target selected from the first AI move order.

The live statistics panel reports:

- the current movement phase: holding, forming at first order, or group route;
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
unit/snapshot/obstacle penetrations under the collision solver's circular
static-obstacle geometry; it is a diagnostic incidence count, not a count of
unique units.
The cohesion columns use snapshots from tick 900 onward so the deliberately
wide recorded starting formation does not masquerade as steady-state spread.

| Variant | Mean cohesion radius after regroup | Maximum after regroup | Compact snapshots (≤2.25) | Obstacle overlaps | Minimum obstacle clearance | Longest stationary run | Anchor travel | Replans |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline` | 5.602 | 6.979 | 0% | 0 | 0.000 tiles | 5.05 s | 0 | 0 |
| `per-unit-grid` | 4.671 | 5.062 | 0% | 0 | +0.000 tiles | 49.85 s | 0 | 0 |
| `cohesive` | **1.104** | **1.220** | **100%** | **0** | **+0.000 tiles** | **5.95 s** | **57.942 tiles** | **0** |

Deterministic final-state hashes for this comparison:

- `baseline`: `1c9d9fbb67e083b346ea78fff41442d70e7ba4369ec6f57b962986188aa230c7`
- `per-unit-grid`: `4c850597a2e6695fdc955d98d110250d713c4f624c66e0d6a94697e9a87ab622`
- `cohesive`: `5ff40e13897f9d65a53d9aa2a051dcb36d6315a91cdf0330e9ba5e07a0ecbe53`

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
passes its seven selected tests, including the Hand Cannoneer and Heavy
Scorpion obstacle-clearance checks, and skips ten tests outside its name
filter. The catalogue export passes 2/2 tests. The full JavaScript suite in the
broader current checkout reports 251/281 passing and 30 failures. Those
failures are in the broader checkout's Champion outcome/comparison,
target-state, and world-tick expectations (for example the Champion 2v3 winner
expectation and the unsupported Champion playback guard), not in the
solo-navigation slice. They are recorded here so a focused green suite is not
misrepresented as a globally green checkout.

Browser verification loaded the cohesive Heavy Scorpion page on the local
server, observed the `Group kiting route` phase at tick 1248 with 6.9 tiles of
anchor travel, and found no browser console errors. Both the local endpoint and
Tailnet endpoint returned HTTP 200 for the same Scorpion run.

## Main files

- `src/combat/kite-timing.js` — mechanics-derived recurring timing and the
  small opening/formation policy table.
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
review in an enemy-free ranged-unit harness. Heavy Scorpion now executes its
mechanics-derived movement clock in that harness; its authentic minimum-range
retreat decision still requires an enemy. The saved baseline and per-unit
variants remain available so reviewer feedback can distinguish group motion,
slot behavior, cornering, and obstacle clearance before any decision to
generalize the mechanism into combat matchups.
