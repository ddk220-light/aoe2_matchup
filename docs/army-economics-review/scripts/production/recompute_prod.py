import json,sqlite3,math,sys,csv
MT='/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/mt'
sys.path.insert(0,MT)
from aoe2x.army_economics import select_investment_route, purchase_bill
db=sqlite3.connect(MT+'/data/golden/army_context.db')
civs={c:json.loads(p) for c,p in db.execute('select civ,payload from civilizations')}
W={'food':1,'wood':1,'gold':1.5,'stone':3}
R=('food','wood','gold','stone')
def labor(bill,prices):
    v=[bill.get(r,0)*W[r] for r in R]
    if all(x<=0 for x in v): return 0.0
    if prices is None: return None
    return max(0.0,max(sum(a*b for a,b in zip(v,row)) for row in prices))
def mine(routes,count,batch,cost,prices):
    orders=math.ceil(count/batch)
    best=None; res=[]
    for r in routes:
        sec=r['secondsPerOrder']; opb=int(60//sec) if sec<=60 else 0
        # guard float: floor(60/sec)
        opb=math.floor(60/sec)
        if opb==0: res.append((r,None)); continue
        n=math.ceil(orders/opb) if orders else 0
        bill={k:cost[k]*orders+r['cost'][k]*n for k in R}
        lab=labor(bill,prices)
        key=(lab if lab is not None else sum(r['cost'][k]*W[k] for k in R)*n, math.ceil(orders/n)*sec if n else 0, r['id'], r['trainedUnitId'])
        res.append((r,(opb,n,key)))
    feas=[x for x in res if x[1]]
    if not feas: return None
    r,(opb,n,key)=min(feas,key=lambda x:x[1][2])
    return dict(id=r['id'],trained=r['trainedUnitId'],opb=opb,n=n,orders=orders,q=key[1])
out=[];mism=0;checked=0
for civ,uid,mode,pl in db.execute('select civ,unit_id,mode,payload from units'):
    p=json.loads(pl); pr=p['pricing']; batch=pr['unitsPerPurchase']; cost=pr['purchaseCost']
    prices=civs[civ]['laborPrices']
    # stored production for 27
    st=p['production']
    m=mine(p['productionRoutes'],27,batch,cost,prices)
    for count in range(1,28):
        mm=mine(p['productionRoutes'],count,batch,cost,prices)
        b=purchase_bill(count,{k:cost[k] for k in R},batch)
        ds,_=select_investment_route(p['productionRoutes'],b['orders'],batch,b['cost'],prices)
        checked+=1
        if (mm is None) != (ds['status']!='modeled') or (mm and (mm['id'],mm['trained'],mm['opb'],mm['n'])!=(ds['id'],ds['trainedUnitId'],ds['ordersPerBuilding'],ds['buildingCount'])):
            mism+=1; print('MISMATCH',civ,p['name'],count,mm,ds.get('id'),ds.get('ordersPerBuilding'),ds.get('buildingCount'),ds['status'])
    stored=(st.get('id'),st.get('ordersPerBuilding'),st.get('buildingCount')) if st['status']=='modeled' else None
    mineT=(m['id'],m['opb'],m['n']) if m else None
    if stored!=mineT: print('STORED MISMATCH',civ,p['name'],stored,mineT)
    out.append(dict(civ=civ,unit_id=uid,mode=mode,name=p['name'],batch=batch,orders27=math.ceil(27/batch),
        route=st.get('name'),sec=st.get('secondsPerOrder'),opb_rt=st.get('ordersPerBuilding'),n_rt=st.get('buildingCount'),
        opb_exp=m and m['opb'],n_exp=m and m['n'],status=st['status']))
csv.DictWriter(open('prod_recompute.csv','w'),fieldnames=list(out[0])).writeheader()
w=csv.DictWriter(open('prod_recompute.csv','a'),fieldnames=list(out[0])); w.writerows(out)
print('unit-counts checked',checked,'mismatches',mism)
