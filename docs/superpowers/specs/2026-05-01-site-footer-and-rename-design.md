# Site footer + rename to "AoE2 Matchup"

**Date:** 2026-05-01
**Status:** Design approved, awaiting implementation plan

## Goal

Add a professional, SEO-friendly footer to every page of the webapp, and rename the user-visible site name from "AoE2 Unit Analyzer" / "AoE2 Analyzer" to **"AoE2 Matchup"**. The footer surfaces sources/credits, social links, a contact form, a legal disclaimer, and reinforces internal linking for SEO.

## Non-goals

- Renaming Python modules, the Git repo, the SQLite databases, route paths, or environment variables. Only user-visible strings change.
- Building a `/contact` page, a newsletter signup, a sitemap link, or anything else not enumerated below.
- Changing the navigation bar's structure or links — only the brand text inside it.

## Decisions

- **Contact form mechanism:** Formspree (third-party). No backend route, no SMTP credentials.
- **Contact form location:** Modal/popup, triggered from a "Contact" button in the footer's Connect column.
- **Sources to credit:** `genieutils-py`, `aoe2techtree.net`, AoE2 Wiki (Fandom). All three are clickable external links.
- **Layout:** Four-column grid on desktop, single stacked column on mobile (≤640px).
- **Copyright owner:** "AoE2 Matchup" (site name, not personal name).
- **Microsoft / Forgotten Empires disclaimer:** required, in the bottom legal strip.
- **Spirit of the Law / GitHub repo / newsletter:** explicitly excluded.

## Architecture

### New partial template

`webapp/templates/_footer.html` is a new Jinja partial containing:

1. The four-column footer markup.
2. The contact modal markup (hidden by default).
3. An inline `<script>` for modal open/close + Formspree submit (no new JS file, no new dependency).

It is included once, near the bottom of `webapp/templates/base.html`, immediately before `</body>` (after `{% block content %}` but before existing trailing `<script>` blocks). Because every page extends `base.html` (verified — all 6 templates do), the footer ships site-wide automatically.

### Footer structure (desktop)

```
┌──────────────────────────────────────────────────────────────────────┐
│  AoE2 Matchup           Explore           Sources           Connect  │
│  [hex SVG logo]         Battle Sim        genieutils-py↗    Discord ↗│
│  Free fan tool for      Matchup Advisor   aoe2techtree.net↗ YouTube ↗│
│  Age of Empires II:DE   Rankings          AoE2 Wiki↗        Instagram↗│
│  matchup analysis.      Civilizations                       Contact  │
│  All 50 civs, fully                                                  │
│  upgraded.                                                           │
│                                                                       │
│  ─────────────────────────────────────────────────────────────────── │
│  © 2026 AoE2 Matchup ·  Age of Empires II is a trademark of Microsoft│
│  Corporation. This site is not affiliated with or endorsed by        │
│  Microsoft, Forgotten Empires, or World's Edge.                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Column 1 — Brand**
- Reuse the existing hex/shield SVG from `.nav-brand-icon` in `base.html`.
- Site name "AoE2 Matchup" in the existing brand font (Cinzel).
- Tagline (one short sentence): "Free fan tool for Age of Empires II:DE matchup analysis. All 50 civs, fully upgraded."

**Column 2 — Explore (internal links)**
- `Battle Sim` → `/`
- `Matchup Advisor` → `/matchup-advisor`
- `Rankings` → `/units`
- `Civilizations` → `/civilizations`

**Column 3 — Sources (external links)**
- `genieutils-py` → `https://github.com/Tapsa/genieutils` (or the actual repo used; URL to be confirmed in implementation)
- `aoe2techtree.net` → `https://aoe2techtree.net`
- `AoE2 Wiki` → `https://ageofempires.fandom.com/wiki/Age_of_Empires_Series_Wiki`

All Sources links: `target="_blank" rel="nofollow noopener"` and a small external-link arrow glyph (↗) to indicate off-site navigation.

