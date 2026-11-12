#!/usr/bin/env python3
"""Export the isolated gold experiment from the reviewed DAT inventory."""
import argparse
import json
import sqlite3
from pathlib import Path
from army_economics_paths import scratch_path


def build(database, mining_level=2, carry_level=2):
    assert mining_level in (0,1,2) and carry_level in (0,1,2)
    c = sqlite3.connect(f'file:{database.resolve()}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    def unit(uid):
        return json.loads(c.execute("select raw_definition from raw_unit_definitions where civ_name='Byzantines' and unit_id=?", (uid,)).fetchone()[0])
    u = unit(579)
    female = unit(581)
    gold = json.loads(c.execute('select raw_definition from gaia_resource_candidates where unit_id=66').fetchone()[0])
    camp = unit(584)
    p = c.execute("select * from actor_parameters where civ_name='Byzantines' and unit_id=579").fetchone()
    evidence = json.loads(p['evidence'])
    assert {e['tech_id'] for e in evidence} == {55,182,213,249}
    applied_ids=({55} if mining_level>=1 else set()) | ({182} if mining_level>=2 else set())
    applied_ids |= ({213} if carry_level>=1 else set()) | ({249} if carry_level>=2 else set())
    evidence=[e for e in evidence if e['tech_id'] in applied_ids]
    final=dict(work_rate=u['bird']['work_rate'],movement_speed=u['speed'],carry_capacity=u['resource_capacity'])
    for e in evidence:
        assert e['command']['type']==5
        final[e['field']] *= e['command']['d']
    carry = u['resource_capacity']
    carry_steps = []
    for e in evidence:
        if e['field'] == 'carry_capacity':
            factor = e['command']['d']
            before = carry
            carry = int(carry * factor + .5)
            carry_steps.append(dict(tech_id=e['tech_id'],before=before,factor=factor,after=carry))
    assert all(u[k] == female[k] for k in ('speed','resource_capacity','collision_size_x','collision_size_y'))
    assert u['bird']['work_rate'] == female['bird']['work_rate']
    metadata = {r['key']:json.loads(r['value']) for r in c.execute('select * from metadata')}
    task = next(t for t in u['bird']['tasks'] if t['action_type']==5 and t['unit_id']==66)
    task_multiplier=c.execute("select final_parameter_value from resource_parameters where civ_name='Byzantines' and resource_id=?",(task['resource_multiplier'],)).fetchone()[0]
    assert task_multiplier==1 and task['work_value_1']==1
    assert u['collision_size_x']==u['collision_size_y']
    # Rows are mining upgrades (none/first/both); columns are carry upgrades
    # (none/Wheelbarrow/Wheelbarrow+Hand Cart), from Gold & Relics.
    reference_seconds=[[27.8,27.4,27.0],[24.4,23.8,23.5],[21.4,21.0,20.5]][mining_level][carry_level]
    return dict(schema_version=1,name='generic-post-imperial-gold',
        upgrade_profile=dict(mining_level=mining_level,carry_level=carry_level,tech_ids=sorted(applied_ids)),
        source=dict(database=str(database),game_source=metadata['source'],
                    worker_ids=[579,581],gold_id=66,camp_id=584,effects=evidence),
        worker=dict(work_rate=final['work_rate'],speed=final['movement_speed'],
            radius=u['collision_size_x'],collision_size_y=u['collision_size_y'],
            minimum_collision_size_multiplier=u['dead_fish']['min_collision_size_multiplier'],
            carry_capacity=carry,unrounded_carry=final['carry_capacity'],carry_steps=carry_steps,
            task_multiplier=task_multiplier,raw_gold_task=task),
        gold=dict(half_width=gold['collision_size_x'],half_height=gold['collision_size_y'],
            amount=next(s['amount'] for s in gold['resource_storages'] if s['type']==3),
            centers=[[10.5,10.5],[11.5,10.5],[10.5,11.5],[11.5,11.5]]),
        camp=dict(half_width=camp['collision_size_x'],half_height=camp['collision_size_y'],center=[11,14]),
        starting_positions=[[10.3,12.2],[10.9,12.2],[11.5,12.2],[12.2,10.3],[12.2,10.9],
            [12.2,11.5],[10.3,9.8],[11.2,9.8],[9.8,10.3],[9.8,11.2]],
        reference=dict(name='Forgotten Empires: Gold & Relics',
            url='https://www.forgottenempires.net/strategy/age-of-empires-ii-strategy-center/gold-relics',
            seconds_per_10_gold=reference_seconds,gold_per_worker_minute=600/reference_seconds,
            conditions=f'One tile from camp, mining level {mining_level}, carry level {carry_level}, no bumping; patch unspecified'),
        assumptions=[
            'Generic mining inputs from Byzantine records; no civilization/team bonuses used.',
            'Carry rounded to nearest integer after each technology, consistent with historical community tests; current DE not captured.',
            'Workers are rigid circles of source radius; minimum collision multiplier is preserved but not activated.',
            'Gold and camp are rectangles; navigation uses conservative expanded-rectangle corners.',
            'Continuous source work rate; instantaneous deposit and task switch at contact.',
            'Workers return to their assigned gold object, selecting reachable contact points; retarget on depletion.',
            'Visibility routing around current worker positions; blocked paths retry after 0.5 game-seconds.',
            'Movement updates are sequential, priority rotates once per game-second; no physical pushing.',
            'No parameter is fitted to the external reference; this is an unvalidated economic model.'])


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',type=Path,default=scratch_path('economy-review/labor-inputs/labor-inputs.sqlite'))
    p.add_argument('--output',type=Path,default=Path('aoe2x/js_simulation/calibration/economy/gold-2026-11-09/fixture.json'))
    p.add_argument('--mining-level',type=int,choices=[0,1,2],default=2)
    p.add_argument('--carry-level',type=int,choices=[0,1,2],default=2)
    p.add_argument('--grid-output',type=Path,help='Export all nine mining/carry upgrade combinations to this directory')
    args=p.parse_args()
    if args.grid_output:
        args.grid_output.mkdir(parents=True,exist_ok=True)
        for m in range(3):
            for h in range(3):
                target=args.grid_output/f'fixture-m{m}-c{h}.json'
                target.write_text(json.dumps(build(args.database,m,h),indent=2)+'\n')
        print(f'Exported 9 source-derived profiles to {args.grid_output}')
    else:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(build(args.database,args.mining_level,args.carry_level),indent=2)+'\n')
        print(args.output)
