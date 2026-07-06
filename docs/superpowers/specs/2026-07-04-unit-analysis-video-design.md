# Unit Analysis Video — Design

**Date:** 2026-07-04
**Branch:** `feature/unit-analysis-video`
**Status:** Approved (validated against Elite Temple Guard / Muisca prototype run)

## Goal

Generate a per-unit "analysis video" for each unique unit: an intro segment
(hi-res unit image + attack animation + stat card), then four narrative
categories of matchups — top-3 expected wins, top-3 unexpected wins, top-3
expected counters, top-3 unexpected counters — each category showing 3 real
recorded AoE2:DE fights followed by a ranked-list card of every remaining
unit in that category, stitched into one video with YouTube chapters.

Two machines, one contract:

- **Analysis** (any machine, incl. this Mac): computes the categorization and
  emits a **storyboard JSON**. Data source is pluggable — the Windows matchup
  baseline DB when present, fresh local sims otherwise.
- **Recording/composition** (Windows box with AoE2:DE + the matchup DB +
  hi-res media): consumes the storyboard, records the 12 fights, composes
  overlays, stitches. Hi-res image / attack-gif assets exist only there; the
  intro composer takes placeholder no-op paths elsewhere.

## Part 1 — Analysis module

New package: `aoe2x/analysis/unit_video_story.py` (+ small helpers). CLI:

```bash
python -m aoe2x.analysis.unit_video_story Muisca elite_temple_guard_muisca \
    --source local-sim --out storyboards/elite_temple_guard_muisca.json
# Windows: --source matchup-db --matchup-db D:/AI/matchup_baseline_170934.db
```

Prints a human-readable summary (picks + full per-category rankings) so the
lists can be eyeballed before any recording happens.

### Opponent pool

- All validated unique units from `auto.build_unique_list.enumerate_uniques()`
  (66 as of build 170934), minus the subject, minus naval
  (`turtle_ship, caravel, longboat, thirisadai, lou_chuan, dromon, galley,
  cannon_galleon`), minus passive/degenerate units
  (`siege_ram, battering_ram, trebuchet, petard, flaming_camel,
  armored_elephant, siege_elephant`).
- Plus 13 generic land staples by line-imperial slug with a **canonical-name
  filter + modal stats-and-cost civ pick** (avoids civ discounts and
  wrong-tier picks like Cavalier-under-paladin-slug):
  `champion, halberdier, arbalester, imp_elite_skirm ("Elite Skirmisher"),
  heavy_cav_archer, paladin, hussar, heavy_camel, elite_steppe,
  elite_elephant, siege_onager, hand_cannoneer, elite_eagle`
  (Heavy Scorpion explicitly excluded — user decision).

### Outcome measurement (S)

Equal-resources battle, budget 3000 weighted resources per side.
`S = (subject_hp_fraction_left − opponent_hp_fraction_left) × 100`, in
[−100, +100]. Two interchangeable backends behind one `MatchupSource`
interface:

- `MatchupDbSource` — reads the Windows baseline DB rows (multi-seed data
  already aggregated by the batch pipeline).
- `LocalSimSource` — `simulation_real.simulate_real_battle`, seeds
  {1..8}, mean margin. (The prototype used the abstract engine for speed;
  production uses `simulation_real` to match the baseline. A 3-matchup
  cross-check showed both engines agree directionally: Chu Ko Nu −100 abs /
  −91 real, Gbeto −98 / −90, Arbalester −33 / −55.)

### Expectation prior (E) — what a knowledgeable player predicts

`E = 0.5·B + 0.3·R + 0.2·C`, clamped [−1, 1].

- **B — net bonus damage** (from `final_attacks_json` / `final_armors_json`):
  each side's class-bonus damage vs the other's armor classes (armor value
  subtracted, floor 0; base-melee/pierce classes 3,4 excluded), normalized by
  base effective damage, difference squashed with `tanh`.
- **R — class rock–paper–scissors**: hand-authored matrix over categories
  {infantry, spear, eagle, archer, skirm, cav_archer, cavalry, light_cav,
  camel, elephant, siege, gunpowder}, antisymmetric lookup, values in
  [−0.7, 0.7]. Categorization from slug keywords + DB `unit_class_name` +
  `is_ranged`, with two overrides discovered in calibration:
  - thrown-weapon infantry (gbeto, throwing axeman, chakram) → `archer`;
  - eagle-classed units with speed < 1.2 → `infantry` (Temple Guard is
    eagle-armor-classed but infantry-speed; it cannot play the eagle game).
- **C — cost prior**: `clamp(ln(subject_cost / opponent_cost) / ln 3, −1, 1)`
  (flat food+wood+gold). Players expect the pricier unit to win.

- **Kiting flag** (not part of E, used in classification): opponent is ranged,
  subject is melee, and `opponent_speed − subject_speed > −0.15`. Everyone
  expects the melee side to lose these, bonus tables or not.

