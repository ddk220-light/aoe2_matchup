#!/usr/bin/env python3
"""Export generic wood profiles and finite forest inputs from the supplied DAT."""
import json
import sqlite3
from pathlib import Path
from army_economics_paths import scratch_path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'aoe2x/js_simulation/calibration/economy/wood-2026-11-09'
OUT.mkdir(parents=True,exist_ok=True)
DB=scratch_path('economy-review/labor-inputs/labor-inputs.sqlite')
c=sqlite3.connect(f'file:{DB}?mode=ro',uri=True);c.row_factory=sqlite3.Row
def unit(uid):return json.loads(c.execute("select raw_definition from raw_unit_definitions where civ_name='Byzantines' and unit_id=?",(uid,)).fetchone()[0])
u=unit(123);female=unit(218);camp=unit(562)
tree=json.loads(c.execute('select raw_definition from gaia_resource_candidates where unit_id=349').fetchone()[0])
actor=c.execute("select * from actor_parameters where civ_name='Byzantines' and unit_id=123").fetchone()
effects=json.loads(actor['evidence'])
assert {e['tech_id'] for e in effects}=={202,203,221,213,249}
assert all(u[k]==female[k] for k in ('speed','resource_capacity','collision_size_x','collision_size_y'))
felling=json.loads(scratch_path('economy-review/wood-felling-source.json').read_text())
source=json.loads(c.execute("select value from metadata where key='source'").fetchone()[0])
assert felling['source']['sha256']==source['sha256']
attack=felling['units']['123']['attack'];graphic=felling['graphics'][str(attack['attack_graphic'])]
assert felling['trees']['349']['armor'] is None
damage=sum(a['amount'] for a in attack['attacks'])
assert damage==15
animation=graphic['frame_count']*graphic['frame_duration']
for level in range(4):
 for carry_level in range(3):
  ids=set([202,203,221][:level]+[213,249][:carry_level]);applied=[e for e in effects if e['tech_id'] in ids]
  values=dict(work_rate=u['bird']['work_rate'],movement_speed=u['speed'],carry_capacity=u['resource_capacity'])
  capacity=u['resource_capacity'];steps=[]
  for e in applied:
   assert e['command']['type']==5
   values[e['field']]*=e['command']['d']
   if e['field']=='carry_capacity':
    before=capacity;capacity=int(capacity*e['command']['d']+.5);steps.append(dict(tech_id=e['tech_id'],before=before,after=capacity,factor=e['command']['d']))
  fixture=dict(name=f'generic-wood-w{level}-c{carry_level}',
   upgrade_profile=dict(wood_level=level,carry_level=carry_level,tech_ids=sorted(ids)),
   source=dict(game_source=source,worker_ids=[123,218],camp_id=562,tree_id=349,effects=applied),
   worker=dict(work_rate=values['work_rate'],speed=values['movement_speed'],carry_capacity=capacity,
    unrounded_carry=values['carry_capacity'],carry_steps=steps,radius=u['collision_size_x'],
    damage_per_swing=damage,attack_period=attack['reload_time'],attack_animation_seconds=animation,
    first_hit_delay=animation/2,raw_frame_delay=attack['frame_delay']),
   tree=dict(name=tree['name'],hit_points=tree['hit_points'],half_width=tree['collision_size_x'],half_height=tree['collision_size_y'],
    wood=next(s['amount'] for s in tree['resource_storages'] if s['type']==1)),
   forest=dict(x=10,y=10,width=8,depth=6),
   camp=dict(center=[14,18],half_width=camp['collision_size_x'],half_height=camp['collision_size_y'],gap=1),
   assumptions=[
    'Generic Byzantine lumberjack values; only selected standard economic upgrades applied. Sappers is absent.',
    'Live tree: source 20 HP and 100 wood. Felling HP and remaining wood are separate. Felled tree keeps its resource footprint until depleted.',
    'No armor entries on tree; summed worker attack classes give 15 damage per swing, two swings to fell.',
    'First swing assumed at half of the current DAT 2-second animation; subsequent swings use coded reload 2 seconds. Raw frame_delay=0 does not resolve worker-task impact timing.',
    'Historical measured 2.25-second total felling is a separate sensitivity case, not silently imposed on the current DAT.',
    'Rigid circular workers and conservative rectangular resource obstacles reuse the gold experiment geometry/pathfinder.',
    'Instant deposits at contact. Partial loads continue to the next tree; all resources exhausted causes final partial deposit.',
    'Workers return to their tree while it is available, choose another accessible tree on depletion or blocked destination, and retry blocked paths after 0.5 game-seconds.',
    'No camp rebuilding. Depletion exposes inner trees and removes empty-tree obstacles; stumps do not obstruct.',
    'One fixed camp, eight-tile-wide six-deep forest, workers initially spread on the front edge at 0.6-tile center spacing.',
    'Observed rates are scenario/model estimates; the same-layout current DE trajectories have not been captured.'])
  (OUT/f'fixture-w{level}-c{carry_level}.json').write_text(json.dumps(fixture,indent=2)+'\n')
(OUT/'felling-source.json').write_text(json.dumps(felling,indent=2)+'\n')
print('Exported 12 wood profiles and felling source to',OUT)
