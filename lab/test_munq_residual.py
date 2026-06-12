import sys,types,json,importlib.util
for m in ('flask','flask_cors','requests'): sys.modules.setdefault(m,types.ModuleType(m))
sys.path[:0]=['C:/dev/aoe2/aoc-mgz-67x','C:/dev/aoe2/aoe2record/lab']
spec=importlib.util.spec_from_file_location('uc','C:/dev/aoe2/aoe2record/visualizer/uc_exp_munq-residual.py')
uc=importlib.util.module_from_spec(spec); spec.loader.exec_module(uc)
import mgz.model, eval_against_truth as E
labels=json.load(open('C:/dev/aoe2/aoe2record/lab/labels.json')); CUT=(42.6-5)*60000
mt=mgz.model.parse_match(open('C:/dev/_tmp_replay/fresh_newpatch.aoe2record','rb'))
tm,_=uc.build_type_map(mt)
for owner,name in ((1,'munq'),(2,'ddk220')):
  mil=[(int(k),E.canon_truth(u['type'])) for k,u in labels.items() if u.get('owner')==owner and E.coarse(E.canon_truth(u['type']))=='military' and (u['created_ms'] or 0)<CUT and int(k) in tm]
  allu=[(int(k),E.canon_truth(u['type'])) for k,u in labels.items() if u.get('owner')==owner and E.coarse(E.canon_truth(u['type']))in('villager','military') and (u['created_ms'] or 0)<CUT and int(k) in tm]
  print(name,'MIL',sum(E.canon_pred(tm[k])==t for k,t in mil),'/',len(mil),'  OVERALL',sum(E.canon_pred(tm[k])==t for k,t in allu),'/',len(allu))
