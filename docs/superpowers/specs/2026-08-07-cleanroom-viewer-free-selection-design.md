# Clean-room viewer: free unit and count selection

**Date:** 2026-08-07
**Branch:** `codex/cleanroom-champion-sim`
**Status:** design, awaiting review

## Goal

Let the clean-room lab viewer run any pair of tested units at any army sizes,
picked in the UI, on a spawn layout produced by a single programmatic placement
system. Everything the viewer runs must be reachable by the eventual website
port: no recorded fixture may sit on the path a product request takes.

## Non-goals

Deliberately out of scope for this change:

- Projectile rendering, unit sprites, or any other renderer work.
- Civilization selection.
- Batch/no-record engine mode for the data pipeline.
- Any UX change beyond unit and count selection.
- Closing the ability-coverage gap (8 of 32 abilities modelled today).

## The constraint that shapes the design

The engine is the deliverable. The recorded tapes are how we *check* it, not how
we *run* it. Concretely, this rules out the shortcut of serving a tape's own
spawn roster when the requested matchup happens to match a recording: that would
make `calibration/fixtures/` load-bearing in the product path and leave the
placement problem unsolved behind a special case.

Every fight the viewer runs — including the 25 matchups that have recordings —
gets its positions from the same placement module.

Recorded data keeps exactly one role: **display and regression**. A recording's
winner and HP may be shown next to a result as a reference number, and the old
endpoints stay reachable so we can prove the engine did not drift. Neither ever
supplies a starting position to a fight the viewer runs.

## Findings that the design rests on

Each was measured in this session against committed data.

### Placement is a stable ordered fill

`calibration/fixtures/spawns.json` holds 339 recorded layouts, 678 side-layouts.
Grouping them by (owner, band edge) and testing whether an N-unit layout is
exactly the first N cells of a larger layout in the same family: **60 of 61
nested**. Only 38 of 678 are full rectangles, so the shape is a blob, not a
rectangle — but the fill order is stable.

That means placement is expressible as: *one ordered cell sequence per side,
anchored at a band edge; take the first N.*

### Band edges follow a three-family rule

Cross-referencing spawn bands against matchup category:

| family | side 2 band edge | side 3 band edge |
|---|---|---|
| melee/siege vs melee (`waves`) | 6.5 | 8.5 |
| one mobile-ranged side (`kite`) | 6.5 | 10.5 |
| ranged vs ranged (`rvr`) | 5.5 | 10.5 |

Side 2 fills upward from its edge, side 3 downward from its edge. Ranged fights
start two tiles further apart than melee fights.

### The current synthetic formation does not match the tapes

`syntheticMatchupPlayback` fills side 2 downward from y=6.5 and side 3 upward
from y=8.5 — both sides packed against the middle. The archive uses y 2.5–6.5
versus y 10.5–13.5. Free-form ratios today therefore run on a geometry no
recording used. `placement.js` replaces this outright.

### Exactly four units kite

Across all 32 calibrated kiting matchups the kiting side is always one of
Arbalester, Hand Cannoneer, Heavy Cav Archer, Elite Skirmisher. Siege (Heavy
Scorpion, Siege Onager) never kites; the remaining nine are melee. So
"exactly one mobile-ranged side → that side kites" is a 14-row lookup on unit
class, not a heuristic.

### The purchase rule is exact, from a specific column

`c = food + wood + 1.5 × gold` over `ref_units.base_cost_food/wood/gold`
reproduces every calibrated unit cost **14/14 exactly**.

Using `final_cost_*` instead — the civ-adjusted column, which is what the
website's served combat dict carries — gives **11/14**: Berbers Hussar
(64 vs 80) and Heavy Camel (116 vs 145), Slavs Siege Onager (308.5 vs 362.5).
Civ discounts must not enter the purchase calculation.

Count rule, confirmed against the calibration rows: the cheaper side buys
`min(21, floor(3000 / c))`; the other side buys `floor(cheaperSpend / cOther)`.

### 85% of the playback payload is a repeated blob

Every snapshot unit carries its full mechanics object. Measured on
`champion_vs_paladin` 15v15: total 101.1 MB, of which mechanics is 86.1 MB
(85.2%). Sending mechanics once and dropping fields the viewer never reads
gives 3.27 MB — **31x smaller**. Engine runtime is not the problem (469 ms for
that fight; 2.8 s for 30v30).

### The calibrated configuration is not pinned

The corpus runs under `AOE2X_EXP_ENGAGEMENT=pursuit AOE2X_EXP_ORDERS=1`, read
from `process.env` at module load in `src/combat/experiments.js` and
`src/combat/ai-orders.js`. The README's start command sets neither. Measured
divergence on `champion_vs_paladin` 5v3: 254 HP / 1155 ticks with the flags,
228 HP / 1161 ticks without. Same winner in the four cases checked, different
numbers in all four.

## Components

### `src/placement.js`

```
placeArmy({ owner, count, bandEdge }) -> [{ x, y }, ...]
```

Pure, no I/O, no fixture reads. Produces the first `count` cells of the ordered
sequence for that side, anchored at `bandEdge`.

The ordered sequence itself is derived from `spawns.json` by a one-time analysis
script kept in `tools/`, whose output is committed as a generated constant
inside this module. The archive is never read at runtime.

`resolveBands({ side2Class, side3Class })` returns the `(side2Edge, side3Edge)`
pair using the three-family table above.

### `src/unit-registry.js`

One row per unit with a mechanics fixture (14 today):

| field | source |
|---|---|
| `slug` | matches `ref_units.unit_slug` |
| `label` | display name |
| `civ` | the civ the fixture was exported for |
| `master` | dat unit constant |
| `fixture` | path under `fixtures/unit_stats/` |
| `class` | `melee` \| `mobile_ranged` \| `siege_ranged` |
| `baseCost` | `{ food, wood, gold }` from `ref_units.base_cost_*` |

