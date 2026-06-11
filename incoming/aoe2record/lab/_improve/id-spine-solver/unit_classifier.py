"""Group-first, confidence-based AoE2:DE unit-type classifier.

Standalone: takes a parsed mgz ``match`` (no Flask dependency). See
CLASSIFIER_REWORK.md for the full design and rationale.

Implemented so far: Stage 0 (context + id normalization), Stage 1 (refined
behavioral class), Stage 2 (co-command class propagation). Stages 3-5 (production
timeline, squad typing, finalize) are scaffolded and filled in subsequent phases.
"""

import bisect
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations

# --- command semantics (refined; see findings in CLASSIFIER_REWORK.md) --------
# Only a MILITARY unit can be the subject of these.
MIL_CMDS = {"STANCE", "FORMATION", "PATROL", "ATTACK_GROUND", "DE_ATTACK_MOVE", "GUARD"}
# Only a VILLAGER can BUILD/REPAIR/WALL (gather is handled via resource targets).
VIL_CMDS = {"BUILD", "REPAIR", "WALL"}
# Commands whose object_ids reference a BUILDING, not the acting unit.
BLD_SUBJECT_CMDS = {
    "DE_QUEUE", "RESEARCH", "GATHER_POINT", "SELL", "BUY",
    "TOWN_BELL", "UNGARRISON", "DE_MULTI_GATHERPOINT",
}
# Commands that can carry a unit "group" (multiple object_ids that act together).
GROUP_CMDS = {"MOVE", "PATROL", "ORDER", "DE_ATTACK_MOVE", "GUARD", "STANCE", "FORMATION"}
# GAIA names only villagers gather (NOT animals: scouts lure boar, both attack).
RESOURCE_KW = ("gold mine", "stone mine", "tree", "bush", "berr", "forage", "shrub", "plant")

# SPECIAL/UNGARRISON encode object ids byte-shifted (id<<8); normalize via >>8.
SHIFT_THRESHOLD = 1_000_000

# Confidence ladder.
CONF = {
    "header": 0.99,
    "hard_class": 0.95,
    "cocmd_class": 0.90,
    "squad_type": 0.80,
    "idrank_type": 0.55,
    "fallback": 0.30,
}

# Base DE train times (seconds). Loaded from train_times.json (extracted from the
# aoe2-unit-analyzer .dat database -- civ-accurate base values); this dict is the
# fallback for tokens the DB names differently. Default 30 for unknowns.
_FALLBACK_TRAIN_TIMES = {
    "villager": 25, "fishingship": 40, "tradecart": 51, "tradecog": 36,
    "militia": 21, "manatarms": 21, "spearman": 22, "eaglescout": 60,
    "archer": 35, "crossbowman": 27, "skirmisher": 22, "cavalryarcher": 34, "handcannoneer": 34,
    "scoutcavalry": 30, "knight": 30, "camelrider": 22, "camelscout": 22, "battleelephant": 24,
    "monk": 51, "mangonel": 46, "scorpion": 30, "batteringram": 36, "trebuchet": 50,
    "bombardcannon": 56, "magyarhuszar": 16,
    # common unique/regional units (base DE values; default 30 otherwise)
    "berserk": 16, "mangudai": 26, "rattanarcher": 16, "steppelancer": 24,
    "battleelephant": 24, "eaglewarrior": 35, "eaglescout": 60, "konnik": 19,
    "woadraider": 10, "huskarl": 16, "tarkan": 14, "genoesecrossbowman": 22,
    "camel": 22, "lightcavalry": 30, "hussar": 30, "elephantarcher": 25,
}


def _load_train_times():
    """Merge the DB-extracted civ-accurate base train times over the fallback."""
    import json as _json
    import os as _os
    tt = dict(_FALLBACK_TRAIN_TIMES)
    try:
        p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "train_times.json")
        data = _json.load(open(p))
        for k, v in (data.get("base") or {}).items():
            if v:
                tt[k] = float(v)
    except Exception:
        pass
    # tokens the DB names differently than DE_QUEUE / the classifier
    tt.setdefault("militia", 21)
    tt.setdefault("manatarms", 21)
    tt.setdefault("champiscout", tt.get("champiwarrior", 26))
    return tt


TRAIN_TIMES = _load_train_times()

# Passive CIV bonuses that change unit CREATION speed. These are NOT in the DB's
# final_train_time (which only reflects tech upgrades), so they must be applied here as
# a multiplier on military train time. Without this the per-building FIFO mis-times (and
# thus mis-orders) a civ's whole army -- e.g. Aztec military trains 11% faster, so the
# base-time model runs ~11% slow and drifts later as the queue deepens.
CIV_MIL_SPEED = {
    "Aztecs": 0.89,   # "Military units created 11% faster"
}


TICKS_PER_SEC = 20   # AoE2 simulation granularity; production completes on tick boundaries

# Lines the Aztec-style "military created faster" bonus applies to. Calibrated from gRPC
# spawn data: Barracks/Archery/Stable AND Siege Workshop ARE sped up (mangonel queue+41s
# = 46x0.89, confirmed), but the MONASTERY is NOT (monks spawn exactly 51s apart = base).
# So the bonus covers every military-production building except the Monastery.
_SPEED_BONUS_LINES = {"arch", "inf", "cav", "siege", "unique"}


def _tt(unit, civ=None):
    """Civ-aware train time in TICKS (20/sec): base DB value x any passive creation-speed
    bonus, then quantised to the game's tick clock so completions land where the engine
    actually spawns them."""
    base = TRAIN_TIMES.get(unit, 30)
    if civ in CIV_MIL_SPEED and unit != "villager" and _line_of(unit) in _SPEED_BONUS_LINES:
        base *= CIV_MIL_SPEED[civ]
    return round(base * TICKS_PER_SEC) / TICKS_PER_SEC   # quantise to the tick clock


def _norm(s):
    return (s or "").lower().replace(" ", "")


def canonical_id(oid):
    """Collapse SPECIAL/UNGARRISON shifted refs (id<<8) back to the real id."""
    return oid >> 8 if oid >= SHIFT_THRESHOLD else oid


@dataclass
class UnitGuess:
    instance_id: int
    player: str = None
    cls: str = "unknown"          # 'villager' | 'military' | 'unknown'
    cls_conf: float = 0.0
    type: str = "unit"
    type_conf: float = 0.0
    squad_id: int = None
    role: str = "unknown"          # behavioral: 'eco'|'cavalry'|'ranged'|'siege'...
    signals: list = field(default_factory=list)
    behavior: dict = field(default_factory=dict)


@dataclass
class Context:
    match: object
    guesses: dict = field(default_factory=dict)        # canonical id -> UnitGuess
    owner: dict = field(default_factory=dict)          # canonical id -> player name
    building_ids: set = field(default_factory=set)     # canonical building ids
    start_ids: set = field(default_factory=set)
    resource_ids: set = field(default_factory=set)     # gaia resources (villager-only)
    gaia_all: set = field(default_factory=set)
    group_cmds: list = field(default_factory=list)     # [(player, [canonical ids]), ...]
    # production: building id -> list of (queue_time, unit_type)
    queues: dict = field(default_factory=lambda: defaultdict(list))
    shifted: set = field(default_factory=set)  # raw ids that arrive byte-shifted
    timeseries: dict = field(default_factory=dict)  # player -> [(t_sec, total_objects)]
    resign: dict = field(default_factory=dict)      # player -> resign time (sec)
    unqueues: dict = field(default_factory=lambda: defaultdict(list))  # building -> [(t, slot)]
    civ: dict = field(default_factory=dict)         # player name -> civilization

    def canon(self, oid):
        """Source-aware id normalization. Only ids that arrive via SPECIAL/
        UNGARRISON are byte-shifted (id<<8) by the parser, so decode *only* those
        -- avoids the fragile >=1M magnitude heuristic that could corrupt a
        legitimate large id in a long game."""
        return (oid >> 8) if oid in self.shifted else oid


def _at(action):
    return str(action.type).replace("Action.", "")


def _seed_class_from_name(name):
    n = _norm(name)
    if "villager" in n or "fishing" in n:
        return "villager"
    if "scout" in n or "king" in n:
        return "military"
    return None


