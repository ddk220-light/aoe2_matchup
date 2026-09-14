"""Compare original and corrected recorded outcomes, never simulation predictions."""
import json
from pathlib import Path
from aoe2x.lab.io import write_json, utc_now
ROOT=Path(__file__).resolve().parents[2]
LAB=ROOT/'aoe2x/js_simulation/calibration/lab'
OUT=LAB/'campaigns/cost-repairs-v2'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def build():
    mapping=read(OUT/'replacement-map.json')['jobs']
    status=read(OUT/'status.json') if (OUT/'status.json').exists() else {}
    verified={r['jobId'] for r in status.get('results',[]) if r['status']=='verified'}
    rows=[]
    for pair in mapping:
        if pair['replacementJobId'] not in verified:continue
        oldroot=LAB/'runs'/pair['originalJobId'];newroot=LAB/'runs'/pair['replacementJobId']
        plan=read(oldroot/'plan.json')
        old=read(oldroot/'live/run_001/manifest.json')['capture']
        new=read(newroot/'live/run_001/manifest.json')['capture']
        def label(result):
            owner=result.get('winnerOwner')
            return plan['side2']['label'] if owner==2 else plan['side3']['label'] if owner==3 else result.get('outcome','Unknown')
        rows.append({**pair,'subject':plan['side2']['label'],'opponent':plan['side3']['label'],'opponentCiv':plan['side3']['civ'],'originalWinner':label(old),'correctedWinner':label(new),'winnerChanged':old.get('winnerOwner')!=new.get('winnerOwner'),'originalWinnerHp':old.get('winnerHp'),'correctedWinnerHp':new.get('winnerHp'),'originalWinnerHpPercent':old.get('winnerRemainingHpPercent'),'correctedWinnerHpPercent':new.get('winnerRemainingHpPercent'),'oldOutcome':old.get('outcome'),'newOutcome':new.get('outcome')})
    changed=[r for r in rows if r['winnerChanged'] and r['subject']!='Slinger']
    report={'state':'COMPLETE' if len(rows)==len(mapping) else 'IN_PROGRESS','updatedAt':utc_now(),'verifiedComparisons':len(rows),'total':len(mapping),'nonSlingerWinnerChanges':len(changed),'note':'Observed original versus corrected recorded battles. New unit counts are verified; single retakes can also differ through combat variation. Unfinished/failed captures are not classified.','rows':rows}
    write_json(OUT/'winner-comparison.json',report)
    lines=['# Corrected matchup winner report','',f"{len(rows)}/{len(mapping)} verified comparisons. Status: {report['state']}.",'',report['note'],'','Inca Slinger has a separate full-video rebuild. Other observed winner changes:','','| Subject | Opponent | Old counts | Corrected counts | Original winner | Corrected winner | New winner HP |','|---|---|---|---|---|---|---:|']
    for r in changed:lines.append(f"| {r['subject']} | {r['opponentCiv']} — {r['opponent']} | {r['oldCounts']} | {r['expectedCounts']} | {r['originalWinner']} | {r['correctedWinner']} | {r['correctedWinnerHp']} |")
    if not changed:lines.append('| No observed changes so far | | | | | | |')
    lines+=['','The JSON contains every completed comparison, including unchanged winners and Inca Slinger. No uploaded video has been altered.']
    (OUT/'winner-comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return report
if __name__=='__main__':
    r=build();print(json.dumps({k:v for k,v in r.items() if k!='rows'}))
