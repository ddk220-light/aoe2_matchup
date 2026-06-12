"""probe_quota.py [g0|train] -- examine over-quota types BEFORE arbitration:
per-candidate keep_score components, current fit vs best alternative fit."""
import sys, types, json, bisect
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = r"C:\dev\aoe2\aoe2record\lab\_improve\ensemble-arbiter"
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab", WORK]
from collections import Counter, defaultdict
import unit_classifier as uc
import eval_against_truth as E
from iterate import GAMES, get_match, known

key = sys.argv[1] if len(sys.argv) > 1 else "train"
replay, labels_path, end_min = GAMES[key]
labels = json.load(open(labels_path))
mt = get_match(key)

# run the pipeline WITHOUT the arbiters to capture pre-arb state
ctx = uc.Ctx() if hasattr(uc, "Ctx") else None
# easier: monkeypatch the arbiters out, then run
real_q, real_m = uc.arbiter_quota, uc.arbiter_monk_quota
uc.arbiter_quota = lambda ctx, **k: None
uc.arbiter_monk_quota = lambda ctx: None
ctx = uc._run(mt)
uc.arbiter_quota, uc.arbiter_monk_quota = real_q, real_m

CUT = (end_min - 5) * 60000
truth_units = {int(k): u for k, u in labels.items()
               if (u.get("created_ms") or 0) < CUT and known(u.get("type"))}

TOL = 4.0
for player in set(g.player for g in ctx.guesses.values() if g.player):
    fifo = sorted(ctx.prod_mil.get(player, []))
    if not fifo:
        continue
    prod = Counter(u for _, u in fifo)
    units = [c for c, g in ctx.guesses.items()
             if g.player == player and g.cls == "military"
             and c not in ctx.building_ids and c not in ctx.gaia_all
             and c not in ctx.start_ids and g.type not in uc.GENERIC_TYPES
             and g.type != "villager"]
    assigned = Counter(ctx.guesses[c].type for c in units)
    over = {t: assigned[t] - prod.get(t, 0) for t in assigned
            if assigned[t] > prod.get(t, 0)}
    if not over:
        continue
    slots_by_type = defaultdict(list)
    for t_, u in fifo:
        slots_by_type[u].append(t_)

    def fit(c, ty):
        fs = ctx.guesses[c].behavior.get("first_seen")
        st = slots_by_type.get(ty)
        if fs is None or not st:
            return None
        k = bisect.bisect_right(st, fs + TOL) - 1
        if k < 0:
            return None
        return max(fs - st[k], 0.0)

    print(f"== {player} over-quota: {over}  (prod {dict(prod)})")
    for T in over:
        cands = [c for c in units if ctx.guesses[c].type == T]
        print(f"-- type {T}: assigned={len(cands)} prod={prod.get(T,0)}")
        for c in sorted(cands):
            g = ctx.guesses[c]
            tlab = truth_units.get(c, {}).get("type", "?")
            fcur = fit(c, T)
            alts = []
            for U, cnt in prod.items():
                if U == T or cnt - assigned[U] <= 0:
                    continue
                f = fit(c, U)
                if f is not None:
                    alts.append((f, U))
            alts.sort()
            print(f"   id={c:6} truth={tlab:<18} src={g.type_src:<12} fs={g.behavior.get('first_seen')} "
                  f"fcur={fcur} hist={[t for _,t in g.type_hist]} alts={alts[:3]}")
