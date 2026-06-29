# SEO Phase 3 — Replay Analyzer Description Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `/replay` real crawlable, user-facing text describing what the Replay Analyzer does (today it's a zero-text full-screen iframe), so crawlers/AI understand the tool and users get context. Add `SoftwareApplication` + `HowTo` structured data.

**Architecture:** The replay viewer is a client-side SPA embedded via `<iframe src="/replay/index.html">`. We don't touch the SPA. We change `replay.html` from a locked full-screen iframe into a normal scrollable page: a server-rendered description + factual feature list ABOVE the embedded viewer, the viewer at a generous fixed height below, and a short "how to use" section. The viewer stays fully functional; deep-link param forwarding (`?match=&profile=&t=`) is preserved.

**Tech Stack:** Flask, Jinja2, pytest. No SPA/JS-tool changes; `replay.html` template + its page CSS only.

**Key design decision — scrollable page, not locked full-screen.** Today `replay.html` sets `html,body { overflow:hidden }` and JS-sizes the iframe to fill the viewport, leaving no room for crawlable text. We convert it to a standard scrollable page: description on top, viewer embedded at `min(78vh, 760px)`, how-to below. This is the only way to surface the descriptive text the goal requires; the trade-off is the viewer is embedded rather than edge-to-edge full-screen (still large and fully usable). **Flag for the user — this changes the replay page from immersive full-screen to a described, embedded tool.**

**Feature facts (from the codebase, for accurate copy — no marketing fluff):** parses `.aoe2record` files (upload or fetch by match/player from the AoE2 Companion API); isometric map playback with player-colored, auto-classified unit sprites (infantry/cavalry/archer/siege/monk/ship/villager), terrain, resources, buildings, walls; build-order & tech timeline; military/eco/APM and production trackers; playback controls (play/pause/step, 1×–16× speed, scrub, zoom/pan); deep-link sharing with timestamp; one-click WebM highlight-clip export of the biggest engagement; save/load processed replays.

**Replay-disabled note:** when `REPLAY_ENABLED` is false the route returns `replay_disabled.html` (503). This plan only touches `replay.html` (the enabled page). Tests must tolerate the disabled case (skip if `/replay` returns 503).

**Test command:** `.venv/bin/python -m pytest tests/test_seo_phase3.py -v` (from repo root). NOTE: in THIS environment `mgz` is missing so `REPLAY_ENABLED` is false and `/replay` returns 503 — the tests below are written to skip gracefully, and the implementer must ALSO verify the enabled-path HTML by rendering the template directly (Step shown in Task 1).

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `apps/website/templates/replay.html` | Modify | Description + feature list section, scrollable layout, embedded viewer, `SoftwareApplication`+`HowTo` JSON-LD. |
| `tests/test_seo_phase3.py` | Create | Phase 3 tests (skip when replay disabled; plus a direct-render test). |

---

## Task 1: Description + feature list + scrollable layout

**Files:**
- Modify: `apps/website/templates/replay.html`
- Test: `tests/test_seo_phase3.py`

- [ ] **Step 1: Read the current `replay.html`** to see its exact `page_css`, `content` (the `#replay-host` + `<iframe>`), and `page_js` (iframe sizing) blocks. You will adapt these blocks.

- [ ] **Step 2: Write the failing test.** Create `tests/test_seo_phase3.py`:

```python
import pytest


def _replay_html(client):
    """Return the rendered enabled-path replay.html, or skip if disabled here."""
    import app
    if not getattr(app, "REPLAY_ENABLED", False):
        # Render the enabled template directly so we can test it even when the
        # mgz-gated blueprint failed to load in this environment.
        with app.app.test_request_context("/replay"):
            from flask import render_template
            return render_template("replay.html", active_nav="replay", replay_qs="")
    return client.get("/replay").data.decode()


def test_replay_describes_the_tool(client):
    body = _replay_html(client)
    # Crawlable feature text is present (not just an empty iframe).
    assert "Replay Analyzer" in body
    assert "build order" in body.lower()
    assert "webm" in body.lower() or "clip" in body.lower()
    # The embedded viewer iframe is still there.
    assert "/replay/index.html" in body


def test_replay_softwareapplication_jsonld(client):
    body = _replay_html(client)
    assert '"@type": "SoftwareApplication"' in body
    assert '"@type": "HowTo"' in body
```

- [ ] **Step 3: Run — FAIL** (no feature text / JSON-LD yet).

- [ ] **Step 4: Implement.** Edit `apps/website/templates/replay.html`:

  **(a)** In `{% block page_css %}`, REMOVE the full-screen lock. Replace any `html, body { overflow: hidden; ... }` rule and fixed-viewport iframe sizing with a scrollable layout:

```css
.replay-page { max-width: 1200px; margin: 0 auto; padding: 20px 16px 64px; }
.replay-intro h1 { font-family: 'Cinzel', serif; color: var(--gold); font-size: 1.8rem; margin: 4px 0 8px; }
.replay-intro p { color: var(--text-muted); max-width: 820px; line-height: 1.6; margin: 0 0 14px; }
.replay-features { list-style: none; padding: 0; margin: 0 0 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 6px 18px; }
.replay-features li { font-size: 0.92rem; padding-left: 18px; position: relative; }
.replay-features li::before { content: "▸"; color: var(--gold); position: absolute; left: 0; }
#replay-host { width: 100%; height: min(78vh, 760px); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
#replay-frame { width: 100%; height: 100%; border: 0; display: block; }
.replay-howto { margin-top: 24px; color: var(--text-muted); font-size: 0.92rem; line-height: 1.6; max-width: 820px; }
.replay-howto h2 { font-family: 'Cinzel', serif; color: var(--gold); font-size: 1.2rem; }
```

  **(b)** Replace the `{% block content %}` with a described, scrollable layout (preserve the iframe `src` with `replay_qs`):

