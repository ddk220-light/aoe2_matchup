"""decode_fight.py — RICH offline decode of a recorded CadeRemote Frames() stream
into a full ground-truth record of one battle, for calibrating the simulation.

`redecode_hp.py` collapses the same capture to two numbers per side per second
(count + total HP). That aggregate is all the sim has ever been fitted against.
This decoder keeps everything the stream actually carries:

  * per-unit state at the stream's native ~60 Hz (position, HP, state, facing),
  * EVERY HIT: the per-hit damage record the game emits as Event field 6 —
    {victimId, attackerId, damage, victimHpAfter}. The repo's cade_api.proto
    stops at field 5, so protobuf parses these as an empty oneof and every
    existing consumer silently drops them. Verified against the decoded entity
    store on a real tape: 222/222 events agree with the HP the store arrives at
    (multiple hits landing on one victim in a single frame chain correctly).
  * projectiles in flight (MissileEntity, type 13) with `fired_from_id`, so a
    shot can be tied to its shooter and to the damage event it produces —
    or to no damage event at all, which is a measured miss.
  * the AI command stream, so "what the AI ordered" stays separable from
    "what the engine did".

Segmentation mirrors redecode_hp: the recorder may start in the editor, so the
dump is split on clock resets / mid-stream full snapshots and the FIGHT segment
is chosen by evidence (both sides field a plausible army; the segment contains
deaths; ties go to the latest).

Outputs, written next to the prefix (or --out DIR):
  <name>.meta.json       capture + segment info, army composition, outcome
  <name>.units.jsonl.gz  per-unit per-sample state
  <name>.damage.jsonl.gz every hit, full resolution, with attacker/victim identity
  <name>.missiles.jsonl.gz projectile tracks
  <name>.commands.jsonl  AI command stream
  <name>.summary.json    per-unit and per-side derived aggregates

  python decode_fight.py <prefix> [--out DIR] [--pos-hz 10] [--name NAME]

Run with a python that has grpcio/protobuf (apps/video/.venv).
"""
import argparse
import gzip
import json
import math
import os
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cade_api_pb2 as pb            # noqa: E402
import decode_state_v2 as D          # noqa: E402

SNAP_RESEED = 400_000                # mid-stream patches above this are full snapshots
F_MASTER, F_OWNER, F_X, F_Y, F_STATE, F_HP = 1, 2, 3, 4, 8, 12
F_UNDER_ATTACK, F_ACTION, F_FACET = 13, 20, 16
F_FIRED_FROM = 22                    # MissileEntity.fired_from_id
F_FORMATION, F_STANCE, F_VOLLEY, F_CHARGE = 35, 36, 42, 44
ARMY_MT = {9, 11, 12}                # combat-entity model types
MISSILE_MT = 13
SCOUT = 448                          # the AI's explorer — never part of an army
MIN_ARMY, MAX_ARMY = 3, 80
SIDES = (2, 3)                       # player slots the golden templates fight on


# ---------------------------------------------------------------------------
# The undocumented damage event (Event field 6)
# ---------------------------------------------------------------------------
def parse_damage_event(raw):
    """Hand-parse Event field 6 -> (victim, attacker, damage, victim_hp_after).

    protobuf can't do this for us: the repo's Event oneof ends at field 5, so a
    field-6 event arrives as an unknown field and WhichOneof() returns None.
    Proto3 omits zero-valued fields, so a killing blow simply has no field 4 —
    hence the .get() defaults rather than a strict 4-field requirement.
    """
    if not raw or raw[0] != 0x32 or raw[1] & 0x80:
        return None
    body = raw[2:2 + raw[1]]
    out, p = {}, 0
    while p < len(body):
        tag = body[p]
        p += 1
        fld, wt = tag >> 3, tag & 7
        if wt == 0:
            v, shift = 0, 0
            while p < len(body):
                b = body[p]
                p += 1
                v |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            out[fld] = v
        elif wt == 5:
            if p + 4 > len(body):
                return None
            out[fld] = struct.unpack_from("<f", body, p)[0]
            p += 4
        else:
            return None
    if 1 not in out or 2 not in out:
        return None
    return out[1], out[2], float(out.get(3, 0.0)), float(out.get(4, 0.0))


