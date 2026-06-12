import sys,types,json,importlib.util
for m in ('flask','flask_cors','requests'): sys.modules.setdefault(m,types.ModuleType(m))
sys.path[:0]=['C:/dev/aoe2/aoc-mgz-67x','C:/dev/aoe2/aoe2record/lab']
import eval_against_truth as E
for n in ['Ibex','Jaguar','Vulture','Hawk','Wild Camel','Cactus','Animal Skeleton','Gold Miner','Lumberjack','Mule Cart','Jaguar Warrior','Monk']:
    print(f"{n!r:22} canon={E.canon_truth(n)!r:22} coarse={E.coarse(E.canon_truth(n))!r}")
