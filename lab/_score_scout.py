import sys,types,json,importlib.util
for m in ('flask','flask_cors','requests'): sys.modules.setdefault(m,types.ModuleType(m))
sys.path[:0]=['C:/dev/aoe2/aoc-mgz-67x','C:/dev/aoe2/aoe2record/lab']
spec=importlib.util.spec_from_file_location('uc','C:/dev/aoe2/aoe2record/visualizer/uc_exp_scout-class.py')
uc=importlib.util.module_from_spec(spec); spec.loader.exec_module(uc)
import mgz.model, eval_against_truth as E
def score(replay,labelsf,endmin):
  labels=json.load(open(labelsf)); CUT=(endmin-5)*60000
  mt=mgz.model.parse_match(open(replay,'rb')); tm,_=uc.build_type_map(mt)
  def known(n): return n and n.lower()!='flare' and not n.startswith('id') and E.coarse(E.canon_truth(n)) in ('villager','military')
  ok=tot=mok=mtot=0
  for k,u in labels.items():
    if (u.get('created_ms') or 0)>=CUT or not known(u.get('type')) or int(k) not in tm: continue
    t=E.canon_truth(u['type']); p=E.canon_pred(tm[int(k)]); tot+=1; ok+= (p==t)
    if E.coarse(t)=='military': mtot+=1; mok+=(p==t)
  return f'overall {100*ok/max(tot,1):.1f}% ({ok}/{tot}) military {100*mok/max(mtot,1):.1f}% ({mok}/{mtot})'
print('GAME2   ', score('C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/AgeIIDE_Replay_482723861.aoe2record','C:/dev/aoe2/aoe2record/lab/labels_g2.json',44.5))
print('ORIGINAL', score('C:/dev/_tmp_replay/fresh_newpatch.aoe2record','C:/dev/aoe2/aoe2record/lab/labels.json',42.6))
