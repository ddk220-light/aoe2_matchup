# Unit Rankings Table Redesign — Design

**Status:** Approved, ready for implementation plan.

**Predecessor:** `2026-04-29-pool-scores-ui-design.md` (HP-only Score column,
scale toggle). This spec restructures the *table* itself — columns shown,
expansion behavior, Special-cell content — while preserving the existing
scale toggle and pool-scores backend.

## Goal

Slim the default Unit Rankings table to ~8 columns and let users
progressively reveal more detail through column-group expansion:

1. Each role column (GC / AC / AT / AA) expands to show per-line means
   (e.g. GC vs Militia / Knight / Archer).
2. The Special column expands to show the existing unit-stats columns.
3. An Expand All / Collapse All button toggles all four groups together.

Per-line breakdown values are computed by the existing pool-scores
pipeline; we surface them by adding a JSON column to `pool_scores.db`.
The Special column gains a "Missing: ..." line listing techs the civ
lacks for that unit.

## Non-goals

- No change to the score formula, scale toggle, or pool definitions.
- No persistence of expansion state — collapsed every page load.
- Siege / naval pools keep their existing columns and scoring.
- No re-ordering of pool tabs or sub-line filters.

## Default column layout (slim view)

State on page load: every expandable group is **collapsed**. Headers
that are expandable carry a chevron (`▸` collapsed, `▾` expanded).

| Pool | Default columns |
| --- | --- |
| Infantry | Civ \| Unit \| Line \| HP \| GC ▸ \| AC ▸ \| AT ▸ \| Special ▸ |
| Archer   | Civ \| Unit \| Line \| HP \| GC ▸ \| AA ▸ \| Special ▸ |
| Stable   | Civ \| Unit \| Line \| HP \| GC ▸ \| AC ▸ \| Special ▸ |

- **Civ / Unit** — same icons + hover cards for tech and unique-effect
  breakdowns as today.
- **Line** — sub-line label (Militia / Spear / Knight / etc.).
- **HP** — the HP-axis pool Score, respecting the existing Pop / Cost /
  Average scale toggle. Header reads `HP (Pop)` / `HP (Cost)` / `HP (Avg)`
  depending on toggle state. Sort default: descending.
- **GC / AC / AT / AA** — role means, signed, two decimals, sortable.
- **Special** — see "Special column" section.

**Siege** and **Naval** tabs are unchanged: their existing columns
(`Civ | Unit | Line | Score | DPS | HP | Atk | M.Arm | P.Arm | Speed |
Range | Cost | Upg Cost | Special`) and legacy `battle_scores` data
remain in place. No expansion behavior on those tabs.

## Expansion behavior

### Per-column expand affordance

Each expandable header has two distinct hit targets:

- **Chevron icon** (`▸` / `▾`) — clicking toggles expansion only.
- **Rest of the header** (label + sort arrow area) — clicking sorts.

### Per-line columns

| Pool | Role | Lines revealed (in order) |
| --- | --- | --- |
| infantry | GC | militia, knight, archer |
| infantry | AC | knight, camel, steppe_lancer, elephant |
| infantry | AT | spear, skirmisher, light_cav |
| stable   | GC | militia, knight, archer |
| stable   | AC | knight, camel, steppe_lancer, elephant, light_cav |
| archer   | GC | militia, knight, archer |
| archer   | AA | archer, skirmisher, cav_archer, gunpowder |

- Per-line column headers use short labels like `vs Militia`, `vs Knight`,
  `vs Camel`.
- Each per-line column is independently sortable.
- Format: signed value, two decimals — same as the role mean.
- Cells with no battle data show `—`.

The line-key list above mirrors `POOL_ROLES` in `pool_scores_lib.py`.

### Special column expansion

Reveals stat columns in this order:

```
DPS | HP | Atk | M/P Arm | Speed | [Range] | Cost | Upg Cost
```

- **HP** here is the **raw unit HP stat** (e.g., 81 for Berserk). Same
  header label as the slim "HP" Score column — distinguished by position
  (slim section vs expanded section). Acceptable per design discussion.
- **M/P Arm** is a single combined column rendered as `0/4`. Sort sorts
  by melee armor as the primary key.
- **Range** is omitted on infantry / stable pools (always `—` would be
  noise). Shown on archer pool. Already shown on siege / naval today.

### Expand All / Collapse All button

A single button at the top of the table (next to the existing CSV
export / civ-filter row).

- If any group is collapsed, button reads `▸ Expand All` and clicking
  expands all four groups (GC, AC/AA, AT, Special).
