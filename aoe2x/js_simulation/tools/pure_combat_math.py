"""Pure combat math for champion_vs_paladin 6v3 run 1 -- no movement, no
targeting logic, no collision.

Stage A: take the tape's OWN swing start times and targets, apply only our
         damage + windup rules. If the HP timeline matches, damage and windup
         are right and the fault is upstream of them.
Stage B: keep the tape's targets but GENERATE swing times ourselves from each
         unit's first swing, repeating at the dat cadence. If A matches and B
         does not, the fault is in the cadence/reload loop.
"""
import collections
import json

TRACE = "cvp_trace/6v3.tape_trace.jsonl"
CHAMPION, PALADIN = 567, 569
ST_SWING = 7

# Sourced values, exactly as the fixtures carry them.
STATS = {
    CHAMPION: {"hp": 70,  "windup": 0.7500000391155481, "reload": 2.0, "name": "Champion"},
    PALADIN:  {"hp": 180, "windup": 0.6716666556894779, "reload": 1.9, "name": "Paladin"},
}
DAMAGE = {(CHAMPION, PALADIN): 13, (PALADIN, CHAMPION): 14}


def load():
    by = collections.defaultdict(list)
    for line in open(TRACE):
        row = json.loads(line)
        if row.get("master") not in STATS:
            continue
        by[row["id"]].append(row)
    for series in by.values():
        series.sort(key=lambda r: r["t_ms"])
    return by


def tape_facts(by):
    units, swings, deaths = {}, [], {}
    for uid, series in by.items():
        units[uid] = {
            "master": series[0]["master"],
            "owner": series[0]["owner"],
            "hp0": STATS[series[0]["master"]]["hp"],
        }
        for i in range(1, len(series)):
            if (series[i].get("action_state") == ST_SWING
                    and series[i - 1].get("action_state") != ST_SWING):
                swings.append({
                    "t": series[i]["t_ms"] / 1000,
                    "actor": uid,
                    "target": series[i].get("target_id"),
                })
        dead = next((r for r in series if (r.get("hp") or 0) <= 0), None)
        if dead:
            deaths[uid] = dead["t_ms"] / 1000
    swings.sort(key=lambda s: s["t"])
    return units, swings, deaths


def resolve(units, swings):
    """Apply damage from a list of swings. Pure arithmetic."""
    hp = {uid: u["hp0"] for uid, u in units.items()}
    died = {}
    hits = []
    for s in swings:
        actor, target = s["actor"], s["target"]
        if target not in units:
            continue
        landing = s["t"] + STATS[units[actor]["master"]]["windup"]
        # actor must still be alive when the blow lands? The tapes show a killer
        # completing its swing, so a swing already started still lands.
        if hp[target] <= 0:
            continue
        amount = DAMAGE[(units[actor]["master"], units[target]["master"])]
        hits.append((landing, actor, target, min(amount, hp[target])))
    hits.sort(key=lambda h: h[0])
    hp = {uid: u["hp0"] for uid, u in units.items()}
    landed = 0
    for landing, actor, target, _ in hits:
        if hp[target] <= 0 or hp.get(actor, 1) <= 0:
            continue
        amount = DAMAGE[(units[actor]["master"], units[target]["master"])]
        hp[target] = max(0, hp[target] - amount)
        landed += 1
        if hp[target] == 0 and target not in died:
            died[target] = landing
    return hp, died, landed


def main():
    by = load()
    units, swings, tape_deaths = tape_facts(by)
    order = sorted(units, key=lambda u: (units[u]["owner"], u))

    print("6v3 champion_vs_paladin, run 1 -- pure damage math, no movement\n")
    print(f"tape swings recorded: {len(swings)}")

    # ---- Stage A: tape swing times, tape targets --------------------------
    hp, died, landed = resolve(units, swings)
    print("\n== STAGE A: tape's own swing times + targets, our damage/windup")
    print(f"   hits landed: {landed}")
    print(f"   {'unit':>6} {'side':9} {'tape death':>11} {'model death':>12} {'tape hp':>8} {'model hp':>9}")
    for uid in order:
        series = by[uid]
        tape_hp = max(0, series[-1].get("hp") or 0)
        td = tape_deaths.get(uid)
        md = died.get(uid)
        print(f"   {uid:>6} {STATS[units[uid]['master']]['name']:9} "
              f"{(f'{td:.2f}' if td else '-'):>11} {(f'{md:.2f}' if md else '-'):>12} "
              f"{tape_hp:8.0f} {hp[uid]:9.0f}")

    # ---- Stage B: our cadence, tape targets -------------------------------
    first_swing, target_at = {}, {}
    for s in swings:
        if s["actor"] not in first_swing:
            first_swing[s["actor"]] = s["t"]
        target_at.setdefault(s["actor"], []).append((s["t"], s["target"]))
    horizon = max(s["t"] for s in swings) + 5
    generated = []
    for uid, t0 in first_swing.items():
        reload_s = STATS[units[uid]["master"]]["reload"]
        t = t0
        while t <= horizon:
            # target: whatever the tape had this unit on at the nearest swing
            nearest = min(target_at[uid], key=lambda pair: abs(pair[0] - t))
            generated.append({"t": t, "actor": uid, "target": nearest[1]})
            t += reload_s
    generated.sort(key=lambda s: s["t"])
    hpB, diedB, landedB = resolve(units, generated)
    print("\n== STAGE B: our cadence from each unit's first swing + tape targets")
    print(f"   swings generated: {len(generated)}  hits landed: {landedB}")
    print(f"   {'unit':>6} {'side':9} {'tape death':>11} {'model death':>12} {'tape hp':>8} {'model hp':>9}")
    for uid in order:
        series = by[uid]
        tape_hp = max(0, series[-1].get("hp") or 0)
        td = tape_deaths.get(uid)
        md = diedB.get(uid)
        print(f"   {uid:>6} {STATS[units[uid]['master']]['name']:9} "
              f"{(f'{td:.2f}' if td else '-'):>11} {(f'{md:.2f}' if md else '-'):>12} "
              f"{tape_hp:8.0f} {hpB[uid]:9.0f}")


if __name__ == "__main__":
    main()
