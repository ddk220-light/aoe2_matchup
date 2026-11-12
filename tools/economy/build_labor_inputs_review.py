#!/usr/bin/env python3
"""Build a reviewable source inventory for future labor-per-replacement estimates.

Requires extract_economy_inputs.py and build_economy_review.py --output labor-base
using the corrected production activation log. No empirical gather rates are
invented, and no production-building workforce metric is included.
"""
import argparse
import json
import sqlite3
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from aoe2x.economy.paths import scratch_path, dat_path  # noqa: E402

from build_production_review import OPS, apply, match, costs, sql_table, attach_game_trees
from build_upgrade_review import command_source
from build_economy_review import csv_write, corrected_commands, dump, JOBS

ROOT = scratch_path('economy-review')
PROD = scratch_path('production-review')
STANDARD = {202:'Double-Bit Axe',203:'Bow Saw',221:'Two-Man Saw',55:'Gold Mining',
    182:'Gold Shaft Mining',278:'Stone Mining',279:'Stone Shaft Mining',
    14:'Horse Collar',13:'Heavy Plow',12:'Crop Rotation',213:'Wheelbarrow',249:'Hand Cart',
    906:'Fishing Lines',65:'Gillnets',48:'Caravan',15:'Guilds',54:'Treadmill Crane',
    1014:'Domestication',1013:'Pastoralism',1012:'Transhumance'}
LAND_STANDARD = {202,203,221,55,182,278,279,14,13,12,213,249}
ATTR = {5:'movement_speed',13:'work_rate',14:'carry_capacity',110:'population_use_raw'}
ECON_RESOURCE_IDS = {0,1,2,3,4,32,36,37,46,47,69,78,79,85,86,88,91,92,93,94,
    189,190,191,205,206,207,208,215,216,219,225,234,236,237,238,239,241,245,
    251,254,266,267,268,269,271,276,287,288,289,290,291,292,293,294,295,296,297,298,502,503,504}
ECO_NAMES = {'Town Center','Mill','Lumber Camp','Mining Camp','Market','Dock','Farm',
    'Folwark','Pasture','Harbor','Feitoria','Caravanserai','Fortified Church','Mule Cart',
    'Fish Trap','Settlement','House'}

