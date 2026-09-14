"""Prepare the corrected full upload with a fresh identity; reuse all ten Shorts."""
import json
from pathlib import Path

from aoe2x.lab.io import write_json

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'aoe2x/js_simulation/calibration/lab'


def main():
    full = LAB/'compilations/flaming-camel-unique-units/final'
    media = json.loads((full/'manifest.json').read_text())
    assert media['fullDecode'] == 'passed' and media['matchups'] == 73
    qa = json.loads((LAB/'flaming-camel-video-production/visual-qa.json').read_text())
    assert qa['status'] == 'passed' and qa.get('revision') == 'grid-v2', 'Review the corrected compilation before preparation'
    old = json.loads((LAB/'youtube-batch-flaming-camel/manifest.json').read_text())
    assert old['authorized']
    original = next(x for x in old['items'] if x['kind'] == 'full')
    original_dir = Path(original['preparation']).parent
    settings = json.loads((original_dir/'youtube-proposed-settings.json').read_text())
    new_dir = full/'youtube-grid-v2';new_dir.mkdir(exist_ok=True)
    desc = new_dir/'youtube-description.txt'
    desc.write_text((full/'youtube-description.txt').read_text(encoding='utf-8'),encoding='utf-8')
    settings.update(descriptionFile=str(desc),privacyStatus='private')
    write_json(new_dir/'youtube-proposed-settings.json',settings)
    preparation = new_dir/'youtube-upload-preparation.json'
    key = 'flaming-camel-full-v2'
    if not preparation.exists():
        write_json(preparation,{'uploadAuthorized':True,'targetChannelVerified':True,
            'targetChannel':old['targetChannel'],'video':media['output'],'stateKey':key,
            'uploadScope':'Authorized corrected full compilation; projectile effects removed from army counts.',
            'supersedesVideoId':'iFheKBOtJMo','preserveSupersededVideo':True})
    shorts = [x for x in old['items'] if x['kind'] == 'short']
    assert len(shorts) == 10
    item = dict(original,key=key,preparation=str(preparation))
    # A fresh full-video state key prevents the old transfer from being reused.
    batch = LAB/'youtube-batch-flaming-camel-v2';batch.mkdir(exist_ok=True)
    manifest = batch/'manifest.json'
    write_json(manifest,dict(old,title='Flaming Camel corrected full and existing Shorts',items=[item,*shorts]))
    print(manifest)


if __name__ == '__main__':
    main()
