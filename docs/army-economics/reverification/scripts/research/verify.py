import sys,os,json,csv,sqlite3,random,collections,math
HERE=os.path.dirname(os.path.abspath(__file__)); BASE=os.path.dirname(HERE)
sys.path.insert(0,HERE); import indep
MT='/home/user/aoe2_matchup'; sys.path.insert(0,MT)
from aoe2x.economy import accounting as AE
RUNTIME=os.environ['RUNTIME_DB']; SNAP=MT+'/data/army_economics/sources/army-context-2026-11-10/army-context.sqlite'
R=('food','wood','gold','stone'); K=dict(zip(R,'fwgs'))
db=sqlite3.connect(f'file:{RUNTIME}?mode=ro',uri=True)
units={}
for civ,uid,mode,p in db.execute("select civ,unit_id,mode,payload from units"):
    units[(civ,uid,mode)]=json.loads(p)
civs={c:json.loads(p) for c,p in db.execute("select civ,payload from civilizations")}
ref=sqlite3.connect('/home/user/aoe2_matchup/data/golden/aoe2_reference_simulation.db')
uclass={(c,m):(cn or str(cl)) for c,m,cl,cn in ref.execute("select civ_name,unit_master,unit_class,unit_class_name from ref_units")}
O=indep.O
def ind_tech(civ,t):
    """independent version of a dataset tech dict"""
    tid=t['id']
    if tid==1350:  # Champi Scout: hidden free tech, not in aoe2techtree
        return dict(id=tid,seconds=0.0,upfront={r:0. for r in R},refund={r:0. for r in R},net={r:0. for r in R},building=t.get('building'),costIsFixed=True)
    bld=(t.get('building') or {}).get('name')
    up,rw,sec,notes=indep.expected(civ,tid,bld)
    upd={r:up[K[r]] for r in R}
    if tid==755: upd={'food':200.,'wood':0.,'gold':150.,'stone':0.}
    free=all(v==0 for v in upd.values()) and sec==0
    refund={r:0. for r in R}
    if not free: refund['gold']=rw
    if t.get('automaticFree'): refund={r:0. for r in R}
    return dict(id=tid,seconds=sec,upfront=upd,refund=refund,net={r:upd[r]-refund[r] for r in R},building=t.get('building'),costIsFixed=tid!=755)
MISSING={  # tech additions an independent reviewer expects (aoe2techtree base, Imperial)
 'Winged Hussar':786,}
def unit_class(civ,p):
    return uclass.get((civ,p['sourceUnitId'])) or uclass.get((civ,p['unitId'])) or '?'

def cls(civ,p):
    c=unit_class(civ,p); return 'Warship' if c=='Unknown' else c

def close(a,b,tol=0.011): return (a is None and b is None) or (a is not None and b is not None and abs(a-b)<=tol)

def ind_totals(civ,techs):
    return AE.research_totals([ind_tech(civ,t) for t in techs])

def compare_unit_totals():
    out=[]
    for (civ,uid,mode),p in sorted(units.items()):
        techs=p['research']['military']['technologies']
        ds=p['research']['military']['totals']; ix=ind_totals(civ,techs)
        for kind in ('upfront','refund','net'):
            for r in R:
                out.append((civ,f"{p['name']} [{uid}/{mode}] military package",f'{kind}_{r}',ds[kind][r],ix[kind][r]))
        out.append((civ,f"{p['name']} [{uid}/{mode}] military package",'workload_seconds',ds['workloadSeconds'],ix['workloadSeconds']))
        out.append((civ,f"{p['name']} [{uid}/{mode}] military package",'technology_count',ds['technologyCount'],ix['technologyCount']))
    return out

def sample_pairs(n_per_civ=6,seed=20261112):
    rnd=random.Random(seed)
    keys=sorted(units)
    bycivname=collections.defaultdict(list)
    for k in keys: bycivname[units[k]['name']].append(k)
    pairs=[]; seen=set()
    civlist=sorted(civs)
    for civ in civlist:
        own=[k for k in keys if k[0]==civ]
        for i in range(n_per_civ):
            a=rnd.choice(own)
            if i%2==0:  # same-name opponent from another civ when possible (mirror: largest common set)
                cands=[k for k in bycivname[units[a]['name']] if k[0]!=civ]
                b=rnd.choice(cands) if cands else rnd.choice(keys)
            elif i%3==0:  # same civ, different unit
                b=rnd.choice([k for k in own if k!=a] or own)
            else:
                b=rnd.choice(keys)
            if (a,b) in seen: continue
            seen.add((a,b)); pairs.append((a,b))
    # class coverage
    classes=collections.defaultdict(list)
    for k in keys: classes[cls(k[0],units[k])].append(k)
    covered={cls(k[0],units[k]) for p in pairs for k in p}
    for c,ks in sorted(classes.items()):
        if c not in covered or True:
            for _ in range(2):
                a=rnd.choice(ks); b=rnd.choice(ks)
                if (a,b) not in seen: seen.add((a,b)); pairs.append((a,b))
    # explicit pairs exercising the missing-tech findings
    extra=[(('Poles',1707,'default'),('Lithuanians',1707,'default')),(('Danes',567,'default'),('Danes',359,'default')),
           (('Saxons',567,'default'),('Saxons',2706,'default')),(('Shu',359,'default'),('Shu',1961,'default')),
           (('Khitans',441,'default'),('Khitans',1372,'default')),(('Teutons',567,'default'),('Teutons',554,'default')),
           (('Georgians',283,'default'),('Georgians',1805,'default')),(('Franks',569,'default'),('Teutons',569,'default')),
           (('Spanish',567,'default'),('Chinese',567,'default')),(('Magyars',441,'default'),('Turks',441,'default'))]
    for e in extra:
        if all(x in units for x in e) and e not in seen: seen.add(e); pairs.append(e)
    return pairs

