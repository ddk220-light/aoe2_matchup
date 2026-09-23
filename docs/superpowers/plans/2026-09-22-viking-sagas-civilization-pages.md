# Viking Sagas Civilization Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Danes, Saxons, Varangians and the new regional units browsable on civilization pages, with their correct rosters and existing approved game-derived media, without changing simulations or ranking results.

**Architecture:** Extend the current main-branch civilization presentation service with a versioned, civilization-only roster supplement. Preserve the current reference/simulation/ranking databases and their build identities. Both server-rendered HTML and the interactive civilization view consume the same composed payload; new media is served from a small, explicitly selected local static bundle.

**Tech Stack:** Existing Flask/Jinja, Python extraction/stat calculation, JSON, vanilla JavaScript, Pillow media conversion, pytest and Node tests. No new frontend framework, database or external service.

**Spec:** The owner's September 22 requests: plan and review before implementation; update civilization pages first; add three new civilizations, their units and attack GIFs; add Varangian Guards for five civilizations and Mounted Crossbowmen where appropriate; simulations and rankings are separate later work. The follow-up selects main as the eventual destination and requests an isolated, correct starting checkout.

**Owner clarification:** This is sequential delivery of the final presentation, not an interim product state. Do not add missing-ranking labels, coming-soon notices, temporary badges or new pending-state behavior. Rankings will be supplied by the following work; preserve the normal presentation and data fields.

