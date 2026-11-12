#!/usr/bin/env python3
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright
OUT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'aoe2x/js_simulation/calibration/economy/farms-2026-11-09'

async def main():
    html=(OUT/'playback.html').read_text();errors=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1200,'height':1000},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.set_content(html,wait_until='load')
        assert 'Banked 0.00' in await page.locator('#stats').inner_text()
        await page.locator('#play').click()
        await page.wait_for_function("+document.getElementById('time').value>1")
        await page.locator('#play').click()
        for profile in ['none','full']:
            await page.select_option('#profile',profile)
            await page.locator('#time').fill('60');await page.locator('#time').dispatch_event('input')
            run=json.loads((OUT/f'{profile}-seed-0.json').read_text())
            frame=next(f for f in run['frames'] if f['t']==60)
            assert f"Banked {frame['banked']:.2f}" in await page.locator('#stats').inner_text()
        # Click outer farm 10 using canvas coordinates mapped into its client box.
        box=await page.locator('#map').bounding_box()
        await page.mouse.click(box['x']+852.5/1000*box['width'],box['y']+322.5/630*box['height'])
        assert 'Farm 10:' in await page.locator('#detail').inner_text()
        assert await page.locator('#events tr').count()>0
        await page.screenshot(path=str(OUT/'playback-desktop.png'),full_page=True)
        await page.select_option('#profile','none')
        await page.locator('#time').fill('600');await page.locator('#time').dispatch_event('input')
        assert 'Reseed wood 0' not in await page.locator('#stats').inner_text()
        base=json.loads((OUT/'none-seed-0.json').read_text())
        depletion=next((e for e in base['events'] if e['event']=='depleted'),None)
        if depletion:
            await page.evaluate("e=>{selected=e.worker;slider.value=e.t+.5;draw()}",depletion)
            assert 'Farm depleted' in await page.locator('#events').inner_text()
        await page.locator('#reset').click()
        assert 'Time 0.0 s' in await page.locator('#stats').inner_text()
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await page.screenshot(path=str(OUT/'playback-mobile.png'),full_page=True)
        assert not errors,errors
        await browser.close()
    result=dict(all_passed=True,checks=['initial_render','animation_advances','base_banked_data','full_banked_data',
                'outer_farm_selection','event_log','reseeding','reset','mobile_no_overflow','no_script_errors']+(['depletion_event'] if depletion else []),
                html_sha256=hashlib.sha256(html.encode()).hexdigest())
    (OUT/'browser-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

asyncio.run(main())
