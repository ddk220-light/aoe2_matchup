#!/usr/bin/env python3
"""Check the woodline playback in Chromium using its embedded data."""
import asyncio
import hashlib
import json
from pathlib import Path
from playwright.async_api import async_playwright

OUT=Path(__file__).resolve().parents[1]/'aoe2x/js_simulation/calibration/economy/wood-2026-11-09'
async def main():
    html=(OUT/'playback.html').read_text();errors=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1320,'height':1000},device_scale_factor=1)
        page.on('pageerror',lambda error:errors.append(str(error)))
        await page.set_content(html,wait_until='load')
        assert 'Banked 0.00' in await page.locator('#stats').inner_text()
        await page.locator('#play').click()
        await page.wait_for_function("parseFloat(document.getElementById('time').value)>1")
        await page.locator('#play').click()
        await page.locator('#time').fill('60');await page.locator('#time').dispatch_event('input')
        assert 'Banked 180.00' in await page.locator('#stats').inner_text()
        await page.select_option('#trial','full-ten')
        assert 'Banked 200.00' in await page.locator('#stats').inner_text()
        await page.locator('#time').fill('420');await page.locator('#time').dispatch_event('input')
        assert 'Depleted trees 21' in await page.locator('#stats').inner_text()
        await page.screenshot(path=str(OUT/'playback-desktop.png'),full_page=True)
        await page.select_option('#trial','full-four-adjacent')
        assert await page.locator('#time').get_attribute('max')=='840'
        await page.locator('#reset').click()
        assert 'Time 0.0 s' in await page.locator('#stats').inner_text()
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await page.screenshot(path=str(OUT/'playback-mobile.png'),full_page=True)
        assert not errors,errors
        await browser.close()
    result={'all_passed':True,'checks':['initial_render','animation_advances','seek_no_upgrades',
        'full_upgrade_selector','tree_depletion_display','adjacent_camp_timeline','reset',
        'mobile_no_overflow','no_javascript_errors'],
        'html_sha256':hashlib.sha256(html.encode()).hexdigest(),'javascript_errors':errors}
    (OUT/'browser-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
asyncio.run(main())