- If all groups are expanded, button reads `▾ Collapse All` and clicking
  collapses all four.
- Mixed state (e.g., GC expanded, AT collapsed) is treated as "not all
  expanded" — button reads `▸ Expand All`, click expands the remainder.
  A second click then collapses everything.

### Slide animation

Expanding a group slides the new columns out from immediately right of
the parent column header. Collapsing reverses.

CSS approach:

```css
.col-expandable {
    transition: max-width 200ms ease, padding 200ms ease, opacity 150ms ease;
    overflow: hidden;
    white-space: nowrap;
}
.col-expandable.collapsed {
    max-width: 0;
    padding-left: 0;
    padding-right: 0;
    opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
    .col-expandable { transition: none; }
}
```

The same DOM is rendered either way — only the `collapsed` class on
`<th>` and `<td>` cells toggles. No add / remove of cells mid-animation.
Reduced-motion users see instant transitions.

### Sort interaction

- Clicking a chevron toggles expansion; sort state is unchanged.
- Clicking a per-line column header sorts on that column. Default
  direction descending (higher = better, matching HP axis).
- If the active sort column is in a hidden group (user sorted by
  `vs Knight` then collapsed GC), the rows stay sorted by that hidden
  column. Re-expanding GC reveals the column still sorted.

### State persistence

Fully transient.

- Collapsed by default on page load.
- Switching line tabs, switching age, refreshing — all reset to collapsed.
- No `localStorage` / `sessionStorage` / URL-param state.

## Special column content

Today: `;`-separated unique effects, e.g.
`Trample 25%; Bleed 5 dps; Charge +30 melee`.

New: two visually distinct lines in the cell.

```
Trample 25%; Bleed 5 dps; Charge +30 melee
Missing: Plate Mail Armor, Squires
```

- Top line: existing unique-effect labels, current rendering preserved.
- Bottom line: `Missing: <comma-separated tech names>`. Rendered with
  `color: var(--text-muted)`, smaller font (`0.65rem`), prefixed with
  `❌` glyph (final glyph choice deferred to implementation if it
  clashes with the warm theme).
- If no special effects: only the missing-techs line shows.
- If no missing techs: only the effects line shows.
- If neither: cell shows `—`.

### Source of "missing techs"

Reuse `_compute_missing_techs(civ_standard_techs, reference_techs_for_slug, slug)`
from `webapp/best_units.py:265`. The reference set per slug is "all
standard techs that any civ has applied to this unit"; the helper
already strips slug-irrelevant techs via `_SLUG_TECH_EXCLUSIONS` so e.g.
Halberdier doesn't show "missing Bracer".

No new exclusion logic is in scope.

## Backend schema & API

### `pool_scores.db` schema change

Add one column to the `pool_scores` table:

```sql
ALTER TABLE pool_scores ADD COLUMN role_line_means TEXT;
```

The column stores a JSON object keyed by role, then by line key:

```json
{
  "GC": {"militia": 12.4, "knight": -3.8, "archer": 4.1},
  "AC": {"knight": 5.2, "camel": 8.7, "steppe_lancer": null, "elephant": 6.3},
  "AT": {"spear": 92.7, "skirmisher": 88.4, "light_cav": 95.1}
}
```

- `null` value: line is in the role definition but had no battles for
  this unit at this scale.
- Missing key: line not part of this pool's role definition.

