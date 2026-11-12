#!/usr/bin/env python3
"""Extract the small attack/animation subset needed to fell trees, from the DAT."""
import json
import hashlib
from dataclasses import asdict
from pathlib import Path
from army_economics_paths import scratch_path, dat_path
from genieutils.datfile import DatFile

raw=json.loads(scratch_path('production-review/current-raw-source.json').read_text())
source=raw['source'];path=dat_path(raw)
assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
data=DatFile.parse(path)
civ=data.civs[raw['civs']['Byzantines']['id']]
units={};graphic_ids=set()
for uid in (123,218):
    u=civ.units[uid]
    units[str(uid)]=dict(name=u.name,attack=asdict(u.type_50),tasks=[asdict(t) for t in u.bird.tasks])
    graphic_ids.add(u.type_50.attack_graphic)
    graphic_ids.update(t.proceeding_graphic_id for t in u.bird.tasks if t.proceeding_graphic_id>=0)
trees={str(uid):dict(name=data.civs[0].units[uid].name,
    armor=asdict(data.civs[0].units[uid].type_50) if data.civs[0].units[uid].type_50 else None)
    for uid in (349,415)}
graphics={str(i):asdict(data.graphics[i]) for i in graphic_ids if i>=0 and data.graphics[i]}
out=scratch_path('economy-review/wood-felling-source.json')
out.write_text(json.dumps(dict(source=source,units=units,trees=trees,graphics=graphics),indent=2)+'\n')
print(out)
for uid,u in units.items():print(uid,u['attack'])
for i,g in graphics.items():print('graphic',i,g)
