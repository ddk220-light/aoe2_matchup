#!/usr/bin/env python3
"""Exercise the standalone review playback in Chromium, without a web server."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from playwright.async_api import async_playwright


async def main(output):
    errors=[]
    html=(output/'playback.html').read_text()
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1280,'height':1000},device_scale_factor=1)
        page.on('pageerror',lambda error:errors.append(str(error)))
        # Managed Chromium restricts file: navigation. Load the authorized,
        # generated standalone HTML into an empty test page instead.
        await page.set_content(html,wait_until='load')
        assert 'Deposited 0.00' in await page.locator('#stats').inner_text()
        await page.locator('#play').click()
        await page.wait_for_function("parseFloat(document.getElementById('time').value) > 1")
        await page.locator('#play').click()
        await page.locator('#time').fill('60')
        await page.locator('#time').dispatch_event('input')
        text=await page.locator('#stats').inner_text()
        assert 'Time 60.0 s' in text and 'Deposited 200.00' in text,text
        await page.screenshot(path=str(output/'playback-desktop.png'),full_page=True)
        await page.select_option('#trial','single-worker')
        assert 'Deposited 20.00' in await page.locator('#stats').inner_text()
        await page.select_option('#trial','ten-walk-only')
        assert 'Deposited 200.00' in await page.locator('#stats').inner_text()
        await page.locator('#reset').click()
        assert 'Time 0.0 s' in await page.locator('#stats').inner_text()
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile horizontal overflow'
        await page.screenshot(path=str(output/'playback-mobile.png'),full_page=True)
        assert not errors,errors
        await browser.close()
    result={'all_passed':True,'checks':['initial_render','animation_advances','seek_60_seconds',
        'baseline_200_banked','single_worker_20_banked','walking_only_selector','reset',
        'mobile_no_horizontal_overflow','no_javascript_errors'],'javascript_errors':errors,
        'html_sha256':hashlib.sha256(html.encode()).hexdigest()}
    (output/'browser-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path,nargs='?',default=Path('aoe2x/js_simulation/calibration/economy/gold-2026-11-09'))
    asyncio.run(main(p.parse_args().output))