```html
{% block content %}
<main class="replay-page">
  <div class="replay-intro">
    <h1>AoE2 Replay Analyzer</h1>
    <p>
      Watch any Age of Empires II match play back on an isometric map — every unit
      auto-classified and player-coloured, with the full build order, tech timeline,
      and army movements reconstructed from the recorded game. Upload an
      <code>.aoe2record</code> file or pull a match straight from a player's recent games.
    </p>
    <ul class="replay-features">
      <li>Isometric playback with classified unit sprites, terrain, resources & buildings</li>
      <li>Full build-order and technology timeline</li>
      <li>Military, economy, APM and production trackers</li>
      <li>Play/pause, step, 1×–16× speed, scrub, zoom &amp; pan</li>
      <li>Search players & load matches from the AoE2 Companion API</li>
      <li>One-click WebM highlight clip of the biggest engagement</li>
      <li>Deep-link sharing to an exact match and timestamp</li>
    </ul>
  </div>

  <div id="replay-host">
    <iframe id="replay-frame" title="AoE2 Replay Analyzer" src="/replay/index.html{{ replay_qs }}"></iframe>
  </div>

  <section class="replay-howto">
    <h2>How to use it</h2>
    <ol>
      <li>Click <strong>Upload</strong> and choose an <code>.aoe2record</code> file, or search a player and pick a recent match.</li>
      <li>Press play (or <kbd>Space</kbd>) to watch the game; scrub the timeline or change speed to focus on key fights.</li>
      <li>Hit <strong>Export clip</strong> to generate a shareable WebM of the biggest engagement.</li>
    </ol>
  </section>
</main>
{% endblock %}
```

  **(c)** In `{% block page_js %}`, REMOVE the JS that force-sizes the iframe to the viewport (the CSS `height: min(78vh, 760px)` on `#replay-host` now handles sizing). Keep any deep-link/param logic if present; delete only the viewport-fill resizer.

- [ ] **Step 5: Run — PASS.** Then full suite: `.venv/bin/python -m pytest -q`.

- [ ] **Step 6: Commit**

```bash
git add apps/website/templates/replay.html tests/test_seo_phase3.py
git commit -m "feat(seo): describe the Replay Analyzer with crawlable text + embedded viewer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `SoftwareApplication` + `HowTo` JSON-LD

**Files:**
- Modify: `apps/website/templates/replay.html` (override `{% block structured_data %}`)
- Test: covered by `test_replay_softwareapplication_jsonld` (Task 1)

- [ ] **Step 1:** The Task 1 test `test_replay_softwareapplication_jsonld` already asserts both blocks — it currently FAILS. Add a `{% block structured_data %}` override near the top of `replay.html` (after the `{% block meta_description %}` line):

```html
{% block structured_data %}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "AoE2 Replay Analyzer",
  "applicationCategory": "GameApplication",
  "operatingSystem": "Web",
  "description": "Watch Age of Empires II replays on an isometric map with auto-classified units, full build-order and tech timelines, and one-click WebM highlight-clip export.",
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" }
}
</script>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "How to analyze an Age of Empires II replay",
  "step": [
    { "@type": "HowToStep", "name": "Load a replay", "text": "Upload an .aoe2record file or search a player and pick a recent match." },
    { "@type": "HowToStep", "name": "Watch the game", "text": "Press play, scrub the timeline, and change speed to study build orders and fights." },
    { "@type": "HowToStep", "name": "Export a clip", "text": "Generate a shareable WebM highlight of the biggest engagement." }
  ]
}
</script>
{% endblock %}
```

(Verify `base.html` has a `{% block structured_data %}`; if the block has a different name, match it. Overriding it replaces the default `WebApplication` block on this page, which is acceptable — `SoftwareApplication` is more specific here.)

- [ ] **Step 2: Run — PASS** (`test_replay_softwareapplication_jsonld`). Validate both JSON-LD blocks parse (a quick `python -c` json.loads over the rendered blocks).

- [ ] **Step 3: Commit**

```bash
git add apps/website/templates/replay.html
git commit -m "feat(seo): add SoftwareApplication + HowTo JSON-LD to /replay

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Verification & ship

- [ ] **Step 1:** Full suite green. JSON-LD blocks parse as valid JSON.
- [ ] **Step 2:** Because `mgz` is absent here, `/replay` returns 503 in this env — so smoke-test by **rendering `replay.html` directly** (as the test helper does) and `curl`-checking the feature text + JSON-LD are in the HTML. On the staging deploy (where replay is enabled), load `/replay`: confirm the description renders above a working embedded viewer, the viewer still plays a replay, and the page scrolls. Screenshot.
- [ ] **Step 3:** `git push origin staging`; ask user to verify on staging (especially that the embedded viewer still works end-to-end). Do NOT push `main`.

---

## Self-Review

**Spec coverage (Phase 5 Replay description):** crawlable description of what the tool does ✓ (Task 1 intro + feature list + how-to); `SoftwareApplication`/`HowTo` JSON-LD ✓ (Task 2); SPA untouched ✓ (only `replay.html`). **Open decision flagged for user:** the page changes from locked full-screen to scrollable-with-description.

**Placeholder scan:** Task 1 step (a)/(c) adapt existing blocks (read-then-edit) — concrete target CSS/HTML given; the only non-pasted part is the existing JS resizer being removed, which is a deletion, not new code.

**Type/name consistency:** the iframe `src` preserves `{{ replay_qs }}`; tests assert the feature text, `/replay/index.html`, and both JSON-LD types; the disabled-env path is handled by rendering the template directly.