**Column 4 — Connect**
- Discord, YouTube, Instagram: small inline-SVG platform icons + label, `target="_blank" rel="noopener"`.
  - The YouTube link additionally carries `rel="me noopener"` to support `rel="me"` profile verification.
  - Each icon link has an `aria-label` (e.g., `aria-label="AoE2 Matchup on Discord"`) since the SVG provides no accessible text.
- "Contact" button: `<button type="button">` styled to match the link list, opens the contact modal.

**Bottom legal strip**
- Single horizontal rule above (subtle, theme-aware).
- Copyright on the left, disclaimer on the right (or wrapping below on narrow viewports).
- Smaller font (~0.85em), muted color via existing CSS variables.

### Mobile (≤640px)

- Columns stack vertically in order: Brand → Explore → Sources → Connect → Legal strip.
- Column headings stay visible.
- Tagline and disclaimer remain full-width.
- Touch targets ≥44px tall on links.

### Contact modal

- **Trigger:** click on the "Contact" button in Column 4.
- **Markup:** semantic `<dialog>` element if browser support is acceptable; otherwise a `<div role="dialog" aria-modal="true" aria-labelledby="...">` with a backdrop `<div>`.
- **Behavior:**
  - Click on backdrop closes modal.
  - `Esc` key closes modal.
  - Focus is moved to the first input on open and trapped inside the dialog.
  - Focus returns to the "Contact" button on close.
- **Fields:**
  - `Name` — `<input type="text" name="name">`, optional.
  - `Email` — `<input type="email" name="email" required>`.
  - `Message` — `<textarea name="message" required minlength="10">`.
  - Honeypot — `<input type="text" name="_gotcha" style="display:none" tabindex="-1" autocomplete="off">` (Formspree convention).
- **Submission:** async fetch
  ```js
  fetch(endpoint, {
      method: 'POST',
      body: new FormData(form),
      headers: { 'Accept': 'application/json' }
  })
  ```
  - On 2xx: replace form body with a "Thanks — I'll get back to you." success message; close button stays visible.
  - On non-2xx: show inline error "Something went wrong. Please email us instead at <fallback>." (fallback address TBD by user during implementation; if none, omit the email reference and just say "please try again later").
  - Disable submit button while in flight; show loading state.