# Human-readable annotations explain numeric DAT commands or retain the source
# label as a clue. Engine hook scope/formula is never inferred from its number.
# category, review note; every annotation is emitted only if the effect is active.
NOTES = {
  447:('carry','Villager carrying capacity +3 before subsequent carry modifiers.'),
  488:('passive_income','Relic-gold parameter ×1.33; requires relic count and elapsed time.'),
  841:('coupled_income','Trade-food parameter 251 increases by 10; trade route and payout semantics remain to model.'),
  853:('population','Mahayana sets villager population use to 0.9; this is not faster harvesting.'),
  609:('movement','Villager movement ×1.05; later effect 626 multiplies by 1.047619 (about ×1.10 together).'),
  626:('movement','Second villager movement modifier ×1.047619.'),
  611:('trade_and_fishing','Fishing/trade ship movement ×1.10; trade-cog work also ×1.10.'),
  826:('movement','Fervor-linked hidden technology gives villagers movement ×1.15.'),
  381:('work_rate','Shepherd work rate ×1.25.'),
  379:('setup_cost','Town Center wood cost ×0.50.'),
  731:('setup_cost','Town Center stone cost ×0.50.'),
  783:('passive_income','Relic-food parameter 225 increases by 20; relic holdings must be specified.'),
  790:('coupled_income','Burgundian Vineyards: resource 236 +2, engine hook 14; retain as farming-linked gold mechanic, not an assumed income rate.'),
  791:('workforce_event','Flemish Revolution triggers engine hook 55; workforce conversion is an event, not a gather bonus.'),
  384:('work_rate','Lumberjack work ×1.15; missing Two-Man Saw is recorded separately.'),
  240:('resource_yield','Chinese own-team effect multiplies farm/pasture food and the farm-upgrade multiplier by 1.10.'),
  863:('carry','Fishing ships and shore-fishing worker variants gain +15 carry; exact target IDs retained.'),
  868:('one_time','Age-triggered +200 wood per activation; not recurring villager income.'),
  613:('one_time','Feudal-age trigger adds 100 food and 100 gold.'),
  614:('one_time','Castle-age trigger adds 100 food and 100 gold.'),
  615:('one_time','Imperial-age trigger adds 100 food and 100 gold.'),
  523:('work_rate','Forager work rate ×1.15.'),
  939:('area_effect','Fortified Church area effect invokes engine hook 9. Radius, worker coverage and stacking are not encoded by this command.'),
  928:('repair','Team effect multiplies resource 271 by 0.75; retain parameter, confirm its repair-cost accounting in the engine.'),
  414:('resource_yield','Hunters gain +15 carry; hunt multiplier ×1.23 paired with worker work ×0.813008. Yield and work must be modeled together.'),
  871:('garrison_income','Mill garrison type/capacity are changed (capacity 10); herdable-income parameter 254 is set to 15. Herdable composition matters.'),
  562:('gold_and_trade','Grand Trunk Road changes gold miners, trade units, relic/passive-gold parameters and market parameters; all targets retained separately.'),
  554:('setup_cost','Silk Road multiplies specified trade-unit resource costs by 0.50.'),
  338:('setup_cost','Mill, Lumber Camp and Mining Camp costs ×0.50.'),
  306:('fishing','Fishing-ship work ×1.05, followed by further age-specific modifiers; survival bonuses kept separately.'),
  993:('depletion','Animal-decay switch resource 292 is set to 1; compare available food, not a flat harvest-rate increase.'),
  1014:('pasture','First pasture upgrade adds 115 × resource 69 to resource 288 and +1 to resource 289.'),
  1013:('pasture','Second pasture upgrade adds 230 × resource 69 to resource 288 and +2 to resource 289.'),
  1012:('pasture','Third pasture upgrade adds 345 × resource 69 to resource 288 and +3 to resource 289.'),
  690:('drop_off','Khmer Instant Farmers hook 50 plus farmer work ×0.95; cannot evaluate as a simple 5% income reduction.'),
  504:('work_rate','Stone-miner work ×1.20; other tree commands are retained as raw provenance.'),
  675:('recurring_cost','Fish Trap resource cost ×0.66667.'),
  677:('resource_yield','Fish-trap food parameter 88 is set to 2130; retain exact value rather than relying on the effect label.'),
  621:('resource_yield','Gold-productivity parameter 276 +10; engine accounting needs confirmation.'),
  617:('setup_cost','Building wood-cost modifiers, including exclusions/reapplications, are retained; do not apply a blanket discount to farms.'),
  1381:('resource_yield','Forager-productivity parameter 215 +25 and engine hook 29; exact credited/depleted-resource rule remains unresolved.'),
  449:('resource_yield','Multiple task-output multipliers ×1.15 paired with lower worker work rates (farmer ×0.81, many other jobs ×0.87).'),
  388:('work_rate','Hunter work rate ×1.40.'),
  1357:('resource_yield','Gold task multiplier ×1.15 paired with miner work ×0.869565; resource yield is distinct from collection speed.'),
  1368:('setup_and_area','Settlement cost ×0.67 and healing-related hook 28; raw settlement forms retained.'),
  421:('setup_speed','Town Center/Dock work modifiers differ by age-specific unit ID: ×1.05/1.10/1.15/1.20. This affects queues, not villager harvest work.'),
  816:('farm_event','Folwark replaces Mill variants; resource 237 = 0.10 × farm-food parameter 36, plus parameters 238/239. Farm placement/renewal rules remain to model.'),
  827:('coupled_income','Stone-mining gold mechanic: resource 241 +33.3333015 and hook 13. Keep gold and stone as joint outputs.'),
  510:('coupled_income','Forager-generated wood: resource 267 +33.3333015. Keep food and wood as joint outputs.'),
  898:('work_rate','Villagers work ×1.05; farmers additionally ×1.038095 and Farm work ×1.05. These are separate parameters, not a measured income uplift.'),
  354:('market','Market cost reduced by 100 wood and market fee parameter changed; trades need a price/quantity scenario.'),
  1455:('repair','Repairer work rate ×1.25.'),
  1465:('building_event','Drop-site variants receive resource-storage changes labelled +35 food/+10 stone; completion event semantics retained for review.'),
  1071:('coupled_income','Lumberjack-food parameter 502 +7 and engine hook 16; preserve wood and food together.'),
  797:('resource_yield','Farm-upgrade food multiplier ×2.25; does not multiply the initial farm food by 2.25.'),
  7:('work_rate','Farmer work ×1.23 and Farm work ×1.15; both enter the future farming model.'),
  490:('trade','Specified trade-unit work rate ×1.25; payout/distance logic still required.'),
  446:('construction','Builder work ×1.30; research pricing and other tree commands remain separately recorded.'),
  181:('research_reward','Research reward parameter 269 points to effect 300, which grants gold. This is setup income, not per-replacement harvesting.'),
  741:('resource_yield','Herdable-food multiplier ×1.57 paired with shepherd/herder work ×0.637; exact stored factors retained.'),
  314:('recurring_cost','Farm cost ×0.60: 36 wood for a standard 60-wood farm in this supplied DAT.'),
  1396:('replacement_refund','Unit Refund hook 27 and parameter 295 = 0.15. Eligible units, trigger and refund resource basis need engine validation.'),
  295:('work_rate','Gold-miner work rate ×1.25.'),
  1475:('coupled_income','Source-labelled gold from sheep/hunt/fishing ships: hook 34 and parameter 298 = 10.0100002.'),
  1490:('trade','Caravan-linked extra trade movement and work ×1.0835; do not turn both modifiers into a guessed income percentage.'),
  669:('coupled_income','Paper Money: gold parameter 266 +1.5 and hook 15; additional hidden modifiers follow researched wood upgrades.'),
  881:('coupled_income','Paper Money parameter ×1.20 conditional on Double-Bit Axe.'),
  882:('coupled_income','Paper Money parameter ×1.20 conditional on Bow Saw.'),
  883:('coupled_income','Paper Money parameter ×1.10 conditional on Two-Man Saw.'),
  411:('setup_cost','Dock costs ×0.85.'),
  1061:('conditional_income','Tuntian: parameter 287 +3 and hook 4; income source/counting semantics remain unresolved.'),
  1084:('building_event','Military-building food reward is stored through resource-storage attribute 27, including Docks.'),
  1485:('combat_income','Razing-bounty parameter 291 +250 and hook 36 with multiple player scopes; event income, not passive worker output.'),
  62:('combat_income','Cavalry-gold source label invokes hook 26; eligible kills/units and amount need engine validation.'),
  734:('building_event','Town Center annex 890 has its dead-unit target set to hidden food object 888; completion/death chain grants the source-labelled 100 food per Town Center.'),
  693:('worker_protection','House variants gain garrison capacity 5 and garrison type 1; protection, not a faster gather rate.'),
  951:('conditional_relic','Free-relic effect requires church-completion technology 107 and creates hidden object 1118; record as a conditional event.'),
  952:('conditional_relic','Hidden relic object fires technology 957, which creates relic unit 285; its income requires a relic-holding scenario.'),
  1408:('building_event','Post-Town-Center event adds 25 each of food, wood, stone and gold; conditional full_tech_mode -13, not automatic passive income.'),
}


