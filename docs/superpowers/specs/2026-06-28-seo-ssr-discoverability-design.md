# SEO / SSR / AI-Discoverability — Complete Overhaul Design

**Date:** 2026-06-28
**Status:** Design — pending user review
**Branch target:** `staging`
**Supersedes the "fast pass" framing in [`seo.md`](../../../seo.md)** — that doc's audit is correct, but this spec commits to the *complete* job, not the interim. `seo.md` stays as the original audit/reference.

---

## 1. Goal

Google Search Console verification is live and crawling **now**. The site's unique value — a battle simulator, unit rankings, per-civ breakdowns, a matchup advisor, and a replay analyzer covering all 53 civilizations — is currently locked behind client-side JavaScript, so crawlers and (critically) AI sources that don't execute JS (Gemini, ChatGPT) see near-empty pages.

**Make every public page fully understandable to a crawler or an AI from raw HTML alone**, without degrading the polished JS/visual experience humans get. A crawler landing cold should be able to answer: *what is this site, what does each tool do, where does the data come from, and what are the actual numbers/verdicts.*

This is the **complete** version: every public page server-rendered with its real data, every page described in plain language, full structured data, a clean sitemap, and a site-wide "what this is and how it works" content layer. Phased, not rushed.

## 2. Non-goals

- No visual redesign of the human-facing UI. SSR content is progressively enhanced by the existing JS; the rendered experience is unchanged or better.
- No new simulation/data pipelines. We expose data that already exists in the committed DBs.
- No keyword stuffing or filler prose. Descriptive copy must be genuinely useful to a human reader; that is also what AI sources quote.
- No off-site work in code (backlinks, Bing submission) — tracked as manual actions in `seo.md`, out of scope for this spec.

## 3. Design principles