def build_context(match):
    """Stage 0: owner map, gaia split, behavior counters, group commands, queues.

    All object ids are normalized to canonical (shifted SPECIAL/UNGARRISON refs
    collapsed and deduped), so each physical unit is one id.
    """
    ctx = Context(match=match)

    # Pre-pass: collect the byte-shifted ids (those that arrive via SPECIAL /
    # UNGARRISON) so ctx.canon can decode exactly those.
    for a in match.actions:
        if a.player and _at(a) in ("SPECIAL", "UNGARRISON"):
            for o in (a.payload or {}).get("object_ids", []):
                ctx.shifted.add(o)

    # gaia: all ids + the villager-only resource subset
    gaia = getattr(match, "gaia", None) or []
    for g in gaia:
        iid = getattr(g, "instance_id", None)
        nm = (getattr(g, "name", None) or "").lower()
        if iid is None:
            continue
        ctx.gaia_all.add(iid)
        if nm and any(k in nm for k in RESOURCE_KW) and "dry" not in nm and "grass" not in nm:
            ctx.resource_ids.add(iid)

    # total_objects timeseries (per-player object count over time) -> used to
    # CALIBRATE production-completion timing for dense/concurrent production where
    # the per-building serial model misfires (multiqueue spreads one building's
    # queue impossibly). Increments are spawn events.
    for p in match.players:
        ctx.civ[p.name] = getattr(p, "civilization", None)
        ts = getattr(p, "timeseries", None) or []
        try:
            ctx.timeseries[p.name] = [(e.timestamp.total_seconds(), e.total_objects) for e in ts]
        except Exception:
            ctx.timeseries[p.name] = []

    # starting (header) units: known owner + name -> seed class at top confidence
    for p in match.players:
        for o in (p.objects or []):
            cid = ctx.canon(o.instance_id)
            ctx.start_ids.add(cid)
            ctx.owner[cid] = p.name
            g = _ensure(ctx, cid, p.name)
            onm = getattr(o, "name", None)
            seeded = _seed_class_from_name(onm)
            if seeded:
                _set_class(g, seeded, CONF["header"], "header")
                # starting units have a KNOWN identity from the header -> type them
                # directly (e.g. the free Scout Cavalry). They aren't produced, so the
                # production alignment must not touch them.
                if seeded == "military" and onm:
                    _set_type(g, _norm(onm), CONF["header"], "header")

    # walk actions: owner, behavior, group commands, queues, building ids
    building_free = defaultdict(float)   # building -> time its queue next goes idle
    for a in match.actions:
        if not a.player:
            continue
        at = _at(a)
        payload = a.payload or {}
        t = a.timestamp.total_seconds()
        if at == "RESIGN":
            # a resigning player stops producing immediately: anything still in the
            # build queue never spawns. Record the cutoff for production_timeline.
            ctx.resign[a.player.name] = t
            continue
        if payload.get("order") == "Unqueue":
            # cancel a unit from a building's production queue (it never spawns). The
            # building id arrives byte-shifted; slot_id is the queue position. Recorded
            # for production_timeline to remove from the FIFO -- without this the model
            # produces phantom units (e.g. ddk220 queued 10 archers, unqueued 5).
            slot = payload.get("slot_id")
            for o in payload.get("object_ids", []):
                ctx.unqueues[ctx.canon(o)].append((t, slot))
            continue
        ids = [ctx.canon(o) for o in payload.get("object_ids", [])]

        # DE_QUEUE etc: object_ids are BUILDINGS, not acting units
        if at in BLD_SUBJECT_CMDS:
            for b in ids:
                ctx.building_ids.add(b)
                ctx.owner.setdefault(b, a.player.name)
            if at == "DE_QUEUE" and ids:
                u = _norm(payload.get("unit"))
                amt = payload.get("amount", 1) or 1
                tt = _tt(u, ctx.civ.get(a.player.name))
                # MULTIQUEUE: object_ids is the full set of selected production
                # buildings; the game load-balances each unit to the one that
                # becomes free soonest. Simulate that so per-building queues are
                # realistic (not all dumped on ids[0]).
                for _ in range(amt):
                    b = min(ids, key=lambda bb: max(building_free[bb], t))
                    building_free[b] = max(building_free[b], t) + tt
                    ctx.queues[b].append((t, u))
            continue

        tgt = payload.get("target_id")
        for cid in ids:
            ctx.owner.setdefault(cid, a.player.name)
            g = _ensure(ctx, cid, a.player.name)
            b = g.behavior
            b.setdefault("first_seen", t)
            if at == "MOVE":
                b["moves"] = b.get("moves", 0) + 1
            elif at == "PATROL":
                b["patrols"] = b.get("patrols", 0) + 1
            elif at in VIL_CMDS:
                b["builds"] = b.get("builds", 0) + 1
            elif at == "ORDER" and isinstance(tgt, int):
                if tgt in ctx.resource_ids:
                    b["gathers"] = b.get("gathers", 0) + 1
                elif tgt not in ctx.gaia_all and ctx.owner.get(tgt) and ctx.owner.get(tgt) != a.player.name:
                    # NOTE: attacking an enemy object is NOT a class signal
                    # (villagers attack too). Recorded only as behavior.
                    b["attacks_building"] = b.get("attacks_building", 0) + 1
                elif tgt in ctx.building_ids and ctx.owner.get(tgt) == a.player.name:
                    # ORDER on a FRIENDLY (own-player) BUILDING. A monk does this to
                    # garrison its home monastery (drop a relic / re-bless); villagers do
                    # it to drop resources at a camp. NOT a class signal -- but among
                    # units already classed MILITARY it is monk-exclusive (a skirmisher/
                    # scout/knight never returns to a building), used by the monk override.
                    b["bld_order"] = b.get("bld_order", 0) + 1

        if at in GROUP_CMDS and len(ids) >= 2:
            ctx.group_cmds.append((a.player.name, sorted(set(ids))))

    return ctx


def _ensure(ctx, cid, player):
    g = ctx.guesses.get(cid)
    if g is None:
        g = ctx.guesses[cid] = UnitGuess(instance_id=cid, player=player)
    if g.player is None:
        g.player = player
    return g


def _set_class(g, cls, conf, signal):
    """Monotonic class update: only raise, never lower confidence."""
    if conf > g.cls_conf:
        g.cls = cls
        g.cls_conf = conf
        if signal not in g.signals:
            g.signals.append(signal)


def behavioral_labels(ctx):
    """Stage 1: refined hard class from a unit's own commands.

    A real unit cannot be both — so a unit that somehow carries BOTH a military
    and a villager hard-signal is treated as CONFLICTED (left unknown, not a
    seed). These are rare and stem from id ambiguity (imperfect SPECIAL/UNGARRISON
    shift-decode or id reuse); forcing a class on them is what erodes the
    otherwise ~100% co-command class purity.
    """
    mil_sig = defaultdict(int)
    vil_sig = defaultdict(int)
    for a in ctx.match.actions:
        if not a.player:
            continue
        at = _at(a)
        is_mil = at in MIL_CMDS
        is_vil = at in VIL_CMDS
        if not (is_mil or is_vil):
            continue
        for o in (a.payload or {}).get("object_ids", []):
            cid = ctx.canon(o)
            if cid in ctx.building_ids:
                continue
            _ensure(ctx, cid, a.player.name)
            (mil_sig if is_mil else vil_sig)[cid] += 1
    # gather-on-resource is a villager-hard signal (recorded during build_context)
    for cid, g in ctx.guesses.items():
        if g.behavior.get("gathers"):
            vil_sig[cid] += 1

    # BUILD/REPAIR/WALL is the only UNAMBIGUOUS villager signal: military units can
    # never build. GATHER, by contrast, is contaminated -- a player who co-selects
    # military with villagers and right-clicks a resource gives the military a phantom
    # "gather" it physically cannot perform. So we record gather separately (soft) and
    # let the production alignment, not the gather, decide a gather-only unit's class.
    build_sig = defaultdict(int)
    for a in ctx.match.actions:
        if not a.player or _at(a) not in VIL_CMDS:
            continue
        for o in (a.payload or {}).get("object_ids", []):
            cid = ctx.canon(o)
            if cid not in ctx.building_ids:
                build_sig[cid] += 1

    for cid in set(mil_sig) | set(vil_sig):
        g = ctx.guesses.get(cid)
        if g is None:
            continue
        m = mil_sig.get(cid, 0)
        bld = build_sig.get(cid, 0)
        gth = g.behavior.get("gathers", 0)
        # flags consumed by the production-alignment stage
        if m:
            g.behavior["hard_mil"] = m
        if bld:
            g.behavior["hard_build"] = bld
        if m and bld:
            g.signals.append("conflict")            # genuine id ambiguity -> unknown
        elif bld:
            _set_class(g, "villager", CONF["hard_class"], "behavior")
        elif m:
            _set_class(g, "military", CONF["hard_class"], "behavior")
        elif gth:
            # gather-only: provisional villager, but LOW confidence so the production
            # alignment can promote it to military if it claims a military slot.
            _set_class(g, "villager", CONF["idrank_type"], "gather")


