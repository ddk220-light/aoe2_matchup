"""Manual browser QA of /matchup-advisor (Revision 4, eco-aware). Not part of CI.

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
WINS = {'dominance', 'kite', 'plain_win', 'power_win'}
CATEGORY_CLASSES = {'win', 'eco', 'loss', 'close', 'pending'}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 for name,viewport in [('desktop',{'width':1440,'height':1000}),('mobile',{'width':390,'height':844})]:
  context=browser.new_context(viewport=viewport)
  page=context.new_page();errors=[];requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:requests.append(r.url))
  page.goto(base+'/matchup-advisor',wait_until='domcontentloaded')
  advisor_tab=page.locator('#navLinks a[href="/matchup-advisor"]')
  assert advisor_tab.get_attribute('aria-current')=='page'
  page.wait_for_selector('#civ-grid .ma-civ-card');assert page.locator('#civ-grid .ma-civ-card').count()==56
  page.locator('[data-civ="Danes"]').click();page.locator('[data-civ="Saxons"]').click()
  page.wait_for_selector('.ma-team-columns')
  assert page.locator('[data-role=main]').count()==2
  assert page.locator('[data-role=sidekick]').count()==2
  assert page.locator('[data-role=additions]').count()==2
  assert page.locator('.ma-match:not(.ma-legend-swatch)').evaluate_all('(buttons)=>buttons.every(button=>button.getAttribute("aria-label") && button.querySelector("img").alt)')
  catalog=json.loads(page.locator('#advisor-config').text_content())
  source=page.request.get(base+catalog['files']['danes']['url']).json()['opponents']['Saxons']
  info={}
  for row in source:
   info[row[0],row[1]]=(row[2],row[9])
   info[row[1],row[0]]=({'a_win':'b_win','b_win':'a_win'}.get(row[2],row[2]),row[10])
  units={unit['key']:unit for unit in catalog['units']}
  for side in ['left','right']:
   plan=page.locator(f'#ma-{side}-plan')
   main=plan.locator('[data-role="main"]');support=plan.locator('[data-role="sidekick"]')
   main_unit=units[main.get_attribute('data-unit')]
   assert main_unit['costs']['gold']>0 and main_unit['name'] not in ('Scorpion','Heavy Scorpion')
   if support.get_attribute('data-unit'):
    support_unit=units[support.get_attribute('data-unit')]
    assert support_unit['key']!=main_unit['key']
    assert support_unit['costs']['gold']==0 or support_unit['name'] in ('Scorpion','Heavy Scorpion')
   # Every icon sits in the line of its own category (pending lines hold inferred cells).
   for line in main.locator('.ma-match-line').all():
    category=line.get_attribute('data-category')
    for button in line.locator('.ma-match').all():
     outcome,cat=info[main_unit['id'],int(button.get_attribute('data-opponent'))]
     assert cat==category or (cat=='pending' and category==('pending_win' if outcome=='a_win' else 'pending_loss')),(category,cat)
   for group in plan.locator('.ma-counter-group').all():
    counter=int(group.get_attribute('data-counter'))
    for target in group.locator('.ma-match').all():
     assert info[counter,int(target.get_attribute('data-opponent'))][0]=='a_win'
   alternatives=page.locator(f'#ma-{side}-units .ma-unit-card')
   assert alternatives.count()<=3
  classes={cls.split()[1].removeprefix('ma-match-') for cls in page.locator('.ma-match:not(.ma-legend-swatch)').evaluate_all('(b)=>b.map(x=>x.className)')}
  assert classes<=CATEGORY_CLASSES,classes
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
  page.screenshot(path=str(output/f'{name}-advisor.png'),full_page=True)
  page.locator('#ma-left-plan .ma-match').first.click();assert page.locator('#ma-detail').is_visible()
  assert 'army sizes set so both armies cost about the same' in page.locator('#ma-detail').inner_text()
  page.locator('.ma-detail-close').click();assert not page.locator('#ma-detail').is_visible()
  assert not any('/api/matchup-sims' in url or '/cached-advisor/' in url for url in requests)
  assert not errors,errors
  if name=='desktop':
   original_top=page.locator('#top-units').inner_html()
   def change_provenance(route):
    response=route.fetch();data=response.json()
    for rows in data['opponents'].values():
     for row in rows:
      row[6]='test-source-tier';row[7]=3;row[8]=-1
    route.fulfill(response=response,json=data)
   page.route('**/danes.json',change_provenance)
   page.reload(wait_until='domcontentloaded')
   page.locator('[data-civ="Danes"]').click();page.locator('[data-civ="Saxons"]').click();page.wait_for_selector('.ma-team-columns')
   assert page.locator('#top-units').inner_html()==original_top
  print(name,'PASS',json.dumps({'civs':56,'cards':page.locator('.ma-unit-card[data-unit]').count(),'matchups':page.locator('.ma-match').count(),'overflow':False,'errors':errors}))
  context.close()
 browser.close()
