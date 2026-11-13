"""Manual browser QA of /matchup-advisor. Not part of CI.

Serve a build (e.g. `python -m http.server 5107` in apps/web/.vercel/output/static after
prepare_release + `npm run build --prefix apps/web`), then run with QA_URL set. The page reads
the published static advisor files, so no API server is needed.
"""
from playwright.sync_api import sync_playwright
import json
import os
from pathlib import Path

base = os.environ.get("QA_URL", "http://127.0.0.1:5107")
output = Path(".scratch/advisor-qa")
output.mkdir(parents=True, exist_ok=True)
SHADES = {'win-strong', 'win', 'loss-light', 'loss', 'close'}
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH', '/usr/bin/chromium'), args=['--no-sandbox'])
    for name, viewport in [('desktop', {'width': 1440, 'height': 1000}), ('mobile', {'width': 390, 'height': 844})]:
        page = browser.new_page(viewport=viewport)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(base + '/matchup-advisor', wait_until='domcontentloaded')
        page.wait_for_selector('#civ-grid .ma-civ-card')
        assert page.locator('#civ-grid .ma-civ-card').count() == 56
        page.locator('[data-civ="Danes"]').click()
        page.locator('[data-civ="Saxons"]').click()
        page.wait_for_selector('#ma-left-plan [data-role=main]')
        assert page.locator('[data-role=main]').count() == 2
        assert page.locator('[data-role=support]').count() <= 2
        # Only the two plans: no alternatives, additions, legend or explanatory text.
        assert page.locator('.ma-team-columns, [data-role=additions], .ma-legend-box, .ma-helps').count() == 0
        labels = set(page.locator('.ma-match-label').all_inner_texts())
        assert labels <= {'Beats', 'Loses to', 'Close'}, labels
        text = page.locator('#top-units').inner_text().lower()
        assert 'pending' not in text and 'advantage' not in text
        shades = {c.split()[1].removeprefix('ma-match-') for c in page.locator('.ma-match').evaluate_all('(b)=>b.map(x=>x.className)')}
        assert shades <= SHADES, shades
        page.locator('#ma-left-plan .ma-match').first.click()
        assert page.locator('#ma-detail').is_visible()
        page.locator('.ma-detail-close').click()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        assert not errors, errors
        page.screenshot(path=str(output / f'{name}.png'), full_page=True)
        print(name, 'PASS', json.dumps({'matchups': page.locator('.ma-match').count()}))
    browser.close()