def cocommand_graph(ctx):
    """Stage 2a: weighted co-command edges between (non-building) units."""
    weight = Counter()
    for _player, ids in ctx.group_cmds:
        units = [i for i in ids if i not in ctx.building_ids]
        if 2 <= len(units) <= 40:
            for x, y in combinations(units, 2):
                weight[(x, y)] += 1
    return weight


def propagate_class(ctx, weight, min_weight=2, iters=12):
    """Stage 2b: spread hard class across the co-command graph.

    Co-command is ~100% class-consistent on hard labels, so we propagate by
    UNANIMITY rather than majority: an unknown unit takes a class only if all of
    its (strong, weight >= min_weight) labeled group-mates agree. This keeps the
    100% purity of the signal instead of letting a lone off-class neighbour drag
    a unit across the boundary. Only fills 'unknown' units; hard/header labels
    are never overwritten.
    """
    adj = defaultdict(list)
    for (x, y), w in weight.items():
        if w < min_weight:
            continue
        adj[x].append((y, w))
        adj[y].append((x, w))

    for _ in range(iters):
        updates = {}
        for cid, nbrs in adj.items():
            g = ctx.guesses.get(cid)
            if g is None or g.cls != "unknown":
                continue
            classes = {ctx.guesses[n].cls for n, _ in nbrs
                       if n in ctx.guesses and ctx.guesses[n].cls != "unknown"}
            if len(classes) == 1:
                updates[cid] = next(iter(classes))
        if not updates:
            break
        for cid, cls in updates.items():
            _set_class(ctx.guesses[cid], cls, CONF["cocmd_class"], "cocmd")


# --- Stage 3: production timeline -------------------------------------------
GENERIC_TYPES = {"unit", "military"}

# Unit type -> production LINE (= the building that makes it). Units from different
# buildings are different lines; the merged FIFO blurs them (a knight reads as a
# concurrent archer), so we align each line's FIFO separately. Default 'arch' for
# unmapped tokens is deliberately overridden below to 'unique' so a stray unique
# unit does not pollute the archery line.
_TYPE_LINE = {
    # archery range
    "archer": "arch", "crossbowman": "arch", "arbalester": "arch", "skirmisher": "arch",
    "eliteskirmisher": "arch", "imperialskirmisher": "arch", "slinger": "arch",
    "cavalryarcher": "arch", "heavycavalryarcher": "arch", "handcannoneer": "arch",
    "genitour": "arch", "elitegenitour": "arch", "rattanarcher": "arch", "elephantarcher": "arch",
    "mangudai": "arch", "warwagon": "arch", "chukonu": "arch", "genoesecrossbowman": "arch",
    "plumedarcher": "arch", "longbowman": "arch", "warwagon": "arch",
    # barracks
    "militia": "inf", "manatarms": "inf", "longswordsman": "inf", "twohandedswordsman": "inf",
    "champion": "inf", "spearman": "inf", "pikeman": "inf", "halberdier": "inf",
    "eaglescout": "inf", "eaglewarrior": "inf", "eliteeaglewarrior": "inf", "champiscout": "inf",
    "huskarl": "inf", "woadraider": "inf", "berserk": "inf", "jaguarwarrior": "inf",
    "throwingaxeman": "inf", "gbeto": "inf", "shotelwarrior": "inf", "condottiero": "inf",
    "karambitwarrior": "inf", "teutonicknight": "inf", "samurai": "inf", "legionary": "inf",
    # stable
    "scoutcavalry": "cav", "lightcavalry": "cav", "hussar": "cav", "winghussar": "cav",
    "knight": "cav", "cavalier": "cav", "paladin": "cav", "camelrider": "cav",
    "heavycamelrider": "cav", "camelscout": "cav", "battleelephant": "cav",
    "steppelancer": "cav", "konnik": "cav", "tarkan": "cav", "magyarhuszar": "cav",
    "boyar": "cav", "cataphract": "cav", "warelephant": "cav", "leitis": "cav",
    "keshik": "cav", "coustillier": "cav", "shrivamsharider": "cav",
    # siege workshop / castle siege
    "batteringram": "siege", "cappedram": "siege", "siegeram": "siege", "mangonel": "siege",
    "onager": "siege", "siegeonager": "siege", "scorpion": "siege", "heavyscorpion": "siege",
    "trebuchet": "siege", "bombardcannon": "siege", "siegetower": "siege", "hussitewagon": "siege",
    "armoredelephant": "siege", "siegeelephant": "siege",
    # monastery
    "monk": "monk", "missionary": "monk", "warriorpriest": "monk", "imam": "monk",
}


def _line_of(t):
    return _TYPE_LINE.get((t or "").replace(" ", "").lower(), "unique")


def _set_type(g, t, conf, signal):
    """Monotonic type update; never downgrade a specific type to a generic one."""
    if not t:
        return
    if g.type not in GENERIC_TYPES and t in GENERIC_TYPES:
        return
    if (g.type in GENERIC_TYPES and t not in GENERIC_TYPES) or conf > g.type_conf:
        g.type = t
        g.type_conf = max(g.type_conf, conf) if g.type == t else conf
        if signal not in g.signals:
            g.signals.append(signal)


def _apply_unqueues(queue, unqs, civ=None):
    """Remove unqueued units from a building's queue. Each Unqueue(t) cancels the
    most-recently-queued unit still PENDING (completion > t) at that moment -- players
    cancel from the BACK of the queue (the excess they just over-queued), which matches
    the gRPC spawns far better than honouring the raw slot index. Removing a unit also
    speeds up everything behind it, so completion is recomputed between unqueues."""
    if not unqs:
        return queue
    q = list(queue)
    for utime, _slot in sorted(unqs):
        if not q:
            break
        done = 0.0
        comp = []
        for qt, u in q:
            done = max(qt, done) + _tt(u, civ)
            comp.append(done)
        pend = [i for i, c in enumerate(comp) if c > utime]   # not yet completed
        if not pend:
            continue
        q = q[:pend[-1]] + q[pend[-1] + 1:]                   # cancel the newest pending
    return q


def production_timeline(ctx):
    """Stage 3: per-building serial completion (max(queue,prev_done)+train_time).

    Returns (full, mil): per-player lists of (completion_time, type), full
    including villagers, mil military-only.
    """
    full = defaultdict(list)
    mil = defaultdict(list)
    for b, q in ctx.queues.items():
        player = ctx.owner.get(b)
        civ = ctx.civ.get(player)
        cutoff = ctx.resign.get(player, float("inf"))   # stop producing at resign
        q = _apply_unqueues(sorted(q), ctx.unqueues.get(b, []), civ)
        done = 0.0
        for ts, u in q:
            done = max(ts, done) + _tt(u, civ)
            if done > cutoff:
                break       # FIFO: this + every later unit in this building never trains
            # carry the building id so units completing on the SAME tick are ordered by
            # building (the engine processes buildings in id order within a tick) -- this
            # resolves sub-tick ties the completion time alone can't.
            full[player].append((done, b, u))
            if u != "villager":
                mil[player].append((done, b, u))
    for d in (full, mil):
        for player in d:
            d[player].sort()                       # (completion, building_id) order
            d[player][:] = [(t, u) for t, _b, u in d[player]]
    ctx.prod_full, ctx.prod_mil = full, mil
    return full, mil


def count_calibrated_mil_stream(ctx, player):
    """Time each military completion using the total_objects increments (real spawn
    events) instead of guessed train times. Returns sorted [(completion_t, type)].
    This fixes ordering for dense/multiqueue production the serial model gets wrong."""
    ts = ctx.timeseries.get(player) or []
    incs = []
    prev = None
    for t, tot in ts:
        if prev is not None and tot > prev:
            incs.extend([t] * (tot - prev))
        prev = tot if prev is None else max(prev, tot)
    events = sorted((qt, u) for b, q in ctx.queues.items() if ctx.owner.get(b) == player
                    for qt, u in q if u != "villager")
    stream = []
    ii = 0
    for qt, u in events:
        while ii < len(incs) and incs[ii] < qt:
            ii += 1
        ct = incs[ii] if ii < len(incs) else qt + 30
        stream.append((ct, u))
        ii += 1
    stream.sort()
    return stream


def _align(ids_sorted, comp_types):
    """Proportional rank alignment: i-th created unit -> i-th completion type."""
    out = {}
    m = len(comp_types)
    n = len(ids_sorted)
    if m == 0:
        return out
    for i, cid in enumerate(ids_sorted):
        j = round(i * (m - 1) / (n - 1)) if n > 1 else 0
        out[cid] = comp_types[j]
    return out


def _role_of(g):
    b = g.behavior
    if g.cls == "villager":
        return "eco"
    if b.get("attacks_building") and not b.get("patrols") and b.get("moves", 0) <= 6:
        return "siege"
    if b.get("patrols"):
        return "cavalry"
    return "military"