**Execution record (2026-09-22):** Owner approved implementation with “Go for it”.
The approved checklist below is retained as the original plan. Local implementation
now includes the scoped reference/media release, composed page API/SSR and existing
UI media controls. All 56 page routes plus overview/sitemap parity pass; the focused
checks report 58 Python and 5 Node tests passing. Desktop/mobile browser smoke and
individual implementation reviews are complete. Reproduction steps, source-quality
decisions and media inventory are recorded in [runbooks §8](../../architecture/runbooks.md#8-civilization-page-only-reference-release-viking-sagas).
The final review identified two copy defects: detail-page SEO language implied
rankings for unranked new rows, and the Franks' Ordonnance Companies discount
needed an explanation. Local corrections are awaiting scoped re-review, followed
by a renewed outgoing-range review. Merge/push to main and deployment still
require separate explicit approval. No production action has occurred.

## Global Constraints

- Planning only until the owner approves implementation. This document is not authorization to publish.
- Do not merge the whole video branch, update main, deploy, upload production media or write production databases without specific approval.
- Do not change the simulation engine, its roster, Matchup Advisor candidates, unit rankings, golden SQLite files, published ranking JSON or the global current-build pointer.
- Preserve the current main-branch typography, building-grouped civilization layout, mobile cards, SSR, navigation and existing ranking behavior.
- No temporary ranking/simulation status UI or new status flags. Do not invent scores or tiers; retain the existing renderer's ordinary treatment of optional score fields, and allow real values to flow through when supplied.
- Preserve the original checkout and its unrelated uncommitted video work.
- Use current installed game DAT plus shipped CivTechTrees JSON as data sources; record provenance. Patch notes explain changes but are not a replacement for tier availability.
- No new renders, model runs, recordings or whole-library regeneration. Reuse approved game-derived assets. Retention in Git does not itself approve experimental FLUX illustrations for website display.
- Only exact selected source/output paths may be staged. Obtain independent scope review of the entire outgoing range before any later push.
- Only focused unit/route/media tests and a desktop/mobile smoke check; no broad hardening or simulation campaign.

## 1. Verified Git starting point and integration decision

Remote refs fetched on September 22:

| Ref | Tip |
| --- | --- |
| origin/main | 0ce703be6db8c4c54b65578bf61f0255c44cf1a8 |
| origin/staging | 0ce703be6db8c4c54b65578bf61f0255c44cf1a8 |
| origin/codex/video-recorder-v3 | 68e9975840fc8e492fc51bf07edebac12b603fcd |

The video branch has 21 unique commits; main has 483 unique commits relative to it. The two latest commits (68e99758, 3919b315) do not edit website code. Across the entire video-only range, direct website changes are two added sprites (Flaming Camel and Missionary), but there are also shared extraction/stat-calculation changes, recording tooling and a package CLI entry. Therefore "all branch changes have no website impact" is not an adequate merge justification.

The clean Codex-managed worktree is already created:

- Path: `C:/Users/ddk22/.codex/worktrees/civilizations-viking-sagas/aoe2_matchup`
- Branch: `codex/civilizations-viking-sagas`
- Base: exact origin/main tip above; no main merge or push performed.
- Baseline: `D:/miniconda3/python.exe -B -m pytest tests/test_seo_civ_pages.py -q -p no:cacheprovider` -> **8 passed**.

Use this branch for implementation. Read approved source assets from the video branch/checkout, then bring over only the web-ready media needed by this feature. Do not cherry-pick a large asset commit just to obtain a few files. Keep the complete video library and workflows on their existing branch; integrating that branch in full is a separate decision.

Git's worktree model supports this separation: https://git-scm.com/docs/git-worktree . New main changes must be integrated into this feature branch before the eventual reviewed promotion, not replaced by the old branch's website files.

## 2. Product scope and verified availability

Use the existing highest-available Imperial-tier convention, not a new age selector. Retain base and elite media for the five new unit lines so future consumers can reuse both; expose the correct available tier on each civilization card.

| New civilization | Castle unique unit | Imperial card |
| --- | --- | --- |
| Danes | Jomsviking | Elite Jomsviking |
| Saxons | Hearth Troop | Elite Hearth Troop |
| Varangians | Jarl | Elite Jarl |

Varangian Guard is a **Barracks regional unit**, not a Castle unique unit. The installed `CivTechTrees` files mark **Elite Varangian Guard available for all five**: Byzantines, Vikings, Danes, Saxons, Varangians. In particular, the Vikings JSON explicitly marks both nodes 2703 and 2704 `ResearchedCompleted`; abbreviated release-note wording must not be interpreted as a base-tier-only restriction.

Mounted Crossbowmen occupy the **Archery Range mounted-ranged line**, not the Stable cavalry roster:

| Highest available tier | Civilizations |
| --- | --- |
| Heavy Mounted Crossbowman | Britons, Celts, Franks, Poles, Sicilians, Spanish, Teutons, Danes, Saxons, Varangians |
| Mounted Crossbowman | Bohemians, Burgundians, Italians, Portuguese, Vikings |

Remove the replaced Cavalry Archer entries on these civilization pages. Bohemians gain the new line rather than replacing a previously available Cavalry Archer. Do not remove Knights, light cavalry or mounted unique units. Byzantines gain Varangian Guards but retain their mounted-ranged availability unless their shipped tech tree says otherwise.

Sources:

- Official update/build identity and regional changes: https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-185872/
- Official regional-unit overview: https://www.ageofempires.com/news/the-warriors-of-the-viking-sagas/
- Exact inspected availability: `D:/SteamLibrary/steamapps/common/AoE2DE/resources/_common/dat/CivTechTrees/{CIV}.json`.
- Existing media provenance: video-branch `graphics/asset_completion_2026-09-22/asset-manifest.json`, DAT SHA256 `4aa2f0a719e88e5f1502517eddb27c669aeb40c2fe9d8c4f3eec7751c01e7baa`.

### Presentation scope following owner clarification

1. New units use the normal cards with stats, costs, descriptions and media. No temporary labels or placeholders. New-civ descriptions are factual; this phase does not invent simulated strength claims.
2. Preserve existing ranking fields and rendering behavior. The roster/media supplement must not hard-code missing scores or suppress later genuine ranking values. Do not relabel old results as build 185872 results.
3. Render the complete supported military roster for each new civilization, not just its unique unit. Preserve the existing site's military-unit scope, building grouping and Imperial convention.
4. Include Longship availability for all three new civs and the consistent Longboat-to-Longship rename on Vikings' page as reference-only data, reusing existing ship media; do not recompute naval rankings. This is part of the complete new-civ rosters, not an optional omission.
5. No global balance-patch refresh for all old civilizations in this phase. The supplement records exactly which rows were refreshed; unaffected old rows retain their existing data provenance.

## 3. Current architecture and the narrow change boundary

Main already has `apps/website/services/civilizations.py`, `routes/civilizations.py`, `services/catalog.py`, `_civ_content.html` and `static/js/civilization-view.js`. Do not implement against the older video branch's monolithic renderer.

Today civilization names come from `_get_ref_civs()` and are also used by Battle Sim/Advisor validation. Civilization cards come from `load_civ_power_units()`. Adding names to the shared reference DB would expose unsupported simulator/advisor choices. Instead:

- Keep `_get_ref_civs()`, `_valid_civs()`, `/api/ref/civ`, shared `SITE_CATALOG.civilizations`, and all simulation/ranking endpoints unchanged.
- Add a civilization-page-only name list, composed from existing names plus the supplement.
- Add `/api/civilizations/<civ_name>` for the composed presentation; switch only the civilization page loader to it. Leave `/api/civ-power-units` unchanged for its existing consumers.
- Route SSR, overview, sitemap civilization entries and interactive content through the same composition service.
- Keep unit-detail/media viewing usable without calling the simulator. No new temporary simulation-state UI; engine integration and its navigation are handled in the next phase, not implemented here.
- Use dedicated static URLs carried in each new row's `media` object. This avoids depending on the older global Postgres asset catalog, its build identity, or production bucket mutations just to display this phase.

## 4. Files and payload contracts

Create:

- `aoe2x/assets/build_civilization_release.py`: offline builder for the scoped roster/stat/media release. Requires explicit output paths; never overwrites golden databases.
- `apps/website/static/data/civilizations-185872.json`: committed page-only supplement, provenance, row replacements/removals and media URLs.
- `apps/website/static/img/civilizations/185872/{danes,saxons,varangians}.png`: real game emblems, not assumed third-party CDN URLs.
- `apps/website/static/media/civilizations/185872/<unit_slug>/`: only selected usable website derivatives (icon, transparent icon, native red idle sprite, attack WebP).
- `tests/test_civilization_release.py`: supplement/composition/source availability contracts.
- `tests/civilization_media.test.cjs`: explicit media, tap/keyboard animation and existing presentation behavior tests.

Modify narrowly:

- `aoe2x/extract/extract_constants.py`, `extract_units.py`: verified new civ IDs Saxons=60, Varangians=61, Danes=62 (source DAT civ-array positions); new unit ID pairs Mounted Crossbowman=2700/2701, Varangian Guard=2703/2704, Hearth Troop=2705/2706, Jarl=2708/2709, Jomsviking=2711/2712.
- `aoe2x/dbgen/unit_analyzer.py`: optional extraction-directory injection with unchanged default, to reuse existing stat calculations without replacing default data files.
- `apps/website/services/civilizations.py`: supplement load and composition, page-only civilization names.
- `apps/website/routes/civilizations.py`, `apps/website/app.py`: page-only wiring, new API route and civilization sitemap list.
- `apps/website/services/catalog.py`: respect an explicit presentation `building` when grouping page rows; preserve fallback grouping for current rows.
- `apps/website/templates/civ_overview.html`, `civ_detail.html`, `_civ_content.html`: dynamic civilization count, real emblems, correct names/rosters and normal detail interaction.
- `apps/website/static/js/matchup.js`, `civilization-view.js`, `apps/website/static/css/matchup.css`: composed endpoint and media previews; retain current layout and ranking rendering.
- `tests/test_seo_civ_pages.py`: new pages/index/sitemap and no-JavaScript roster coverage.
- `docs/architecture/runbooks.md`: this partial reference-release workflow, clearly distinguished from the full patch/simulation pipeline.

Pure service interfaces:

```python
def load_civilization_supplement(path=None) -> dict:
    """Versioned local JSON, cached using the existing service style."""

def civilization_page_names(reference_names: list[str], supplement: dict) -> list[str]:
    return sorted(set(reference_names) | set(supplement["civilizations"]))

def compose_civilization_analysis(name: str, age: str, baseline: dict | None,
                                  supplement: dict) -> dict:
    """Return a fresh existing-shape analysis; never mutate cached baseline."""
```

Supplement top-level keys: `schema_version` (1), `reference_build` (185872), `published_at` (ISO date recorded when this reference content is finalized), `source_dat_sha256`, `source_tech_tree_sha256` (civ->hash), `civilizations` (civ->record). Each civ record contains `description`, `emblem_url`, `complete_roster` (true only for new civs), `remove_slugs`, `units` (the new/updated rows). Existing-row output still uses `power_units[column][line]` arrays to preserve the renderer. Composition removes each explicitly replaced slug before inserting the new row.

Row extensions: `building`, `reference_build`, `media` (`icon`, `icon_transparent`, `idle`, `idle_blue`, `attack`). Keep the current `unit_name`, `unit_slug`, `line_slug`, `is_unique`, `stats`, `special_effects`, `bonus_abilities` fields. The supplement owns reference/media fields only: it neither supplies nor clears `tier`, `score` or `stat_baseline`. Composition retains those fields from actual ranking rows matched by civilization and unit slug; otherwise they remain absent under the existing optional-field contract. Do not introduce `ranking_status` or `simulation_available`. A description of a triggered ability is not a permanent numerical stat bonus.

## Task 1: Produce a scoped reference/media release

**Interfaces:** Builder accepts installed DAT, CivTechTrees directory, approved source-assets directory and explicit output directory. It produces the supplement above and exactly its referenced media files.

- [ ] Add focused tests for the five Varangian Guard grants, 15 Mounted Crossbowman grants, ten Heavy tiers, Bohemian addition and the three new unique units. Use small fixtures copied from shipped tech-tree nodes, including `NotAvailable` nodes, so unavailable upgrade cards cannot slip in.
- [ ] Run the new tests and confirm they fail before adding the builder.
- [ ] Add extraction input injection: `UnitAnalyzer(extracted_dir=None)` stores `self.extracted_dir`, defaulting to current `OUTPUT_DIR`; its loaders read that directory. Extend known extracted identities only with verified game IDs.
- [ ] Extract into ignored `data/local/generated/civilizations-185872/extracted/` using existing `extract_all(dat_path, output_dir)`. Do not invoke `patch_pipeline`, `generate_main_db`, ranking derivation, or default-output reference generation.
- [ ] Build availability from shipped tech-tree nodes (`Use Type == Unit`, `Node Status != NotAvailable`) and their upgrade links. Keep the highest available tier in the current military-unit categories. For each selected top-tier node, feed an explicit unit configuration to the existing stat calculator:

```python
unit_config = {
    "base_id": node["Node ID"],
    "display_name": node["Name"],
    "unit_class": analyzer.get_unit(node["Node ID"])["class"],
    "upgrades": [],
}
result = analyzer.calculate_unit_stats_for_civ(civ_name, unit_config, max_age=4)
```

- [ ] Use the existing extraction field `class` (written by `extract_unit_data`) for that lookup. Treat a selected node missing from extracted units as an explicit release-build failure, rather than silently dropping part of a new civ's roster. Correct only a demonstrated blocker to displayed new-unit stats, with a focused test. A combat-engine implementation is not part of this task.
- [ ] New-civ complete rosters and the specific changed existing-civ rows get fresh reference stats. Include affected upgrade/bonus descriptions (e.g. Cranequins) and explain conditional effects; do not invent an always-active maximum for building-count or formation bonuses.
- [ ] Give Longship and Elite Longship explicit page-only media aliases to existing Longboat and Elite Longboat assets. Keep the engine's old slugs and global icon-name mappings unchanged; do not rely on looking up a new display name in a legacy display-name-keyed catalog. Test that all four civ pages retain a visible ship icon after the rename.
- [ ] Read the ten unit folders at source revision 68e99758: mounted_crossbowman, heavy_mounted_crossbowman, varangian_guard, elite_varangian_guard, hearth_troop, elite_hearth_troop, jarl, elite_jarl, jomsviking, elite_jomsviking. Reuse `icon.png`, `icon_transparent.png`, approved dat4x red/blue idle PNGs and attack GIFs. Convert attack GIFs to animated WebP preserving transparency, frame timing and loop behavior. Do not use experimental artwork or redo upscaling.

  Implementation source inspection supersedes the planned idle selection: DAT4x/UltraSharp idle files show severe streaks; native `_idle_dir06.png` files are clean. Reuse the native idle. No clean blue source was found, so omit the blue derivative and its media control rather than label red as blue or ship corrupted images. Preserve original source-library files unchanged. Attack assets require their own visual check. A top-level media map retains usable assets for all ten base/elite forms without adding unavailable roster tiers.
- [ ] Copy actual installed game emblems for the three new civs. Record source and output paths in the supplement/build report. Do not rely on unverified external CDN availability for new emblems.
- [ ] Validate output references and animation frame counts; inspect one of each new unit line visually. Scratch and full extracted game JSON remain ignored; commit only the scoped supplement, exact web derivatives and reusable builder.

Example acceptance test:

```python
def test_regional_reference_row(release):
    row = next(u for u in release["civilizations"]["Vikings"]["units"]
               if u["unit_slug"] == "elite_varangian_guard")
    assert row["building"] == "barracks"
    assert row["is_unique"] is False
    assert "score" not in row and "tier" not in row
    assert "ranking_status" not in row
    assert row["media"]["attack"].endswith(".webp")
```

Run: `python -m pytest tests/test_civilization_release.py -q`.

## Task 2: Compose civilization-only data without exposing unfinished simulations

**Interfaces:** Consume the supplement contract and existing analysis dict; produce the same `power_units` shape plus reference/media fields, with no new status contract.

- [ ] Write composition tests for an existing unaffected civ, an affected old civ, and each new civ. Prove the input dict is unchanged after composition. Supply a real-shaped scored row for a new unit in a test and prove composition preserves its tier/score instead of masking it; no ranking calculation is required.
- [ ] Implement composition using a deep copy of baseline analysis. For new civs start with empty column maps and the reference description. Delete replaced Cavalry Archer slugs, then insert rows under their appropriate columns/lines. Set explicit building values: Guard -> barracks, Crossbowman -> archery_range, new unique -> castle.
- [ ] Update overview/detail to use page-only names and the composed analysis. Add the new read-only endpoint inside the civilization blueprint; validate against this page-only name list and the existing Imperial age policy.
- [ ] Change only civilization sitemap entries to use page names; preserve Advisor/versus sitemap generation and global engine validators. Use the supplement's recorded publication date for affected civilization-page lastmod, not the old rankings generation date; leave other sitemap entries unchanged.
- [ ] Keep the existing power-unit endpoint and published files untouched. Avoid claiming a new global release in `/api/release`.

```python
def test_new_civ_is_page_only(client):
    assert client.get("/civilizations/danes").status_code == 200
    assert client.get("/api/civilizations/Danes").status_code == 200
    assert client.get("/api/ref/civ/Danes").status_code == 400
    assert b"/civilizations/danes</loc>" in client.get("/sitemap.xml").data
```

Run: `python -m pytest tests/test_civilization_release.py tests/test_seo_civ_pages.py -q`.

## Task 3: Preserve the current UI and expose the correct media

**Interfaces:** Both `_civ_content.html` and `civilization-view.js` consume the composed analysis. The new rows' direct static media URLs override legacy helpers only for those rows.

- [ ] Add route/render tests for unit names, emblems, explicit buildings and media details in server-rendered HTML. Assert no new temporary ranking/simulation status copy is introduced.
- [ ] Change `matchup.js` selection from `/api/civ-power-units/` to `/api/civilizations/`. Continue using the existing cancellable data loader and SSR bootstrap.
- [ ] In Jinja and JS, prefer `unit.media.idle` / `unit.media.icon` when present; otherwise keep the existing global helpers. Prefer the supplied civilization emblem URL for new civs.
- [ ] Keep stats/ability text in the existing tooltip/detail interaction; add the new rows' post-discount costs from `stats.cost_food`, `stats.cost_wood`, `stats.cost_gold` using the existing resource icons, omitting zero resources. Provide an explicit Attack preview that works with hover, tap and keyboard; use the row's attack WebP directly rather than depending on the global bucket catalog. Keep icon/transparent-icon and idle media accessible in that same detail area without a new top-level gallery page.
- [ ] Reuse existing tier/score rendering exactly: genuine values render normally, absent optional values do not produce invented ranks, placeholder labels or new badges. Do not add coming-soon messages or ranking-state controls.
- [ ] Unit-card media/detail interaction stays on the civilization page and needs no engine call. Preserve existing navigation; do not add simulator support or a separate temporary navigation state in this phase.
- [ ] Derive the civilization count from data. Retain current building cards, page structure and mobile layout without an interim-state redesign.

```javascript
function civilizationUnitMedia(unit, name) {
    return {
        idle: unit.media?.idle || spriteFor(name) || getIconUrl(name),
        attack: unit.media?.attack || animFor(name),
    };
}
```

Run: `node --test tests/civilization_media.test.cjs` and the two focused Python files above. Assert new cards use their media URLs without new status copy, and a supplied score still renders through the normal path. Test positive food/wood/gold cost values, omitted zero costs, and the page-only ship media aliases.

## Task 4: Focused verification, plan review and eventual publication

- [ ] Preview all three new civ pages, Vikings, Byzantines, one Heavy Crossbowman civ, Bohemians and one unaffected civ. Check initial SSR plus interactive switching, desktop plus phone-width layout, attack animation and static fallback. No simulation reruns.
- [ ] Verify all 56 civilization URLs return 200; overview/sitemap list the same set; new engine/Advisor choices remain absent. Confirm replaced Cavalry Archers are absent only in the intended civilization presentation rows.
- [ ] Verify no changes in golden SQLite files, rankings JSON, engine files or the current build pointer. Compare original and feature worktree status so concurrent video work remains separate.
- [ ] Record the partial reference-release process and approved asset source revision in the runbook. Explicitly state this is not the full patch pipeline.
- [ ] Stage exact source, test, doc, JSON and media paths. Review changed paths and binary sizes against this plan; do not stage the entire graphics tree or unrelated branch commits.
- [ ] Obtain independent review of implementation and full proposed outgoing commit range against current origin/main; resolve scoped defects.
- [ ] Present the local preview and request specific approval to merge/push to main and deploy. Main is the intended destination, not a grant to deploy during planning. If live main advances, integrate it on this feature branch and rerun the focused smoke check before renewed outgoing-range review.

## Planning review record

- Self-review: scope covers new civ index/detail pages, complete military rosters, exact regional tiers, media access, replaced mounted-archer rows, main-based isolation and no simulation/ranking publication.
- Shared-consumer boundaries: separate page-only names/API, immutable ranking baseline composition, no default golden rebuild, no global release bump, local static media independent of production asset-catalog writes.
- Owner clarification incorporated: no interim status presentation or new status flags; preserve the existing UI and accept the real ranking rows from the subsequent phase without masking them. No blocking implementation question remains. Complete new-civ military rosters include their Longships; no naval ranking refresh is implied.
- Independent read-only review (`civilization_plan_review`) identified four actionable clarifications: make Longships consistent with complete rosters, spell out new cost rendering, alias renamed ship media explicitly, and use extracted `class` rather than `unit_class`. All four are incorporated above. No implementation or publication was performed during review.
