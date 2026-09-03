"""Voluntary retarget rate vs fight size, over every decoded tape."""
import json,collections,glob,os,statistics,math
CH,PA=567,569
def fight(path):
    by=collections.defaultdict(list)
    for line in open(path):
        r=json.loads(line)
        if r.get('master') in (CH,PA): by[r['id']].append(r)
    for s in by.values(): s.sort(key=lambda r:r['t_ms'])
    death={}
    for uid,s in by.items():
        for r in s:
            if r.get('hp') is not None and r['hp']<=0: death[uid]=r['t_ms']; break
    END=max(death.values()) if death else max(max(r['t_ms'] for r in s) for s in by.values())
    vol=0; unitsec=0.0
    for uid,s in by.items():
        cur=None; t0=None; tend=min(death.get(uid,END),END)
        for r in s:
            if r['t_ms']>tend: break
            t=r.get('target_id')
            if t in (None,-1,0): t=None
            if t is not None:
                if t0 is None: t0=r['t_ms']
                if t!=cur:
                    if cur is not None:
                        d=death.get(cur)
                        if d is None or r['t_ms']<d-100: vol+=1
                    cur=t
        if t0 is not None: unitsec+=(tend-t0)/1000.0
    return len(by),vol,unitsec
rows=[]
for d in ['cvc','pvp','cvp92']:
    for p in sorted(glob.glob(f'{d}/*.tape_trace.jsonl')):
        n,v,us=fight(p)
        if us>0: rows.append((n,v,us,os.path.basename(p).split('.')[0],d))
buckets=[(2,4),(5,9),(10,15),(16,25),(26,40)]
print('Voluntary retarget rate vs FIGHT SIZE (all 122 recorded fights)\n')
print(f"{'units':>10} {'fights':>7} {'switches':>9} {'unit-sec':>10} {'per unit-sec':>13} {'1 per':>9}")
print('-'*64)
for lo,hi in buckets:
    sel=[r for r in rows if lo<=r[0]<=hi]
    if not sel: continue
    v=sum(r[1] for r in sel); us=sum(r[2] for r in sel)
    rate=v/us
    print(f'{lo:4d}-{hi:<5d} {len(sel):7d} {v:9d} {us:10.0f} {rate:13.4f} {(1/rate if rate else 0):8.1f}s')
print('-'*64)
v=sum(r[1] for r in rows); us=sum(r[2] for r in rows)
print(f"{'ALL':>10} {len(rows):7d} {v:9d} {us:10.0f} {v/us:13.4f} {us/v:8.1f}s")
# correlation between fight size and rate, per fight
xs=[r[0] for r in rows if r[2]>5]; ys=[r[1]/r[2] for r in rows if r[2]>5]
mx,my=statistics.mean(xs),statistics.mean(ys)
num=sum((a-mx)*(b-my) for a,b in zip(xs,ys))
den=math.sqrt(sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))
print(f'\nper-fight correlation(units, rate) = {num/den:+.2f}  over {len(xs)} fights')
