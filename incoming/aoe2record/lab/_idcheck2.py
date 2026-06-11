import sys, types, json, collections
for m in ('flask','flask_cors','requests'): sys.modules[m]=types.ModuleType(m)
sys.path.insert(0,'C:/dev/aoe2/aoc-mgz-67x')
from mgz.model import parse_match
with open('C:/dev/_tmp_replay/fresh_newpatch.aoe2record','rb') as f:
    mt=parse_match(f)
print("match attrs:", [a for a in dir(mt) if not a.startswith('_')])
inp0=mt.inputs[0]
print("input attrs:", [a for a in dir(inp0) if not a.startswith('_')])
print("input0:", inp0)
# find a queue/build action
seen=collections.Counter()
qb=set()
for inp in mt.inputs:
    typ=getattr(inp,'type',None)
    seen[str(typ)]+=1
    pl=getattr(inp,'payload',None)
    if typ and ('Queue' in str(typ) or 'Build' in str(typ)) and pl:
        if not qb:
            print("QUEUE/BUILD payload sample:", typ, pl)
        for key in ('object_ids','building_id','target_id'):
            v=pl.get(key) if isinstance(pl,dict) else None
            if isinstance(v,list): qb.update(v)
            elif v: qb.add(v)
print("mgz input types:", seen.most_common(15))
print("mgz building/obj ids sample:", sorted(x for x in qb if isinstance(x,int) and x>100)[:15])
