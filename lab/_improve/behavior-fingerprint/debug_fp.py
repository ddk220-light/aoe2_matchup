"""Dump fingerprint decisions (pins, excl_vil, mil_fp) with truth names."""
import sys, types, json
from collections import Counter, defaultdict
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x", "C:/dev/aoe2/aoe2record/lab",
                r"C:\dev\aoe2\aoe2record\lab\_improve\behavior-fingerprint"]
import mgz.model
import unit_classifier as uc

GAMES = {
    "g0": ("C:/dev/_tmp_replay/fresh_newpatch.aoe2record", r"C:\dev\aoe2\aoe2record\lab\labels.json"),
    "train": (r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
              r"C:\dev\aoe2\aoe2record\lab\labels_g2.json"),
}

for game, (REPLAY, LABELS) in GAMES.items():
    labels = json.load(open(LABELS))
    tn = {int(k): u.get("type") for k, u in labels.items()}
    mt = mgz.model.parse_match(open(REPLAY, "rb"))
    ctx = uc._run(mt)
    print(f"\n========== {game} ==========")
    print("PINS:")
    for cid, t in sorted(ctx.pins.items()):
        b = ctx.guesses[cid].behavior
        print(f"  {cid} -> {t:10} truth={tn.get(cid)}  relic={b.get('relic_order',0)} pack={b.get('pack_treb',0)}")
    print(f"EXCL_VIL ({len(ctx.excl_vil)}): non-villager-truth members:")
    for cid in sorted(ctx.excl_vil):
        t = tn.get(cid) or "?"
        if not any(k in t.lower() for k in ("villager", "lumberjack", "miner", "hunter", "shepherd",
                                            "builder", "forager", "farmer", "fisher")):
            b = ctx.guesses[cid].behavior
            print(f"  {cid} truth={t} gt={b.get('gather_times')} solo={b.get('solo_gather',0)} "
                  f"garr={b.get('garrison_small',0)} atk={b.get('atk_enemy',0)}")
    print("MIL_FP units:")
    cnt = Counter()
    for cid, g in ctx.guesses.items():
        if g.behavior.get("mil_fp"):
            cnt[tn.get(cid) or "?"] += 1
    print("  ", dict(cnt))
    # fence check: which units were fenced from siege
    print("SIEGE-FENCED (garrison>0 or own_bld>=2&noatk) among military-classed:")
    for cid, g in ctx.guesses.items():
        b = g.behavior
        if cid in ctx.building_ids or cid in ctx.gaia_all:
            continue
        fenced = b.get("garrison") or (len(b.get("own_bld_times", ())) >= 2
                                       and not b.get("atk_enemy") and not b.get("attacks_building"))
        t = tn.get(cid) or "?"
        if fenced and any(k in t for k in ("Hussite", "Mangonel", "Scorpion", "Trebuchet")):
            print(f"  {cid} truth={t} garr={b.get('garrison',0)} own_bld={b.get('own_bld_times')} "
                  f"atk={b.get('atk_enemy',0)} ab={b.get('attacks_building',0)}")
