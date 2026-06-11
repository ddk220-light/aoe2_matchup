"""Parse both replays, scrub unpicklable members (hash, CodecInfo), pickle, verify."""
import sys, types, pickle, time, codecs
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x"]
import mgz.model

GAMES = {
    "g0": "C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
    "train": r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
}
OUT = r"C:\dev\aoe2\aoe2record\lab\_improve\queue-ledger\match_cache_{k}.pkl"


def scrub(obj, depth=0, seen=None):
    """Find CodecInfo instances reachable via __dict__/list/dict and None them."""
    if seen is None:
        seen = set()
    oid = id(obj)
    if oid in seen or depth > 6:
        return
    seen.add(oid)
    d = getattr(obj, "__dict__", None)
    if d is not None:
        for k, v in list(d.items()):
            if isinstance(v, codecs.CodecInfo):
                print(f"  scrubbed CodecInfo at .{k} on {type(obj).__name__}")
                d[k] = None
            else:
                scrub(v, depth + 1, seen)
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(v, codecs.CodecInfo):
                print(f"  scrubbed CodecInfo at [{k!r}]")
                obj[k] = None
            else:
                scrub(v, depth + 1, seen)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            scrub(v, depth + 1, seen)


for k, path in GAMES.items():
    t0 = time.time()
    mt = mgz.model.parse_match(open(path, "rb"))
    print(f"{k}: parsed in {time.time()-t0:.0f}s")
    mt.hash = None
    scrub(mt)
    data = pickle.dumps(mt, protocol=4)
    mt2 = pickle.loads(data)   # verify round-trip in-process
    print(f"{k}: roundtrip ok, players={[p.name for p in mt2.players]}")
    with open(OUT.format(k=k), "wb") as f:
        f.write(data)
print("done")
