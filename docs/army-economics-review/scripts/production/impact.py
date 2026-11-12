import json,sqlite3,math,sys,copy
MT='/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/mt'
sys.path.insert(0,MT)
from aoe2x.army_economics import select_investment_route, purchase_bill, compiled_labor, weighted_cost, add_costs
db=sqlite3.connect(MT+'/data/golden/army_context.db')
civs={c:json.loads(p) for c,p in db.execute('select civ,payload from civilizations')}
def unit(civ,name):
    for pl, in db.execute('select payload from units where civ=?',(civ,)):
        p=json.loads(pl)
        if p['name']==name: return p
def headline(p,routes,cost=None,count=27,rebate=None):
    cost=cost or p['pricing']['purchaseCost']; batch=p['pricing']['unitsPerPurchase']
    b=purchase_bill(count,cost,batch); prices=civs[p['civ']]['laborPrices']
    if rebate:
        routes=copy.deepcopy(routes)
        for r in routes:
            if r['id'] in rebate[0]: r['cost']['food']-=rebate[1]  # negative food = rebate (only for labor eval)
    prod,_=select_investment_route(routes,b['orders'],batch,b['cost'],prices)
    if prod['status']!='modeled': return prod['status']
    lab=compiled_labor(weighted_cost(add_costs(b['cost'],prod['investmentCost'])),prices)
    return dict(route=prod['name'],sec=round(prod['secondsPerOrder'],2),opb=prod['ordersPerBuilding'],n=prod['buildingCount'],bld=prod['investmentCost'],vm=round(lab['villagerMinutes'],2))
def show(label,civ,name,fn):
    p=unit(civ,name); a=headline(p,p['productionRoutes']); b=fn(p)
    print(f"{label}: {civ} {name}\n   dataset: {a}\n   corrected: {b}")
    if isinstance(a,dict) and isinstance(b,dict): print(f"   delta VM {b['vm']-a['vm']:+.2f} ({100*(b['vm']-a['vm'])/a['vm']:+.1f}%)")
# 1 Persians docks
for nm in ('Galleon','Fast Fire Ship','Heavy Demo Ship','Elite Cannon Galleon','Carrack'):
    def f(p):
        rs=copy.deepcopy(p['productionRoutes'])
        for r in rs: r['secondsPerOrder']=r['secondsPerOrder']*1.05/1.2
        return headline(p,rs)
    show('Persian dock',"Persians",nm,f)
    p=unit('Persians',nm); ch=[]
    for c in range(1,28):
        rs=copy.deepcopy(p['productionRoutes']); 
        for r in rs: r['secondsPerOrder']*=1.05/1.2
        A=headline(p,p['productionRoutes'],count=c); B=headline(p,rs,count=c)
        if A['n']!=B['n']: ch.append((c,A['n'],B['n']))
    print('   counts where building count changes:',ch)
# 2 Armenian warrior priest
def f(p):
    rs=copy.deepcopy(p['productionRoutes']); rs[0]['cost']['wood']=200; rs[0]['name']='Fortified Church'; return headline(p,rs)
show('Fortified Church','Armenians','Warrior Priest',f)
# 3 Mapuche skirm/halb
for nm,bid,bname in (('Elite Skirmisher',87,'Archery Range'),('Halberdier',12,'Barracks')):
    def f(p,bid=bid,bname=bname):
        rs=[r for r in copy.deepcopy(p['productionRoutes']) if r['id']!=1665]
        alt=copy.deepcopy(rs[0]); alt.update(id=bid,name=bname,secondsPerOrder=22/1.3300000429153442,cost={'food':0,'wood':175,'gold':0,'stone':0})
        return headline(p,rs+[alt])
    show('Mapuche route','Mapuche',nm,f)
# 4 Kona
def f(p): return headline(p,p['productionRoutes'],cost={'food':55,'wood':0,'gold':34,'stone':0})
show('Butalmapu','Mapuche','Elite Kona',f)
# 5 Wu rebate
for nm in ('Halberdier','Champion','Arbalester','Heavy Hei-Kuang Cavalry','Jian Swordsman','Onager','Galleon'):
    show('Wu +55F','Wu',nm,lambda p: headline(p,p['productionRoutes'],rebate=({12,87,101,49,45},55)))