- **Endpoint configuration:** the Formspree URL is **not hardcoded** in templates. `app.py` registers a `@app.context_processor` that exposes `contact_form_endpoint` to all templates by reading the `CONTACT_FORM_ENDPOINT` env var. If the env var is unset, the variable is `None` and the contact button is hidden / disabled (so a misconfigured deploy doesn't render a broken form).

### Site-wide rename

Files where the user-visible string `"AoE2 Unit Analyzer"` or `"AoE2 Analyzer"` is replaced with `"AoE2 Matchup"`:

- `webapp/templates/base.html`:
  - Default `<title>` block content.
  - Default `meta description` block content (rewrite to mention "AoE2 Matchup").
  - `og:site_name` content.
  - JSON-LD `name` field.
  - Nav brand text inside `.nav-brand` (currently "AoE2 Analyzer").
- Any other template that hardcodes the old name in headings, footers, or JSON-LD overrides — to be enumerated by grep during implementation.

The browser favicon, logo SVG, and color palette remain unchanged.

### SEO additions

These are additive changes attached to the rename, not a separate effort:

1. **`sameAs` in JSON-LD** — extend the existing `WebApplication` JSON-LD in `base.html` with a `sameAs` array listing the Discord, YouTube, and Instagram profile URLs. Tells search engines those social profiles belong to this entity. Implemented as a Jinja `set` of URLs in `base.html` so the same array can also drive the footer Connect column (single source of truth).

2. **`rel` attributes** — Sources column links use `rel="nofollow noopener"`, social links use `rel="noopener"` (with `rel="me noopener"` on at least one).

3. **`aria-label` on icon-only links** — accessibility + a small SEO benefit since search engines index aria-labels.

4. **Microsoft disclaimer text** — disambiguates the site from official Microsoft properties for both users and crawlers.

### CSS approach

Footer styles append to `webapp/static/css/base.css` (the existing global stylesheet — confirmed it exists and is loaded by `base.html`). Use existing CSS custom properties for theme-awareness (light/dark) so no new variables are needed unless an existing one is missing for the footer surface color, in which case add one.

The contact modal also uses the existing color tokens. The modal's z-index must clear the navbar (current navbar z-index to be confirmed in implementation).

No new fonts. No external CSS or JS dependencies.

## Files touched

| File | Change |
|---|---|
| `webapp/templates/_footer.html` | **NEW** — footer markup, contact modal markup, modal JS |
| `webapp/templates/base.html` | Include `_footer.html`; rewrite title / meta description / og:site_name / JSON-LD `name` / nav-brand text to "AoE2 Matchup"; add `sameAs` JSON-LD array; define social-URL Jinja vars |
| `webapp/static/css/base.css` | Append `.site-footer`, `.contact-modal`, mobile breakpoint rules |
| `webapp/app.py` | Add a `@app.context_processor` exposing `contact_form_endpoint`, `social_discord_url`, `social_youtube_url`, `social_instagram_url` from env vars |
| Other templates (`index.html`, `simulate.html`, `civ_detail.html`, `matchup_advisor.html`, `matchup_landing.html`, `deprecated-civ.html`) | Search-and-replace any hardcoded "AoE2 Unit Analyzer" / "AoE2 Analyzer" strings |
| `README.md` | Document the new env vars: `CONTACT_FORM_ENDPOINT`, `SOCIAL_DISCORD_URL`, `SOCIAL_YOUTUBE_URL`, `SOCIAL_INSTAGRAM_URL` |

No DB migrations. No new routes. No new Python or JS dependencies. No changes to `analysis/`, `extraction/`, or any sim code.

## Configuration

Env vars to set on Railway (and locally for dev):

| Variable | Purpose | If unset |
|---|---|---|
| `CONTACT_FORM_ENDPOINT` | Formspree URL (e.g., `https://formspree.io/f/xxxxxxxx`) | Contact button is hidden |
| `SOCIAL_DISCORD_URL` | Public Discord invite | Discord link is hidden |
| `SOCIAL_YOUTUBE_URL` | YouTube channel URL | YouTube link is hidden |
| `SOCIAL_INSTAGRAM_URL` | Instagram profile URL | Instagram link is hidden |

Any social link whose env var is unset is omitted from both the footer Connect column and the JSON-LD `sameAs` array. The footer still renders cleanly with zero social links if all are unset.

## Open questions resolved during implementation

These are items the implementation plan needs concrete values for, but they don't block this design:

1. The exact Formspree endpoint (user creates the Formspree form and sets the env var).
2. The exact social URLs (user provides; set via env vars).
3. The genieutils-py repo URL — confirm whether the project uses `Tapsa/genieutils` or a Python wrapper / fork.
4. A fallback contact email for the modal's error state (optional).
5. Whether any other template hardcodes "AoE2 Unit Analyzer" / "AoE2 Analyzer" beyond `base.html` (grep during implementation).

## Risks

- **Formspree free tier limit (50 submissions/month).** Acceptable for a hobby site. If exceeded, swap the endpoint for any drop-in replacement (Tally, Web3Forms, etc.) — the modal's submit code is provider-agnostic.
- **Theming regression.** Adding new CSS to `base.css` could conflict with existing rules. Mitigated by namespacing under `.site-footer` and `.contact-modal` and using existing CSS vars.
- **Layout regression on existing pages.** A long footer pushed onto pages with already-tall content could affect existing scroll behavior. Mitigated by the footer being a normal block-flow element with no sticky/fixed positioning.

## Success criteria

- Footer renders correctly on all 6 templates in both light and dark themes.
- Footer collapses to a single-column stack at ≤640px viewport.
- Contact modal opens, submits to Formspree, shows success state, closes via Esc/backdrop, traps focus.
- Contact button is hidden when `CONTACT_FORM_ENDPOINT` env var is unset.
- Each unset social env var hides the corresponding link without breaking the layout.
- Page title, OG tags, and JSON-LD all show "AoE2 Matchup" — verified via View Source on at least the home page and one detail page.
- No regressions in existing page styling, navbar behavior, or theme toggle.
- Lighthouse SEO score on the home page is unchanged or improved after deploy.
