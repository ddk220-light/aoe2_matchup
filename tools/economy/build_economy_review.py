#!/usr/bin/env python3
"""First-pass post-Imperial economic source inventory; not an effective-income simulator."""
import argparse
import csv
import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from aoe2x.economy.paths import scratch_path, dat_path  # noqa: E402

from build_production_review import AGES, OPS, RESOURCES, apply, match, costs, sql_table, attach_game_trees
from build_upgrade_review import command_source

DEFAULT = scratch_path('economy-review')
PROD = scratch_path('production-review')
JOBS = {259: ('farmer', 0, 190), 123: ('lumberjack', 1, 189),
        579: ('gold_miner', 3, 47), 124: ('stone_miner', 2, 79),
        120: ('forager', 0, 296), 122: ('hunter', 0, 268),
        592: ('shepherd', 0, 216), 56: ('shore_fisher', 0, 219)}
ECON_CLASSES = {2, 4, 19, 21, 49}
ATTRS = {5: 'movement_speed', 13: 'work_rate', 14: 'carry_capacity', 110: 'population_use_raw'}
EXTRA_RESOURCES = {36, 37, 46, 47, 69, 78, 79, 85, 86, 189, 190, 191,
                   206, 208, 216, 219, 225, 236, 237, 242, 243, 244, 245,
                   238,239,241,251,254,266,267,268,269,276,288,289,296,503,504,512,563}
ECO_BUILDING_NAMES={'Town Center','Mill','Lumber Camp','Mining Camp','Market','Dock','Farm',
                    'Folwark','Pasture','Harbor','Feitoria','Caravanserai','Fortified Church'}
ECON_RESEARCH_PARAMETERS={36,37,46,78,191,206,208,225,236,237,238,239,241,251,254,
                         266,267,276,288,289,503,504,512,563}


def corrected_commands(raw, base, evaluation, research_rows):
    """Reject inaccessible nonzero-cost/time hidden technologies, then recheck gates.

    A hidden team-bonus tech with a dummy 1F/1s cost is not automatic. The owning
    team effect must first make it free and instantaneous. Building events and
    the shipped available-research tree remain explicit activation evidence.
    """
    log=json.loads(evaluation['active_technologies'])
    roots=command_source(raw,base['tree_id'],'civilization')+command_source(raw,base['team_id'],'own_team_bonus')
    active={r['tech_id'] for r in log}
    explicit={r['tech_id'] for r in log if r['reason']=='building_completion'}|set(AGES)
    def commands_for(ids):
        result=list(roots)
        for item in log:
            if item['tech_id'] in ids:
                result+=command_source(raw,raw['techs'][str(item['tech_id'])]['effect_id'],item['reason'],item['tech_id'])
        return result
    removed={}
    while True:
        commands=commands_for(active)
        remove={}
        for tid in active-explicit:
            t=raw['techs'][str(tid)]
            locs=t['research_locations']
            if any(l['location_id']>=0 for l in locs):
                if (base['name'],tid) not in research_rows:
                    remove[tid]='not_granted_as_available_research_in_shipped_tree'
                continue
            price={r['type']:float(r['amount']) for r in t['resource_costs'] if r['type']>=0 and r['flag']}
            times=[float(l['research_time']) for l in locs]
            for s in commands:
                if s['tech_id']==tid:continue
                c=s['command']
                if c['type'] not in (101,103) or c['a'] not in (tid,-1):continue
                def op(v):return c['d'] if c['c']==0 else v*c['d'] if c['c']==2 else v+c['d']
                if c['type']==101:
                    for rid in list(price):
                        if c['b'] in (rid,-1):price[rid]=op(price[rid])
                else:times=[op(v) for v in times]
            if any(v>1e-6 for v in price.values()) or any(v>1e-6 for v in times):
                remove[tid]='hidden_technology_not_free_and_instant'
                continue
            req=[r for r in t['required_techs'] if r>=0];required=t['required_tech_count']
            if sum(r in active for r in req)<(required if required>0 else len(req)):
                remove[tid]='prerequisite_not_active_after_hidden_gate_filter'
        if not remove:break
        active-=remove.keys();removed.update(remove)
    return commands_for(active),[dict(civ_name=base['name'],tech_id=i,technology=raw['techs'][str(i)]['name'],reason=r) for i,r in sorted(removed.items())]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def extract(dat_path, path, names):
    from genieutils.datfile import DatFile
    data = DatFile.parse(dat_path)
    civs = {}
    for name, base in names.items():
        civ = data.civs[base['id']]
        units = {}
        for uid, unit in enumerate(civ.units):
            if not unit or unit.class_ not in ECON_CLASSES:
                continue
            units[str(uid)] = dict(id=uid,name=unit.name,type=unit.type,class_id=unit.class_,
                work_rate=unit.bird.work_rate if unit.bird else None,
                movement_speed=unit.speed,carry_capacity=unit.resource_capacity,
                resource_storages=[asdict(x) for x in unit.resource_storages],
                tasks=[asdict(t) for t in unit.bird.tasks] if unit.bird else [],
                costs=[asdict(x) for x in unit.creatable.resource_costs] if unit.creatable else [])
        civs[name] = dict(id=base['id'],resources=list(civ.resources),units=units)
    dump(path,dict(source_sha256=hashlib.sha256(dat_path.read_bytes()).hexdigest(),civs=civs))


