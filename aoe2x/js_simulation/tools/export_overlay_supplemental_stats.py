import json
from pathlib import Path
from aoe2x.js_simulation.tools.export_roster_mechanics import supplemental_reference,ROOT
from aoe2x.js_simulation.tools.export_unit_mechanics import _raw_unit
roster=json.loads((ROOT/'data/unique-unit-roster.json').read_text())['units']
out={}
for u in roster:
 if u['master'] not in (775,1263): continue
 r=supplemental_reference(u); _,raw=_raw_unit(ROOT/'data/inputs/empires2_x2_p1.dat',u['civ'],u['master'])
 a=json.loads(r['final_attacks_json']); ar=json.loads(r['final_armors_json'])
 r.update(unit_name=u['label'],unit_slug=u['slug'],base_attack=raw.type_50.displayed_attack,final_attack=max(a.get('3',0),a.get('4',0)),base_melee_armor=raw.type_50.displayed_melee_armour,final_melee_armor=ar.get('4',0),base_pierce_armor=raw.creatable.displayed_pierce_armour,final_pierce_armor=ar.get('3',0),base_range=raw.type_50.max_range,ignores_pierce_armor=False,ignores_melee_armor=False,icon_id=raw.icon_id)
 out[u['slug']]=r
p=ROOT/'apps/video/overlay/supplemental-stats.json'; p.write_text(json.dumps(out,indent=2)+'\n'); print(p)