def connect(path):
    c=sqlite3.connect(f'file:{path.resolve()}?mode=ro',uri=True);c.row_factory=sqlite3.Row
    return c


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'labor-inputs')
    args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    raw=json.loads((PROD/'current-raw-source.json').read_text())
    attach_game_trees(raw,PROD/'current-input/dat/CivTechTrees')
    source=json.loads((ROOT/'labor-source.json').read_text())
    assert source['source']['sha256']==raw['source']['sha256']
    base=connect(ROOT/'labor-base/economy-source-review.sqlite')
    prod=connect(ROOT/'corrected-production/production-review.sqlite')
    research=connect(scratch_path('research-review/current-results/unit-upgrades.sqlite'))
    techs={(r['civ_name'],r['tech_id']):dict(r) for r in research.execute('select * from civilization_upgrades')}
    evaluations={r['civ_name']:dict(r) for r in prod.execute('select * from civilization_evaluation')}
    counts=Counter(t['tech_id'] for r in evaluations.values() for t in json.loads(r['active_technologies']))
    commands=[];activations=[];snapshots=[];parameters=[];special=[];candidates=[];standard=[];summaries=[];replacements=[];conditional=[]
    classes={2:'trade_cog',4:'villager',19:'trade_cart',21:'fishing_ship',49:'farm_or_fish_trap'}

    for name,civ in sorted(raw['civs'].items()):
        cs=source['civs'][name]
        active,excluded=corrected_commands(raw,civ,evaluations[name],techs)
        excluded_ids={r['tech_id'] for r in excluded}
        active_ids={t['tech_id'] for t in json.loads(evaluations[name]['active_technologies']) if t['tech_id'] not in excluded_ids}
        for t in json.loads(evaluations[name]['active_technologies']):
            if t['tech_id'] not in active_ids:continue
            definition=raw['techs'][str(t['tech_id'])]
            activations.append(dict(civ_name=name,tech_id=t['tech_id'],reason=t['reason'],
                required_tech_ids=definition['required_techs'],required_count=definition['required_tech_count'],
                repeatable=definition['repeatable'],definition=definition))
        grouped=defaultdict(list)
        for order,s in enumerate(active):
            c=s['command'];tid=s['tech_id'];t=raw['techs'].get(str(tid),{})
            unique=tid is None or t.get('civ')==civ['id'] or (counts[tid]<10 and not any(x['location_id']>=0 for x in t.get('research_locations',[])))
            row=dict(civ_name=name,sequence=order,is_civilization_specific=int(unique),effect_name=raw['effects'][str(s['effect_id'])]['name'],**s)
            commands.append(row);grouped[(tid,s['effect_id'],unique)].append(row)

        actor_ids=set()
        for uid,u in cs['units'].items():
            node=u['tree_node'];building_name=node['Name'] if node else None
            selection='tree_available' if node and node['Node Status']!='NotAvailable' else 'tree_unavailable' if node else 'raw_candidate_or_linked_form'
            snapshots.append(dict(civ_name=name,unit_id=int(uid),name=building_name or u['name'],selection=selection,raw_definition=u))
            economic=u['class_'] in classes or building_name in ECO_NAMES
            if economic:actor_ids.add(int(uid))
            if not economic:continue
            values=dict(movement_speed=u['speed'],carry_capacity=u['resource_capacity'],
                work_rate=u['bird']['work_rate'] if u['bird'] else None,
                population_use_raw=next((x['amount'] for x in u['resource_storages'] if x['type']==4),None))
            initial=dict(values);unit=dict(id=int(uid),class_id=u['class_'],costs=u['creatable']['resource_costs'] if u['creatable'] else [])
            price=costs(unit);base_price=dict(price);evidence=[]
            for s in active:
                c=s['command']
                if c['type'] not in OPS or not match(c,unit):continue
                a=c['c']
                if a in ATTR and values[ATTR[a]] is not None:
                    field=ATTR[a];before=values[field];values[field]=apply(before,c)
                    if values[field]!=before:evidence.append(dict(s,field=field,before=before,after=values[field]))
                elif a in (100,103,104,105,106):
                    before=dict(price)
                    for resource in list(price) if a==100 else [{103:'food',104:'wood',105:'gold',106:'stone'}[a]]:price[resource]=apply(price[resource],c)
                    if before!=price:evidence.append(dict(s,field='resource_cost',before=before,after=dict(price)))
            parameters.append(dict(civ_name=name,unit_id=int(uid),name=building_name or u['name'],selection=selection,
                actor_class=classes.get(u['class_'],'economic_infrastructure'),base_parameters=initial,final_parameters=values,
                base_cost=base_price,final_cost=price,drop_sites=u['bird']['drop_sites'] if u['bird'] else [],
                resource_storages=u['resource_storages'],evidence=evidence,
                effective_delivered_rate=None,rate_status='requires_scenario_and_engine_or_empirical_calibration'))

        for (tid,eid,unique),rows in grouped.items():
            if not unique and eid not in NOTES:continue
            reasons=set();target_ids=set()
            for r in rows:
                c=r['command']
                if c['type'] in OPS:
                    targets={i for i in actor_ids if match(c,dict(id=i,class_id=cs['units'][str(i)]['class_']))}
                    target_ids|=targets
                    if targets and c['c'] in (5,13,14,100,101,103,104,105,106,110):reasons.add('direct_economic_actor_parameter')
                    if targets and c['c'] in (26,27):reasons.add('resource_storage_event')
                if c['type'] in (1,6) and c['a'] in ECON_RESOURCE_IDS:reasons.add('economic_player_parameter')
            note=NOTES.get(eid)
            hooks=[r for r in rows if r['command']['type'] in (1,11,21,31) and r['command']['a']==33]
            if note or reasons:
                category,description=note or ('parameter_change',raw['effects'][str(eid)]['name']+'; inspect exact commands and target IDs.')
                special.append(dict(civ_name=name,tech_id=tid,effect_id=eid,source_label=raw['effects'][str(eid)]['name'],
                    category=category,description=description,target_unit_ids=sorted(target_ids),
                    identification='annotated_source_commands' if note else 'structural_economic_match',
                    interpretation_status='engine_behavior_unresolved' if hooks or category in ('coupled_income','passive_income','resource_yield','pasture','area_effect','garrison_income','conditional_income') else 'raw_parameter_change_not_measured_income',
                    evidence=rows))
            # Keep every unclassified unique hook/resource command. This catch-all
            # intentionally includes military mechanisms rather than silently
            # dropping possible economic connections.
            unresolved=[r for r in rows if (r['command']['type'] in (1,6,11,16,21,26,31,36) and r['command']['a'] not in ECON_RESOURCE_IDS)]
            if unresolved and not note:
                candidates.append(dict(civ_name=name,tech_id=tid,effect_id=eid,source_label=raw['effects'][str(eid)]['name'],
                    status='scope_unresolved_may_be_military',evidence=unresolved))

        # Inventory dormant civilization-specific economy effects too, without
        # applying them. Some require a building event, others an unavailable
        # upgrade; preserve that distinction for review instead of assuming
        # that all hidden technologies should activate.
        excluded_by_id={x['tech_id']:x['reason'] for x in excluded}
        for tid_string,t in raw['techs'].items():
            tid=int(tid_string)
            if t['civ']!=civ['id'] or tid in active_ids or str(t['effect_id']) not in raw['effects']:continue
            eid=t['effect_id'];ee=raw['effects'][str(eid)]['effect_commands']
            related=eid in NOTES or any(c['type'] in (1,6) and c['a'] in ECON_RESOURCE_IDS for c in ee)
            related |= any(c['type'] in OPS and c['c'] in (5,13,14,100,103,104,105,106,110)
                           and any(match(c,dict(id=i,class_id=cs['units'][str(i)]['class_'])) for i in actor_ids) for c in ee)
            if not related:continue
            conditional.append(dict(civ_name=name,tech_id=tid,effect_id=eid,source_label=raw['effects'][str(eid)]['name'],
                description=NOTES[eid][1] if eid in NOTES else 'Conditional economic candidate; not applied to final parameters.',
                status=excluded_by_id.get(tid,'not_in_static_activation_log'),
                missing_prerequisite_ids=[i for i in t['required_techs'] if i>=0 and i not in active_ids],
                full_tech_mode=t['full_tech_mode'],definition=t,effect_commands=ee))

        # Economic buildings can carry income logic in base tasks rather than
        # technologies. Feitoria is a concrete example of this path.
        for uid,u in cs['units'].items():
            if not u['tree_node'] or u['tree_node']['Node Status']=='NotAvailable':continue
            n=u['tree_node']['Name'];tasks=u['bird']['tasks'] if u['bird'] else []
            if n not in ('Feitoria','Folwark','Pasture','Fortified Church','Mule Cart','Caravanserai','Settlement'):continue
            special.append(dict(civ_name=name,tech_id=None,effect_id=None,source_label=n,
                category='special_infrastructure',description=n+' base definition: costs, garrison/storage, tasks, drop sites and linked forms retained.',
                target_unit_ids=[int(uid)],identification='available_shipped_tree_building',
                interpretation_status='base_definition_requires_engine_and_scenario',evidence=[dict(unit_id=int(uid),raw_definition=u)]))

        missing=[];free=[];discounted=[]
        for tid,label in STANDARD.items():
            row=techs.get((name,tid));t=raw['techs'][str(tid)]
            standard.append(dict(civ_name=name,tech_id=tid,technology=label,available=int(row is not None),
                free=row['free'] if row else None,instant=row['instant'] if row else None,
                final_research_seconds=row['final_seconds'] if row else None,
                base_cost={r:row['base_'+r] for r in ('food','wood','stone','gold')} if row else None,
                upfront_cost={r:row['upfront_'+r] for r in ('food','wood','stone','gold')} if row else None,
                reward={r:row['reward_'+r] for r in ('food','wood','stone','gold')} if row else None,
                effect_id=t['effect_id'],research_record=row))
            if not row and tid in LAND_STANDARD:missing.append(label)
            if row and row['free']:free.append(label)
            if row and any(row['upfront_'+r]<row['base_'+r]-1e-6 for r in ('food','wood','stone','gold')) and not row['free']:discounted.append(label)
        ss=[s for s in special if s['civ_name']==name]
        summaries.append(dict(civ_name=name,mechanic_count=len(ss),
            unique_economic_effects=[s['description'] for s in ss],
            missing_standard_land_upgrades=missing,free_economic_upgrades=free,discounted_economic_upgrades=discounted,
            unresolved_effects=[r['source_label'] for r in candidates if r['civ_name']==name],
            conditional_economic_effects=[r['source_label'] for r in conditional if r['civ_name']==name],
            labor_per_replacement_status='not_calculated_effective_delivered_gather_rates_required'))

    for r in base.execute('select * from unit_funding_demand'):
        replacements.append(dict(civ_name=r['civ_name'],unit_id=r['unit_id'],unit_name=r['unit_name'],
            **{resource:r['unit_cost_'+resource] for resource in ('food','wood','stone','gold')},
            cost_evidence=json.loads(r['cost_evidence']),labor_seconds=None,
            status='resource_demand_only; rates_maintenance_and_conditional_refunds_not_yet_evaluated'))
    tables={'civilization_summary':summaries,'standard_upgrade_availability':standard,
        'civilization_mechanics':special,'unresolved_effect_candidates':candidates,
        'conditional_economic_effects':conditional,
        'actor_parameters':parameters,'raw_unit_definitions':snapshots,'active_effect_commands':commands,
        'technology_activation':activations,'replacement_resource_costs':replacements,
        'gaia_resource_candidates':[dict(unit_id=int(i),name=u['name'],raw_definition=u) for i,u in source['gaia_resource_candidates'].items()],
        'initial_player_resources':[dict(civ_name=n,resources=c['resources']) for n,c in source['civs'].items()],
        'raw_technologies':[dict(tech_id=int(i),definition=t) for i,t in raw['techs'].items()],
        'raw_effects':[dict(effect_id=int(i),definition=e) for i,e in raw['effects'].items()]}
    for table in ('civilization_parameters','economic_actors','gather_tasks','economic_effects','resource_parameters','economic_technologies','activation_exclusions'):
        tables[table]=[dict(r) for r in base.execute('select * from '+table)]
    manifest=dict(source=raw['source'],scope='Economic source inputs for labor per replacement unit; no calibrated labor estimate yet',
        assumptions=['Post-Imperial, all available upgrades; own team bonus only.',
            'Research/free upgrades are setup advantages; their ongoing actor effects apply once.',
            'Raw work rates and task products are not measured delivered-resource income.',
            'One-time grants, combat/event income, population and economic expansion are separate from harvesting.',
            'All active commands and raw technology/effect definitions retained; unclassified hooks explicitly listed.',
            'Source labels are review hints. Numeric commands take precedence; engine-hook internals are unavailable.',
            'Actor candidates/linked forms do not imply every raw record is available in normal play.',
            'No workforce-per-production-building metric or economic simulation is included.'],
        source_paths=dict(labor_source=str(ROOT/'labor-source.json'),base_inventory=str(ROOT/'labor-base'),
            production_activation=str(ROOT/'corrected-production/production-review.sqlite')),
        simulation_inputs_still_needed=['Drop-off distance and geometry, collision and congestion, carry rounding, task/animation scheduling',
            'Tree depletion and retargeting, mine layout, resource availability and decay',
            'Farm work/buffer/worker interaction, reseed construction time and recurring wood',
            'Area coverage/stacking, garrison composition, trade distance, relic/building counts',
            'Conditional secondary-resource/refund/event semantics and scenario time horizon'])
    tables['metadata']=[dict(key=k,value=v) for k,v in manifest.items()]
    tmp=out/'labor-inputs.build.sqlite'
    if tmp.exists():tmp.unlink()
    db=sqlite3.connect(tmp)
    for table,rows in tables.items():
        if not rows:continue
        fields=[k for k in rows[0] if any(isinstance(r[k],(list,dict)) for r in rows)]
        sql_table(db,table,rows,fields)
    for table,fields in [('civilization_summary','civ_name'),('standard_upgrade_availability','civ_name,tech_id'),
        ('actor_parameters','civ_name,unit_id'),('raw_unit_definitions','civ_name,unit_id'),
        ('replacement_resource_costs','civ_name,unit_id')]:db.execute(f'create unique index {table}_key on {table}({fields})')
    db.commit()
    checks=dict(integrity=db.execute('pragma integrity_check').fetchone()[0]=='ok',all_56_civilizations=len(summaries)==56,
        complete_standard_grid=len(standard)==56*len(STANDARD),all_1030_replacement_costs=len(replacements)==1030,
        no_invented_labor=all(r['labor_seconds'] is None for r in replacements),
        no_invented_delivered_rates=all(r['effective_delivered_rate'] is None for r in parameters),
        no_sustain_building_table='unit_funding_demand' not in tables,
        all_active_commands_exact=all(raw['effects'][str(r['effect_id'])]['effect_commands'][r['command_index']]==r['command'] for r in commands),
        georgian_area_hook=any(r['civ_name']=='Georgians' and r['effect_id']==939 for r in special),
        tupi_refund_retained=any(r['civ_name']=='Tupi' and r['effect_id']==1396 for r in special),
        ethiopian_age_grants_retained=all(any(r['civ_name']=='Ethiopians' and r['effect_id']==i for r in special) for i in (613,614,615)),
        portuguese_feitoria=any(r['civ_name']=='Portuguese' and r['source_label']=='Feitoria' for r in special),
        lithuanian_reward_object=any(r['civ_name']=='Lithuanians' and r['unit_id']==888 for r in snapshots),
        armenian_relic_event_preserved=any(r['civ_name']=='Armenians' and r['tech_id']==949 for r in conditional),
        unavailable_armenian_saw_not_applied=not any(r['civ_name']=='Armenians' and r['tech_id']==962 for r in activations))
    assert all(checks.values()),checks
    db.close();tmp.replace(out/'labor-inputs.sqlite')
    for table in ('civilization_summary','standard_upgrade_availability','civilization_mechanics','conditional_economic_effects','unresolved_effect_candidates','actor_parameters','replacement_resource_costs'):
        csv_write(out/(table.replace('_','-')+'.csv'),tables[table])
    dump(out/'manifest.json',manifest)
    validation=dict(all_passed=True,checks=checks,counts={t:len(r) for t,r in tables.items()})
    dump(out/'validation.json',validation)
    lines=['# Economic inputs for labor per replacement','',
        'Source: user-supplied DAT, archive dated 2026-10-29, SHA-256 `'+raw['source']['sha256']+'`. No external game descriptions used.','',
        'This inventory records parameters, upgrade availability and source evidence for all 56 civilizations. Effective resource income and villager-seconds per replacement are deliberately uncalculated.','',
        'The table lists active economic effect labels and special infrastructure; some labels are internal names. Detailed notes, exact commands, activation prerequisites and unresolved mechanics are in the CSVs and database. A blank direct-bonus list does not imply identical economies: missing upgrades still matter.','',
        '| Civilization | Economic effects/infrastructure detected | Missing standard land upgrades | Free economic research (setup only) |',
        '|---|---|---|---|']
    for r in summaries:
        labels=list(dict.fromkeys(s['source_label'].replace('C-Bonus, ','') for s in special if s['civ_name']==r['civ_name']))
        labels += ['Conditional: '+s['source_label'].replace('C-Bonus, ','') for s in conditional
                   if s['civ_name']==r['civ_name'] and s['effect_id'] in NOTES]
        lines.append('| '+r['civ_name']+' | '+('; '.join(labels) or 'No direct effect identified')+' | '+('; '.join(r['missing_standard_land_upgrades']) or 'None')+' | '+('; '.join(r['free_economic_upgrades']) or 'None')+' |')
    lines+=['','## Mechanics requiring separate treatment','', '| Civilization | Mechanic | Source effect |','|---|---|---|']
    for s in special:
        if s['effect_id'] in NOTES:
            lines.append('| '+s['civ_name']+' | '+s['description']+' | '+str(s['effect_id'])+' |')
    lines+=['','## Files','',
        '- `labor-inputs.sqlite`: full relational inventory, raw definitions, active commands and provenance.',
        '- `civilization-summary.csv`: all 56 civilizations, upgrade gaps, free/discounted research and unresolved labels.',
        '- `civilization-mechanics.csv`: classified economic effects and special infrastructure with exact evidence.',
        '- `standard-upgrade-availability.csv`: available/missing/free/instant, costs, rewards, research time and modifiers.',
        '- `actor-parameters.csv`: base/final work, movement, carry, population, costs, drop sites and evidence.',
        '- `replacement-resource-costs.csv`: 1,030 advisor entries; labor remains null pending calibrated rates.',
        '- `unresolved-effect-candidates.csv`: raw hooks/resources whose economic scope is not established; includes military effects.',
        '- `conditional-economic-effects.csv`: dormant economic candidates and exact prerequisites/events, including unavailable-upgrade branches; these are not applied to final work parameters.',
        '- `manifest.json`, `validation.json`: assumptions, limitations, source identity and verification.','',
        'Raw definitions preserve tasks, farm buffers, resource storage/decay, drop sites, garrisons, construction/training definitions and age/annex forms. Resource-object candidates include scenario/editor records and must be filtered for a later simulation.','',
        'Future labor model: replacement resource vector plus recurring inputs (such as reseeding wood/time), divided by calibrated delivered-output rates. Mixed-output jobs require joint allocation; refunds and passive income require explicit conditions. Research setup costs are excluded from each replacement.']
    (out/'README.md').write_text('\n'.join(lines)+'\n')
    with zipfile.ZipFile(out.parent/'labor-inputs-review.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.iterdir()):
            if f.is_file():z.write(f,f.name)
        for name in ('extract_economy_inputs.py','build_labor_inputs_review.py','build_economy_review.py','build_production_review.py','build_upgrade_review.py'):
            z.write(Path(__file__).parent/name,'generators/'+name)
    print(json.dumps(validation,indent=2))


if __name__=='__main__':
    main()
