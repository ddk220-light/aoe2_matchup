/* Run against a local server configured with ARMY_ECONOMICS_MODE=review. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.QA_URL || 'http://127.0.0.1:5055';
const out = '.scratch/army-economics-qa';

(async () => {
  fs.mkdirSync(out, {recursive: true});
  const browser = await chromium.launch({executablePath: process.env.CHROME_PATH || '/usr/bin/chromium', headless: true});
  try {
    for (const [name, viewport] of [['desktop', {width: 1440, height: 1000}], ['mobile', {width: 390, height: 844}]]) {
      const ctx = await browser.newContext({viewport});
      const page = await ctx.newPage(), errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(base + '/?civ1=Spanish&unit1=champion&civ2=Saracens&unit2=arbalester&mode=count&count1=7&count2=7');
      await page.waitForFunction(() => document.getElementById('eco1Score')?.textContent === '42.8 weighted villager-min');
      assert.match(await page.locator('#eco1Losses').innerText(), /^0 replacements/);
      assert.match(await page.locator('#eco1Queue').innerText(), /3 Barracks.*training within 60s/);
      assert.match(await page.locator('#eco2Queue').innerText(), /4 Archery Range/);
      assert.match(await page.locator('#eco1Investment').innerText(), /525W/);
      assert.match(await page.locator('#eco1Comparison').innerText(), /Army A needs 7.4% less weighted investment/);
      await page.screenshot({path: `${out}/${name}-preview.png`, fullPage: false});
      await page.locator('#armyEconomics > summary').click();
      await page.locator('#armyEconomics').scrollIntoViewIfNeeded();
      assert.match(await page.locator('#armyEconomicsBody').innerText(), /Common workload/);
      assert.match(await page.locator('#armyEconomicsBody').innerText(), /Combined bill after scarcity weights/);
      assert.doesNotMatch(await page.locator('#armyEconomicsBody').innerText(), /2,000|Unused building budget|100 dedicated villagers/);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await page.screenshot({path: `${out}/${name}-details.png`, fullPage: false});
      await page.locator('#playPauseBtn').click();
      await page.waitForFunction(() => window.simulation.state === 'playing');
      await page.locator('#playPauseBtn').click();
      assert.equal(await page.evaluate(() => window.simulation.state), 'paused');
      const paused = await page.locator('#eco1Losses').innerText();
      await page.waitForTimeout(300);
      assert.equal(await page.locator('#eco1Losses').innerText(), paused);
      await page.locator('#playPauseBtn').click();
      for (let i = 0; i < 3; i++) await page.locator('#speedBtn').click();
      await page.waitForFunction(() => window.simulation.state === 'completed', {}, {timeout: 90000});
      const dead = await page.evaluate(() => {
        const counts = [0, 0], seen = new Set();
        for (const snapshot of window.simulation.snapshots) for (const event of snapshot.events || []) {
          const id = event.type === 'death' ? event.targetId : event.type === 'unit-dismount-pending' ? event.actorId : null;
          const owner = window.simulation.unitIndex.get(id)?.owner;
          if ((owner === 2 || owner === 3) && !seen.has(id)) { seen.add(id); counts[owner - 2]++; }
        }
        return counts;
      });
      for (let i = 0; i < 2; i++) assert.match(await page.locator(`#eco${i + 1}Losses`).innerText(), new RegExp(`^${dead[i]} replacement`));
      assert.match(await page.locator('#eco1Queue').innerText(), /3 Barracks/);
      assert.equal(await page.locator('#eco1Score').innerText(), '42.8 weighted villager-min');
      await page.locator('#restartBtn').click();
      await page.waitForFunction(() => window.simulation.state === 'playing');
      await page.waitForFunction(() => document.getElementById('eco1Losses').textContent.startsWith('0 replacements'));
      await page.locator('[data-action="clearUnit"][data-team="1"]').click();
      assert.equal(await page.locator('#armyEconomics').isVisible(), false);
      assert.equal(await page.evaluate(() => window.simulation.config), null);
      assert.deepEqual(errors, []);
      console.log(`${name}: preview, details, pause, live casualties, restart and reset PASS`);
      await ctx.close();
    }
    const konnik = await browser.newPage();
    await konnik.goto(base + '/?civ1=Bulgarians&unit1=elite_konnik_bulgarians&civ2=Spanish&unit2=paladin&mode=count&count1=3&count2=12');
    await konnik.waitForFunction(() => document.getElementById('eco1Queue')?.textContent.includes('Krepost'));
    await konnik.locator('#playPauseBtn').click();
    await konnik.waitForFunction(() => window.simulation.state === 'playing');
    await konnik.evaluate(() => { window.simulation.speedMultiplier = 64; });
    await konnik.waitForFunction(() => window.simulation.state === 'completed', {}, {timeout: 90000});
    const dismounts = await konnik.evaluate(() => window.simulation.snapshots.flatMap(s => s.events || []).filter(e => e.type === 'unit-dismounted').length);
    assert.ok(dismounts > 0, 'exercise real mounted-to-foot transitions');
    assert.match(await konnik.locator('#eco1Losses').innerText(), /^3 replacements/);
    console.log('Konnik at 64x: mounted losses counted once across dismount and foot death PASS');
    await konnik.close();
    const batch = await browser.newPage();
    await batch.goto(base + '/?civ1=Tupi&unit1=elite_blackwood_archer_tupi&civ2=Spanish&unit2=champion&mode=count&count1=27&count2=27');
    await batch.waitForFunction(() => document.getElementById('eco1Batch')?.textContent.includes('1 extra unit'));
    await batch.locator('[data-army-details]').first().click();
    assert.match(await batch.locator('#armyEconomicsBody').innerText(), /Buildings and upgrades are charged once/);
    console.log('Batch surplus and one-time investment are explicit PASS');
    await batch.close();

    const pasture = await browser.newPage();
    await pasture.goto(base + '/?civ1=Khitans&unit1=champion&civ2=Spanish&unit2=champion&mode=count&count1=7&count2=7');
    await pasture.waitForFunction(() => document.getElementById('armyEconomicsStatus')?.textContent.includes('measurements deferred'));
    assert.equal(await pasture.locator('#eco1Investment').innerText(), '525W');
    assert.notEqual(await pasture.locator('#eco1Score').innerText(), 'Unavailable');
    assert.match(await pasture.locator('#eco1Queue').innerText(), /3 Barracks/);
    await pasture.locator('[data-army-details]').first().click();
    assert.match(await pasture.locator('#armyEconomicsBody').innerText(), /estimated gathering|Post-Imperial|post-Imperial/);
    await pasture.locator('.army-team-details').first().locator('summary').click();
    assert.match(await pasture.locator('#armyEconomicsBody').innerText(), /25.2 food\/villager-minute/);
    assert.match(await pasture.locator('#armyEconomicsBody').innerText(), /110 wood per 1035 food/);
    console.log('Pasture estimate funds the army and exposes rate, renewal wood and source PASS');
    await pasture.close();
    const page = await browser.newPage();
    await page.route('**/api/v3/army-context', route => route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({error: 'Test context unavailable'})}));
    await page.goto(base + '/?civ1=Spanish&unit1=champion&civ2=Spanish&unit2=champion&mode=count&count1=1&count2=1');
    await page.waitForFunction(() => document.getElementById('armyEconomicsStatus')?.textContent.includes('Test context unavailable'));
    await page.locator('#playPauseBtn').click();
    await page.waitForFunction(() => window.simulation.state === 'playing');
    console.log('Context endpoint failure: combat remains available PASS');
    await page.close();
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