### Classification — every opponent lands in exactly one category

Thresholds: `WIN_T = 15` (|S| below ⇒ dead even), `B_T = 0.2` (meaningful
bonus), `B_STRONG = 0.45` (dedicated-counter bonus), `E_T = 0.15`.

| Category | Rule | Full-list sort |
|---|---|---|
| `even` | \|S\| ≤ 15 | S desc |
| `expected_win` | win ∧ (B ≥ B_T, or no-bonus with E ≥ 0) | S desc |
| `unexpected_win` | win ∧ (B ≤ −B_T — *they* have the bonus — or no-bonus with E < 0) | B asc, then S asc (biggest enemy bonus, narrowest win first) |
| `expected_counter` | loss ∧ (B ≤ −B_STRONG ∨ kited ∨ E < −E_T); ranged no-bonus losses default here | S asc, then B asc |
| `unexpected_counter` | loss ∧ melee opponent ∧ B > −B_STRONG ∧ E ≥ −E_T (a "safe-on-paper" brawl lost to hidden mechanics: armor strip, charge burst, bleed) | S desc (narrowest loss first) |

### Top-3 pick rules (stricter than list membership)

- `expected_win` picks additionally require B ≥ B_T **and** opponent costs
  gold (no trash — "beats skirmishers" is not video material).
- One pick per unit line (ratha melee/ranged collapse to one).
- **Unique-unit preference**: walking the sorted candidates, a generic staple
  takes a pick slot only if its |S| beats the next unique's by ≥ 15 points
  (`OUTLIER_MARGIN`). Validated: Heavy Camel Rider (+79) legitimately
  displaces Elite Shrivamsha (+60); Halberdier does not displace Ghulam.

### "Why" captions

