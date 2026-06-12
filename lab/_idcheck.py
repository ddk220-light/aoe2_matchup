import sys, types, json
for m in ('flask','flask_cors','requests'): sys.modules[m]=types.ModuleType(m)
sys.path.insert(0,'C:/dev/aoe2/aoc-mgz-67x')
from mgz.model import parse_match
from mgz.fast.enums import Action
with open('C:/dev/_tmp_replay/fresh_newpatch.aoe2record','rb') as f:
    mt=parse_match(f)
# collect object ids referenced by DE_QUEUE/MULTIQUEUE actions in mgz inputs
qbuildings=set(); qtrains=set()
acts=collections=0
import collections as C
seen=C.Counter()
for inp in mt.inputs[:20000]:
    a=getattr(inp,'action',None)
    if a is None: continue
    t=getattr(a,'type',None)
    seen[str(t)]+=1
    p=getattr(a,'payload',{}) or {}
    if t is not None and 'QUEUE' in str(t):
        for o in p.get('object_ids',[]): qbuildings.add(o)
        if 'unit_id' in p: qtrains.add(p.get('unit_id'))
        if 'type' in p: qtrains.add(p.get('type'))
print("mgz action types seen (top):", seen.most_common(12))
print("sample queue payload keys:")
for inp in mt.inputs:
    a=getattr(inp,'action',None)
    if a and 'QUEUE' in str(getattr(a,'type','')):
        print("  ", a.type, a.payload); break
print("mgz queue building ids sample:", sorted(qbuildings)[:15])
# gRPC capture building ids
gb=set()
for line in open('C:/dev/aoe2/aoe2record/lab/commands_log.jsonl',encoding='utf-8'):
    o=json.loads(line)
    for k in ('buildingIds','selectedBuildingId'):
        v=o.get(k)
        if isinstance(v,list): gb.update(v)
        elif v: gb.add(v)
print("gRPC capture building ids:", sorted(x for x in gb if x>100)[:15])
