from playwright.sync_api import sync_playwright
import json
import os
import re
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
  advisor_tab=page.locator('#navLinks a[href="/matchup-advisor"]')
  assert page.locator('#navLinks .nav-tab').count()==4
  assert advisor_tab.get_attribute('aria-current')=='page'
  assert advisor_tab.is_visible()
  if name=='mobile':
   page.locator('#navHamburger').click()
   assert advisor_tab.locator('.nav-tab-label').is_visible()
   assert advisor_tab.locator('.nav-tab-label').inner_text()=='Matchup Advisor'
   page.locator('#navHamburger').click()
  page.wait_for_selector('#civ-grid .ma-civ-card');assert page.locator('#civ-grid .ma-civ-card').count()==56
  page.locator('[data-civ="Danes"]').click();page.locator('[data-civ="Saxons"]').click()
  page.wait_for_selector('.ma-team-columns')
  assert page.locator('.ma-result-banner').is_visible()
  assert page.locator('.ma-unit-card[data-unit]').count()>10
  assert page.locator('.ma-match').count()>0
  assert page.locator('.ma-provisional, .ma-evidence-mark, .ma-detail-badge, .is-estimated, .is-low-support').count()==0
  assert not re.search(r'\b(provisional|observed|inferred|estimated|forecast|unvalidated|low.support)\b',page.locator('.ma-advisor').inner_text(),re.I)
  assert all(re.fullmatch(r'ma-match ma-match-(win|loss|close)',cls) for cls in page.locator('.ma-match').evaluate_all('(buttons)=>buttons.map(button=>button.className)'))
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
  page.screenshot(path=str(output/f'{name}-advisor.png'),full_page=True)
  page.locator('.ma-match').first.click();assert page.locator('#ma-detail').is_visible()
  assert 'cost-adjusted armies' in page.locator('#ma-detail').inner_text()
  original_detail=page.locator('#ma-detail').inner_html()
  page.locator('.ma-detail-close').click();assert not page.locator('#ma-detail').is_visible()
  assert not any('/api/matchup-sims' in url or '/cached-advisor/' in url for url in requests)
  assert not errors,errors
  visible=page.locator('.ma-unit-card[data-unit] .ma-unit-icon').first
  assert visible.evaluate('(img)=>img.complete && img.naturalWidth>0')
  if name=='desktop':
   original_top=page.locator('#top-units').inner_html();original_results=page.locator('#results').inner_html()
   def change_provenance(route):
    response=route.fetch();data=response.json()
    kinds={row[3] for rows in data['opponents'].values() for row in rows}
    assert 'observed' in kinds and 'predicted_unvalidated' in kinds
    for rows in data['opponents'].values():
     for row in rows:
      row[3]='observed' if row[3]=='predicted_unvalidated' else 'predicted_unvalidated'
      row[6]='test-source-tier';row[7]=3;row[8]=-1
    route.fulfill(response=response,json=data)
   page.route('**/api/advisor-matchups/Danes',change_provenance)
   page.reload(wait_until='domcontentloaded')
   page.locator('[data-civ="Danes"]').click();page.locator('[data-civ="Saxons"]').click();page.wait_for_selector('.ma-team-columns')
   assert page.locator('#top-units').inner_html()==original_top
   assert page.locator('#results').inner_html()==original_results
   page.locator('.ma-match').first.click();assert page.locator('#ma-detail').inner_html()==original_detail
   page.locator('.ma-detail-close').click()
  print(name,'PASS',json.dumps({'civs':56,'cards':page.locator('.ma-unit-card[data-unit]').count(),'matchups':page.locator('.ma-match').count(),'uniform_presentation':True,'overflow':False,'errors':errors}))
  page.locator('#themeToggle').click()
  assert page.evaluate("document.documentElement.getAttribute('data-theme')")=='dark'
  page.locator('[data-civ=Danes]').click();assert page.locator('.ma-team-columns').count()==0
  page.locator('[data-civ=Varangians]').click();page.wait_for_selector('.ma-team-columns')
  assert page.locator('.ma-team-left>header h2').inner_text()=='Varangians'
  page.screenshot(path=str(output/f'{name}-dark.png'),full_page=False)
  context.close()
 browser.close()
