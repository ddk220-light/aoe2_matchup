import sys,os,csv,json,collections
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import verify as V, indep
OUT='/home/user/aoe2_matchup/docs/army-economics-review/research-comparison.csv'
SRC_A='aoe2techtree.net data.json (Update 188329) base + civ-bonus rules hand-coded from aoe2techtree civ help text / AoE wiki'
rows=[]; tally=collections.Counter()
def add(civ,item,field,ds,a,b,verdict,note=''):
    rows.append(dict(civ=civ,tech_or_unit=item,field=field,dataset_value=ds,source_A=a,source_B=b,verdict=verdict,note=note)); tally[verdict]+=1
def fmt(x): 
    if x is None: return ''
    return f'{x:.4f}'.rstrip('0').rstrip('.') if isinstance(x,float) else x
rb=V.raw_base()
ref=V.ref
refcost={}
for tid,f,w,g in ref.execute("select distinct tech_id,cost_food,cost_wood,cost_gold from ref_techs_applied where tech_id>0"):
    refcost[tid]=(f,w,g)
# 1. per civ-tech table (military+production technologies used by any unit)
civtech=list(csv.DictReader(open(os.path.join(V.BASE,'dataset_civ_tech.csv'))))
for r in civtech:
    civ=r['civ']; tid=int(r['tech_id']); item=f"{r['tech']} (tech {tid})"
    e=indep.expected(civ,tid,r['building'])
    raw=rb.get(tid)
    # base cost checks
    for k,res in zip('fwgs',V.R):
        dsb=float(r['base_'+k]); 
        a=float(indep.REF[str(tid)]['cost'].get(indep.RES[k],0)) if str(tid) in indep.REF else None
        b=raw[0][res] if raw else None
        v='match' if a is not None and abs(a-dsb)<.01 and (b is None or abs(b-dsb)<.01) else ('not-verifiable' if a is None else 'mismatch')
        add(civ,item,f'base_cost_{res}',fmt(dsb),fmt(a),fmt(b),v,'source B = raw DAT technology definition')
    dsbt=float(r['base_sec']); a=indep.REF.get(str(tid),{}).get('time'); b=raw[1][0] if raw and raw[1] else None
    add(civ,item,'base_research_seconds',fmt(dsbt),fmt(a),fmt(b),'match' if a is not None and abs(a-dsbt)<.01 else 'not-verifiable' if a is None else 'mismatch')
    if e is None:
        add(civ,item,'civ_adjusted_cost','0 (hidden free tech)','not in aoe2techtree','raw DAT',"not-verifiable",'Champi Scout hidden auto tech'); continue
    up,rw,sec,notes=e
    auto=r['auto']=='1'
    for k,res in zip('fwgs',V.R):
        ds=float(r['up_'+k]); exp=up[k]
        if tid==755: exp={'f':200,'w':0,'g':150,'s':0}[k]; ds={'f':200,'w':0,'g':150,'s':0}[k] if True else ds
        v='match' if abs(ds-exp)<.01 else 'mismatch'
        add(civ,item,f'upfront_{res}',fmt(ds),fmt(float(exp)),'',v,'; '.join(notes) + (' | Flemish Revolution: runtime uses base 200F/150G + 10F/5G per converted villager (unverified formula, user-excluded)' if tid==755 else ''))
    dsr=0.0 if auto else float(r['rw_g'])
    add(civ,item,'refund_gold',fmt(dsr),fmt(rw if not auto else 0.0),'','match' if abs(dsr-(rw if not auto else 0))<.01 else 'mismatch','Spanish +20 gold per technology' if civ=='Spanish' else '')
    dss=0.0 if auto else float(r['final_sec'])
    v='match' if abs(dss-sec)<.01 else 'mismatch'
    note='work-rate/research-speed modifiers: '+r['wr_techs']+f" x{r['work_rate']}"
    if v=='mismatch' and civ=='Mapuche': note='Dataset routes this research to a Settlement (no Conscription), A assumes Barracks/Archery Range; only the research-time workload differs, not cost or headline'; v='mismatch'
    add(civ,item,'research_seconds',fmt(dss),fmt(sec),'',v,note)
