"""Where does a champion's life go?

The lopsided ratios show our losing champions dealing 28-46% more damage per
second alive than the game's. Damage per second alive is just

    (fraction of life spent attacking) x (damage per second while attacking)

The second factor is a verified constant (13 dmg / 2.0 s reload = 6.5). So the
whole gap has to be in the first. This measures it directly, per champion, over
its own lifetime, and splits the non-attacking remainder into MOVING and IDLE.

Tape: Action.state 4=moving, 6=reload, 7=swing (attacking = 6 or 7).
Sim: engagedTargetId non-null = attacking; else moving if position changed.
"""
import collections
import json
import statistics
import sys

CH, PA = 567, 569
ST_MOVE, ST_RELOAD, ST_SWING = 4, 6, 7


def load(path):
    by = collections.defaultdict(list)
    with open(path) as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("master") in (CH, PA):
                by[r["id"]].append(r)
    for s in by.values():
        s.sort(key=lambda r: r["t_ms"])
    return by


def budget(path, tape, master=CH):
    by = load(path)
    out = []
    for uid, s in by.items():
        if s[0]["master"] != master:
            continue
        # life ends at death, else at the last frame
        life = []
        for i, r in enumerate(s):
            hp = r.get("hp")
            life.append(r)
            if hp is not None and hp <= 0:
                break
        if len(life) < 3:
            continue
        span = (life[-1]["t_ms"] - life[0]["t_ms"]) / 1000.0
        if span <= 0:
            continue
        att = mov = idle = 0
        for i in range(1, len(life)):
            dt = (life[i]["t_ms"] - life[i - 1]["t_ms"]) / 1000.0
            r = life[i]
            if tape:
                st = r.get("action_state")
                if st in (ST_RELOAD, ST_SWING):
                    att += dt
                elif st == ST_MOVE:
                    mov += dt
                else:
                    idle += dt
            else:
                if r.get("engaged") is not None:
                    att += dt
                else:
                    p = life[i - 1]
                    moved = abs(r["x"] - p["x"]) + abs(r["y"] - p["y"]) > 1e-9
                    if moved:
                        mov += dt
                    else:
                        idle += dt
        out.append((span, att, mov, idle))
    return out


def main():
    print("CHAMPION TIME BUDGET over its own lifetime "
          "(attacking = swinging or reloading)\n")
    hdr = (f"{'ratio':>6} {'src':>5} | {'life':>7} {'attacking':>10} {'moving':>9} "
           f"{'idle':>8} | {'dmg/sec alive':>14}")
    print(hdr)
    print("-" * len(hdr))
    for ratio in sys.argv[1:]:
        keep = {}
        for src, path, tape in [("tape", f"cvp92/{ratio}.tape_trace.jsonl", True),
                                ("sim", f"cvp92/{ratio}.sim_trace.jsonl", False)]:
            rows = budget(path, tape)
            if not rows:
                print(f"{ratio:>6} {src:>5} | (no data)")
                continue
            span = statistics.mean(r[0] for r in rows)
            tot = sum(r[0] for r in rows)
            att = sum(r[1] for r in rows) / tot * 100
            mov = sum(r[2] for r in rows) / tot * 100
            idl = sum(r[3] for r in rows) / tot * 100
            keep[src] = (att, mov, idl, span)
            print(f"{ratio:>6} {src:>5} | {span:6.2f}s {att:9.1f}% {mov:8.1f}% "
                  f"{idl:7.1f}% | {att / 100 * 6.5:13.2f}")
        if len(keep) == 2:
            t, s = keep["tape"], keep["sim"]
            print(f"{'':>6} {'DELTA':>5} | {'':7} {s[0] - t[0]:+8.1f}pt "
                  f"{s[1] - t[1]:+7.1f}pt {s[2] - t[2]:+6.1f}pt")
        print()


if __name__ == "__main__":
    main()
