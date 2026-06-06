# Patch Analysis & Unit Timeline — Design Spec

**Date:** 2026-06-06
**Status:** Draft for review

## Goal

A flagship "Patches" feature with two intertwined outcomes:

1. **Readable patch log** — each AoE2:DE balance patch presented with a user-provided
   summary of the relevant changes and a link to the official notes. (We do NOT
   reproduce the full official notes; the user pastes the relevant text, we store/format it.)
2. **Data-driven impact analysis** — for every unit a patch changed, show *how the
   change moved its rankings and matchups*, using our simulation: stat deltas
   (before→after), ranking movement, and the specific matchups that flipped — each
   with a deep link to view that fight in the Battle Sim.

Every patch's changes are **tagged**, so a unit's record across patches forms a
**timeline** ("how this unit has evolved"). This is intended to be a major highlight
of the site.

## First patch to process

- **Build 177723** — https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-177723/
- **Baseline ("before") = our current extracted data** (the 170934 state), per decision.
  The timeline seeds at `[170934 → 177723]` and grows forward with each future patch.
- The new `.dat` (`extraction/empires2_x2_p1.dat`, dated Jun 2) is build 177723.

**Combat-relevant unit changes in 177723** (what the analysis will quantify):

| Unit / civ | Change |
|---|---|
| Armenians — Elite Composite Bowman | HP 45 → 50; civ gains Siege Ram |
| Muisca — (Elite) Temple Guard | cost 80f/45g → 70f/45g; anti-cav bonus +3→+5 (Elite +6→+8) |
| Muisca — (Elite) Guecha Warrior | HP 50→55 (Elite 50→60) |
| Wei — (Elite) Tiger Cavalry | HP 115→110 (Elite 130→125); train 15→18s |
| Tupi — Blackwood Archer | train 14→18s (Elite unchanged) |
| Inca — Kamayuk | food cost adjusted to net-unchanged (civ food discount ↑) |
| Champi Warrior-line | train times; Runner/Warrior upgrade cost & research time |
| Slinger | cost 70f/10w → 50f/25w; +2 conversion resistance |
| Xolotl Warrior | newly affected by 6 techs |

Economy/civ-bonus/naval/tower changes (Burgundians eco, Inca/Mapuche/Muisca eco
bonuses, Dock/Tower anti-ship) are recorded in the patch summary but are **not
unit-vs-unit matchup changes**, so they get a note, not a re-sim.

## Architecture — 5 components

```
.dat (new patch)
  │  (1) patch_pipeline.py: archive old JSON, re-extract, diff
  ▼
extracted_data/ (new)  ──diff vs──  extracted_data_prev/ (before)
  │                                        │
  │  (2) rebuild ref/main DBs, re-apply surgical patches
  ▼                                        ▼
aoe2_reference.db (new patch state)   patch_unit_changes (raw stat deltas)
  │
  │  (3) re-sim ONLY changed units (--changed-units, already built);
  │      snapshot old matchup outcomes first
  ▼
matchup_db.db  ──diff outcomes──►  patch_matchup_changes + patch_unit_ranking
  │
  │  re-derive pool_scores / derived_data / civ_power_units
  │  → INSERT a NEW snapshot TAGGED by build_number (never overwrite the prior one)
  ▼
patches.db  ◄── (writes all of the above, tagged by patch_id; holds the builds registry)
  │
  │  current_build = newest patch in the registry
  ▼
Rankings, Matchup Advisor (and other stat pages) read ONLY the current build's snapshot
  │
  ├─ (4) /patches  → Patches tab: timeline + per-patch summary + official link
  └─ (5) /patches/<build>/<civ>/<unit> → per-unit analysis: stat deltas, ranking move,
         matchup flips, "▶ View this fight" deep links into the Battle Sim
```

## Data model — new `webapp/patches.db`

