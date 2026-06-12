"""diag2.py [g0|train] -- foundational checks for the id-spine:
1. id monotone vs truth created_ms (per player + global)?
2. LCS ceiling: truth-token seq (cands in id order) vs model slot seq (time order)
3. model timing error: truth created_ms vs matched slot time (via LCS backtrace)
4. how many truthed commanded units are NOT the player's own production (converted)
"""
import sys, types, json, os
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
WORK = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab"]
sys.path.insert(0, WORK)
from collections import Counter, defaultdict
import eval_against_truth as E
sys.path.insert(0, WORK)
import mgz.model
import unit_classifier as uc

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
           "C:/dev/aoe2/aoe2record/lab/labels.json", 42.6),
    "train": ("C:/Users/ddk22/Games/Age of Empires 2 DE/76561198053842894/savegame/AgeIIDE_Replay_482723861.aoe2record",
              "C:/dev/aoe2/aoe2record/lab/labels_g2.json", 44.5),
}
key = sys.argv[1] if len(sys.argv) > 1 else "g0"
replay, labels_path, end_min = GAMES[key]
labels = json.load(open(labels_path))
mt = mgz.model.parse_match(open(replay, "rb"))

ctx = uc.build_context(mt)
uc.behavioral_labels(ctx)
uc.production_timeline(ctx)

truth = {}      # id -> (token, created_s, owner)
for k, u in labels.items():
    t = E.canon_truth(u.get("type") or "")
    if E.coarse(t) in ("villager", "military"):
        truth[int(k)] = (t, (u.get("created_ms") or 0) / 1000.0, u.get("owner"))

# 1. id vs created_ms monotonicity (all truthed units, global)
ids = sorted(truth)
inv = sum(1 for a, b in zip(ids, ids[1:]) if truth[a][1] > truth[b][1] + 0.5)
print(f"GLOBAL truthed ids={len(ids)} created_ms inversions(>0.5s)={inv}")

player_names = [p.name for p in mt.players]
# owner number -> name guess: use ctx.owner of truthed commanded ids
own_map = {}
for cid in ids:
    if cid in ctx.owner and ctx.owner[cid] in player_names:
        own_map.setdefault(truth[cid][2], Counter())[ctx.owner[cid]] += 1
print("owner->player:", {k: v.most_common(1)[0][0] for k, v in own_map.items()})

for player in player_names:
    slots = sorted(ctx.prod_full.get(player, []))
    sl_tok = [E.canon_pred(u) for _, u in slots]
    sl_t = [t for t, _ in slots]
    cand = sorted(c for c, g in ctx.guesses.items()
                  if g.player == player and c not in ctx.building_ids
                  and c not in ctx.gaia_all and c not in ctx.start_ids
                  and g.behavior.get("first_seen") is not None)
    tc = [c for c in cand if c in truth]
    seq = [truth[c][0] for c in tc]
    # per-player created_ms monotonicity on truthed cands
    invp = sum(1 for a, b in zip(tc, tc[1:]) if truth[a][1] > truth[b][1] + 0.5)
    # spawn vs first_seen sanity: fs >= created?
    fs_before = sum(1 for c in tc if ctx.guesses[c].behavior["first_seen"] < truth[c][1] - 1.0)
    print(f"\n=== {key} {player} ===")
    print(f" truthed cands={len(tc)} id-vs-created inversions={invp}  fs<created cases={fs_before}")
    # 4. produced-here check: truth type present in player's production at the right count?
    prodc = Counter(sl_tok)
    seqc = Counter(seq)
    over = {t: c - prodc.get(t, 0) for t, c in seqc.items() if c > prodc.get(t, 0)}
    print(f" truth-token counts beyond modeled production: {over}")
    # 2. LCS truth seq (id order) vs slot tokens (time order)
    n, m = len(seq), len(sl_tok)
    if n and m:
        dp = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            si = seq[i - 1]
            dpi, dpm = dp[i], dp[i - 1]
            for j in range(1, m + 1):
                dpi[j] = dpm[j - 1] + 1 if sl_tok[j - 1] == si else max(dpm[j], dpi[j - 1])
        lcs = dp[n][m]
        print(f" LCS ceiling: {lcs}/{n} = {100*lcs/n:.1f}%")
        # 3. backtrace -> matched slot per cand -> timing error created vs slot_t
        i, j = n, m
        pairs = []
        while i > 0 and j > 0:
            if sl_tok[j - 1] == seq[i - 1] and dp[i][j] == dp[i - 1][j - 1] + 1:
                pairs.append((tc[i - 1], j - 1)); i -= 1; j -= 1
            elif dp[i - 1][j] >= dp[i][j - 1]:
                i -= 1
            else:
                j -= 1
        errs = sorted(sl_t[j] - truth[c][1] for c, j in pairs)
        def pct(p): return errs[int(p * (len(errs) - 1))]
        print(f" slot_t - created: p10={pct(.1):.0f} p50={pct(.5):.0f} p90={pct(.9):.0f}  |>20s|={sum(1 for e in errs if abs(e)>20)}/{len(errs)}")
