import json
P=r"C:/Users/ddk22/AppData/Local/Programs/Python/Python312/Lib/site-packages/aocref/data/datasets/100.json"
d=json.load(open(P,encoding='utf-8'))
obj=d['objects']
for i in [83,4,74,109,4033,4040,562,70,2556,75,73,79,103,87,101,49,68,584]:
    print(i, "->", obj.get(str(i)))
print("--- count objects:", len(obj))
# also technologies for research commands
print("tech sample:", list(d['technologies'].items())[:3] if isinstance(d['technologies'],dict) else d['technologies'][:3])