def csv_write(path, rows):
    if not rows:
        return
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)


def build(args):
    args.output.mkdir(parents=True,exist_ok=True)
    raw=json.loads(args.raw.read_text())
    attach_game_trees(raw,PROD/'current-input/dat/CivTechTrees')
    if args.extract or not args.eco_source.exists():
        extract(dat_path(raw),args.eco_source,raw['civs'])
    eco=json.loads(args.eco_source.read_text())
    assert raw['source']['sha256']==eco['source_sha256']
    # Reuse the previous DAT extraction for special economic buildings outside
    # villager/farm classes, including Feitoria's resource-generation tasks.
    if not eco.get('economic_building_tasks_enriched'):
        link_path=scratch_path('research-review/unit-research-links.json')
        links=json.loads(link_path.read_text())
        assert links['source_sha256']==eco['source_sha256']
        for name,base in raw['civs'].items():
            for node in base['game_tree']['civ_techs_buildings']:
                uid=str(node['Node ID'])
                if node['Name'] not in ECO_BUILDING_NAMES or uid in eco['civs'][name]['units'] or uid not in base['units']:continue
                u=base['units'][uid];extra=links['civs'][str(base['id'])][uid]
                eco['civs'][name]['units'][uid]=dict(id=int(uid),name=u['name'],type=u['type'],class_id=u['class_id'],
                    work_rate=u['work_rate'],movement_speed=None,carry_capacity=None,tasks=extra['tasks'],
                    costs=u['costs'],resource_storages=extra['resource_storages'])
        del links
        eco['economic_building_tasks_enriched']=str(link_path)
        dump(args.eco_source,eco)
    prod=sqlite3.connect(f'file:{args.production.resolve()}?mode=ro',uri=True);prod.row_factory=sqlite3.Row
    research=sqlite3.connect(f'file:{args.research.resolve()}?mode=ro',uri=True);research.row_factory=sqlite3.Row
    research_rows={(r['civ_name'],r['tech_id']):dict(r) for r in research.execute('select * from civilization_upgrades')}
    evaluations={r['civ_name']:dict(r) for r in prod.execute('select * from civilization_evaluation')}
    summaries,actors,task_rows,effect_rows,resource_rows,technology_rows,activation_exclusions=[],[],[],[],[],[],[]
    all_commands={}; economic_tech_ids=set();matched_techs=defaultdict(set);tech_roles=defaultdict(set)
    for name,base in sorted(raw['civs'].items()):
        source=eco['civs'][name]
        nodes={n['Node ID']:n for n in base['game_tree']['civ_techs_buildings']}
        eco_building_ids={i for i,n in nodes.items() if n['Name'] in ECO_BUILDING_NAMES}
        for uid in eco_building_ids:
            if str(uid) not in source['units'] and str(uid) in base['units']:
                u=base['units'][str(uid)]
                source['units'][str(uid)]=dict(id=uid,name=u['name'],type=u['type'],class_id=u['class_id'],
                    work_rate=u['work_rate'],movement_speed=None,carry_capacity=None,tasks=[],costs=u['costs'],resource_storages=[])
        resources={i:float(v) for i,v in enumerate(source['resources'])}
        resource_changes=defaultdict(list)
        commands,excluded=corrected_commands(raw,base,evaluations[name],research_rows)
        activation_exclusions.extend(excluded)
        all_commands[name]=commands
        task_resource_ids={t['resource_multiplier'] for u in source['units'].values() for t in u['tasks'] if t['resource_multiplier']>=0}
        relevant_resources=EXTRA_RESOURCES|task_resource_ids
        relevant_resources.update(s['command']['a'] for s in commands if s['command']['type'] in (1,6) and s['command']['a']!=33)
        for s in commands:
            c=s['command']
            if c['type'] in (1,6) and c['a'] in relevant_resources:
                rid=c['a'];before=resources.get(rid,0)
                amount=c['d']*(resources.get(c['c'],0) if c['type']==1 and c['c']>=0 else 1)
                resources[rid]=(before*amount if c['type']==6 else amount if c['b']==0 else before+amount)
                resource_changes[rid].append(dict(s,before=before,after=resources[rid]))
        final_actors={}
        for uid_string,u in source['units'].items():
            uid=int(uid_string)
            if not u['tasks'] and u['class_id']!=49 and uid not in eco_building_ids:
                continue
            u['population_use_raw']=next((x['amount'] for x in u['resource_storages'] if x['type']==4),None)
            values={field:u[field] for field in ATTRS.values()}
            base_cost=costs(u);price=dict(base_cost);evidence=[]
            for s in commands:
                c=s['command']
                if c['type'] not in OPS or not match(c,u):
                    continue
                attr=c['c']
                if attr in ATTRS and values[ATTRS[attr]] is not None:
                    field=ATTRS[attr];before=values[field];values[field]=apply(before,c)
                    if before!=values[field]:evidence.append(dict(s,target=field,before=before,after=values[field]))
                elif attr in (100,103,104,105,106):
                    before=dict(price)
                    names=list(price) if attr==100 else [{103:'food',104:'wood',105:'gold',106:'stone'}[attr]]
                    for resource in names:price[resource]=apply(price[resource],c)
                    if price!=before:evidence.append(dict(s,target='unit_or_farm_cost',before=before,after=dict(price)))
            row=dict(civ_name=name,unit_id=uid,raw_name=u['name'],class_id=u['class_id'],
                     building_name=nodes.get(uid,{}).get('Name'),
                     building_available=int(nodes[uid]['Node Status']!='NotAvailable') if uid in nodes else None,
                     **{'base_'+k:v for k,v in {f:u[f] for f in ATTRS.values()}.items()},
                     **{'final_'+k:v for k,v in values.items()},
                     **{'base_cost_'+k:v for k,v in base_cost.items()},**{'final_cost_'+k:v for k,v in price.items()},
                     evidence=evidence)
            actors.append(row);final_actors[uid]=row
            for s in evidence:
                if s['tech_id'] is not None and (name,s['tech_id']) in research_rows:
                    economic_tech_ids.add(s['tech_id']);matched_techs[name].add(s['tech_id'])
                    tech_roles[(name,s['tech_id'])].add('worker_or_infrastructure_parameter')
            for index,t in enumerate(u['tasks']):
                if t['action_type'] not in (5,110,111,122,151) or (t['resource_in']<0 and t['resource_out']<0):
                    continue
                rid=t['resource_multiplier']
                output=t['resource_out'] if t['resource_out']>=0 else t['resource_in']
                if output not in RESOURCES:
                    continue
                mult=resources.get(rid) if rid>=0 else 1.0
                value=t['work_value_1']
                # Expose raw components. Only primary gather tasks receive a
                # nominal work-rate product; secondary income/trade needs rules.
                primary=t['action_type'] in (5,110)
                nominal=values['work_rate']*value*mult if primary and values['work_rate'] is not None and mult is not None else None
                task_rows.append(dict(civ_name=name,unit_id=uid,task_index=index,action_type=t['action_type'],
                    resource=RESOURCES[output],target_unit_id=t['unit_id'],target_class_id=t['class_id'],
                    multiplier_resource_id=rid,base_multiplier=source['resources'][rid] if 0<=rid<len(source['resources']) else 1,
                    final_multiplier=mult,task_work_value=value,nominal_work_product_per_second=nominal,
                    interpretation='nominal_work_product_not_delivered_income' if primary else 'secondary_income_or_trade_needs_engine_semantics',
                    raw_task=t))
        for s in commands:
            c=s['command'];kind=None
            if c['type'] in OPS:
                targets=[int(uid) for uid,u in source['units'].items() if match(c,u)]
                if targets:
                    kind='actor_attribute_or_cost' if c['c'] in ATTRS|{100:'cost',101:'training',103:'food',104:'wood',105:'gold',106:'stone'} else 'actor_survival_or_other_attribute'
            elif c['type'] in (1,6) and c['a'] in relevant_resources:
                targets=[];kind='player_resource_parameter'
            elif c['type'] in (1,6) and c['a']==33:
                targets=[];kind='engine_calculation_hook_needs_scope_review'
            if kind:
                tid=s['tech_id'];definition=raw['techs'].get(str(tid),{})
                effect_rows.append(dict(civ_name=name,technology=definition.get('name'),classification=kind,target_unit_ids=targets,**s))
                if tid is not None and (name,tid) in research_rows and c['type'] in (1,6) and c['a'] in ECON_RESEARCH_PARAMETERS:
                    economic_tech_ids.add(tid);matched_techs[name].add(tid)
                    tech_roles[(name,tid)].add('player_economy_parameter')
                if tid is not None and (name,tid) in research_rows and kind=='actor_survival_or_other_attribute' and any(source['units'][str(uid)]['class_id']==4 for uid in targets):
                    economic_tech_ids.add(tid);matched_techs[name].add(tid)
                    tech_roles[(name,tid)].add('worker_survival_or_other_attribute')
        for rid in sorted(relevant_resources):
            resource_rows.append(dict(civ_name=name,resource_id=rid,base_value=source['resources'][rid] if rid<len(source['resources']) else None,
                                     final_parameter_value=resources.get(rid),evidence=resource_changes[rid]))
        summary=dict(civ_name=name)
        for uid,(job,resource,rid) in JOBS.items():
            actor=final_actors[uid]
            summary[job+'_work_rate']=actor['final_work_rate']
            summary[job+'_task_multiplier']=resources.get(rid)
            summary[job+'_nominal_work_product_per_second']=actor['final_work_rate']*resources[rid]
            summary[job+'_carry_capacity_raw']=actor['final_carry_capacity']
            summary[job+'_movement_speed']=actor['final_movement_speed']
        farm=final_actors[50]
        summary.update(farm_available=int(nodes.get(50,{}).get('Node Status') not in (None,'NotAvailable')),
                       farm_food_parameter=resources.get(36),farm_wood_cost=farm['final_cost_wood'],
                       farm_work_rate=farm['final_work_rate'],farm_wood_per_food= farm['final_cost_wood']/resources[36] if resources.get(36,0)>0 else None,
                       farming_warning='Farmer work rate, farm work rate, carry, walking and special mechanics must be modeled together')
        summaries.append(summary)
    # Shadow modifiers can be conditional on a paid upgrade (e.g. Armenians).
    # Retain the raw prerequisite connection, rather than silently ignoring it.
    for name in raw['civs']:
        for s in effect_rows:
            if s['civ_name']!=name or s['tech_id'] is None:
                continue
            tid=s['tech_id']
            for req in raw['techs'][str(tid)]['required_techs']:
                if (name,req) in research_rows and s['classification']=='actor_attribute_or_cost':
                    economic_tech_ids.add(req);matched_techs[name].add(req)
                    tech_roles[(name,req)].add('enables_conditional_economic_effect')
    for name in sorted(raw['civs']):
        for tid in sorted(economic_tech_ids):
            t=raw['techs'][str(tid)];row=research_rows.get((name,tid))
            # Civ-specific technologies have no meaning in other civ trees.
            if t['civ'] not in (-1,raw['civs'][name]['id']):continue
            technology_rows.append(dict(civ_name=name,tech_id=tid,technology=row['technology'] if row else t['name'],
                available=int(row is not None),has_economic_connection=int(tid in matched_techs[name]),
                economic_roles=sorted(tech_roles[(name,tid)]),
                free=row['free'] if row else None,instant=row['instant'] if row else None,
                upfront_food=row['upfront_food'] if row else None,upfront_wood=row['upfront_wood'] if row else None,
                upfront_gold=row['upfront_gold'] if row else None,final_research_seconds=row['final_seconds'] if row else None,
                effect_id=t['effect_id'],required_techs=t['required_techs']))
    # Costs and train time alone determine required resource flow. Villager
    # counts remain unset until effective resource-specific gather rates exist.
    funding=[]
    for p in prod.execute('select * from unit_production order by civ_name,unit_name'):
        name=p['civ_name'];uid=p['source_unit_id'] or p['unit_id']
        unit=raw['civs'][name]['units'][str(uid)];price=costs(unit);evidence=[]
        for s in all_commands[name]:
            c=s['command']
            if c['type'] not in OPS or c['c'] not in (100,103,104,105,106) or not match(c,unit):continue
            before=dict(price)
            for resource in list(price) if c['c']==100 else [{103:'food',104:'wood',105:'gold',106:'stone'}[c['c']]]:
                price[resource]=apply(price[resource],c)
            if before!=price:evidence.append(dict(s,before=before,after=dict(price)))
        building=raw['civs'][name]['units'][str(p['building_id'])]
        training=float(p['base_train_seconds']);rate=building['work_rate'];time_evidence=[]
        for s in all_commands[name]:
            c=s['command']
            if c['type'] not in OPS:continue
            if c['c']==101 and match(c,unit):
                before=training;training=apply(training,c)
                if before!=training:time_evidence.append(dict(s,target='training_time',before=before,after=training))
            elif c['c']==13 and match(c,building):
                before=rate;rate=apply(rate,c)
                if before!=rate:time_evidence.append(dict(s,target='production_work_rate',before=before,after=rate))
        seconds=training/rate if rate and rate>0 else None
        funding.append(dict(civ_name=name,unit_id=p['unit_id'],source_unit_id=uid,unit_name=p['unit_name'],
            production_building=p['building'],train_seconds=seconds,
            previous_review_train_seconds=p['final_train_seconds'],
            training_correction=int(seconds is not None and abs(seconds-p['final_train_seconds'])>1e-5),
            **{'unit_cost_'+r:v for r,v in price.items()},
            **{'resource_per_game_minute_'+r:60*v/seconds if seconds else None for r,v in price.items()},
            interpretation='one_building_continuously_training; farm_maintenance_and_effective_villager_rates_not_yet_included',
            cost_evidence=evidence,training_evidence=time_evidence))
    out=args.output
    tables=[('civilization_parameters',summaries),('economic_actors',actors),('gather_tasks',task_rows),
            ('economic_effects',effect_rows),('resource_parameters',resource_rows),('economic_technologies',technology_rows),
            ('activation_exclusions',activation_exclusions),('unit_funding_demand',funding)]
    dbpath=out/'economy-source-review.sqlite'
    temporary=out/'economy-source-review.build.sqlite'
    if temporary.exists():temporary.unlink()
    con=sqlite3.connect(temporary)
    for table,rows in tables:
        json_fields=[k for k in rows[0] if any(isinstance(r[k],(dict,list)) for r in rows)]
        sql_table(con,table,rows,json_fields)
    metadata=dict(source=raw['source'],scope='Economic parameters, technology availability and effect provenance; not effective gather rates',
        assumptions=['Post-Imperial with all available upgrades, own team bonus, no allied bonuses',
                     'Free/cheap research affects setup investment; final actor effects applied once',
                     'Nominal work products exclude walking, drop-off, reseeding, congestion, task scheduling and global special mechanics',
                     'Farm wood/food ratio is a nominal seed-maintenance ratio; special farm bonuses need separate treatment',
                     'Player-resource commands with c>=0 scale their amount by that resource parameter (e.g. farm upgrade multiplier 69)',
                     'Player-resource parameters and engine calculation hooks are retained for review',
                     'Unit funding demand is resource flow for one continuously training building; no army-size normalization'],
        paths=dict(eco_source=str(args.eco_source),production=str(args.production),research=str(args.research)))
    sql_table(con,'metadata',[dict(key=k,value=v) for k,v in metadata.items()],['value'])
    con.execute('create unique index civ_parameters_key on civilization_parameters(civ_name)')
    con.execute('create unique index eco_tech_key on economic_technologies(civ_name,tech_id)')
    con.execute('create unique index eco_actor_key on economic_actors(civ_name,unit_id)')
    con.commit()
    checks=validate(con,raw,summaries)
    con.close();temporary.replace(dbpath)
    for table,rows in tables:
        csv_write(out/(table.replace('_','-')+'.csv'),rows)
    csv_write(out/'production-corrections.csv',[row for row in funding if row['training_correction']])
    dump(out/'manifest.json',metadata);dump(out/'validation.json',checks)
    print(json.dumps(checks,indent=2))


