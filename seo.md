# SEO & AI-Discoverability — Recommendations

Audit of how well [aoe2matchup.com](https://aoe2matchup.com) can be crawled and
indexed by Google Search and AI sources (Gemini, ChatGPT, etc.), with concrete
code changes. Status reflects work on branch
`claude/website-search-discoverability-3d98lj` (merged to `main`).

---

## TL;DR

The HTML-level SEO is already in good shape. The two things actually holding
back discoverability are **(1) off-site registration** (Search Console / Bing —
manual, see bottom) and **(2) the main content pages render entirely in
JavaScript**, which Gemini and most AI crawlers cannot execute. Fix #2 and the
site's unique data (rankings, civ breakdowns) becomes visible to AI sources.

---

## ✅ Already implemented (this branch)

- **Search-engine verification meta tags** — `GOOGLE_SITE_VERIFICATION` /
  `BING_SITE_VERIFICATION` env vars inject `<meta name="google-site-verification">`
  and `<meta name="msvalidate.01">` (`app.py` `inject_site_url`, `base.html`).
- **Richer `sitemap.xml`** — `<lastmod>`/`<changefreq>`/`<priority>`, plus the
  `/patches` and `/replay` hubs (`app.py` `sitemap_xml`).
- **De-orphaned `/vs/` landing pages** — each now cross-links ~12 sibling
  matchups (`_related_matchups`), forming a crawlable internal-link graph
  instead of being reachable only via the sitemap.
- **Rich-snippet hints** — `max-image-preview:large, max-snippet:-1` on the
  robots meta.

---

## 🔴 Priority 1 — Server-render the JS-only content (biggest win)

**Problem.** `/units` (Rankings), `/civilizations`, and `/matchup-advisor` ship
an empty `<div id="...">` that JavaScript fills on the client. Googlebot can
render JS (delayed, unreliably); **Gemini and most AI crawlers do not execute JS
at all** — so the site's most valuable, unique data is invisible to exactly the
AI sources we want to appear in.

**Recommended changes (in priority order):**

1. **Civilizations page (cheapest — data is already server-side).**
   `civ_overview.html` already receives `{{ civs | tojson }}`. Render a
   server-side `<ul>`/`<section>` per civ (name, power units, one-line identity)
   *inside `{% block content %}`*, then let the existing JS progressively enhance
   it. Even a static, crawlable list of all 53 civs + their key units is a huge
   gain for AI answers like "best Aztec units in AoE2".

2. **Rankings page (`/units`).** Currently fetches everything via
   `rankings.js`. Add a server-rendered baseline table (top units per class from
   `derived_data.db` / `pool_scores.db`) in the template, then hydrate. The JS
   toggles (Pop/Cost/Average) can stay client-side; the *default view* must exist
   in the initial HTML.

3. **Matchup Advisor.** Render at least the civ-selection grid and a static
   intro server-side; the recommendation engine can stay interactive.

4. **`<noscript>` fallback** as a cheaper interim: emit the key facts (and links
   to the server-rendered `/vs/` pages) inside `<noscript>` on each JS page.
   Lower quality than true SSR but trivial to add.

**Acceptance check:** `curl https://aoe2matchup.com/civilizations | grep -i
"Aztecs"` should return the civ's data in raw HTML (no JS).

---

## 🟠 Priority 2 — Structured data & internal hubs

1. **`ItemList` JSON-LD on `/units`** — mark up the ranked unit table so Google
   can surface it as a list/rich result.

2. **`BreadcrumbList` JSON-LD** on `/vs/`, civ, and patch pages — improves SERP
   appearance and helps crawlers understand hierarchy.

3. **Add a `/matchups` HTML hub page** — a real, paginated/curated index linking
   into the `/vs/` landing pages, then link it from the footer + nav. This gives
   the ~3,000 landing pages a permanent crawl entry point (the per-page
   cross-links added this branch help, but a top-level hub is stronger) and is a
   keyword-rich page in its own right ("AoE2 unit matchups").

4. **`Dataset` / `SoftwareApplication` enrichment** — the existing
   `WebApplication` JSON-LD could add `aggregateRating`, `featureList`, and
   `screenshot` to qualify for richer cards.

---

## 🟡 Priority 3 — Sitemap & coverage

1. **Broaden matchup coverage.** `_matchup_seed_pairs()` only emits
   unique-vs-unique pairs. Add high-volume generic matchups people actually
   search (knight vs pikeman, archer vs skirmisher, etc.) — these are the
   highest-traffic long-tail queries.

2. **Add patch pages to the sitemap.** `/patches/<build>/<civ>/<unit>` pages
   exist but aren't listed. Enumerate them from `patches.db`.

3. **Split the sitemap** if it grows past ~50k URLs / 50 MB — use a sitemap
   index (`<sitemapindex>`) per the spec.

4. **Real `lastmod` per page** — drive matchup-page `lastmod` from the data
   build/patch date rather than "today", so crawlers don't see every URL change
   daily (which erodes trust in the signal).

---

## 🟢 Priority 4 — Content, semantics, performance

1. **Unique title/description per `/vs/` page** is done; extend the same care to
   adding a short, server-rendered **verdict sentence** ("In a 30v30 sim, X beats
   Y") on each landing page — that is exactly the snippet AI sources quote.
2. **Image `alt` text** on unit/civ icons (accessibility + image SEO).
3. **Core Web Vitals** — defer non-critical JS, preconnect to the fonts origin
   (`fonts.googleapis.com`/`fonts.gstatic.com`), and self-host or `font-display:
   swap` (already set) to cut LCP.
4. **`<h1>`/heading hierarchy** — confirm each page has exactly one `<h1>` and
   logical `<h2>`s (most do).

---

## Manual / off-site actions (cannot be done in code — do these first)

These are almost certainly the real reason the site isn't appearing yet:

1. **Google Search Console** — add `aoe2matchup.com`, submit
   `https://aoe2matchup.com/sitemap.xml`, and "Request Indexing" on top URLs.
   You may be able to verify instantly via the existing GA tag
   (`G-MYNEW08LBR`) if it's the same Google account; otherwise set
   `GOOGLE_SITE_VERIFICATION` in Railway (meta tag support shipped this branch).
2. **Bing Webmaster Tools** — submit the sitemap. Bing feeds ChatGPT; Google's
   index feeds Gemini.
3. **Backlinks / authority** — new sites rank slowly until linked. Post to
   r/aoe2, AoE Discords, aoe2techtree community, etc. A few real backlinks often
   matter more than any meta tag.
4. **Confirm `SITE_URL`** env var is `https://aoe2matchup.com` in production so
   canonicals/sitemap emit the right host.
