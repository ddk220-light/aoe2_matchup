import json
P=r"C:/Users/ddk22/AppData/Local/Programs/Python/Python312/Lib/site-packages/aocref/data/datasets/100.json"
d=json.load(open(P,encoding='utf-8'))
print("TOP KEYS:", list(d.keys()))
obj=d.get('objects') or d.get('units')
print("type of objects:", type(obj))
if isinstance(obj,dict):
    items=list(obj.items())[:3]; print("sample:",items)
elif isinstance(obj,list):
    print("sample:",obj[:3])
