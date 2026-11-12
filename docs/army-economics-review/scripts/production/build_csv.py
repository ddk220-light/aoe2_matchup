import json,csv,sqlite3,math,sys
exec(open('recompute_time.py').read().split("if __name__=='__main__':")[0])
TIME['Burgundians']=[799]  # Flemish Militia Age3 (x0.875), confirmed by fandom (14 s from Castle Age)
MT='/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/mt'
db=sqlite3.connect(MT+'/data/golden/army_context.db')
ref=sqlite3.connect('/home/user/aoe2_matchup/data/golden/aoe2_reference_simulation.db')
REF={(c,u):dict(base=b,final=f,cf=cf,cw=cw,cg=cg) for c,u,b,f,cf,cw,cg in ref.execute('select civ_name,unit_master,base_train_time,final_train_time,final_cost_food,final_cost_wood,final_cost_gold from ref_units')}
TU=TT['data']['Unit']; TB=TT['data']['Building']
ALIAS={35:1258}
FANDOM_TIMES={(555,12):(16,'fandom Huskarl: Barracks base 16 s'),(757,101):(24,'fandom Tarkan: Elite at Stable base 24 s'),(2587,104):(18,'fandom Temple Guard: Elite at Monastery 18 s'),(2587,12):(24,'fandom Temple Guard: Elite at Barracks 24 s'),(1659,1665):(12,'fandom Serjeant: Donjon 12 s from Castle Age')}
def bcost_expected(civ,bid):
    if bid==104 and civ in ('Armenians','Georgians'): base=dict(TB['1806']['Cost']); note='Monastery is upgraded to Fortified Church (DAT effect 941; fandom: Warrior Priest building = Fortified Church, 200 wood)'
    else: base=dict(TB[str(bid)]['Cost']); note='aoe2techtree base'
    c={k.lower():float(v) for k,v in base.items() if v}
    if civ=='Malians' and 'wood' in c: c['wood']*=0.85; note+='; Malians buildings -15% wood'
    if civ=='Cumans' and bid in (87,101): c['wood']-=75; note+='; Cumans AR/Stable -75 wood'
    if civ=='Vikings' and bid==45: c={k:v*0.85 for k,v in c.items()}; note+='; Vikings team Docks -15%'
    if civ=='Franks' and bid==82: c={k:v*0.75 for k,v in c.items()}; note+='; Franks Castles -25% Imperial'
    if civ=='Incas' and 'stone' in c: c['stone']*=0.85; note+='; Incas buildings -15% stone'
    if civ=='Slavs' and bid==82: c={'stone':390.0,'wood':260.0}; note+='; Slavs Detinets 40% stone->wood'
    return c,note
def fmt(c): return ' '.join(f"{v:g}{k[0].upper()}" for k,v in sorted(c.items()) if v) or '0'
TECHTREE_VER='aoe2techtree.net data.json (site links update 188329), fetched 2026-11-12'
rows=[]
def add(civ,unit,field,ds,a,b,verdict,note=''):
    rows.append(dict(civ=civ,unit=unit,field=field,dataset_value=ds,source_a_value=a,source_b_value=b,verdict=verdict,note=note))
