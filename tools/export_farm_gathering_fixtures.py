#!/usr/bin/env python3
"""Export generic farm profiles from the reviewed user DAT extract, without civ bonuses."""
import json
import sqlite3
import sys
from pathlib import Path
from army_economics_paths import scratch_path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT / 'aoe2x/js_simulation/calibration/economy/farms-2026-11-09'
DB = scratch_path('economy-review/labor-inputs/labor-inputs.sqlite')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    def unit(uid):
        return json.loads(c.execute("select raw_definition from raw_unit_definitions where civ_name='Byzantines' and unit_id=?", (uid,)).fetchone()[0])
    def resource(rid):
        return dict(c.execute("select * from resource_parameters where civ_name='Byzantines' and resource_id=?", (rid,)).fetchone())
    worker, female, farm, mill, builder = [unit(i) for i in (259, 214, 50, 68, 118)]
    for k in ('speed', 'resource_capacity', 'collision_size_x', 'collision_size_y'):
        assert worker[k] == female[k]
    assert worker['bird']['work_rate'] == female['bird']['work_rate']
    evidence = json.loads(c.execute("select evidence from actor_parameters where civ_name='Byzantines' and unit_id=259").fetchone()[0])
    assert {e['tech_id'] for e in evidence} == {213, 13, 249}
    multiplier = resource(190)
    assert multiplier['final_parameter_value'] == 1
    capacity = resource(36)
    capacity_evidence = json.loads(capacity['evidence'])
    for e in evidence + capacity_evidence:
        raw = json.loads(c.execute('select definition from raw_effects where effect_id=?', (e['effect_id'],)).fetchone()[0])
        commands = raw.get('commands', raw.get('effect_commands'))
        assert commands[e['command_index']] == e['command']
    source = json.loads(c.execute("select value from metadata where key='source'").fetchone()[0])
    # Tile-aligned pinwheel: eight surrounding farms, two next to the east/west farms.
    # All farm rectangles are passable to villagers; only the mill obstructs walking.
    origins = [(-3,-3),(0,-3),(3,-3),(2,0),(2,3),(-1,3),(-4,3),(-3,0),(-6,0),(5,0)]
    for name, ids in [('none', []), ('wheelbarrow', [213]), ('wheelbarrow-plow', [14,213,13]), ('full', [14,213,13,249,12])]:
        selected = [e for e in evidence if e['tech_id'] in ids]
        values = dict(work_rate=worker['bird']['work_rate'], movement_speed=worker['speed'], carry_capacity=worker['resource_capacity'])
        steps = []
        for e in selected:
            field, cmd = e['field'], e['command']
            before = values[field]
            assert cmd['type'] in (4, 5)
            after = before + cmd['d'] if cmd['type'] == 4 else before * cmd['d']
            values[field] = int(after + .5) if field == 'carry_capacity' else after
            steps.append(dict(**e, runtime_before=before, runtime_after=values[field]))
        food = capacity['base_value']
        for e in capacity_evidence:
            if e['tech_id'] in ids:
                assert e['command']['type'] == 1 and e['command']['b'] == 1
                food += e['command']['d']
        fixture = dict(name='generic-farm-' + name, profile=name, technology_ids=ids,
            source=dict(game_source=source, worker_ids=[214,259], farm_id=50, mill_id=68,
                        worker_effects=steps, farm_capacity_effects=[e for e in capacity_evidence if e['tech_id'] in ids]),
            worker=dict(work_rate=values['work_rate'], speed=values['movement_speed'], carry_capacity=values['carry_capacity'], radius=worker['collision_size_x'], task_output_multiplier=1),
            farm=dict(food=food, generation_rate=farm['bird']['work_rate'], pool_capacity=farm['resource_capacity'],
                      initial_pool=0, half_width=farm['collision_size_x'], half_height=farm['collision_size_y'],
                      wood_cost=next(r['amount'] for r in farm['creatable']['resource_costs'] if r['type']==1),
                      build_seconds=farm['creatable']['train_locations'][0]['train_time']/builder['bird']['work_rate']),
            mill=dict(x0=0,y0=0,x1=2*mill['collision_size_x'],y1=2*mill['collision_size_y'],wood_cost=next(r['amount'] for r in mill['creatable']['resource_costs'] if r['type']==1)),
            farms=[dict(id=i,x0=x,y0=y,x1=x+3,y1=y+3,position='outer' if i>=8 else 'inner') for i,(x,y) in enumerate(origins)],
            behavior=dict(work_spot_offsets=[.5,1.5,2.5], spots_per_load=4, deposit_seconds=0, blocked_retry_seconds=.5),
            assumptions=[
                'Standard generic profile from Byzantine raw units; only explicit economic techs are replayed. Treadmill Crane is excluded.',
                'Integer carry rounded after each upgrade: base 10, Wheelbarrow 13, Heavy Plow 14, Hand Cart 21. Engine rounding is historical evidence, not a current executable trace.',
                'Farm replenishment and buffer are separate from worker harvesting. Initial available pool is zero; listed farm food includes all food in this model.',
                'Centered 2x2 work area reflects DE update 50292. Nine grid points and uniform choice excluding the previous point are a community-informed approximation.',
                'Four equal portions per load approximate observed quarter-load moves. Variable portion sizes and occasional fifth stops are unresolved, tested separately.',
                'No fixed stand timer: harvest rate and pool availability determine time at each spot. Instant deposits at body contact; no invented deposit animation delay.',
                'Rigid circular collisions and shortest visibility routes approximate engine pathing. Farms are passable; mill is solid. Dynamic priority rotates every second.',
                'Starts: finished farms, empty food pools, empty-handed workers at farm centers; walk to first chosen working spot. Initial construction excluded.',
                'Reseed diagnostic deposits any final partial load, returns to the previous working spot, rebuilds for 15 seconds, and pays 60 wood from an external wood budget.',
                'Not current-DE trajectory validation; do not use as a calibrated civilization-bonus predictor yet.'])
        (OUT/f'fixture-{name}.json').write_text(json.dumps(fixture,indent=2)+'\n')
    (OUT/'raw-source.json').write_text(json.dumps(dict(source=source,units={str(u['id']):u for u in (worker,female,farm,mill,builder)},resource_36=capacity,resource_190=multiplier),indent=2)+'\n')
    print('Exported four farm profiles to', OUT)

if __name__ == '__main__':
    main()
