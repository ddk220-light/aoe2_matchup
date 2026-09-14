"""Export representative frames for a human visual check of a finished episode."""
import argparse,json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw
from overlay.ffutil import find_ffmpeg

def build(key, battles_only=False):
    lab=Path('aoe2x/js_simulation/calibration/lab').resolve()
    out=lab/f'compilations/{key}-unique-units/final-cost-v2'
    manifest=json.loads((out/('battles-manifest.json' if battles_only else 'manifest.json')).read_text())
    qa=out/'qa';qa.mkdir(exist_ok=True)
    def frame(video,seconds,path):
        subprocess.run([find_ffmpeg(),'-v','error','-y','-ss',str(seconds),'-i',str(video),'-frames:v','1',str(path)],check=True)
        return Image.open(path).convert('RGB')
    indices=[0,len(manifest['results'])//2,len(manifest['results'])-1]
    sheet=Image.new('RGB',(1280,3*750),'#191919');draw=ImageDraw.Draw(sheet)
    for row,index in enumerate(indices):
        x=manifest['results'][index];seconds=x['startSeconds']+x['durationSeconds']*.5
        im=frame(manifest['output'],seconds,qa/f'full-{index:02}.png')
        sheet.paste(im.resize((1280,720)),(0,row*750+30));draw.text((10,row*750+8),x['title'],fill='white')
    sheet.save(qa/'full-contact.jpg',quality=92)
    selection=json.loads((lab/f'shorts/{key}-selected-10/selection.json').read_text())['items']
    sheet=Image.new('RGB',(1350,1020),'#191919');draw=ImageDraw.Draw(sheet)
    for index,x in enumerate(selection):
        target=Path(x['output']);duration=json.loads((target/'validation.json').read_text())['durationSeconds']
        assert duration<=180, 'Selected Short exceeds 3 minutes'
        im=frame(target/'short.mp4',duration*.5,qa/f'short-{index:02}.png')
        xx=(index%5)*270;yy=(index//5)*510
        sheet.paste(im.resize((270,480)),(xx,yy+30));draw.text((xx+5,yy+8),x['unit'],fill='white')
    sheet.save(qa/'shorts-contact.jpg',quality=92)
    print(qa)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('key');p.add_argument('--battles-only',action='store_true');a=p.parse_args();build(a.key,a.battles_only)
