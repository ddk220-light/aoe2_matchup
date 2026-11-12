"""Rebuild the reviewer's dataset_civ_tech.csv flattening from a runtime DB (adapted for re-verification)."""
import csv, json, os, sqlite3, sys
RUNTIME=sys.argv[1]; OUT=sys.argv[2]
SNAP='/home/user/aoe2_matchup/data/army_economics/sources/army-context-2026-11-10/army-context.sqlite'
s=sqlite3.connect(SNAP); s.row_factory=sqlite3.Row
base={(r['civ_name'],r['tech_id']):r for r in s.execute('select * from research_civilization_upgrades')}
raw={r['tech_id']:json.loads(r['definition']) for r in s.execute('select * from research_raw_technologies')}
loc={(r['civ_name'],r['tech_id'],r['building_id']):r for r in s.execute('select * from research_research_locations')}
db=sqlite3.connect(RUNTIME)
seen={}
for civ,p in db.execute('select civ,payload from units'):
    p=json.loads(p)
    for pkg in ('military','production'):
        for t in p['research'][pkg]['technologies']:
            seen.setdefault((civ,t['id']),t)
rows=[]
for (civ,tid),t in sorted(seen.items()):
    b=base.get((civ,tid))
    if b is not None: bc={k:b['base_'+k] for k in ('food','wood','gold','stone')}
    else:
        bc={'food':0.,'wood':0.,'gold':0.,'stone':0.}
        for rc in raw[tid]['resource_costs']:
            if rc['type'] in (0,1,2,3) and rc['flag']: bc[{0:'food',1:'wood',2:'stone',3:'gold'}[rc['type']]]+=rc['amount']
    bld=(t.get('building') or {})
    l=loc.get((civ,tid,bld.get('id')))
    rows.append(dict(civ=civ,tech_id=tid,tech=t['name'],building=bld.get('name'),free=int(t['automaticFree']),auto=int(t['automaticFree']),
        **{'base_'+k[0]:bc[k] for k in ('food','wood','gold','stone')},
        **{'up_'+k[0]:t['upfront'][k] for k in ('food','wood','gold','stone')},
        **{'rw_'+k[0]:t['refund'][k] for k in ('food','wood','gold','stone')},
        base_sec=t['baseSeconds'],final_sec=t['seconds'],work_rate=(l['final_work_rate'] if l else ''),wr_techs=(l['work_rate_tech_ids'] if l else '[]'),
        modified_sec=(l['modified_seconds'] if l else ''),cost_mod_techs=json.dumps(t['pricingTechnologyIds']),fixed=int(t['costIsFixed'])))
w=csv.DictWriter(open(OUT,'w'),fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows),'civ-tech rows')
