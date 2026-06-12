import json, collections
c=collections.Counter()
make_links=[]
with open('C:/dev/aoe2/aoe2record/lab/commands_log.jsonl',encoding='utf-8') as f:
    for line in f:
        try: o=json.loads(line)
        except: continue
        c[o.get('cmd')]+=1
        if o.get('cmd')=='make':
            make_links.append(o)
print("COMMAND TYPES in capture:")
for k,v in c.most_common(): print(f"  {k}: {v}")
print("total lines:", sum(c.values()))
print("\nMAKE commands (production->unit link):", len(make_links))
for m in make_links[:8]: print(" ", m)
