"""Choose ten Mounted Trebuchet Shorts from recorded outcomes and persisted unit costs."""
import argparse,json,sqlite3
from pathlib import Path
from overlay.battle_end import terminal_row
LAB=Path('aoe2x/js_simulation/calibration/lab').resolve()
OUT=LAB/'shorts/mounted-trebuchet-selected-10'

def main():
    p=argparse.ArgumentParser();p.add_argument('--early',action='store_true');a=p.parse_args()
    state=json.loads((LAB/'campaigns/mounted-trebuchet-all-unique-overlays/status.json').read_text())
    if not a.early:assert state['state']=='COMPLETE', 'All overlays must be verified before selection'
    inventory=[]
    for j in state['jobs']:
        run=LAB/'runs'/j['jobId']/'live/run_001';plan=json.loads((run.parent.parent/'plan.json').read_text());s=plan['side3']
        if (run/'unit-hp-overlay/units.json').exists():data=json.loads((run/'unit-hp-overlay/units.json').read_text())
        else:
            from overlay.unit_timeline import decode
            data=decode(run)
        if not a.early:assert data['mapping'].get('alignment')
        last=terminal_row(data['rows'])
        alive=[int(o) for o in ('2','3') if any(u['hp']>0 for u in last['sides'][o])];winner=alive[0] if len(alive)==1 else 0
        if (run/'static-stats-overlay/stats.json').exists():stats=json.loads((run/'static-stats-overlay/stats.json').read_text())['units'][1]['stats']
        else:
            from overlay.static_stats import resolve_stats,REPO
            with sqlite3.connect(f'file:{REPO / "data/golden/aoe2_reference.db"}?mode=ro',uri=True) as db:
                db.row_factory=sqlite3.Row;stats=resolve_stats(db,s)
        inventory.append(dict(subject='mounted-trebuchet',jobId=j['jobId'],unit=s['label'],civ=s['civ'],cost=s['weightedCost'],category=stats.get('unit_class_name','Special'),ranged=s['ranged'],winner=winner,winnerHp=sum(u['hp'] for u in last['sides'][str(winner)]) if winner else 0,run=str(run)))
    selected=[];used=set();notes=[]
    def add(x,reason):
        x=dict(x);n=len(selected)+1;x.update(number=n,reason=reason,output=str(OUT/f'{n:02}-{x["jobId"]}'));selected.append(x);used.add(x['jobId'])
    assert len(inventory)==33 and all(x['ranged'] for x in inventory), 'Ranged-only roster required'
    for label,predicate in [('foot archer',lambda x:x['category']=='Archer'),('mounted archer',lambda x:x['category']=='Cavalry Archer'),('siege',lambda x:'siege' in x['category'].lower())]:
        for winner,expensive in [(2,True),(3,False)]:
            choices=[x for x in inventory if predicate(x) and x['winner']==winner and x['jobId'] not in used]
            reason=('Most expensive '+label+' defeated') if expensive else ('Cheapest '+label+' loss')
            if choices:add(sorted(choices,key=lambda x:(-x['cost'] if expensive else x['cost'],x['unit']))[0],reason)
            else:notes.append('No eligible matchup for '+reason+'; an additional interesting matchup fills this slot.')
    for name,reason in [('Missionary','Conversion versus mobile siege'),('Houfnice','A duel between long-range siege units'),('Elite War Wagon','Durable ranged cavalry against fire pots'),('Elite Mameluke','Short-range mounted attackers closing the gap'),('Elite Longbowman','Long-range archers contesting siege reach'),('Elite Mangudai','Mobile archers with anti-siege attacks'),('Elite Chu Ko Nu','Dense volleys against mobile siege')]:
        if len(selected)>=10:break
        x=next((x for x in inventory if x['unit']==name),None)
        if x is None:continue
        if x['jobId'] not in used:add(x,reason)
    for x in sorted(inventory,key=lambda x:(x['winnerHp'],x['unit'])):
        if len(selected)>=10:break
        if x['jobId'] not in used:add(x,'Close finish: low remaining winner HP')
    assert len(selected)==10 and len(used)==10
    assert 'Missionary' in {x['unit'] for x in selected}
    assert all(x['unit']!='Mounted Trebuchet' for x in selected)
    notes.append('Ranged-only episode: melee categories and Flaming Camel are ineligible; foot archers, mounted archers, siege and other eligible ranged matchups fill the ten slots. Mounted Trebuchet self-match excluded.')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'inventory.json').write_text(json.dumps(inventory,indent=2))
    (OUT/'selection.json').write_text(json.dumps({'costBasis':'Recorded scenario food + wood + gold per unit, excluding upgrades. Game classes define foot archers, mounted archers and siege; every opponent must belong to the approved ranged-only roster. Actual gRPC ownership and HP determine winners.','notes':notes,'items':selected},indent=2))
    print(json.dumps({'items':[(x['unit'],x['reason']) for x in selected],'notes':notes}),flush=True)
if __name__=='__main__':main()
