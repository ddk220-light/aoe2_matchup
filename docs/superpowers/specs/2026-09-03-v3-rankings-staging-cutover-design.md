# Simulation V3 Unit Rankings Staging Cutover — Design

**Status:** Approved architecture, ready for implementation planning.

**Target:** Staging only. This design does not authorize a production database
write, a push to `main`, or a production deployment.

## Goal

Make the Simulation V3 campaign results the source of truth for the land-unit
rankings that the current V3 campaign covers, while preserving the current
retail sources for Siege, Naval, and Matchup Advisor candidate selection.

The staging rankings experience will expose one cost-based score only. The old
equal-unit-count and averaged ranking scales, and the `pool_scores.db` UI path
that supports them, will be removed from the rankings page. Civilization power
unit rankings will use the same V3-backed artifact as the main rankings table.

The work starts from the current `origin/staging` tip so the V3 battle page and
other staging-only UI changes remain intact.

## Non-goals

- Do not replace Matchup Advisor candidate selection yet.
- Do not generate the full 22,650-battle advisor corpus in this change.
- Do not replace retail Siege or Naval ranking semantics.
- Do not publish the new V3 Mangonel combat score yet.
- Do not change AoE2 unit/reference data or the current game build number.
- Do not redesign unrelated staging pages.
- Do not deploy to production or push/merge to `main`.

## Source data

The input campaign is the local Simulation V3 rankings database:

`data/local/v3_unit_rankings.db`

The accepted campaign snapshot has:

- 755 Imperial-age civilization/unit variants across the covered ranking lines;
- 4,530 matchups, exactly six ranking yardsticks per variant;
- 22,650 runs, exactly five seeded runs per matchup;
- 15,855 score rows, exactly 21 score metrics per variant;
- zero campaign failures and zero orphaned unit/reference joins;
- resource weights of food `1`, wood `1`, and gold `1`;
- a maximum army size of 27 units;
- engine revision `96c9404dc3f2bb5b6f617d1e640142d7d7836acf`;
- mechanics build
  `ce3530df36cf0b333a9751cb0ff94460fe904f811feecec8ae9794701622b4cf`.

The five runs remain independent observations. A matchup score uses their
campaign aggregate; run-level remaining HP, elapsed duration, survivors,
winner, timeout, and winner-flip evidence stays in the local campaign database
for auditability and is not copied into the serving schema.

## Published artifact

Create a new committed serving database:

`data/golden/derived_data_v3.db`

It uses the existing `derived_data.db` schema, including the `build_number`
field and uniqueness rules. It is a separate file because the V3 corpus is
intentionally incomplete for advisor use; changing rows in the existing retail
database would make that boundary implicit and unsafe.

All published rows use build number `177723`, the current AoE2 data build.
Simulation-engine identity is not encoded as a fake game build number.

Add a sidecar manifest:

`data/golden/derived_data_v3.metadata.json`

The manifest records at least:

- source campaign path and generation timestamp;
- game build number;
- engine revision and mechanics-build hash;
- seed count, yardstick count, resource weights, and unit cap;
- V3-covered score types and retained retail score types;
- source retail database/build used for the copied Siege and Naval rows;
- validation counts.

The sidecar preserves provenance without changing the serving database schema.

## Hybrid data assembly

Build `derived_data_v3.db` from two explicit sources for build `177723`:

1. V3 campaign scores for covered Infantry, Archery, and Stable lines.
2. Retail `derived_data.db` rows for Siege and Naval.

Do not begin with a blind copy of every retail row and overwrite selected rows.
Assemble an explicit allowlist of score types so an unreviewed retail land score
cannot silently survive in the V3 artifact.

### V3 score selection

For each covered Imperial civilization/unit variant, publish the campaign's
final score for its ranking family:

| Ranking family | V3 final metric |
| --- | --- |
| Infantry | `militia_value` |
| Archery | `ranged_effectiveness` |
| Stable | `stable_effectiveness` |

The family metric is selected from the unit-line classification, not inferred
from which numeric column happens to be present. The resulting row retains the
unit's concrete `line_slug`, civilization, unit slug, age, rank, score, and
current game build in the existing `battle_scores` shape.

Supporting V3 role scores used by the rankings breakdown are also copied from
the campaign using their existing score-type names. The six yardstick values
shown in the breakdown come from the same V3 campaign snapshot; they must not
be recomputed from retail battles or from `pool_scores.db`.

### Retained retail score selection

Copy only the rows needed to preserve the current published semantics:

- Siege: `anti_building_score` and the score rows the existing Siege table
  consumes.
- Naval: `naval_effectiveness` and the score rows the existing Naval table
  consumes.

V3 `v3_combat_effectiveness` Mangonel data is intentionally omitted from the
serving artifact until Siege is explicitly migrated. The UI presents the
hybrid table uniformly and does not add "legacy" badges or labels.

### Rank derivation

Ranks are derived within the same partitions currently expected by the site:
line, age, score type, and game build. Ties use the current deterministic
ordering convention. Every published partition must have contiguous ranks
starting at one and no duplicate civilization/unit/score/build key.

## Consumer routing

Database selection is explicit by product surface:

| Consumer | Database after this change |
| --- | --- |
| Main unit rankings API/page | `derived_data_v3.db` |
| SEO unit-line pages | `derived_data_v3.db` |
| Civilization power unit ranking generation | `derived_data_v3.db` |
| Civilization page/API power-unit loading | `civ_power_units/<build>.json` generated from V3 |
| Matchup Advisor candidate selection | existing `derived_data.db` plus frozen `advisor_power_units/<build>.json` |
| Siege ranking rows | retained retail rows inside `derived_data_v3.db` |
| Naval ranking rows | retained retail rows inside `derived_data_v3.db` |

