"""Parse both dev replays once and pickle the match objects for fast iteration."""
import sys, types, pickle, time
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x"]
import mgz.model

GAMES = {
    "g0": "C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
    "train": r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
}
OUT = r"C:\dev\aoe2\aoe2record\lab\_improve\queue-ledger\match_cache_{k}.pkl"

for k, path in GAMES.items():
    t0 = time.time()
    mt = mgz.model.parse_match(open(path, "rb"))
    print(f"{k}: parsed in {time.time()-t0:.0f}s; actions={len(mt.actions)}")
    mt.hash = None  # _hashlib.HASH is unpicklable; classifier never uses it
    t0 = time.time()
    with open(OUT.format(k=k), "wb") as f:
        pickle.dump(mt, f, protocol=4)
    print(f"{k}: pickled in {time.time()-t0:.0f}s")
print("done")
