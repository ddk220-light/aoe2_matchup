const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
  ? {executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH} : {channel:'chrome'})});
 const base=process.env.QA_URL || 'http://127.0.0.1:5056';
 fs.mkdirSync('.scratch/architecture-qa',{recursive:true});
 for(const [name,viewport] of [['laptop',{width:1366,height:768}],['mobile',{width:390,height:844}]]) {
  const context=await browser.newContext({viewport});const page=await context.newPage();const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/?civ1=Spanish&unit1=hand_cannoneer&civ2=Chinese&unit2=arbalester&mode=count&count1=5&count2=5');
  await page.waitForFunction(()=>window.simulation?.renderer && document.querySelector('#prog1Name')?.textContent.includes('Hand Cannoneer'));
  if(name==='mobile') {
   const layout=await page.evaluate(()=>({
    arenaTop:document.querySelector('#arena').getBoundingClientRect().top+scrollY,
    playerBottom:document.querySelector('.arena-player').getBoundingClientRect().bottom,
    statsTop:document.querySelector('#team1Live').getBoundingClientRect().top,
   }));
   assert.ok(layout.arenaTop<600,'selected teams should leave the arena near the first phone screen');
   assert.ok(layout.statsTop>layout.playerBottom,'detailed stats belong below the arena and controls');
  }
  await page.locator('#playPauseBtn').click();
  await page.waitForFunction(()=>window.simulation?.state==='playing');
  const seed=await page.evaluate(()=>window.simulation.config.seed);
  await page.locator('#playPauseBtn').click();
  assert.equal(await page.evaluate(()=>window.simulation.state),'paused');
  if(name==='mobile') {
   const hp=await page.locator('#prog1Hp').textContent();
   await page.setViewportSize({width:1366,height:768});
   await page.waitForFunction(()=>document.querySelector('#team1Live').parentElement.id==='team1Rail');
   await page.setViewportSize(viewport);
   await page.waitForFunction(()=>document.querySelector('#team1Live').parentElement.id==='mobileMatchupStats');
   assert.equal(await page.locator('#prog1Hp').textContent(),hp,'resize must preserve live statistics');
   assert.equal(await page.locator('#team1Live').count(),1,'responsive layout must not duplicate readouts');
   assert.equal(await page.evaluate(()=>window.simulation.state),'paused');
  }
  await page.waitForTimeout(500);
  await page.screenshot({path:'.scratch/architecture-qa/'+name+'-battle.png',fullPage:false});
  await page.locator('#playPauseBtn').click();
  await page.locator('#speedBtn').click();await page.locator('#speedBtn').click();await page.locator('#speedBtn').click();
  await page.waitForFunction(()=>window.simulation.state==='completed',{},{timeout:30000});
  await page.locator('#restartBtn').click();
  await page.waitForFunction(old=>window.simulation?.config?.seed!==old && window.simulation.state==='playing',seed);
  await page.locator('[data-action="clearUnit"][data-team="1"]').click();
  assert.equal(await page.evaluate(()=>window.simulation.state),'selecting');
  assert.equal(await page.evaluate(()=>window.simulation.config),null);
  assert.ok(await page.locator('[data-action="selectUnit"]').count()>0);
  if(name==='mobile') {
   assert.ok(await page.locator('.unit-pick span').first().evaluate(el=>parseFloat(getComputedStyle(el).fontSize)>=12));
   await page.locator('[data-action="clearCiv"][data-team="1"]').click();
   assert.ok(await page.locator('.civ-card span').first().evaluate(el=>parseFloat(getComputedStyle(el).fontSize)>=12));
   assert.ok(await page.locator('#team1Rail .picker-browse-hint').isVisible());
   assert.ok(await page.locator('#team1Search').isVisible());
   assert.equal(await page.locator('#team1Live').isVisible(),false);
  }
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.goto(base+'/civilizations/spanish');
  await page.waitForSelector('#results .unit-badge');
  await page.waitForTimeout(500);
  await page.screenshot({path:'.scratch/architecture-qa/'+name+'-civilization.png',fullPage:false});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.goto(base+'/units');await page.waitForSelector('#tableContainer tbody tr');
  await page.waitForTimeout(500);
  await page.screenshot({path:'.scratch/architecture-qa/'+name+'-rankings.png',fullPage:false});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.deepEqual(errors,[]);
  console.log(name+': playback, restart, selection reset, three-page layout PASS');
  await context.close();
 }
 const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();
 await page.goto(base+'/civilizations/spanish');assert.ok(await page.locator('#results .unit-badge').count()>5);
 assert.ok((await page.locator('#results').innerText()).includes('Spanish'));
 console.log('JavaScript disabled: civilization text, units and links PASS');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