def read_frames(path):
    """Yield Frame messages from a length-prefixed FrameSequence dump."""
    with open(path, "rb") as f:
        while True:
            hdr = f.read(4)
            if len(hdr) < 4:
                return
            (ln,) = struct.unpack("<I", hdr)
            buf = f.read(ln)
            if len(buf) < ln:
                return
            sq = pb.FrameSequence()
            try:
                sq.ParseFromString(buf)
            except Exception:
                continue
            for fr in sq.frame:
                yield fr


def derive_army(es):
    """Army membership per side. hp > 0 only (not a higher floor): the Elite
    Blackwood Archer has 25 HP and a 30-HP 'decoration filter' would drop that
    whole army. Our scenarios strip camp props, so owner+type+not-scout is tight."""
    army = {o: set() for o in SIDES}
    for k, e in es.items():
        if (e.get("__type__") in ARMY_MT and e.get(F_OWNER) in SIDES
                and e.get(F_MASTER) != SCOUT
                and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 0):
            army[e.get(F_OWNER)].add(k)
    return army


class Segment:
    """One continuous game instance inside the dump."""

    __slots__ = ("idx", "army", "start_counts", "rows", "damage", "missiles",
                 "commands", "first_t", "last_t", "identity", "deaths")

    def __init__(self, idx, army):
        self.idx = idx
        self.army = army
        self.start_counts = tuple(len(army[o]) for o in SIDES)
        self.rows = []
        self.damage = []
        self.missiles = []
        self.commands = []
        self.first_t = self.last_t = None
        self.identity = {}
        self.deaths = 0

    def plausible(self):
        return all(MIN_ARMY <= c <= MAX_ARMY for c in self.start_counts)

    def score(self):
        return (1 if self.plausible() else 0, 1 if self.deaths >= 2 else 0, self.idx)


def decode(prefix, pos_hz):
    doc = es = world_id = None
    seg = None
    segments = []
    seg_idx = 0
    last_sec = None
    next_pos_t = None
    pos_dt = 1.0 / pos_hz if pos_hz > 0 else 0.0
    tick_times = []
    alive_prev = None

    for fr in read_frames(prefix + ".frames.bin"):
        t = fr.time / 1000.0
        p = fr.patch

        if p and len(p) > SNAP_RESEED:
            # full snapshot => a fresh game instance; start a new segment
            tmp = prefix + ".reseed.bin"
            with open(tmp, "wb") as f:
                f.write(p)
            doc, es = D.Doc(), {}
            _, world_id = D.seed_from_snapshot(tmp, doc, es)
            army = derive_army(es)
            seg = Segment(seg_idx, army)
            seg_idx += 1
            segments.append(seg)
            for o in SIDES:
                for k in army[o]:
                    seg.identity[k] = (o, es[k].get(F_MASTER))
            last_sec, next_pos_t, alive_prev = None, t, None
            continue

        if es is None or seg is None:
            continue

        sec = int(t)
        if last_sec is not None and sec < last_sec - 2:
            # clock went backwards: new instance with no snapshot yet
            es = seg = None
            continue
        last_sec = sec

        # --- events: the per-hit damage record (full resolution, never sampled)
        for ev in fr.event:
            if ev.WhichOneof("event") is not None:
                continue
            d = parse_damage_event(ev.SerializeToString())
            if d is None:
                continue
            victim, attacker, dmg, hp_after = d
            seg.damage.append({
                "t": round(t, 3), "attacker": attacker, "victim": victim,
                "damage": round(dmg, 3), "victim_hp_after": round(hp_after, 3),
                "kill": hp_after <= 0.0,
            })

        for cm in fr.command:
            kind = cm.WhichOneof("command")
            if kind:
                seg.commands.append({"t": round(t, 3), "kind": kind})

        if p:
            D.apply_patch(doc, p, es, world_id)

        # newly-seen army members (reinforcements / revive units like the Konnik)
        for k, e in es.items():
            if (k not in seg.identity and e.get("__type__") in ARMY_MT
                    and e.get(F_OWNER) in SIDES and e.get(F_MASTER) != SCOUT
                    and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 0):
                seg.identity[k] = (e.get(F_OWNER), e.get(F_MASTER))
                seg.army[e.get(F_OWNER)].add(k)

        alive = sum(1 for o in SIDES for k in seg.army[o]
                    if isinstance((es.get(k) or {}).get(F_HP), (int, float))
                    and es[k][F_HP] > 0)
        if alive_prev is None:
            alive_prev = alive
        seg.deaths = max(seg.deaths, alive_prev - alive)

        if seg.first_t is None:
            seg.first_t = t
        seg.last_t = t
        tick_times.append(t)

        # --- sampled per-unit state
        if next_pos_t is None or t + 1e-9 >= next_pos_t:
            next_pos_t = t + pos_dt
            for o in SIDES:
                for k in seg.army[o]:
                    e = es.get(k)
                    if not e:
                        continue
                    hp = e.get(F_HP)
                    if not isinstance(hp, (int, float)) or hp <= 0:
                        continue
                    seg.rows.append({
                        "t": round(t, 3), "id": k, "owner": o,
                        "master": e.get(F_MASTER),
                        "x": _r(e.get(F_X)), "y": _r(e.get(F_Y)),
                        "hp": round(float(hp), 2),
                        "state": e.get(F_STATE), "facet": e.get(F_FACET),
                        "under_attack": e.get(F_UNDER_ATTACK),
                        "stance": e.get(F_STANCE), "formation": e.get(F_FORMATION),
                        "volley": _r(e.get(F_VOLLEY)), "charge": _r(e.get(F_CHARGE)),
                    })
        # Missiles are tracked at FULL frame rate, never at the sampled rate: a
        # projectile fired at short range can live well under 100 ms, so a 10 Hz sample
        # misses whole shots. Measured on the spike: sampled tracking counted 357 shots
        # against 368 recorded hits — a 103% "accuracy" that is arithmetically impossible
        # and would have silently corrupted every accuracy figure in the golden set.
        for k, e in es.items():
            if e.get("__type__") != MISSILE_MT:
                continue
            seg.missiles.append({
                "t": round(t, 3), "id": k, "owner": e.get(F_OWNER),
                "master": e.get(F_MASTER), "fired_from": e.get(F_FIRED_FROM),
                "x": _r(e.get(F_X)), "y": _r(e.get(F_Y)),
            })

    return segments, tick_times