The same schema is created by `pool_scores_db.create_db()` for fresh
DBs and applied via `ALTER TABLE` for existing DBs (in
`derive_pool_scores.py`'s migration step).

### Library change

`pool_scores_lib.derive_unit_scores()` already computes per-line means
internally (see `pool_scores_lib.py:325–333`). Today they collapse into
`role_means[role]` and are discarded. We thread them into output rows
under a new `role_line_means` field, JSON-serialized at the writer
boundary.

### Writer change

`pool_scores_db.insert_score()` writes the new column. Schema in
`pool_scores_db.create_db()` includes the new column.

### Re-derivation

Run `python webapp/derive_pool_scores.py` once after the schema change.
The DB is committed to git (per the Railway-deployment convention
established in commit `c271ecf`); the regenerated `pool_scores.db` blob
is committed.

### API: `/api/ref/unit-line/<slug>`

The existing `pool_scores` payload per unit row gains a `role_line_means`
map per scale, alongside the current `final` / `gc` / `ac` / `at` / `aa`
fields:

```json
{
  "civ_name": "Vikings",
  "unit_slug": "elite_berserk_vikings",
  "...existing fields...": "...",
  "pool_scores": {
    "pool": "infantry",
    "scales": {
      "30v30": {
        "hp": {
          "final": 8.9, "gc": -6.8, "ac": -1.6, "at": 92.7,
          "role_line_means": {
            "GC": {"militia": -10.2, "knight": -5.5, "archer": -4.6},
            "AC": {"knight": -2.1, "camel": 0.0, "steppe_lancer": null, "elephant": -2.8},
            "AT": {"spear": 92.7, "skirmisher": 91.4, "light_cav": 94.0}
          }
        },
        "cost":  {"...": "same shape..."},
        "speed": {"...": "same shape..."},
        "shape": {"...existing...": "..."}
      },
      "3k": {"...same...": "..."}
    }
  },
  "missing_techs": ["Plate Mail Armor", "Squires"]
}
```

`missing_techs` is a new top-level field per unit row. Computed in the
same loop that already builds `special_abilities` (avoids extra
`ref_techs_applied` round-trips).

### `pool_scores_query.load_pool_scores()`

Includes the new column in the SELECT and decodes `role_line_means` into
the response shape. The function's return contract gains the new key
inside each scale's axis dict.

## Frontend state model

```js
// Per-line expansion state — fully transient, resets on page load
const expandedRoles = new Set();   // {"GC", "AC", "AT", "AA", "Special"}

function isExpanded(group) { return expandedRoles.has(group); }

function toggleGroup(group) {
    if (expandedRoles.has(group)) expandedRoles.delete(group);
    else expandedRoles.add(group);
    renderTable();
}

function expandAll() {
    expandedRoles.add("GC"); expandedRoles.add("AC");
    expandedRoles.add("AT"); expandedRoles.add("AA");
    expandedRoles.add("Special");
    renderTable();
}

function collapseAll() { expandedRoles.clear(); renderTable(); }
```

Per-line column keys for sorting follow the pattern
`role_line:<ROLE>:<line_key>` (e.g., `role_line:GC:militia`).
Cell values are denormalized onto the enriched row during the existing
enrichment pass, e.g. `enriched.role_line_GC_militia = ...`, so the
existing `sortBy(column)` function works unchanged.

Switching pool tabs (line tabs in the UI) clears `expandedRoles`
implicitly through the existing tab-switch render path. Same for age
toggle.

## Testing

### Backend (Python)

- `test_pool_scores_lib.py` — extend `derive_unit_scores` tests to
  verify `role_line_means` is present in output rows with correct
  per-line means. Berserker GC values pinned: militia / knight / archer.
- `test_pool_scores_db.py` — schema test verifies the new
  `role_line_means TEXT` column.
- `test_pool_scores_integration.py` — Berserker fixture asserts
  `role_line_means["GC"]["militia"]` matches the expected pinned value.
- `test_pool_scores_api.py` — `/api/ref/unit-line/militia` response
  includes `role_line_means` in each scale's axis dict; `missing_techs`
  array attached to unit row (empty for Berserk under Goths since
  Goths get all militia-line techs).

### Frontend (manual smoke test)

No JS test framework in repo; rely on manual checks:

1. Click chevron on GC → 3 columns slide out; sort by `vs Knight` works.
2. Click GC chevron again → columns slide back; sort retained on
   hidden column.
3. Click Expand All → all four groups expand simultaneously; button
   label changes to `▾ Collapse All`.
4. Switch from infantry tab to archer tab → expansion state resets;
   scale toggle preserved.
5. Refresh page → all groups collapsed, sort defaults restored.

### Reference values

Berserker on infantry tab, default toggles (HP-axis / Average scale):

- **HP**: `+20.25`
- **GC**: `+5.28` — expanding reveals 3 per-line columns.
- **AC**: `+17.6` — expanding reveals 4 per-line columns.
- **AT**: `+92.8` — expanding reveals 3 per-line columns.
- **Special**: `Berserker regen + 0/3 charge` (existing) plus
  `Missing:` line if any (Goths typically have all militia-line techs).

## Out of scope (deferred)

- **Persisting expansion state** across refreshes / sessions — transient
  for v1.
- **Siege / naval pool restructuring** — unchanged.
- **Profile labels** (DOMINANT / RELIABLE / etc.) — still deferred.
- **Per-line breakdown for cost / speed axes** in the UI — the JSON
  column stores all axes, but the v1 UI is HP-only (matches predecessor
  spec).
- **Re-deriving `pool_scores.db` automatically** in CI — manual
  re-derivation + commit, as today.
