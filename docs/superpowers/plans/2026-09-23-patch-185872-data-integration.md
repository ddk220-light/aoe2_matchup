# Patch 185872 data integration implementation plan

> **For agentic workers:** Use superpowers:executing-plans for the data pipeline; independently audit the new mechanics and existing-civilization deltas. Checkboxes track the bounded work.

**Goal:** Produce a local, reproducible 56-civilization data candidate with current stats, upgrades, costs and sourced special-effect records, before simulation validation.

**Architecture:** Extend the existing DAT extraction, UnitAnalyzer and reference/main SQLite generators. Read the installed CivTechTrees alongside the DAT to resolve regional availability. Generate into ignored `data/local/generated/patch-185872/`, preserving the shipped golden databases and rankings for comparison.

**Tech stack:** Existing Python, genieutils-py 0.1.2, SQLite and pytest.

**Spec:** Owner's September 23 request in the current task: integrate the latest data and new civilizations/units; explain stat/upgrade/bonus/cost changes, distinguishing mechanical reassignment from net gameplay changes; simulation checks against E-drive recordings come afterward.

## Global constraints

- No website, copy, asset, production, ranking or simulation changes in this phase.
- No publication; local feature branch only. Preserve the dirty primary checkout.
- Keep the existing Imperial-only database convention and stable old unit slugs.
- Keep conditional bonuses separate from unconditional stats; do not invent a building count, wounded HP, formation size or combat duration.
- Preserve installed game files and all external-drive recordings.
- Generated candidates, extraction outputs and large audit files belong in ignored storage.
- The owner has already requested execution; routine internal implementation does not require duplicate approval. Ask only about a material new choice or scope expansion.

## Review focus

- Regional replacements must not leave both old and new cavalry-archer lines available.
- A base-stat reduction plus a broader civilization bonus may leave final stats unchanged (Teutons).
- Internal technology names can be stale; effect commands, not those labels, determine numbers.
- Conditional and secondary attacks must not be silently folded into ordinary attack/armor/cost.
- Candidate generation must not overwrite shipped stats or mix new stats with old ranking results.

### Task 1: Existing-pipeline roster and availability

**Files:** `aoe2x/extract/{run,extract_effects,extract_units}.py`, `aoe2x/dbgen/{config_units,config_constants,unit_analyzer}.py`, focused patch tests.

**Consumes:** Installed DAT and `CivTechTrees/*.json` for build185872.
**Produces:** Existing eight extracted JSON files enriched with resolved tree evidence; normal configs for the new regional/unique units.

- [x] Write and run focused tests showing regional availability and tier gates currently fail.
- [x] Merge resolved tree node availability into the extracted civ records and analyzer, including unavailable techs and upgrade triggers.
- [x] Register Mounted Crossbowmen, Varangian Guards, Hearth Troops, Jarls, Jomsvikings and regional ships using actual IDs/upgrades.
- [x] Remove confirmed stale patch rules; test calculated results rather than source text.
- [x] Run only the patch tests and directly affected data-pipeline checks.

### Task 2: Candidate generation and effect recording

**Files:** Existing reference/main generators; a data-only patch preparation entry point; focused generation tests.

**Consumes:** Task1 extracted data and existing golden reference as a read-only baseline.
**Produces:** Separate candidate reference/main databases, provenance manifest and sourced effect audit.

- [x] Add explicit input/output paths to existing generator entry points where absent; preserve default behavior.
- [x] Generate fully upgraded reference rows and stat/tech audit chains using current inputs.
- [x] Record applicable new effects with exact tech/effect IDs and conditional requirements; distinguish recorded definitions from simulation support.
- [x] Build the normal flat stats DB from that reference without touching ranking databases.
- [x] Check all 56 civs, the regional replacement sets, new unique units, costs and known no-net-change cases.

### Task 3: Explain changes and hand off to simulation validation

**Files:** `docs/patches/185872-data-integration.md`; ignored machine-readable audit outputs.

**Consumes:** Candidate/baseline rows keyed by civilization, stable unit slug and age; raw effect evidence.
**Produces:** Full local diff and concise human report of real changes, reassigned bonuses and outstanding engine work.

- [x] Compare base, final, upgrade and effect values; report added/removed rosters separately from changed stats.
- [x] Trace Elite Teutonic Knight armor explicitly and document conditional assumptions without choosing simulation conditions.
- [x] Locate relevant E-drive recordings read-only for the next phase; do not run battles yet.
- [x] Obtain an independent whole-change scope/correctness review and resolve material findings.
- [x] Report candidate paths, verification results and remaining simulation work. Do not push or deploy.

## Execution record

- Baseline: `e9b07348`, shipped reference972 Imperial rows /53 civilizations.
- Installed DAT SHA256: `4aa2f0a719e88e5f1502517eddb27c669aeb40c2fe9d8c4f3eec7751c01e7baa`; matches prior page-only extraction provenance.
- Local branch: `codex/patch-185872-data-integration` in the existing clean isolated worktree.
- Completed candidate: 1030 Imperial rows /56 civilizations;73 added,15 removed,200 changed. Both SQLite integrity checks returned `ok`; flat available rows match the reference.
- Tests:27 focused checks passed; new behaviors observed failing before their fixes. No simulations or broad test suites run.
- Independent review `/root/patch185872_final_review`: no Critical/Important findings; data candidate ready, not runtime/production ready.
- Ruling: conditional bonuses remain sourced definitions without selected simulation conditions; otherwise an arbitrary building count/formation would contaminate the cost/stat baseline.
- Ruling: preserve the inherited upgrade-cost aggregate definition; raw unit-tier research costs are separately captured. Consequence: the old aggregate is not a full unit-tier research budget.
- Ruling: defer two old tree-filename aliases after review found no patch result difference, and leave the existing transform-boolean warning unchanged. These limitations are disclosed in the integration report; neither is a newly introduced failure.
- Report: `docs/patches/185872-data-integration.md`. Generated artifacts stay ignored. No push or deployment.
