import sqlite3,json,csv,sys
MT='/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/mt'
db=sqlite3.connect(MT+'/data/golden/army_context.db')
out=[]
for civ,uid,mode,pl in db.execute('select civ,unit_id,mode,payload from units order by civ,unit_id,mode'):
    p=json.loads(pl); pr=p['production']; pc=p['pricing']
    mods=[]
    for m in pr.get('modifiers') or []:
        mods.append(f"{m.get('effect_name')}[{m.get('effect_id')}]:{m.get('target')}:{m['command']['type']}:{round(m['command']['d'],4)}")
    out.append(dict(civ=civ,uid=uid,mode=mode,name=p['name'],slug=p['slug'],src=p['sourceUnitId'],
      batch=pc['unitsPerPurchase'],pf=pc['purchaseCost']['food'],pw=pc['purchaseCost']['wood'],pg=pc['purchaseCost']['gold'],ps=pc['purchaseCost']['stone'],
      sf=pc['sourceCost']['food'],sw=pc['sourceCost']['wood'],sg=pc['sourceCost']['gold'],ss=pc['sourceCost']['stone'],cond=pc['conditionalMultiplier'],
      status=pr.get('status'),bid=pr.get('id'),bname=pr.get('name'),trained=pr.get('trainedUnitId'),base=pr.get('baseTrainSeconds'),sec=pr.get('secondsPerOrder'),
      opb=pr.get('ordersPerBuilding'),nb=pr.get('buildingCount'),bcost=json.dumps(pr.get('cost')),qsec=pr.get('trainingSeconds'),
      nroutes=len(p['productionRoutes']),routes='|'.join(f"{r['name']}#{r['id']}:{r['baseTrainSeconds']}->{round(r['secondsPerOrder'],3)}" for r in p['productionRoutes']),
      mods=' ; '.join(mods), formid=json.dumps(pr.get('formIdentity'))))
w=csv.DictWriter(open('runtime_units.csv','w'),fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print(len(out))
import collections
print(collections.Counter(r['status'] for r in out))
print(collections.Counter(r['batch'] for r in out))
for r in out:
    if r['status']!='modeled': print(r['civ'],r['uid'],r['name'],r['status'],r['routes'])
