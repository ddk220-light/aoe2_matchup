"""calibrate.py [g0|train] -- compare FIFO-model completion times vs gRPC truth spawn
times per player+type, to calibrate train times (game constants) offline."""
import sys, types, json
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab",
                r"C:\dev\aoe2\aoe2record\lab\_improve\civ-tech-prior"]
from collections import Counter, defaultdict
import mgz.model
import unit_classifier as uc
import eval_against_truth as E

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", r"C:\dev\aoe2\aoe2record\lab\labels.json", 42.6),
    "train": (r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
              r"C:\dev\aoe2\aoe2record\lab\labels_g2.json", 44.5),
}
game = sys.argv[1] if len(sys.argv) > 1 else "g0"
REPLAY, LABELS, END_MIN = GAMES[game]

labels = json.load(open(LABELS))
mt = mgz.model.parse_match(open(REPLAY, "rb"))
ctx = uc.build_context(mt)
uc.production_timeline(ctx)

# player name <-> owner number
print("players:", [(p.name, getattr(p, "number", None), getattr(p, "civilization", None)) for p in mt.players])
num2name = {getattr(p, "number", None): p.name for p in mt.players}

# truth spawn times per player+queue-token. Map truth name -> queue token by norm.
def truth_tok(name):
    return uc._norm(name)

spawns = defaultdict(list)   # (player_name, token) -> [spawn_sec]
for k, u in labels.items():
    nm = u.get("type") or ""
    o = u.get("owner")
    cms = u.get("created_ms")
    if cms is None or o not in num2name:
        continue
    spawns[(num2name[o], truth_tok(nm))].append(cms / 1000.0)
for v in spawns.values():
    v.sort()

# model: per-player completion stream by type
model = defaultdict(list)    # (player, token) -> [completion_sec]
for pl, comp in ctx.prod_full.items():
    for t, u in comp:
        model[(pl, u)].append(t)

# Also raw queue times by type
qtimes = defaultdict(list)
for b, q in ctx.queues.items():
    pl = ctx.owner.get(b)
    for t, u in sorted(q):
        qtimes[(pl, u)].append(t)

# truth names use display names ('Elite Skirmisher'); queue uses normed names. Group truth
# by exact normed name so upgrades line up (eliteskirmisher vs skirmisher).
for (pl, tok), mts in sorted(model.items()):
    sts = spawns.get((pl, tok), [])
    print(f"\n--- {pl} :: {tok}  model={len(mts)} truth={len(sts)} queued={len(qtimes.get((pl,tok),[]))}")
    n = min(len(mts), len(sts))
    # align k-th model completion to k-th truth spawn
    diffs = [mts[i] - sts[i] for i in range(n)]
    if diffs:
        import statistics
        print(f"   k-th aligned model-truth diff: med={statistics.median(diffs):+.1f}s "
              f"first5={[f'{d:+.0f}' for d in diffs[:5]]} last5={[f'{d:+.0f}' for d in diffs[-5:]]}")
    qs = qtimes.get((pl, tok), [])
    if sts and qs:
        # train-time estimate from isolated first productions: spawn - queue for k-th pairs
        m2 = min(len(qs), len(sts))
        est = [sts[i] - qs[i] for i in range(min(m2, 8))]
        print(f"   spawn-queue (first 8 kth-pairs): {[f'{d:.0f}' for d in est]}")

# truth types present without model production (token mismatch check)
print("\n=== truth tokens with NO matching model stream (per player) ===")
for (pl, tok), sts in sorted(spawns.items()):
    if (pl, tok) not in model and len(sts) >= 1:
        nm_sample = tok
        print(f"  {pl} :: {tok} x{len(sts)} first_spawn={sts[0]/60:.1f}m")