`class` drives both the kite decision and the band selection. `baseCost` drives
the purchase solver.

Costs are exported from `data/golden/aoe2_reference.db` — the same database the
website serves — by extending `tools/export_unit_mechanics.py` to emit the three
`base_cost_*` values into each mechanics fixture, with the existing provenance
stamp. Regenerating the 14 fixtures must produce an **additive-only** diff (the
three new keys and their provenance entries, nothing else). Any other change
stops the work: it means the reference DB moved under the calibration.

### `src/purchase.js`

```
weightedCost({ food, wood, gold }) -> food + wood + 1.5 * gold
deriveCounts(costA, costB, { budget = 3000, cap = 21 }) -> { countA, countB }
```

Pure. Gated by a test that reproduces the `side2.n` / `side3.n` pairs of all 101
rows in `docs/data/standard_units_2026-08-07.json`.

### `src/fight.js` and the `/api/fight` endpoint

```
GET /api/fight?side2=<slug>&n2=<int>&side3=<slug>&n3=<int>
```

Resolves both units through the registry, picks bands from their classes, calls
`placeArmy` for each side, sets `kiteOwner` when exactly one side is
`mobile_ranged`, runs the engine, returns a slim playback.

`/api/matchup/*` and `/api/champion/*` are left untouched so nothing that works
today can regress, but **the viewer stops calling them**. They become
regression-test surface only (verification gate 5).

`/api/fight` never reads a tape roster. When the requested pair has a recording,
it attaches that recording's winner and HP as `tapeReference` — numbers for the
ledger to display, computed from `calibration/fixtures/` at response time and
having no effect on the run. When there is no recording the field is null and
the ledger shows dashes, as it already does for synthetic ratios today.

### Slim playback format

Per-tick unit records carry only what the viewer reads:
`[referenceId, owner, x, y, hp, alive, action, pursuitTargetId,
engagedTargetId, attackTargetId]`. Mechanics ship once, keyed by unit id, in a
sibling `units` map. `finalStateHash` and `eventLogHash` are still computed over
the full internal state, so the hashes stay comparable to today's.

Client change is confined to the one place that reads `unit.mechanics.hp`.

### Pinned configuration

`experiments.js` and `ai-orders.js` take their values from an exported config
object whose committed defaults are the calibrated ones
(`engagement: "pursuit"`, `orders: true`). Environment variables still override,
for experiments. This also removes the two `process.env` reads that block the
engine from ever running in a browser — not the goal here, but free.

### UI delta

In `viewer/index.html`, the single Matchup `<select>` becomes two unit selects
(Side 2, Side 3) populated from `/api/units`, and the engagement-ratio combobox
becomes two number inputs. Counts default to the `purchase.js` result for the
selected pair and are freely editable from there.

The repeat select stays in place; it selects which recorded repeat supplies the
`tapeReference` numbers, and is disabled when the current selection has no
recording.

Transport, telemetry, event tape, run ledger, map toggles, review panel,
provenance block: unchanged.

## Verification

Each gate is pass/fail, not a judgement call.

1. **Placement reproduces the archive.** `placeArmy` regenerates all 678
   recorded side-layouts exactly, as unordered position sets. This is the gate on
   the whole design; if it cannot reach 100%, the residue is characterised and
   reported before anything is built on top.
2. **Purchase reproduces the corpus.** `deriveCounts` returns the recorded
   `(n2, n3)` for all 101 matchups.
3. **Costs reproduce the corpus.** The 14 registry `baseCost` rows yield the 14
   calibrated cost scalars exactly.
4. **Fixture regeneration is additive-only.** Diff of the 14 regenerated
   mechanics fixtures touches only the new cost keys.
5. **No engine drift.** With the config pinned, existing
   `/api/matchup/result` responses keep their current `finalStateHash` and
   `eventLogHash` for all 25 matchups at every recorded ratio.
6. **Payload budget.** A 20v20 fight serialises under 10 MB.
7. `node --test aoe2x/js_simulation/tests` stays green.

Gate 5 is the "same results as what we derived" check, and it is worth being
precise about what it does and does not promise. It pins the *engine*: given the
tape's own roster, today's numbers must survive pinning the config. It does not
pin `/api/fight`, which runs generated rosters and therefore has no prior number
to match — including for the same 25 pairs, whose `/api/fight` results will
differ from their `/api/matchup/result` results because the starting positions
differ. That divergence is expected and is the point of the change.

Gate 1 is what makes the divergence small: the closer `placeArmy` reproduces the
recorded layouts, the closer a generated fight sits to its calibrated
counterpart. Once gates 1 and 2 pass, the natural follow-on measurement — not
part of this change — is to re-run the 101-matchup sweep with generated rosters
and generated counts, and see how far the corpus moves. That number is the real
verdict on whether the product path is faithful.

## Known limits of the input data

Neither of these is caused by this change; both affect how a result should be
read once the viewer can produce it.

- **Hand Cannoneer's kite beat is constructed, not measured.** It comes from the
  unit's reload rather than from a tape column, and the standard-units summary
  names it as the likely cause of its four large deltas. Its fights run; their
  numbers carry less weight than the other three kiters'.
- **Ranged vs ranged has no order model.** Those 21 corpus matchups run natively
  and are reported as unmodelled. Two ranged units selected in the viewer will
  produce a fight, but not a validated one.

## What this does not move

The gap between this engine and replacing the website engine is ability
coverage: the registry declares 32 abilities, the website engine implements and
exercises all 32, the clean-room engine implements 8. This change does not
narrow that. It makes the shell able to exercise what exists.
