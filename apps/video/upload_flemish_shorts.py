"""Publish reviewed Flemish Shorts independently of the blocked intro narration."""
import time
from pathlib import Path
from urllib.parse import urlencode
from finish_pending_production import ROOT, LAB, read, write, prepare, run, pause_check
from upload_youtube import API, require

def main():
    key, label, civ, slug = 'flemish-militia', 'Flemish Militia', 'Burgundians', 'flemish_militia_burgundians'
    shorts = LAB / f'shorts/{key}-selected-10'
    assert read(shorts / 'visual-qa.json')['passed']
    items = []
    for x in read(shorts / 'selection.json')['items']:
        target = Path(x['output']); desc = target / 'youtube-description.txt'
        desc.write_text(f'{label} vs {x["unit"]} ({x["civ"]}) in Age of Empires II: Definitive Edition.\n\nEqual resources using civilization-specific Imperial costs per unit, with a 27-unit cap. Ranged units get a small front line of hussars against melee units.\n\nTry your own matchup: https://aoe2matchup.com/?civ1={civ}&unit1={slug}&age1=Imperial\n\n#Shorts #AoE2 #AoE2DE #RTS #BattleSimulation #UnitCounters\n', encoding='utf-8')
        items.append(prepare(key, label, civ, slug, target / 'short.mp4', desc,
            ROOT / f'apps/video/intro/thumbnails/{key}-shorts.jpg', target / 'youtube',
            f'{key}-short-{x["number"]:02}-cost-v2', f'{label} vs {x["unit"]} | AoE2 DE #Shorts', False))
    write(shorts / 'upload-manifest.json', dict(items=items))
    for item in items:
        run('upload_youtube.py', '--preparation', item['preparation'], '--state-key', item['stateKey'], '--processing-wait-seconds', '0')
    api = API(ROOT / 'data/local/youtube'); deadline = time.time() + 3600
    while True:
        pause_check()
        local = {read(ROOT / f'data/local/youtube/{x["stateKey"]}-upload-status.json')['videoId']: x for x in items}
        code, _, body = api.request('https://www.googleapis.com/youtube/v3/videos?' + urlencode({'part': 'snippet,status,processingDetails', 'id': ','.join(local)}))
        remote = require(code, body)['items']; assert len(remote) == 10
        completed = 0
        for video in remote:
            assert video['snippet']['channelId'] == 'UCKYN-pN4AZ3w4LpRxcdSciA'
            phase = video['processingDetails']['processingStatus']; assert phase not in ('failed', 'terminated')
            item = local[video['id']]; path = ROOT / f'data/local/youtube/{item["stateKey"]}-upload-status.json'
            saved = read(path); assert saved.get('thumbnailSet')
            saved.update(state='COMPLETE' if phase == 'succeeded' else 'PROCESSING', processingStatus=phase, privacyStatus=video['status']['privacyStatus'])
            write(path, saved); write(Path(item['preparation']).parent / 'youtube-video-status.json', video)
            completed += phase == 'succeeded'
        write(shorts / 'upload-completion.json', dict(state='COMPLETE' if completed == 10 else 'PROCESSING', completed=completed, total=10,
            videos=[read(ROOT / f'data/local/youtube/{x["stateKey"]}-upload-status.json') for x in items]))
        if completed == 10: break
        assert time.time() < deadline
        time.sleep(20)
    print('All ten Flemish Shorts uploaded and processed', flush=True)

if __name__ == '__main__':
    main()
