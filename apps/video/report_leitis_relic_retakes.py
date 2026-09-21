"""Compare preserved zero-relic recordings to corrected four-relic captures."""
import copy
import json
from pathlib import Path

from overlay.unit_timeline import decode
from report_champi_geometric import save

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/local/leitis-four-relic-retakes'
ARCHIVE = Path('D:/AoE2 Renders')


def result(archive_dir, job):
    index = json.loads((archive_dir/'run.json').read_text())
    entry = next(r for r in index['matchups'] if r['jobId'] == job)
    # Materialize only a tiny descriptor; use the archived frames in place.
    work = OUT/'analysis'/job
    work.mkdir(parents=True,exist_ok=True)
    recording = copy.deepcopy(entry['recording'])
    recording['files']['frames']['path'] = str(archive_dir/entry['files']['frames.bin']['path'])
    save(work/'recording.json',recording)
    timeline = decode(work)
    opening = {p:sum(u['hp'] for u in timeline['rows'][0]['sides'][p]) for p in ('2','3')}
    final = {p:sum(u['hp'] for u in timeline['rows'][-1]['sides'][p]) for p in ('2','3')}
    if final['2'] > 0 and final['3'] > 0:
        raise ValueError(f'No completed outcome in {job}')
    winner = '2' if final['2'] else '3' if final['3'] else 'draw'
    percentage = 100*final[winner]/opening[winner] if winner != 'draw' else 0
    return dict(winner=winner, winnerLabel=entry['plan']['side'+winner]['label'] if winner!='draw' else 'Draw',
                remainingPercent=percentage, openingHp=opening, finalHp=final,
                framesSha256=entry['files']['frames.bin']['sha256'],
                video=str(archive_dir/entry['files']['battle.mp4']['path']))


def main():
    queue = json.loads((OUT/'queue.json').read_text(encoding='utf-8-sig'))
    rows = []
    for campaign in queue['campaigns']:
        kind = 'paladin' if 'paladin' in campaign['work'] else 'cavalier'
        old_prefix = 'paladin-line' if kind == 'paladin' else 'cavalier'
        for job in campaign['jobs']:
            civ = job['civilization']
            old = result(ARCHIVE/f'{old_prefix}-{civ.lower()}',job['baselineJobId'])
            new = result(ARCHIVE/f'{kind}-leitis-four-relics-{civ.lower()}',job['jobId'])
            rows.append(dict(civilization=civ,group=kind,counts=job['counts'],
                             previous=old,corrected=new,winnerFlipped=old['winner']!=new['winner']))
    save(OUT/'comparison-report.json',dict(rows=rows,flips=sum(r['winnerFlipped'] for r in rows),
        metric='Winner remaining HP divided by that winner\'s starting HP; P2 featured cavalry, P3 Elite Leitis.',
        scope='One preserved battle and one corrected battle per pairing; only the Leitis +4 scenario condition changed.'))
    lines = ['# Elite Leitis four-relic retakes','',
             'All original recordings are preserved. Counts are featured cavalry / Leitis. Remaining HP is a percentage of the winning army\'s opening HP.','',
             '| Group | Civilization | Counts | Previous winner / HP | Corrected winner / HP | Winner changed |',
             '|---|---|---|---|---|---|']
    for r in rows:
        a,b=r['previous'],r['corrected']
        lines.append(f"| {r['group'].title()} | {r['civilization']} | {r['counts'][0]} / {r['counts'][1]} | {a['winnerLabel']} / {a['remainingPercent']:.1f}% | {b['winnerLabel']} / {b['remainingPercent']:.1f}% | {'Yes' if r['winnerFlipped'] else 'No'} |")
    lines += ['',f"Winner changes: {sum(r['winnerFlipped'] for r in rows)} of {len(rows)}.",'',
              'Full video paths, frame hashes and HP totals are saved in comparison-report.json. The Champi comparison is unchanged.']
    (OUT/'comparison-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))


if __name__=='__main__':
    main()