```sql
CREATE TABLE patches (
  id INTEGER PRIMARY KEY,
  build_number TEXT UNIQUE NOT NULL,   -- "177723"
  release_date TEXT,                   -- "2026-06-02"
  title TEXT,                          -- "Update 177723"
  summary_md TEXT,                     -- user-pasted relevant notes (markdown)
  source_url TEXT,                     -- official link
  baseline_build TEXT,                 -- "170934" (the 'before')
  is_current INTEGER DEFAULT 0,        -- exactly one row = 1; the build the live pages read
  created_at TEXT
);

-- Raw game changes, straight from the .dat diff (pre-modeling). One row per field.
CREATE TABLE patch_unit_changes (
  patch_id INTEGER, civ_name TEXT, unit_slug TEXT,
  field TEXT,                          -- "hp" | "attack" | "cost_food" | "train_time" | "attack_bonus:cavalry" ...
  old_value REAL, new_value REAL,
  note TEXT                            -- optional human note ("gains Siege Ram")
);

-- How the unit's ranking moved (per pool/scale). From re-derived scores.
CREATE TABLE patch_unit_ranking (
  patch_id INTEGER, civ_name TEXT, unit_slug TEXT, scale TEXT,
  old_score REAL, new_score REAL, old_rank INTEGER, new_rank INTEGER
);

-- Matchups that shifted for a changed unit. Drives "now beats / now loses".
CREATE TABLE patch_matchup_changes (
  patch_id INTEGER, my_civ TEXT, my_unit_slug TEXT,
  opp_civ TEXT, opp_unit_slug TEXT, scale TEXT,
  old_winner INTEGER, new_winner INTEGER,
  old_score REAL, new_score REAL, swing REAL
);
```

Timeline = `SELECT ... WHERE unit_slug=? ORDER BY p.release_date` across all tables.
Committed like our other sim-data DBs. *(Rejected alternative: per-patch JSON files —
simpler but poor for cross-patch queries.)*

## Versioning the result DBs (rankings + matchup advisor)

The derived result data that drives the Rankings and Matchup Advisor pages is itself
**versioned by build**, so each patch keeps its own immutable snapshot and the live pages
always read the **current (newest) build**. This is also what makes the timeline real: the
per-unit "ranking moved X→Y" is just two adjacent build snapshots compared.

**What gets tagged (all small — KB/low-MB, cheap to keep every build, committed):**

| Result artifact | File | Versioning change |
|---|---|---|
| `battle_scores` | `webapp/derived_data.db` | add `build_number` column; one snapshot per build |
| pool scores | `webapp/pool_scores.db` | add `build_number` column; one snapshot per build |
| civ power units | `webapp/civ_power_units/<build>.json` | one file per build (replaces the single flat file) |

The big `matchup_db.db` (193 MB, local, not committed) is **not** versioned per build — it
stays the live incrementally-updated source. The "before" outcomes needed for the diff are
preserved in `patch_matchup_changes` at re-sim time (snapshot-before-overwrite, per pipeline
step 5), so we never need to keep two copies of the 193 MB DB.

**Current-build resolution.** The `patches.is_current` flag (one row = 1) marks the current
build; it's explicit and overridable, and defaults to the newest by `release_date`. A single
helper `get_current_build()` (reads `patches.db`) is the one place the answer lives —
`SELECT build_number FROM patches WHERE is_current=1`.

The Rankings query (`/api/ref/unit-line`) and the advisor's `civ_power_units` load both
resolve through `get_current_build()` and filter `WHERE build_number = ?` (or load
`civ_power_units/<current>.json`). No page hard-codes a build.

**Baseline migration (one-time, before the first patch run).** The currently committed
`derived_data.db` / `pool_scores.db` / `civ_power_units.json` already represent the **170934**
state. A one-time migration tags them as `build_number = '170934'`, seeds a `patches` row for
170934 (marked current), and moves the flat JSON to `civ_power_units/170934.json`. After the
177723 pipeline runs, 177723 becomes current; 170934 remains queryable as the prior snapshot.

**Scope note:** the *stat-source* DBs (`aoe2_units.db`, `aoe2_reference.db`) and the live
legacy-sim overlay (`/api/matchup-sims`) reflect the **current** build only — they are rebuilt
in place each patch and are not snapshotted per build in this iteration. Consequence: a
"▶ View this fight" deep link always opens the fight at *current* stats, while the patch page's
stored stat-deltas/outcomes show the historical before→after. Versioning the stat-source DBs
(to replay a fight exactly as it was in an old patch) is future work.

## Pipeline — `webapp/patch_pipeline.py` (one repeatable run per patch)