def pair_compare(a,b):
    ta=units[a]['research']['military']['technologies']; tb=units[b]['research']['military']['technologies']
    ds=AE.compare_research(ta,tb)
    ix=AE.compare_research([ind_tech(a[0],t) for t in ta],[ind_tech(b[0],t) for t in tb])
    return ds,ix

# ---- Missing technologies (independent finding) ----
def class_num(civ,uid):
    r=ref.execute("select unit_class from ref_units where civ_name=? and unit_master=?",(civ,uid)).fetchone()
    return r[0] if r else None
MISSING_RULES=[  # (civ, tech id, name, base cost, base secs, unit predicate)
 ('Poles',786,'Winged Hussar',{'food':600,'gold':800},60,'Stable',lambda civ,uid,p: uid==1707),
 ('Lithuanians',786,'Winged Hussar',{'food':600,'gold':800},60,'Stable',lambda civ,uid,p: uid==1707),
 ('Danes',1484,'Hamask',{'food':250,'gold':450},35,'Castle',lambda civ,uid,p: class_num(civ,p['sourceUnitId'])==6),
 ('Saxons',1464,'Shield Wall',{'food':525,'gold':475},45,'Castle',lambda civ,uid,p: class_num(civ,p['sourceUnitId'])==6),
 ('Khitans',1007,'Ordo Cavalry',{'food':600,'gold':300},45,'Castle',lambda civ,uid,p: class_num(civ,p['sourceUnitId'])==12 and uid!=1923),
 ('Mapuche',1380,'Butalmapu',{'food':500,'gold':450},45,'Castle',lambda civ,uid,p: uid in (2568,2567)),
 ('Wu',1080,'Red Cliff Tactics',{'food':400,'gold':250},40,'Castle',lambda civ,uid,p: p['name'] in ('Demo Ship','Heavy Demo Ship','Demolition Ship','Heavy Demolition Ship','Demolition Raft')),
 ('Shu',1070,'Coiled Serpent Array',{'food':350,'gold':300},40,'Castle',lambda civ,uid,p: p['name'] in ('Halberdier','Pikeman','Spearman','Elite White Feather Guard','White Feather Guard')),
]
def missing_tech(civ,tid,name,cost,secs,bld):
    up={r:float(cost.get(r,0)) for r in R}
    if civ=='Poles' and tid==786: up['food']*=0.5
    wr=1.33
    return dict(id=tid,name=name,seconds=secs/wr,upfront=up,refund={r:0. for r in R},net=dict(up),building={'name':bld},costIsFixed=True,automaticFree=False)
def corrected_techs(key):
    civ,uid,mode=key; p=units[key]; techs=list(p['research']['military']['technologies'])
    added=[]
    for c,tid,name,cost,secs,bld,pred in MISSING_RULES:
        if c==civ and pred(civ,uid,p) and tid not in {t['id'] for t in techs}:
            t=missing_tech(civ,tid,name,cost,secs,bld); techs.append(t); added.append(t)
    return techs,added

def headline(key,common_net,count=20):
    """Re-evaluate the runtime headline for one side with a given common research net bill."""
    p=units[key]; civ=key[0]; prices=civs[civ]['laborPrices']
    start=p['lookup'][count]
    prod,_=AE.select_investment_route(p['productionRoutes'],start['orders'],p['pricing']['unitsPerPurchase'],AE.add_costs(start['cost'],common_net),prices)
    inv=AE.army_investment(start['cost'],prod,{'net':common_net,'costIsFixed':True},prices)
    return inv['labor']['villagerMinutes'] if inv['labor'] else None

def raw_base():
    c=sqlite3.connect(f'file:{SNAP}?mode=ro',uri=True)
    out={}
    for tid,d in c.execute("select tech_id,definition from research_raw_technologies"):
        d=json.loads(d); cost={'food':0.,'wood':0.,'gold':0.,'stone':0.}
        for rc in d['resource_costs']:
            if rc['type'] in (0,1,2,3) and rc['flag']: cost[{0:'food',1:'wood',2:'stone',3:'gold'}[rc['type']]]+=rc['amount']
        out[tid]=(cost,[l['research_time'] for l in d.get('research_locations',[])])
    return out