1. **Progressive enhancement, one source of truth.** The server renders real, semantic HTML data. The existing JS enhances it in place or replaces it on load. We do **not** maintain a second parallel copy of the data or its formatting logic — data-fetch logic is factored into shared helpers that both the JSON API routes and the page routes call.
2. **Hydration contract (per page):** SSR content is rendered *inside* the container the JS targets. On load, the page's JS either (a) replaces the container's contents (the common `innerHTML = …` case — SSR content naturally disappears), or (b) where the JS appends, we add an explicit "clear SSR" step keyed off a `data-ssr` marker. Each page's JS is audited for which case applies. If JS fails to load, the SSR content remains as a usable, crawlable fallback — never a blank page.
3. **Concise framing, real data.** Each tool page gets a short (2–4 sentence) intro describing what it shows and how to read it, plus the actual data. Long-form "methodology / how it works" content lives in one dedicated place (the About/methodology layer) and is linked, not duplicated per page.
4. **Structured data mirrors visible content.** Every JSON-LD block describes content that is actually present in the rendered HTML (no markup for invisible data — that's a structured-data violation).
5. **Honest crawl signals.** `lastmod` reflects real data/build dates, not "today". Canonicals and the sitemap emit the production host.

## 4. Architecture

### 4.1 Shared SSR data helpers (`app.py`)

Extract the data-assembly logic currently embedded in the JSON API routes into plain functions so page routes can render the same data server-side:

- `get_unit_line_data(line_slug)` — factored out of `api_ref_unit_line` ([app.py:1121](../../../apps/website/app.py)). Returns the ranked, score-attached unit rows for a line. `api_ref_unit_line` becomes a thin `jsonify(get_unit_line_data(...))`; the `/units` page route calls it to render the default-view table.
- `get_civ_overview_data()` — wraps `load_civ_power_units(current_build())` + the civ list (`_get_ref_civs`) + each civ's one-line identity, returning a per-civ structure for SSR. `/api/civ-power-units/<civ>` and `/civilizations` both consume it.
- Reuse existing single-call loaders where they already exist (`load_civ_power_units`, `load_pool_scores`) — no new query duplication.

**Rule (extends the CLAUDE.md cross-file sync rules):** a page's server-rendered data and its JSON API MUST derive from the same helper. No copy of formatting/scoring logic in a template.

### 4.2 Per-civ identity text

The civ pages need a one-line strategic identity per civ ("Aztecs — aggressive infantry & monks, no cavalry…"). **Decision:** introduce a single committed data file `data/golden/civ_identity.json` (one sentence per civ × 53) as the source of truth, *unless* Phase 2's investigation finds a suitable existing field in the ref DB — in which case prefer that and skip the new file. This is the only net-new content corpus; everything else renders existing data.

### 4.3 Descriptive content layer ("understanding" layer)

A small set of reusable, server-rendered descriptive blocks so a crawler/AI understands the project as a whole:

- **Site-level methodology** — one authoritative explanation: data extracted from the AoE2:DE `.dat`, fully-upgraded Imperial stats for 53 civs, ~500k pre-simulated matchups, what a "score" means, what each sim count (30v30 / cost-parity) means. **Decision:** the full version lives on a dedicated `/about` (methodology) page linked site-wide from the footer; a condensed 2–3 sentence summary sits on the homepage's lower fold and links to `/about`. One authoritative source, one short pointer — no duplication.
- **Per-tool intros** — 2–4 sentences each, in each page's `{% block content %}`.

## 5. Per-page plan (every public surface)

| Page | Route | SSR content added | Descriptive copy | Structured data |
|---|---|---|---|---|
| Battle Sim (home) | `/`, `/simulate` | Crawlable intro + featured/popular matchup links + what the simulator does; canvas stays JS | Yes — flagship "what is this site" + methodology fold | `WebApplication` (enriched: featureList, screenshot) + `BreadcrumbList` |
| Rankings | `/units` | Default "Average" baseline table (top units per pool) as real `<table>`; JS keeps Pop/Cost/Average toggles | Yes — what the score means, how to read it | `ItemList` of ranked units |
| Civilizations | `/civilizations` | All 53 civs as `<section>`s: name, power units, one-line identity | Yes — what the page shows | `ItemList` of civs |
| Matchup Advisor | `/matchup-advisor` | Civ-selection grid + static intro; recommendation engine stays interactive | Yes — what it recommends and how | `WebApplication`/`BreadcrumbList` |
| Replay Analyzer | `/replay` | Descriptive section: what it analyzes (build order, military timeline, APM, eco), how to upload/use; SPA stays JS | Yes — full tool description (no data to render) | `SoftwareApplication` + `HowTo` |
| Patch tracker hub | `/patches` | Already SSR (summary_html); enrich + cross-link to per-patch pages | Yes — what patch tracking shows | `ItemList` / `BreadcrumbList` |
| Per-patch landing *(new)* | `/patches/<build>` | **The page that serves "AoE2 new patch" searches.** Full server-rendered notes for one update: title, release date, complete unit/civ change list, links into per-unit pages | Yes — "Age of Empires II Update `<build>` — balance changes & patch notes" | `NewsArticle` (`datePublished`=release_date) + `BreadcrumbList` |
| Patch unit page | `/patches/<build>/<civ>/<unit>` | Server-rendered stat-delta summary for that unit across the patch | Yes — verdict sentence ("Buffed/Nerfed in <build>: …") | `BreadcrumbList` |
| Matchup landing | `/vs/<a>/<ua>/<b>/<ub>` | Server-rendered verdict sentence ("In a 30v30 sim, X beats Y …") + existing related-matchup links | Already has title/desc; add verdict | `BreadcrumbList` (extends existing JSON-LD) |
| Matchups hub *(new)* | `/matchups` | Real, curated/paginated index into the `/vs/` pages; linked from footer + nav | Yes — "AoE2 unit matchups" keyword page | `CollectionPage` / `ItemList` |
| About / methodology *(new)* | `/about` | Full server-rendered methodology + project description; linked from footer site-wide | Yes — authoritative "what this is & how it works" | `AboutPage` |
| Redirect aliases | `/civ`, `/civ/<n>`, `/civilizations/<n>` | Keep 301s (no change) | — | — |

**Coverage expansion for `/vs/`:** broaden `_matchup_seed_pairs()` beyond unique-vs-unique to include high-traffic generic matchups (knight vs pikeman, archer vs skirmisher, etc.) — the highest-volume long-tail search queries. New pairs flow into the sitemap and the `/matchups` hub.

## 6. Sitemap, robots, crawl hygiene

1. Drive each URL's `lastmod` from the real data/patch build date (or git mtime of the underlying artifact), not "today".
2. Add `/matchups` hub, `/about`, every `/patches/<build>` per-patch page, and all `/patches/<build>/<civ>/<unit>` pages (enumerated from `patches.db`) to the sitemap. Per-patch `lastmod` = the patch `release_date`.
3. Add a `<sitemapindex>` split **only if** total URLs cross ~50k / 50 MB.
4. Confirm `SITE_URL` / canonical host is `https://aoe2matchup.com` in production (already wired via `inject_site_url`; verify in deploy).

## 7. Structured data (JSON-LD) summary

- Enrich the existing site-wide `WebApplication` ([base.html:40](../../../apps/website/templates/base.html)) with `featureList`, `screenshot`, and `aggregateRating` only if a real rating source exists (else omit — no fake ratings).
- Add `ItemList` (rankings, civs, matchups hub), `BreadcrumbList` (vs / civ / patch / advisor), `SoftwareApplication` + `HowTo` (replay), `CollectionPage` (matchups hub), `NewsArticle` (per-patch landing pages, `datePublished`=release_date — the freshness signal for "new patch" queries), `AboutPage` (`/about`).
- All blocks validated against the rendered HTML they describe.

## 8. Phasing

Ordered so the live crawler sees real content fastest, lowest-risk first. Every phase ends green (tests pass, smoke-tested) and is independently shippable to `staging`.

- **Phase 0 — Zero-risk additive wins** (no interactive render paths touched): real `lastmod`; fonts `preconnect`; `alt` text on unit/civ icons; single-`<h1>` audit; `/vs/` verdict sentence + `BreadcrumbList`; `/matchups` hub page + footer/nav link; sitemap adds (hub + patch pages).
- **Phase 1 — Shared SSR helpers**: extract `get_unit_line_data`, `get_civ_overview_data`; API routes become thin wrappers; add tests pinning API output unchanged.
- **Phase 2 — Civilizations SSR** + per-civ identity corpus + `ItemList`.
- **Phase 3 — Rankings SSR** (default table) + score-explainer copy + `ItemList`.
- **Phase 4 — Matchup Advisor SSR** (grid + intro).
- **Phase 5 — Replay Analyzer description** + `SoftwareApplication`/`HowTo`.
- **Phase 6 — Patch tracker** — add the new `/patches/<build>` per-patch landing page (the "AoE2 new patch" target) with `NewsArticle`/`datePublished`, enrich the `/patches` hub + per-unit pages, link them together, and add every patch URL to the sitemap. High priority within the run: patch queries are high-volume and time-sensitive.
- **Phase 7 — Homepage flagship content + methodology/About layer** + `WebApplication` enrichment + final site-wide crawl audit.
- **Phase 8 — `/vs/` coverage expansion** (generic high-traffic pairs) — last because it enlarges the sitemap and benefits from all prior verdict/SSR work.

## 9. Testing & acceptance

- **Real crawlable-content checks** (replace `seo.md`'s flawed `grep "Aztecs"`, which matches the inline `<script>const CIVS=` JSON today). Each check must assert the data appears in **rendered markup outside `<script>` tags** — e.g. an HTML-stripped fetch still contains "Aztecs" and its power units; the rankings table `<td>`s contain unit names; a `/vs/` page contains the verdict sentence.
- Add `pytest` cases hitting each page route and asserting key strings + JSON-LD validity in the response body.
- Existing API-output tests pin that the helper refactor (Phase 1) doesn't change JSON responses.
- Per-page: JS still hydrates correctly (manual/preview smoke test — no duplicated or doubled content; SSR fallback survives JS-disabled).
- Each phase: full `pytest` green before commit; regenerate `.golden/baseline.json` only if sim behavior changes (it won't here).

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| SSR table + JS table drift | Single shared helper (§4.1); API-parity tests (Phase 1). |
| Double-render / content flash on hydrate | Per-page hydration contract (§3.2); `data-ssr` marker + clear where JS appends. |
| Fake `aggregateRating` → structured-data penalty | Only emit ratings if a real source exists; otherwise omit. |
| Sitemap `lastmod` churn erodes trust | Drive from real build/patch dates. |
| `/vs/` expansion bloats sitemap | Phase 8 last; sitemap-index split if >50k. |
| Server render cost per request | Reuse already-loaded DBs/caches; SSR the *default* view only, not all toggle states. |

## 11. Cross-file sync notes (per CLAUDE.md)

- New shared helpers add a sync rule: page SSR ↔ JSON API derive from the same function.
- `UNIT_LINES` JS copy (`static/js/rankings.js`) ↔ Python (`aoe2x/sim/unit_lines.py`) — unchanged, but rankings SSR reads the Python source; do not fork.
- Frontend constants stay in `static/js/constants.js` only.
- Any new committed data file (e.g. `civ_identity.json`) is a deployment artifact — regenerate → commit on `staging` → smoke-test → promote.