0. **(One-time, first run only) Baseline migration** — `migrate_baseline.py`: add the
   `build_number` columns, tag existing `derived_data.db` / `pool_scores.db` rows as `170934`,
   move `civ_power_units.json` → `civ_power_units/170934.json`, and seed the `patches` row for
   170934 marked `is_current=1`. Idempotent; skips if 170934 already present.
1. **Archive** current `extraction/extracted_data/` → `extraction/extracted_data_prev/`.
2. **Re-extract**: `python -m extraction.run` on the new `.dat` → fresh JSON. (genieutils-py confirmed installed.)
3. **Diff JSON** prev↔new → write `patch_unit_changes` (raw, pre-modeling — clean attribution of *game* changes). Cross-check against the pasted notes; flag anything in the notes not seen in the diff (and vice-versa).
4. **Rebuild** `aoe2_reference.db` + `aoe2_units.db`; re-apply surgical patches (`analysis/patches/patch_mayan_archer_cost.py`).
5. **Snapshot** current matchup outcomes for the changed units (from `D:\AI\matchup_db.db`); **re-sim** only the changed units (`run_matchup_battles.py --changed-units <list>`, derived from step 3).
6. **Diff outcomes** → `patch_matchup_changes`; **re-derive** the result DBs as a **new
   build-tagged snapshot** (INSERT rows with `build_number=<new>` into `pool_scores.db` /
   `derived_data.db`; write `civ_power_units/<new>.json`) — the prior build's snapshot is left
   intact. Capture old-vs-new scores (current build vs new build) → `patch_unit_ranking`.
7. **Insert** the `patches` row (build, date, pasted `summary_md`, `source_url`) and flip
   `is_current` to the new build (clear it on the prior one). This is the switch that makes the
   live pages show the new patch.

Changed-unit list for re-sim = (units with stat changes in step 3) ∩ (matchup-DB slugs),
plus their elite/imperial forms. Re-uses the incremental machinery already built.

## UI

**Nav:** add a single **"Patches"** tab (`active_nav='patches'`) to `base.html`.

**`/patches`** — timeline (newest first). Each patch card: title, date, official-link
button, the formatted summary, and a chip list of changed units (linking to per-unit
analysis).

**`/patches/<build>/<civ>/<unit>`** — dedicated per-unit analysis page (linked from the
patch card's changed-unit chips):
- **Stat deltas**: table of changed fields, before→after, with up/down arrows.
- **Ranking move**: pool score + rank before→after, per scale (30v30 / 3k).
- **Matchup shifts**: grouped "Now beats" / "Now loses to" / "Bigger/smaller margin",
  each row = opponent + scale + before→after score + swing, and a **"▶ View this fight"**
  link to the Battle Sim.
- **Timeline strip**: this unit's prior patch changes (once >1 patch exists).

**Deep links:** add `?civ1=&unit1=&civ2=&unit2=&mode=` query-param support to the Battle
Sim page (`simulate.html`/`simulate.js`) so links pre-load + auto-run the exact matchup.

**Existing pages read the current build.** The Rankings page (`/api/ref/unit-line`,
`derived_data.db` + `pool_scores.db`) and the Matchup Advisor (`civ_power_units`) are updated
to resolve `get_current_build()` and read only that build's snapshot. They show the latest
patch automatically once the pipeline flips `is_current`. (A user-facing patch/version selector
on these pages is a possible later enhancement — out of scope here; default is always latest.)

## Testing

- Pipeline: unit-test the JSON diff (synthetic before/after) and the matchup-delta computation.
- A `patches.db` integrity check (every `patch_matchup_changes` row references a real patch + unit).
- Frontend: routes return 200; deep-link params parse correctly.
- Cross-check: the diff's changed units match the pasted notes' unit list (warn on mismatch).
- Versioning: exactly one `is_current` build; `get_current_build()` returns the newest patch;
  Rankings/Advisor read only current-build rows; the baseline migration is idempotent and leaves
  170934 + 177723 snapshots both queryable.

## Out of scope (future)

- Back-filling patches earlier than 170934 (would need older `.dat`s).
- Live/on-request re-sim (everything is precomputed + stored).
- Auto-fetching official notes (user pastes the relevant text).
