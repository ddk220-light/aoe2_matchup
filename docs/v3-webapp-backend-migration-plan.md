# V3 web-app migration plan: backend first

**Date:** 2026-09-02
**Status:** backend implemented on `simulationv3`; frontend migration pending
**Scope of this document:** make the calibrated V3 simulation engine and its
complete unit-mechanics data available to the production web app and to
headless callers. The visual migration follows only after the backend gates in
this document pass.

## 1. Decisions

1. The production unit picker remains backed by `aoe2_reference.db` and the
   existing civilization/unit catalogue. There will not be a second,
   hand-maintained production unit list.
2. The existing endpoint
   `/api/ref/combat-unit/<civ_name>/<unit_slug>?age=Imperial` remains the
   canonical unit lookup. Its response is extended additively with a versioned
   V3 `mechanics` object.
3. V3 mechanics are generated for every selectable civilization/unit/age row
   when the reference database is built. Production does not read the game DAT
   and does not generate mechanics on request.
4. Ordinary stats and special-effect parameters remain data. The V3 engine
   implements reusable mechanic families. It must not contain matchup-specific
   winner, HP, timing, target, or waypoint corrections.
5. The same V3 combat modules run in three places:
   - the browser Web Worker for an interactive fight;
   - a Node headless CLI for tests and one-off runs;
   - Node worker threads for batch simulation.
6. The interactive backend returns data and scenario configuration; it does not
   precompute the fight. The browser starts stepping and rendering the fight as
   soon as configuration arrives.
7. The existing V3 JSON fixtures remain regression evidence. They do not become
   the production catalogue or a runtime filesystem dependency.

## 2. Current state and the seam to preserve

The current production flow is already sound:

```text
picker
  -> GET /api/ref/combat-unit/<civ>/<slug>
  -> Flask queries ref_units
  -> build_combat_dict_from_ref(row)
  -> browser receives one combat dict per side
  -> createSimulation({ teams, seed })
```

The migration replaces the simulation implementation behind that seam. It does
not replace the picker, SQLite lookup, upgrade calculation, or asset catalogue.

There are currently two mechanics representations:

- `build_combat_dict_from_ref()` emits the flat object consumed by the existing
  web engine. Its ability fields are generated from `ability_registry.py`.
- `export_unit_mechanics.py` combines reference-database values with additional
  DAT structure and V3 runtime effects to create the richer nested fixtures
  consumed by the calibrated engine.

The backend migration consolidates these into one generator. In particular,
`REFERENCE_EFFECT_COLUMNS`, `CURATED_RUNTIME_EFFECTS`, and
`CURATED_CIV_RUNTIME_EFFECTS` must not remain a production-only second registry
inside the fixture exporter.

## 3. Target data contract

### 3.1 Stable unit identity

Every mechanics record is keyed by:

```json
{
  "civilization": "Chinese",
  "unit_slug": "elite_chu_ko_nu_chinese",
  "age": "Imperial",
  "unit_master": 559,
  "mode": "default"
}
```

Civilization and mode are part of the identity. A slug alone is insufficient
because civilization upgrades change final stats and some units expose more
than one weapon form.

### 3.2 Runtime mechanics object

The V3 object stored and served by the backend contains only runtime data:

- final HP, speed, sight, population, cost, attack and armor classes;
- collision, clearance and outline geometry;
- attack animation duration and projectile release delay;
- reload, attack range, minimum range and accuracy;
- primary, secondary and charge-projectile structure;
- blast, splash, pass-through and friendly-fire parameters;
- charge, regeneration, bleed, armor interaction, defensive, aura, tempo,
  transformation and dismount blocks;
- movement/obstruction classification and behavior family;
- named weapon modes where a unit has more than one selectable mode.

Local capture paths, calibration outcomes, expected winners and survivor HP do
not belong in this payload.

### 3.3 Versioning and integrity

Each payload carries:

```json
{
  "mechanics_schema_version": 1,
  "mechanics_hash": "<sha256 of canonical runtime JSON>",
  "source_build": "<game/reference-data build identifier>"
}
```

The engine has its own `engine_version`. A battle result records both profile
hashes, the engine version, scenario version and seed, making any result exactly
identifiable without retaining a large replay.

## 4. Backend implementation phases

### Phase B0 — checkpoint and baseline

Before migration edits:

1. Commit the current V3 engine, its unit-effect implementations, tests and
   documentation as an isolated checkpoint.
2. Exclude raw recordings, decoded traces, videos, screenshots, temporary
   reports and other generated bulk data.
3. Record a deterministic five-seed result manifest for the accepted regression
   matchups. This is a gate, not a source of runtime parameters.

**Exit gate:** a clean commit identifies the accepted pre-migration engine and
its deterministic regression results.

### Phase B1 — define one canonical mechanics schema

Create a browser-safe schema module and JSON Schema for the V3 mechanics
object. Split it into these conceptual sections:

```text
identity
base combat stats
geometry
attack timing
ranged/projectile model (nullable)
blast model
charge model (nullable)
effects
alternate forms/modes
behavior classification
```

Add strict validation for finite numbers, nonnegative radii/times, required
attack and armor maps, valid enum values and recursively validated alternate
forms.

Do not silently substitute legacy defaults for an invalid or incomplete special
ability. Neutral defaults are allowed only when the schema explicitly defines
them.

**Exit gate:** every checked-in V3 mechanics fixture validates under the same
schema and the engine accepts only that validated shape.

### Phase B2 — consolidate special-effect declarations

Make `aoe2x/dbgen/ability_registry.py` the declaration point for every runtime
effect required by V3, including fields that currently exist only in
`export_unit_mechanics.py`, such as:

- on-hit slow details and affected-unit exclusions;
- nearby-unit aura radius;
- delayed impact, repeated impact and death explosion;
- persistent impact hazards;
- charged movement conditions;
- volley cadence and reload-after-final-projectile behavior;
- weapon-mode-specific mechanics.

Keep the distinction between:

1. DAT-extracted fields;
2. values derived from the fully upgraded technology chain;
3. documented unit/civilization rules that are not represented as a simple DAT
   scalar;
4. source-backed V3 behavioral measurements, such as a repeating-volley release
   cadence.

All four are unit mechanics, but their provenance must remain explicit. Move
curated values into the existing dbgen configuration/registry layer so both the
database and fixture exporter consume them.

Generate the list of reference columns from the registry. Delete the duplicated
manual `REFERENCE_EFFECT_COLUMNS` list after parity is proven.

**Exit gate:** an automated audit finds no runtime-effect key emitted by the V3
fixture exporter that is absent from the canonical registry/data builder.

### Phase B3 — turn the V3 fixture exporter into a reusable builder

Refactor `export_unit_mechanics.py` so its core is an importable pure builder:

```python
build_v3_unit_mechanics(
    reference_row,
    stat_chain,
    applied_techs,
    dat_unit,
    dat_projectiles,
    declared_effects,
    mode,
) -> dict
```

The command-line fixture exporter becomes a thin caller of this function.
Reference database generation calls the same function for every selectable row.
This prevents production payloads and calibration fixtures from drifting.

The builder must support nested alternate forms (Konnik dismount, Jian
transformation) and explicit modes (Ratha and War Chariot) without checking the
opposing unit or scenario family.

**Exit gate:** regenerating each existing calibrated fixture through the shared
builder produces the same canonical runtime mechanics after excluding
provenance-only fields.

### Phase B4 — store complete V3 mechanics in the reference database

Add the DAT master identifier to `ref_units`, then add a one-to-one table:

```sql
CREATE TABLE ref_unit_mechanics (
    ref_unit_id INTEGER PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    mechanics_json TEXT NOT NULL,
    mechanics_hash TEXT NOT NULL,
    source_build TEXT NOT NULL,
    FOREIGN KEY (ref_unit_id) REFERENCES ref_units(id)
);
```

Generate canonical compact JSON with sorted keys. Store one row for every
selectable reference unit, including ordinary units whose `effects` object is
empty. This gives one uniform production path instead of a generic path plus a
special-unit fixture fallback.

Production Railway builds continue to consume the checked-in generated
reference database. They never require a local AoE2 installation or DAT file.

**Exit gates:**

- every selectable unit row has exactly one valid mechanics row;
- every mechanics hash recomputes correctly;
- no mechanics payload contains a local path, live result or calibration
  expectation;
- regenerating the database twice from the same inputs is byte/canonical-JSON
  deterministic.

### Phase B5 — extend the existing combat-unit API additively

Keep the existing flat response fields for the current production page and add:

```json
{
  "mechanics_schema_version": 1,
  "mechanics_hash": "...",
  "mechanics": { "...": "complete V3 runtime payload" }
}
```

The endpoint loads the mechanics row in the same database transaction as the
unit row and validates its schema version. Return a clear server error if the
payload is missing, invalid or incompatible; never silently fall back to the
old mechanics for a V3 request.

Use the mechanics hash as an ETag and allow immutable/private caching of a
specific generated data build. Keep the old response contract intact so this
can deploy before the frontend migration.

**Exit gates:**

- existing endpoint tests pass unchanged;
- new contract tests cover an ordinary melee unit, ordinary ranged unit,
  repeating volley, charge, splash/pass-through, transformation, dismount and
  two-mode unit;
- a catalogue test requests or directly builds all selectable rows and validates
  every returned mechanics object.

### Phase B6 — extract a shared V3 engine package

Separate browser-safe mechanics from Node adapters:

```text
aoe2x/js_simulation/src/combat/       pure deterministic engine
aoe2x/js_simulation/src/scenario/     pure scenario construction
aoe2x/js_simulation/node/             filesystem, CLI and worker-thread adapters
apps/website/static/js/v3/            served entry points or build output
```

The pure layer must have no DOM, Flask, SQLite or Node filesystem dependency.
Replace `fight.js` filesystem fixture loading with dependency injection: callers
provide validated mechanics objects.

Add a compact stepping API that retains current state and aggregate counters but
does not append the full event log and full snapshot history every tick:

```js
const battle = createBattle(config)
battle.stepFixedTick()
const frame = battle.presentationSnapshot()
const result = battle.result()
```

**Exit gates:**

- existing V3 regression tests pass through the extracted package;
- browser and Node imports execute identical seeded fights and produce the same
  final-state/event hashes;
- the compact runtime does not grow memory linearly with fight duration.

### Phase B7 — provide a reusable headless interface

Add a Node JSON-lines CLI that accepts complete battle configurations on stdin
and writes structured results on stdout. It must support:

- one fight with an explicit seed;
- N seeds in parallel using worker threads;
- fixed-count and equal-resource army sizing;
- direct and buffered scenarios;
- concise result output by default and optional trace/event output;
- deterministic ordering of results regardless of worker completion order.

Python orchestration may invoke this CLI, but must not reimplement combat
mechanics. This is the supported interface for batch rankings, calibration and
other services that need to run the engine independently of the website.

**Exit gates:** five-seed output matches direct in-process Node execution, CPU
workers are bounded/configurable, failures are reported per seed, and a failed
job cannot corrupt another result.

### Phase B8 — centralize battle/scenario configuration

Add a backend battle-config endpoint, while continuing to use the existing unit
lookup internally:

```http
POST /api/v3/battle-config
```

Input:

- both civilization/unit/age/mode selections;
- army-size rule and its parameters;
- optional explicit seed;
- `engagement_mode: "direct" | "ranged_buffer"`.

Output:

