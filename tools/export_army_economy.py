#!/usr/bin/env python3
"""Source-only post-Imperial inputs for every civilization; no online constants."""
import json,os,sqlite3
from pathlib import Path
from army_economics_paths import scratch_path
from eco_scope import mechanic_scope, blocks_land_labor
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('ARMY_CONTEXT_OUT',str(ROOT/'aoe2x/js_simulation/calibration/economy/army-context-2026-11-09')))
DB=scratch_path('economy-review/labor-inputs/labor-inputs.sqlite')

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(f'file:{DB}?mode=ro',uri=True);c.row_factory=sqlite3.Row
 actors={(r['civ_name'],r['unit_id']):dict(r) for r in c.execute('select * from actor_parameters')}
 params={(r['civ_name'],r['resource_id']):r['final_parameter_value'] for r in c.execute('select * from resource_parameters')}
 def raw(civ,uid):return json.loads(c.execute('select raw_definition from raw_unit_definitions where civ_name=? and unit_id=?',(civ,uid)).fetchone()[0])
 def worker(civ,uid,mult):
  a=actors[civ,uid];base=json.loads(a['base_parameters']);final=json.loads(a['final_parameters']);carry=base['carry_capacity']
  for e in json.loads(a['evidence']):
   if e['field']=='carry_capacity':
    cmd=e['command'];carry=cmd['d'] if cmd['type']==0 else carry+cmd['d'] if cmd['type']==4 else carry*cmd['d']
    carry=int(carry+.5)
  return dict(work_rate=final['work_rate'],speed=final['movement_speed'],carry_capacity=carry,
              radius=raw(civ,uid)['collision_size_x'],task_output_multiplier=mult)
 eco=ROOT/'aoe2x/js_simulation/calibration/economy'
 farm_base=json.loads((eco/'farms-refinement-2026-11-09/fixture-full.json').read_text())
 wood_base=json.loads((eco/'wood-2026-11-09/fixture-w3-c2.json').read_text())
 gold_base=json.loads((eco/'gold-2026-11-09/fixture.json').read_text())
 specs=[]
 for row in c.execute('select * from civilization_parameters order by civ_name'):
  p=dict(row);name=p['civ_name'];jobs={}
  farm=json.loads(json.dumps(farm_base));farm['source']={'database':str(DB),'civ_name':name}
  farm['worker']=worker(name,259,p['farmer_task_multiplier'])
  farm['farm'].update(food=p['farm_food_parameter'],generation_rate=p['farm_work_rate'],wood_cost=p['farm_wood_cost'])
  build=json.loads(actors[name,118]['final_parameters'])['work_rate'];farm['farm']['build_seconds']=15/build
  # Bonuses are activated by source hooks/parameters, not civilization names.
  hooks=[json.loads(r[0]) for r in c.execute("select command from active_effect_commands where civ_name=? and effect_name like '%Instant Farmers%'",(name,))]
  farm['behavior']['auto_deposit']=any(x['a']==33 and x['d']==50 for x in hooks)
  if params.get((name,238),-1)>=0 and params.get((name,239),-1)>=0:
   origins=[(0,-3),(3,0),(0,3),(-3,0),(3,-3),(3,3),(-3,3),(-3,-3),(-6,0),(6,0)]
   farm['mill']={'x0':0,'y0':0,'x1':3,'y1':3}
   farm['farms']=[dict(id=i,x0=x,y0=y,x1=x+3,y1=y+3,position='inner' if i<8 else 'outer',instant_food=params[name,237] if i<8 else 0) for i,(x,y) in enumerate(origins)]
  jobs['food']=dict(engine='farm' if p['farm_available'] else 'unsupported_pasture',fixture=farm)
  wood=json.loads(json.dumps(wood_base));wood['source']={'database':str(DB),'civ_name':name}
  wood['worker'].update(worker(name,123,p['lumberjack_task_multiplier']))
  # With no generation pool, convert natural resource units to credited units.
  wood['worker']['work_rate']*=p['lumberjack_task_multiplier'];wood['tree']['wood']*=p['lumberjack_task_multiplier']
  mule=c.execute("select raw_definition from raw_unit_definitions where civ_name=? and name='Mule Cart' and selection='tree_available'",(name,)).fetchone()
  if mule:
   cart=json.loads(mule[0]);wood['camp'].update(half_width=cart['collision_size_x'],half_height=cart['collision_size_y'])
  jobs['wood']=dict(engine='wood',fixture=wood)
  for resource,uid,rid,prefix in [('gold',579,47,'gold_miner'),('stone',124,79,'stone_miner')]:
   f=json.loads(json.dumps(gold_base));f['source']={'database':str(DB),'civ_name':name}
   f['worker'].update(worker(name,uid,p[prefix+'_task_multiplier']))
   f['worker']['work_rate']*=p[prefix+'_task_multiplier']
   mineral=json.loads(c.execute('select raw_definition from gaia_resource_candidates where unit_id=?',(66 if resource=='gold' else 102,)).fetchone()[0])
   mineral_amount=next(x['amount'] for x in mineral['resource_storages'] if x['type']==(3 if resource=='gold' else 2))
   f['gold']['amount']=mineral_amount*p[prefix+'_task_multiplier']
   if mule:f['camp'].update(half_width=cart['collision_size_x'],half_height=cart['collision_size_y'])
   jobs[resource]=dict(engine='mine',fixture=f)
  mechanisms=[dict(r) for r in c.execute('select * from civilization_mechanics where civ_name=?',(name,))]
  for m in mechanisms:m['late_game_scope']=mechanic_scope(m)
  flags=[]
  for m in mechanisms:
   if blocks_land_labor(m):
    flags.append(m['source_label']+': conditional or engine-hook income not credited in baseline')
  if not p['farm_available']:flags.append('Pasture has multiple herders/annex mechanics; ordinary farm rates must not be substituted')
  specs.append(dict(civ_name=name,jobs=jobs,flags=flags,farm_food=p['farm_food_parameter'],farm_wood=p['farm_wood_cost'],farm_yield=p['farmer_task_multiplier'],mechanisms=mechanisms))
 (OUT/'eco-inputs.json').write_text(json.dumps(specs,indent=2)+'\n')
 (OUT/'PLAN.md').write_text('''# Army context analysis plan

1. Use the supplied DAT extract, corrected production database, existing Imperial-priced upgrade database and consolidated matchup runs. Preserve all originals.
2. Replay available economic effects for all 56 civs, with integer carry rounding. Run source-derived food/wood/gold/stone scenarios; reuse identical physical parameter sets. Add generic yield, instant-collection and auto-deposit policies for farming.
3. Record every known economic mechanic with a modeled, conditional, event-only or unresolved status. Never substitute generic farming for unavailable farms or guess compiled-engine hook formulas.
4. Build one SQLite review database containing source inventories, rates and individual runs, unit replacement labor, production routes, research costs/time/buildings and every selected battle.
5. For every saved run with winner HP fraction below 0.25, compare dead-unit replacement labor and production queue time; report shared-upgrade cost/time separately from exclusive upgrades and infrastructure.
6. Flag attrition reversals and concurrent queue advantages as candidates, with ±5% resource-rate sensitivity. Keep HP-equivalent damage replacement as a separate diagnostic, because wounded survivors are not dead units.
7. Validate coverage, identity joins, accounting, special policies and missing-data exclusions; export all candidates and civ rates, then write the findings and limitations.

Baseline: post-Imperial with every available upgrade, own bonuses only, no allied team bonuses, no relics/trade/market purchases, no externally supplied resources, no covered church aura. Resource allocation can be optimized separately for each unit. Buildings are already built for replacement labor; their costs remain separate. All battle outcomes are retained. A candidate is not a newly simulated battle victory. No army-cost normalization is used for upgrade comparison.
''')
 print('Exported',len(specs),'civilizations')

if __name__=='__main__':main()
