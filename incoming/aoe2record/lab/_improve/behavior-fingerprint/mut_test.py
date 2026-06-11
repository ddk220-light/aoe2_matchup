import sys, types, json, hashlib
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = r"C:\dev\aoe2\aoe2record\lab\_improve\behavior-fingerprint"
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab", WORK]
import mgz.model
import unit_classifier as uc

mt = mgz.model.parse_match(open("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", "rb"))
for i in range(3):
    tm, _ = uc.build_type_map(mt)
    s = json.dumps(sorted(tm.items()))
    print(f"call {i}: hash {hashlib.md5(s.encode()).hexdigest()} n={len(tm)} "
          f"7489={tm.get(7489)} 6436={tm.get(6436)} 5102={tm.get(5102)}")
