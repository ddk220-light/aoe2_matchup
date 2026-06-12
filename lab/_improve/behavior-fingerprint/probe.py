"""Probe action payload structure of both games: what behavioral signals exist?"""
import sys, types, json
from collections import Counter, defaultdict
for m in ("flask", "flask_cors", "requests"):
    sys.modules.setdefault(m, types.ModuleType(m))
sys.path[:0] = ["C:/dev/aoe2/aoc-mgz-67x"]
import mgz.model

GAMES = {
    "g0": "C:/dev/_tmp_replay/fresh_newpatch.aoe2record",
    "train": r"C:\Users\ddk22\Games\Age of Empires 2 DE\76561198053842894\savegame\AgeIIDE_Replay_482723861.aoe2record",
}

for name, path in GAMES.items():
    mt = mgz.model.parse_match(open(path, "rb"))
    print(f"\n================ {name} ================")
    print("players:", [(p.name, p.civilization) for p in mt.players])
    at_counter = Counter()
    payload_keys = defaultdict(Counter)
    samples = {}
    for a in mt.actions:
        at = str(a.type).replace("Action.", "")
        at_counter[at] += 1
        if a.payload:
            for k in a.payload:
                payload_keys[at][k] += 1
        if at not in samples and a.payload:
            samples[at] = (a.timestamp.total_seconds(), getattr(a.player, 'name', None),
                           {k: (str(v)[:90]) for k, v in a.payload.items()},
                           str(getattr(a, 'position', None)))
    print("\naction types:", dict(at_counter.most_common()))
    for at in sorted(payload_keys):
        print(f"\n  {at} keys: {dict(payload_keys[at])}")
        if at in samples:
            t, pl, pay, pos = samples[at]
            print(f"    sample t={t:.0f} player={pl} pos={pos} payload={pay}")
    # gaia names
    gaia_names = Counter((getattr(g, 'name', '') or '').lower() for g in (mt.gaia or []))
    relics = {n: c for n, c in gaia_names.items() if 'relic' in n}
    print("\n  gaia w/ 'relic':", relics)
    # stance / formation values
    for at in ("STANCE", "FORMATION"):
        vals = Counter()
        for a in mt.actions:
            if str(a.type).replace("Action.", "") == at and a.payload:
                vals[str({k: v for k, v in a.payload.items() if k not in ("object_ids",)})] += 1
        print(f"  {at} payload values: {dict(vals.most_common(8))}")
