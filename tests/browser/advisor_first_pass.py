from playwright.sync_api import sync_playwright
import json
import os
from pathlib import Path

base = os.environ.get("QA_URL", "http://127.0.0.1:5107")
output = Path(".scratch/advisor-qa")
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 for name,viewport in [('desktop',{'width':1440,'height':1000}),('mobile',{'width':390,'height':844})]:
  context=browser.new_context(viewport=viewport)
  page=context.new_page();errors=[];requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:requests.append(r.url))
  page.goto(base+'/matchup-advisor',wait_until='domcontentloaded')
  page.wait_for_selector('#civ-grid .ma-civ-card');assert page.locator('#civ-grid .ma-civ-card').count()==56
  page.locator('[data-civ="Danes"]').click();page.locator('[data-civ="Saxons"]').click()
  page.wait_for_selector('.ma-team-columns')
  assert page.locator('.ma-provisional').inner_text()=='PROVISIONAL'
  assert page.locator('.ma-unit-card[data-unit]').count()>10
  assert page.locator('.ma-match.is-estimated').count()>0
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
  page.screenshot(path=str(output/f'{name}-advisor.png'),full_page=True)
  page.locator('.ma-match.is-estimated').first.click();assert page.locator('#ma-detail').is_visible()
  assert 'first-pass estimate' in page.locator('#ma-detail').inner_text()
  page.locator('.ma-detail-close').click();assert not page.locator('#ma-detail').is_visible()
  assert not any('/api/matchup-sims' in url or '/cached-advisor/' in url for url in requests)
  assert not errors,errors
  visible=page.locator('.ma-unit-card[data-unit] .ma-unit-icon').first
  assert visible.evaluate('(img)=>img.complete && img.naturalWidth>0')
  print(name,'PASS',json.dumps({'civs':56,'cards':page.locator('.ma-unit-card[data-unit]').count(),'estimates':page.locator('.ma-match.is-estimated').count(),'overflow':False,'errors':errors}))
  page.locator('#themeToggle').click()
  assert page.evaluate("document.documentElement.getAttribute('data-theme')")=='dark'
  page.locator('[data-civ=Danes]').click();assert page.locator('.ma-team-columns').count()==0
  page.locator('[data-civ=Varangians]').click();page.wait_for_selector('.ma-team-columns')
  assert page.locator('.ma-team-left>header h2').inner_text()=='Varangians'
  page.screenshot(path=str(output/f'{name}-dark.png'),full_page=False)
  context.close()
 browser.close()
