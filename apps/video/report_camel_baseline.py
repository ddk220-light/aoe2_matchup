"""Compare verified camel outcomes with Turks; keep draw and missing states explicit."""
from pathlib import Path

from run_champi_comparison_capture import read, save
from prepare_camel_baseline import WORK, ORIGINAL


def classify(baseline, variant):
    if baseline is None or variant is None:
        return 'PENDING'
    if baseline == 'DRAW' or variant == 'DRAW':
        return 'DRAW_COMPARISON'
    if baseline == 'LOSS' and variant == 'WIN':
        return 'BETTER_THAN_BASELINE'
    if baseline == 'WIN' and variant == 'LOSS':
        return 'WORSE_THAN_BASELINE'
    return 'BOTH_WIN' if baseline == 'WIN' else 'BOTH_LOSE'


def main():
    manifest=read(WORK/'manifest.json')['matchups']
    verified={}
    for path in (WORK/'pilot-phase/capture/status.json', WORK/'capture/status.json'):
        if path.exists():
            verified.update({r['jobId']:r for r in read(path).get('results',[]) if r['status']=='verified'})
    results=[]
    for job in manifest:
        record=verified.get(job['id'])
        if not record:
            continue
        directory=Path(record['runDirectory'])
        capture=read(directory/'manifest.json')['capture']
        plan=read(WORK/'plans'/f'{job["id"]}.json')
        results.append(dict(jobId=job['id'], civilization='Turks', opponent=job['side3'],
            counts=[plan[s]['count'] for s in ('side2','side3')],
            outcome='DRAW' if capture['winnerOwner'] is None else 'WIN' if capture['winnerOwner']==2 else 'LOSS',
            signedRemainingHpPercent=capture['signedRemainingHpPercent'],
            winnerHpPercent=capture['winnerRemainingHpPercent'], runDirectory=str(directory)))
    save(WORK/'results.json',dict(total=len(manifest), verified=len(results), results=results))
    baseline={r['opponent']:r for r in results}
    original=read(ORIGINAL/'results.json')['results']
    variants={(r['opponent'],r['civilization']):r for r in original}
    civs=list(dict.fromkeys(r['civilization'] for r in original))
    comparisons=[]
    lines=['# Camel outcomes versus Turkish baseline', '', f'{len(results)} / {len(manifest)} baseline recordings verified.', '',
           'Better: Turks loses and variant wins. Worse: Turks wins and variant loses. Both win gets no special highlight. Draws stay separate. These are individual recorded battles, not estimates of win probability.', '',
           '| Opponent | Turks | '+' | '.join(civs)+' |', '|---|'+'---|'*(len(civs)+1)]
    for job in manifest:
        opponent=job['side3'];base=baseline.get(opponent);cells=[]
        for civ in civs:
            variant=variants.get((opponent,civ))
            flag=classify(base['outcome'] if base else None, variant['outcome'] if variant else None)
            comparisons.append(dict(opponent=opponent, civilization=civ, classification=flag,
                                    baseline=base, variant=variant))
            cells.append((variant['outcome'] if variant else 'N/A')+' / '+flag.replace('_',' ').lower())
        lines.append('| '+opponent.replace('_',' ')+' | '+(base['outcome'] if base else 'Pending')+' | '+' | '.join(cells)+' |')
    save(WORK/'baseline-comparison.json',dict(baseline='Turks', baselineVerified=len(results), comparisons=comparisons))
    (WORK/'BASELINE_COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
