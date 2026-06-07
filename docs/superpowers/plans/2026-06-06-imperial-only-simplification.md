# Imperial-Only Simplification — Implementation Plan

**Goal:** Make the app deal only with fully-upgraded **Imperial Age** units. Remove Castle Age from all user-facing surfaces (rankings, civ pages, matchup advisor, battle sim) and expose each civ's actual top unit per line (e.g. Korean knight line → **Cavalier**, not Paladin).

**Approach (user-approved):** *Hide everywhere* — keep Castle rows in `ref_units`/`unit_stats` as dormant upgrade-chain intermediates (the pipeline needs them to compute the Imperial unit), but never serve or show Castle. Plus a **top-unit lookup** helper/API/JSON.

**Key fact:** The Imperial `ref_units.unit_name` already resolves to the per-civ highest tier (Koreans paladin→Cavalier, Persians→Savar). So naming is mostly a *display* fix, not a data fix.

---

## Phase 1 — Top-unit lookup (self-contained, high value)
- Create `webapp/top_units.py`: `compute_top_units(ref_db)` → `{civ: {line_key: {line_name, building, units:[{slug, unit, is_unique}]}}}` resolved from `UNIT_LINES` (unique vs standard `imperial_slug`) × `ref_units` Imperial rows (only lines the civ actually has).
- Generate committed `webapp/civ_top_units.json` (easy access for app + assistant).
- API: `GET /api/top-units/<civ>` and `GET /api/top-unit/<civ>/<line>`.
- Verify: Koreans knight→Cavalier, Persians knight→Savar, Franks knight→Paladin, Aztecs no knight.

## Phase 2 — Backend: serve Imperial only
- `app.py`: every rankings/pool/civ-power/matchup/combat-unit query defaults to and is locked at Imperial. Drop the `castle` branch from `/api/civ-power-units` response and the rankings/units payloads. `_VALID_AGES` → imperial-only (reject/ignore castle).
- `best_units.compute_civ_power_units`: stop emitting the `castle` age key (imperial only).

## Phase 3 — Frontend: remove Castle controls
- `rankings.js`: drop the Castle/Imperial age toggle; hardcode Imperial; remove `line.castle` usage.
- `civ-detail.js`: drop age toggle; Imperial units only.
- `matchup_advisor.js`: drop age buttons; lock `imperial`.
- `simulate.js` / `simulate.html`: remove the Castle option from the unit/age pickers; default + lock Imperial.
- Templates (`index.html`, `civilizations`, `matchup_advisor.html`, `simulate.html`): remove age-toggle markup.

## Phase 4 — Verify + ship
- Boot server; confirm no Castle controls anywhere, rankings/civ/matchup/sim show Imperial top units with correct per-civ names, top-unit API works.
- Commit on staging → promote to main.

**Non-goals:** Deleting Castle rows from DBs; restructuring the pipeline's age dimension (deferred — "hide" approach keeps them dormant).