def assign_types(ctx, squads):
    """Stage 4: GROUP-based typing.

    Each 'blob' -- a co-command squad, or a lone unit -- is typed as ONE unit, so
    co-moving groups come out homogeneous (the strongest signal we have:
    co-commanded units are ~100% the same type). Military types are handed out
    from the player's production stream with a REMAINING-BUDGET constraint, so
    homogenizing can't let the dominant unit (huszar) absorb the minorities
    (cav-archer/treb) -- global proportions still track production.

    This replaces the old per-unit id-rank typing + inert gap-fill smoothing.
    """
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.start_ids or cid in ctx.gaia_all:
            continue
        g.role = _role_of(g)

    squad_of = {}
    for sid, c in enumerate(squads):
        for cid in c:
            squad_of[cid] = sid

    blobs = defaultdict(list)
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.start_ids or cid in ctx.gaia_all:
            continue
        key = ("sq", squad_of[cid]) if cid in squad_of else ("solo", cid)
        blobs[key].append(cid)

    by_player = defaultdict(list)
    for members in blobs.values():
        by_player[ctx.guesses[members[0]].player].append(members)

    def blob_class(members):
        known = [ctx.guesses[m].cls for m in members if ctx.guesses[m].cls != "unknown"]
        return Counter(known).most_common(1)[0][0] if known else None

    def med(members):
        s = sorted(members)
        return s[len(s) // 2]

    for player, blist in by_player.items():
        # ONE budget over the full production stream (villagers + every military
        # type), so blobs are handed types in creation order, constrained by what
        # the player actually produced. This keeps proportions honest across BOTH
        # classes -- unknowns can't all pile into the single most-common type.
        full = [t for _, t in ctx.prod_full.get(player, [])]
        F = len(full)
        mil_types = set(t for t in full if t != "villager") or {"military"}
        target = Counter(full)        # production counts per type (the quota)
        assigned = Counter()          # running assignment

        all_ids = sorted(cid for members in blist for cid in members)
        Nall = len(all_ids)
        rank = {cid: i for i, cid in enumerate(all_ids)}

        def pos(cid):
            return round(rank[cid] * (F - 1) / (Nall - 1)) if (Nall > 1 and F > 0) else 0

        # Pick the in-window candidate furthest BELOW its production quota, so
        # minorities (cav-archer/cart/treb) get their share and large blobs still
        # fall to the large types -- proportions track production without one
        # type starving the rest.
        def pick(cand, s):
            return min(cand, key=lambda c: (assigned[c] + s) / max(1, target.get(c, 1)))

        HARD = CONF["hard_class"]
        for members in sorted(blist, key=med):
            s = len(members)
            cls = blob_class(members)
            window = full[min(pos(m) for m in members):max(pos(m) for m in members) + 1] if F else []
            mil_cand = set(w for w in window if w != "villager") or mil_types
            # A blob that carries BOTH hard-villager and hard-military members is a
            # mass-select (select-all + move), NOT a real co-typed squad. Co-command
            # co-typing is invalid here, so SOFT members are typed individually by
            # their own production rank instead of inheriting the blob majority.
            hetero = (any(ctx.guesses[m].cls_conf >= HARD and ctx.guesses[m].cls == "military" for m in members)
                      and any(ctx.guesses[m].cls_conf >= HARD and ctx.guesses[m].cls == "villager" for m in members))
            # base type for the blob's SOFT (no-hard-signal) members
            if cls == "villager":
                base_t, base_conf = "villager", CONF["squad_type"]
            elif cls == "military":
                base_t, base_conf = pick(mil_cand, s), CONF["squad_type"]
            else:  # no class signal -> full window decides vil/mil
                cand = set(window) or set(full) or {"unit"}
                base_t, base_conf = pick(cand, s), CONF["idrank_type"]
            # A HARD individual class (gather->villager, patrol/stance/attack-ground
            # ->military) must NEVER be overridden by the blob majority. Big mixed
            # "mass-select" components otherwise paint their minority class wrong.
            for m in members:
                gm = ctx.guesses[m]
                if gm.cls_conf >= HARD and gm.cls == "military":
                    t = base_t if base_t != "villager" else pick(mil_cand, 1)
                    _set_type(gm, t, CONF["squad_type"], "group")
                    _set_class(gm, "military", CONF["squad_type"], "group")
                    assigned[t] += 1
                elif gm.cls_conf >= HARD and gm.cls == "villager":
                    _set_type(gm, "villager", CONF["squad_type"], "group")
                    _set_class(gm, "villager", CONF["squad_type"], "group")
                    assigned["villager"] += 1
                elif hetero and F:
                    # mass-select: type this soft unit by its own production rank
                    t = full[pos(m)]
                    _set_type(gm, t, CONF["idrank_type"], "group")
                    _set_class(gm, "villager" if t == "villager" else "military",
                               CONF["idrank_type"], "group")
                    assigned[t] += 1
                else:
                    _set_type(gm, base_t, base_conf, "group")
                    _set_class(gm, "villager" if base_t == "villager" else "military",
                               base_conf, "group")
                    assigned[base_t] += 1


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def form_squads(ctx, weight, min_weight=2):
    """Stage 4a: connected components of the strong co-command graph = squads."""
    uf = _UF()
    for (x, y), w in weight.items():
        if w >= min_weight and x not in ctx.building_ids and y not in ctx.building_ids:
            uf.union(x, y)
    comps = defaultdict(list)
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.start_ids or cid in ctx.gaia_all:
            continue
        comps[uf.find(cid)].append(cid)
    squads = [c for c in comps.values() if len(c) >= 3]
    for sid, c in enumerate(squads):
        for cid in c:
            ctx.guesses[cid].squad_id = sid
    return squads


def dp_align_player(ctx, player, TOL=4.0, BIG=1e9):
    """Order-preserving (instance_id) alignment of a player's commanded military to
    the FIFO production stream. Lag-free: matches by spawn ORDER, with the hard
    constraint that a unit's slot is at-or-before its first command (spawn precedes
    command). Globally one-to-one (a DP), so each produced unit claims its own slot
    -- which resolves dense interleavings (skirmisher/spearman/slinger; knight amid
    archers) that command-time matching blurs. Returns {cid: type}."""
    units = sorted(c for c, g in ctx.guesses.items()
                   if g.player == player and g.cls == "military"
                   and c not in ctx.building_ids and c not in ctx.gaia_all
                   and c not in ctx.start_ids                       # starting units aren't produced
                   and g.behavior.get("first_seen") is not None)   # instance_id order
    fifo = sorted(ctx.prod_mil.get(player, []))
    N, M = len(units), len(fifo)
    if N == 0 or M == 0 or N > M:
        return {}
    ft = [t for t, _ in fifo]; fu = [u for _, u in fifo]
    fs = [ctx.guesses[c].behavior["first_seen"] for c in units]
    INF = float("inf")
    dp = [[INF] * (M + 1) for _ in range(N + 1)]
    bt = [[0] * (M + 1) for _ in range(N + 1)]
    for j in range(M + 1):
        dp[0][j] = 0.0
    for i in range(1, N + 1):
        di, dim1, bti, fsi = dp[i], dp[i - 1], bt[i], fs[i - 1]
        for j in range(i, M + 1):
            skip = di[j - 1]
            # spawn precedes command; among valid slots prefer the one closest to the
            # command (lowest lag). The order constraint (monotonic DP) keeps the
            # instance_id ordering; this resolves the dense interleaving + knights.
            lag = fsi - ft[j - 1]
            cst = BIG if lag < -TOL else (lag if lag > 0 else 0.0)
            match = dim1[j - 1] + cst
            if match <= skip:
                di[j] = match; bti[j] = 1
            else:
                di[j] = skip
    i, j = N, M; out = {}
    while i > 0 and j > 0:
        if bt[i][j] == 1:
            out[units[i - 1]] = fu[j - 1]; i -= 1; j -= 1
        else:
            j -= 1
    return out


def align_production(ctx, TOL=4.0, SKIP=22.0, EPS=0.5, BIG=1e9):
    """Unified class+type assignment from the per-player military FIFO.

    Aligns every candidate unit (anything not a confirmed builder-villager) to the
    military production stream by instance_id ORDER (lag-free spawn order) with a
    match/skip DP:
      - match unit i -> military slot j   (cost = command lag; spawn must precede cmd)
      - skip unit i   -> the unit is a villager (cost SKIP; +inf for a hard-military
        unit that MUST occupy a slot)
      - skip slot j   -> a produced unit that was never individually commanded (cost 0)
    A matched unit becomes military with its slot's exact type; an unmatched candidate
    keeps villager. This is where the building/queue -- not the contaminated gather --
    sets a unit's class, so a slinger from an archery range is military even with a
    phantom gather. Returns the set of matched cids."""
    matched_all = set()
    players = set(g.player for g in ctx.guesses.values() if g.player)
    for player in players:
        fifo = sorted(ctx.prod_mil.get(player, []))
        M = len(fifo)
        if M == 0:
            continue
        ft = [t for t, _ in fifo]
        fu = [u for _, u in fifo]
        cand = []
        for c, g in ctx.guesses.items():
            if g.player != player:
                continue
            if c in ctx.building_ids or c in ctx.gaia_all or c in ctx.start_ids:
                continue
            if g.behavior.get("first_seen") is None:
                continue
            if g.behavior.get("hard_build"):
                continue                       # confirmed villager: never military
            cand.append(c)
        cand.sort()                            # instance_id == spawn order
        if not cand:
            continue
        fsmap = {c: ctx.guesses[c].behavior["first_seen"] for c in cand}
        hmmap = {c: bool(ctx.guesses[c].behavior.get("hard_mil")) for c in cand}
        patmap = {c: bool(ctx.guesses[c].behavior.get("patrols")) for c in cand}
        # Split the FIFO into per-LINE streams and claim them SMALLEST-FIRST: a
        # distinctive line (monk: 2 slots) claims its units before the dominant
        # archery line can absorb them. Each line's match/skip DP only sees the units
        # not yet claimed by a more specific line.
        lines = defaultdict(list)
        for t, u in fifo:
            lines[_line_of(u)].append((t, u))
        # Phase 1 -- LINE: claim units to lines SMALLEST-FIRST with STRICT lag, so the
        # exact-spawn owner wins each slot and a distinctive line is not absorbed by
        # archery. This decides which building-line each unit came from (and its class).
        claimed = {}
        raider_pool = len(lines.get("cav", [])) + len(lines.get("inf", []))
        for L in sorted(lines, key=lambda L: len(lines[L])):
            fifo_L = lines[L]
            ftL = [t for t, _ in fifo_L]
            fuL = [u for _, u in fifo_L]
            pool = [c for c in cand if c not in claimed]
            # A patrol-microd unit is a mobile raider (scout/cav/infantry). A set-and-fire
            # siege/monk line should not absorb it -- UNLESS that line is the player's main
            # army (mass hussite/monk push). Fence patrollers out of a SMALL siege/monk line
            # only when cav+inf raider production outnumbers it, so it can't steal raiders
            # from the cav/inf line they belong to. (Unified, no per-player branch.)
            if L in ("siege", "monk") and len(fifo_L) >= 4 and raider_pool > len(fifo_L):
                pool = [c for c in pool if not patmap[c]]
            if not pool:
                continue
            fsL = [fsmap[c] for c in pool]
            hmL = [hmmap[c] for c in pool]
            mm = _match_dp(pool, fsL, hmL, ftL, fuL, TOL, SKIP, EPS, BIG, pack=False, strict=True)
            for c in mm:
                claimed[c] = L
        # Phase 2 -- TYPE: within each line, re-align its claimed units by EARLIEST-
        # PACKING (every time-valid slot equal), so a held unit takes its true early
        # slot instead of stealing a later same-line slot of another type via low lag.
        byline = defaultdict(list)
        for c, L in claimed.items():
            byline[L].append(c)
        for L, cids in byline.items():
            fifo_L = lines[L]
            ftL = [t for t, _ in fifo_L]
            fuL = [u for _, u in fifo_L]
            cs = sorted(cids)
            fsL = [fsmap[c] for c in cs]
            hmL = [True] * len(cs)
            mm = _match_dp(cs, fsL, hmL, ftL, fuL, TOL, SKIP, EPS, BIG, pack=True)
            for c in cs:
                g = ctx.guesses[c]
                g.type = mm.get(c, fuL[0])
                g.type_conf = CONF["squad_type"]
                g.cls = "military"
                g.cls_conf = max(g.cls_conf, CONF["squad_type"])
                matched_all.add(c)
        # Leftover-raider rescue: a candidate the primary alignment SKIPPED that attacked
        # an enemy building is ~85% military in truth (a raiding scout/militia the soft skip
        # dropped to villager). Tolerate a FEW phantom gathers (co-selected with villagers
        # right-clicking a resource) by requiring building-attacks to dominate (ab>=2*gh).
        # Leftover-SCOUT rescue: a skipped candidate that ONLY moves -- scouts/lures but never
        # gathers/builds/attacks-a-building -- is a scout/eagle dropped to villager. To avoid
        # grabbing a real villager from a select-all ball, require a SMALL co-command squad
        # with a military member and NO hard-villager (a real scouting pack). Neither branch
        # disturbs the primary one-to-one alignment (we only rescue units the DP left behind).
        SCOUT_MOVES = 5
        SCOUT_SQUAD_MAX = 10
        if M:
            sq_members = defaultdict(list)
            for mm_, gm in ctx.guesses.items():
                if gm.squad_id is not None:
                    sq_members[gm.squad_id].append(mm_)
            sq_mil_type = {}
            for sid, mem in sq_members.items():
                votes = Counter(ctx.guesses[m].type for m in mem
                                if ctx.guesses[m].cls == "military"
                                and ctx.guesses[m].type not in GENERIC_TYPES)
                if votes:
                    sq_mil_type[sid] = votes.most_common(1)[0][0]
            for c in cand:
                if c in claimed:
                    continue
                g = ctx.guesses[c]
                b = g.behavior
                ab = b.get("attacks_building", 0)
                gh = b.get("gathers", 0)
                raider = ab >= 1 and ab >= 2 * gh
                scout = (not raider and not gh and not b.get("builds")
                         and not ab and b.get("moves", 0) >= SCOUT_MOVES)
                rescued_type = None
                if scout:
                    sid = g.squad_id
                    if sid is None:
                        continue
                    mates = sq_members.get(sid, [])
                    if len(mates) > SCOUT_SQUAD_MAX:
                        continue
                    has_mil = any(ctx.guesses[m].cls == "military" for m in mates)
                    has_hard_vil = any(ctx.guesses[m].cls == "villager"
                                       and ctx.guesses[m].cls_conf >= CONF["hard_class"]
                                       for m in mates)
                    if not has_mil or has_hard_vil:
                        continue
                    rescued_type = sq_mil_type.get(sid)
                elif not raider:
                    continue
                if rescued_type is None:
                    fs = b["first_seen"]
                    k = bisect.bisect_right(ft, fs + TOL) - 1
                    if k < 0:
                        k = 0
                    rescued_type = fu[k]
                g.type = rescued_type
                g.type_conf = CONF["idrank_type"]
                g.cls = "military"
                g.cls_conf = max(g.cls_conf, CONF["squad_type"])
                matched_all.add(c)
    return matched_all


def _match_dp(cand, fs, hardmil, ft, fu, TOL, SKIP, EPS, BIG, pack, strict=False):
    """Order-preserving match/skip DP. Returns {cid: slot_type}.
      - match unit i -> slot j: cost 0 if pack-or-hardmil (earliest slot wins via the
        EPS skip cost), else the command lag (gates ambiguous units to nearby slots).
      - skip unit i: cost SKIP (BIG for a hard-military unit that must occupy a slot).
      - skip slot j: cost EPS (favours packing units onto their earliest valid slots)."""
    N, M = len(cand), len(ft)
    if N == 0 or M == 0:
        return {}
    INF = float("inf")
    dp = [[INF] * (M + 1) for _ in range(N + 1)]
    bt = [[0] * (M + 1) for _ in range(N + 1)]   # 0 skip-slot, 1 match, 2 skip-unit
    dp[0][0] = 0.0
    for j in range(1, M + 1):
        dp[0][j] = j * EPS
    for i in range(1, N + 1):
        su = BIG if hardmil[i - 1] else SKIP
        fsi = fs[i - 1]
        # strict: cost is the command lag for EVERYONE, so the unit that spawned just
        # before a slot (lowest lag) wins it -- the exact-spawn true owner beats a
        # held concurrent unit. Used for per-line claiming where stealing a slot means
        # a cross-line type error.
        free = (pack or hardmil[i - 1]) and not strict
        di, dim1, bti = dp[i], dp[i - 1], bt[i]
        di[0] = dim1[0] + su
        bti[0] = 2
        for j in range(1, M + 1):
            best = dim1[j] + su
            arg = 2
            v0 = di[j - 1] + EPS
            if v0 < best:
                best = v0
                arg = 0
            lag = fsi - ft[j - 1]
            if lag >= -TOL:
                mc = dim1[j - 1] + (0.0 if free else (lag if lag > 0 else 0.0))
                if mc < best:
                    best = mc
                    arg = 1
            di[j] = best
            bti[j] = arg
    i, j = N, M
    out = {}
    while i > 0 or j > 0:
        a = bt[i][j]
        if a == 1:
            out[cand[i - 1]] = fu[j - 1]
            i -= 1
            j -= 1
        elif a == 2:
            i -= 1
        else:
            j -= 1
    return out


UB_SNAP_TOL = 12.0   # FIFO slot may run a little late vs the true spawn; allow slack
UB_PACK_TOL = 200.0  # max FIFO-vs-ub drift when packing a cohort (p100 observed ~175)


def _cohort_snap(ctx, units_fs, PT, PU, iso, iso_gate, TOL, pack=True):
    """FIFO snap with COHORT packing. units_fs = [(cid, fs)] for one player.

    Singleton fs: keep the classic isolation-gated snap (last slot <= fs+TOL).
    A cohort (>=2 units sharing one first-command timestamp) is a mass command
    whose first-timers are the most recent production, so in id order they occupy
    CONSECUTIVE production slots ending at the last slot before the command. Pack
    them backward (largest id -> latest slot); a member whose reached slot predates
    its spawn upper bound by more than the FIFO drift allowance is a stale unit
    swept into the wave (long-idle), not new production -- skip it, consume no slot.
    Returns {cid: slot_index}."""
    ubf = _ub_fn(ctx)
    by_fs = defaultdict(list)
    for c, fs in units_fs:
        by_fs[fs].append(c)
    out = {}
    for fs, mem in by_fs.items():
        k = bisect.bisect_right(PT, fs + TOL) - 1
        if k < 0:
            continue
        if len(mem) == 1 or not pack:
            if iso[k] >= iso_gate:
                for c in mem:
                    out[c] = k
            continue
        j = k
        for c in sorted(mem, reverse=True):
            if j < 0:
                break
            if PT[j] <= ubf(c) + UB_PACK_TOL:
                if iso[j] >= iso_gate:   # only trust isolated slots, like the classic snap
                    out[c] = j
                j -= 1                   # the slot is consumed either way
            # else: stale unit mass-selected into the wave -- no snap, no slot used
    return out


def _ub_fn(ctx):
    """Cached id-spine spawn upper-bound lookup (see _first_refs): ub(cid) is the
    earliest time any id >= cid was referenced, so cid spawned at or before ub(cid).
    A FIFO snap onto a slot later than ub+tol is provably impossible."""
    cached = getattr(ctx, "_ub_cache", None)
    if cached is None:
        ref_ids, ref_ubs = _first_refs(ctx)

        def cached(cid, _ids=ref_ids, _ubs=ref_ubs):
            k = bisect.bisect_left(_ids, cid)
            return _ubs[k] if k < len(_ids) else float("inf")

        ctx._ub_cache = cached
    return cached


def refine_military(ctx, iso_gate=14.0, TOL=4.0, smooth_thresh=0.6):
    """UNIFIED class+type assignment (same for every player):
      1. align_production: match/skip DP -> class + base type from the FIFO.
      2. co-command smoothing: snap a HOMOGENEOUS squad to its majority type -- this
         corrects held units whose command lag drifted them off their FIFO slot (a
         defensive ball is commanded together, so it is homogeneous); a genuinely
         mixed squad has no majority and is left to the alignment.
      3. FIFO-isolation override: a matched unit whose spawn time lands in a clean
         single-type production run IS that type (rescues time-separated minorities
         like militia that the order-DP can drift on)."""
    matched = align_production(ctx)
    # 2. co-command smoothing of homogeneous squads
    members = defaultdict(list)
    for c in matched:
        sid = ctx.guesses[c].squad_id
        if sid is not None:
            members[sid].append(c)
    for mem in members.values():
        votes = Counter(ctx.guesses[c].type for c in mem)
        dom, dn = votes.most_common(1)[0]
        if dn / sum(votes.values()) >= smooth_thresh:
            for c in mem:
                ctx.guesses[c].type = dom
    players = set(ctx.guesses[c].player for c in matched)
    for player in players:
        pm = sorted(ctx.prod_mil.get(player, []))
        PT = [t for t, _ in pm]
        PU = [u for _, u in pm]
        if not PT:
            continue
        iso = [min((abs(PT[x] - PT[k]) for x in range(len(PT)) if PU[x] != PU[k]),
                   default=float("inf")) for k in range(len(PT))]
        units_fs = []
        for c in matched:
            if ctx.guesses[c].player != player:
                continue
            fs = ctx.guesses[c].behavior.get("first_seen")
            if fs is None:
                continue
            units_fs.append((c, fs))
        # NOTE: cohort PACKING (pack=True) was evaluated and reverted: it fixes
        # mass-command clusters (train militia +2) but mis-packs continuously
        # commanded streams (train scouts/comps -4, claims-tracking variant -6).
        for c, k in _cohort_snap(ctx, units_fs, PT, PU, iso, iso_gate, TOL,
                                 pack=False).items():
            ctx.guesses[c].type = PU[k]
            ctx.guesses[c].type_conf = CONF["hard_class"]

    # MONK override (unified, no per-player branch). A meso monk heals/blesses at its
    # monastery and converts enemy units, but never builds, gathers, or attack-moves --
    # so the spawn-order FIFO alignment (which matches on first-command lag) hands its
    # slot to a same-time eagle scout, leaving the monk typed eaglescout or villager.
    # Recover it from behaviour: the player produced monks, the unit ordered its OWN
    # monastery (bld_order = relic/heal garrison), repeatedly "attacked" enemy mobiles
    # (attacks_building = the convert order), and never built/gathered. The conjunction
    # is monk-exclusive across all labelled games (0 false positives).
    monk_players = {p for p, comp in ctx.prod_mil.items()
                    if any(u == "monk" for _, u in comp)}
    for c, g in ctx.guesses.items():
        if c in ctx.building_ids or c in ctx.gaia_all or c in ctx.start_ids:
            continue
        b = g.behavior
        if g.player not in monk_players or b.get("builds") or b.get("gathers") or b.get("hard_build"):
            continue
        strong = b.get("bld_order", 0) >= 1 and b.get("attacks_building", 0) >= 5
        # an already-military unit that garrisons its own monastery is a monk even
        # without a logged convert (returning to a building is monk-exclusive among military)
        weak = g.cls == "military" and b.get("bld_order", 0) >= 1
        if strong or weak:
            g.type = "monk"
            g.type_conf = CONF["hard_class"]
            g.cls = "military"
            g.cls_conf = max(g.cls_conf, CONF["hard_class"])


def refine_ball_types(ctx, squads):
    """For BALL players (a heterogeneous mass-select squad mixes hard-villager and
    hard-military, so co-command can't separate types), re-type ALL their military
    with the order-preserving DP alignment to the FIFO stream. Matching by instance_id
    ORDER (lag-free) resolves the dense interleaved production that command-time
    matching blurs -- the ball case where the squad/budget logic fails."""
    HARD = CONF["hard_class"]
    ball_players = set()
    for c in squads:
        hm = any(ctx.guesses[m].cls == "military" and ctx.guesses[m].cls_conf >= HARD for m in c)
        hv = any(ctx.guesses[m].cls == "villager" and ctx.guesses[m].cls_conf >= HARD for m in c)
        if hm and hv:
            ball_players.add(ctx.guesses[c[0]].player)
    for player in ball_players:
        for cid, t in dp_align_player(ctx, player).items():
            ctx.guesses[cid].type = t
            ctx.guesses[cid].type_conf = CONF["squad_type"]


def refine_separable_military(ctx, threshold=0.3):
    """Your pipeline for SEPARABLE players: attribute each military unit to the
    production stream by anchoring its first-command time (instance_id/production
    + correct multiqueue/train-time order), then snap minority squad outliers to
    the squad majority (co-command update). Applied only to players whose military
    is NOT dominated by a mass-select ball (where this fails -> keep current/ball
    handling). On separable play this beats budget-typing."""
    HARD = CONF["hard_class"]
    sm = defaultdict(list)
    for cid, g in ctx.guesses.items():
        if g.squad_id is not None:
            sm[g.squad_id].append(cid)
    ball = set()
    for mem in sm.values():
        hm = any(ctx.guesses[m].cls == "military" and ctx.guesses[m].cls_conf >= HARD for m in mem)
        hv = any(ctx.guesses[m].cls == "villager" and ctx.guesses[m].cls_conf >= HARD for m in mem)
        if hm and hv:
            ball |= set(mem)
    by_player = defaultdict(list)
    for cid, g in ctx.guesses.items():
        if g.cls == "military" and cid not in ctx.building_ids and cid not in ctx.gaia_all:
            by_player[g.player].append(cid)
    for player, mil in by_player.items():
        if not mil or sum(c in ball for c in mil) / len(mil) >= threshold:
            continue   # ball-blob player -> keep current/ball-refined handling
        pm = sorted(ctx.prod_mil.get(player, []))
        if not pm:
            continue
        PT = [c for c, _ in pm]; PU = [t for _, t in pm]    # FIFO spawn times (sec) + types
        # A unit's spawn time is the LAST FIFO completion at or before its first
        # command (a unit is only commanded after it spawns -> lag is never negative,
        # so "last-before" lands on its own slot; "nearest" would wrongly grab the
        # next unit that spawned during the command lag). A small +tolerance absorbs
        # the FIFO's own few-second prediction error. No co-command re-homogenizing.
        # isolation[k] = gap from slot k to the nearest DIFFERENT-typed slot. A slot
        # in a clean single-type run is trustworthy; one wedged among other types
        # (a hussite amid archers) is not -- leave those to the squad typing.
        isolation = []
        for k in range(len(PT)):
            isolation.append(min((abs(PT[x] - PT[k]) for x in range(len(PT)) if PU[x] != PU[k]),
                                 default=float("inf")))
        TOL, GATE = 4.0, 14.0
        units_fs = []
        for c in mil:
            fs = ctx.guesses[c].behavior.get("first_seen")
            if fs is None:
                continue
            units_fs.append((c, fs))
        for c, k in _cohort_snap(ctx, units_fs, PT, PU, isolation, GATE, TOL,
                                 pack=False).items():
            ctx.guesses[c].type = PU[k]
            ctx.guesses[c].type_conf = CONF["hard_class"]


def finalize(ctx):
    """Stage 5: class-aware fallback -- a unit we know is MILITARY but couldn't
    type still gets the player's dominant military type, never bare 'unit'."""
    dom = {}
    for player, comp in ctx.prod_mil.items():
        c = Counter(t for _, t in comp)
        if c:
            dom[player] = c.most_common(1)[0][0]
    for g in ctx.guesses.values():
        if g.type in GENERIC_TYPES:
            if g.cls == "villager":
                _set_type(g, "villager", CONF["fallback"], "fallback")
            elif g.cls == "military" and g.player in dom:
                _set_type(g, dom[g.player], CONF["fallback"], "fallback")


# --- id-spine global assignment ------------------------------------------------
# Per player, the sequence of new instance_ids (ascending) is EXACTLY the spawn
# order (verified: 0 inversions vs gRPC created_ms on every labelled game), and the
# production model's slot stream is the time-ordered list of what was produced. So
# typing is a global monotone alignment problem: match units (id order) to slots
# (time order) with skips on both sides, solved with one DP per player over the FULL
# stream (villagers + military together -- villager hard-pins segment the military
# sequence, which the old military-only aligner threw away).

SPINE = {
    "NEG_TOL": 25.0,    # model lateness allowance before "slot after first ref" costs
    "W_LATE": 0.12,     # per-second cost for slot_t exceeding the unit's upper bound
    # class-dependent idle windows (cmd-delay p90: military ~60-100s, villager ~250-420s)
    "FREE_MIL": 60.0,   # free idle window before a military unit's first command
    "W_LAG_MIL": 0.04,  # per-second lag cost on military slots beyond the window
    "CAP_MIL": 12.0,    # lag-cost cap (rare units idle 20+ min before first command)
    "FREE_VIL": 150.0,
    "W_LAG_VIL": 0.012,
    "CAP_VIL": 8.0,
    "EPS_SLOT": 0.05,   # cost to leave a produced slot uncommanded
    "SKIP_U": 18.0,     # cost to leave a commanded unit unexplained (converted etc.)
    "W_SOFT_VIL": 7.0,  # a no-eco-evidence commanded unit on a villager slot (~93% mil)
    "W_COCMD_M": 8.0,   # violating a co-command-propagated MILITARY class
    "W_GATHER": 2.5,    # gather hint (contaminated) violated by a military slot
    "W_MONK": 30.0,     # behavioral monk pin on a non-monk slot
}


def _first_refs(ctx):
    """Global (cross-player) first-reference time per canonical id. Because ids are
    allocated from one global monotone counter, ub(id) = min first-reference over all
    ids >= id upper-bounds the SPAWN time of id: if any LATER id existed at time t,
    this id existed before t too. Sources: own first command, building first queue,
    and command target references."""
    refs = {}

    def note(cid, t):
        if 0 < cid < SHIFT_THRESHOLD and (cid not in refs or t < refs[cid]):
            refs[cid] = t

    for cid, g in ctx.guesses.items():
        fs = g.behavior.get("first_seen")
        if fs is not None:
            note(cid, fs)
    for b, q in ctx.queues.items():
        if q:
            note(b, min(t for t, _ in q))
    for a in ctx.match.actions:
        if not a.player:
            continue
        p = a.payload or {}
        t = a.timestamp.total_seconds()
        tgt = p.get("target_id")
        if isinstance(tgt, int):
            note(ctx.canon(tgt), t)
    items = sorted(refs.items())
    ids = [i for i, _ in items]
    ubs = [t for _, t in items]
    for k in range(len(ubs) - 2, -1, -1):
        if ubs[k + 1] < ubs[k]:
            ubs[k] = ubs[k + 1]
    return ids, ubs


def _spine_candidates(ctx, player):
    return sorted(c for c, g in ctx.guesses.items()
                  if g.player == player
                  and c not in ctx.building_ids and c not in ctx.gaia_all
                  and c not in ctx.start_ids
                  and g.behavior.get("first_seen") is not None)


def _monk_pin(ctx, g):
    """Behavioral monk signature (see monk override): garrisons its own monastery and
    repeatedly 'attacks' enemy mobiles (convert orders), never builds/gathers."""
    b = g.behavior
    if b.get("builds") or b.get("gathers") or b.get("hard_build"):
        return False
    return b.get("bld_order", 0) >= 1 and b.get("attacks_building", 0) >= 5


def spine_align(ctx):
    """Global per-player monotone assignment of commanded units to the full
    production stream. Returns set of matched unit ids (military-slot matches)."""
    P = SPINE
    ref_ids, ref_ubs = _first_refs(ctx)

    def ub_of(cid):
        k = bisect.bisect_left(ref_ids, cid)
        return ref_ubs[k] if k < len(ref_ids) else float("inf")

    matched_mil = set()
    INF = float("inf")
    players = set(g.player for g in ctx.guesses.values() if g.player)
    monk_players = {pl for pl, comp in ctx.prod_mil.items()
                    if any(u == "monk" for _, u in comp)}
    for player in players:
        slots = sorted(ctx.prod_full.get(player, []))
        cand = _spine_candidates(ctx, player)
        N, M = len(cand), len(slots)
        if N == 0 or M == 0:
            continue
        st = [t for t, _ in slots]
        su = [u for _, u in slots]
        s_vil = [u == "villager" for u in su]
        # per-unit evidence
        U = []          # spawn-time upper bound
        hardV = []
        hardM = []
        soft = []       # signed class hint weight: + leans villager, - leans military
        monkp = []
        for c in cand:
            g = ctx.guesses[c]
            b = g.behavior
            fs = b["first_seen"]
            U.append(min(fs, ub_of(c)))
            hb, hm = bool(b.get("hard_build")), bool(b.get("hard_mil"))
            if hb and hm:               # conflicted id -> no hard constraint
                hb = hm = False
            hardV.append(hb)
            hardM.append(hm)
            # signed class hint: + costs military slots, - costs villager slots.
            # Measured on labelled games: a commanded unit with NO eco evidence is ~93%
            # military; the gather hint leans villager but is contaminated (mass-select);
            # cocmd-propagated VILLAGER class is ~50/50 noise (ignored), cocmd MILITARY
            # is reliable.
            w = 0.0
            if not hb and not hm:
                cocmdV = g.cls == "villager" and g.cls_conf >= CONF["cocmd_class"]
                cocmdM = g.cls == "military" and g.cls_conf >= CONF["cocmd_class"]
                if b.get("gathers"):
                    w = P["W_GATHER"]
                elif cocmdM:
                    w = -P["W_COCMD_M"]
                elif cocmdV:
                    w = 0.0
                else:
                    w = -P["W_SOFT_VIL"]
            soft.append(w)
            monkp.append(player in monk_players and _monk_pin(ctx, g))

        def mcost(i, j):
            vil = s_vil[j]
            if hardV[i] and not vil:
                return INF
            if hardM[i] and vil:
                return INF
            c = 0.0
            if soft[i] > 0 and not vil:
                c += soft[i]
            elif soft[i] < 0 and vil:
                c -= soft[i]
            if monkp[i] and su[j] != "monk":
                c += P["W_MONK"]
            d = st[j] - U[i]
            if d > P["NEG_TOL"]:
                c += P["W_LATE"] * (d - P["NEG_TOL"])
            else:
                lag = -d
                if vil:
                    if lag > P["FREE_VIL"]:
                        c += min(P["W_LAG_VIL"] * (lag - P["FREE_VIL"]), P["CAP_VIL"])
                elif lag > P["FREE_MIL"]:
                    c += min(P["W_LAG_MIL"] * (lag - P["FREE_MIL"]), P["CAP_MIL"])
            return c

        EPS, SKIP_U = P["EPS_SLOT"], P["SKIP_U"]
        prev = [j * EPS for j in range(M + 1)]
        bts = [None] * (N + 1)
        for i in range(1, N + 1):
            cur = [0.0] * (M + 1)
            bt = bytearray(M + 1)
            cur[0] = prev[0] + SKIP_U
            bt[0] = 2
            ii = i - 1
            for j in range(1, M + 1):
                best = prev[j] + SKIP_U
                arg = 2
                v = cur[j - 1] + EPS
                if v < best:
                    best, arg = v, 0
                mc = mcost(ii, j - 1)
                if mc < INF:
                    mc += prev[j - 1]
                    if mc < best:
                        best, arg = mc, 1
                cur[j] = best
                bt[j] = arg
            bts[i] = bt
            prev = cur
        # backtrace
        i, j = N, M
        assign = {}
        while i > 0:
            a = bts[i][j]
            if a == 1:
                assign[cand[i - 1]] = j - 1
                i -= 1
                j -= 1
            elif a == 2:
                i -= 1
            else:
                j -= 1
        # apply
        for c in cand:
            g = ctx.guesses[c]
            j = assign.get(c)
            if j is not None:
                t = su[j]
                g.type = t
                g.type_conf = CONF["squad_type"]
                g.cls = "villager" if t == "villager" else "military"
                g.cls_conf = max(g.cls_conf, CONF["squad_type"])
                if t != "villager":
                    matched_mil.add(c)
            else:
                # unexplained commanded unit: keep a confident prior class; else villager
                if g.cls == "military" and g.cls_conf >= CONF["cocmd_class"]:
                    pass            # finalize will give the dominant military type
                else:
                    g.type = "villager"
                    g.type_conf = CONF["idrank_type"]
                    if g.cls_conf < CONF["hard_class"]:
                        g.cls = "villager"
                        g.cls_conf = max(g.cls_conf, CONF["idrank_type"])
    return matched_mil


SPINE_SMOOTH = True


def spine_post(ctx, matched_mil, smooth_thresh=0.6):
    """Post-passes: (1) co-command squad type smoothing over military-matched units;
    (2) behavioral monk override (verbatim from refine_military)."""
    members = defaultdict(list)
    for c in matched_mil:
        sid = ctx.guesses[c].squad_id
        if sid is not None:
            members[sid].append(c)
    if SPINE_SMOOTH:
        for mem in members.values():
            votes = Counter(ctx.guesses[c].type for c in mem)
            dom, dn = votes.most_common(1)[0]
            if dn / sum(votes.values()) >= smooth_thresh:
                for c in mem:
                    ctx.guesses[c].type = dom
    # monk override
    monk_players = {p for p, comp in ctx.prod_mil.items()
                    if any(u == "monk" for _, u in comp)}
    for c, g in ctx.guesses.items():
        if c in ctx.building_ids or c in ctx.gaia_all or c in ctx.start_ids:
            continue
        b = g.behavior
        if g.player not in monk_players or b.get("builds") or b.get("gathers") or b.get("hard_build"):
            continue
        strong = b.get("bld_order", 0) >= 1 and b.get("attacks_building", 0) >= 5
        weak = g.cls == "military" and b.get("bld_order", 0) >= 1
        if strong or weak:
            g.type = "monk"
            g.type_conf = CONF["hard_class"]
            g.cls = "military"
            g.cls_conf = max(g.cls_conf, CONF["hard_class"])


def _run(match):
    """Run the full pipeline; returns the Context.

    HYBRID: the local/greedy typing stack (assign_types + refine_military) is
    measurably better wherever it reaches squad-tier confidence or above, while the
    global monotone id-spine DP is measurably better on the leftovers (idrank/
    fallback-tier units -- the C_forced/D_guess evidence tiers), where it converts
    villager<->military coin flips into id-interval-forced assignments. So: run
    both on the same evidence snapshot and merge by baseline confidence tier."""
    ctx = build_context(match)
    behavioral_labels(ctx)
    weight = cocommand_graph(ctx)
    propagate_class(ctx, weight)
    production_timeline(ctx)
    squads = form_squads(ctx, weight)   # sets squad_id (used by both branches)
    pre = {cid: (g.type, g.type_conf, g.cls, g.cls_conf)
           for cid, g in ctx.guesses.items()}
    # branch A: baseline local typing
    assign_types(ctx, squads)
    refine_military(ctx)
    base = {cid: (g.type, g.type_conf, g.cls, g.cls_conf)
            for cid, g in ctx.guesses.items()}
    # branch B: global id-spine alignment (restore the pre-typing snapshot first)
    for cid, (t, tc, c, cc) in pre.items():
        g = ctx.guesses[cid]
        g.type, g.type_conf, g.cls, g.cls_conf = t, tc, c, cc
    matched = spine_align(ctx)
    spine_post(ctx, matched)
    spine_t = {cid: g.type for cid, g in ctx.guesses.items()}
    # merge: baseline wins at squad tier and above; spine wins below
    for cid, (t, tc, c, cc) in base.items():
        if t not in GENERIC_TYPES and tc >= CONF["squad_type"]:
            g = ctx.guesses[cid]
            g.type, g.type_conf, g.cls, g.cls_conf = t, tc, c, cc
    # evidence-mined arbitration overrides (validated on g0+train disagreements):
    SIEGE = {"mangonel", "scorpion", "trebuchet", "batteringram", "bombardcannon",
             "armoredelephant", "siegetower"}
    for cid, g in ctx.guesses.items():
        if cid in ctx.building_ids or cid in ctx.gaia_all or cid in ctx.start_ids:
            continue
        b = g.behavior
        if b.get("first_seen") is None or b.get("hard_mil") or b.get("hard_build"):
            continue
        st = spine_t.get(cid)
        # A) siege slots are sparse and slow-trained; the fs-time FIFO snap routinely
        #    lands a siege unit on the busy adjacent slot, while the global monotone
        #    spine places it right. When the spine says siege and the local stack
        #    says non-siege, trust the spine.
        if st in SIEGE and g.type not in SIEGE:
            g.type = st
            g.type_conf = CONF["squad_type"]
            g.cls = "military"
            g.cls_conf = max(g.cls_conf, CONF["squad_type"])
            continue
        # B) eco-pinned villager: repeated gathering with near-zero tactical activity
        #    is villager-exclusive (mass-select phantom gathers come with 10+ moves).
        if (b.get("gathers", 0) >= 1 and b.get("moves", 0) <= 3
                and b.get("attacks_building", 0) <= 2 and g.type != "villager"):
            g.type = "villager"
            g.type_conf = CONF["squad_type"]
            g.cls = "villager"
            g.cls_conf = max(g.cls_conf, CONF["squad_type"])
            continue
        # C) deposit/garrison-only unit: orders its OWN buildings repeatedly, never
        #    gathers, near-zero movement -- a tasked-to-garrison villager, not the
        #    siege/military type the FIFO snap claims (real monks move 70+ times).
        if (b.get("bld_order", 0) >= 2 and not b.get("gathers")
                and b.get("moves", 0) <= 6 and g.type != "monk"
                and g.type != "villager"):
            g.type = "villager"
            g.type_conf = CONF["squad_type"]
            g.cls = "villager"
            g.cls_conf = max(g.cls_conf, CONF["squad_type"])
    finalize(ctx)
    return ctx


def classify(match):
    """Run the full pipeline. Returns {canonical instance_id: UnitGuess}."""
    return _run(match).guesses


def build_type_map(match):
    """For process_replay: returns (flat, remap).

    flat  = {canonical instance_id: type_string} (class-only units -> 'villager'
            or 'unit').
    remap = {raw shifted id: canonical id} so the caller can canonicalize the
            ids it sees (collapsing the SPECIAL/UNGARRISON phantom duplicates).
    """
    ctx = _run(match)
    flat = {}
    for cid, g in ctx.guesses.items():
        # buildings and gaia (resources/herdables) are not mobile units -- the
        # visualizer renders them from building/gaia data, so don't emit a unit type.
        if cid in ctx.building_ids or cid in ctx.gaia_all:
            continue
        t = g.type if g.type not in GENERIC_TYPES else ("villager" if g.cls == "villager" else "unit")
        flat[cid] = t
    remap = {o: (o >> 8) for o in ctx.shifted}
    return flat, remap