def _r(v, nd=3):
    return round(float(v), nd) if isinstance(v, (int, float)) else None


# ---------------------------------------------------------------------------
# Derived aggregates
# ---------------------------------------------------------------------------
def summarize(seg, names):
    per_unit = {}
    for uid, (owner, master) in seg.identity.items():
        per_unit[uid] = {
            "id": uid, "owner": owner, "master": master,
            "name": names.get(master, str(master)),
            "hits_landed": 0, "hits_taken": 0,
            "damage_dealt": 0.0, "damage_taken": 0.0,
            "kills": 0, "died_at": None, "killed_by": None,
            "first_hit_t": None, "last_hit_t": None,
            "damage_per_hit": Counter(), "targets": Counter(),
            "swing_intervals": [],
        }

    for d in seg.damage:
        a, v = d["attacker"], d["victim"]
        if a in per_unit:
            u = per_unit[a]
            u["hits_landed"] += 1
            u["damage_dealt"] += d["damage"]
            u["damage_per_hit"][round(d["damage"], 1)] += 1
            u["targets"][v] += 1
            if u["first_hit_t"] is None:
                u["first_hit_t"] = d["t"]
            if u["last_hit_t"] is not None:
                u["swing_intervals"].append(round(d["t"] - u["last_hit_t"], 3))
            u["last_hit_t"] = d["t"]
            if d["kill"]:
                u["kills"] += 1
        if v in per_unit:
            w = per_unit[v]
            w["hits_taken"] += 1
            w["damage_taken"] += d["damage"]
            if d["kill"] and w["died_at"] is None:
                w["died_at"] = d["t"]
                w["killed_by"] = a

    # distance travelled, from the sampled position track
    track = defaultdict(list)
    for r in seg.rows:
        track[r["id"]].append((r["x"], r["y"]))
    for uid, pts in track.items():
        if uid not in per_unit:
            continue
        dist = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if None in (x0, y0, x1, y1):
                continue
            dist += math.hypot(x1 - x0, y1 - y0)
        per_unit[uid]["distance_tiles"] = round(dist, 2)
        per_unit[uid]["samples"] = len(pts)

    out_units = []
    for u in per_unit.values():
        iv = u.pop("swing_intervals")
        u["swing_interval_median"] = round(sorted(iv)[len(iv) // 2], 3) if iv else None
        u["swing_interval_min"] = round(min(iv), 3) if iv else None
        u["damage_per_hit"] = dict(u["damage_per_hit"])
        u["distinct_targets"] = len(u["targets"])
        u["targets"] = dict(u["targets"].most_common(5))
        u["damage_dealt"] = round(u["damage_dealt"], 1)
        u["damage_taken"] = round(u["damage_taken"], 1)
        out_units.append(u)
    out_units.sort(key=lambda u: (u["owner"], u["id"]))

    sides = {}
    for o in SIDES:
        us = [u for u in out_units if u["owner"] == o]
        alive = [u for u in us if u["died_at"] is None]
        masters = Counter(u["master"] for u in us)
        top = masters.most_common(1)[0][0] if masters else None
        sides[f"side{o}"] = {
            "owner": o,
            "unit": names.get(top, str(top)), "master": top,
            "start_count": len(us), "survivors": len(alive),
            "hp_start": None,                      # filled below, from first samples
            "hits_landed": sum(u["hits_landed"] for u in us),
            "damage_dealt": round(sum(u["damage_dealt"] for u in us), 1),
            "kills": sum(u["kills"] for u in us),
            "hp_remaining": None,
        }
    # survivor HP = last sampled HP of units that never took a killing blow. Counting
    # a dead unit's final pre-death sample would inflate this (a wiped side must read 0).
    survivors = {u["id"] for u in out_units if u["died_at"] is None}
    for o in SIDES:
        last_hp, first_hp = {}, {}
        for r in seg.rows:
            if r["owner"] != o:
                continue
            first_hp.setdefault(r["id"], r["hp"])       # rows are time-ordered
            if r["id"] in survivors:
                last_hp[r["id"]] = r["hp"]
        sides[f"side{o}"]["hp_remaining"] = round(sum(last_hp.values()), 1)
        # starting pool, so "the winner kept X% of its HP" is answerable without
        # re-deriving max HP per unit from the reference DB
        sides[f"side{o}"]["hp_start"] = round(sum(first_hp.values()), 1)

    s2, s3 = sides["side2"], sides["side3"]
    if s3["survivors"] == 0 and s2["survivors"] > 0:
        outcome = "side2"
    elif s2["survivors"] == 0 and s3["survivors"] > 0:
        outcome = "side3"
    elif s2["survivors"] == 0 and s3["survivors"] == 0:
        outcome = "both_wiped"
    else:
        outcome = "timeout"

    return {"outcome": outcome, "sides": sides, "units": out_units}


def _names_from_scenario_parser():
    """master_id -> readable name, from AoE2ScenarioParser's UnitInfo. Fallback for
    when aocref isn't installed (it isn't in the recording venv)."""
    try:
        from AoE2ScenarioParser.datasets.units import UnitInfo
    except Exception:
        return {}
    out = {}
    for u in UnitInfo:
        try:
            out.setdefault(int(u.ID), u.name.replace("_", " ").title())
        except Exception:
            continue
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("prefix", help="capture prefix (without .frames.bin)")
    ap.add_argument("--out", default=None, help="output directory (default: alongside)")
    ap.add_argument("--name", default=None, help="basename for the outputs")
    ap.add_argument("--pos-hz", type=float, default=10.0,
                    help="per-unit position/state sample rate (0 = every frame). "
                         "Damage events are ALWAYS full resolution.")
    args = ap.parse_args(argv)

    prefix = args.prefix
    name = args.name or os.path.basename(prefix)
    outdir = args.out or os.path.dirname(os.path.abspath(prefix))
    os.makedirs(outdir, exist_ok=True)
    base = os.path.join(outdir, name)

    names = D.load_unit_names() or _names_from_scenario_parser()
    segments, tick_times = decode(prefix, args.pos_hz)
    if not segments:
        print("no decodable segment (no full snapshot in the dump?)")
        return 1
    seg = max(segments, key=Segment.score)

    dt = [b - a for a, b in zip(tick_times, tick_times[1:]) if 0 < b - a < 1]
    hz = round(1.0 / (sum(dt) / len(dt)), 1) if dt else None

    summary = summarize(seg, names)

    with gzip.open(base + ".units.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in seg.rows:
            f.write(json.dumps(r) + "\n")
    with gzip.open(base + ".damage.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in seg.damage:
            a = seg.identity.get(r["attacker"])
            v = seg.identity.get(r["victim"])
            r = dict(r)
            r["attacker_owner"], r["attacker_master"] = (a or (None, None))
            r["victim_owner"], r["victim_master"] = (v or (None, None))
            f.write(json.dumps(r) + "\n")
    with gzip.open(base + ".missiles.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in seg.missiles:
            f.write(json.dumps(r) + "\n")
    with open(base + ".commands.jsonl", "w", encoding="utf-8") as f:
        for r in seg.commands:
            f.write(json.dumps(r) + "\n")

    # POSITION-FREEZE CHECK. On 2026-07-31 the game's position stream silently stopped
    # updating ~21 hours into a session: every unit logged its spawn tile for the whole
    # fight while hp and damage kept flowing, so the tapes decoded clean and looked valid.
    # 59 melee fights were recorded that way before anyone noticed. A fight where NOTHING
    # moved is never real -- units re-target, close, and get pushed -- so say so loudly.
    # Not fatal: the outcome/damage data in such a tape is still good, and failing the
    # decode would just make the recorder re-record into the same broken session.
    moved = set()
    seen_at = {}
    for r in seg.rows:
        prev = seen_at.get(r["id"])
        if prev is None:
            seen_at[r["id"]] = (r["x"], r["y"])
        elif prev != (r["x"], r["y"]):
            moved.add(r["id"])
    frozen = seg.rows and not moved
    if frozen:
        print("WARNING: positions frozen — every unit stayed on its spawn tile for the "
              "whole fight. The game's position stream has stalled; RESTART THE GAME. "
              "Damage/hp in this tape are still usable, positions are not.", flush=True)

    meta = {
        "capture_prefix": os.path.abspath(prefix),
        "positions_frozen": bool(frozen),
        "units_that_moved": len(moved),
        "segments_in_dump": len(segments),
        "segment_chosen": seg.idx,
        "segment_start_counts": list(seg.start_counts),
        "stream_hz": hz,
        "position_sample_hz": args.pos_hz or hz,
        "fight_t_start": seg.first_t, "fight_t_end": seg.last_t,
        "duration_s": round((seg.last_t or 0) - (seg.first_t or 0), 2),
        "damage_events": len(seg.damage),
        "unit_samples": len(seg.rows),
        "missile_samples": len(seg.missiles),
        "commands": len(seg.commands),
        "composition": {
            f"side{o}": dict(Counter(
                names.get(m, str(m)) for k, (ow, m) in seg.identity.items() if ow == o))
            for o in SIDES},
    }
    for extra in (".meta.json",):
        src = prefix + extra
        if os.path.exists(src):
            try:
                meta["recorder_meta"] = json.load(open(src))
            except Exception:
                pass
    with open(base + ".meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    with open(base + ".summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"segments={len(segments)} picked={seg.idx} start={seg.start_counts} "
          f"stream={hz}Hz dur={meta['duration_s']}s")
    print(f"  damage events {len(seg.damage)}   unit samples {len(seg.rows)}   "
          f"missiles {len(seg.missiles)}   commands {len(seg.commands)}")
    for o in SIDES:
        s = summary["sides"][f"side{o}"]
        print(f"  side{o} {s['unit']:26s} {s['start_count']:2d} -> {s['survivors']:2d} "
              f"survivors, {s['hits_landed']:4d} hits, {s['damage_dealt']:7.0f} dmg, "
              f"{s['kills']:2d} kills")
    print(f"  OUTCOME: {summary['outcome']}")
    print(f"  -> {base}.{{meta,summary}}.json  {base}.{{units,damage,missiles}}.jsonl.gz")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))
