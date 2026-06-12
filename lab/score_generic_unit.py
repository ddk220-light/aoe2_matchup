import sys,types,json,importlib.util
for m in ('flask','flask_cors','requests'): sys.modules.setdefault(m,types.ModuleType(m))
sys.path[:0]=['C:/dev/aoe2/aoc-mgz-67x','C:/dev/aoe2/aoe2record/lab']
MODFILE=sys.argv[1] if len(sys.argv)>1 else 'C:/dev/aoe2/aoe2record/visualizer/uc_exp_generic-unit.py'
spec=importlib.util.spec_from_file_location('uc',MODFILE)
uc=importlib.util.module_from_spec(spec); spec.loader.exec_module(uc)
import mgz.model, eval_against_truth as E
from collections import defaultdict
def known(n): return n and n.lower()!='flare' and not n.startswith('id') and E.coarse(E.canon_truth(n)) in ('villager','military')
def score(rep,lf,end):
  L=json.load(open(lf)); CUT=(end-5)*60000; mt=mgz.model.parse_match(open(rep,'rb')); tm,_=uc.build_type_map(mt)
  o=defaultdict(lambda:[0,0])
  for k,u in L.items():
    if (u.get('created_ms') or 0)>=CUT or not known(u['type']) or int(k) not in tm: continue
    t=E.canon_truth(u['type']);p=E.canon_pred(tm[int(k)])
    if E.coarse(t)=='military': o[u['owner']][1]+=1; o[u['owner']][0]+= (p==t)
  return {ow:f'{100*a/b:.1f}% ({a}/{b})' for ow,(a,b) in sorted(o.items())}
print('GAME2',score('C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/AgeIIDE_Replay_482723861.aoe2record','C:/dev/aoe2/aoe2record/lab/labels_g2.json',44.5))
print('ORIG ',score('C:/dev/_tmp_replay/fresh_newpatch.aoe2record','C:/dev/aoe2/aoe2record/lab/labels.json',42.6))
