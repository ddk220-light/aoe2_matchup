"""Refresh the local, source-linked Comp4 capture and four-arena result report."""
import argparse,datetime,html,json
from pathlib import Path
from build_comp4_scenario import ROOT

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'data/local/comp4-champi-all-unique')
    args=parser.parse_args();directory=args.directory
    manifest=json.loads((directory/'manifest.json').read_text());state=json.loads((directory/'status.json').read_text())
    rows=[];body=[]
    for job in manifest['jobs']:
        found=state['completed'].get(job['id']);error=state['failed'].get(job['id'])
        for pair in job['pairs']:
            p=str(['Incas','Mapuche','Muisca','Tupi'].index(pair['civ'])+1)
            result=found and found['pairs'].get(p)
            label='Verified' if result else 'Failed' if error else 'Capturing' if (state.get('active') or {}).get('id')==job['id'] else 'Pending'
            won=result and result['winnerOwner']==int(p)
            outcome=('Draw' if result['winnerOwner'] is None else 'Victory' if won else 'Defeat') if result else ''
            hp=result['subject' if won else 'opponent']['hp'] if result else None
            denominator=pair['subjectCount']*([65,80,65,65][int(p)-1]) if won else sum(pair['opponentHP'])
            percent=round(hp/denominator*100,2) if hp is not None else None
            row={'job':job['id'],'opponent':job['opponent']['label'],'opponentCiv':job['opponent']['civ'],
                 'champiCiv':pair['civ'],'status':label,'subjectCount':pair['subjectCount'],
                 'opponentHP':pair['opponentHP'],'outcome':outcome,'winnerHpPercent':percent,
                 'endGameSeconds':result['endGameSeconds'] if result else None,'capture':found['capture'] if found else None}
            rows.append(row)
            cells=[row['opponentCiv']+' / '+row['opponent'],row['champiCiv'],label,str(row['subjectCount']),
                   ', '.join(f'{v:g}' for v in row['opponentHP']),outcome,'' if percent is None else f'{percent:g}%',
                   '' if not result else f"{result['endGameSeconds']:.3f}s"]
            body.append('<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in cells)+'</tr>')
    report={'updated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'state':state['state'],'total':manifest['total'],
            'verified':len(state['completed']),'failed':len(state['failed']),'rows':rows}
    (directory/'report.json').write_text(json.dumps(report,indent=2))
    page='''<!doctype html><meta charset="utf-8"><title>Champi four-civilization capture report</title>
<style>body{font:16px system-ui;background:#171a1f;color:#edf0ee;margin:40px}p{max-width:1050px;line-height:1.5}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid #39414b;padding:10px;text-align:left}th{position:sticky;top:0;background:#29313a}tr:hover{background:#252c33}</style>
<h1>Champi Warrior · four-civilization recordings</h1>'''
    page+=f"<p>{report['verified']} / {report['total']} verified recordings · {report['failed']} failed · {html.escape(report['state'])}. Updated {report['updated']}.</p>"
    page+='<p>Eight-unit cap; no buffer. The most expensive Champi variant sets the integer reference counts. Incas’ 60/75 cost ratio scales that reference opponent HP pool, retaining a partially injured final unit. This is the approved HP handicap, not exact purchase-cost equality. Winner HP uses that side’s actual opening HP pool. A defeat reports the enemy’s remaining HP. Each recording retains full raw video, length-prefixed gRPC frames, timestamped HP, scenario, cost evidence and validation.</p>'
    page+='<table><thead><tr>'+''.join('<th>'+v+'</th>' for v in ['Opponent','Champi civ','Capture','Champi count','Opponent opening HP','Result','Winner HP left','Game end'])+'</tr></thead><tbody>'+''.join(body)+'</tbody></table>'
    (directory/'report.html').write_text(page,encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))

if __name__=='__main__':main()
