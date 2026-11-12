#!/usr/bin/env python3
"""Audit farming effects and economic research against the supplied DAT extract."""
import csv
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

from build_labor_inputs_review import STANDARD, LAND_STANDARD
from eco_scope import mechanic_scope

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'aoe2x/js_simulation/calibration/economy/army-context-2026-11-10'
OLD = OUT.with_name('army-context-2026-11-09')
RES = ('food', 'wood', 'stone', 'gold')
STANDARD = {**STANDARD, 17: 'Banking', 23: 'Coinage', 373: 'Shipwright', 22: 'Loom'}
SPECIAL = {'Bengalis': [834], 'Bohemians': [231, 252, 785], 'Burgundians': [754],
           'Hindustanis': [506], 'Italians': [499], 'Vietnamese': [629],
           'Wei': [1061], 'Spanish': [440], 'Mongols': [487], 'Khitans': [1014,1013,1012]}
SPECIAL_EFFECTS = {
    834:'Villager population use becomes 0.9; population capacity, not faster work.',
    231:'Bohemian hidden effect also increases villager HP; protection only.',
    252:'Bohemian hidden effect multiplies villager movement by 1.15; included in walking.',
    785:'Monastery technologies replace their gold cost with food, including Fervor and Sanctity.',
    754:'Farming-linked gold income; source parameter 236 and hook 14 retained. Numerical gold rate unresolved.',
    506:'Gold-miner work ×1.10; separate trade, passive-gold and market effects also retained.',
    499:'Trade-unit costs ×0.50; requires a trade scenario.',
    629:'Woodcutting-linked gold income; parameter 266 starts at 1.5 and follows three researched wood-upgrade modifiers. Numerical gold rate unresolved.',
    1061:'Persistent income parameter 287 = 3 and hook 4; scope/counting formula unresolved.',
    440:'Villager combat/survival improvement; no harvesting-rate increase.',
    487:'Housing-loss protection; no harvesting-rate increase.',
    1014:'Pasture food parameter +115 × farm-upgrade multiplier; capacity parameter +1.',
    1013:'Pasture food parameter +230 × farm-upgrade multiplier; capacity parameter +2.',
    1012:'Pasture food parameter +345 × farm-upgrade multiplier; capacity parameter +3.',
}
REVIEW_DESCRIPTIONS = {
    953:'Mule Cart resource costs ×0.75 (25% cheaper).',
    956:'Each available wood upgrade also applies work ×1.06667: approximately +28% per level instead of +20%. These enhanced effects are already modeled.',
    958:'Each available gold-mining upgrade also applies work ×1.05217: approximately +21% per level instead of +15%. These enhanced effects are already modeled.',
    959:'Each available stone-mining upgrade also applies work ×1.05217: approximately +21% per level instead of +15%. These enhanced effects are already modeled.',
    816:'Folwark replaces the Mill; instant collection is 10% of current farm food, recalculated after farming upgrades. Modeled on creation/reseeding for covered farms.',
    7:'Farmer work ×1.23 and Farm generation ×1.15; both are modeled separately.',
    898:'Villager work ×1.05, farmer work additionally ×1.038095, and Farm generation ×1.05; all are modeled separately.',
}


def encoded(v):
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v


def save_table(db, name, rows):
    db.execute(f'DROP TABLE IF EXISTS "{name}"')
    cols = list(rows[0])
    types = []
    for key in cols:
        values = [r[key] for r in rows if r[key] is not None]
        types.append('INTEGER' if values and all(isinstance(v, (int, bool)) for v in values)
                     else 'REAL' if values and all(isinstance(v, (int, float)) for v in values) else 'TEXT')
    db.execute(f'CREATE TABLE "{name}" (' + ','.join(f'"{k}" {t}' for k, t in zip(cols, types)) + ')')
    db.executemany(f'INSERT INTO "{name}" VALUES ({",".join("?" for _ in cols)})',
                   [[encoded(r[k]) for k in cols] for r in rows])
    with (OUT / (name.replace('late_', '').replace('_', '-') + '.csv')).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows({k: encoded(v) for k, v in r.items()} for r in rows)


