import sys, types
for m in ('flask','flask_cors','requests'):
    sys.modules[m] = types.ModuleType(m)
sys.path.insert(0, 'C:/dev/aoe2/aoc-mgz-67x')
from mgz.model import parse_match
with open('C:/dev/_tmp_replay/fresh_newpatch.aoe2record','rb') as f:
    m = parse_match(f)
print("MAP:", m.map.name)
print("DURATION ms:", m.duration)
try: print("VERSION:", m.version, getattr(m,'game_version',None))
except: pass
for p in m.players:
    print("PLAYER:", p.number, repr(p.name), "civ=", p.civilization, "winner=", getattr(p,'winner',None))
print("dataset:", getattr(m,'dataset',None))