- resolved unit counts and costs;
- the two complete mechanics objects and hashes;
- golden-map/scenario version;
- formations, initial orders, diplomacy and triggers;
- public team mapping and internal owner mapping;
- generated seed and engine version.

`direct` is the default and contains only the two opposing armies.
`ranged_buffer` is initially offered only for a ranged-versus-melee pairing and
uses the validated fixed P4 screen, diplomacy and defeat trigger. The auxiliary
owner is an internal scenario actor, not a third user-selected team.

Count derivation and golden placement filling are shared with the headless
runner so an interactive and headless request with the same configuration starts
from exactly the same state.

**Exit gates:** direct and buffered configs validate for both visual
orientations, counts never exceed formation capacity, and the returned public
winner excludes auxiliary units.

### Phase B9 — complete backend validation and observability

Required automated gates before frontend work begins:

1. **Catalogue coverage:** 100% of selectable civ/unit/age/mode choices produce
   valid V3 mechanics.
2. **Ability coverage:** every non-neutral declared runtime effect maps to an
   implemented V3 mechanic family.
3. **No silent fallback:** deleting a mechanics row or handler makes the build or
   request fail explicitly.
4. **Fixture parity:** accepted calibrated units match the canonical DB-generated
   runtime payload.
5. **Determinism:** same config and seed produce the same event/final-state hash
   across repeated runs and worker counts.
6. **Regression:** accepted live-comparison matchups retain the correct winner
   and recorded HP-delta thresholds.
7. **API compatibility:** the current production frontend still works against
   the extended endpoint.
8. **Performance:** five-seed headless runs use bounded parallelism; a single
   browser-scale 27v27 fight can be stepped faster than presentation time on the
   deployment and target-device baselines.

Log small structured records only: battle ID, selected identities, counts,
profile hashes, engine/scenario versions, seed, duration, winner, remaining HP,
tick count and error code. Do not retain per-tick traces unless explicitly
requested.

## 5. Backend commit sequence

Keep the migration reviewable with isolated commits:

1. `v3: add canonical mechanics schema and validation`
2. `data: consolidate v3 runtime effects into ability registry`
3. `data: share mechanics builder between fixtures and reference db`
4. `data: persist versioned mechanics for every selectable unit`
5. `web: expose v3 mechanics through combat-unit api`
6. `v3: extract browser-safe engine and compact stepping api`
7. `v3: add deterministic headless and worker-thread runner`
8. `web: add versioned v3 battle-config endpoint`
9. `test: enforce catalogue, ability, parity and regression gates`

Do not mix generated capture artifacts, videos, decoded frames or calibration
scratch output into these commits.

## 6. Backend completion definition

Backend migration is complete when:

- any unit available in the current web picker returns a complete, validated V3
  mechanics object through the current combat-unit path;
- every special effect used by those units is represented as data and handled by
  a reusable V3 mechanic;
- arbitrary supported matchups can run through the documented headless CLI
  without the website;
- the battle-config endpoint creates the same deterministic initial world as the
  headless runner;
- the current production page remains operational because all API changes are
  additive;
- no production path loads a checked-in per-unit V3 fixture or requires a game
  DAT installation;
- no output fitting or matchup-specific runtime rule has been introduced.

At that point the frontend can migrate independently: request one battle config,
start the V3 engine in a Web Worker, and render snapshots immediately with the
new isometric map and the existing production unit/projectile artwork.

## 7. Interactive execution after the backend migration

The backend does not make the user wait for a complete simulation:

```text
Run clicked
  -> fetch battle config and any uncached artwork
  -> initialize browser worker
  -> worker advances fixed V3 ticks
  -> page renders the newest snapshot while the fight is running
  -> worker emits the final result at completion
```

The only initial wait is the configuration/assets request. The server is not
running or recording the interactive fight. Headless server-side execution is a
separate facility for batch jobs, validation and future ranking generation.
