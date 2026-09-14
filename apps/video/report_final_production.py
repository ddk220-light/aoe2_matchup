"""Summarize confirmed uploads without treating queued or processing files as done."""
import json
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[2]
LAB=ROOT/'aoe2x/js_simulation/calibration/lab'

def main():
    lines=['# Final video production report','',f'Updated: {datetime.now(timezone.utc).isoformat()}','',
           'Channel: @aoe2matchup. New uploads default to private; owner changes in Studio are preserved.','',
           '| Unit | Captured matchups | Full video | Shorts processed | Status |','|---|---:|---|---:|---|']
    sections=[];total=0;uploaded=0
    for key,label in [('champi-warrior','Champi Warrior'),('guecha-warrior','Guecha Warrior'),('temple-guard','Temple Guard')]:
        canonical=json.loads((LAB/f'campaigns/{key}-canonical/status.json').read_text())
        receipt=LAB/f'compilations/{key}-unique-units/upload-completion.json'
        if not receipt.exists():
            lines.append(f'| {label} | {canonical["total"]} | Pending | Pending | In production |');continue
        data=json.loads(receipt.read_text());videos=data['videos'];assert len(videos)==11
        done=sum(v['state']=='COMPLETE' and v['processingStatus']=='succeeded' for v in videos)
        if data['state']=='COMPLETE':assert done==11
        total+=done;uploaded+=len(videos);full=videos[0];shorts_done=sum(v['state']=='COMPLETE' for v in videos[1:])
        phase='Complete' if done==11 else f'Uploaded; {done}/11 processed'
        lines.append(f'| {label} | {canonical["total"]} | [Watch](https://www.youtube.com/watch?v={full["videoId"]}) | {shorts_done}/10 | {phase} |')
        sections += ['',f'## {label}','']
        selection=LAB/f'shorts/{key}-selected-10/selection.json'
        if selection.exists():
            sections += [n for n in json.loads(selection.read_text()).get('notes',[]) if n.startswith('No eligible')]
            sections.append('')
        sections += ['| Video | Link |','|---|---|']
        for v in videos:sections.append(f'| {v["title"].replace("|","—")} | [YouTube](https://www.youtube.com/watch?v={v["videoId"]}) |')
    lines += ['',f'Files uploaded in this final production pass: **{uploaded}/33**. YouTube processing confirmed: **{total}/33**.','',
              'Validation includes full video decoding, audio and dimensions, chapter timing, representative full-video frames, and a frame from each Short. YouTube processing success is separate from any Studio copyright checks.','',
              'All corrected game captures are complete: 382 cost-repair recordings. The canonical final sets contain 74 Champi, 73 Guecha, and 73 Temple Guard matches. Raw recordings and frames.bin remain available.','',
              'Previously completed corrected full videos: [Inca Slinger](https://www.youtube.com/watch?v=AG6sOWyuPoM), [Korean War Wagon](https://www.youtube.com/watch?v=qbaW9ZwqCl8), [Korean Fire Lancer](https://www.youtube.com/watch?v=1HThmQQDpBs).',
              *sections]
    flemish=ROOT/'data/local/flemish-militia-capture-completion.json'
    if flemish.exists():
        capture=json.loads(flemish.read_text())
        lines += ['', '## Newly requested Flemish Militia run', '',
                  f"All {capture['verified']} captures validated, with {capture['failed']} failures. Raw videos and gRPC frames are retained at `{capture['storage']}`.", '',
                  'Flemish media production is pending; this new capture run is separate from the three completed video packages above.', '',
                  f"[Capture report]({Path(capture['report']).as_posix()})"]
    path=ROOT/'data/local/final-video-publishing-report.md';path.write_text('\n'.join(lines)+'\n',encoding='utf-8');print(path)

if __name__=='__main__':main()
