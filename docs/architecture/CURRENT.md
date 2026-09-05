# Website architecture — September 2026

Flask, SQLite and the shared V3 JavaScript engine remain in place. This cleanup
changes boundaries, not simulation rules, published scores, URLs or visual design.

## Ownership

| Concern | Owner | Contract |
| --- | --- | --- |
| Reference statistics and rosters | `data/golden/aoe2_reference.db`, `aoe2x/dbgen/` | Generated, civilization/age-specific stats; never modify at request time. |
| V3 mechanics | Validated runtime profiles in the reference database; `services/mechanics.py` | Direct V3 loading; legacy combat-dict responses remain compatibility adapters. |
| Active engine | `aoe2x/js_simulation/src/` | Shared by browser worker and Node. |
| Published rankings | `data/golden/derived_data.db` and `derived_data_v3.metadata.json` | Frozen published values; no browser recomputation. |
| Ranking methodology | `aoe2x/rank/ranking_methods.json` -> serving builder -> published metadata | Opponents, settings, weights, normalization and source engine ship with scores. Historical categories remain labeled. |
| Historical features | Existing advisor, patch and replay databases/modules | Retained; not implicitly regenerated or migrated to V3. |
| Read-only access | `aoe2x/storage.py`; website DB configuration in `app.py` | URI `mode=ro` and `query_only`; generation tools own writes. |
| Application services | `apps/website/services/` | Battle construction, mechanics, ranking reads, civilization analysis, catalog, SEO and release identity. |
| Feature routes | `apps/website/routes/` | Battle/civilization blueprints adapt services to HTTP; `app.py` remains composition and other compatibility routes. |
| Catalog | `aoe2x/assets/presentation.json`, `services/catalog.py` | One icon/building catalog and reference-derived civilization roster; old global helpers are adapters. |

No database layouts were changed or databases regenerated. Live captures,
calibration evidence and hidden Advisor/Patch implementations are preserved.

## Frontend boundaries

- `simulate.js`: composition, roster controls and options wiring.
- `battle/selection.js`: team state and option serialization.
- `shared/api.js`: HTTP errors, timeouts, cancellation and latest-request tickets.
- `battle/worker-session.js`: owns one worker and rejects older-run messages.
- `battle/playback.js`: selecting, loading, playing, paused, completed and failed
  states, snapshot playback and renderer integration.
- `battle/statistics.js`: matchup explanations and live team cards.
- `shared/catalog.js`: explicit catalog imports for the battle page.
- `shared/page-data.js`: bootstrap/cache access and stale selection rejection.
- `matchup.js` / `civilization-view.js`: civilization controller / presentation.
- `rankings.js` / `rankings-view.js`: ranking controller/table / hover presentation.
- `rankings_score_method.js`: renders published methodology, not a second model.

Roster edits and army-option changes invalidate the old config. Starting a run
cancels stale requests and workers. Pause preserves the run; restart requests a
new randomized seed. Rendering retains approved sprites, scales, projectiles and
responsive CSS. Physics is not changed to fit outcomes.

This is an incremental extraction, not a rewrite: classic-script helpers and
legacy endpoints remain where older pages consume them. Migrate callers before
removing adapters. `static/js/engine/` is retained legacy code, not the active
`aoe2x/js_simulation/src/` engine.

## Crawlers and deployment

Civilization detail routes render descriptions and grouped units from the same
analysis service used by the API. `CIV_ANALYSIS` bootstraps the interactive page
without an extra request; JavaScript enhances/replaces the same container. The
removed all-civilizations summary stays removed. Civilization navigation remains
real canonical links. Ranking and matchup landing SSR is preserved.

Sitemap entries come from valid route/database sources, are deduplicated, and
exclude API/query variants and aliases. Dates use recorded data revisions or patch
release dates, never filesystem mtimes; unknown dates are omitted. Preserve
canonical metadata, structured data, 404s and permanent redirects.

Set `SITE_URL` to the production canonical origin. Set `SEARCH_INDEXING=false` on
staging and `true` on production explicitly. Without an override, only the canonical
host in a production environment is indexable. Staging sends HTML noindex metadata
and `X-Robots-Tag: noindex, nofollow`. Assets remain crawlable: blocking all robots
would prevent crawlers from seeing noindex. See `.env.example`.

`/api/release` exposes portable game/reference, mechanics-schema, engine-source
and published-ranking identities. Engine hashes normalize line endings and avoid
machine paths. `aoe2x/rank/build_v3_serving_db.py` emits ranking methodology alongside
the serving database; do not silently replace published metadata with draft text.

## Maintenance and release gate

1. Edit the owning module; preserve external response shapes with adapters.
2. Run the deployment suite in `.github/workflows/ci.yml`. CI labels website,
   active V3, frontend integration and retained legacy contracts separately.
3. `tests/test_architecture_baseline.py` pins six API digests and five small seeded
   battles: melee, ranged, siege, dismount and buffer. Structural refactors must
   preserve config, event and final-state hashes and published ranking values.
   Change these contracts only with an intentional reviewed engine/data release.
4. Run `tests/browser/architecture-smoke.cjs` locally and on staging. Install
   Playwright and its Chrome channel in a development environment, or point
   `PLAYWRIGHT_MODULE` to an existing installation. `QA_URL` selects the server.
   Screenshots are ignored under `.scratch/architecture-qa/`; inspect them too.
5. SEO tests cover every civilization's initial HTML, sitemap coverage/uniqueness,
   invalid routes and environment policy. Browser smoke covers laptop/mobile
   pages, play/pause/resume, randomized restart, selection changes and no-JS SSR.
6. Commit code, docs and necessary portable metadata only; never experiment
   recordings, matchup snapshots or generated screenshots.
7. Push incremental staging commits; check CI/deployment and request review.
   Promote to main only after approval, retaining production DB configuration and
   checking production indexing after promotion.

Other architecture documents describe earlier engines/data pipelines and retained
features. This document takes precedence for the current web/V3 integration.
Do not bulk regenerate historical data to perform a website refactor.
