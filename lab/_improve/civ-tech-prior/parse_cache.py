"""Parse g0 + train replays once, pickle the mgz match objects for fast iteration."""
import sys, types, pickle, time
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x"]
import mgz.model

GAMES = {
    "g0": "C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
    "train": r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
}
OUT = r"C:\dev\aoe2\aoe2record\lab\_improve\civ-tech-prior"

for name, path in GAMES.items():
    t0 = time.time()
    mt = mgz.model.parse_match(open(path, "rb"))
    print(f"{name}: parsed in {time.time()-t0:.1f}s")
    try:
        with open(f"{OUT}\\{name}.pkl", "wb") as f:
            pickle.dump(mt, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"{name}: pickled OK")
    except Exception as e:
        print(f"{name}: PICKLE FAILED: {e}")
