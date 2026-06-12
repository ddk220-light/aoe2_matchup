"""Diag: (1) own-ORDER-target units (mule cart signal) with truth, both games;
(2) train P1/P2 military FIFO around the error clusters; (3) error units' behavior."""
from collections import Counter, defaultdict

u = reload_uc()

for game in ("g0", "train"):
    mt = MTS[game]
    labels = LBL[game]
    tn = {int(k): v.get("type") for k, v in labels.items()}
    ctx = u._run(mt)

    # (1) mobile units that are ORDER-targets of their OWN player's commands
    own_tgt = Counter()
    own_tgt_n = defaultdict(list)
    for a in mt.actions:
        if not a.player or u._at(a) != "ORDER":
            continue
        p = a.payload or {}
        tgt = p.get("target_id")
        if not isinstance(tgt, int) or tgt <= 0:
            continue
        ct = ctx.canon(tgt)
        if ct in ctx.building_ids or ct in ctx.gaia_all:
            continue
        if ctx.owner.get(ct) == a.player.name:
            ids = p.get("object_ids", [])
            if ct in [ctx.canon(o) for o in ids]:
                continue  # self-target
            own_tgt[ct] += 1
            own_tgt_n[ct].append(len(ids))
    print(f"=== {game}: own-ORDER-target mobiles (truth, count, selection sizes, gathers) ===")
    for ct, c in own_tgt.most_common(20):
        g = ctx.guesses.get(ct)
        b = g.behavior if g else {}
        print(f"  id={ct} truth={tn.get(ct)} hits={c} n={own_tgt_n[ct][:8]} "
              f"gt={len(b.get('gather_times', ()))} gathers={b.get('gathers',0)} build={b.get('builds',0)}")

print()
# (2) train FIFOs
ctx = u._run(MTS["train"])
tn = {int(k): v.get("type") for k, v in LBL["train"].items()}
for player in sorted(ctx.prod_mil):
    fifo = sorted(ctx.prod_mil[player])
    print(f"--- train FIFO {player} ({len(fifo)} slots) ---")
    line = defaultdict(list)
    for t, ut in fifo:
        line[u._line_of(ut)].append((round(t), ut))
    for L in sorted(line):
        print(f"  {L}: {line[L]}")

# (3) error unit info
errs = [6679, 5785, 6700, 5680, 5682, 6444, 6445, 6446, 6492, 5679, 5751, 6661, 4617,
        5117, 5340, 5318, 5801, 4597, 4598, 5832, 3907, 4204, 4850]
print("\n--- train error units ---")
for c in errs:
    g = ctx.guesses.get(c)
    if not g:
        print(f"  {c}: no guess")
        continue
    b = dict(g.behavior)
    b.pop("first_seen", None)
    print(f"  {c} truth={tn.get(c)} pred={g.type} cls={g.cls}/{g.cls_conf} sq={g.squad_id} "
          f"fs={g.behavior.get('first_seen')} sig={g.signals} b={ {k: (sorted(v) if isinstance(v, set) else v) for k, v in b.items()} }")