The advisor boundary must be represented by a separately named legacy/retail
database loader or path. It must not depend on a global `DERIVED_DB_PATH` that
is changed for rankings, because that would switch candidate selection as an
accidental side effect.

Both advisor entry points also collect their candidate roster and opponent
strengths from the power-unit JSON. They therefore load a separately named,
frozen retail snapshot rather than the regenerated V3 civilization-page
artifact. This keeps advisor behavior unchanged until the complete V3 matchup
corpus is ready.

Civilization power units stop preferring `pool_scores.db` percentiles for land
families. They use the same final V3 family scores and partitions as the unit
rankings page. Siege and Naval continue to resolve through the retained retail
rows in the V3 serving artifact.

## Rankings API and score semantics

`/api/ref/unit-line/<slug>` returns a single final score per row for the selected
line. It uses an explicit line-family-to-final-metric mapping rather than the
current generic first-match score-key fallback. This avoids a supporting metric
such as `general_combat` becoming the visible rank merely because it appears
earlier in a tuple.

The response may include one structured V3 breakdown for expandable detail:

- the family/role aggregates already produced by the V3 campaign;
- the six yardstick matchup scores;
- raw unit stats already shown by the current table.

No `pool_scores` payload, scale name, equal-count score, or average-of-scales
score is required for V3 land ranking rows.

## Rankings UI

The table remains visually uniform across Infantry, Archery, Stable, Siege,
and Naval. Source differences are an implementation detail, not a label in the
rankings UI.

Remove:

- the Pop / Cost / Average scale selector;
- client-side scale state and scale switching;
- columns whose only purpose is comparing the retired scales;
- rankings-page reads from `pool_scores.db`.

Use this compact default layout:

| Column | Meaning |
| --- | --- |
| Rank | Rank within the selected line/family partition |
| Civ | Civilization icon and name |
| Unit | Unit icon and name |
| Line | Concrete line on aggregate family views; omitted when redundant |
| V3 Score | Final cost-based family score for land; existing final score for Siege/Naval |
| Δ Line | Difference from the selected line's median score |
| Cost | Food + wood + gold with all resources weighted 1:1:1 |
| Special | Existing concise unique-effect/missing-tech presentation |

The header/help copy calls the land score "cost-based" or "equal resources."
It must not call the score "3K," because army size comes from relative cost and
the 27-unit cap rather than a fixed 3,000-resource budget.

One compact Breakdown disclosure may expose the existing GC/AC/AT/AA-style
role scores and six V3 yardsticks. Raw combat stats may remain behind the
existing Special/stat expansion. The default view should stay compact.

Siege and Naval render with the same table shell and interaction style. Their
score labels use neutral language (`Score`) where a `V3 Score` label would be
factually inaccurate.

CSV export mirrors the visible single-score model and removes the retired scale
columns. Breakdown fields may be exported as separately named columns when
present; Siege/Naval cells without those fields remain empty.

## Build pipeline

Add one deterministic local build command that:

1. reads `data/local/v3_unit_rankings.db`;
2. reads build `177723` from `data/golden/derived_data.db` for the retained
   Siege/Naval score allowlist;
3. creates a fresh temporary `derived_data_v3.db` with the existing schema;
4. writes selected V3 and retained retail rows;
5. derives and validates ranks;
6. writes the metadata sidecar;
7. atomically replaces the committed golden V3 artifact only after validation.

The command is a data-build step, not an application startup migration. Staging
serves the committed artifact exactly as production currently serves the golden
retail databases.

## Validation gates

The artifact is eligible for staging only when all of these checks pass:

- V3 source has zero campaign failures.
- Each covered variant has exactly six expected yardsticks.
- Each V3 matchup has exactly five runs.
- Source-to-reference joins have zero missing civilization/unit variants.
- Published V3 variant counts match the accepted campaign snapshot.
- Published score types match the explicit V3 and retail allowlists.
- Every ranking partition is complete, unique, and contiguously ranked.
- Game build is `177723` for every row.
- The metadata engine revision and mechanics hash match the source campaign.
- Siege/Naval retained row counts and values match retail build `177723`.
- Matchup Advisor candidate queries still open the retail `derived_data.db`.
- Rankings, SEO line pages, and civilization power data open
  `derived_data_v3.db`.
- The rankings page has no Pop/Cost/Average control and makes no
  `pool_scores.db` request/read.

Proportionate smoke coverage includes one representative line from each V3
family, the Jaguar Warrior row used for the original spike, one Siege line, one
Naval line, one civilization power-unit response, and one advisor candidate
selection response.

## Staging integration and release

Implementation is performed on `codex/v3-rankings-staging`, created from the
current `origin/staging` commit. This makes the staging V3 battle-page work and
other staging-only changes part of the base rather than merge-conflict fallout.

After implementation and validation:

1. review the feature diff against `origin/staging`;
2. bring in any newer `origin/staging` commits if the branch moved;
3. re-run the targeted data, application, JavaScript, and smoke checks;
4. merge the feature branch into local `staging` without discarding staging
   history;
5. push `staging` to `origin/staging`.

The staging push is the only remote mutation in scope. Any later merge to
`main`, production deploy, or production database change requires a new,
explicit user approval for that exact action.

## Rollback

The change is isolated by artifact and consumer routing. A staging rollback is
the revert of the cutover commit(s), which restores rankings and civilization
power consumers to `derived_data.db` and the current `pool_scores.db` UI. The
retail database is never overwritten, so Matchup Advisor and the rollback path
retain their original data throughout.
