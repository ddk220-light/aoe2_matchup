# V3 web simulation backend

The backend migration is complete. The production unit catalogue remains
`data/golden/aoe2_reference.db`; the calibrated V3 engine no longer needs a
hand-maintained production unit list or per-unit JSON fixtures.

## Runtime flow

1. `GET /api/ref/combat-unit/<civilization>/<unit_slug>` reads the existing
   fully upgraded unit row and adds its validated, versioned `mechanics`
   profile, profile hash, source build, selected mode, and available modes.
2. `POST /api/v3/battle-config` resolves two selections, modes, resource/count
   policy, seed, scenario family, and optional ranged buffer. It returns the
   complete unit profiles plus the actual golden map, first-N formation cells,
   patrols, diplomacy, triggers, victory teams, and Player 4 mechanics.
3. The browser frontend can pass that response directly to its worker and
   animate snapshots while the fight is running. Frontend rendering is the
   next migration phase; the backend does not precompute interactive fights.
4. Other systems can send the same response to the Node headless runner. The
   engine uses the supplied database profiles and never imports SQLite.

Special effects are data too. DAT/technology-chain scalars come from
`ref_units`; nested event and weapon-mode declarations that cannot be expressed
as one scalar live in `aoe2x/dbgen/v3_runtime_config.py`. The fixture exporter
and reference database generator consume that same configuration. Matchup
results, survivors, fitted delays, targets, or waypoints are not accepted as
runtime mechanics.

## Rebuilding the golden database

The deployed app only needs the committed SQLite file. A machine regenerating
it needs the extracted project data and, for the V3 profiles, a local AoE2 DAT:

```powershell
python -m aoe2x.dbgen.generate_reference `
  --reference-db data/golden/aoe2_reference.db `
  --v3-dat "C:\path\to\AoE2DE\resources\_common\dat\empires2_x2_p1.dat" `
  --require-v3
```

`AOE2_DAT_PATH` may replace `--v3-dat`. Generation builds and validates every
profile before atomically replacing either mechanics table. A bad unit cannot
publish a partially populated table.

Database ownership is complete:

- `ref_units.unit_master` stores the concrete DAT master identifier;
- `ref_unit_mechanics` stores one or more named modes per selectable row and
  enforces one default mode;
- `ref_auxiliary_mechanics` stores scenario-owned actors such as the golden
  Player 4 Scout Cavalry/Hussar body.

Each compact JSON profile is validated, canonically serialized, SHA-256 hashed,
and tagged with its source DAT hash. The runtime payload intentionally excludes
local paths and calibration provenance.

## API examples

Retrieve a unit's default mode:

```http
GET /api/ref/combat-unit/Shu/war_chariot_shu?age=Imperial
```

Select another mode:

```http
GET /api/ref/combat-unit/Shu/war_chariot_shu?age=Imperial&mode=barrage
```

Resolve an interactive or headless fight:

```json
POST /api/v3/battle-config
{
  "teams": [
    {"civ": "Chinese", "unit_slug": "arbalester", "count": 20},
    {"civ": "Spanish", "unit_slug": "paladin", "count": 20}
  ],
  "army": {"mode": "explicit"},
  "engagement_mode": "ranged_buffer",
  "seed": 12
}
```

Army modes are `explicit`, `equal_count`, and `equal_resources`. Resource
weights are configurable and may be zero as long as at least one weight is
positive. Formation limits are validated before a config is returned.

## Headless execution

The runner accepts one JSON document, an array, a `{ "jobs": [...] }` document,
or newline-delimited JSON on stdin or through `--input`. An integer `seeds`
expands to seeds starting at zero; an array selects exact seeds. Results remain
in input order even when worker threads finish out of order.

```powershell
node aoe2x/js_simulation/node/headless-runner.mjs --workers 4 --input battle.json
```

By default it returns compact results: winner, remaining HP, starting HP,
ticks, engine family, unit summaries, and deterministic event/final-state
hashes. Set `retainSnapshots: true` only when playback is explicitly needed.
One invalid job returns an error row for that job without discarding completed
siblings.

For `ranged_buffer`, pass the battle-config response so the generated Player 4
mechanics accompanies the job. Direct fights require only the two team
profiles. The headless adapter loads golden scenario files; the combat engine
itself receives mechanics and scenario data through dependency injection.

## Validation

Focused backend gates live in `tests/test_v3_backend.py` and
`aoe2x/js_simulation/tests/mechanics-schema.test.mjs`. They cover:

- every selectable database row and mode;
- canonical JSON and mechanics hashes;
- additive compatibility of the existing combat-unit endpoint;
- alternate weapon modes;
- direct and buffered golden configuration, including Player 4;
- actual database-profile fights through Node;
- repeatability across serial and parallel execution;
- per-job failure isolation and schema/provenance rejection.
