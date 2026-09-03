import json,collections,glob,os,sys
from read_orders import orders
CH,PA=567,569
named_sw=named_tot=other_sw=other_tot=0
for path in sorted(glob.glob('cvp92/*.frames.bin')):
    tag=os.path.basename(path).replace('.frames.bin','')
    tr=f'cvp92/{tag}.tape_trace.jsonl'
    if not os.path.exists(tr): continue
    o,_=orders(path)
    if not o: continue
    by=collections.defaultdict(list)
    for line in open(tr):
        r=json.loads(line)
        if r.get('master') in (CH,PA): by[r['id']].append(r)
    for s in by.values(): s.sort(key=lambda r:r['t_ms'])
    # target at each time per unit
    switches=collections.defaultdict(list)   # uid -> [t_ms of any target change]
    for uid,s in by.items():
        cur=None
        for r in s:
            if r.get('hp') is not None and r['hp']<=0: break
            t=r.get('target_id')
            if t in (None,-1,0): t=None
            if t is not None and t!=cur:
                if cur is not None: switches[uid].append(r['t_ms'])
                cur=t
    alive_ids=set(by)
    for rec in o:
        named=set(rec['unitIds']) | ({rec['recipient']} if rec['recipient']>0 else set())
        named &= alive_ids
        others=alive_ids-named
        t0=rec['t']
        for uid in named:
            named_tot+=1
            if any(abs(x-t0)<=60 for x in switches.get(uid,[])): named_sw+=1
        for uid in others:
            other_tot+=1
            if any(abs(x-t0)<=60 for x in switches.get(uid,[])): other_sw+=1
print('At each AiOrder, did the units NAMED in it change target within 60 ms?\n')
print(f'  units named in the order   : {named_sw}/{named_tot}  ({named_sw/named_tot*100:.1f}%)')
print(f'  every other live unit      : {other_sw}/{other_tot}  ({other_sw/other_tot*100:.1f}%)')
print(f'\n  lift: {(named_sw/named_tot)/(other_sw/other_tot):.1f}x')
