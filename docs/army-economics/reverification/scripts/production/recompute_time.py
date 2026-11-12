import json,sqlite3,csv,math
exec(open('raw.py').read())
TT=json.load(open('online/data.json'))
shipw={civ for civ,c in TT['civs'].items() if c.get('era')=='base' and 373 in c['Tech']}
consc={civ for civ,c in TT['civs'].items() if c.get('era')=='base' and 315 in c['Tech']}
IMP={12:20,87:14,101:153,45:51,109:142}
def cmds(eid): return E[str(eid)]['effect_commands']
def unit_mults(eid):  # train-time multipliers (c=101,type5) -> list of (a,b,d)
    return [(x['a'],x['b'],x['d']) for x in cmds(eid) if x['c']==101 and x['type']==5]
def bld_mults(eid):
    return {x['a']:x['d'] for x in cmds(eid) if x['c']==13 and x['type'] in (5,15)}
TIME={  # civ -> effects with unit train-time multipliers
 'Magyars':[6],'Turks':[410],'Aztecs':[447],'Gurjaras':[843],'Khitans':[1011],'Mapuche':[1405,1406,1407],
 'Cumans':[726],'Romans':[895],'Muisca':[1366],'Portuguese':[1404],'Saxons':[1491]}
BLD={'Britons':[399],'Celts':[401],'Goths':[405,513],'Huns':[484],'Lithuanians':[713],'Persians':[421],'Franks':[548],'Berbers':[607]}
GENERIC_TIME=[511,102]  # eagle age3, castle-age DSERJEANT (applies to all civs)
def expected(civ,uid,bid,base):
    u=C[civ]['units'][str(uid)]; cls=u['class_id']
    t=base; notes=[]
    effs=TIME.get(civ,[])+GENERIC_TIME+([371] if civ in shipw else [])
    for e in effs:
        for a,b,dd in unit_mults(e):
            if a==uid or (a==-1 and b==cls):
                t*=dd; notes.append(f"{E[str(e)]['name']} x{dd:.4f}")
    rate=1.0; ib=IMP.get(bid,bid)
    if civ=='Malay' and bid==45: ib=1189
    for e in ([315] if civ in consc else [])+BLD.get(civ,[]):
        m=bld_mults(e)
        if ib in m: rate*=m[ib]; notes.append(f"{E[str(e)]['name']} work x{m[ib]:.4f}@{ib}")
    return t/rate, notes
if __name__=='__main__':
    db=sqlite3.connect('$MT_CHECKOUT/data/golden/army_context.db')
    out=[]
    for civ,uid,mode,pl in db.execute('select civ,unit_id,mode,payload from units order by civ,unit_id,mode'):
        p=json.loads(pl)
        for r in p['productionRoutes']:
            loc=[l for l in C[civ]['units'][str(r['trainedUnitId'])]['train_locations'] if l['unit_id']==r['id']]
            dat_base=loc[0]['train_time'] if loc else None
            exp,notes=expected(civ,r['trainedUnitId'],r['id'],r['baseTrainSeconds'])
            sel = p['production'].get('id')==r['id'] and p['production'].get('trainedUnitId')==r['trainedUnitId']
            out.append(dict(civ=civ,unit_id=uid,mode=mode,name=p['name'],trained=r['trainedUnitId'],building=r['name'],bid=r['id'],selected=int(sel),
               base_runtime=r['baseTrainSeconds'],base_dat_loc=dat_base,sec_runtime=r['secondsPerOrder'],sec_expected=exp,
               diff=r['secondsPerOrder']-exp,notes='; '.join(notes),
               runtime_mods='; '.join(f"{m.get('effect_name')}:{m.get('target')}:{round(m['command']['d'],4)}" for m in r['modifiers'])))
    w=csv.DictWriter(open('time_recompute.csv','w'),fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    bad=[o for o in out if abs(o['diff'])>1e-3 or (o['base_dat_loc'] is not None and o['base_dat_loc']!=o['base_runtime'])]
    print(len(out),'routes;',len(bad),'mismatches')
    for o in bad: print(o['civ'],o['name'],o['building'],o['trained'],'rt',round(o['sec_runtime'],3),'exp',round(o['sec_expected'],3),'|',o['notes'],'||',o['runtime_mods'])