def near(a, b):
    assert math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-6), (a, b)


def resource_cost(r, prefix):
    return {k: r[prefix + '_' + k] for k in RES}


def change_text(r):
    if not r['available']:
        return ''
    if r['automatic_free']:
        return 'free and instant'
    parts = []
    for res in RES:
        base, final = r['base_cost'][res], r['upfront_cost'][res]
        if base and abs(final - base) > 0.001:
            parts.append(f'{res} cost {(final / base - 1) * 100:+.1f}%')
        elif not base and final:
            parts.append(f'{final:g} {res} added')
    if r['base_seconds'] and abs(r['seconds'] - r['base_seconds']) > .001:
        parts.append(f'research time {(r["seconds"] / r["base_seconds"] - 1) * 100:+.1f}%')
    for res in RES:
        if r['reward'][res]:
            parts.append(f'+{r["reward"][res]:g} {res} on completion')
    return '; '.join(parts)


def main():
    db = sqlite3.connect(OUT / 'army-context.sqlite')
    db.row_factory = sqlite3.Row
    specs = {r['civ_name']: r for r in json.loads((OUT / 'eco-inputs.json').read_text())}
    techs = {(r['civ_name'], r['tech_id']): dict(r) for r in db.execute('select * from research_civilization_upgrades')}
    rawtechs = {r['tech_id']: json.loads(r['definition']) for r in db.execute('select * from eco_raw_technologies')}
    effects = {r['effect_id']: json.loads(r['definition']) for r in db.execute('select * from eco_raw_effects')}
    rawunits = {(r['civ_name'], r['unit_id']): json.loads(r['raw_definition']) for r in db.execute('select * from eco_raw_unit_definitions')}
    buildings = {(r['civ_name'], r['building_id']): dict(r) for r in db.execute('select * from research_buildings')}
    rates = {(r['civ_name'], r['resource']): r['rate'] for r in db.execute('select * from gather_rates')}
    parameters = {(r['civ_name'], r['resource_id']): dict(r) for r in db.execute('select * from eco_resource_parameters')}
    commands = defaultdict(list)
    for r in db.execute('select * from eco_active_effect_commands order by civ_name,sequence'):
        item = dict(r);item['command'] = json.loads(r['command']);commands[r['civ_name']].append(item)
        assert item['command'] == effects[r['effect_id']]['effect_commands'][r['command_index']]
    active = defaultdict(set)
    for r in db.execute('select civ_name,tech_id from eco_technology_activation'):
        active[r['civ_name']].add(r['tech_id'])
    conditional=[];unit_events=defaultdict(list)
    for source in db.execute('select * from eco_conditional_economic_effects'):
        row=dict(source);definition=json.loads(row['definition']);cmds=json.loads(row['effect_commands'])
        triggers=[i for i in definition['required_techs'] if i in STANDARD]
        grants=[c for c in cmds if c['type']==7]
        missing=json.loads(row['missing_prerequisite_ids'])
        scope=('research_linked_unit_grant' if triggers and grants else 'unavailable_upgrade_dependency' if missing and triggers
               else 'conditional_relic_event' if row['effect_id'] in [951,952] else 'excluded_start_or_age_scenario_event')
        entry=dict(civ_name=row['civ_name'],hidden_tech_id=row['tech_id'],effect_id=row['effect_id'],
                   mechanic=row['source_label'],scope=scope,trigger_technology_ids=triggers,
                   trigger_technologies=[STANDARD[i] for i in triggers],
                   research_available=all((row['civ_name'],i) in techs for i in triggers),
                   other_required_tech_ids=[i for i in definition['required_techs'] if i>=0 and i not in triggers],
                   full_tech_mode=row['full_tech_mode'],missing_prerequisite_ids=missing,
                   creation_commands=grants,effect_commands=cmds,
                   credited_resource_discount=0,credited_gather_multiplier=1,
                   status='retained_event_semantics_not_simulated')
        conditional.append(entry)
        if scope=='research_linked_unit_grant' and entry['research_available']:
            for tid in triggers:unit_events[row['civ_name'],tid].append(entry)
    standard, special, farms, scopes, civs = [], [], [], [], []
    for civ, spec in sorted(specs.items()):
        resources = json.loads(db.execute('select resources from eco_initial_player_resources where civ_name=?', (civ,)).fetchone()[0])
        resources = dict(enumerate(resources))
        actor_rows = []
        evidence = []
        # Replay raw commands independently of cached actor/resource summaries.
        for uid in [259, 214, 50]:
            u = rawunits[civ, uid]
            v = dict(speed=u['speed'],work=u['bird']['work_rate'],carry=u['resource_capacity'])
            cost = {k: 0.0 for k in RES}
            for x in u['creatable']['resource_costs']:
                if x['type'] in [0, 1, 2, 3] and x['flag']:
                    cost[{0:'food',1:'wood',2:'stone',3:'gold'}[x['type']]] += x['amount']
            for s in commands[civ]:
                c = s['command']
                if c['type'] not in [0, 4, 5] or not (c['a'] == uid or c['a'] == -1 and c['b'] == u['class_']):
                    continue
                op = lambda x: c['d'] if c['type'] == 0 else x+c['d'] if c['type'] == 4 else x*c['d']
                key = {5:'speed',13:'work',14:'carry'}.get(c['c'])
                if key:
                    v[key] = op(v[key])
                    if key == 'carry':v[key] = math.floor(v[key] + .5)
                    evidence.append(dict(unit_id=uid,field=key,tech_id=s['tech_id'],effect_id=s['effect_id'],command=c))
                if c['c'] in [100,103,104,105,106]:
                    for res in RES if c['c'] == 100 else [{103:'food',104:'wood',105:'gold',106:'stone'}[c['c']]]:
                        cost[res] = op(cost[res])
            actor_rows.append((v,cost))
        for s in commands[civ]:
            c = s['command'];rid=c['a']
            if c['type'] == 1:
                value = c['d'] * resources.get(c['c'], 0) if c['c'] >= 0 else c['d']
                resources[rid] = value if c['b'] == 0 else resources.get(rid,0)+value
            elif c['type'] == 6:
                resources[rid] = resources.get(rid,0)*c['d']
        f = spec['jobs']['food']['fixture'];farmer,fcost=actor_rows[0];farm,farmcost=actor_rows[2]
        assert actor_rows[0][0] == actor_rows[1][0], civ
        for field,key in [('speed','speed'),('carry','carry_capacity'),('work','work_rate')]:near(farmer[field],f['worker'][key])
        near(farm['work'],f['farm']['generation_rate']);near(farmcost['wood'],f['farm']['wood_cost'])
        near(resources[36],f['farm']['food']);near(resources[190],f['worker']['task_output_multiplier'])
        for rid in [36,69,190,236,237,238,239,266,287,288,289,290,293,294]:
            if (civ,rid) in parameters:near(resources[rid],parameters[civ,rid]['final_parameter_value'])
        for tid in [14,13,12,213,249,1014,1013,1012]:
            assert ((civ,tid) in techs) == (tid in active[civ]), (civ,tid)
        farms.append(dict(civ_name=civ,farming_system='farm' if f and spec['jobs']['food']['engine']=='farm' else 'pasture',
            horse_collar=int((civ,14) in techs),heavy_plow=int((civ,13) in techs),crop_rotation=int((civ,12) in techs),
            wheelbarrow=int((civ,213) in techs),hand_cart=int((civ,249) in techs),
            pasture_upgrades=[STANDARD[t] for t in [1014,1013,1012] if (civ,t) in techs],
            farm_food=resources[36] if spec['jobs']['food']['engine']=='farm' else None,
            farm_wood=farmcost['wood'] if spec['jobs']['food']['engine']=='farm' else None,
            farmer_carry=farmer['carry'] if spec['jobs']['food']['engine']=='farm' else None,
            farmer_speed=farmer['speed'],farmer_work=farmer['work'],farm_generation=farm['work'],farm_yield=resources[190],
            auto_deposit=f['behavior'].get('auto_deposit',False),folwark_instant_food=resources[237] if civ=='Poles' else None,
            pasture_food_parameter=resources[288] if civ=='Khitans' else None,
            pasture_animal_count_parameter=resources[289] if civ=='Khitans' else None,
            pasture_herder_count_parameter=resources[290] if civ=='Khitans' else None,
            modeled_food_per_minute=rates[civ,'food']*60 if rates[civ,'food'] else None,
            evidence=evidence,audit='raw_replay_matches_simulation_inputs'))
        for tid,label in STANDARD.items():
            record=techs.get((civ,tid));raw=rawtechs[tid]
            base={k:0.0 for k in RES}
            for x in raw['resource_costs']:
                if x['type'] in [0,1,2,3] and x['flag']:base[{0:'food',1:'wood',2:'stone',3:'gold'}[x['type']]]+=x['amount']
            scope='core_land' if tid in LAND_STANDARD else 'pasture' if tid in [1012,1013,1014] else 'water' if tid in [906,65,373] else 'worker_protection' if tid==22 else 'construction' if tid==54 else 'trade_or_market'
            b=buildings.get((civ,record['selected_building_id'])) if record else None
            r=dict(civ_name=civ,tech_id=tid,technology=label,scope=scope,available=bool(record),
                base_cost=base,upfront_cost=resource_cost(record,'upfront') if record else None,
                reward=resource_cost(record,'reward') if record else None,net_cost=resource_cost(record,'net') if record else None,
                base_seconds=record['base_seconds'] if record else None,seconds=record['final_seconds'] if record else None,
                automatic_free=bool(record and record['automatic_free']),
                building=b['building_name'] if b else None,building_id=b['building_id'] if b else None,
                building_cost=resource_cost(b,'cost') if b else None,
                queue_building_required=bool(record and not record['automatic_free']),
                modifiers=json.loads(record['modifiers']) if record else [],
                pricing_tech_ids=json.loads(record['pricing_tech_ids']) if record else [],
                completion_unit_reward_events=unit_events[civ,tid])
            r['advantage']=change_text(r);standard.append(r)
        for tid in SPECIAL.get(civ,[]):
            t=techs[civ,tid];b=buildings[civ,t['selected_building_id']]
            descendants={tid}
            while True:
                extra={i for i in active[civ] if any(req in descendants for req in rawtechs[i]['required_techs'])}
                if extra<=descendants:break
                descendants|=extra
            special.append(dict(civ_name=civ,tech_id=tid,technology=t['technology'],upfront_cost=resource_cost(t,'upfront'),
                reward=resource_cost(t,'reward'),net_cost=resource_cost(t,'net'),seconds=t['final_seconds'],
                building=b['building_name'],building_cost=resource_cost(b,'cost'),
                pricing_tech_ids=json.loads(t['pricing_tech_ids']),modifiers=json.loads(t['modifiers']),
                direct_commands=effects[rawtechs[tid]['effect_id']]['effect_commands'],
                active_descendant_effects=[s for s in commands[civ] if s['tech_id'] in descendants-{tid}],
                effect_summary=SPECIAL_EFFECTS[tid],
                note='All available upgrades; castle research uses Conscription. Workload is not build-order elapsed time.'))
        local_scopes=[]
        for m in spec['mechanisms']:
            scope=mechanic_scope(m)
            row=dict(civ_name=civ,tech_id=m['tech_id'],effect_id=m['effect_id'],mechanic=m['source_label'],
                     scope=scope,description=REVIEW_DESCRIPTIONS.get(m['effect_id'],m['description']),evidence=m['evidence'])
            scopes.append(row);local_scopes.append(row)
        own=[r for r in standard if r['civ_name']==civ]
        grouped=defaultdict(list)
        for r in own:
            if r['advantage']:grouped[r['advantage']].append(r['technology'])
        adv=[f'{", ".join(names)}: {effect}' for effect,names in grouped.items()]
        event_techs=[r['technology'] for r in own if r['completion_unit_reward_events']]
        if event_techs:adv.append(f'Research-linked villager-grant hooks for {len(event_techs)} available economic technologies; spawn/count semantics unresolved, no resource refund credited')
        civs.append(dict(civ_name=civ,
            missing_standard_land_upgrades=[r['technology'] for r in own if r['scope']=='core_land' and not r['available']],
            technology_advantages=adv,
            unit_reward_technologies=event_techs,
            sustained_land_effects=list(dict.fromkeys(r['description'] for r in local_scopes if r['scope']=='sustained_land_parameters')),
            conditional_land_effects=list(dict.fromkeys(r['description'] for r in local_scopes if r['scope']=='conditional_land_income')),
            infrastructure_effects=list(dict.fromkeys(r['description'] for r in local_scopes if r['scope']=='infrastructure_or_worker_replacement')),
            nonland_or_capacity_effects=list(dict.fromkeys(r['description'] for r in local_scopes if r['scope'].startswith('conditional_') and r['scope']!='conditional_land_income' or r['scope']=='population_capacity')),
            excluded_early_effects=list(dict.fromkeys(r['mechanic'] for r in local_scopes if r['scope'].startswith('excluded_')))))
    assert len(farms)==56 and len(standard)==56*len(STANDARD)
    assert not any(r['scope']=='review_scope_required' for r in scopes),[(r['civ_name'],r['mechanic']) for r in scopes if r['scope']=='review_scope_required']
    assert all(not specs[c]['flags'] for c in ['Portuguese','Bengalis','Mapuche','Varangians'])
    assert all(specs[c]['flags'] for c in ['Burgundians','Vietnamese','Poles','Shu','Wei','Georgians','Malians','Tupi'])
    old_rates={(r['civ_name'],r['resource']):r['rate'] for r in json.loads((OLD/'gather-rates.json').read_text())}
    assert rates==old_rates,'Scope and research audit must not silently change numerical harvesting results'
    old=sqlite3.connect(f'file:{OLD / "army-context.sqlite"}?mode=ro',uri=True);old.row_factory=sqlite3.Row
    differences=[]
    for before in old.execute('select * from research_civilization_upgrades'):
        after=techs[before['civ_name'],before['tech_id']]
        assert all(before[p+'_'+r]==after[p+'_'+r] for p in ['base','upfront','reward','net'] for r in RES)
        if before['final_seconds']!=after['final_seconds']:
            assert before['civ_name']=='Persians'
            differences.append(dict(civ_name=before['civ_name'],technology=before['technology'],tech_id=before['tech_id'],
                previous_seconds=before['final_seconds'],corrected_seconds=after['final_seconds']))
    assert len(differences)==12
    for name,rows in [('late_farming_audit',farms),('late_eco_technology_ledger',standard),('late_unique_eco_technologies',special),
                      ('late_effect_scopes',scopes),('late_civilization_review',civs),('late_research_corrections',differences),
                      ('late_conditional_event_review',conditional)]:
        save_table(db,name,rows)
    db.execute('CREATE VIEW IF NOT EXISTS eco_technology_advantages AS SELECT * FROM late_eco_technology_ledger WHERE available=1 AND (advantage!=\'\' OR completion_unit_reward_events!=\'[]\')')
    db.commit();assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
    summary=dict(civilizations=56,farming_audits=len(farms),available_horse_collar=sum(r['horse_collar'] for r in farms),
                 available_heavy_plow=sum(r['heavy_plow'] for r in farms),available_crop_rotation=sum(r['crop_rotation'] for r in farms),
                 all_have_wheelbarrow_and_hand_cart=all(r['wheelbarrow'] and r['hand_cart'] for r in farms),
                 technology_grid_rows=len(standard),unique_or_special_tech_rows=len(special),mechanics_scoped=len(scopes),
                 conditional_events_reviewed=len(conditional),
                 research_linked_unit_reward_techs=sum(bool(r['completion_unit_reward_events']) for r in standard),
                 technology_advantage_civs=[r['civ_name'] for r in civs if r['technology_advantages']],
                 excluded_early_mechanics=sum(r['scope'].startswith('excluded_') for r in scopes),
                 raw_commands_verified=sum(map(len,commands.values())),raw_farming_replay='passed',
                 research_corrections=differences,existing_gather_rates_unchanged=True,
                 pasture_numerical_rate_still_unresolved=True)
    (OUT/'late-game-validation.json').write_text(json.dumps(summary,indent=2)+'\n')
    def cost(c):return ', '.join(f'{v:g} {k}' for k,v in c.items() if v) or 'free'
    lines=['# Late-game economy and technology review','',
        'Source: supplied DAT archive, SHA-256 `d0aefd92428e2215d6f4d9b1d544901e6f171e19183f9e0b88218de5153a337f`. All prices assume Imperial Age and all available upgrades. No external bonus descriptions were used.','',
        'Hunt, berries, temporary animal-food advantages, starting resources and age-up grants are excluded from the settled land economy. Research discounts, rewards and speed remain an upfront investment ledger. Free research contributes its ordinary lasting effect once; it does not add a permanent gather multiplier. Water, trade, relic, garrison, population and combat-event effects are retained as conditional systems.','',
        '## Corrections and coverage','',
        '- Every farming fixture was independently replayed from raw source commands, for both farmer sexes and the Farm. All 56 matched; no missing standard farm technology was found.',
        '- 55 civilizations have Horse Collar and Heavy Plow; 36 have Crop Rotation. All 56 have Wheelbarrow and Hand Cart. Khitans use Domestication, Pastoralism and Transhumance instead of farms.',
        '- Persian research now uses Imperial Town Center/Dock forms: Wheelbarrow 62.50 s, Hand Cart 45.83 s, Gillnets 25.00 s, Fishing Lines 16.67 s. Twelve research rows changed; all technology costs stayed identical.',
        '- Portuguese berry wood, Mapuche foraging and other excluded food-source effects no longer mark ordinary land replacement calculations as unresolved. Persistent secondary-income hooks remain flagged.',
        '- All 28 dormant/event-gated economic effects were reviewed. Wei has villager-grant hooks attached to 14 available economic technologies (the Two-Man Saw and Guilds branches are unavailable). These also require Town Center Spawn gates; event multiplicity/timing remains unvalidated and no food refund or extra farmer rate is credited.',
        '- Existing gather-rate estimates are numerically unchanged. Khitan pasture rate and compiled-engine secondary-income formulas remain unresolved. Raw parameters are not advertised as measured income.','',
        '## Economic research advantages','',
        '| Civilization | Source-derived cost/time advantage |','|---|---|',
        *[f"| {r['civ_name']} | {'; '.join(r['technology_advantages'])} |" for r in civs if r['technology_advantages']],'',
        'Wei is a conditional unit-reward entry; the other listed rows are price/time/research-gold differences. Other civilizations have no special price/time advantage in the listed standard economic technologies. Enhanced technology effects, unique paid technologies and unavailable upgrades are tracked below and in separate CSV columns.','',
        '## Unique and worker-support technologies','',
        '| Civilization | Technology | Upfront cost | Research seconds | Building | Building cost | Lasting effect |','|---|---|---|---:|---|---|---|',
        *[f"| {r['civ_name']} | {r['technology']} | {cost(r['upfront_cost'])} | {r['seconds']:.2f} | {r['building']} | {cost(r['building_cost'])} | {r['effect_summary']} |" for r in special],'',
        'Castle durations include generic Conscription; this is not a civilization-specific speed advantage. Each building cost is listed for review, not charged repeatedly for every technology. Fervor/Sanctity prices for Bohemians assume Hussite Reforms, whose own cost is recorded. Protection and population effects do not increase harvesting directly.','',
        '## Complete farming availability audit','',
        'HC = Horse Collar; HP = Heavy Plow; CR = Crop Rotation. All listed farm civilizations have HC and HP. Missing CR is retained as a lower-capacity farm, not counted as cheaper/faster research. Food/min is the previously modeled 10-worker scenario including reseeding. Farm food is the natural resource capacity: Mayan credited yield is 550 × 1.15 = 632.5 food.','',
        '| Civilization | Farming upgrades | Farm food | Farm wood | Farmer carry | Food/min estimate | Other missing land eco techs |','|---|---|---:|---:|---:|---:|---|',
        *[f"| {f['civ_name']} | {'HC, HP, CR' if f['crop_rotation'] else 'HC, HP' if f['horse_collar'] else ', '.join(f['pasture_upgrades'])} | {format(f['farm_food'],'.6g') if f['farm_food'] is not None else '—'} | {format(f['farm_wood'],'.6g') if f['farm_wood'] is not None else '—'} | {f['farmer_carry'] if f['farmer_carry'] is not None else '—'} | {format(f['modeled_food_per_minute'],'.2f') if f['modeled_food_per_minute'] else 'unresolved'} | {', '.join(x for x in next(c for c in civs if c['civ_name']==f['civ_name'])['missing_standard_land_upgrades'] if x not in ['Horse Collar','Heavy Plow','Crop Rotation']) or '—'} |" for f in farms],'',
        '## Civilization-by-civilization lasting effects','',
        '| Civilization | Sustained land parameters / infrastructure | Additional land income needing a model | Other conditional systems | Excluded early food/grants |',
        '|---|---|---|---|---|',
        *[f"| {r['civ_name']} | {'; '.join(r['sustained_land_effects']+r['infrastructure_effects']) or '—'} | {'; '.join(r['conditional_land_effects']) or '—'} | {'; '.join(r['nonland_or_capacity_effects']) or '—'} | {'; '.join(r['excluded_early_effects']) or '—'} |" for r in civs],'',
        '## Database','',
        'The joined `army-context.sqlite` includes `late_farming_audit`, `late_eco_technology_ledger`, `late_unique_eco_technologies`, `late_effect_scopes`, `late_civilization_review`, `late_research_corrections`, and `late_conditional_event_review`. `eco_technology_advantages` exposes the technology exceptions. The canonical current economic research ledger is `late_eco_technology_ledger`; `eco_` source-copy tables retain historical input records for provenance, including their earlier research times. Every current ledger retains IDs, modifier evidence, costs by resource, rewards, research locations and construction costs. The original 2026-11-09 snapshot is preserved.','']
    lines += ['## Reproduce in this worktree','',
        '```bash',
        'python tools/build_upgrade_review.py --output /workspace/scratch/research-review/late-game-2026-11-10',
        'export ARMY_CONTEXT_OUT=/workspace/aoe2_matchup-advisor/aoe2x/js_simulation/calibration/economy/army-context-2026-11-10',
        'export ARMY_RESEARCH_DB=/workspace/scratch/research-review/late-game-2026-11-10/unit-upgrades.sqlite',
        'python tools/export_army_economy.py',
        'node tools/run_army_economy.mjs',
        'python tools/build_army_context.py',
        'python tools/review_late_game_economy.py',
        'python tools/validate_army_context.py',
        '```','',
        'Unchanged physical scenarios reuse cached runs only when the fixture and engine hashes match. The source databases and prior fixture files referenced by the tools remain required inputs.','']
    (OUT/'LATE-GAME-REVIEW.md').write_text('\n'.join(lines))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