def validate(con,raw,summaries):
    rows={r['civ_name']:r for r in summaries}
    checks=dict(integrity=con.execute('pragma integrity_check').fetchone()[0]=='ok',all_civilizations=len(rows)==56)
    s=rows['Spanish'];c=rows['Celts'];t=rows['Turks'];te=rows['Teutons'];sl=rows['Slavs']
    checks['spanish_nominal_lumber']=abs(s['lumberjack_work_rate']-.39*1.2*1.2*1.1)<1e-5
    checks['celt_missing_two_man_saw_accounted']=abs(c['lumberjack_work_rate']-.39*1.15*1.2*1.2)<1e-5
    checks['turk_gold_rate']=abs(t['gold_miner_work_rate']-.38*1.15*1.15*1.25)<1e-5
    checks['teuton_farm_discount']=abs(te['farm_wood_cost']/s['farm_wood_cost']-.6)<1e-5
    checks['slav_farmer_and_farm_rates_separate']=abs(sl['farmer_work_rate']/s['farmer_work_rate']-1.23)<1e-5 and abs(sl['farm_work_rate']/s['farm_work_rate']-1.15)<1e-5
    checks['free_handcart_not_double_applied']=abs(rows['Vikings']['lumberjack_carry_capacity_raw']-s['lumberjack_carry_capacity_raw'])<1e-5
    checks['spanish_missing_crop_rotation']=abs(s['farm_food_parameter']-375)<1e-5
    checks['chinese_own_team_farm_bonus']=abs(rows['Chinese']['farm_food_parameter']-412.5)<1e-4
    checks['sicilian_farm_upgrade_resource_multiplier']=abs(rows['Sicilians']['farm_food_parameter']-(175+375*2.25))<1e-4
    checks['no_eco_rate_nulls']=all(r['lumberjack_work_rate']>0 and r['gold_miner_work_rate']>0 for r in summaries)
    count=0
    for encoded, in con.execute('select evidence from economic_actors'):
        for x in json.loads(encoded):
            assert raw['effects'][str(x['effect_id'])]['effect_commands'][x['command_index']]==x['command'];count+=1
    checks['raw_command_provenance']=count>0
    checks['funding_demand_covers_advisor_roster']=con.execute('select count(*) from unit_funding_demand').fetchone()[0]==1030
    checks['positive_funding_training_times']=con.execute('select count(*) from unit_funding_demand where train_seconds is null or train_seconds<=0').fetchone()[0]==0
    checks['no_negative_funding_costs']=con.execute('select count(*) from unit_funding_demand where unit_cost_food<0 or unit_cost_wood<0 or unit_cost_gold<0 or unit_cost_stone<0').fetchone()[0]==0
    checks['bengali_villager_population_modifier']=abs(con.execute("select final_population_use_raw from economic_actors where civ_name='Bengalis' and unit_id=83").fetchone()[0]+.9)<1e-5
    assert all(checks.values()),checks
    return dict(checks=checks,all_passed=True,verified_actor_effect_commands=count,
                counts={t:con.execute('select count(*) from '+t).fetchone()[0] for t in ['civilization_parameters','economic_actors','gather_tasks','economic_effects','economic_technologies','unit_funding_demand']})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw',type=Path,default=PROD/'current-raw-source.json')
    p.add_argument('--eco-source',type=Path,default=DEFAULT/'raw-economy-source.json')
    p.add_argument('--production',type=Path,default=PROD/'current-results/production-review.sqlite')
    p.add_argument('--research',type=Path,default=scratch_path('research-review/current-results/unit-upgrades.sqlite'))
    p.add_argument('--output',type=Path,default=DEFAULT/'current-results')
    p.add_argument('--extract',action='store_true')
    build(p.parse_args())