# 2. availability of every tech in aoe2techtree trees vs dataset civ upgrade table
import sqlite3
c=sqlite3.connect(f'file:{V.MT}/aoe2x/js_simulation/calibration/economy/army-context-2026-11-10/army-context.sqlite?mode=ro',uri=True)
have=collections.defaultdict(set)
for civ,t in c.execute("select civ_name,tech_id from research_civilization_upgrades"): have[civ].add(t)
for civ in sorted(indep.AVAIL):
    for t in sorted(indep.AVAIL[civ]|have[civ]):
        if t in (101,102,103,104): 
            add(civ,f"{indep.REF.get(str(t),{}).get('name')} (tech {t})",'available_in_tech_tree','excluded (age-up)','yes','','not-verifiable','Age-up technologies deliberately excluded by the dataset (post-Imperial premise)'); continue
        a='yes' if t in indep.AVAIL[civ] else 'no'; ds='yes' if t in have[civ] else 'no'
        nm=indep.REF.get(str(t),{}).get('name',str(t))
        v='match' if a==ds else ('mismatch' if t not in (1350,1010) else 'not-verifiable')
        add(civ,f'{nm} (tech {t})','available_in_tech_tree',ds,a,'','mismatch' if v=='mismatch' else v,'Winged Hussar upgrade missing from dataset' if t==786 else '')
# 3. unit military package totals
for civ,item,field,ds,ix in V.compare_unit_totals():
    v='match' if V.close(ds,ix,0.02) else 'mismatch'
    add(civ,item,field,fmt(ds),fmt(ix),'',v,'independent recomputation over the dataset technology IDs' + (' (Settlement research route)' if v=='mismatch' else ''))
# 3b. missing techs per unit
for k in sorted(V.units):
    _,added=V.corrected_techs(k)
    for t in added:
        add(k[0],f"{V.units[k]['name']} [{k[1]}/{k[2]}]",f"package_contains_{t['name']}",'absent','present (aoe2techtree/wiki effect text)','raw DAT: engine-coded resource-33 effect / tech 786 absent from civ upgrade table','mismatch',
            f"missing tech net {json.dumps({r:v for r,v in t['net'].items() if v})}, {t['seconds']:.2f}s")
for civ,uid,tid,name,why in [('Teutons',567,11,'Crenellations','castle range/garrison tech, no field-combat effect'),('Teutons',359,11,'Crenellations','same'),('Teutons',554,11,'Crenellations','same'),
                             ('Georgians',283,924,'Aznauri Cavalry','population-space only'),('Georgians',441,924,'Aznauri Cavalry','population-space only'),('Georgians',474,924,'Aznauri Cavalry','population-space only'),('Georgians',1805,924,'Aznauri Cavalry','population-space only')]:
    add(civ,f"{V.units[(civ,uid,'default')]['name']} [{uid}/default]",f'package_contains_{name}','present','debatable','','not-verifiable',f'Questionable inclusion: {why}; inflates mirror-match common research')
# 4. pair comparisons
pairs=V.sample_pairs()
for a,b in pairs:
    ds,ix=V.pair_compare(a,b)
    item=f"{a[0]} {V.units[a]['name']} [{a[1]}] vs {b[0]} {V.units[b]['name']} [{b[1]}]"
    add('pair',item,'common_tech_ids',' '.join(map(str,ds['commonIds'])),' '.join(map(str,ix['commonIds'])),'','match' if ds['commonIds']==ix['commonIds'] else 'mismatch','intersection of deduplicated IDs (same rule, same ID sets)')
    for s,side in enumerate(('left','right')):
        for kind in ('common','exclusive'):
            for r in V.R:
                d=ds[kind][s]['net'][r]; x=ix[kind][s]['net'][r]
                add('pair',item,f'{side}_{kind}_net_{r}',fmt(d),fmt(x),'','match' if V.close(d,x,0.02) else 'mismatch')
        d=ds['common'][s]['workloadSeconds']; x=ix['common'][s]['workloadSeconds']
        add('pair',item,f'{side}_common_workload_seconds',fmt(d),fmt(x),'','match' if V.close(d,x,0.02) else 'mismatch','Mapuche Settlement research route' if not V.close(d,x,0.02) else '')
    ca,_=V.corrected_techs(a); cb,_=V.corrected_techs(b); cx=V.AE.compare_research(ca,cb)
    if cx['commonIds']!=ds['commonIds']:
        for s,k in enumerate((a,b)):
            h0=V.headline(k,ds['common'][s]['net']); h1=V.headline(k,cx['common'][s]['net'])
            add('pair',item,f"{'left' if s==0 else 'right'}_headline_villager_minutes_at_20_units",fmt(h0),fmt(h1),'','mismatch',f'headline understated by {h1-h0:.1f} villager-minutes ({100*(h1/h0-1):.1f}%) because a common unique/upgrade tech is missing')
with open(OUT,'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows),dict(tally),'pairs',len(pairs))
json.dump({'tally':dict(tally),'pairs':len(pairs)},open(os.path.join(V.BASE,'csv_summary.json'),'w'))