Template per category citing real numbers, driven by the dominant factor:
bonus value ("+8 vs Cavalry applies"), inverted bonus ("Halberdier's +32 vs
cavalry does not apply — not cavalry"), kiting ("1.05 speed never reaches
them"), hidden mechanic (from ability columns: `armor_strip_per_hit`,
`charge_attack_melee`, `bleed_dps`, …), cost ("45% cheaper per fighting
power"). `why_factors {bonus, rps, cost}` ship in the storyboard for overlay
widgets.

### Validated result (Elite Temple Guard, Muisca — prototype)

Picks: **expected wins** Heavy Camel Rider +79 / Elite Shrivamsha Rider +60 /
Elite Tiger Cavalry +58; **unexpected wins** Elite White Feather Guard +28
(28% HP left) / Elite Huskarl +29 / Elite Ghulam +45; **expected counters**
Elite Chakram Thrower −100 / Grenadier −100 / Elite Chu Ko Nu −100;
**unexpected counters** Elite Urumi Swordsman −25 (charge burst) / Elite
Obuch −42 (armor strip) / Elite Liao Dao −48 (bleed). Full lists: 30
expected wins, 6 unexpected wins, 25 expected counters, 6 unexpected
counters, 9 even. Prototype script: `2026-07-04-unit-analysis-video-prototype.py`
(this directory) — the implementation's constants/rules must match it.

## Part 2 — Storyboard JSON (the machine contract)

```json
{
  "schema_version": 1,
  "build": "170934",
  "subject": {"civ": "Muisca", "slug": "elite_temple_guard_muisca",
               "name": "Elite Temple Guard", "line": "shock_infantry",
               "stats": {"hp": 115, "attack": 16, "melee_armor": 5,
                          "pierce_armor": 6, "speed": 1.05,
                          "cost": {"food": 70, "gold": 45},
                          "bonuses": [{"class": "Cavalry", "amount": 8}]}},
  "generated": {"source": "local_sim", "seeds": 8, "budget_res": 3000,
                 "date": "2026-07-04", "params": {"WIN_T": 15, "B_T": 0.2,
                 "B_STRONG": 0.45, "E_T": 0.15, "OUTLIER_MARGIN": 15,
                 "weights": {"bonus": 0.5, "rps": 0.3, "cost": 0.2}}},
  "segments": [
    {"order": 1, "category": "expected_win", "rank": 1,
     "opponent": {"civ": "Persians", "slug": "heavy_camel", "name": "Heavy Camel Rider"},
     "score": 79.1, "expectation": 0.31, "surprise": 0.49,
     "hp_left": {"subject": 79, "opponent": 0},
     "counts": {"subject": 26, "opponent": 37},
     "why": "…", "why_factors": {"bonus": 0.43, "rps": 0.3, "cost": 0.0}}
  ],
  "category_lists": {
    "expected_win":       [{"rank": 1, "name": "…", "civ": "…", "slug": "…",
                             "score": 81.0, "picked": false}, "…"],
    "unexpected_win":     ["…"], "expected_counter": ["…"],
    "unexpected_counter": ["…"], "even": ["…"]
  },
  "all_results": [{"slug": "…", "civ": "…", "S": 0.0, "E": 0.0,
                    "surprise": 0.0, "category": "…", "factors": {}}]
}
```

- `segments` = the 12 recordings in narrative order: expected wins →
  unexpected wins → expected counters → unexpected counters.
- `category_lists` = the exhaustive rankings (drive the ranked-list cards;
  `even` gets a card but no fights).
- `counts` precomputed so the recorder never re-derives army sizes.
- `all_results` for debugging/tuning without re-simming.

## Part 3 — Video orchestrator (Windows, later)

New: `apps/video/auto/run_unit_analysis_video.py`. Consumes a storyboard.

Video structure:

1. **Intro segment** — hi-res unit image + attack-animation gif + stat card
   (unit panel already exists: `render_card.render_unit_panel`). Gif/hi-res
   are **placeholder hooks**: an `AssetResolver` that returns paths if the
   media dir is configured, else None → composer falls back to static card
   only. (Media lives on the Windows box / Railway bucket `gifs/<slug>.gif`.)
2. Per category: **category banner card** → 3 recorded fights (existing
   `run_matchup()` pipeline) each with banner + "why" caption overlaid →
   **ranked-list card** of the remaining units (from `category_lists`).
3. `even` list card near the end. Optional honorable-mention slot exists in
   the schema (future).
4. Stitch via existing `concat_videos` (stream-copy; new card segments must
   use the same `_x264()`/`_AAC`/48 kHz encode params) + chapters via
   `write_chapters` fed from segment metadata — **never from filenames**.

### Prerequisite fixes & refactors (from the 2026-07-04 pipeline review)

Blocking:
1. **Stale repo-layout paths** — `overlay/overlay_data.py:23` and
   `overlay/results.py:30` resolve repo root as `parents[2]`;
   `auto/build_unique_list.py:28` points at `webapp/aoe2_reference.db`.
   Unify all DB/asset roots in `auto/config.py`. (Un-skip/fix the silent
   test `tests/test_pure.py:283`.)

In scope (serve this feature directly):
2. **Generic queue runner with manifest** — extract the resume-skip +
   per-clip-recovery loop from `run_guecha_sweep.py:144` and the
   list-input + `preflight()` from `batch_matchups.py`; specs carry
   `{civ1, slug1, civ2, slug2, name, label, category, why}`; per-clip
   metadata lives in `out_dir/manifest.json` (chapters/recompose read it, not
   filename regexes). Guecha sweep becomes a thin caller.
3. **`make_live_overlay_video` extra overlay slots** — one
   `extra_overlays=[(png, x, y, t0, t1, fade)]` param for banners/captions in
   the same single-encode filter graph (`overlay/compose.py:405`).
4. **Animated intro helper** — `_card_segment` variant accepting an optional
   gif input (`-stream_loop`/`-ignore_loop`), matching encode params.
5. **New cards** — category banner, "why" caption pill, ranked-list card
   (new `build_*_html` + `render_*` pairs in `render_card.py`).
6. Pure-helper moves so analysis/compose never import the OCR-nav stack:
   `resolve_side`/`equal_resource_counts` out of `orchestrate_matchup.py:93`,
   `log()` out of `record_until_end.py:88`.

Out of scope (noted for a later cleanup pass): legacy compose chain removal
(`make_real_video.py`, `compose.py:625` era, `hud._draw_side`), the
`results.py:148` NotImplementedError stub, naval-list unification.

## Testing

- **Unit tests (Mac, no game):** classification rules against fixture rows
  (each category's boundary: B_T/B_STRONG/E_T/WIN_T edges, kiting predicate,
  speed-override, unique-preference margin, line dedupe); storyboard schema
  round-trip; staple civ picker rejects discount civs.
- **Golden test:** Temple Guard storyboard picks pinned (same 12 given the
  same sim backend + seed set) — catches accidental rule drift.
- **Prototype parity:** implementation re-run must reproduce the validated
  Temple Guard lists above.
- Recording-side changes (queue runner, overlays) get dry-run/`--stitch-only`
  paths testable without the game.

## Decisions log

- Data source: matchup DB when present, local re-sim fallback (user).
- Opponent pool: uniques + generic staples; Heavy Scorpion excluded (user).
- Equal-resources only, budget 3000 (user).
- All 12 matchups recorded in-game (user).
- Buckets keyed on bonus-direction + kiting, not blended-prior surprise
  (user; iterated three times against real Temple Guard output).
- Unique units preferred; generics only as ≥15-pt outliers (user).
- Every unit categorized; non-picked units shown as ranked list after each
  category's fights; five lists incl. "even" (user).
- No per-matchup verdict text on the website — this is video-only content
  (existing SEO/SSR project constraint does not apply here).
