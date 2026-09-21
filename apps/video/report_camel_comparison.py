"""Rebuild a compact eight-civilization outcome table from verified captures."""
from pathlib import Path

from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'data/local/camel-comparison'
CIVS = ('Hindustanis','Gurjaras','Berbers','Byzantines','Ethiopians','Saracens','Khitans','Malians')


def main():
    manifest = read(WORK/'manifest.json')['matchups']
    verified = {}
    for path in [WORK/'pilot-phase/capture/status.json', WORK/'capture/status.json']:
        if path.exists():
            verified.update({r['jobId']:r for r in read(path).get('results',[]) if r['status']=='verified'})
    results = []
    for job in manifest:
        record = verified.get(job['id'])
        if not record:
            continue
        directory = Path(record['runDirectory'])
        capture = read(directory/'manifest.json')['capture']
        plan = read(WORK/'plans'/f'{job["id"]}.json')
        results.append(dict(jobId=job['id'], civilization=job['civ2'], opponent=job['side3'],
                            opponentCivilization=job['civ3'], counts=[plan[s]['count'] for s in ('side2','side3')],
                            outcome='DRAW' if capture['winnerOwner'] is None else 'WIN' if capture['winnerOwner']==2 else 'LOSS',
                            signedRemainingHpPercent=capture['signedRemainingHpPercent'],
                            winnerHpPercent=capture['winnerRemainingHpPercent'], runDirectory=str(directory)))
    totals={c:dict(verified=sum(r['civilization']==c for r in results),
                   wins=sum(r['civilization']==c and r['outcome']=='WIN' for r in results),
                   planned=sum(r['civ2']==c for r in manifest)) for c in CIVS}
    save(WORK/'results.json',dict(total=len(manifest), verified=len(results), byCivilization=totals, results=results))
    lines=['# Eight-civilization camel results','',f'{len(results)} / {len(manifest)} verified recordings.',
           '', 'Each cell shows outcome, winning army HP remaining, and camel/opponent counts. Loss HP belongs to the surviving opponent. Pending cells are blank; self-match is omitted.',
           '', '| Opponent | '+' | '.join(CIVS)+' |','|---|'+'---|'*len(CIVS)]
    index={(r['opponent'],r['civilization']):r for r in results}
    for opponent in dict.fromkeys(r['side3'] for r in manifest):
        cells=[]
        for civ in CIVS:
            r=index.get((opponent,civ))
            cells.append(f"{r['outcome']} {r['winnerHpPercent']:.1f}% ({r['counts'][0]} vs {r['counts'][1]})" if r else '')
        lines.append('| '+opponent.replace('_',' ')+' | '+' | '.join(cells)+' |')
    (WORK/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':main()