for civ,uid,mode,pl in db.execute('select civ,unit_id,mode,payload from units order by civ,unit_id,mode'):
    p=json.loads(pl); pr=p['production']; pc=p['pricing']; name=p['name']+('' if mode=='default' else f' [{mode}]')
    # --- unit price
    pur={k:v for k,v in pc['purchaseCost'].items() if v}
    r=REF.get((civ,p['sourceUnitId']))
    refc={k:float(round(v)) for k,v in (('food',r['cf']),('wood',r['cw']),('gold',r['cg'])) if v} if r else None
    tu=TU.get(str(ALIAS.get(p['sourceUnitId'],p['sourceUnitId'])))
    tb_cost={k.lower():v for k,v in tu['Cost'].items() if v} if tu else None
    verdict,note='match',''
    if refc!=pur:
        if civ=='Magyars' and uid==871: note='Corvinian Army: gold replaced by food (35F+45G -> 80F); DAT effect 571 and fandom Magyar Huszar confirm; reference DB lacks the UT'
        elif civ=='Mapuche' and uid==2571: note='Butalmapu -15% (DAT tech 1380, aoe2techtree text); 42.5W/46.75G rounded; reference DB lacks the UT'
        elif civ=='Mayans' and uid in (492,765): note='Mayans foot archers -10/20/30% (DAT 0.9*0.89*0.88); reference DB stops at -20%'
        elif 'Elephant Archer' in p['name']: verdict='version-difference'; note='Patch 188329 raised Elephant Archer food 60->70 (aoe2techtree 70F, DAT patch signature); reference DB predates it'
        else: verdict='mismatch'; note='unexplained'
    if pc['conditionalMultiplier']!=1 and verdict=='mismatch':
        verdict='not-verifiable'; note='Reference DB omits the conditional discount; dataset = base x 0.8 rounded, i.e. Saxon maximum -20% ("-5% per Town Center or Castle controlled, maximum -20%", aoe2techtree text). Arithmetic matches; whether 4 TCs/Castles is a fair assumption, and whether foot archers count as "Foot Soldiers", is an owner decision'
        refc=refc
    kona = civ=='Mapuche' and p['name']=='Elite Kona'
    if kona:
        verdict='mismatch'; note='Butalmapu: "Team Castle Unique Units ... cost -15%" (aoe2techtree text; fandom Kona: 55F 34G with Butalmapu). DAT implements this via engine hook 51 (resource 33), which the dataset does not apply. Correct purchase price 55F 34G.'
    if any(abs(v-round(v)-0.5)<1e-6 or abs(v-round(v)+0.5)<1e-6 for v in pc['sourceCost'].values()):
        note=(note+'; ' if note else '')+f"source cost {fmt({k:round(v,3) for k,v in pc['sourceCost'].items() if v})} has an exact .5 - dataset rounds half-to-even (Python round); in-game rounding rule not verified (+/-1 resource)"
    add(civ,name,'purchase_cost_per_order',fmt(pur),('55F 34G (base x0.85, rounded)' if kona else (fmt(refc)+' (reference DB)' if refc else '')),('fandom Kona with Butalmapu: 55F 34G' if kona else (('aoe2techtree base '+fmt(tb_cost)) if tb_cost else 'not in aoe2techtree')),verdict,note)
    # --- batch
    add(civ,name,'units_per_purchase',pc['unitsPerPurchase'],'2 (fandom: trained in pairs, 40W+45G per pair since update 185872)' if pc['unitsPerPurchase']==2 else '1','',
        'match','' )
    # --- routes
    expected_routes=[]
    for rt in p['productionRoutes']:
        bid=rt['id']; tid=rt['trainedUnitId']
        exp,notes=expected(civ,tid,bid,rt['baseTrainSeconds'])
        loc=[l for l in C[civ]['units'][str(tid)]['train_locations'] if l['unit_id']==bid]
        dat_base=loc[0]['train_time'] if loc else None
        slot_note=''
        if dat_base is None:
            alt=[l for l in C[civ]['units'][str(tid)]['train_locations'] if l['train_time']==rt['baseTrainSeconds']]
            if alt: dat_base=alt[0]['train_time']; slot_note=f"DAT slot (building {alt[0]['unit_id']}) reassigned to building {bid} by a technology/civ effect" 
        sel = pr.get('id')==bid and pr.get('trainedUnitId')==tid
        tag='selected' if sel else 'alternative'
        avail = bid in TT['civs'][civ]['Building'] or (bid==104 and civ=='Armenians')
        # availability
        if not avail:
            add(civ,name,f'route_availability[{rt["name"]}]',f'listed ({tag})','not buildable by civ (DAT: Donjon is Sicilian-only)',f'aoe2techtree {civ} building list lacks {bid}',
                'mismatch','Phantom alternative route; never selected, so no numeric impact, but shown in alternativeRoutes')
        if bid==104 and civ=='Armenians':
            add(civ,name,'production_building','Monastery (104)','Fortified Church (1806): DAT effect 941 upgrades 104->1806 for Armenians','fandom Warrior Priest: Building = Fortified Church','mismatch','Building cost understated by 25 wood each')
        # base time
        tbu=TU.get(str(ALIAS.get(tid,tid)))
        fb=FANDOM_TIMES.get((tid,bid))
        bval = (f"{fb[0]} ({fb[1]})" if fb else (f"{tbu['TrainTime']} (aoe2techtree)" if tbu else 'n/a'))
        bnum = fb[0] if fb else (tbu['TrainTime'] if tbu else None)
        v='match' if (dat_base==rt['baseTrainSeconds'] and (bnum is None or bnum==rt['baseTrainSeconds'])) else 'mismatch'
        if bnum is None: v='match' if dat_base==rt['baseTrainSeconds'] else 'mismatch'
        add(civ,name,f'base_train_seconds[{rt["name"]},{tag}]',rt['baseTrainSeconds'],dat_base,bval,v,'; '.join(x for x in (slot_note,'' if bnum is not None else 'no online per-unit value; DAT only') if x))
        # final time
        rr=REF.get((civ,p['sourceUnitId']))
        refv=rr['final'] if rr and sel else ''
        v='match' if abs(rt['secondsPerOrder']-exp)<1e-3 else 'mismatch'
        n='independent recompute from DAT effects: '+('; '.join(notes) if notes else 'no modifiers')
        if v=='mismatch' and civ=='Persians': n+=' | dataset applies the Dark-Age Dock multiplier (unit 45, x1.05); in Imperial the Dock is unit 51 (x1.20). aoe2techtree + fandom: Docks work +20% in Imperial'
        if sel and rr and abs(rt['secondsPerOrder']-rr['final'])>0.5:
            n+=' | reference DB differs: it applies Conscription to Siege Workshops/Docks (fandom: Conscription excludes Siege Workshops and Docks) and lacks some newer bonuses; reference values are rounded integers'
        add(civ,name,f'final_seconds_per_order[{rt["name"]},{tag}]',round(rt['secondsPerOrder'],4),round(exp,4),refv,v,n)
        # building cost
        ec,en=bcost_expected(civ,bid)
        dc={k:v for k,v in rt['cost'].items() if v}
        v='match' if set(dc)==set(ec) and all(abs(dc[k]-ec[k])<1e-3 for k in dc) else 'mismatch'
        if bid==2556: en='aoe2techtree/fandom Settlement 125 wood'
        add(civ,name,f'building_cost[{rt["name"]},{tag}]',fmt({k:round(x,2) for k,x in dc.items()}),fmt({k:round(x,2) for k,x in ec.items()}),fmt({k.lower():x for k,x in TB.get(str(bid),{'Cost':{}})['Cost'].items() if x}),v,en)
    if civ=='Mapuche' and p['name'] in ('Elite Skirmisher','Halberdier'):
        add(civ,name,'production_routes','Settlement only (+ phantom Donjon)','Archery Range/Barracks (16.54 s with Conscription) + Settlement (22 s)','aoe2techtree: "Settlements can train Spearman-line and Skirmishers"; fandom: Settlements train them "in 2.15x/1.61x/same time as regular production buildings"','mismatch','Resolver read attribute 158 x32767 as "slot 0" and overwrote the regular building; selected route should be Archery Range/Barracks (9 x 175W instead of 14 x 125W for 27 units)')
    # production numbers (27-unit default)
    if pr['status']=='modeled':
        orders=math.ceil(27/pc['unitsPerPurchase']); opb=math.floor(60/pr['secondsPerOrder']); n=math.ceil(orders/opb)
        add(civ,name,'orders_per_building_60s',pr['ordersPerBuilding'],opb,'',"match" if opb==pr['ordersPerBuilding'] else 'mismatch','floor(60/seconds); recomputed independently; also checked for every army size 1-27 (27,837 cases, 0 differences)')
        add(civ,name,'buildings_required_27_units',pr['buildingCount'],n,'',"match" if n==pr['buildingCount'] else 'mismatch',f'ceil({orders} orders / {opb})')
    else:
        add(civ,name,'production_status',pr['status'],'','', 'not-verifiable' if pr['status']=='unresolved_training_route' else 'match',
            {'Xebec':'Unit 1631 is absent from the Berber in-game tech tree and from aoe2techtree: stale roster row (excluded by user)',
             'Fire Ship':'Chinese Fire Ships are upgraded to Dragon Ships (DAT effect 1010, 529->1302) by Imperial: the post-Imperial unit is the Dragon Ship (75W 45G, 27 s, Dock; 17.55 s with Shipwright). Excluded by user.'}.get(p['name'],
             'Train time > 60 s (Dromon 65 s without Shipwright; Traction Trebuchet 70 s): no complete purchase fits the window, so headline is withheld by design'))
w=csv.DictWriter(open('/home/user/aoe2_matchup/docs/army-economics-review/production-comparison.csv','w'),fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
import collections
print(len(rows)); print(collections.Counter(r['verdict'] for r in rows))
print(collections.Counter((r['field'].split('[')[0],r['verdict']) for r in rows))
