"""Auto-discovering trace: when an AssignField/AssignKey hits an UNKNOWN field,
use the lookahead value-width guesser to determine the value size, record the
(model_type, field, width) as a discovered drift field, and CONTINUE. Track how
far we get and whether we reach World.entities, and how many entities/players we
can recover. Stops only on a true structural break (invalid op that can't be
guessed past).
"""
import struct
import sys
from collections import Counter, defaultdict
import patch_decode as P
import schema_patches

SCHEMA = P.SCHEMA
schema_patches.apply(SCHEMA)
TYPE2NAME = P.TYPE2NAME
import trace_snapshot as TS  # reuse name helpers
tname = TS.tname
fname = TS.fname

# guess width helper (same logic as patch_decode.guess_value but returns width)
def guess_width(d, p):
    for w in (1, 2, 4, 8):
        if P._op_ok(d, p + w, depth=3):
            return w
    return None


def run(data, log_discoveries=True):
    r = P.Reader(data)
    root = {"__type__": 0}
    stack = [root]
    ops = 0
    discovered = defaultdict(Counter)   # (ty,field) -> Counter(width)
    discovered_examples = {}
    hard_stops = 0
    entities_first_op = None
    players_first_op = None
    master_first_op = None
    structural_break = None

    def topinfo():
        t = stack[-1]; return t, t["__type__"], SCHEMA.get(t["__type__"], {})

    while r.p < len(data):
        op_pos = r.p
        op = r.u8()
        if not (1 <= op <= 14):
            structural_break = ("invalid_op", op_pos, op, len(stack))
            break
        top, ty, fields = topinfo()
        try:
            if op == 1:
                if len(stack) > 1: stack.pop()
            elif op == 2:
                f = r.u8(); kind = fields.get(f)
                if kind is None:
                    w = guess_width(r.d, r.p)
                    if w is None:
                        structural_break = ("noguess_field", op_pos, (ty, f), len(stack)); break
                    discovered[(ty, f)][w] += 1
                    if (ty, f) not in discovered_examples:
                        discovered_examples[(ty,f)] = r.d[r.p:r.p+w].hex()
                    r.p += w
                else:
                    top[f] = P.read_value(r, kind)
            elif op == 3:
                f = r.u8(); stack.append(top.setdefault(f, {"__type__": -1}))
            elif op == 4:
                f = r.u8(); mt = r.u8(); c = {"__type__": mt}; top[f] = c; stack.append(c)
            elif op == 5:
                f = r.u8(); top.pop(f, None)
            elif op == 6:
                f = r.u8(); k = r.i32(); kind = fields.get(f)
                if kind is None:
                    w = guess_width(r.d, r.p)
                    if w is None:
                        structural_break = ("noguess_mapfield", op_pos, (ty,f), len(stack)); break
                    discovered[(ty, f)][w] += 1
                    if (ty,f) not in discovered_examples:
                        discovered_examples[(ty,f)] = r.d[r.p:r.p+w].hex()
                    r.p += w
                else:
                    top.setdefault(f, {})[k] = P.read_value(r, kind)
            elif op == 7:
                f = r.u8(); k = r.i32(); stack.append(top.setdefault(f, {}).setdefault(k, {"__type__": -1}))
            elif op == 8:
                f = r.u8(); mt = r.u8(); k = r.i32(); c = {"__type__": mt}
                top.setdefault(f, {})[k] = c; stack.append(c)
                if ty == 1 and f == 1 and entities_first_op is None: entities_first_op = ops
                if ty == 1 and f == 2 and players_first_op is None: players_first_op = ops
                if ty == 5 and f == 4 and master_first_op is None: master_first_op = ops
            elif op == 9:
                f = r.u8(); k = r.i32(); top.get(f, {}).pop(k, None)
            elif op == 10:
                f = r.u8(); k = r.i32(); kind = fields.get(f)
                if kind is None:
                    w = guess_width(r.d, r.p)
                    if w is None:
                        structural_break = ("noguess_insert", op_pos, (ty,f), len(stack)); break
                    discovered[(ty,f)][w] += 1; r.p += w
                else:
                    top.setdefault(f, {})[k] = P.read_value(r, kind)
            elif op == 11:
                f = r.u8(); mt = r.u8(); k = r.i32(); c = {"__type__": mt}
                top.setdefault(f, {})[k] = c; stack.append(c)
            elif op == 12:
                f = r.u8(); k = r.i32()
            elif op == 13:
                f = r.u8(); r.i32(); r.i32()
            elif op == 14:
                f = r.u8(); r.i32()
        except Exception as ex:
            structural_break = ("exception", op_pos, str(ex), len(stack)); break
        ops += 1

    return {
        "root": root, "ops": ops, "pos": r.p, "total": len(data),
        "discovered": discovered, "examples": discovered_examples,
        "entities_first_op": entities_first_op,
        "players_first_op": players_first_op,
        "master_first_op": master_first_op,
        "structural_break": structural_break,
    }


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "first_patch_seg2.bin"
    data = open(path, "rb").read()
    print(f"auto-tracing {path} ({len(data)} bytes)")
    res = run(data)
    print(f"\nops={res['ops']}  consumed={res['pos']}/{res['total']} "
          f"({100*res['pos']/res['total']:.2f}%)")
    sb = res["structural_break"]
    if sb:
        print(f"STRUCTURAL BREAK: kind={sb[0]} at byte {sb[1]} info={sb[2]} stackdepth={sb[3]}")
        ctx = data[max(0,sb[1]-32):sb[1]+32]
        print(f"  bytes: {ctx.hex()}")
    print(f"\norder: entities_first_op={res['entities_first_op']} "
          f"players_first_op={res['players_first_op']} master_first_op={res['master_first_op']}")

    print("\nDISCOVERED new fields (model_type/name . field -> width:count):")
    for (ty, f), wc in sorted(res["discovered"].items()):
        ex = res["examples"].get((ty,f), "")
        print(f"  {tname(ty)}(t{ty}).{f}: {dict(wc)}  ex={ex}")

    world = res["root"].get(0, {})
    if isinstance(world, dict):
        ents = world.get(1, {})
        if isinstance(ents, dict):
            real = {k:v for k,v in ents.items() if isinstance(v,dict)}
            print(f"\nWorld.entities recovered: {len(real)}")
            mt = Counter(v.get('__type__') for v in real.values())
            print(f"  by model type: {dict(mt)}")
            # entity stats
            byom = Counter((v.get(2), v.get(1)) for v in real.values() if v.get(1) is not None)
            print(f"  entities with master_id: {sum(byom.values())}")
            for (o,m),n in byom.most_common(15):
                print(f"    owner={o} master_id={m} count={n}")


if __name__ == "__main__":
    main()
